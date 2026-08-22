# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

import asyncio
import os
import re
import time
import logging
from typing import Dict, Any, Optional, List

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from config import API_ID, API_HASH, LOG_GROUP, STRING, FORCE_SUB, FREEMIUM_LIMIT, PREMIUM_LIMIT
from utils.func import (
    get_user_data, get_user_data_key, is_premium_user,
    parse_tg_link, get_all_forum_topics, get_topic_messages_list,
    create_forum_topic_safe, create_cloned_supergroup, cleanup_stray_temp_files, E
)
from shared_client import app as X
from plugins.start import subscribe as sub
from plugins.batch import (
    get_ubot, get_uclient, get_msg, process_msg,
    is_user_active, add_active_batch, update_batch_progress,
    should_cancel, remove_active_batch, upd_dlg, UB, UC, Z
)
from utils.custom_filters import login_in_progress

logger = logging.getLogger(__name__)

# State storage for cloning conversations
CLONE_STATE: Dict[int, Dict[str, Any]] = {}
FAILED_TASKS: Dict[int, Dict[str, Any]] = {}


async def resolve_tg_chat(client, chat_identifier):
    """Resolves chat_identifier to Chat object and resolved_id with deep fallback search."""
    target_raw_id = str(chat_identifier).replace('-100', '') if str(chat_identifier).startswith('-100') else str(chat_identifier)
    
    # 1. Direct get_chat
    try:
        c_id = int(f"-100{target_raw_id}") if target_raw_id.isdigit() else chat_identifier
        chat = await client.get_chat(c_id)
        return chat, chat.id
    except Exception:
        pass

    # 2. Resolve peer
    try:
        peer = await client.resolve_peer(chat_identifier)
        if hasattr(peer, 'channel_id'):
            res_id = int(f"-100{peer.channel_id}")
        elif hasattr(peer, 'chat_id'):
            res_id = int(f"-{peer.chat_id}")
        elif hasattr(peer, 'user_id'):
            res_id = peer.user_id
        else:
            res_id = chat_identifier
        chat = await client.get_chat(res_id)
        return chat, res_id
    except Exception:
        pass

    # 3. Deep search in user's dialogs
    try:
        async for dialog in client.get_dialogs(limit=300):
            d_chat = dialog.chat
            if str(d_chat.id).replace('-100', '') == target_raw_id or getattr(d_chat, 'username', '') == str(chat_identifier).lstrip('@'):
                return d_chat, d_chat.id
    except Exception as e:
        logger.error(f"Error searching dialogs for {chat_identifier}: {e}")

    # 4. Fallback proxy chat object if numeric ID is valid
    if target_raw_id.isdigit():
        c_id = int(f"-100{target_raw_id}")
        class ProxyChat:
            def __init__(self, cid):
                self.id = cid
                self.title = f"Group ({cid})"
                self.description = ""
                self.photo = None
                self.is_forum = True
        return ProxyChat(c_id), c_id

    return None, chat_identifier


async def handle_link_flow(c: Client, m: Message, link_text: str, status_msg: Message):
    """Processes any Telegram link into Topic / Group Clone flow."""
    uid = m.from_user.id
    chat_id, topic_id, msg_id, link_type = parse_tg_link(link_text)

    if not chat_id:
        await status_msg.edit_text("❌ Invalid Telegram link format. Please provide a valid channel, group, or topic link.")
        CLONE_STATE.pop(uid, None)
        return

    uc = await get_uclient(uid)
    if not uc:
        await status_msg.edit_text("⚠️ User client session error. Please use `/login` first.")
        CLONE_STATE.pop(uid, None)
        return

    await status_msg.edit_text("⏳ Inspecting chat and discovering forum topics...")
    await upd_dlg(uc)

    chat_obj, resolved_id = await resolve_tg_chat(uc, chat_id)
    if not chat_obj:
        await status_msg.edit_text(
            "❌ Could not access this chat.\n"
            "Please make sure your logged-in account has joined this group/channel!"
        )
        CLONE_STATE.pop(uid, None)
        return

    chat_title = getattr(chat_obj, 'title', str(resolved_id))
    chat_desc = getattr(chat_obj, 'description', '')
    chat_photo = getattr(chat_obj.photo, 'big_file_id', None) if getattr(chat_obj, 'photo', None) else None
    is_forum = getattr(chat_obj, 'is_forum', True)

    CLONE_STATE[uid] = {
        'chat_id': resolved_id,
        'chat_title': chat_title,
        'chat_desc': chat_desc,
        'chat_photo': chat_photo,
        'link_type': link_type,
        'is_forum': is_forum
    }
    state = CLONE_STATE[uid]

    # Case 1: Specific Topic Link provided (e.g. .../49012 or .../49012/100)
    if topic_id is not None:
        state['topic_id'] = topic_id
        state['step'] = 'confirm_single_topic'

        await status_msg.edit_text(f"⏳ Fetching messages inside Topic `{topic_id}`...")
        msg_ids = await get_topic_messages_list(uc, resolved_id, topic_id)
        state['msg_ids'] = msg_ids
        state['all_msg_ids'] = list(msg_ids)
        state['topic_title'] = f"Topic #{topic_id}"

        btn = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"▶️ Start from Beginning ({len(msg_ids)})", callback_data="clone_start_topic"),
            ],
            [
                InlineKeyboardButton("⏭️ Resume / Skip First X", callback_data="clone_skip_topic_prompt"),
                InlineKeyboardButton("❌ Cancel", callback_data="clone_cancel")
            ]
        ])

        await status_msg.edit_text(
            f"📌 **Forum Topic Detected!**\n\n"
            f"📁 **Group:** {chat_title}\n"
            f"🏷️ **Topic ID:** `{topic_id}`\n"
            f"📊 **Messages Found:** `{len(msg_ids)}`\n\n"
            f"Choose an option to start cloning:",
            reply_markup=btn
        )
        return

    # Case 2: Full Forum Supergroup Link provided (e.g. https://t.me/c/2884241848)
    topics = await get_all_forum_topics(uc, resolved_id)
    if topics:
        state['topics'] = topics
        state['all_topics'] = list(topics)
        state['step'] = 'select_topic_mode'

        topics_list_text = "\n".join(
            [f"• `{i+1}.` 🔹 **{t['title']}** (`ID: {t['id']}`) - ~{t['total_messages']} msgs" for i, t in enumerate(topics[:15])]
        )
        if len(topics) > 15:
            topics_list_text += f"\n• ... and {len(topics) - 15} more topics"

        btn = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🚀 Clone All Topics ({len(topics)})", callback_data="clone_choose_destination"),
            ],
            [
                InlineKeyboardButton("🚫 Ignore Specific Topics", callback_data="clone_ignore_topics_prompt"),
                InlineKeyboardButton("🎯 Select Specific Topics", callback_data="clone_pick_topic")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="clone_cancel")
            ]
        ])

        await status_msg.edit_text(
            f"📁 **Forum Supergroup Detected!**\n\n"
            f"🏷️ **Group Title:** {chat_title}\n"
            f"📑 **Found {len(topics)} Topics:**\n\n"
            f"{topics_list_text}\n\n"
            f"Choose an option below to proceed:",
            reply_markup=btn
        )
        return

    # Case 3: Normal Channel or Group
    state['step'] = 'normal_chat_confirm'
    btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Clone All Messages", callback_data="clone_normal_all"),
            InlineKeyboardButton("❌ Cancel", callback_data="clone_cancel")
        ]
    ])

    await status_msg.edit_text(
        f"📢 **Channel / Group Detected:** {chat_title}\n\n"
        f"Do you want to clone messages from this chat?",
        reply_markup=btn
    )


@X.on_message(filters.command(['clone', 'topic', 'clonegroup', 'groupclone']) & filters.private, group=10)
async def clone_command_handler(c: Client, m: Message):
    uid = m.from_user.id

    if FREEMIUM_LIMIT == 0 and not await is_premium_user(uid):
        await m.reply_text("⚠️ This bot does not provide free services, get a subscription from OWNER.")
        return

    if await sub(c, m) == 1:
        return

    pro = await m.reply_text("🔍 Checking configuration, please hold on...")

    if is_user_active(uid):
        await pro.edit_text("⚠️ You already have an active task running. Use `/stop` or `/cancel` to cancel it first.")
        return

    ubot = await get_ubot(uid)
    if not ubot:
        await pro.edit_text("⚠️ Please add your bot using `/setbot <token>` first.")
        return

    uc = await get_uclient(uid)
    if not uc:
        await pro.edit_text("⚠️ User session not found! Please login using `/login` to access groups and topics.")
        return

    # Check if link was provided directly in command: /clone https://t.me/...
    args = m.text.split(maxsplit=1)
    if len(args) > 1:
        link_text = args[1].strip()
        await handle_link_flow(c, m, link_text, pro)
        return

    CLONE_STATE[uid] = {'step': 'waiting_link'}

    help_text = (
        "🚀 **Smart Topic & Group Cloner**\n\n"
        "Please send the **Group, Channel, or Forum Topic link**:\n\n"
        "📌 **Examples:**\n"
        "• Private Forum Group: `https://t.me/c/2884241848`\n"
        "• Specific Forum Topic: `https://t.me/c/2884241848/49012`\n"
        "• Public Group/Channel: `https://t.me/groupusername`\n\n"
        "👉 _The bot will automatically discover all topics and can create a brand new cloned group with same Name, DP & Topics!_"
    )

    await pro.edit_text(help_text)


@X.on_message(filters.regex(r'(https?://)?(t\.me|telegram\.me)/') & filters.private & ~login_in_progress, group=11)
async def auto_link_handler(c: Client, m: Message):
    """Automatically handles any Telegram link sent directly to the bot."""
    uid = m.from_user.id

    if uid in Z:
        return

    if is_user_active(uid):
        await m.reply_text("⚠️ You already have an active task running. Use `/stop` to cancel it.")
        return

    if FREEMIUM_LIMIT == 0 and not await is_premium_user(uid):
        await m.reply_text("⚠️ This bot does not provide free services, get a subscription from OWNER.")
        return

    if await sub(c, m) == 1:
        return

    ubot = await get_ubot(uid)
    if not ubot:
        await m.reply_text("⚠️ Please add your bot using `/setbot <token>` first.")
        return

    uc = await get_uclient(uid)
    if not uc:
        await m.reply_text("⚠️ User session not found! Please login using `/login` to access groups and topics.")
        return

    status_msg = await m.reply_text("🔍 Telegram link detected! Checking...")
    await handle_link_flow(c, m, m.text.strip(), status_msg)


@X.on_message(filters.text & filters.private & ~login_in_progress & ~filters.command([
    'start', 'batch', 'cancel', 'login', 'logout', 'stop', 'set', 
    'pay', 'redeem', 'gencode', 'single', 'generate', 'keyinfo', 'encrypt', 'decrypt', 'keys', 'setbot', 'rembot',
    'clone', 'topic', 'clonegroup', 'groupclone']), group=12)
async def clone_text_handler(c: Client, m: Message):
    uid = m.from_user.id
    if uid not in CLONE_STATE:
        return

    state = CLONE_STATE[uid]
    step = state.get('step')

    if step == 'waiting_link':
        status_msg = await m.reply_text("🔍 Processing link...")
        await handle_link_flow(c, m, m.text.strip(), status_msg)

    elif step == 'waiting_skip_count':
        input_val = m.text.strip()
        if not input_val.isdigit():
            await m.reply_text("❌ Please send a valid number (e.g. `21` to skip the first 21 messages).")
            return
        
        skip_count = int(input_val)
        all_msg_ids = state.get('all_msg_ids', [])
        if not all_msg_ids:
            all_msg_ids = state.get('msg_ids', [])
            state['all_msg_ids'] = list(all_msg_ids)

        if skip_count >= len(all_msg_ids):
            await m.reply_text(f"❌ Skip count ({skip_count}) is greater than or equal to total messages ({len(all_msg_ids)}).")
            return

        state['msg_ids'] = all_msg_ids[skip_count:]
        topic_title = state.get('topic_title', 'Topic')
        chat_title = state.get('chat_title', '')

        btn = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"▶️ Start Cloning ({len(state['msg_ids'])} msgs)", callback_data="clone_start_topic"),
                InlineKeyboardButton("❌ Cancel", callback_data="clone_cancel")
            ]
        ])

        await m.reply_text(
            f"⏭️ **Skipped first {skip_count} messages!**\n\n"
            f"📁 **Group:** {chat_title}\n"
            f"📂 **Topic:** {topic_title}\n"
            f"📊 **Remaining Messages to Clone:** `{len(state['msg_ids'])}`\n\n"
            f"Ready to proceed?",
            reply_markup=btn
        )

    elif step == 'waiting_ignore_topics':
        # User gave comma-separated topic numbers to ignore: e.g. "1, 3, 5"
        input_val = m.text.strip()
        all_topics = state.get('all_topics', [])
        raw_parts = [p.strip() for p in input_val.replace(' ', ',').split(',') if p.strip()]
        
        ignore_indices = set()
        ignore_ids = set()
        for p in raw_parts:
            if p.isdigit():
                val = int(p)
                # If 1-based index
                if 1 <= val <= len(all_topics):
                    ignore_indices.add(val - 1)
                else:
                    ignore_ids.add(val)

        remaining_topics = []
        for i, t in enumerate(all_topics):
            if i not in ignore_indices and t['id'] not in ignore_ids:
                remaining_topics.append(t)

        if not remaining_topics:
            await m.reply_text("❌ All topics were ignored! Please provide a valid ignore list.")
            return

        state['topics'] = remaining_topics
        ignored_count = len(all_topics) - len(remaining_topics)

        # Proceed to destination choice
        chat_title = state.get('chat_title', 'Group')
        btn = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🆕 Auto-Create New Cloned Group ({len(remaining_topics)} Topics)", callback_data="clone_mode_new_group")
            ],
            [
                InlineKeyboardButton("🎯 Clone into Configured Chat / PM", callback_data="clone_mode_existing_chat")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="clone_cancel")
            ]
        ])

        await m.reply_text(
            f"✅ **{ignored_count} topic(s) ignored.**\n"
            f"📑 **{len(remaining_topics)} topics will be cloned.**\n\n"
            f"Choose destination to start:",
            reply_markup=btn
        )

    elif step == 'waiting_topic_number':
        input_val = m.text.strip()
        all_topics = state.get('all_topics', state.get('topics', []))

        # Check if user entered multiple topics to clone (e.g. "1, 2, 4" or single "3")
        raw_parts = [p.strip() for p in input_val.replace(' ', ',').split(',') if p.strip()]
        selected_topics = []

        for p in raw_parts:
            if p.isdigit():
                idx = int(p)
                if 1 <= idx <= len(all_topics):
                    selected_topics.append(all_topics[idx - 1])
                else:
                    for t in all_topics:
                        if t['id'] == idx:
                            selected_topics.append(t)
                            break

        if not selected_topics:
            await m.reply_text(
                f"❌ Invalid selection. Please send topic numbers (e.g. `1` or `1, 2, 4`)."
            )
            return

        if len(selected_topics) == 1:
            # Single topic selected
            selected_topic = selected_topics[0]
            state['topic_id'] = selected_topic['id']
            state['topic_title'] = selected_topic['title']
            state['step'] = 'confirm_single_topic'

            uc = await get_uclient(uid)
            status_msg = await m.reply_text(f"⏳ Discovering messages for topic '{selected_topic['title']}'...")
            msg_ids = await get_topic_messages_list(uc, state['chat_id'], selected_topic['id'])
            state['msg_ids'] = msg_ids
            state['all_msg_ids'] = list(msg_ids)

            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"▶️ Start from Beginning ({len(msg_ids)})", callback_data="clone_start_topic"),
                ],
                [
                    InlineKeyboardButton("⏭️ Resume / Skip First X", callback_data="clone_skip_topic_prompt"),
                    InlineKeyboardButton("❌ Cancel", callback_data="clone_cancel")
                ]
            ])

            await status_msg.edit_text(
                f"📌 **Topic Selected:** {selected_topic['title']}\n"
                f"🏷️ **Topic ID:** `{selected_topic['id']}`\n"
                f"📊 **Messages Found:** `{len(msg_ids)}`\n\n"
                f"Ready to clone all contents belonging to this topic?",
                reply_markup=btn
            )
        else:
            # Multiple topics selected
            state['topics'] = selected_topics
            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"🆕 Auto-Create New Group ({len(selected_topics)} Topics)", callback_data="clone_mode_new_group")
                ],
                [
                    InlineKeyboardButton("🎯 Clone into Configured Chat / PM", callback_data="clone_mode_existing_chat")
                ],
                [
                    InlineKeyboardButton("❌ Cancel", callback_data="clone_cancel")
                ]
            ])

            await m.reply_text(
                f"🎯 **{len(selected_topics)} topics selected for cloning.**\n\n"
                f"Choose destination to start:",
                reply_markup=btn
            )


@X.on_callback_query(filters.regex(r'^clone_'))
async def clone_callback_handler(c: Client, cb: CallbackQuery):
    uid = cb.from_user.id
    data = cb.data

    # Handle Retry of Failed Tasks even if CLONE_STATE is empty
    if data == "clone_retry_failed":
        if uid in FAILED_TASKS:
            task_info = FAILED_TASKS[uid]
            await cb.answer("Retrying failed messages...")
            asyncio.create_task(
                run_retry_failed_cloning(c=c, uid=uid, status_msg=cb.message, task_info=task_info)
            )
            return
        else:
            await cb.answer("No failed task info available.", show_alert=True)
            return

    if uid not in CLONE_STATE:
        await cb.answer("Session expired or task already started/cancelled.", show_alert=True)
        try:
            await cb.message.delete()
        except Exception:
            pass
        return

    state = CLONE_STATE[uid]

    if data == "clone_cancel":
        CLONE_STATE.pop(uid, None)
        await cb.answer("Cancelled.")
        await cb.message.edit_text("❌ Clone operation cancelled.")
        return

    elif data == "clone_skip_topic_prompt":
        state['step'] = 'waiting_skip_count'
        all_msgs = state.get('all_msg_ids', [])
        if not all_msgs:
            all_msgs = state.get('msg_ids', [])
            state['all_msg_ids'] = list(all_msgs)
        await cb.answer()
        await cb.message.edit_text(
            f"🔢 **Resume / Skip Setup:**\n\n"
            f"Total messages available: `{len(all_msgs)}`\n\n"
            f"👉 **Send the number of messages to skip:**\n"
            f"_(For example, send `21` to skip the first 21 already downloaded videos and start from #22)_"
        )
        return

    elif data == "clone_ignore_topics_prompt":
        topics = state.get('all_topics', state.get('topics', []))
        state['step'] = 'waiting_ignore_topics'

        topics_text = "🚫 **Ignore Topics Setup:**\n\n"
        for i, t in enumerate(topics[:30], 1):
            topics_text += f"`{i}.` 🔹 **{t['title']}** (`ID: {t['id']}`)\n"

        if len(topics) > 30:
            topics_text += f"\n... and {len(topics) - 30} more."

        topics_text += "\n👉 **Send the numbers of topics to IGNORE separated by comma (e.g. `1, 3, 5`):**"

        await cb.answer()
        await cb.message.edit_text(topics_text)
        return

    elif data == "clone_pick_topic":
        topics = state.get('all_topics', state.get('topics', []))
        state['step'] = 'waiting_topic_number'

        topics_text = "🔢 **Please reply with the number(s) of the topic(s) to clone:**\n\n"
        for i, t in enumerate(topics[:30], 1):
            topics_text += f"`{i}.` 🔹 **{t['title']}** (`ID: {t['id']}`)\n"

        if len(topics) > 30:
            topics_text += f"\n... and {len(topics) - 30} more."

        topics_text += "\n_(You can send a single number like `2` or multiple like `1, 3, 4`)_"

        await cb.answer()
        await cb.message.edit_text(topics_text)
        return

    elif data == "clone_choose_destination":
        chat_title = state.get('chat_title', 'Group')
        topics_count = len(state.get('topics', []))
        btn = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🆕 Auto-Create New Cloned Group ({topics_count} Topics)", callback_data="clone_mode_new_group")
            ],
            [
                InlineKeyboardButton("🎯 Clone into Configured Chat / PM", callback_data="clone_mode_existing_chat")
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="clone_cancel")
            ]
        ])

        await cb.answer()
        await cb.message.edit_text(
            f"🎯 **Choose Destination for Cloning '{chat_title}':**\n\n"
            f"1. **🆕 Auto-Create New Cloned Group**:\n"
            f"> Creates a brand new Supergroup on your account with the **same Name, same DP/PFP**, enables forum topics, creates all matching topics with exact IDs, and uploads everything there automatically!\n\n"
            f"2. **🎯 Configured Chat / PM**:\n"
            f"> Uploads into the target chat ID configured in `/settings` (or your private bot chat).",
            reply_markup=btn
        )
        return

    elif data in ["clone_mode_new_group", "clone_mode_existing_chat"]:
        is_new_group = (data == "clone_mode_new_group")
        await cb.answer("Starting cloning...")
        topics = state.get('topics', [])
        chat_id = state.get('chat_id')
        chat_title = state.get('chat_title', str(chat_id))
        chat_desc = state.get('chat_desc', '')
        chat_photo = state.get('chat_photo', None)
        link_type = state.get('link_type', 'private')

        if not topics:
            await cb.message.edit_text("⚠️ No topics found in this group.")
            CLONE_STATE.pop(uid, None)
            return

        asyncio.create_task(
            run_full_group_cloning(
                c=c,
                uid=uid,
                status_msg=cb.message,
                chat_id=chat_id,
                chat_title=chat_title,
                chat_desc=chat_desc,
                chat_photo=chat_photo,
                topics=topics,
                link_type=link_type,
                auto_create_new_group=is_new_group
            )
        )
        return

    elif data == "clone_start_topic":
        await cb.answer("Starting topic cloning...")
        topic_id = state.get('topic_id')
        topic_title = state.get('topic_title', f'Topic {topic_id}')
        msg_ids = state.get('msg_ids', [])
        chat_id = state.get('chat_id')
        chat_title = state.get('chat_title', str(chat_id))
        link_type = state.get('link_type', 'private')

        if not msg_ids:
            await cb.message.edit_text("⚠️ No messages found in this topic to clone.")
            CLONE_STATE.pop(uid, None)
            return

        asyncio.create_task(
            run_single_topic_cloning(
                c=c,
                uid=uid,
                status_msg=cb.message,
                chat_id=chat_id,
                chat_title=chat_title,
                topic_id=topic_id,
                topic_title=topic_title,
                msg_ids=msg_ids,
                link_type=link_type
            )
        )
        return

    elif data == "clone_normal_all":
        await cb.answer("Starting channel cloning...")
        chat_id = state.get('chat_id')
        chat_title = state.get('chat_title', str(chat_id))
        link_type = state.get('link_type', 'private')

        asyncio.create_task(
            run_normal_channel_cloning(
                c=c,
                uid=uid,
                status_msg=cb.message,
                chat_id=chat_id,
                chat_title=chat_title,
                link_type=link_type
            )
        )
        return


async def run_single_topic_cloning(
    c: Client,
    uid: int,
    status_msg: Message,
    chat_id: Any,
    chat_title: str,
    topic_id: int,
    topic_title: str,
    msg_ids: List[int],
    link_type: str
):
    """Clones all messages from a single topic with automatic retries and resume support."""
    ubot = await get_ubot(uid)
    uc = await get_uclient(uid)

    if not ubot or not uc:
        await status_msg.edit_text("❌ Setup missing: Bot or user client unavailable.")
        CLONE_STATE.pop(uid, None)
        return

    total = len(msg_ids)
    success = 0
    failed = 0
    failed_ids = []

    await add_active_batch(uid, {
        "total": total,
        "current": 0,
        "success": 0,
        "cancel_requested": False,
        "progress_message_id": status_msg.id,
        "type": "topic_clone"
    })

    await status_msg.edit_text(
        f"⚡ **Smart Topic Cloner Active...**\n\n"
        f"📁 **Group:** {chat_title}\n"
        f"📂 **Topic:** {topic_title} (`ID: {topic_id}`)\n"
        f"📊 **Messages to Clone:** `{total}`\n"
        f"🚀 **Status:** Processing..."
    )

    try:
        dest_chat = await get_user_data_key(str(uid), 'chat_id', None)
        target_override = None
        topic_override = None

        if dest_chat:
            if '/' in dest_chat:
                parts = dest_chat.split('/', 1)
                target_override = int(parts[0])
                topic_override = int(parts[1]) if len(parts) > 1 else None
            else:
                target_override = int(dest_chat)

        for idx, mid in enumerate(msg_ids, 1):
            if should_cancel(uid):
                await status_msg.edit_text(
                    f"⛔ **Clone Cancelled by User!**\n\n"
                    f"📂 Topic: {topic_title}\n"
                    f"📊 Progress: `{idx - 1}/{total}`\n"
                    f"✅ Success: `{success}`"
                )
                break

            await update_batch_progress(uid, idx, success)

            # Retry up to 2 times per message to prevent false failures
            cloned = False
            for attempt in range(2):
                try:
                    msg = await get_msg(ubot, uc, str(chat_id), mid, link_type)
                    if msg:
                        res = await process_msg(
                            ubot, uc, msg, str(uid), link_type, uid, str(chat_id),
                            target_override=target_override,
                            topic_override=topic_override
                        )
                        if any(k in str(res) for k in ['Done', 'Copied', 'Sent', 'directly']):
                            success += 1
                            cloned = True
                            break
                    else:
                        await asyncio.sleep(1)
                except FloodWait as e:
                    logger.warning(f"FloodWait hit: sleeping for {e.value + 1}s")
                    await asyncio.sleep(e.value + 1)
                except Exception as e:
                    logger.error(f"Attempt {attempt+1} error cloning msg {mid}: {e}")
                    await asyncio.sleep(1)

            if not cloned:
                failed += 1
                failed_ids.append(mid)

            if idx % 3 == 0 or idx == total:
                percent = int((idx / total) * 100)
                bar = '🟢' * int(percent / 10) + '🔴' * (10 - int(percent / 10))
                try:
                    await status_msg.edit_text(
                        f"⚡ **Smart Topic Cloner Active...**\n\n"
                        f"📁 **Group:** {chat_title}\n"
                        f"📂 **Topic:** {topic_title} (`ID: {topic_id}`)\n"
                        f"{bar} `{percent}%`\n\n"
                        f"📊 **Progress:** `{idx}/{total}`\n"
                        f"✅ **Success:** `{success}` | ❌ **Failed:** `{failed}`\n"
                        f"⏳ Use `/stop` to cancel."
                    )
                except Exception:
                    pass

            await asyncio.sleep(1.2)

        if not should_cancel(uid):
            btn = None
            if failed_ids:
                FAILED_TASKS[uid] = {
                    'chat_id': chat_id,
                    'chat_title': chat_title,
                    'topic_id': topic_id,
                    'topic_title': topic_title,
                    'failed_ids': failed_ids,
                    'link_type': link_type,
                    'target_override': target_override,
                    'topic_override': topic_override
                }
                btn = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🔄 Retry Failed Messages ({len(failed_ids)})", callback_data="clone_retry_failed")]
                ])

            await c.send_message(
                uid,
                f"🎉 **Topic Clone Finished!**\n\n"
                f"📁 **Group:** {chat_title}\n"
                f"📂 **Topic:** {topic_title} (`ID: {topic_id}`)\n"
                f"📊 **Total Processed:** `{total}`\n"
                f"✅ **Cloned:** `{success}`\n"
                f"❌ **Skipped/Failed:** `{failed}`",
                reply_markup=btn
            )

    finally:
        await remove_active_batch(uid)
        CLONE_STATE.pop(uid, None)


async def run_full_group_cloning(
    c: Client,
    uid: int,
    status_msg: Message,
    chat_id: Any,
    chat_title: str,
    chat_desc: str,
    chat_photo: Any,
    topics: List[Dict[str, Any]],
    link_type: str,
    auto_create_new_group: bool = False
):
    """Clones all topics from a forum supergroup."""
    ubot = await get_ubot(uid)
    uc = await get_uclient(uid)

    if not ubot or not uc:
        await status_msg.edit_text("❌ Setup missing: Bot or user client unavailable.")
        CLONE_STATE.pop(uid, None)
        return

    total_topics = len(topics)
    total_cloned = 0
    total_failed = 0

    await add_active_batch(uid, {
        "total": total_topics,
        "current": 0,
        "success": 0,
        "cancel_requested": False,
        "progress_message_id": status_msg.id,
        "type": "full_group_clone"
    })

    base_target_chat = None
    created_group_link = None
    dest_is_forum = False

    if auto_create_new_group:
        await status_msg.edit_text(
            f"🛠️ **Creating Brand New Supergroup...**\n\n"
            f"🏷️ Title: **{chat_title}**\n"
            f"🖼️ Setting Profile Picture: {'Yes' if chat_photo else 'No'}\n"
            f"📑 Enabling Forum Topics & Promoting Bot as Admin..."
        )
        new_chat_id, invite_link = await create_cloned_supergroup(
            client=uc,
            bot_client=ubot,
            title=chat_title,
            description=chat_desc,
            photo_file_id=chat_photo
        )
        if new_chat_id:
            base_target_chat = new_chat_id
            created_group_link = invite_link
            dest_is_forum = True
            await c.send_message(
                uid,
                f"🎉 **New Cloned Supergroup Created Successfully!**\n\n"
                f"🏷️ **Title:** {chat_title}\n"
                f"🔗 **Invite Link:** {invite_link or 'Created in your account'}\n"
                f"⚙️ **Status:** Topics creation & content upload started..."
            )
        else:
            await c.send_message(uid, "⚠️ Auto-group creation failed, falling back to configured chat / PM.")
            base_target_chat = uid
    else:
        dest_chat = await get_user_data_key(str(uid), 'chat_id', None)
        if dest_chat:
            if '/' in dest_chat:
                parts = dest_chat.split('/', 1)
                base_target_chat = int(parts[0])
            else:
                base_target_chat = int(dest_chat)
        else:
            base_target_chat = uid

        try:
            dest_obj = await uc.get_chat(base_target_chat)
            dest_is_forum = getattr(dest_obj, 'is_forum', False)
        except Exception:
            dest_is_forum = False

    group_display_link = f" [🔗 Open Group]({created_group_link})" if created_group_link else ""
    await status_msg.edit_text(
        f"🚀 **Full Group Cloning Active!**\n\n"
        f"📁 **Source Group:** {chat_title}\n"
        f"📑 **Total Topics:** `{total_topics}`\n"
        f"🎯 **Destination:** `{'Auto-Created Cloned Forum' if auto_create_new_group else 'Configured Chat/PM'}`{group_display_link}\n\n"
        f"Starting topic-by-topic cloning..."
    )

    try:
        for t_idx, topic in enumerate(topics, 1):
            if should_cancel(uid):
                await status_msg.edit_text(
                    f"⛔ **Group Cloning Cancelled!**\n\n"
                    f"📂 Topics Processed: `{t_idx - 1}/{total_topics}`\n"
                    f"✅ Total Messages Cloned: `{total_cloned}`"
                )
                break

            t_id = topic['id']
            t_title = topic.get('title', f"Topic {t_id}")

            msg_ids = await get_topic_messages_list(uc, chat_id, t_id)
            topic_total = len(msg_ids)

            if not msg_ids:
                continue

            dest_topic_id = None
            if dest_is_forum:
                try:
                    created_id = await create_forum_topic_safe(uc, base_target_chat, t_title)
                    if not created_id:
                        created_id = await create_forum_topic_safe(ubot, base_target_chat, t_title)
                    dest_topic_id = created_id
                    logger.info(f"Target topic ID for '{t_title}': {dest_topic_id}")
                except Exception as ex:
                    logger.error(f"Could not create topic '{t_title}' in dest: {ex}")
            else:
                try:
                    await ubot.send_message(
                        base_target_chat,
                        f"📌 ═════════════════════════\n"
                        f"📂 **Topic: {t_title}** (`ID: {t_id}`)\n"
                        f"📊 Total Messages: `{topic_total}`\n"
                        f"════════════════════════════"
                    )
                except Exception:
                    pass

            for m_idx, mid in enumerate(msg_ids, 1):
                if should_cancel(uid):
                    break

                cloned = False
                for attempt in range(2):
                    try:
                        msg = await get_msg(ubot, uc, str(chat_id), mid, link_type)
                        if msg:
                            res = await process_msg(
                                ubot, uc, msg, str(uid), link_type, uid, str(chat_id),
                                target_override=base_target_chat,
                                topic_override=dest_topic_id
                            )
                            if any(k in str(res) for k in ['Done', 'Copied', 'Sent', 'directly']):
                                total_cloned += 1
                                cloned = True
                                break
                        else:
                            await asyncio.sleep(1)
                    except FloodWait as e:
                        logger.warning(f"FloodWait hit in group clone: sleeping for {e.value + 1}s")
                        await asyncio.sleep(e.value + 1)
                    except Exception as e:
                        logger.error(f"Attempt {attempt+1} error cloning msg {mid} in topic {t_id}: {e}")
                        await asyncio.sleep(1)

                if not cloned:
                    total_failed += 1

                if m_idx % 3 == 0 or m_idx == topic_total:
                    try:
                        await status_msg.edit_text(
                            f"⚡ **Full Group Cloner Active...**\n\n"
                            f"📁 **Source:** {chat_title}\n"
                            f"📂 **Current Topic:** {t_title} (`{t_idx}/{total_topics}`)\n"
                            f"📊 **Topic Progress:** `{m_idx}/{topic_total}`\n"
                            f"⚡ **Total Cloned:** `{total_cloned}`\n\n"
                            f"⏳ Use `/stop` to cancel."
                        )
                    except Exception:
                        pass

                await asyncio.sleep(1.2)

        if not should_cancel(uid):
            link_info = f"\n🔗 **New Cloned Group:** {created_group_link}" if created_group_link else ""
            await c.send_message(
                uid,
                f"🎉 **Full Group Cloning Completed!**\n\n"
                f"📁 **Group:** {chat_title}\n"
                f"📑 **Topics Processed:** `{total_topics}`\n"
                f"✅ **Total Messages Cloned:** `{total_cloned}`\n"
                f"❌ **Skipped/Failed:** `{total_failed}`"
                f"{link_info}"
            )

    finally:
        await remove_active_batch(uid)
        CLONE_STATE.pop(uid, None)


async def run_retry_failed_cloning(c: Client, uid: int, status_msg: Message, task_info: Dict[str, Any]):
    """Retries only the failed messages from a previous cloning run."""
    ubot = await get_ubot(uid)
    uc = await get_uclient(uid)

    if not ubot or not uc:
        await status_msg.edit_text("❌ Setup missing: Bot or user client unavailable.")
        return

    failed_ids = task_info.get('failed_ids', [])
    chat_id = task_info.get('chat_id')
    chat_title = task_info.get('chat_title', '')
    topic_id = task_info.get('topic_id')
    topic_title = task_info.get('topic_title', '')
    link_type = task_info.get('link_type', 'private')
    target_override = task_info.get('target_override')
    topic_override = task_info.get('topic_override')

    if not failed_ids:
        await status_msg.edit_text("✅ No failed messages to retry.")
        return

    total = len(failed_ids)
    success = 0
    failed = 0
    new_failed_ids = []

    await add_active_batch(uid, {
        "total": total,
        "current": 0,
        "success": 0,
        "cancel_requested": False,
        "progress_message_id": status_msg.id,
        "type": "retry_clone"
    })

    await status_msg.edit_text(
        f"🔄 **Retrying {total} Failed Messages...**\n\n"
        f"📁 **Group:** {chat_title}\n"
        f"📂 **Topic:** {topic_title}\n"
        f"⏳ Processing retries..."
    )

    try:
        for idx, mid in enumerate(failed_ids, 1):
            if should_cancel(uid):
                await status_msg.edit_text(f"⛔ Retry cancelled. Success: {success}/{total}")
                break

            await update_batch_progress(uid, idx, success)

            cloned = False
            for attempt in range(2):
                try:
                    msg = await get_msg(ubot, uc, str(chat_id), mid, link_type)
                    if msg:
                        res = await process_msg(
                            ubot, uc, msg, str(uid), link_type, uid, str(chat_id),
                            target_override=target_override,
                            topic_override=topic_override
                        )
                        if any(k in str(res) for k in ['Done', 'Copied', 'Sent', 'directly']):
                            success += 1
                            cloned = True
                            break
                    else:
                        await asyncio.sleep(1)
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except Exception as e:
                    logger.error(f"Retry error on msg {mid}: {e}")
                    await asyncio.sleep(1)

            if not cloned:
                failed += 1
                new_failed_ids.append(mid)

            if idx % 3 == 0 or idx == total:
                try:
                    await status_msg.edit_text(
                        f"🔄 **Retrying Failed Messages...**\n\n"
                        f"📊 Progress: `{idx}/{total}`\n"
                        f"✅ Success: `{success}` | ❌ Still Failed: `{failed}`"
                    )
                except Exception:
                    pass

            await asyncio.sleep(1.2)

        FAILED_TASKS[uid]['failed_ids'] = new_failed_ids
        btn = None
        if new_failed_ids:
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🔄 Retry Again ({len(new_failed_ids)})", callback_data="clone_retry_failed")]
            ])

        await c.send_message(
            uid,
            f"🎉 **Retry Complete!**\n\n"
            f"✅ **Recovered/Cloned:** `{success}/{total}`\n"
            f"❌ **Unrecoverable/Deleted:** `{failed}`",
            reply_markup=btn
        )
    finally:
        await remove_active_batch(uid)


async def run_normal_channel_cloning(
    c: Client,
    uid: int,
    status_msg: Message,
    chat_id: Any,
    chat_title: str,
    link_type: str
):
    """Clones messages from a non-forum channel or group."""
    ubot = await get_ubot(uid)
    uc = await get_uclient(uid)

    if not ubot or not uc:
        await status_msg.edit_text("❌ Setup missing: Bot or user client unavailable.")
        CLONE_STATE.pop(uid, None)
        return

    await status_msg.edit_text("⏳ Discovering messages in channel...")

    msg_ids = []
    try:
        maxlimit = PREMIUM_LIMIT if await is_premium_user(uid) else FREEMIUM_LIMIT
        async for msg in uc.get_chat_history(chat_id, limit=maxlimit):
            if msg and not getattr(msg, 'empty', False):
                msg_ids.append(msg.id)
    except Exception as e:
        logger.error(f"Error discovering channel history for {chat_id}: {e}")

    if not msg_ids:
        await status_msg.edit_text("❌ No messages found in this channel/group.")
        CLONE_STATE.pop(uid, None)
        return

    msg_ids.reverse()
    total = len(msg_ids)
    success = 0
    failed = 0

    await add_active_batch(uid, {
        "total": total,
        "current": 0,
        "success": 0,
        "cancel_requested": False,
        "progress_message_id": status_msg.id,
        "type": "channel_clone"
    })

    dest_chat = await get_user_data_key(str(uid), 'chat_id', None)
    target_override = None
    topic_override = None
    if dest_chat:
        if '/' in dest_chat:
            parts = dest_chat.split('/', 1)
            target_override = int(parts[0])
            topic_override = int(parts[1]) if len(parts) > 1 else None
        else:
            target_override = int(dest_chat)

    try:
        for idx, mid in enumerate(msg_ids, 1):
            if should_cancel(uid):
                await status_msg.edit_text(
                    f"⛔ **Channel Clone Cancelled!**\n\n"
                    f"📊 Progress: `{idx - 1}/{total}`\n"
                    f"✅ Success: `{success}`"
                )
                break

            await update_batch_progress(uid, idx, success)

            cloned = False
            for attempt in range(2):
                try:
                    msg = await get_msg(ubot, uc, str(chat_id), mid, link_type)
                    if msg:
                        res = await process_msg(
                            ubot, uc, msg, str(uid), link_type, uid, str(chat_id),
                            target_override=target_override,
                            topic_override=topic_override
                        )
                        if any(k in str(res) for k in ['Done', 'Copied', 'Sent', 'directly']):
                            success += 1
                            cloned = True
                            break
                    else:
                        await asyncio.sleep(1)
                except FloodWait as e:
                    logger.warning(f"FloodWait hit in channel clone: sleeping for {e.value + 1}s")
                    await asyncio.sleep(e.value + 1)
                except Exception as e:
                    logger.error(f"Attempt {attempt+1} error cloning channel msg {mid}: {e}")
                    await asyncio.sleep(1)

            if not cloned:
                failed += 1

            if idx % 3 == 0 or idx == total:
                percent = int((idx / total) * 100)
                bar = '🟢' * int(percent / 10) + '🔴' * (10 - int(percent / 10))
                try:
                    await status_msg.edit_text(
                        f"⚡ **Channel Cloner Active...**\n\n"
                        f"📢 **Channel:** {chat_title}\n"
                        f"{bar} `{percent}%`\n\n"
                        f"📊 **Progress:** `{idx}/{total}`\n"
                        f"✅ **Success:** `{success}` | ❌ **Failed:** `{failed}`\n"
                        f"⏳ Use `/stop` to cancel."
                    )
                except Exception:
                    pass

            await asyncio.sleep(1.2)

        if not should_cancel(uid):
            await c.send_message(
                uid,
                f"🎉 **Channel Cloning Completed!**\n\n"
                f"📢 **Channel:** {chat_title}\n"
                f"📊 **Total Messages:** `{total}`\n"
                f"✅ **Cloned:** `{success}`\n"
                f"❌ **Skipped/Failed:** `{failed}`"
            )

    finally:
        await remove_active_batch(uid)
        CLONE_STATE.pop(uid, None)
