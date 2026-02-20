
# Copyright (c) 2025 Gagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

from shared_client import client as bot_client, app
from telethon import events
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton as IK, InlineKeyboardMarkup as IKM
from datetime import timedelta
from config import OWNER_ID, JOIN_LINK as JL , ADMIN_CONTACT as AC
from utils.func import (
    add_premium_user, is_private_chat, a1, a2, a3, a4, a5,
    a7, a8, a9, a10, a11, premium_users_collection, get_display_name
)
import base64 as spy
from plugins.start import subscribe


@bot_client.on(events.NewMessage(pattern='/add'))
async def add_premium_handler(event):
    if not await is_private_chat(event):
        await event.respond(
            'This command can only be used in private chats for security reasons.'
        )
        return

    """Handle /add command to add premium users (owner only)"""
    user_id = event.sender_id
    if user_id not in OWNER_ID:
        await event.respond('This command is restricted to the bot owner.')
        return

    text = event.message.text.strip()
    parts = text.split(' ')
    if len(parts) != 4:
        await event.respond(
            """Invalid format. Use: /add user_id duration_value duration_unit
Example: /add 123456 1 week"""
        )
        return

    try:
        target_user_id = int(parts[1])
        duration_value = int(parts[2])
        duration_unit = parts[3].lower()
        valid_units = ['min', 'hours', 'days', 'weeks', 'month', 'year', 'decades']
        if duration_unit not in valid_units:
            await event.respond(
                f"Invalid duration unit. Choose from: {', '.join(valid_units)}"
            )
            return

        success, result = await add_premium_user(target_user_id, duration_value, duration_unit)
        if success:
            expiry_utc = result
            expiry_ist = expiry_utc + timedelta(hours=5, minutes=30)
            formatted_expiry = expiry_ist.strftime('%d-%b-%Y %I:%M:%S %p')
            await event.respond(
                f"""✅ User {target_user_id} added as premium member
Subscription valid until: {formatted_expiry} (IST)"""
            )
            await bot_client.send_message(target_user_id,
                f"""✅ You have been added as premium member
**Validity upto**: {formatted_expiry} (IST)"""
            )
        else:
            await event.respond(f'❌ Failed to add premium user: {result}')

    except ValueError:
        await event.respond(
            'Invalid user ID or duration value. Both must be integers.'
        )
    except Exception as e:
        await event.respond(f'Error: {str(e)}')


@app.on_message(filters.command("get"))
async def get_users(client, message):
    if isinstance(OWNER_ID, list):
        if message.from_user.id not in OWNER_ID:
            return await message.reply("🚫 You are not authorized.")
    else:
        if message.from_user.id != OWNER_ID:
            return await message.reply("🚫 You are not authorized.")

    try:
        users = await premium_users_collection.find().to_list(length=1000)
        if not users:
            return await message.reply("❌ No premium users found.")

        text_lines = []
        for user in users:
            user_id = user["user_id"]
            try:
                user_entity = await app.get_users(user_id)
                name = get_display_name(user_entity)
                username = f"@{user_entity.username}" if user_entity.username else "NoUsername"
                line = f"{name} ({username}) - `{user_id}`"
            except Exception:
                line = f"Unknown - `({user_id})`"
            text_lines.append(line)

        final_text = f"👥 Total Premium Users: {len(text_lines)}\n\n" + "\n".join(text_lines)

        if len(final_text) > 4000:
            with open("premium_users.txt", "w", encoding="utf-8") as f:
                f.write(final_text)
            await message.reply_document("premium_users.txt", caption="📄 Premium User List")
        else:
            await message.reply(final_text)

    except Exception as e:
        await message.reply(f"❌ Error while fetching users: {str(e)}")


attr1 = spy.b64encode("photo".encode()).decode()
attr2 = spy.b64encode("file_id".encode()).decode()

@app.on_message(filters.command(spy.b64decode(a5.encode()).decode()))
async def start_handler(client, message):
    subscription_status = await subscribe(client, message)
    if subscription_status == 1:
        return

    b7 = spy.b64decode(a8).decode()
    b8 = spy.b64decode(a9).decode()
    welcome_text = spy.b64decode(a7).decode().format(user=message.from_user.first_name)
    photo_url = spy.b64decode(a10).decode()
    kb = IKM([
        [IK(b7, url=JL)],
        [IK(b8, url=AC)]
    ])
    await message.reply_photo(
        photo=photo_url,
        caption=welcome_text,
        reply_markup=kb
    )
