
# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

from datetime import timedelta, datetime
from shared_client import client as bot_client
from telethon import events
from utils.func import get_premium_details, is_private_chat, get_display_name, get_user_data, premium_users_collection, is_premium_user
from config import OWNER_ID
import logging
logging.basicConfig(format=
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger('teamspy')


@bot_client.on(events.NewMessage(pattern='/status'))
async def status_handler(event):
    if not await is_private_chat(event):
        await event.respond("This command can only be used in private chats for security reasons.")
        return
    
    """Handle /status command to check user session and bot status"""
    user_id = event.sender_id
    user_data = await get_user_data(user_id)
    
    session_active = False
    bot_active = False
    
    if user_data and "session_string" in user_data:
            session_active = True
    
    # Check if user has a custom bot
    if user_data and "bot_token" in user_data:
        bot_active = True
    
    # Add premium status check
    premium_status = "❌ Not a premium member"
    premium_details = await get_premium_details(user_id)
    if premium_details:
        # Convert to IST timezone
        expiry_utc = premium_details["subscription_end"]
        expiry_ist = expiry_utc + timedelta(hours=5, minutes=30)
        formatted_expiry = expiry_ist.strftime("%d-%b-%Y %I:%M:%S %p")
        premium_status = f"✅ Premium until {formatted_expiry} (IST)"
    
    await event.respond(
        "**Your current status:**\n\n"
        f"**Login Status:** {'✅ Active' if session_active else '❌ Inactive'}\n"
        f"**Premium:** {premium_status}"
    )

@bot_client.on(events.NewMessage(pattern='/transfer'))
async def transfer_premium_handler(event):
    if not await is_private_chat(event):
        await event.respond(
            'This command can only be used in private chats for security reasons.'
            )
        return
    user_id = event.sender_id
    sender = await event.get_sender()
    sender_name = get_display_name(sender)
    if not await is_premium_user(user_id):
        await event.respond(
            "❌ You don't have a premium subscription to transfer.")
        return
    args = event.text.split()
    if len(args) != 2:
        await event.respond(
            'Usage: /transfer user_id\nExample: /transfer 123456789')
        return
    try:
        target_user_id = int(args[1])
    except ValueError:
        await event.respond(
            '❌ Invalid user ID. Please provide a valid numeric user ID.')
        return
    if target_user_id == user_id:
        await event.respond('❌ You cannot transfer premium to yourself.')
        return
    if await is_premium_user(target_user_id):
        await event.respond(
            '❌ The target user already has a premium subscription.')
        return
    try:
        premium_details = await get_premium_details(user_id)
        if not premium_details:
            await event.respond('❌ Error retrieving your premium details.')
            return
        target_name = 'Unknown'
        try:
            target_entity = await bot_client.get_entity(target_user_id)
            target_name = get_display_name(target_entity)
        except Exception as e:
            logger.warning(f'Could not get target user name: {e}')
        now = datetime.now()
        expiry_date = premium_details['subscription_end']
        await premium_users_collection.update_one({'user_id':
            target_user_id}, {'$set': {'user_id': target_user_id,
            'subscription_start': now, 'subscription_end': expiry_date,
            'expireAt': expiry_date, 'transferred_from': user_id,
            'transferred_from_name': sender_name}}, upsert=True)
        await premium_users_collection.delete_one({'user_id': user_id})
        expiry_ist = expiry_date + timedelta(hours=5, minutes=30)
        formatted_expiry = expiry_ist.strftime('%d-%b-%Y %I:%M:%S %p')
        await event.respond(
            f'✅ Premium subscription successfully transferred to {target_name} ({target_user_id}). Your premium access has been removed.'
            )
        try:
            await bot_client.send_message(target_user_id,
                f'🎁 You have received a premium subscription transfer from {sender_name} ({user_id}). Your premium is valid until {formatted_expiry} (IST).'
                )
        except Exception as e:
            logger.error(f'Could not notify target user {target_user_id}: {e}')
        try:
            owner_id = int(OWNER_ID) if isinstance(OWNER_ID, str
                ) else OWNER_ID[0] if isinstance(OWNER_ID, list) else OWNER_ID
            await bot_client.send_message(owner_id,
                f'♻️ Premium Transfer: {sender_name} ({user_id}) has transferred their premium to {target_name} ({target_user_id}). Expiry: {formatted_expiry}'
                )
        except Exception as e:
            logger.error(f'Could not notify owner about premium transfer: {e}')
        return
    except Exception as e:
        logger.error(
            f'Error transferring premium from {user_id} to {target_user_id}: {e}'
            )
        await event.respond(f'❌ Error transferring premium: {str(e)}')
        return
@bot_client.on(events.NewMessage(pattern='/rem'))
async def remove_premium_handler(event):
    user_id = event.sender_id
    if not await is_private_chat(event):
        return
    if user_id not in OWNER_ID:
        return
    args = event.text.split()
    if len(args) != 2:
        await event.respond('Usage: /rem user_id\nExample: /rem 123456789')
        return
    try:
        target_user_id = int(args[1])
    except ValueError:
        await event.respond(
            '❌ Invalid user ID. Please provide a valid numeric user ID.')
        return
    if not await is_premium_user(target_user_id):
        await event.respond(
            f'❌ User {target_user_id} does not have a premium subscription.')
        return
    try:
        target_name = 'Unknown'
        try:
            target_entity = await bot_client.get_entity(target_user_id)
            target_name = get_display_name(target_entity)
        except Exception as e:
            logger.warning(f'Could not get target user name: {e}')
        result = await premium_users_collection.delete_one({'user_id':
            target_user_id})
        if result.deleted_count > 0:
            await event.respond(
                f'✅ Premium subscription successfully removed from {target_name} ({target_user_id}).'
                )
            try:
                await bot_client.send_message(target_user_id,
                    '⚠️ Your premium subscription has been removed by the administrator.'
                    )
            except Exception as e:
                logger.error(
                    f'Could not notify user {target_user_id} about premium removal: {e}'
                    )
        else:
            await event.respond(
                f'❌ Failed to remove premium from user {target_user_id}.')
        return
    except Exception as e:
        logger.error(f'Error removing premium from {target_user_id}: {e}')
        await event.respond(f'❌ Error removing premium: {str(e)}')
        return
