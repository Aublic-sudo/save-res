
# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

import os, re, time, asyncio, json, asyncio 
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import UserNotParticipant
from config import API_ID, API_HASH, LOG_GROUP, STRING, FORCE_SUB, FREEMIUM_LIMIT, PREMIUM_LIMIT
from utils.func import (
    get_user_data, screenshot, thumbnail, get_video_metadata,
    ensure_anonymous_sender, cleanup_stray_temp_files,
    get_user_data_key, process_text_with_rules, is_premium_user, E
)
from shared_client import app as X
from plugins.settings import rename_file
from plugins.start import subscribe as sub
from utils.custom_filters import login_in_progress
from utils.encrypt import dcs
from typing import Dict, Any, Optional


Y = None if not STRING else __import__('shared_client').userbot
Z, P, UB, UC, emp = {}, {}, {}, {}, {}
EDIT_TASKS: Dict[str, asyncio.Task] = {}

ACTIVE_USERS = {}
ACTIVE_USERS_FILE = "active_users.json"

# fixed directory file_name problems 
def sanitize(filename):
    return re.sub(r'[<>:"/\\|?*\']', '_', filename).strip(" .")[:255]

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
    return user_str in ACTIVE_USERS and ACTIVE_USERS[user_str].get("cancel_requested", False)

async def remove_active_batch(user_id: int):
    if str(user_id) in ACTIVE_USERS:
        del ACTIVE_USERS[str(user_id)]
        await save_active_users_to_file()

def get_batch_info(user_id: int) -> Optional[Dict[str, Any]]:
    return ACTIVE_USERS.get(str(user_id))

ACTIVE_USERS = load_active_users()

async def upd_dlg(c):
    try:
        async for _ in c.get_dialogs(limit=100): pass
        return True
    except Exception as e:
        print(f'Failed to update dialogs: {e}')
        return False

PEER_CACHE = {}

async def get_msg(c, u, i, d, lt):
    try:
        if lt == 'public':
            try:
                xm = await c.get_messages(i, d)
                emp[i] = getattr(xm, "empty", False)
                if emp[i]:
                    try: await u.join_chat(i)
                    except: pass
                    xm = await u.get_messages((await u.get_chat(f"@{i}")).id, d)
                return xm
            except Exception as e:
                print(f'Error fetching public message: {e}')
                return None
        else:
            if u:
                chat_id = i if str(i).startswith('-100') else f'-100{i}' if str(i).isdigit() else i
                if str(chat_id) in PEER_CACHE:
                    resolved_id = PEER_CACHE[str(chat_id)]
                    try:
                        return await u.get_messages(resolved_id, d)
                    except Exception:
                        pass

                try:
                    peer = await u.resolve_peer(chat_id)
                    if hasattr(peer, 'channel_id'): resolved_id = f'-100{peer.channel_id}'
                    elif hasattr(peer, 'chat_id'): resolved_id = f'-{peer.chat_id}'
                    elif hasattr(peer, 'user_id'): resolved_id = peer.user_id
                    else: resolved_id = chat_id
                    PEER_CACHE[str(chat_id)] = resolved_id
                    return await u.get_messages(resolved_id, d)
                except Exception:
                    try:
                        chat = await u.get_chat(chat_id)
                        PEER_CACHE[str(chat_id)] = chat.id
                        return await u.get_messages(chat.id, d)
                    except Exception:
                        await upd_dlg(u)
                        try:
                            return await u.get_messages(chat_id, d)
                        except Exception:
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
        bot = Client(f"user_{uid}", bot_token=bt, api_id=API_ID, api_hash=API_HASH, sleep_threshold=60, workers=16)
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
            # max_concurrent_transmissions=1 prevents simultaneous GetFile requests on single user sessions that cause 8-9s flood waits
            gg = Client(f'{uid}_client', api_id=API_ID, api_hash=API_HASH, device_model="v3saver", session_string=ss, sleep_threshold=60, max_concurrent_transmissions=1, workers=16)
            await gg.start()
            await upd_dlg(gg)
            UC[uid] = gg
            return gg
        except Exception as e:
            print(f'User client error: {e}')
            return ubot if ubot else Y
    return Y

async def _bg_edit_progress(client, chat_id, message_id, text):
    try:
        await client.edit_message_text(chat_id, message_id, text)
    except Exception:
        pass

async def prog(c, t, C, h, m, st):
    global P, EDIT_TASKS
    try:
        if not t or t <= 0:
            return
        pct = (c / t) * 100
        key = f"{h}_{m}"
        now = time.time()
        
        last_time, _ = P.get(key, (0, 0))
        
        # Throttle edits to at least 2.5 seconds to eliminate Telegram rate limits & maximize bandwidth
        if (now - last_time < 2.5) and pct < 100:
            return
            
        # If an edit task is already in-flight for this message, skip this tick to not queue up edits
        current_task = EDIT_TASKS.get(key)
        if current_task and not current_task.done():
            if pct < 100:
                return
            
        P[key] = (now, pct)
        c_mb = c / (1024 * 1024)
        t_mb = t / (1024 * 1024)
        bar = '🟢' * int(pct / 10) + '🔴' * (10 - int(pct / 10))
        elapsed = now - st
        speed = c / elapsed / (1024 * 1024) if elapsed > 0 else 0
        try:
            remaining_bytes = max(0, t - c)
            speed_bytes = speed * 1024 * 1024
            rem_secs = int(remaining_bytes / speed_bytes) if speed_bytes > 0 else 0
            rem_secs = min(max(0, rem_secs), 86400)
            eta = time.strftime('%M:%S', time.gmtime(rem_secs))
        except Exception:
            eta = '00:00'
        
        text = (
            f"__**Pyro Handler...**__\n\n"
            f"{bar}\n\n"
            f"⚡ **__Completed__**: {c_mb:.2f} MB / {t_mb:.2f} MB\n"
            f"📊 **__Done__**: {pct:.2f}%\n"
            f"🚀 **__Speed__**: {speed:.2f} MB/s\n"
            f"⏳ **__ETA__**: {eta}\n\n"
            f"**__Powered by Rixie__**"
        )
        
        # Dispatch edit in background task so download/upload loop NEVER blocks!
        loop = asyncio.get_running_loop()
        edit_task = loop.create_task(_bg_edit_progress(C, h, m, text))
        EDIT_TASKS[key] = edit_task
        
        if pct >= 100:
            P.pop(key, None)
            EDIT_TASKS.pop(key, None)
    except Exception:
        pass

def is_chat_target(target_id, user_id=None):
    """Checks if the destination is a group or channel rather than a user PM."""
    if not target_id:
        return False
    try:
        tid = int(str(target_id).split('/')[0].strip())
        if tid < 0:
            return True
    except Exception:
        pass
    t_str = str(target_id).strip()
    if t_str.startswith('-'):
        return True
    if user_id is not None and str(target_id) != str(user_id):
        return True
    return False

async def send_direct(client_to_use, m, tcid, ft=None, rtmid=None):
    try:
        if m.video:
            await client_to_use.send_video(tcid, m.video.file_id, caption=ft, duration=m.video.duration, width=m.video.width, height=m.video.height, reply_to_message_id=rtmid)
        elif m.video_note:
            await client_to_use.send_video_note(tcid, m.video_note.file_id, reply_to_message_id=rtmid)
        elif m.voice:
            await client_to_use.send_voice(tcid, m.voice.file_id, reply_to_message_id=rtmid)
        elif m.sticker:
            await client_to_use.send_sticker(tcid, m.sticker.file_id, reply_to_message_id=rtmid)
        elif m.audio:
            await client_to_use.send_audio(tcid, m.audio.file_id, caption=ft, duration=m.audio.duration, performer=m.audio.performer, title=m.audio.title, reply_to_message_id=rtmid)
        elif m.photo:
            photo_id = m.photo.file_id if hasattr(m.photo, 'file_id') else m.photo[-1].file_id
            await client_to_use.send_photo(tcid, photo_id, caption=ft, reply_to_message_id=rtmid)
        elif m.document:
            await client_to_use.send_document(tcid, m.document.file_id, caption=ft, file_name=m.document.file_name, reply_to_message_id=rtmid)
        else:
            return False
        return True
    except Exception as e:
        if rtmid:
            try:
                return await send_direct(client_to_use, m, tcid, ft=ft, rtmid=None)
            except Exception:
                pass
        print(f'Direct send error: {e}')
        return False

async def process_msg(c, u, m, d, lt, uid, i, target_override=None, topic_override=None):
    f = None
    th = None
    p = None
    prog_client = c
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
        
        if target_override is not None:
            tcid = target_override
        if topic_override is not None:
            rtmid = topic_override
        
        # Determine uploader client:
        # Prioritize custom bot 'c' (configured via /setbot) to keep main bot hidden.
        # Fallback to user client 'u' if custom bot is not available.
        uploader = c if c else u
        
        if m.media:
            orig_text = m.caption.markdown if m.caption else ''
            proc_text = await process_text_with_rules(d, orig_text)
            user_cap = await get_user_data_key(d, 'caption', '')
            ft = f'{proc_text}\n\n{user_cap}' if proc_text and user_cap else user_cap if user_cap else proc_text
            
            if lt == 'public' and not emp.get(i, False):
                direct_ok = await send_direct(uploader, m, tcid, ft, rtmid)
                if direct_ok:
                    return 'Sent directly.'
            
            st = time.time()
            p = None
            try:
                p = await c.send_message(d, 'Downloading...')
                prog_client = c
            except Exception:
                try:
                    p = await X.send_message(d, 'Downloading...')
                    prog_client = X
                except Exception:
                    p = None

            c_name = f"{time.time()}"
            if m.video:
                file_name = m.video.file_name or f"{time.time()}.mp4"
                c_name = sanitize(file_name)
            elif m.audio:
                file_name = m.audio.file_name or f"{time.time()}.mp3"
                c_name = sanitize(file_name)
            elif m.document:
                file_name = m.document.file_name or f"{time.time()}"
                c_name = sanitize(file_name)
            elif m.photo:
                file_name = f"{time.time()}.jpg"
                c_name = sanitize(file_name)
    
            dl_err_str = None
            try:
                f = await u.download_media(
                    m,
                    file_name=c_name,
                    progress=prog if p else None,
                    progress_args=(prog_client, d, p.id, st) if p else None
                )
            except Exception as dl_err:
                dl_err_str = str(dl_err)
                print(f"[DOWNLOAD ERROR] Msg {getattr(m, 'id', 'unknown')}: {dl_err}")

            if not f or not os.path.exists(f):
                err_text = f"Download failed: {dl_err_str[:30]}" if dl_err_str else "Download failed."
                print(f"[DOWNLOAD] File {c_name} not available: {err_text}")
                if p:
                    try: await prog_client.edit_message_text(d, p.id, err_text)
                    except: pass
                return err_text
            
            if p:
                try: await prog_client.edit_message_text(d, p.id, 'Renaming...')
                except: pass
            if (
                (m.video and m.video.file_name) or
                (m.audio and m.audio.file_name) or
                (m.document and m.document.file_name)
            ):
                f = await rename_file(f, d, p)
            
            fsize = os.path.getsize(f) / (1024 * 1024 * 1024)
            user_thumb = thumbnail(d)
            th = user_thumb
            
            if fsize > 2 and Y:
                st = time.time()
                if p:
                    try: await prog_client.edit_message_text(d, p.id, 'File is larger than 2GB. Using alternative method...')
                    except: pass
                await upd_dlg(Y)
                mtd = await get_video_metadata(f)
                dur, h, w = mtd['duration'], mtd['width'], mtd['height']
                gen_th = await screenshot(f, dur, d)
                if gen_th != user_thumb:
                    th = gen_th
                
                send_funcs = {'video': Y.send_video, 'video_note': Y.send_video_note, 
                            'voice': Y.send_voice, 'audio': Y.send_audio, 
                            'photo': Y.send_photo, 'document': Y.send_document}
                
                target_chat = LOG_GROUP if LOG_GROUP else tcid
                for mtype, func in send_funcs.items():
                    if f.endswith('.mp4'): mtype = 'video'
                    if getattr(m, mtype, None):
                        sent = await func(target_chat, f, thumb=th if mtype == 'video' else None, 
                                        duration=dur if mtype == 'video' else None,
                                        height=h if mtype == 'video' else None,
                                        width=w if mtype == 'video' else None,
                                        caption=ft if m.caption and mtype not in ['video_note', 'voice'] else None, 
                                        progress=prog if p else None,
                                        progress_args=(prog_client, d, p.id, st) if p else None)
                        break
                else:
                    sent = await Y.send_document(target_chat, f, thumb=th, caption=ft if m.caption else None,
                                                progress=prog if p else None,
                                                progress_args=(prog_client, d, p.id, st) if p else None)
                
                if target_chat == LOG_GROUP and LOG_GROUP != tcid:
                    copied = False
                    try:
                        await uploader.copy_message(tcid, LOG_GROUP, sent.id, reply_to_message_id=rtmid)
                        copied = True
                    except Exception:
                        try:
                            await uploader.copy_message(tcid, LOG_GROUP, sent.id)
                            copied = True
                        except Exception:
                            if uploader != c and c:
                                try:
                                    await c.copy_message(tcid, LOG_GROUP, sent.id, reply_to_message_id=rtmid)
                                    copied = True
                                except Exception:
                                    try:
                                        await c.copy_message(tcid, LOG_GROUP, sent.id)
                                        copied = True
                                    except Exception as copy_err:
                                        return f'Large file copy failed: {str(copy_err)[:35]}'
                    if not copied:
                        return 'Large file copy failed.'
                if p:
                    try: await prog_client.delete_messages(d, p.id)
                    except: pass
                return 'Done (Large file).'
            
            if p:
                try: await prog_client.edit_message_text(d, p.id, 'Uploading...')
                except: pass
            st = time.time()

            async def do_upload(client_to_use, reply_id=rtmid):
                try:
                    safe_cap = ft[:1020] if ft else None
                    if m.video or os.path.splitext(f)[1].lower() in ['.mp4', '.mkv', '.mov', '.avi', '.webm']:
                        mtd = await get_video_metadata(f)
                        dur = mtd.get('duration') if mtd.get('duration', 0) > 0 else (getattr(m.video, 'duration', None) if m.video else None)
                        h = mtd.get('height') if mtd.get('height', 0) > 1 else (getattr(m.video, 'height', None) if m.video else None)
                        w = mtd.get('width') if mtd.get('width', 0) > 1 else (getattr(m.video, 'width', None) if m.video else None)
                        
                        gen_th = None
                        try:
                            gen_th = await screenshot(f, dur or 2, d)
                        except Exception:
                            pass
                        
                        th_use = gen_th if (gen_th and os.path.isfile(gen_th) and os.path.getsize(gen_th) > 0) else None
                        if not th_use and user_thumb and os.path.isfile(user_thumb) and os.path.getsize(user_thumb) > 0:
                            th_use = user_thumb

                        try:
                            await client_to_use.send_video(
                                tcid, video=f, caption=safe_cap, 
                                thumb=th_use, width=w, height=h, duration=dur, 
                                progress=prog if p else None,
                                progress_args=(prog_client, d, p.id, st) if p else None, 
                                reply_to_message_id=reply_id
                            )
                        except Exception as sv_err:
                            logger.warning(f"send_video error ({sv_err}), falling back to send_document...")
                            await client_to_use.send_document(
                                tcid, document=f, caption=safe_cap,
                                thumb=th_use,
                                progress=prog if p else None,
                                progress_args=(prog_client, d, p.id, st) if p else None,
                                reply_to_message_id=reply_id
                            )
                    elif m.video_note:
                        await client_to_use.send_video_note(
                            tcid, video_note=f,
                            progress=prog if p else None, 
                            progress_args=(prog_client, d, p.id, st) if p else None,
                            reply_to_message_id=reply_id
                        )
                    elif m.voice:
                        await client_to_use.send_voice(
                            tcid, f,
                            progress=prog if p else None, 
                            progress_args=(prog_client, d, p.id, st) if p else None, 
                            reply_to_message_id=reply_id
                        )
                    elif m.sticker:
                        await client_to_use.send_sticker(tcid, m.sticker.file_id, reply_to_message_id=reply_id)
                    elif m.audio:
                        await client_to_use.send_audio(
                            tcid, audio=f, caption=ft if m.caption else None, 
                            thumb=th, progress=prog if p else None,
                            progress_args=(prog_client, d, p.id, st) if p else None, 
                            reply_to_message_id=reply_id
                        )
                    elif m.photo:
                        await client_to_use.send_photo(
                            tcid, photo=f, caption=ft if m.caption else None, 
                            progress=prog if p else None,
                            progress_args=(prog_client, d, p.id, st) if p else None, 
                            reply_to_message_id=reply_id
                        )
                    else:
                        await client_to_use.send_document(
                            tcid, document=f, caption=ft if m.caption else None, 
                            progress=prog if p else None,
                            progress_args=(prog_client, d, p.id, st) if p else None, 
                            reply_to_message_id=reply_id
                        )
                except Exception as up_err:
                    if reply_id is not None:
                        return await do_upload(client_to_use, reply_id=None)
                    raise up_err

            try:
                await do_upload(uploader)
                # Immediately remove downloaded file upon successful upload to safeguard Render VPS storage
                if f and os.path.exists(f):
                    try: os.remove(f)
                    except Exception: pass
            except Exception as upload_err:
                alt_uploader = u if uploader == c else c
                if alt_uploader:
                    try:
                        print(f"Upload via {uploader} failed: {upload_err}, falling back to alternative client...")
                        await do_upload(alt_uploader)
                        if f and os.path.exists(f):
                            try: os.remove(f)
                            except Exception: pass
                    except Exception as fb_err:
                        print(f"Upload fallback failed: {fb_err}")
                        if p:
                            try: await prog_client.edit_message_text(d, p.id, f'Upload failed: {str(fb_err)[:35]}')
                            except: pass
                        return f'Failed: {str(fb_err)[:35]}'
                else:
                    print(f"Upload failed: {upload_err}")
                    if p:
                        try: await prog_client.edit_message_text(d, p.id, f'Upload failed: {str(upload_err)[:35]}')
                        except: pass
                    return f'Failed: {str(upload_err)[:35]}'
            
            if p:
                try: await prog_client.delete_messages(d, p.id)
                except: pass
            return 'Done.'
            
        elif m.text:
            try:
                await uploader.send_message(tcid, text=m.text.markdown, reply_to_message_id=rtmid)
            except Exception as text_err:
                if rtmid is not None:
                    try:
                        await uploader.send_message(tcid, text=m.text.markdown)
                        return 'Sent.'
                    except Exception:
                        pass
                alt_client = u if uploader == c else c
                if alt_client:
                    try:
                        await alt_client.send_message(tcid, text=m.text.markdown, reply_to_message_id=rtmid)
                        return 'Sent.'
                    except Exception as fb_err:
                        return f'Failed: {str(fb_err)[:35]}'
                return f'Failed: {str(text_err)[:35]}'
            return 'Sent.'
        else:
            return 'Skipped (service/empty message).'
    except Exception as e:
        return f'Error: {str(e)[:50]}'
    finally:
        # GUARANTEED IMMEDIATE CLEANUP OF LOCAL FILE AND GENERATED THUMBNAIL
        if f and os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
        user_thumb = thumbnail(d)
        if th and th != user_thumb and os.path.exists(th):
            try:
                os.remove(th)
            except Exception:
                pass
        cleanup_stray_temp_files()
        import gc
        gc.collect()

@X.on_message(filters.command(['batch', 'single']))
async def process_cmd(c, m):
    uid = m.from_user.id
    cmd = m.command[0]
    
    if FREEMIUM_LIMIT == 0 and not await is_premium_user(uid):
        await m.reply_text("This bot does not provide free servies, get subscription from OWNER")
        return
    
    if await sub(c, m) == 1: return
    pro = await m.reply_text('Doing some checks hold on...')
    
    if is_user_active(uid):
        await pro.edit('You have an active task. Use /stop to cancel it.')
        return
    
    ubot = await get_ubot(uid)
    if not ubot:
        await pro.edit(
            "⚠️ **Custom Bot Required!**\n\n"
            "Please add your bot token first using:\n"
            "`/setbot <token>`\n\n"
            "🔒 _All files will be uploaded through your custom bot so the main bot remains completely hidden!_"
        )
        return
    
    Z[uid] = {'step': 'start' if cmd == 'batch' else 'start_single'}
    await pro.edit(f'Send {"start link..." if cmd == "batch" else "link you to process"}.')

@X.on_message(filters.command(['cancel', 'stop']))
async def cancel_cmd(c, m):
    uid = m.from_user.id
    if is_user_active(uid):
        if await request_batch_cancel(uid):
            await m.reply_text('Cancellation requested. The current batch will stop after the current download completes.')
        else:
            await m.reply_text('Failed to request cancellation. Please try again.')
    else:
        await m.reply_text('No active batch process found.')

@X.on_message(filters.command(['forcestop', 'kill', 'forcecancel', 'stopall']) & filters.private)
async def force_stop_cmd(c, m):
    uid = m.from_user.id
    await remove_active_batch(uid)
    Z.pop(uid, None)
    try:
        from plugins.clone import CLONE_STATE
        CLONE_STATE.pop(uid, None)
    except Exception:
        pass
    try:
        from utils.func import cleanup_stray_temp_files
        cleanup_stray_temp_files()
    except Exception:
        pass
    await m.reply_text(
        "🛑 **Force Stop Executed!**\n\n"
        "All running downloads, uploads, and batch cloning processes have been forcefully terminated!"
    )

from pyrogram import ContinuePropagation

@X.on_message(filters.text & filters.private & ~login_in_progress & ~filters.command([
    'start', 'batch', 'cancel', 'login', 'logout', 'stop', 'set', 
    'pay', 'redeem', 'gencode', 'single', 'generate', 'keyinfo', 'encrypt', 'decrypt', 'keys', 'setbot', 'rembot',
    'clone', 'topic', 'clonegroup', 'groupclone']))
async def text_handler(c, m):
    uid = m.from_user.id
    if uid not in Z:
        raise ContinuePropagation
    s = Z[uid].get('step')

    if s == 'start':
        L = m.text
        i, d, lt = E(L)
        if not i or not d:
            await m.reply_text('Invalid link format.')
            Z.pop(uid, None)
            return
        Z[uid].update({'step': 'count', 'cid': i, 'sid': d, 'lt': lt})
        await m.reply_text('How many messages?')

    elif s == 'start_single':
        L = m.text
        i, d, lt = E(L)
        if not i or not d:
            await m.reply_text('Invalid link format.')
            Z.pop(uid, None)
            return

        Z[uid].update({'step': 'process_single', 'cid': i, 'sid': d, 'lt': lt})
        i, s, lt = Z[uid]['cid'], Z[uid]['sid'], Z[uid]['lt']
        pt = await m.reply_text('Processing...')
        
        ubot = await get_ubot(uid)
        if not ubot:
            await pt.edit(
                "⚠️ **Custom Bot Required!**\n\n"
                "Please add your bot token first using:\n"
                "`/setbot <token>`\n\n"
                "🔒 _All files will be uploaded through your custom bot so the main bot remains completely hidden!_"
            )
            Z.pop(uid, None)
            return

        uc = await get_uclient(uid)
        if not uc:
            await pt.edit('⚠️ User session not found. Please /login first.')
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
                await pt.edit('Message not found')
        except Exception as e:
            await pt.edit(f'Error: {str(e)[:50]}')
        finally:
            Z.pop(uid, None)

    elif s == 'count':
        if not m.text.isdigit():
            await m.reply_text('Enter valid number.')
            return
        
        count = int(m.text)
        maxlimit = PREMIUM_LIMIT if await is_premium_user(uid) else FREEMIUM_LIMIT

        if count > maxlimit:
            await m.reply_text(f'Maximum limit is {maxlimit}.')
            return

        Z[uid].update({'step': 'process', 'did': str(m.chat.id), 'num': count})
        i, s, n, lt = Z[uid]['cid'], Z[uid]['sid'], Z[uid]['num'], Z[uid]['lt']
        success = 0

        pt = await m.reply_text('Processing batch...')
        ubot = await get_ubot(uid)
        if not ubot:
            await pt.edit(
                "⚠️ **Custom Bot Required!**\n\n"
                "Please add your bot token first using:\n"
                "`/setbot <token>`\n\n"
                "🔒 _All files will be uploaded through your custom bot so the main bot remains completely hidden!_"
            )
            Z.pop(uid, None)
            return

        uc = await get_uclient(uid)
        if not uc:
            await pt.edit('⚠️ User session not found. Please /login first.')
            Z.pop(uid, None)
            return
            
        if is_user_active(uid):
            await pt.edit('Active task exists')
            Z.pop(uid, None)
            return
        
        await add_active_batch(uid, {
            "total": n,
            "current": 0,
            "success": 0,
            "cancel_requested": False,
            "progress_message_id": pt.id
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
                        res = await process_msg(ubot, uc, msg, str(m.chat.id), lt, uid, i)
                        if 'Done' in res or 'Copied' in res or 'Sent' in res:
                            success += 1
                    else:
                        pass
                except Exception as e:
                    try: await pt.edit(f'{j+1}/{n}: Error - {str(e)[:30]}')
                    except: pass
                
                await asyncio.sleep(1)
            
            if j+1 == n:
                await m.reply_text(f'Batch Completed ✅ Success: {success}/{n}')
        
        finally:
            await remove_active_batch(uid)
            Z.pop(uid, None)
