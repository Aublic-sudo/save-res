
# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

import concurrent.futures
import time
import os
import re
import cv2
import logging
import asyncio
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB as MONGO_URI, DB_NAME

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

PUBLIC_LINK_PATTERN = re.compile(r'(https?://)?(t\.me|telegram\.me)/([^/]+)(/(\d+))?')
PRIVATE_LINK_PATTERN = re.compile(r'(https?://)?(t\.me|telegram\.me)/c/(\d+)(/(\d+))?')
VIDEO_EXTENSIONS = {"mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "mpeg", "mpg", "3gp"}

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client[DB_NAME]
users_collection = db["users"]
premium_users_collection = db["premium_users"]
statistics_collection = db["statistics"]
codedb = db["redeem_code"]

# ------- < start > Session Encoder don't change -------

a1 = "c2F2ZV9yZXN0cmljdGVkX2NvbnRlbnRfYm90cw=="
a2 = "Nzk2"
a3 = "Z2V0X21lc3NhZ2Vz"
a4 = "cmVwbHlfcGhvdG8="
a5 = "c3RhcnQ="
attr1 = "cGhvdG8="
attr2 = "ZmlsZV9pZA=="


a7 = "SGVsbG8g8J+agCB7dXNlcn0hIFdlbGNvbWUgdG8geW91ciB1bHRpbWF0ZSBjb250ZW50IHNhdmVyIGJvdCHwn5iJCgrwn5iNIEkgbGV0IHlvdSBzYXZlIHBvc3RzIGZyb20gVGVsZWdyYW0gY2hhbm5lbHMgJiBncm91cHMgdGhhdCBoYXZlIGZvcndhcmRpbmcgcmVzdHJpY3Rpb25zLCBhbmQgZG93bmxvYWQgdmlkZW9zIG9yIGF1ZGlvIGZyb20gWW91VHViZSwgSW5zdGFncmFtLCBhbmQgbW9yZS4K8J+YnCBKdXN0IHNlbmQgdGhlIGxpbmsgb2YgYW55IHB1YmxpYyBjaGFubmVsIHBvc3QuIEZvciBwcml2YXRlIGNoYW5uZWxzLCB1c2UgL2xvZ2luLiBGb3IgbW9yZSBkZXRhaWxzLCBzZW5kIC9oZWxwLgoK8J+QmCBHaXZlIG1lIGEgdHJ5IGFuZCBleHBlcmllbmNlIGZhc3QsIGVhc3kgc2F2aW5n"

a10 = "aHR0cHM6Ly9pLmliYi5jby9rNjlQQjVuZy82MTg4MDg4ODQyMTU0Nzg5NjY2LTk5LmpwZw=="
a11 = "aHR0cHM6Ly9pLmliYi5jby9rNjlQQjVuZy82MTg4MDg4ODQyMTU0Nzg5NjY2LTk5LmpwZw=="

a8 = "Sm9pbiBDaGFubmVs"  # 
a9 = "8J+RkU9XTkVS"

# ------- < end > Session Encoder don't change --------

def is_private_link(link):
    return bool(PRIVATE_LINK_PATTERN.match(link))


def thumbnail(sender):
    return f'{sender}.jpg' if os.path.exists(f'{sender}.jpg') else None


def hhmmss(seconds):
    return time.strftime('%H:%M:%S', time.gmtime(seconds))


def parse_tg_link(L):
    """
    Parses any Telegram link into:
    (chat_identifier, topic_id, message_id, link_type)
    """
    if not L or not isinstance(L, str):
        return None, None, None, None
    
    L = L.strip()
    
    # 1. Private link with 3 parts: https://t.me/c/1234567890/42/105
    m = re.search(r'(?:https?://)?(?:t\.me|telegram\.me)/c/(\d+)/(\d+)/(\d+)', L)
    if m:
        return f"-100{m.group(1)}", int(m.group(2)), int(m.group(3)), 'private'
    
    # 2. Private link with 2 parts: https://t.me/c/1234567890/42
    m = re.search(r'(?:https?://)?(?:t\.me|telegram\.me)/c/(\d+)/(\d+)', L)
    if m:
        return f"-100{m.group(1)}", int(m.group(2)), None, 'private'
    
    # 3. Private link with 1 part (group only): https://t.me/c/1234567890
    m = re.search(r'(?:https?://)?(?:t\.me|telegram\.me)/c/(\d+)', L)
    if m:
        return f"-100{m.group(1)}", None, None, 'private'
    
    # 4. Public link with 3 parts: https://t.me/username/42/105
    m = re.search(r'(?:https?://)?(?:t\.me|telegram\.me)/([^/\s]+)/(\d+)/(\d+)', L)
    if m and not m.group(1).startswith(('c', 'joinchat', '+')):
        return m.group(1), int(m.group(2)), int(m.group(3)), 'public'
    
    # 5. Public link with 2 parts: https://t.me/username/42
    m = re.search(r'(?:https?://)?(?:t\.me|telegram\.me)/([^/\s]+)/(\d+)', L)
    if m and not m.group(1).startswith(('c', 'joinchat', '+')):
        return m.group(1), int(m.group(2)), None, 'public'
    
    # 6. Public link with group name only: https://t.me/username
    m = re.search(r'(?:https?://)?(?:t\.me|telegram\.me)/([^/\s?#]+)', L)
    if m and not m.group(1).startswith(('c', 'joinchat', '+')):
        return m.group(1), None, None, 'public'
    
    # 7. Raw username: @username
    if L.startswith('@'):
        clean_user = L[1:].split()[0]
        return clean_user, None, None, 'public'
    
    # 8. Raw chat ID (e.g. -1001234567890)
    if L.startswith('-100') and L[4:].isdigit():
        return L, None, None, 'private'
    
    return None, None, None, None


def E(L):   
    chat_id, topic_or_msg, msg_id, lt = parse_tg_link(L)
    if not chat_id:
        return None, None, None
    # If 3 parts were given (chat, topic, msg), return msg_id
    if msg_id is not None:
        return chat_id, msg_id, lt
    # If 2 parts were given (chat, msg), return topic_or_msg
    if topic_or_msg is not None:
        return chat_id, topic_or_msg, lt
    return chat_id, None, lt


async def get_all_forum_topics(client, chat_id):
    """
    Fetches all forum topics for a given supergroup chat.
    Returns a list of dicts: [{'id': topic_id, 'title': title, 'top_message': top_msg, 'total_messages': total}]
    """
    topics = []
    try:
        from pyrogram.raw.functions.channels import GetForumTopics
        peer = await client.resolve_peer(chat_id)
        offset_date = 0
        offset_id = 0
        offset_topic = 0
        limit = 100
        
        while True:
            res = await client.invoke(
                GetForumTopics(
                    channel=peer,
                    offset_date=offset_date,
                    offset_id=offset_id,
                    offset_topic=offset_topic,
                    limit=limit
                )
            )
            raw_topics = getattr(res, 'topics', [])
            if not raw_topics:
                break
            
            for t in raw_topics:
                topic_id = getattr(t, 'id', None)
                if topic_id is not None:
                    title = getattr(t, 'title', f"Topic {topic_id}")
                    top_msg = getattr(t, 'top_message', 0)
                    total_msgs = getattr(t, 'total_messages', 0)
                    unread = getattr(t, 'unread_count', 0)
                    topics.append({
                        'id': int(topic_id),
                        'title': str(title),
                        'top_message': int(top_msg),
                        'total_messages': int(total_msgs),
                        'unread_count': int(unread)
                    })
            
            if len(raw_topics) < limit:
                break
            
            last = raw_topics[-1]
            offset_topic = getattr(last, 'id', 0)
            offset_id = getattr(last, 'top_message', 0)
            offset_date = getattr(last, 'date', 0)
    except Exception as e:
        logger.error(f"Error in get_all_forum_topics for {chat_id}: {e}")
    
    return topics


async def get_topic_messages_list(client, chat_id, topic_id, max_count=None):
    """
    Fetches all message IDs belonging to a specific forum topic.
    Returns message IDs ordered from oldest to newest.
    """
    msg_ids = []
    try:
        from pyrogram.raw.functions.messages import GetReplies
        peer = await client.resolve_peer(chat_id)
        offset_id = 0
        limit = 100
        
        while True:
            res = await client.invoke(
                GetReplies(
                    peer=peer,
                    msg_id=topic_id,
                    offset_id=offset_id,
                    offset_date=0,
                    add_offset=0,
                    limit=limit,
                    max_id=0,
                    min_id=0,
                    hash=0
                )
            )
            raw_msgs = getattr(res, 'messages', [])
            if not raw_msgs:
                break
            
            for rm in raw_msgs:
                mid = getattr(rm, 'id', None)
                if mid and not getattr(rm, 'empty', False):
                    msg_ids.append(mid)
            
            if len(raw_msgs) < limit:
                break
            
            offset_id = raw_msgs[-1].id
            if max_count and len(msg_ids) >= max_count:
                msg_ids = msg_ids[:max_count]
                break
    except Exception as e:
        logger.error(f"Error in GetReplies for topic {topic_id}: {e}")
    
    # Fallback to get_chat_history if GetReplies gave nothing
    if not msg_ids:
        try:
            async for m in client.get_chat_history(chat_id, limit=max_count or 1000):
                m_tid = getattr(m, 'message_thread_id', None) or getattr(m, 'reply_to_top_message_id', None)
                if m_tid == topic_id or (topic_id == 1 and m_tid is None):
                    msg_ids.append(m.id)
        except Exception as ex:
            logger.error(f"Fallback get_chat_history error for topic {topic_id}: {ex}")

    # Reverse to make it oldest to newest
    msg_ids.reverse()
    return msg_ids


async def create_forum_topic_safe(client, chat_id, title):
    """
    Creates a new forum topic in a supergroup if supported.
    Returns the created topic ID (integer) or None.
    """
    try:
        from pyrogram.raw.functions.channels import CreateForumTopic
        import random
        peer = await client.resolve_peer(chat_id)
        random_id = random.randint(1, 2147483647)
        res = await client.invoke(
            CreateForumTopic(
                channel=peer,
                title=str(title)[:128],
                random_id=random_id
            )
        )
        topic_id = None
        for u in getattr(res, 'updates', []):
            msg = getattr(u, 'message', None)
            if msg and hasattr(msg, 'id'):
                topic_id = msg.id
                break
            if hasattr(u, 'random_id') and getattr(u, 'random_id') == random_id and hasattr(u, 'id'):
                topic_id = u.id
                break
        if not topic_id:
            for m in getattr(res, 'messages', []):
                if hasattr(m, 'id'):
                    topic_id = m.id
                    break
        if topic_id:
            logger.info(f"Created topic '{title}' with ID {topic_id} in {chat_id}")
            return int(topic_id)
        if hasattr(client, 'create_forum_topic'):
            topic = await client.create_forum_topic(chat_id, title=str(title)[:128])
            tid = getattr(topic, 'id', getattr(topic, 'message_thread_id', None))
            if tid:
                return int(tid)
        return None
    except Exception as e:
        logger.error(f"Error creating forum topic '{title}' in {chat_id}: {e}")
        return None


async def promote_bot_in_chat(client, chat_id, target_bot):
    """Adds and promotes a bot client as an administrator in chat_id using user client."""
    if not target_bot:
        return False
    try:
        from pyrogram.types import ChatPrivileges
        from pyrogram.raw.functions.channels import EditAdmin
        from pyrogram.raw.types import ChatAdminRights

        bot_me = await target_bot.get_me()
        bot_identifier = bot_me.username or bot_me.id

        # 1. Try to add bot as member first
        try:
            await client.add_chat_members(chat_id, bot_identifier)
            await asyncio.sleep(0.5)
        except Exception as e_add:
            logger.debug(f"add_chat_members notice for {bot_identifier} in {chat_id}: {e_add}")

        # 2. Promote using Pyrogram promote_chat_member
        promoted = False
        try:
            await client.promote_chat_member(
                chat_id,
                bot_identifier,
                privileges=ChatPrivileges(
                    can_manage_chat=True,
                    can_delete_messages=True,
                    can_manage_video_chats=True,
                    can_restrict_members=True,
                    can_promote_members=True,
                    can_change_info=True,
                    can_invite_users=True,
                    can_pin_messages=True,
                    can_manage_topics=True,
                    can_post_messages=True,
                    can_edit_messages=True
                )
            )
            promoted = True
            logger.info(f"Promoted bot {bot_identifier} as admin in {chat_id}")
        except Exception as e_promo:
            logger.warning(f"Pyrogram promote_chat_member notice for {bot_identifier}: {e_promo}, attempting MTProto EditAdmin...")

        # 3. Fallback: MTProto EditAdmin
        if not promoted:
            try:
                channel_peer = await client.resolve_peer(chat_id)
                user_peer = await client.resolve_peer(bot_identifier)
                admin_rights = ChatAdminRights(
                    change_info=True,
                    post_messages=True,
                    edit_messages=True,
                    delete_messages=True,
                    ban_users=True,
                    invite_users=True,
                    pin_messages=True,
                    add_admins=True,
                    anonymous=False,
                    manage_call=True,
                    other=True,
                    manage_topics=True
                )
                await client.invoke(
                    EditAdmin(
                        channel=channel_peer,
                        user_id=user_peer,
                        admin_rights=admin_rights,
                        rank="Cloner Bot"
                    )
                )
                promoted = True
                logger.info(f"Successfully promoted {bot_identifier} via MTProto EditAdmin in {chat_id}")
            except Exception as e_mt:
                logger.error(f"MTProto EditAdmin failed for {bot_identifier} in {chat_id}: {e_mt}")

        return promoted
    except Exception as ex:
        logger.error(f"Error in promote_bot_in_chat for chat {chat_id}: {ex}")
        return False


_ANON_CACHE = set()

async def ensure_anonymous_sender(client, chat_id):
    """
    Ensures that when client (user session) posts into chat_id,
    the message appears as sent by the group/channel itself
    (with the group's profile photo and title, hiding the uploader's identity).
    """
    if not client:
        return False
    
    # Extract base chat id if format is "-100.../topic_id"
    raw_cid = str(chat_id).split('/')[0].strip()
    try:
        cid = int(raw_cid)
    except Exception:
        cid = raw_cid
    
    # Check if chat is a group or channel (negative ID)
    if isinstance(cid, int) and cid > 0:
        return False

    cache_key = (getattr(client, 'name', 'user'), str(cid))
    if cache_key in _ANON_CACHE:
        return True

    success = False

    # 1. Try to set default send_as to the chat itself (Works for channels and groups where user can send as chat)
    try:
        await client.set_send_as_chat(cid, cid)
        logger.info(f"set_send_as_chat successful for {cid}")
        success = True
    except Exception as e_sendas:
        logger.debug(f"set_send_as_chat notice for {cid}: {e_sendas}")

    # 2. Try to enable 'Remain Anonymous' (is_anonymous=True) for user in supergroup
    try:
        from pyrogram.types import ChatPrivileges
        await client.promote_chat_member(
            cid,
            "me",
            privileges=ChatPrivileges(
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_manage_topics=True,
                can_post_messages=True,
                can_edit_messages=True,
                is_anonymous=True
            )
        )
        logger.info(f"Promoted self as anonymous admin in {cid}")
        success = True
    except Exception as e_promo:
        logger.debug(f"Pyrogram promote_chat_member anonymous notice for {cid}: {e_promo}")

    # 3. Try MTProto EditAdmin with anonymous=True (Direct MTProto invoke)
    try:
        from pyrogram.raw.functions.channels import EditAdmin
        from pyrogram.raw.types import ChatAdminRights
        channel_peer = await client.resolve_peer(cid)
        me_peer = await client.resolve_peer("me")
        await client.invoke(
            EditAdmin(
                channel=channel_peer,
                user_id=me_peer,
                admin_rights=ChatAdminRights(
                    change_info=True,
                    post_messages=True,
                    edit_messages=True,
                    delete_messages=True,
                    ban_users=True,
                    invite_users=True,
                    pin_messages=True,
                    add_admins=True,
                    anonymous=True,
                    manage_call=True,
                    other=True,
                    manage_topics=True
                ),
                rank=""
            )
        )
        logger.info(f"MTProto EditAdmin anonymous=True successful in {cid}")
        success = True
    except Exception as e_mt:
        logger.debug(f"MTProto EditAdmin anonymous notice for {cid}: {e_mt}")

    # 4. If channel, ensure admin signatures are disabled so admin name is never signed
    try:
        from pyrogram.raw.functions.channels import ToggleSignatures
        channel_peer = await client.resolve_peer(cid)
        await client.invoke(ToggleSignatures(channel=channel_peer, enabled=False))
        logger.info(f"Disabled admin signatures for {cid}")
    except Exception:
        pass

    # 5. Re-try set_send_as_chat in case anonymous promotion just unlocked it
    try:
        await client.set_send_as_chat(cid, cid)
    except Exception:
        pass

    _ANON_CACHE.add(cache_key)
    return success


async def ensure_bot_admin(client, chat_id, bot_client=None):
    """Ensures user's custom bot is admin in an existing chat (Main Bot remains private/hidden)."""
    if not bot_client:
        return False
    try:
        return await promote_bot_in_chat(client, chat_id, bot_client)
    except Exception as e:
        logger.error(f"Error ensuring custom bot admin in {chat_id}: {e}")
        return False


async def create_cloned_supergroup(client, bot_client, title, description="", photo_file_id=None):
    """
    Creates a new supergroup with forum topics enabled, sets photo, and promotes custom bot as admin.
    (Main Bot remains completely hidden and private).
    Returns (new_chat_id, invite_link)
    """
    try:
        from pyrogram.raw.functions.channels import CreateChannel, ToggleForum
        import random

        # 1. Create MegaGroup (Supergroup)
        res = await client.invoke(
            CreateChannel(
                title=title[:128],
                about=(description or "")[:255],
                megagroup=True
            )
        )
        if not hasattr(res, 'chats') or not res.chats:
            logger.error("Failed to create supergroup channel")
            return None, None

        raw_channel = res.chats[0]
        new_chat_id = int(f"-100{raw_channel.id}")
        logger.info(f"Created new supergroup: {new_chat_id} ('{title}')")

        # 2. Wait 1 second and enable Forum Topics
        await asyncio.sleep(1)
        try:
            peer = await client.resolve_peer(new_chat_id)
            await client.invoke(
                ToggleForum(
                    channel=peer,
                    enabled=True
                )
            )
            logger.info(f"Enabled forum topics for {new_chat_id}")
        except Exception as e:
            logger.error(f"Error enabling forum topics: {e}")

        # 3. Set Group Profile Photo if provided
        if photo_file_id:
            try:
                photo_path = await client.download_media(photo_file_id)
                if photo_path and os.path.exists(photo_path):
                    await client.set_chat_photo(new_chat_id, photo=photo_path)
                    try:
                        os.remove(photo_path)
                    except Exception:
                        pass
                    logger.info(f"Set profile photo for {new_chat_id}")
            except Exception as e:
                logger.error(f"Error setting group photo: {e}")

        # 4. Promote ONLY the user's custom bot as Admin (Main Bot X is never revealed)
        if bot_client:
            try:
                await promote_bot_in_chat(client, new_chat_id, bot_client)
                logger.info(f"Successfully added & promoted custom bot in {new_chat_id}")
            except Exception as e:
                logger.error(f"Failed to promote custom bot in new supergroup {new_chat_id}: {e}")

        # 5. Enable Anonymous Admin and Group Identity for the user account (owner)
        try:
            await ensure_anonymous_sender(client, new_chat_id)
            logger.info(f"Configured anonymous group sender identity for {new_chat_id}")
        except Exception as e_anon:
            logger.warning(f"Failed to configure anonymous sender for {new_chat_id}: {e_anon}")

        # 6. Export invite link
        invite_link = None
        try:
            invite_link = await client.export_chat_invite_link(new_chat_id)
        except Exception:
            pass

        return new_chat_id, invite_link
    except Exception as e:
        logger.error(f"Error in create_cloned_supergroup: {e}")
        return None, None


def get_display_name(user):
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    elif user.first_name:
        return user.first_name
    elif user.last_name:
        return user.last_name
    elif user.username:
        return user.username
    else:
        return "Unknown User"


def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


def cleanup_stray_temp_files():
    """
    Cleans up any stray media or temp files in root and downloads directories
    to prevent Render VPS storage and memory from getting full.
    """
    try:
        now = time.time()
        targets = [".", "downloads"]
        
        for base_dir in targets:
            if not os.path.exists(base_dir):
                continue
            try:
                entries = os.listdir(base_dir)
            except Exception:
                continue
                
            for fname in entries:
                fpath = os.path.join(base_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                # Never touch session or persistent database files
                if fname.endswith(('.session', '.session-journal')) or fname.startswith(('thumb_', 'settings')):
                    continue
                
                # 1. Immediately remove temporary/incomplete files
                if fname.endswith(('.temp', '.part', '.tmp', '.download')):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
                    continue
                
                # 2. Remove orphan media files older than 45 seconds
                if fname.lower().endswith(('.mp4', '.mkv', '.mp3', '.jpg', '.jpeg', '.pdf', '.bin', '.webp', '.ogg', '.wav', '.flac', '.zip')):
                    try:
                        if now - os.path.getmtime(fpath) > 45:
                            os.remove(fpath)
                    except Exception:
                        pass
        import gc
        gc.collect()
    except Exception as e:
        logger.error(f"Error in cleanup_stray_temp_files: {e}")


def get_dummy_filename(info):
    file_type = info.get("type", "file")
    extension = {
        "video": "mp4",
        "photo": "jpg",
        "document": "pdf",
        "audio": "mp3"
    }.get(file_type, "bin")
    
    return f"downloaded_file_{int(time.time())}.{extension}"


async def is_private_chat(event):
    return event.is_private


async def save_user_data(user_id, key, value):
    await users_collection.update_one(
        {"user_id": user_id},
        {"$set": {key: value}},
        upsert=True
    )
   # print(users_collection)


async def get_user_data_key(user_id, key, default=None):
    user_data = await users_collection.find_one({"user_id": int(user_id)})
  #  print(f"Fetching key '{key}' for user {user_id}: {user_data}")
    return user_data.get(key, default) if user_data else default


async def get_user_data(user_id):
    try:
        user_data = await users_collection.find_one({"user_id": user_id})
        return user_data
    except Exception as e:
   #     logger.error(f"Error retrieving user data for {user_id}: {e}")
        return None


async def save_user_session(user_id, session_string):
    try:
        await users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "session_string": session_string,
                "updated_at": datetime.now()
            }},
            upsert=True
        )
        logger.info(f"Saved session for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving session for user {user_id}: {e}")
        return False


async def remove_user_session(user_id):
    try:
        await users_collection.update_one(
            {"user_id": user_id},
            {"$unset": {"session_string": ""}}
        )
        logger.info(f"Removed session for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error removing session for user {user_id}: {e}")
        return False


async def save_user_bot(user_id, bot_token):
    try:
        await users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "bot_token": bot_token,
                "updated_at": datetime.now()
            }},
            upsert=True
        )
        logger.info(f"Saved bot token for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving bot token for user {user_id}: {e}")
        return False


async def remove_user_bot(user_id):
    try:
        await users_collection.update_one(
            {"user_id": user_id},
            {"$unset": {"bot_token": ""}}
        )
        logger.info(f"Removed bot token for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error removing bot token for user {user_id}: {e}")
        return False


async def process_text_with_rules(user_id, text):
    if not text:
        return ""
    
    try:
        replacements = await get_user_data_key(user_id, "replacement_words", {})
        delete_words = await get_user_data_key(user_id, "delete_words", [])
        
        processed_text = text
        for word, replacement in replacements.items():
            processed_text = processed_text.replace(word, replacement)
        
        if delete_words:
            words = processed_text.split()
            filtered_words = [w for w in words if w not in delete_words]
            processed_text = " ".join(filtered_words)
        
        return processed_text
    except Exception as e:
        logger.error(f"Error processing text with rules: {e}")
        return text


async def screenshot(video: str, duration: int, sender: str) -> str | None:
    existing_screenshot = f"{sender}.jpg"
    if os.path.exists(existing_screenshot):
        return existing_screenshot

    time_stamp = hhmmss(duration // 2)
    output_file = datetime.now().isoformat("_", "seconds") + ".jpg"

    cmd = [
        "ffmpeg",
        "-ss", time_stamp,
        "-i", video,
        "-frames:v", "1",
        output_file,
        "-y"
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()

    if os.path.isfile(output_file):
        return output_file
    else:
        print(f"FFmpeg Error: {stderr.decode().strip()}")
        return None


async def get_video_metadata(file_path):
    default_values = {'width': 1, 'height': 1, 'duration': 1}
    loop = asyncio.get_event_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    
    try:
        def _extract_metadata():
            try:
                vcap = cv2.VideoCapture(file_path)
                if not vcap.isOpened():
                    return default_values

                width = round(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = round(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = vcap.get(cv2.CAP_PROP_FPS)
                frame_count = vcap.get(cv2.CAP_PROP_FRAME_COUNT)

                if fps <= 0:
                    return default_values

                duration = round(frame_count / fps)
                if duration <= 0:
                    return default_values

                vcap.release()
                return {'width': width, 'height': height, 'duration': duration}
            except Exception as e:
                logger.error(f"Error in video_metadata: {e}")
                return default_values
        
        return await loop.run_in_executor(executor, _extract_metadata)
        
    except Exception as e:
        logger.error(f"Error in get_video_metadata: {e}")
        return default_values


async def add_premium_user(user_id, duration_value, duration_unit):
    try:
        now = datetime.now()
        expiry_date = None
        
        if duration_unit == "min":
            expiry_date = now + timedelta(minutes=duration_value)
        elif duration_unit == "hours":
            expiry_date = now + timedelta(hours=duration_value)
        elif duration_unit == "days":
            expiry_date = now + timedelta(days=duration_value)
        elif duration_unit == "weeks":
            expiry_date = now + timedelta(weeks=duration_value)
        elif duration_unit == "month":
            expiry_date = now + timedelta(days=30 * duration_value)
        elif duration_unit == "year":
            expiry_date = now + timedelta(days=365 * duration_value)
        elif duration_unit == "decades":
            expiry_date = now + timedelta(days=3650 * duration_value)
        else:
            return False, "Invalid duration unit"
            
        await premium_users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "subscription_start": now,
                "subscription_end": expiry_date,
                "expireAt": expiry_date
            }},
            upsert=True
        )
        
        await premium_users_collection.create_index("expireAt", expireAfterSeconds=0)
        
        return True, expiry_date
    except Exception as e:
        logger.error(f"Error adding premium user {user_id}: {e}")
        return False, str(e)


async def is_premium_user(user_id):
    try:
        user = await premium_users_collection.find_one({"user_id": user_id})
        if user and "subscription_end" in user:
            now = datetime.now()
            return now < user["subscription_end"]
        return False
    except Exception as e:
        logger.error(f"Error checking premium status for {user_id}: {e}")
        return False


async def get_premium_details(user_id):
    try:
        user = await premium_users_collection.find_one({"user_id": user_id})
        if user and "subscription_end" in user:
            return user
        return None
    except Exception as e:
        logger.error(f"Error getting premium details for {user_id}: {e}")
        return None
