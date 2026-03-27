# Copyright (c) 2025 devgagan : https://github.com/devgaganin.
# Licensed under the GNU General Public License v3.0.
# See LICENSE file in the repository root for full license text.

import os, re, time, asyncio, json, asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
from typing import Dict, Any, Optional

Y = None if not STRING else __import__('shared_client').userbot
Z, P, UB, UC, emp = {}, {}, {}, {}, {}
BOTCHAT_STATE = {}
ACTIVE_USERS = {}
ACTIVE_USERS_FILE = "active_users.json"


# fixed directory file_name problems
def sanitize(filename):
    return re.sub(r'[<>:"/\\|?*\']', '_', filename).strip(" .")[:255]

# Add this function after sanitize() function
def parse_chat_input(text: str):
    """
    Parse chat input: @username, -100chatid, or t.me links
    Returns: (chat_id, thread_id) tuple. thread_id is None for non-topic links
    """
    text = text.strip()
    
    # Pattern 1: https://t.me/c/{chat_id}/{topic_id} (private topic link)
    topic_match = re.match(r'https?://t\.me/c/(\d+)/(\d+)', text)
    if topic_match:
        chat_id = int(f"-100{topic_match.group(1)}")
        thread_id = int(topic_match.group(2))
        return chat_id, thread_id
    
    # Pattern 2: https://t.me/c/{chat_id} (private chat link without topic)
    private_match = re.match(r'https?://t\.me/c/(\d+)/?$', text)
    if private_match:
        chat_id = int(f"-100{private_match.group(1)}")
        return chat_id, None
    
    # Pattern 3: https://t.me/username/{message_id} or https://t.me/username
    public_match = re.match(r'https?://t\.me/([^/]+)(?:/\d+)?$', text)
    if public_match:
        username = public_match.group(1)
        if username.lower() not in ['c', 'joinchat', 'addstickers', 'addemoji']:
            return f"@{username}", None
    
    # Pattern 4: Direct -100chatid input
    if re.match(r'^-100\d+$', text):
        return text, None
    
    # Pattern 5: @username direct input
    if text.startswith('@'):
        return text, None
    
    # Return as-is for other cases (will fail gracefully in get_chat_history)
    return text, None

def load_active_users():
    try:
        if os.path.exists(ACTIVE_USERS_FILE):
            with open(ACTIVE_USERS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception:
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
    if str(user_id) in ACTIVE_USERS:
        ACTIVE_USERS[str(user_id)]["current"] = current
        ACTIVE_USERS[str(user_id)]["success"] = success
        await save_active_users_to_file()


async def request_batch_cancel(user_id: int):
    if str(user_id) in ACTIVE_USERS:
        ACTIVE_USERS[str(user_id)]["cancel_requested"] = True
        await save_active_users_to_file()
        return True
    return False


def should_cancel(user_id: int) -> bool:
    user_str = str(user_id)
    return user_str in ACTIVE_USERS and ACTIVE_USERS[user_str].get(
        "cancel_requested", False)


async def remove_active_batch(user_id: int):
    if str(user_id) in ACTIVE_USERS:
        del ACTIVE_USERS[str(user_id)]
        await save_active_users_to_file()


def get_batch_info(user_id: int) -> Optional[Dict[str, Any]]:
    return ACTIVE_USERS.get(str(user_id))


ACTIVE_USERS = load_active_users()


async def upd_dlg(c):
    try:
        async for _ in c.get_dialogs(limit=100):
            pass
        return True
    except Exception as e:
        print(f'Failed to update dialogs: {e}')
        return False


async def get_msg(c, u, i, d, lt):
    try:
        if lt == 'public':
            try:
                xm = await c.get_messages(i, d)
                emp[i] = getattr(xm, "empty", False)
                if emp[i]:
                    try:
                        await u.join_chat(i)
                    except:
                        pass
                    xm = await u.get_messages((await u.get_chat(f"@{i}")).id,
                                              d)
                return xm
            except Exception as e:
                print(f'Error fetching public message: {e}')
                return None
        else:
            if u:
                try:
                    async for _ in u.get_dialogs(limit=50):
                        pass
                    chat_id = i if str(i).startswith(
                        '-100') else f'-100{i}' if i.isdigit() else i
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
            return None
    except Exception as e:
        print(f'Error fetching message: {e}')
        return None


async def get_ubot(uid):
    bt = await get_user_data_key(uid, "bot_token", None)
    if not bt: return None
    if uid in UB: return UB.get(uid)
    try:
        bot = Client(f"user_{uid}",
                     bot_token=bt,
                     api_id=API_ID,
                     api_hash=API_HASH)
        await bot.start()
        UB[uid] = bot
        return bot
    except Exception as e:
        print(f"Error starting bot for user {uid}: {e}")
        return None


async def get_uclient(uid):
    ud = await get_user_data(uid)
    ubot = UB.get(uid)
    cl = UC.get(uid)
    if cl: return cl
    if not ud: return ubot if ubot else None
    xxx = ud.get('session_string')
    if xxx:
        try:
            ss = dcs(xxx)
            gg = Client(f'{uid}_client',
                        api_id=API_ID,
                        api_hash=API_HASH,
                        device_model="v3saver",
                        session_string=ss)
            await gg.start()
            await upd_dlg(gg)
            UC[uid] = gg
            return gg
        except Exception as e:
            print(f'User client error: {e}')
            return ubot if ubot else Y
    return Y


async def prog(c, t, C, h, m, st):
    global P
    p = c / t * 100
    interval = 10 if t >= 100 * 1024 * 1024 else 20 if t >= 50 * 1024 * 1024 else 30 if t >= 10 * 1024 * 1024 else 50
    step = int(p // interval) * interval
    if m not in P or P[m] != step or p >= 100:
        P[m] = step
        c_mb = c / (1024 * 1024)
        t_mb = t / (1024 * 1024)
        bar = '🟢' * int(p / 10) + '🔴' * (10 - int(p / 10))
        speed = c / (time.time() - st) / (1024 *
                                          1024) if time.time() > st else 0
        eta = time.strftime(
            '%M:%S', time.gmtime(
                (t - c) / (speed * 1024 * 1024))) if speed > 0 else '00:00'
        await C.edit_message_text(
            h, m,
            f"__**Pyro Handler...**__\n\n{bar}\n\n⚡**__Completed__**: {c_mb:.2f} MB / {t_mb:.2f} MB\n📊 **__Done__**: {p:.2f}%\n🚀 **__Speed__**: {speed:.2f} MB/s\n⏳ **__ETA__**: {eta}\n\n**__Powered by @RixieHQ__**"
        )
        if p >= 100: P.pop(m, None)


async def send_direct(c, m, tcid, ft=None, rtmid=None):
    try:
        if m.video:
            await c.send_video(tcid,
                               m.video.file_id,
                               caption=ft,
                               duration=m.video.duration,
                               width=m.video.width,
                               height=m.video.height,
                               reply_to_message_id=rtmid)
        elif m.video_note:
            await c.send_video_note(tcid,
                                    m.video_note.file_id,
                                    reply_to_message_id=rtmid)
        elif m.voice:
            await c.send_voice(tcid,
                               m.voice.file_id,
                               reply_to_message_id=rtmid)
        elif m.sticker:
            await c.send_sticker(tcid,
                                 m.sticker.file_id,
                                 reply_to_message_id=rtmid)
        elif m.audio:
            await c.send_audio(tcid,
                               m.audio.file_id,
                               caption=ft,
                               duration=m.audio.duration,
                               performer=m.audio.performer,
                               title=m.audio.title,
                               reply_to_message_id=rtmid)
        elif m.photo:
            photo_id = m.photo.file_id if hasattr(
                m.photo, 'file_id') else m.photo[-1].file_id
            await c.send_photo(tcid,
                               photo_id,
                               caption=ft,
                               reply_to_message_id=rtmid)
        elif m.document:
            await c.send_document(tcid,
                                  m.document.file_id,
                                  caption=ft,
                                  file_name=m.document.file_name,
                                  reply_to_message_id=rtmid)
        else:
            return False
        return True
    except Exception as e:
        print(f'Direct send error: {e}')
        return False


async def process_msg(c, u, m, d, lt, uid, i):
    try:
        cfg_chat = await get_user_data_key(d, 'chat_id', None)
        tcid = d
        rtmid = None
        if cfg_chat:
            if '/' in cfg_chat:
                parts = cfg_chat.split('/', 1)
                tcid = int(parts[0])
                rtmid = int(parts[1]) if len(parts) > 1 else None
            else:
                tcid = int(cfg_chat)

        if m.media:
            orig_text = m.caption.markdown if m.caption else ''
            proc_text = await process_text_with_rules(d, orig_text)
            user_cap = await get_user_data_key(d, 'caption', '')
            ft = f'{proc_text}\n\n{user_cap}' if proc_text and user_cap else user_cap if user_cap else proc_text

            if lt == 'public' and not emp.get(i, False):
                await send_direct(c, m, tcid, ft, rtmid)
                return 'Sent directly.'

            st = time.time()
            p = await c.send_message(d, 'Downloading...')

            c_name = f"{time.time()}"
            if m.video:
                file_name = m.video.file_name
                if not file_name:
                    file_name = f"{time.time()}.mp4"
                    c_name = sanitize(file_name)
            elif m.audio:
                file_name = m.audio.file_name
                if not file_name:
                    file_name = f"{time.time()}.mp3"
                    c_name = sanitize(file_name)
            elif m.document:
                file_name = m.document.file_name
                if not file_name:
                    file_name = f"{time.time()}"
                    c_name = sanitize(file_name)
            elif m.photo:
                file_name = f"{time.time()}.jpg"
                c_name = sanitize(file_name)

            f = await u.download_media(m,
                                       file_name=c_name,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st))

            if not f:
                await c.edit_message_text(d, p.id, 'Failed.')
                return 'Failed.'

            await c.edit_message_text(d, p.id, 'Renaming...')
            if ((m.video and m.video.file_name)
                    or (m.audio and m.audio.file_name)
                    or (m.document and m.document.file_name)):
                f = await rename_file(f, d, p)

            fsize = os.path.getsize(f) / (1024 * 1024 * 1024)
            th = thumbnail(d)

            if fsize > 2 and Y:
                st = time.time()
                await c.edit_message_text(
                    d, p.id,
                    'File is larger than 2GB. Using alternative method...')
                await upd_dlg(Y)
                mtd = await get_video_metadata(f)
                dur, h, w = mtd['duration'], mtd['width'], mtd['height']
                th = await screenshot(f, dur, d)

                send_funcs = {
                    'video': Y.send_video,
                    'video_note': Y.send_video_note,
                    'voice': Y.send_voice,
                    'audio': Y.send_audio,
                    'photo': Y.send_photo,
                    'document': Y.send_document
                }

                for mtype, func in send_funcs.items():
                    if f.endswith('.mp4'): mtype = 'video'
                    if getattr(m, mtype, None):
                        sent = await func(
                            LOG_GROUP,
                            f,
                            thumb=th if mtype == 'video' else None,
                            duration=dur if mtype == 'video' else None,
                            height=h if mtype == 'video' else None,
                            width=w if mtype == 'video' else None,
                            caption=ft if m.caption
                            and mtype not in ['video_note', 'voice'] else None,
                            reply_to_message_id=rtmid,
                            progress=prog,
                            progress_args=(c, d, p.id, st))
                        break
                else:
                    sent = await Y.send_document(
                        LOG_GROUP,
                        f,
                        thumb=th,
                        caption=ft if m.caption else None,
                        reply_to_message_id=rtmid,
                        progress=prog,
                        progress_args=(c, d, p.id, st))

                await c.copy_message(d, LOG_GROUP, sent.id)
                os.remove(f)
                await c.delete_messages(d, p.id)

                return 'Done (Large file).'

            await c.edit_message_text(d, p.id, 'Uploading...')
            st = time.time()

            try:
                if m.video or os.path.splitext(f)[1].lower() == '.mp4':
                    mtd = await get_video_metadata(f)
                    dur, h, w = mtd['duration'], mtd['width'], mtd['height']
                    th = await screenshot(f, dur, d)
                    await c.send_video(tcid,
                                       video=f,
                                       caption=ft if m.caption else None,
                                       thumb=th,
                                       width=w,
                                       height=h,
                                       duration=dur,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st),
                                       reply_to_message_id=rtmid)
                elif m.video_note:
                    await c.send_video_note(tcid,
                                            video_note=f,
                                            progress=prog,
                                            progress_args=(c, d, p.id, st),
                                            reply_to_message_id=rtmid)
                elif m.voice:
                    await c.send_voice(tcid,
                                       f,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st),
                                       reply_to_message_id=rtmid)
                elif m.sticker:
                    await c.send_sticker(tcid, m.sticker.file_id)
                elif m.audio:
                    await c.send_audio(tcid,
                                       audio=f,
                                       caption=ft if m.caption else None,
                                       thumb=th,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st),
                                       reply_to_message_id=rtmid)
                elif m.photo:
                    await c.send_photo(tcid,
                                       photo=f,
                                       caption=ft if m.caption else None,
                                       progress=prog,
                                       progress_args=(c, d, p.id, st),
                                       reply_to_message_id=rtmid)
                else:
                    await c.send_document(tcid,
                                          document=f,
                                          caption=ft if m.caption else None,
                                          progress=prog,
                                          progress_args=(c, d, p.id, st),
                                          reply_to_message_id=rtmid)
            except Exception as e:
                await c.edit_message_text(d, p.id,
                                          f'Upload failed: {str(e)[:30]}')
                if os.path.exists(f): os.remove(f)
                return 'Failed.'

            os.remove(f)
            await c.delete_messages(d, p.id)

            return 'Done.'

        elif m.text:
            await c.send_message(tcid,
                                 text=m.text.markdown,
                                 reply_to_message_id=rtmid)
            return 'Sent.'
    except Exception as e:
        return f'Error: {str(e)[:50]}'


@X.on_message(filters.command(['batch', 'single']))
async def process_cmd(c, m):
    uid = m.from_user.id
    cmd = m.command[0]

    if FREEMIUM_LIMIT == 0 and not await is_premium_user(uid):
        await m.reply_text(
            "This bot does not provide free servies, get subscription from OWNER"
        )
        return

    if await sub(c, m) == 1: return
    pro = await m.reply_text('Doing some checks hold on...')

    if is_user_active(uid):
        await pro.edit('You have an active task. Use /stop to cancel it.')
        return

    ubot = await get_ubot(uid)
    if not ubot:
        await pro.edit('Add your bot with /setbot first')
        return

    Z[uid] = {'step': 'start' if cmd == 'batch' else 'start_single'}
    await pro.edit(
        f'Send {"start link..." if cmd == "batch" else "link you to process"}.'
    )


@X.on_message(filters.command(['cancel', 'stop']))
async def cancel_cmd(c, m):
    uid = m.from_user.id
    if is_user_active(uid):
        if await request_batch_cancel(uid):
            await m.reply_text(
                'Cancellation requested. The current batch will stop after the current download completes.'
            )
        else:
            await m.reply_text(
                'Failed to request cancellation. Please try again.')
    else:
        await m.reply_text('No active batch process found.')








# ============ CALLBACK HANDLER ============
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ============ CALLBACK HANDLER ============
@X.on_callback_query(filters.regex(r"^filter_(video|doc|all|cancel|explore|download)$"))
async def filter_callback_handler(c, callback_query):
    uid = callback_query.from_user.id
    data = callback_query.data
    
    try:
        if is_user_active(uid):
            await callback_query.answer("Active task! Use /stop first.", show_alert=True)
            return
    except:
        pass
    
    if uid not in BOTCHAT_STATE:
        await callback_query.answer("Session expired.", show_alert=True)
        return
    
    state = BOTCHAT_STATE[uid]
    
    if data == "filter_cancel":
        BOTCHAT_STATE.pop(uid, None)
        await callback_query.message.edit_text("❌ Cancelled.")
        return
    
    # EXPLORE - Show what's in topic
    if data == "filter_explore":
        await callback_query.answer("Exploring topic...", show_alert=False)
        await explore_topic_contents(c, callback_query.message, uid, state)
        return
    
    # Direct download without explore
    if data == "filter_download":
        await callback_query.answer("Starting download...", show_alert=False)
        await start_topic_download(c, callback_query.message, uid)
        return
    
    filter_map = {
        "filter_video": "video",
        "filter_doc": "document", 
        "filter_all": None
    }
    
    selected_filter = filter_map.get(data)
    state["filter"] = selected_filter
    
    filter_name = "Videos" if selected_filter == "video" else "Docs" if selected_filter == "document" else "All"
    
    # Show options
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 EXPLORE (See what's inside)", callback_data="filter_explore")],
        [InlineKeyboardButton(f"⬇️ DOWNLOAD ALL {filter_name.upper()}", callback_data="filter_download")],
        [InlineKeyboardButton("❌ Cancel", callback_data="filter_cancel")]
    ])
    
    await callback_query.message.edit_text(
        f"✅ **Selected:** {filter_name}\n\n"
        f"📌 Topic: `{state.get('thread_id')}`\n\n"
        f"Choose:\n"
        f"• **EXPLORE** - See message IDs first\n"
        f"• **DOWNLOAD** - Start immediately",
        reply_markup=keyboard
    )


# ============ EXPLORE TOPIC - See what's inside ============
async def explore_topic_contents(c, message, uid, state):
    """Show what's inside the topic - message list"""
    chat = state["chat"]
    thread_id = state.get("thread_id")
    selected_filter = state.get("filter")
    
    uc = await get_uclient(uid)
    if not uc:
        await message.reply_text("❌ Client not available")
        return
    
    topic_info = f"\n📌 Topic: `{thread_id}`" if thread_id else ""
    
    # Quick explore - get first 100 messages with details
    explore_msg = await message.reply_text(
        f"🔍 **Exploring Topic**{topic_info}\n"
        f"⏳ Fetching first 100 messages..."
    )
    
    messages_list = []
    media_count = {"video": 0, "document": 0, "photo": 0, "audio": 0, "total": 0}
    
    try:
        async for msg in uc.get_chat_history(chat, limit=100):
            # Topic check
            if thread_id:
                msg_topic = getattr(msg, "message_thread_id", None) or getattr(msg, "reply_to_top_message_id", None)
                if msg_topic != thread_id:
                    continue
            
            # Determine type
            msg_type = "TEXT"
            emoji = "💬"
            
            if msg.video:
                msg_type = "VIDEO"
                emoji = "🎬"
                media_count["video"] += 1
                media_count["total"] += 1
            elif msg.document:
                msg_type = "DOC"
                emoji = "📄"
                media_count["document"] += 1
                media_count["total"] += 1
            elif msg.photo:
                msg_type = "PHOTO"
                emoji = "🖼️"
                media_count["photo"] += 1
                media_count["total"] += 1
            elif msg.audio:
                msg_type = "AUDIO"
                emoji = "🎵"
                media_count["audio"] += 1
                media_count["total"] += 1
            
            # Filter check
            if selected_filter:
                if selected_filter == "video" and not msg.video:
                    continue
                if selected_filter == "document" and not msg.document:
                    continue
            
            # Store
            content = msg.caption or msg.text or "No caption"
            content = str(content)[:50].replace("\n", " ")
            
            messages_list.append({
                "id": msg.id,
                "type": msg_type,
                "emoji": emoji,
                "content": content
            })
            
    except Exception as e:
        await explore_msg.edit_text(f"❌ Error: `{str(e)[:100]}`")
        return
    
    await explore_msg.delete()
    
    if not messages_list:
        await message.reply_text(f"⚠️ No messages found{topic_info}")
        return
    
    # Build preview
    preview_text = f"📋 **Topic Contents**{topic_info}\n"
    preview_text += f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    all_ids = []
    for item in messages_list[:20]:  # Show first 20
        preview_text += f"`{item['id']}` │ {item['emoji']} {item['type']:<6} │ {item['content']}\n"
        all_ids.append(str(item["id"]))
    
    if len(messages_list) > 20:
        preview_text += f"\n... and {len(messages_list) - 20} more\n"
    
    preview_text += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
    preview_text += f"📊 **Found:** `{media_count['video']}`🎬 `{media_count['document']}`📄 `{media_count['photo']}`🖼️ `{media_count['audio']}`🎵\n"
    preview_text += f"📦 **Total:** `{media_count['total']}` messages\n\n"
    
    # Store for download
    state["explored_ids"] = [m["id"] for m in messages_list]
    state["media_count"] = media_count
    
    # Buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⬇️ DOWNLOAD ALL ({media_count['total']})", callback_data="filter_download")],
        [InlineKeyboardButton("📄 Get IDs List", callback_data="filter_get_ids")],
        [InlineKeyboardButton("🔁 Explore More (Next 100)", callback_data="filter_explore_more")],
        [InlineKeyboardButton("❌ Cancel", callback_data="filter_cancel")]
    ])
    
    # Send as file if too long
    if len(preview_text) > 4000:
        # Truncate and send file
        preview_text = preview_text[:3500] + "\n\n... (truncated)"
        
        # Also send IDs as file
        ids_text = "\n".join([f"{m['id']} - {m['emoji']} {m['type']}" for m in messages_list])
        
        file_name = f"topic_{thread_id}_contents.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(ids_text)
        
        await message.reply_document(file_name, caption=preview_text[:1000])
        os.remove(file_name)
    
    await message.reply_text(preview_text, reply_markup=keyboard)


# ============ DOWNLOAD TOPIC ============
async def start_topic_download(c, message, uid):
    """Download from topic"""
    state = BOTCHAT_STATE.get(uid)
    if not state:
        return
    
    chat = state["chat"]
    thread_id = state.get("thread_id")
    selected_filter = state.get("filter")
    
    # Get IDs to download
    download_ids = state.get("explored_ids", [])
    
    # If no explored IDs, fetch fresh
    if not download_ids:
        await message.reply_text("⏳ Fetching message IDs...")
        
        uc = await get_uclient(uid)
        download_ids = []
        count = 0
        
        try:
            async for msg in uc.get_chat_history(chat, limit=10000):
                if thread_id:
                    msg_topic = getattr(msg, "message_thread_id", None) or getattr(msg, "reply_to_top_message_id", None)
                    if msg_topic != thread_id:
                        continue
                
                if selected_filter:
                    if selected_filter == "video" and not msg.video:
                        continue
                    if selected_filter == "document" and not msg.document:
                        continue
                
                download_ids.append(msg.id)
                count += 1
                
                if count >= 5000:  # Max 5000
                    break
                    
        except Exception as e:
            await message.reply_text(f"❌ Error: `{str(e)[:100]}`")
            return
    
    if not download_ids:
        await message.reply_text("⚠️ No messages to download!")
        BOTCHAT_STATE.pop(uid, None)
        return
    
    # Start download
    total = len(download_ids)
    topic_info = f"\n📌 Topic: `{thread_id}`" if thread_id else ""
    
    start_msg = await message.reply_text(
        f"🚀 **Starting Download**{topic_info}\n"
        f"📦 **Total:** `{total}` messages\n"
        f"⏳ Starting..."
    )
    await asyncio.sleep(2)
    await start_msg.delete()
    
    # Register
    try:
        await add_active_batch(uid, {
            "total": total, "current": 0, "success": 0,
            "cancel_requested": False, "progress_message_id": None
        })
    except:
        pass
    
    uc = await get_uclient(uid)
    ubot = await get_ubot(uid)
    
    chat_type = "public" if str(chat).startswith("@") else "private"
    destination = str(message.chat.id)
    
    pt = await message.reply_text(
        f"🚀 Downloading{topic_info}\n"
        f"📦 Total: `{total}`\n"
        f"⏳ Progress: `0/{total}`\n"
        f"✅ Done: `0`"
    )
    
    success = 0
    
    for idx, mid in enumerate(download_ids, start=1):
        try:
            if should_cancel(uid):
                await pt.edit_text(f"🛑 Cancelled {idx}/{total}{topic_info}\n✅ Done: {success}")
                break
        except:
            pass
        
        try:
            msg = await get_msg(ubot, uc, chat, mid, chat_type)
            if not msg:
                continue
            
            # Topic check
            if thread_id:
                msg_topic = getattr(msg, "message_thread_id", None) or getattr(msg, "reply_to_top_message_id", None)
                if msg_topic != thread_id:
                    continue
            
            # Filter
            if selected_filter and not getattr(msg, selected_filter, None):
                continue
            
            # Process
            res = await process_msg(ubot, uc, msg, destination, chat_type, uid, chat)
            
            if any(x in str(res) for x in ["Done", "Sent", "Copied", "directly"]):
                success += 1
            
            # Update
            if idx % 1 == 0:
                try:
                    await pt.edit_text(
                        f"🚀 Downloading{topic_info}\n"
                        f"📦 Total: `{total}`\n"
                        f"⏳ Progress: `{idx}/{total}`\n"
                        f"✅ Done: `{success}`\n\n"
                        f"🔄 Current: `{mid}`"
                    )
                except:
                    pass
            
            await asyncio.sleep(2)
            
        except Exception as e:
            continue
    
    # Final
    final_text = (
        f"✅ Complete!{topic_info}\n\n"
        f"📦 Total: `{total}`\n"
        f"✅ Success: `{success}`\n"
        f"❌ Failed: `{total - success}`"
    )
    
    try:
        await pt.edit_text(final_text)
    except:
        await message.reply_text(final_text)
    
    try:
        await remove_active_batch(uid)
    except:
        pass
    
    BOTCHAT_STATE.pop(uid, None)


# ============ CHATID COMMAND ============
@X.on_message(filters.command("chatid"))
async def botchat_cmd(c, m):
    uid = m.from_user.id

    if await sub(c, m) == 1:
        return
    
    try:
        if is_user_active(uid):
            await m.reply_text("⚠️ Active task! Use /stop first.")
            return
    except:
        pass

    uc = await get_uclient(uid)
    if not uc:
        await m.reply_text("❌ Login first with /login")
        return

    BOTCHAT_STATE[uid] = {
        "step": "chat",
        "chat": None,
        "thread_id": None,
        "filter": None,
        "explored_ids": [],
        "media_count": {}
    }

    await m.reply_text(
        "📥 **Send topic link:**\n\n"
        "`https://t.me/c/2884241848/44514`\n\n"
        "I'll show you what's inside first!"
    )


# ============ TEXT HANDLER ============
@X.on_message(filters.text & filters.private & ~login_in_progress
              & ~filters.command([
                  'start', 'batch', 'cancel', 'login', 'logout', 'stop', 'set',
                  'pay', 'redeem', 'gencode', 'single', 'generate', 'keyinfo',
                  'encrypt', 'decrypt', 'keys', 'setbot', 'rembot', 'chatid'
              ]))
async def text_handler(c, m):
    uid = m.from_user.id
    
    if uid in BOTCHAT_STATE:
        pass
    else:
        try:
            if is_user_active(uid) and m.text.strip().lower() not in ['cancel', '/cancel', 'stop', '/stop']:
                await m.reply_text("⚠️ Active task! Use /stop.")
                return
        except:
            pass
    
    if uid in BOTCHAT_STATE:
        state = BOTCHAT_STATE[uid]
        
        if state["step"] == "chat":
            chat_input = m.text.strip()
            chat_id, thread_id = parse_chat_input(chat_input)
            
            if not thread_id:
                # Try manual format: chat_id topic_id
                parts = chat_input.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    thread_id = int(parts[1])
                else:
                    await m.reply_text(
                        "❌ **Need topic ID!**\n\n"
                        "Send:\n"
                        "`https://t.me/c/2884241848/44514`"
                    )
                    return
            
            state["chat"] = chat_id
            state["thread_id"] = thread_id
            
            # Show initial options
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎬 Videos", callback_data="filter_video")],
                [InlineKeyboardButton("📄 Documents", callback_data="filter_doc")],
                [InlineKeyboardButton("📦 All Media", callback_data="filter_all")],
                [InlineKeyboardButton("❌ Cancel", callback_data="filter_cancel")]
            ])
            
            await m.reply_text(
                f"📌 **Topic:** `{thread_id}`\n\n"
                f"🎯 **What do you want to explore?**",
                reply_markup=keyboard
            )
            
            state["step"] = "select_type"
            return
    
    # ============ BATCH/SINGLE (UNCHANGED) ============
    if uid not in Z:
        return
        
    s = Z[uid].get('step')

    if s == 'start':
        L = m.text
        i, d, lt = E(L)
        if not i or not d:
            await m.reply_text('❌ Invalid link format.')
            Z.pop(uid, None)
            return
        Z[uid].update({'step': 'count', 'cid': i, 'sid': d, 'lt': lt})
        await m.reply_text('📊 How many messages?')
        

    # ... rest unchanged ...

    elif s == 'start_single':
        L = m.text
        i, d, lt = E(L)
        if not i or not d:
            await m.reply_text('❌ Invalid link format.')
            Z.pop(uid, None)
            return

        Z[uid].update({'step': 'process_single', 'cid': i, 'sid': d, 'lt': lt})
        i, s_link, lt = Z[uid]['cid'], Z[uid]['sid'], Z[uid]['lt']
        pt = await m.reply_text('🔄 Processing...')

        ubot = UB.get(uid)
        if not ubot:
            await pt.edit('❌ Add bot with /setbot first')
            Z.pop(uid, None)
            return

        uc = await get_uclient(uid)
        if not uc:
            await pt.edit('❌ Cannot proceed without user client.')
            Z.pop(uid, None)
            return

        try:
            msg = await get_msg(ubot, uc, i, s_link, lt)
            if msg:
                res = await process_msg(ubot, uc, msg, str(m.chat.id), lt, uid, i)
                await pt.edit(f'✅ 1/1: {res}')
            else:
                await pt.edit('❌ Message not found')
        except Exception as e:
            await pt.edit(f'💥 Error: {str(e)[:100]}')
        finally:
            Z.pop(uid, None)

    elif s == 'count':
        if not m.text.isdigit():
            await m.reply_text('❌ Enter a valid number.')
            return

        count = int(m.text)
        maxlimit = PREMIUM_LIMIT if await is_premium_user(uid) else FREEMIUM_LIMIT

        if count > maxlimit:
            await m.reply_text(f'⚠️ Maximum limit is {maxlimit}.')
            return

        Z[uid].update({'step': 'process', 'did': str(m.chat.id), 'num': count})
        i, s_link, n, lt = Z[uid]['cid'], Z[uid]['sid'], Z[uid]['num'], Z[uid]['lt']
        success = 0

        pt = await m.reply_text('🚀 Processing batch...')
        uc = await get_uclient(uid)
        ubot = UB.get(uid)

        if not uc or not ubot:
            await pt.edit('❌ Missing client setup')
            Z.pop(uid, None)
            return

        await add_active_batch(uid, {
            "total": n, "current": 0, "success": 0,
            "cancel_requested": False, "progress_message_id": pt.id
        })

        try:
            for j in range(n):
                if should_cancel(uid):
                    await pt.edit(f'🛑 Cancelled at {j}/{n}\n✅ Success: {success}')
                    break

                await update_batch_progress(uid, j, success)
                mid = int(s_link) + j

                try:
                    msg = await get_msg(ubot, uc, i, mid, lt)
                    if msg:
                        res = await process_msg(ubot, uc, msg, str(m.chat.id), lt, uid, i)
                        if 'Done' in res or 'Copied' in res or 'Sent' in res:
                            success += 1
                except Exception as e:
                    pass

                await asyncio.sleep(2)

            await m.reply_text(f'✅ Batch Completed!\nSuccess: {success}/{n}')

        finally:
            await remove_active_batch(uid)
            Z.pop(uid, None)
