
# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from config import API_ID, API_HASH, BOT_TOKEN, STRING
from pyrogram import Client
from pyrogram.errors import FloodWait
import sys

client = TelegramClient("telethonbot", API_ID, API_HASH)
app = Client("pyrogrambot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("4gbbot", api_id=API_ID, api_hash=API_HASH, session_string=STRING)

async def start_client():
    if not client.is_connected():
        try:
            await client.start(bot_token=BOT_TOKEN)
            print("SpyLib started...")
        except FloodWaitError as e:
            print(f"⚠️ Telegram Rate Limit on Bot Token: Wait of {e.seconds}s required on this BOT_TOKEN.")
            print("💡 TIP: Change BOT_TOKEN from @BotFather in Render Environment Variables to start immediately without waiting!")
            raise e
    if STRING:
        try:
            await userbot.start()
            print("Userbot started...")
        except Exception as e:
            print(f"Hey honey!! check your premium string session, it may be invalid or expired: {e}")
            sys.exit(1)
    await app.start()
    print("Pyro App Started...")
    return client, app, userbot

