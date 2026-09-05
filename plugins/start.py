
# Copyright (c) 2025 devgagan : https://github.com/devgaganin.  
# Licensed under the GNU General Public License v3.0.  
# See LICENSE file in the repository root for full license text.

import logging
from datetime import datetime, timedelta
import psutil
from shared_client import app
from pyrogram import filters
from pyrogram.errors import UserNotParticipant, PeerIdInvalid, ChannelInvalid, ChatAdminRequired, ChannelPrivate
from pyrogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from config import LOG_GROUP, OWNER_ID, FORCE_SUB, JOIN_LINK as JL, ADMIN_CONTACT as AC, FREEMIUM_LIMIT, PREMIUM_LIMIT
from utils.func import is_premium_user, get_premium_details, get_user_data, users_collection, premium_users_collection

logger = logging.getLogger(__name__)

def get_start_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Clone Group/Topic", callback_data="btn_clone_help"),
            InlineKeyboardButton("📥 Batch Extract", callback_data="btn_batch_help")
        ],
        [
            InlineKeyboardButton("🔑 Login Session", callback_data="btn_login_info"),
            InlineKeyboardButton("⚙️ Settings", callback_data="btn_settings_info")
        ],
        [
            InlineKeyboardButton("📊 My Plan / Status", callback_data="btn_myplan"),
            InlineKeyboardButton("❓ Help & Commands", callback_data="help_0")
        ],
        [
            InlineKeyboardButton("📢 Updates Channel", url=JL if JL else "https://t.me/forcesub123"),
            InlineKeyboardButton("👨‍💻 Admin Support", url=AC if AC else "https://t.me/RixieHQ")
        ]
    ])

def get_start_text(name):
    return (
        f"👋 **Hello {name}!**\n\n"
        f"🚀 Welcome to the **Save Restricted Content & Forum Cloner Bot**!\n\n"
        f"✨ **What I Can Do:**\n"
        f"• 📥 **Direct & Batch Saver**: Download restricted media from private or public channels\n"
        f"• 📑 **Smart Forum Cloner**: Clone complete forum groups & topics with auto-admin promotion\n"
        f"• 🎯 **Topic-Specific Routing**: Upload directly into specific topics (`-100.../TOPIC_ID`)\n"
        f"• ⚙️ **Customization**: Custom thumbnail, rename tags, captions & word replacements\n\n"
        f"👇 *Choose an option below to get started:*"
    )

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    join = await subscribe(client, message)
    if join == 1:
        return

    name = message.from_user.first_name if message.from_user else "User"
    await message.reply_text(
        get_start_text(name),
        reply_markup=get_start_keyboard(),
        disable_web_page_preview=True
    )

@app.on_message(filters.command("myplan"))
async def myplan_command(client, message: Message):
    uid = message.from_user.id
    prem_info = await get_premium_details(uid)
    ud = await get_user_data(uid)
    has_session = bool(ud and ud.get('session_string'))
    has_bot = bool(ud and ud.get('bot_token'))
    chat_cfg = ud.get('chat_id', 'Not Set (PM)') if ud else 'Not Set (PM)'

    if prem_info:
        exp_utc = prem_info['subscription_end']
        exp_ist = exp_utc + timedelta(hours=5, minutes=30)
        formatted_exp = exp_ist.strftime('%d-%b-%Y %I:%M:%S %p')
        status_line = f"✅ **Active Premium** (Valid until: `{formatted_exp}` IST)"
        limit_line = f"Unlimited ({PREMIUM_LIMIT} msgs)"
    else:
        status_line = "🆓 **Free Tier**"
        limit_line = f"{FREEMIUM_LIMIT} msgs / day"

    text = (
        f"📊 **Your Account & Plan Details:**\n\n"
        f"👤 **User ID:** `{uid}`\n"
        f"💎 **Plan Status:** {status_line}\n"
        f"📈 **Limit:** `{limit_line}`\n"
        f"🔑 **User Session:** {'✅ Logged In' if has_session else '❌ Not Logged In (/login)'}\n"
        f"🧸 **Custom Bot:** {'✅ Configured' if has_bot else 'ℹ️ Optional (/setbot)'}\n"
        f"🎯 **Upload Destination:** `{chat_cfg}`\n\n"
        f"💡 To upgrade or extend, contact [Admin]({AC})."
    )
    await message.reply_text(text, disable_web_page_preview=True)

@app.on_message(filters.command("plan"))
async def plan_command(client, message: Message):
    text = (
        "💎 **Premium Subscription Plans:**\n\n"
        "⚡ **Features Included:**\n"
        "• Unlimited batch extractions & single downloads\n"
        "• Smart Forum Topic & Supergroup Cloning\n"
        "• Custom thumbnail, caption footers & word replacements\n"
        "• Direct uploads to private channels and topics\n"
        "• Priority support & fastest server speeds\n\n"
        "🗓️ **Pricing Options:**\n"
        "• 1 Week Access\n"
        "• 1 Month Access\n"
        "• Lifetime / Custom Plans\n\n"
        f"👉 Contact **[Admin Support]({AC})** to purchase your premium subscription!"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Contact Owner to Buy", url=AC if AC else "https://t.me/RixieHQ")]
    ])
    await message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)

@app.on_message(filters.command("terms"))
async def terms_command(client, message: Message):
    text = (
        "📜 **Terms of Service & Usage Guidelines:**\n\n"
        "1. This bot is strictly designed for personal backup, archiving, and educational purposes.\n"
        "2. Do not use this service to download, clone, or redistribute copyrighted content without permission.\n"
        "3. Users are solely responsible for compliance with Telegram's Terms of Service and local laws.\n"
        "4. Spamming, flooding, or abusing server resources will lead to an immediate ban.\n"
        "5. Subscriptions are non-refundable once activated.\n\n"
        "By using this bot, you agree to these guidelines."
    )
    await message.reply_text(text)

@app.on_message(filters.command("stats"))
async def stats_command(client, message: Message):
    try:
        total_users = await users_collection.count_documents({})
        premium_users = await premium_users_collection.count_documents({})
        cpu_usage = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        ram_used = f"{ram.used / (1024 ** 3):.2f} GB / {ram.total / (1024 ** 3):.2f} GB ({ram.percent}%)"

        text = (
            "📈 **Bot System & User Statistics:**\n\n"
            f"👥 **Total Registered Users:** `{total_users}`\n"
            f"💎 **Active Premium Users:** `{premium_users}`\n"
            f"🖥️ **CPU Usage:** `{cpu_usage}%`\n"
            f"💾 **RAM Usage:** `{ram_used}`\n"
            f"⚙️ **Status:** `Online & Operational` 🟢"
        )
    except Exception as e:
        text = f"📈 **Bot Statistics:**\n\nError calculating system stats: {e}"
    await message.reply_text(text)

async def subscribe(app, message):
    if not FORCE_SUB:
        return 0
    try:
        user = await app.get_chat_member(FORCE_SUB, message.from_user.id)
        if str(user.status) in ("ChatMemberStatus.BANNED", "BANNED"):
            await message.reply_text("You are Banned. Contact -- @RixieHQ")
            return 1
        return 0
    except UserNotParticipant:
        try:
            link = await app.export_chat_invite_link(FORCE_SUB)
        except Exception as le:
            logger.warning(f"[FORCE_SUB] Could not export chat invite link for {FORCE_SUB}: {le}")
            link = JL if JL else "https://t.me/forcesub123"
        caption = "Join our channel to use the bot"
        try:
            await message.reply_photo(
                photo="https://graph.org/file/d44f024a08ded19452152.jpg",
                caption=caption,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Now...", url=f"{link}")]])
            )
        except Exception:
            await message.reply_text(
                caption,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Now...", url=f"{link}")]])
            )
        return 1
    except (PeerIdInvalid, ChannelInvalid, ChatAdminRequired, ChannelPrivate) as e:
        logger.warning(
            f"[FORCE_SUB CONFIG] Bot cannot access force-sub channel '{FORCE_SUB}': {e}. "
            f"Please make sure your bot is an ADMINISTRATOR in that channel! "
            f"Bypassing force-sub check so users are not blocked."
        )
        return 0
    except Exception as ggn:
        logger.error(f"[FORCE_SUB ERROR] Exception during force-sub check: {ggn}", exc_info=True)
        err_msg = str(ggn).lower()
        if any(k in err_msg for k in ["peer id", "channel", "admin", "chat_id", "participant"]):
            logger.warning(f"[FORCE_SUB] Bypassing force-sub check due to channel/peer access issue: {ggn}")
            return 0
        await message.reply_text(f"Something Went Wrong. Contact admins... with following message {ggn}")
        return 1 
     
@app.on_message(filters.command("set"))
async def set(_, message):
    if message.from_user.id not in OWNER_ID:
        await message.reply("You are not authorized to use this command.")
        return
     
    await app.set_bot_commands([
        BotCommand("start", "🚀 Start the bot"),
        BotCommand("clone", "🚀 Smart Topic & Group Cloner"),
        BotCommand("topic", "📑 Clone forum topics / groups"),
        BotCommand("batch", "🫠 Extract in bulk"),
        BotCommand("login", "🔑 Get into the bot"),
        BotCommand("setbot", "🧸 Add your bot for handling files"),
        BotCommand("logout", "🚪 Get out of the bot"),
        BotCommand("adl", "👻 Download audio from 30+ sites"),
        BotCommand("dl", "💀 Download videos from 30+ sites"),
        BotCommand("status", "⟳ Refresh Payment status"),
        BotCommand("transfer", "💘 Gift premium to others"),
        BotCommand("add", "➕ Add user to premium"),
        BotCommand("rem", "➖ Remove from premium"),
        BotCommand("rembot", "🤨 Remove your custom bot"),
        BotCommand("settings", "⚙️ Personalize things"),
        BotCommand("plan", "🗓️ Check our premium plans"),
        BotCommand("terms", "🥺 Terms and conditions"),
        BotCommand("help", "❓ If you're a noob, still!"),
        BotCommand("cancel", "🚫 Cancel login/batch/settings process"),
        BotCommand("stop", "🚫 Cancel batch process")
    ])
 
    await message.reply("✅ Commands configured successfully!")
 
 
 
 
help_pages = [
    (
        "📝 **Bot Commands Overview (1/2)**:\n\n"
        "1. **/add userID**\n"
        "> Add user to premium (Owner only)\n\n"
        "2. **/rem userID**\n"
        "> Remove user from premium (Owner only)\n\n"
        "3. **/transfer userID**\n"
        "> Transfer premium to your beloved major purpose for resellers (Premium members only)\n\n"
        "4. **/get**\n"
        "> Get all user IDs (Owner only)\n\n"
        "5. **/lock**\n"
        "> Lock channel from extraction (Owner only)\n\n"
        "6. **/dl link**\n"
        "> Download videos (Not available in v3 if you are using)\n\n"
        "7. **/adl link**\n"
        "> Download audio (Not available in v3 if you are using)\n\n"
        "8. **/login**\n"
        "> Log into the bot for private channel access\n\n"
        "9. **/clone** or **/topic**\n"
        "> 🚀 Smart Group & Topic Cloner (Auto-detects all topics & non-contiguous IDs)\n\n"
        "10. **/batch**\n"
        "> Bulk extraction for posts (After login)\n\n"
    ),
    (
        "📝 **Bot Commands Overview (2/2)**:\n\n"
        "10. **/logout**\n"
        "> Logout from the bot\n\n"
        "11. **/stats**\n"
        "> Get bot stats\n\n"
        "12. **/plan**\n"
        "> Check premium plans\n\n"
        "13. **/speedtest**\n"
        "> Test the server speed (not available in v3)\n\n"
        "14. **/terms**\n"
        "> Terms and conditions\n\n"
        "15. **/cancel**\n"
        "> Cancel ongoing batch process\n\n"
        "16. **/myplan**\n"
        "> Get details about your plans\n\n"
        "17. **/session**\n"
        "> Generate Pyrogram V2 session\n\n"
        "18. **/settings**\n"
        "> 1. SETCHATID : To directly upload in channel or group or user's dm use it with -100[chatID]\n"
        "> 2. SETRENAME : To add custom rename tag or username of your channels\n"
        "> 3. CAPTION : To add custom caption\n"
        "> 4. REPLACEWORDS : Can be used for words in deleted set via REMOVE WORDS\n"
        "> 5. RESET : To set the things back to default\n\n"
        "> You can set CUSTOM THUMBNAIL, PDF WATERMARK, VIDEO WATERMARK, SESSION-based login, etc. from settings\n\n"
        "**__Powered by Rixiex_Robot__**"
    )
]
 
 
async def send_or_edit_help_page(_, message, page_number):
    if page_number < 0 or page_number >= len(help_pages):
        return
 
     
    prev_button = InlineKeyboardButton("◀️ Previous", callback_data=f"help_prev_{page_number}")
    next_button = InlineKeyboardButton("Next ▶️", callback_data=f"help_next_{page_number}")
 
     
    buttons = []
    if page_number > 0:
        buttons.append(prev_button)
    if page_number < len(help_pages) - 1:
        buttons.append(next_button)
 
     
    keyboard = InlineKeyboardMarkup([buttons])
 
     
    await message.delete()
 
     
    await message.reply(
        help_pages[page_number],
        reply_markup=keyboard
    )
 
 
@app.on_message(filters.command("help"))
async def help(client, message):
    join = await subscribe(client, message)
    if join == 1:
        return
     
    await send_or_edit_help_page(client, message, 0)
 
 
@app.on_callback_query(filters.regex(r"help_(prev|next)_(\d+)"))
async def on_help_navigation(client, callback_query):
    action, page_number = callback_query.data.split("_")[1], int(callback_query.data.split("_")[2])
 
    if action == "prev":
        page_number -= 1
    elif action == "next":
        page_number += 1

    await send_or_edit_help_page(client, callback_query.message, page_number)
     
@app.on_callback_query(filters.regex(r"^btn_"))
async def start_button_callbacks(client, cq: CallbackQuery):
    data = cq.data
    uid = cq.from_user.id
    name = cq.from_user.first_name if cq.from_user else "User"

    if data == "btn_home":
        await cq.message.edit_text(
            get_start_text(name),
            reply_markup=get_start_keyboard(),
            disable_web_page_preview=True
        )
    elif data == "btn_clone_help":
        text = (
            "🚀 **Smart Topic & Group Cloner:**\n\n"
            "• Send `/clone` or send any Telegram group / forum link.\n"
            "• The bot automatically reads all topics and message history.\n"
            "• **Options:**\n"
            "  1. Clone into a **Brand New Cloned Group** (Bot auto-adds itself as Admin & enables topics).\n"
            "  2. Clone into your **Pre-Configured Chat/Topic** (`/settings`).\n\n"
            "💡 *No custom bot (`/setbot`) is required for cloning!*"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_home")]
        ])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    elif data == "btn_batch_help":
        text = (
            "📥 **Batch & Single Downloader:**\n\n"
            "• Send `/batch` to extract messages in bulk.\n"
            "• Or send `/single` or just paste any post link directly.\n"
            "• **Where do files go?**\n"
            "  1. If you configured `/settings` (Chat ID): Uploads directly into that channel or specific topic.\n"
            "  2. If Chat ID is NOT set: Uploads into your PM (via your custom bot if `/setbot` is added, or via Main Bot).\n\n"
            "💡 *Use `/stop` anytime to pause or cancel.*"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_home")]
        ])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    elif data == "btn_login_info":
        text = (
            "🔑 **User Session Login (/login):**\n\n"
            "• Required to download from **private restricted channels** and to clone groups.\n"
            "• Send `/login` and provide your phone number with country code.\n"
            "• Enter the Telegram OTP and 2FA password (if enabled).\n"
            "• Your session is encrypted securely with AES-256.\n"
            "• Use `/logout` anytime to terminate and delete your session."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_home")]
        ])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    elif data == "btn_settings_info":
        text = (
            "⚙️ **Personalized Settings (/settings):**\n\n"
            "Configure how files and media are uploaded:\n\n"
            "• **Set Chat ID**: Pass channel ID (e.g. `-1001234567890`) or a specific topic ID (e.g. `-1001234567890/42`).\n"
            "• **Set Rename Tag**: Add custom username or suffix to all file names.\n"
            "• **Set Caption**: Append custom text or channel footer.\n"
            "• **Thumbnail**: Upload custom thumbnail image.\n"
            "• **Replace / Delete Words**: Filter unwanted links or ads.\n\n"
            "👉 Send `/settings` in chat to open the interactive settings panel!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_home")]
        ])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    elif data == "btn_myplan":
        prem_info = await get_premium_details(uid)
        ud = await get_user_data(uid)
        has_session = bool(ud and ud.get('session_string'))
        has_bot = bool(ud and ud.get('bot_token'))
        chat_cfg = ud.get('chat_id', 'Not Set (PM)') if ud else 'Not Set (PM)'

        if prem_info:
            exp_utc = prem_info['subscription_end']
            exp_ist = exp_utc + timedelta(hours=5, minutes=30)
            formatted_exp = exp_ist.strftime('%d-%b-%Y %I:%M:%S %p')
            status_line = f"✅ **Active Premium** (`{formatted_exp}` IST)"
            limit_line = f"Unlimited ({PREMIUM_LIMIT} msgs)"
        else:
            status_line = "🆓 **Free Tier**"
            limit_line = f"{FREEMIUM_LIMIT} msgs / day"

        text = (
            f"📊 **Your Account Details:**\n\n"
            f"👤 **User ID:** `{uid}`\n"
            f"💎 **Plan:** {status_line}\n"
            f"📈 **Daily Limit:** `{limit_line}`\n"
            f"🔑 **Session:** {'✅ Active' if has_session else '❌ Inactive (/login)'}\n"
            f"🧸 **Custom Bot:** {'✅ Added' if has_bot else 'ℹ️ Optional (/setbot)'}\n"
            f"🎯 **Upload Destination:** `{chat_cfg}`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 View Premium Plans", callback_data="btn_plans")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_home")]
        ])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    elif data == "btn_plans":
        text = (
            "💎 **Upgrade to Premium:**\n\n"
            "• Unlimited downloads & clone operations\n"
            "• No restrictions or wait timers\n"
            "• Clone entire groups with all topics preserved\n"
            "• Direct priority uploads\n\n"
            f"👉 Contact **[Owner / Support]({AC})** to get premium access!"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Buy Premium", url=AC if AC else "https://t.me/RixieHQ")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_home")]
        ])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

    await cq.answer()


 
