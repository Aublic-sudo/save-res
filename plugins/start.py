# Copyright (c) 2025 devgagan : https://github.com/devgaganin.
# Licensed under the GNU General Public License v3.0.
# See LICENSE file in the repository root for full license text.

from shared_client import app
from pyrogram import filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from config import LOG_GROUP, OWNER_ID, FORCE_SUB


# ─────────────────────────────────────────────────────────────────────────────
#  Force-subscribe check
# ─────────────────────────────────────────────────────────────────────────────

async def subscribe(app, message):
    if not FORCE_SUB:
        return 0
    try:
        user = await app.get_chat_member(FORCE_SUB, message.from_user.id)
        if str(user.status) == "ChatMemberStatus.BANNED":
            await message.reply_text("You are Banned. Contact -- @RixieHQ")
            return 1
    except UserNotParticipant:
        link    = await app.export_chat_invite_link(FORCE_SUB)
        caption = "Join our channel to use the bot"
        await message.reply_photo(
            photo="https://graph.org/file/d44f024a08ded19452152.jpg",
            caption=caption,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Join Now...", url=link)]
            ])
        )
        return 1
    except Exception as e:
        await message.reply_text(
            f"Something went wrong. Contact admins with this message:\n`{e}`"
        )
        return 1
    return 0


# ─────────────────────────────────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def start_cmd(_, message):
    join = await subscribe(_, message)
    if join == 1:
        return

    await message.reply_text(
        "👋 **Hey there!**\n\n"
        "I can save restricted content from Telegram channels & bots.\n\n"
        "📌 **Quick start:**\n"
        "> • /login — connect your account\n"
        "> • /setbot — add your upload bot\n"
        "> • /batch — bulk extract posts\n"
        "> • /botchat — extract by message IDs\n\n"
        "> Use /help for full command list.\n\n"
        "**__Powered by Rixie__**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Help 📖", callback_data="help_page_0")]
        ])
    )


# ─────────────────────────────────────────────────────────────────────────────
#  /set  — configure bot commands (owner only)
# ─────────────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("set"))
async def set_commands(_, message):
    if message.from_user.id not in OWNER_ID:
        await message.reply("You are not authorized to use this command.")
        return

    await app.set_bot_commands([
        BotCommand("start",    "🚀 Start the bot"),
        BotCommand("batch",    "🫠 Extract in bulk"),
        BotCommand("botchat",  "🤖 Extract from bot chat using IDs"),
        BotCommand("login",    "🔑 Get into the bot"),
        BotCommand("setbot",   "🧸 Add your bot for handling files"),
        BotCommand("logout",   "🚪 Get out of the bot"),
        BotCommand("adl",      "👻 Download audio from 30+ sites"),
        BotCommand("dl",       "💀 Download videos from 30+ sites"),
        BotCommand("status",   "⟳ Refresh payment status"),
        BotCommand("transfer", "💘 Gift premium to others"),
        BotCommand("add",      "➕ Add user to premium"),
        BotCommand("rem",      "➖ Remove from premium"),
        BotCommand("rembot",   "🤨 Remove your custom bot"),
        BotCommand("settings", "⚙️ Personalise things"),
        BotCommand("plan",     "🗓️ Check our premium plans"),
        BotCommand("terms",    "🥺 Terms and conditions"),
        BotCommand("help",     "❓ If you're a noob, still!"),
        BotCommand("cancel",   "🚫 Cancel login/batch/settings process"),
        BotCommand("stop",     "🚫 Cancel batch process"),
    ])
    await message.reply("✅ Commands configured successfully!")


# ─────────────────────────────────────────────────────────────────────────────
#  Help pages
# ─────────────────────────────────────────────────────────────────────────────

help_pages = [
    (
        "📝 **Bot Commands Overview (1/2)**:\n\n"
        "1. **/add userID**\n"
        "> Add user to premium (Owner only)\n\n"
        "2. **/rem userID**\n"
        "> Remove user from premium (Owner only)\n\n"
        "3. **/transfer userID**\n"
        "> Transfer premium to your beloved — major use for resellers (Premium only)\n\n"
        "4. **/get**\n"
        "> Get all user IDs (Owner only)\n\n"
        "5. **/lock**\n"
        "> Lock channel from extraction (Owner only)\n\n"
        "6. **/dl link**\n"
        "> Download videos (Not available in v3)\n\n"
        "7. **/adl link**\n"
        "> Download audio (Not available in v3)\n\n"
        "8. **/login**\n"
        "> Log into the bot for private channel access\n\n"
        "9. **/batch**\n"
        "> Bulk extraction for posts (after login)\n\n"
        "10. **/botchat**\n"
        "> Extract videos from bot chat using message IDs (no link needed)\n\n"
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
        "> Get details about your plan\n\n"
        "17. **/session**\n"
        "> Generate Pyrogram V2 session\n\n"
        "18. **/settings**\n"
        "> 1. SETCHATID — upload directly to channel/group/DM (-100chatID)\n"
        "> 2. SETRENAME — custom rename tag or channel username\n"
        "> 3. CAPTION — custom caption\n"
        "> 4. REPLACEWORDS — replace words removed via REMOVE WORDS\n"
        "> 5. RESET — restore everything to default\n\n"
        "> Also supports: custom thumbnail, PDF watermark, video watermark, session login\n\n"
        "**__Powered by Rixie__**"
    ),
]


def _build_help_keyboard(page: int) -> InlineKeyboardMarkup:
    """Build prev/next navigation keyboard for the given page."""
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"help_page_{page - 1}"))
    if page < len(help_pages) - 1:
        buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"help_page_{page + 1}"))
    return InlineKeyboardMarkup([buttons]) if buttons else None


# ─────────────────────────────────────────────────────────────────────────────
#  /help  command
# ─────────────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("help"))
async def help_cmd(client, message):
    join = await subscribe(client, message)
    if join == 1:
        return
    await message.reply(
        help_pages[0],
        reply_markup=_build_help_keyboard(0)
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Help pagination callback
# ─────────────────────────────────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^help_page_(\d+)$"))
async def help_navigate(client, callback_query):
    page = int(callback_query.data.split("_")[-1])
    if page < 0 or page >= len(help_pages):
        await callback_query.answer("No more pages.", show_alert=False)
        return

    await callback_query.message.edit_text(
        help_pages[page],
        reply_markup=_build_help_keyboard(page)
    )
    await callback_query.answer()
