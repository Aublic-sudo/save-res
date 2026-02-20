# Save Restricted Content Bot v3

## Overview
A Telegram bot built with Pyrogram and Telethon that retrieves restricted messages from Telegram channels and groups. Includes a Flask web server for health checks/status display.

## Project Architecture
- **app.py** - Flask web server serving a welcome/status page on port 5000
- **main.py** - Telegram bot entry point, loads plugins from `plugins/` directory
- **run.py** - Combined runner that starts both Flask and the bot process
- **config.py** - Configuration loaded from environment variables
- **shared_client.py** - Shared Telegram client instances (Telethon + Pyrogram)
- **plugins/** - Bot command handlers (batch, login, pay, premium, settings, start, stats, ytdl)
- **utils/** - Utility functions (encryption, filters, helpers)
- **templates/** - Flask HTML templates

## Required Environment Variables
- `API_ID` - Telegram API ID
- `API_HASH` - Telegram API Hash
- `BOT_TOKEN` - Telegram Bot Token
- `MONGO_DB` - MongoDB connection string
- `OWNER_ID` - Bot owner Telegram ID(s), space-separated
- `DB_NAME` - Database name (default: telegram_downloader)
- `STRING` - Pyrogram session string (optional, for userbot/premium features)
- `LOG_GROUP` - Telegram group ID for logging
- `FORCE_SUB` - Force subscribe channel ID
- `MASTER_KEY` - Encryption master key
- `IV_KEY` - Encryption IV key

## Tech Stack
- Python 3.11
- Flask (web server)
- Pyrogram (custom build) + Telethon (Telegram clients)
- MongoDB (via motor/pymongo)
- yt-dlp (video downloads)

## Running
The `run.py` script starts both the Flask web server (port 5000) and the Telegram bot. If bot credentials are not configured, only the Flask server runs.
