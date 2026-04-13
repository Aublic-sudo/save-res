# Copyright (c) 2025 devgagan : https://github.com/devgaganin.
# Licensed under the GNU General Public License v3.0.
# See LICENSE file in the repository root for full license text.

import os
import re
import time
import asyncio
import json
from typing import Dict, Any, Optional

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import UserNotParticipant

from config import API_ID, API_HASH, LOG_GROUP, STRING, FORCE_SUB, FREEMIUM_LIMIT, PREMIUM_LIMIT
from utils.func import get_user_data, screenshot, thumbnail, get_video_metadata
from utils.func import get_user_data_key, process_text_with_rules, is_premium_user, E
from shared_client import app as X
from plugins.settings import rename_file
from plugins.start import subscribe as sub
from utils.custom_filters import login_in_progress
from utils.encrypt import dcs

Y = None if not STRING else __import__('shared_client').userbot

# ── State dicts ───────────────────────────────────────────────────────────────
Z             = {}   # batch / single conversation state
P             = {}   # progress tracker (per message id)
UB            = {}   # user bot clients cache
UC            = {}   # user session clients cache
emp           = {}   # empty-message flags per channel
BOTCHAT_STATE = {}   # /botchat multi-step state

# ── Active batch tracking ─────────────────────────────────────────────────────
ACTIVE_USERS: Dict[str, Any] = {}
ACTIVE_USERS_FILE = "active_users.json"


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def sanitize(filename: str) -> str:
    """Strip illegal filesystem characters and limit length."""
    return re.sub(r'[<>:"/\\|?*\']', '_', filename).strip(" .")[:255]


# ─────────────────────────────────────────────────────────────────────────────
#  Active-users persistence
# ─────────────────────────────────────────────────────────────────────────────

def load_active_users() -> dict:
    try:
        if os.path.exists(ACTIVE_USERS_FILE):
            with open(ACTIVE_USERS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


async def save_active_users_to_file():
    try:
        with open(ACTIVE_USERS_FILE, 'w') as f:
            json.dump(ACTIVE_USERS, f)
    except Exception as e:
        print(f"Error saving active users: {e}")


async def add_active_batch(user_id: int, batch_info: Dict[str, Any]):
    ACTIVE_USERS[str(user_id)] = batch_info
    await save_active_users_to_file()


def is_user_active(user_id: int) -> bool:
    return str(user_id) in ACTIVE_USERS


async def update_batch_progress(user_id: int, current: int, success: int):
    uid_str = str(user_id)
    if uid_str in ACTIVE_USERS:
        ACTIVE_USERS[uid_str]["current"] = current
        ACTIVE_USERS[uid_str]["success"] = success
        await save_active_users_to_file()


async def request_batch_cancel(user_id: int) -> bool:
    uid_str = str(user_id)
    if uid_str in ACTIVE_USERS:
        ACTIVE_USERS[uid_str]["cancel_requested"] = True
        await save_active_users_to_file()
        return True
    return False


def should_cancel(user_id: int) -> bool:
    uid_str = str(user_id)
    return uid_str in ACTIVE_USERS and ACTIVE_USERS[uid_str].get("cancel_requested", False)


async def remove_active_batch(user_id: int):
    uid_str = str(user_id)
    if uid_str in ACTIVE_USERS:
        del ACTIVE_USERS[uid_str]
        await save_active_users_to_file()


def get_batch_info(user_id: int) -> Optional[Dict[str, Any]]:
    return ACTIVE_USERS.get(str(user_id))


# Initialise on import
ACTIVE_USERS = load_active_users()


# ─────────────────────────────────────────────────────────────────────────────
#  Dialog updater
# ─────────────────────────────────────────────────────────────────────────────

async def upd_dlg(c) -> bool:
    try:
        async for _ in c.get_dialogs(limit=100):
            pass
        return True
    except Exception as e:
        print(f'Failed to update dialogs: {e}')
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  Message fetcher
# ─────────────────────────────────────────────────────────────────────────────

async def get_msg(c, u, i, d, lt):
    """Fetch a single message from public or private source."""
    try:
        if lt == 'public':
            try:
                xm = await c.get_messages(i, d)
                emp[i] = getattr(xm, "empty", False)
                if emp[i]:
                    try:
                        await u.join_chat(i)
                    except Exception:
                        pass
                    xm = await u.get_messages((await u.get_chat(f"@{i}")).id, d)
                return xm
            except Exception as e:
                print(f'Error fetching public message: {e}')
                return None
        else:
            if not u:
                return None
            try:
                async for _ in u.get_dialogs(limit=50):
                    pass
                chat_id = (i if str(i).startswith('-100')
                           else f'-100{i}' if str(i).isdigit()
                           else i)
                try:
                    peer = await u.resolve_peer(chat_id)
                    if hasattr(peer, 'channel_id'):
                        resolved_id = f'-100{peer.channel_id}'
                    elif hasattr(peer, 'chat_id'):
                        resolved_id = f'-{peer.chat_id}'
                    elif hasattr(peer, 'user_id'):
                        resolved_id = peer.user_id
                    else:
                        resolved_id = chat_id
                    return await u.get_messages(resolved_id, d)
                except Exception:
                    try:
                        chat = await u.get_chat(chat_id)
                        return await u.get_messages(chat.id, d)
                    except Exception:
                        async for _ in u.get_dialogs(limit=200):
                            pass
                        return await u.get_messages(chat_id, d)
            except Exception as e:
                print(f'Private channel error: {e}')
                return None
    except Exception as e:
        print(f'Error fetching message: {e}')
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Bot / user-client getters
# ─────────────────────────────────────────────────────────────────────────────

async def get_ubot(uid):
    """Return a cached (or freshly started) user-owned bot client."""
    bt = await get_user_data_key(uid, "bot_token", None)
    if not bt:
        return None
    if uid in UB:
        return UB[uid]
    try:
        bot = Client(f"user_{uid}", bot_token=bt, api_id=API_ID, api_hash=API_HASH)
        await bot.start()
        UB[uid] = bot
        return bot
    except Exception as e:
        print(f"Error starting bot for user {uid}: {e}")
        return None


async def get_uclient(uid):
    """Return a cached (or freshly started) user session client."""
    ud   = await get_user_data(uid)
    ubot = UB.get(uid)
    cl   = UC.get(uid)
    if cl:
        return cl
    if not ud:
        return ubot or None
    xxx = ud.get('session_string')
    if xxx:
        try:
            ss = dcs(xxx)
            gg = Client(
                f'{uid}_client',
                api_id=API_ID,
                api_hash=API_HASH,
                device_model="v3saver",
                session_string=ss,
            )
            await gg.start()
            await upd_dlg(gg)
            UC[uid] = gg
            return gg
        except Exception as e:
            print(f'User client error: {e}')
            return ubot or Y
    return Y


# ─────────────────────────────────────────────────────────────────────────────
#  Progress callback
# ─────────────────────────────────────────────────────────────────────────────

async def prog(c, t, C, h, m, st):
    global P
    p = c / t * 100
    if   t >= 100 * 1024 * 1024: interval = 10
    elif t >=  50 * 1024 * 1024: interval = 20
    elif t >=  10 * 1024 * 1024: interval = 30
    else:                         interval = 50

    step = int(p // interval) * interval
    if m not in P or P[m] != step or p >= 100:
        P[m]  = step
        c_mb  = c / (1024 * 1024)
        t_mb  = t / (1024 * 1024)
        bar   = '🟢' * int(p / 10) + '🔴' * (10 - int(p / 10))
        elapsed = time.time() - st
        speed = (c / elapsed / (1024 * 1024)) if elapsed > 0 else 0
        eta   = (time.strftime('%M:%S', time.gmtime((t - c) / (speed * 1024 * 1024)))
                 if speed > 0 else '00:00')
        await C.edit_message_text(
            h, m,
            f"__**Pyro Handler...**__\n\n{bar}\n\n"
            f"⚡**__Completed__**: {c_mb:.2f} MB / {t_mb:.2f} MB\n"
            f"📊 **__Done__**: {p:.2f}%\n"
            f"🚀 **__Speed__**: {speed:.2f} MB/s\n"
            f"⏳ **__ETA__**: {eta}\n\n"
            f"**__Powered by Team SPY__**"
        )
        if p >= 100:
            P.pop(m, None)


# ─────────────────────────────────────────────────────────────────────────────
#  Direct send (no download — uses file_id)
# ─────────────────────────────────────────────────────────────────────────────

async def send_direct(c, m, tcid, ft=None, rtmid=None) -> bool:
    """Re-forward a media message using its file_id (fastest path)."""
    try:
        if m.video:
            await c.send_video(tcid, m.video.file_id, caption=ft,
                               duration=m.video.duration, width=m.video.width,
                               height=m.video.height, reply_to_message_id=rtmid)
        elif m.video_note:
            await c.send_video_note(tcid, m.video_note.file_id,
                                    reply_to_message_id=rtmid)
        elif m.voice:
            await c.send_voice(tcid, m.voice.file_id, reply_to_message_id=rtmid)
        elif m.sticker:
            await c.send_sticker(tcid, m.sticker.file_id,
                                 reply_to_message_id=rtmid)
        elif m.audio:
            await c.send_audio(tcid, m.audio.file_id, caption=ft,
                               duration=m.audio.duration,
                               performer=m.audio.performer,
                               title=m.audio.title,
                               reply_to_message_id=rtmid)
        elif m.photo:
            photo_id = (m.photo.file_id if hasattr(m.photo, 'file_id')
                        else m.photo[-1].file_id)
            await c.send_photo(tcid, photo_id, caption=ft,
                               reply_to_message_id=rtmid)
        elif m.document:
            await c.send_document(tcid, m.document.file_id, caption=ft,
                                  file_name=m.document.file_name,
                                  reply_to_message_id=rtmid)
        else:
            return False
        return True
    except Exception as e:
        print(f'Direct send error: {e}')
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  Core message processor
# ─────────────────────────────────────────────────────────────────────────────

async def process_msg(c, u, m, d, lt, uid, i) -> str:
    """Download (if needed) and re-upload a single message."""
    try:
        cfg_chat = await get_user_data_key(d, 'chat_id', None)
        tcid  = d
        rtmid = None
        if cfg_chat:
            if '/' in cfg_chat:
                parts = cfg_chat.split('/', 1)
                tcid  = int(parts[0])
                rtmid = int(parts[1]) if len(parts) > 1 else None
            else:
                tcid = int(cfg_chat)

        # ── Media path ────────────────────────────────────────────────────────
        if m.media:
            orig_text  = m.caption.markdown if m.caption else ''
            proc_text  = await process_text_with_rules(d, orig_text)
            user_cap   = await get_user_data_key(d, 'caption', '')
            ft = (f'{proc_text}\n\n{user_cap}' if proc_text and user_cap
                  else user_cap if user_cap
                  else proc_text)

            # Fast path: public channel → use file_id directly (no download)
            if lt == 'public' and not emp.get(i, False):
                await send_direct(c, m, tcid, ft, rtmid)
                return 'Sent directly.'

            # Download
            st = time.time()
            p  = await c.send_message(d, 'Downloading...')

            if m.video:
                c_name = sanitize(m.video.file_name or f"{time.time()}.mp4")
            elif m.audio:
                c_name = sanitize(m.audio.file_name or f"{time.time()}.mp3")
            elif m.document:
                c_name = sanitize(m.document.file_name or f"{time.time()}")
            elif m.photo:
                c_name = sanitize(f"{time.time()}.jpg")
            else:
                c_name = f"{time.time()}"

            f = await u.download_media(m, file_name=c_name,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st))
            if not f:
                await c.edit_message_text(d, p.id, 'Download failed.')
                return 'Failed.'

            # Rename (if user has a rename template set)
            await c.edit_message_text(d, p.id, 'Renaming...')
            if ((m.video    and m.video.file_name) or
                (m.audio    and m.audio.file_name) or
                (m.document and m.document.file_name)):
                f = await rename_file(f, d, p)

            fsize = os.path.getsize(f) / (1024 * 1024 * 1024)
            th    = thumbnail(d)

            # ── Large file (> 2 GB) via userbot relay ─────────────────────────
            if fsize > 2 and Y:
                st = time.time()
                await c.edit_message_text(d, p.id,
                                          'File > 2 GB — using alternative method...')
                await upd_dlg(Y)
                mtd          = await get_video_metadata(f)
                dur, h, w    = mtd['duration'], mtd['width'], mtd['height']
                th           = await screenshot(f, dur, d)
                send_funcs   = {
                    'video':      Y.send_video,
                    'video_note': Y.send_video_note,
                    'voice':      Y.send_voice,
                    'audio':      Y.send_audio,
                    'photo':      Y.send_photo,
                    'document':   Y.send_document,
                }
                sent = None
                for mtype, func in send_funcs.items():
                    if f.endswith('.mp4'):
                        mtype = 'video'
                    if getattr(m, mtype, None):
                        sent = await func(
                            LOG_GROUP, f,
                            thumb=th   if mtype == 'video' else None,
                            duration=dur if mtype == 'video' else None,
                            height=h   if mtype == 'video' else None,
                            width=w    if mtype == 'video' else None,
                            caption=(ft if m.caption and mtype not in
                                     ['video_note', 'voice'] else None),
                            reply_to_message_id=rtmid,
                            progress=prog,
                            progress_args=(c, d, p.id, st),
                        )
                        break
                if not sent:
                    sent = await Y.send_document(
                        LOG_GROUP, f, thumb=th,
                        caption=ft if m.caption else None,
                        reply_to_message_id=rtmid,
                        progress=prog, progress_args=(c, d, p.id, st),
                    )
                await c.copy_message(d, LOG_GROUP, sent.id)
                os.remove(f)
                await c.delete_messages(d, p.id)
                return 'Done (Large file).'

            # ── Normal upload ─────────────────────────────────────────────────
            await c.edit_message_text(d, p.id, 'Uploading...')
            st = time.time()
            try:
                if m.video or os.path.splitext(f)[1].lower() == '.mp4':
                    mtd       = await get_video_metadata(f)
                    dur, h, w = mtd['duration'], mtd['width'], mtd['height']
                    th        = await screenshot(f, dur, d)
                    await c.send_video(tcid, video=f,
                                       caption=ft if m.caption else None,
                                       thumb=th, width=w, height=h, duration=dur,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st),
                                       reply_to_message_id=rtmid)
                elif m.video_note:
                    await c.send_video_note(tcid, video_note=f,
                                            progress=prog,
                                            progress_args=(c, d, p.id, st),
                                            reply_to_message_id=rtmid)
                elif m.voice:
                    await c.send_voice(tcid, f,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st),
                                       reply_to_message_id=rtmid)
                elif m.sticker:
                    await c.send_sticker(tcid, m.sticker.file_id)
                elif m.audio:
                    await c.send_audio(tcid, audio=f,
                                       caption=ft if m.caption else None,
                                       thumb=th,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st),
                                       reply_to_message_id=rtmid)
                elif m.photo:
                    await c.send_photo(tcid, photo=f,
                                       caption=ft if m.caption else None,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st),
                                       reply_to_message_id=rtmid)
                else:
                    await c.send_document(tcid, document=f,
                                          caption=ft if m.caption else None,
                                          progress=prog,
                                          progress_args=(c, d, p.id, st),
                                          reply_to_message_id=rtmid)
            except Exception as e:
                await c.edit_message_text(d, p.id,
                                          f'Upload failed: {str(e)[:30]}')
                if os.path.exists(f):
                    os.remove(f)
                return 'Failed.'

            os.remove(f)
            await c.delete_messages(d, p.id)
            return 'Done.'

        # ── Text message path ─────────────────────────────────────────────────
        elif m.text:
            await c.send_message(tcid, text=m.text.markdown,
                                 reply_to_message_id=rtmid)
            return 'Sent.'

    except Exception as e:
        return f'Error: {str(e)[:50]}'


# ─────────────────────────────────────────────────────────────────────────────
#  /batch  and  /single  command
# ─────────────────────────────────────────────────────────────────────────────

@X.on_message(filters.command(['batch', 'single']))
async def process_cmd(c, m):
    uid = m.from_user.id
    cmd = m.command[0]

    if FREEMIUM_LIMIT == 0 and not await is_premium_user(uid):
        await m.reply_text(
            "This bot does not provide free services. "
            "Get a subscription from OWNER."
        )
        return

    if await sub(c, m) == 1:
        return

    pro = await m.reply_text('Doing some checks, hold on...')

    if is_user_active(uid):
        await pro.edit('You have an active task. Use /stop to cancel it.')
        return

    ubot = await get_ubot(uid)
    if not ubot:
        await pro.edit('Add your bot with /setbot first.')
        return

    Z[uid] = {'step': 'start' if cmd == 'batch' else 'start_single'}
    await pro.edit(
        'Send the start link...' if cmd == 'batch' else 'Send the link to process.'
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /cancel  and  /stop  command
# ─────────────────────────────────────────────────────────────────────────────

@X.on_message(filters.command(['cancel', 'stop']))
async def cancel_cmd(c, m):
    uid = m.from_user.id
    if is_user_active(uid):
        if await request_batch_cancel(uid):
            await m.reply_text(
                'Cancellation requested. '
                'Batch will stop after the current file completes.'
            )
        else:
            await m.reply_text('Failed to request cancellation. Please try again.')
    else:
        await m.reply_text('No active batch process found.')


# ─────────────────────────────────────────────────────────────────────────────
#  /botchat  command
# ─────────────────────────────────────────────────────────────────────────────

@X.on_message(filters.command("botchat"))
async def botchat_cmd(c, m):
    uid = m.from_user.id

    if await sub(c, m) == 1:
        return

    uc = await get_uclient(uid)
    if not uc:
        await m.reply_text("❌ Please login first using /login")
        return

    BOTCHAT_STATE[uid] = {"step": "select_bot"}
    await m.reply_text("🤖 Send your bot username (the bot you want to use for upload)")


# ─────────────────────────────────────────────────────────────────────────────
#  Unified private-message / text handler
# ─────────────────────────────────────────────────────────────────────────────

_EXCLUDED_CMDS = [
    'start', 'batch', 'cancel', 'login', 'logout', 'stop', 'set',
    'pay', 'redeem', 'gencode', 'single', 'generate', 'keyinfo',
    'encrypt', 'decrypt', 'keys', 'setbot', 'rembot', 'botchat',
]


@X.on_message(
    filters.text & filters.private
    & ~login_in_progress
    & ~filters.command(_EXCLUDED_CMDS)
)
async def text_handler(c, m):
    uid = m.from_user.id

    # ══════════════════════════════════════════════════════════════════════════
    #  BOTCHAT FLOW
    # ══════════════════════════════════════════════════════════════════════════
    if uid in BOTCHAT_STATE:
        state = BOTCHAT_STATE[uid]

        # STEP 1 — receive bot username
        if state["step"] == "select_bot":
            bot_username = m.text.strip().lstrip("@")
            ubot = await get_ubot(uid)
            if not ubot:
                await m.reply_text("❌ Bot not set. Use /setbot first.")
                BOTCHAT_STATE.pop(uid, None)
                return
            state["bot"]  = bot_username
            state["step"] = "limit"
            await m.reply_text("📊 Enter how many messages to fetch (example: 10)")
            return

        # STEP 2 — receive fetch limit
        elif state["step"] == "limit":
            if not m.text.isdigit():
                await m.reply_text("❌ Enter a valid number")
                return
            state["limit"] = int(m.text)
            state["step"]  = "chat"
            await m.reply_text(
                "📥 Now send target chat username (example: Course_adminbot)"
            )
            return

        # STEP 3 — receive chat username → list recent messages
        elif state["step"] == "chat":
            chat           = m.text.strip()
            state["chat"]  = chat
            state["step"]  = "ids"
            uc   = await get_uclient(uid)
            text = "📋 **Recent Messages (Latest First):**\n\n"
            try:
                async for msg in uc.get_chat_history(chat, limit=state["limit"]):
                    mtype = "None"
                    if msg.video:
                        mtype = "VIDEO 🎥"
                    elif msg.document:
                        mtype = "DOCUMENT 📁"
                    caption = (
                        msg.caption.markdown
                        if getattr(msg.caption, "markdown", None)
                        else "No Caption"
                    )
                    text += (
                        f"**ID:** `{msg.id}`\n"
                        f"**Type:** {mtype}\n"
                        f"**Caption:** {caption}\n\n------\n"
                    )
            except Exception:
                await m.reply_text("❌ Cannot access chat (join bot / check username)")
                BOTCHAT_STATE.pop(uid, None)
                return
            await m.reply_text(text + "\n👉 Send IDs like: `123` or `123&124`")
            return

        # STEP 4 — process selected IDs
        elif state["step"] == "ids":
            chat = state["chat"]
            try:
                ids = [int(x.strip()) for x in m.text.split("&")]
            except Exception:
                await m.reply_text("❌ Invalid format. Use: 123 or 123&124")
                return
            ubot   = await get_ubot(uid)
            uc     = await get_uclient(uid)
            status = await m.reply_text(f"🚀 Starting...\n0/{len(ids)}")
            success = 0
            for idx, mid in enumerate(ids, start=1):
                try:
                    msg = await get_msg(ubot, uc, chat, mid, "private")
                    if msg:
                        res = await process_msg(
                            ubot, uc, msg, str(m.chat.id), "private", uid, chat
                        )
                        if "Done" in res or "Sent" in res:
                            success += 1
                        await status.edit_text(f"{idx}/{len(ids)}: {res}")
                    else:
                        await status.edit_text(f"{idx}/{len(ids)}: Message not found")
                except Exception:
                    await status.edit_text(f"{idx}/{len(ids)}: Error")
                await asyncio.sleep(1)
            await m.reply_text(f"✅ Completed: {success}/{len(ids)}")
            BOTCHAT_STATE.pop(uid, None)
            return

    # ══════════════════════════════════════════════════════════════════════════
    #  BATCH / SINGLE FLOW
    # ══════════════════════════════════════════════════════════════════════════
    if uid not in Z:
        return

    s = Z[uid].get('step')

    # ── Step: receive start link for /batch ───────────────────────────────────
    if s == 'start':
        i, d, lt = E(m.text)
        if not i or not d:
            await m.reply_text('Invalid link format.')
            Z.pop(uid, None)
            return
        Z[uid].update({'step': 'count', 'cid': i, 'sid': d, 'lt': lt})
        await m.reply_text('How many messages?')

    # ── Step: receive link for /single ────────────────────────────────────────
    elif s == 'start_single':
        i, d, lt = E(m.text)
        if not i or not d:
            await m.reply_text('Invalid link format.')
            Z.pop(uid, None)
            return
        Z[uid].update({'step': 'process_single', 'cid': i, 'sid': d, 'lt': lt})
        i, s, lt = Z[uid]['cid'], Z[uid]['sid'], Z[uid]['lt']
        pt   = await m.reply_text('Processing...')
        ubot = UB.get(uid)
        if not ubot:
            await pt.edit('Add bot with /setbot first.')
            Z.pop(uid, None)
            return
        uc = await get_uclient(uid)
        if not uc:
            await pt.edit('Cannot proceed without user client.')
            Z.pop(uid, None)
            return
        if is_user_active(uid):
            await pt.edit('Active task exists. Use /stop first.')
            Z.pop(uid, None)
            return
        try:
            msg = await get_msg(ubot, uc, i, s, lt)
            if msg:
                res = await process_msg(ubot, uc, msg, str(m.chat.id), lt, uid, i)
                await pt.edit(f'1/1: {res}')
            else:
                await pt.edit('Message not found.')
        except Exception as e:
            await pt.edit(f'Error: {str(e)[:50]}')
        finally:
            Z.pop(uid, None)

    # ── Step: receive message count for /batch ────────────────────────────────
    elif s == 'count':
        if not m.text.isdigit():
            await m.reply_text('Enter a valid number.')
            return
        count    = int(m.text)
        maxlimit = PREMIUM_LIMIT if await is_premium_user(uid) else FREEMIUM_LIMIT
        if count > maxlimit:
            await m.reply_text(f'Maximum limit is {maxlimit}.')
            return
        Z[uid].update({'step': 'process', 'did': str(m.chat.id), 'num': count})
        i, s, n, lt = (
            Z[uid]['cid'], Z[uid]['sid'],
            Z[uid]['num'], Z[uid]['lt'],
        )
        success = 0
        pt      = await m.reply_text('Processing batch...')
        uc      = await get_uclient(uid)
        ubot    = UB.get(uid)
        if not uc or not ubot:
            await pt.edit('Missing client setup. Use /setbot and /login first.')
            Z.pop(uid, None)
            return
        if is_user_active(uid):
            await pt.edit('Active task exists. Use /stop first.')
            Z.pop(uid, None)
            return
        await add_active_batch(uid, {
            "total": n, "current": 0, "success": 0,
            "cancel_requested": False,
            "progress_message_id": pt.id,
        })
        try:
            for j in range(n):
                if should_cancel(uid):
                    await pt.edit(f'Cancelled at {j}/{n}. Success: {success}')
                    break
                await update_batch_progress(uid, j, success)
                mid = int(s) + j
                try:
                    msg = await get_msg(ubot, uc, i, mid, lt)
                    if msg:
                        res = await process_msg(
                            ubot, uc, msg, str(m.chat.id), lt, uid, i
                        )
                        if 'Done' in res or 'Copied' in res or 'Sent' in res:
                            success += 1
                except Exception as e:
                    try:
                        await pt.edit(f'{j + 1}/{n}: Error — {str(e)[:30]}')
                    except Exception:
                        pass
                await asyncio.sleep(2)   # 2 s gap (was 10 s) — faster batch
            else:
                # `for` completed without `break` → all messages processed
                await m.reply_text(f'Batch Completed ✅  Success: {success}/{n}')
        finally:
            await remove_active_batch(uid)
            Z.pop(uid, None)
