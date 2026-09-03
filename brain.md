# 🧠 Save Restricted Content Bot - Repository Master Brain (Architecture & Guide)

> **File:** `brain.md`  
> **Purpose:** Comprehensive architecture manual, system breakdown, and developer reference for the entire repository. This document serves as the single source of truth for the codebase, including client models, pipelines, database schemas, and state management.

---

## 1. 🏗️ High-Level System Architecture

The project is an advanced Telegram Content Saver & Supergroup/Forum Cloner designed to extract restricted messages/media from public and private channels/groups, download media from 30+ external sites (YouTube, Instagram, etc.), and clone entire forum supergroups (including non-contiguous message IDs and topics) into new or existing groups.

```
+-----------------------------------------------------------------------------------+
|                                TELEGRAM CLIENTS                                   |
|                                                                                   |
|  +-----------------------------+       +---------------------------------------+  |
|  |   Pyrogram Main Bot (app/X) |       |     Telethon Bot Client (client/gf)   |  |
|  | - Core commands (/start,    |       | - Telethon handlers (/settings,       |  |
|  |   /clone, /batch, /login)   |       |   /status, /transfer, /rem, ytdl)     |  |
|  | - Uploads, media transfers  |       | - Fast direct downloads via Spylib    |  |
|  +--------------+--------------+       +-------------------+-------------------+  |
|                 |                                          |                      |
|  +--------------v--------------+       +-------------------v-------------------+  |
|  |  User Session Client (uc)   |       |      Dynamic Custom Bots (UB)         |  |
|  | - Logged-in user account    |       | - User-added bots via /setbot         |  |
|  | - Accesses private channels |       | - Used for private batch uploads      |  |
|  | - Creates supergroups/topics|       |   directly to user                    |  |
|  +-----------------------------+       +---------------------------------------+  |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                               DATABASE & STORAGE                                  |
|                                                                                   |
|  +--------------------------- MongoDB (telegram_downloader) -------------------+  |
|  |  * users: Settings, tokens, rename tags, captions, chat_id, delete/replace   |  |
|  |  * premium_users: Expiry dates, subscription levels, transfer history       |  |
|  |  * statistics: Overall usage, tasks executed                                |  |
|  |  * redeem_code: Prepaid voucher codes for premium access                    |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 2. 📂 Directory & File Structure Breakdown

```
save-res-main/
│
├── config.py                 # Environment variables, cookies, limits, mongo URIs
├── shared_client.py          # Centralized client initialization (Pyrogram & Telethon)
├── main.py                   # Main bot process launcher, plugin dynamic loader
├── app.py                    # Flask web server for health checks / keep-alive ping
├── run.py                    # Dual-process supervisor (runs app.py + main.py simultaneously)
├── requirements.txt          # Python dependencies
├── Procfile / heroku.yml     # Heroku & cloud platform deployment manifests
├── Dockerfile                # Container definition
├── brain.md                  # Master repository documentation (THIS FILE)
│
├── plugins/                  # Bot feature modules
│   ├── start.py              # /start UI keyboard, /help navigation, /set commands, /myplan, /stats
│   ├── clone.py              # Smart Group & Topic Cloner, auto forum discovery, group cloner
│   ├── batch.py              # Bulk message extraction, single downloads, 2GB+ handling, upload engine
│   ├── login.py              # Phone OTP + 2FA interactive login, Pyrogram V2 session generator, /setbot
│   ├── settings.py           # User preferences menu (Telethon UI: chat_id, caption, watermark, rename)
│   ├── premium.py            # Owner premium management (/add, /get), original start hook
│   ├── stats.py              # Subscription status check (/status), premium transfer (/transfer), /rem
│   ├── ytdl.py               # YouTube & social media video/audio downloader via yt-dlp
│   └── pay.py                # Payment gateway placeholder
│
├── utils/                    # Shared helpers and business logic
│   ├── func.py               # Core utilities: DB CRUD, group creation, topic creation, link parsing
│   ├── custom_filters.py     # Pyrogram message filters (login state tracking, step filters)
│   └── encrypt.py            # AES-256 / Fernet session string encryption and decryption
│
└── templates/
    └── welcome.html          # HTML template for Flask web server landing page
```

---

## 3. 👥 Multi-Client Model & Responsibilities

The codebase operates with **four distinct client roles**:

| Client Symbol | Library | Identity | Purpose |
|---|---|---|---|
| **`app` / `X`** | Pyrogram | Main Bot (`BOT_TOKEN`) | Core command handling (`/start`, `/batch`, `/clone`), progress bars, public downloads, upload fallback, forum group management. |
| **`client` / `gf`** | Telethon | Main Bot (`BOT_TOKEN`) | Telethon inline buttons for `/settings`, Spylib fast upload/download hooks, `/status`, `/transfer`. |
| **`userbot` / `Y`** | Pyrogram | Optional Shared Userbot (`STRING`) | Fallback global session if user has not logged in with their own session. |
| **`uc` (`Client`)** | Pyrogram | User's Personal Session (`session_string`) | Created dynamically when a user logs in via `/login`. Reads private channels, creates cloned supergroups, creates forum topics. |
| **`ubot` (`UB[uid]`)** | Pyrogram | User's Custom Bot (`bot_token`) | Created dynamically if user ran `/setbot`. Dedicated file delivery bot for that user's private batch/single downloads. |

---

## 4. 🗄️ Database Architecture (MongoDB)

Database Name: `telegram_downloader` (configurable via `DB_NAME`)

### Collection: `users`
Stores user-specific settings, credentials, and text manipulation rules.
- `user_id` (`int` / `str`): Telegram User ID.
- `session_string` (`str`): Encrypted Pyrogram V2 session string.
- `bot_token` (`str`): Custom bot token if set via `/setbot`.
- `chat_id` (`str`): Target destination chat ID (e.g. `-100123456789` or `-100123456789/42` with topic ID).
- `caption` (`str`): Custom footer or template caption appended to uploads.
- `rename_tag` (`str`): Custom tag/suffix appended to filenames (e.g., `@MyChannel`).
- `replacement_words` (`dict`): Mapping of `{"old_word": "new_word"}` for caption/filename cleanup.
- `delete_words` (`list`): List of words to strip out of captions and filenames.

### Collection: `premium_users`
Stores active subscription records.
- `user_id` (`int`): Telegram User ID.
- `subscription_start` (`datetime`): Subscription activation UTC timestamp.
- `subscription_end` (`datetime`): Expiration UTC timestamp.
- `expireAt` (`datetime`): TTL index for automated expiry.

### Collection: `statistics`
Stores cumulative usage metrics (total downloads, active users).

### Collection: `redeem_code`
Stores voucher codes for self-service premium activation.

---

## 5. 🔄 Core Workflows & Pipelines

### A. Smart Topic & Group Cloning (`/clone` / `/topic`)
1. **Prerequisite**: User must configure their custom bot using `/setbot <token>`. Main Bot `X` acts purely as command interface and is **never revealed**.
2. **Link Intake**: User sends forum supergroup link (e.g., `https://t.me/c/123456789/42` or `https://t.me/groupname`).
3. **Resolution**: `resolve_tg_chat` resolves the chat peer using user client (`uc`).
4. **Topic Discovery**: `get_all_forum_topics` scans MTProto for all topics in the forum.
5. **Interactive Choice**:
   - Clone All Topics
   - Select Specific Topic(s)
   - Ignore Specific Topic(s)
6. **Destination Decision**:
   - **Auto-Create Cloned Group**: `create_cloned_supergroup` creates a fresh supergroup under `uc`'s account, enables forum mode, copies avatar/title, and **auto-adds and promotes ONLY the Custom Bot (`ubot`) as Admin**. Main Bot `X` is never added or exposed.
   - **Target Configured Chat**: Uses `chat_id` stored in user settings.
7. **Execution Loop**:
   - Fetches message IDs in topic via `get_topic_messages_list`.
   - Creates corresponding destination topic via `create_forum_topic_safe`.
   - Downloads media using `uc` -> Renames -> Adds thumbnail -> Uploads strictly using Custom Bot `ubot` -> Cleans up temp disk storage.

> [!IMPORTANT]
> **Zero Main Bot Exposure**: All uploaded files into user chats, channels, and groups are delivered strictly through the user's custom bot (`ubot`).

---

### B. Bulk & Single Message Extraction (`/batch` / `/single` / pasted link)
1. **Mandatory Custom Bot**: User must provide a bot token via `/setbot <token>` first.
2. **Target Identification**:
   - Reads `chat_id` from user settings.
   - If `chat_id` is set (e.g. `-100CHANNELID` or `-100CHANNELID/TOPIC_ID`):
     - Uploads directly into that channel or specific topic using Custom Bot `ubot`.
   - If `chat_id` is **NOT set**:
     - Uploads directly into the **Custom Bot's chat with the user** (`ubot.send_video(uid, ...)`).
3. **Speed & Throughput Optimization (Fixing 8-9s `upload.GetFile` FloodWait)**:
   - `max_concurrent_transmissions` is tuned to `4` (down from 24). This prevents Telegram from flagging the session with 8-9 second rate limit delays on every chunk.
   - Batch interval pause reduced from 10 seconds to 1 second.
   - Upload and download throughput reaches continuous wire speed (3MB/s - 6MB/s).
4. **Large File Handling (> 2GB)**:
   - Pyrogram bots have a 2GB upload limit.
   - Files > 2GB use the Userbot (`Y`) to upload to `LOG_GROUP`, then copy to user destination strictly using Custom Bot `ubot`.
5. **Local Storage Cleanup**:
   - Every downloaded file and generated thumbnail is strictly wiped in the `finally:` block of `process_msg` and through `cleanup_stray_temp_files()` to prevent VPS disk fill-up.

---

## 6. 🏷️ Topic ID Routing Specification (`-100.../TOPIC_ID`)

When uploading to Telegram Forum Supergroups:
- Telegram Forum Topics are anchored at the message ID of the topic's initial creation message (`message_thread_id` / `top_msg_id`).
- When user sets:
  ```
  -1002345678901/42
  ```
  The system extracts:
  - Destination Channel ID: `-1002345678901`
  - Topic Thread ID: `42`
- All Pyrogram upload methods (`send_video`, `send_document`, `send_photo`, `send_audio`, `send_message`, `send_voice`, `send_sticker`) pass `reply_to_message_id=42`.
- **Fault-Tolerant Topic Fallback**: If the topic has been closed, deleted, or thread ID is invalid (`REPLY_MESSAGE_ID_INVALID`), the upload retries without `reply_to_message_id` into the general chat instead of crashing and discarding downloaded files.

---

## 7. 🤖 Bot Commands Matrix

| Command | Handler File | Access | Status | Description |
|---|---|---|---|---|
| `/start` | `plugins/start.py` | Everyone | ✅ Active | Interactive main menu, navigation keyboards |
| `/clone`, `/topic` | `plugins/clone.py` | Premium / Free | ✅ Active | Smart group and forum topic cloner |
| `/batch`, `/single`| `plugins/batch.py` | Premium / Free | ✅ Active | Bulk & single restricted post downloader |
| `/login` | `plugins/login.py` | Everyone | ✅ Active | Interactive phone OTP + 2FA session login |
| `/logout` | `plugins/login.py` | Everyone | ✅ Active | Deletes active session from database |
| `/setbot` | `plugins/login.py` | Everyone | ✅ Active | Configures custom bot for private batch uploads |
| `/rembot` | `plugins/login.py` | Everyone | ✅ Active | Removes custom bot token |
| `/settings` | `plugins/settings.py`| Everyone | ✅ Active | Configures destination chat, caption, tags |
| `/status`, `/myplan`| `plugins/stats.py`, `start.py`| Everyone | ✅ Active | Checks subscription expiry (IST) & limits |
| `/plan` | `plugins/start.py` | Everyone | ✅ Active | Displays pricing plans and features |
| `/terms` | `plugins/start.py` | Everyone | ✅ Active | Terms of service and usage guidelines |
| `/stats` | `plugins/start.py` | Everyone | ✅ Active | Bot health, system RAM, user statistics |
| `/add` | `plugins/premium.py`| Owner Only | ✅ Active | Adds user to premium database |
| `/rem` | `plugins/stats.py` | Owner Only | ✅ Active | Removes user from premium database |
| `/get` | `plugins/premium.py`| Owner Only | ✅ Active | Exports full list of premium users |
| `/transfer` | `plugins/stats.py` | Premium User | ✅ Active | Transfers remaining subscription to another user |
| `/stop`, `/cancel` | `plugins/clone.py`, `batch.py` | Active User | ✅ Active | Gracefully cancels current running task |
| `/forcestop` | `plugins/batch.py` | Active User | ✅ Active | Force kills background tasks and cleans disk |
| `/adl`, `/dl` | `plugins/ytdl.py` | Premium / Free | ✅ Active | YouTube & social media video/audio downloader |

---

## 8. 🛡️ Known Pitfalls & Solutions

1. **Telegram Rate Limits (FloodWait)**:
   - Handled with `except FloodWait as e: await asyncio.sleep(e.value + 1)` across all cloning and batch loops.
2. **PeerIdInvalid on New Chats**:
   - `resolve_tg_chat` implements a 4-tier resolution ladder (Direct get_chat -> MTProto ResolvePeer -> ProxyChat 0s fallback -> Dialog scan).
3. **Bot Missing in Auto-Created Groups**:
   - Solved in `create_cloned_supergroup` by ensuring `uc` adds and promotes Main Bot `X` via username and MTProto `EditAdmin` with all administrative privileges (`can_manage_topics`, `can_post_messages`, etc.).
4. **Temporary Disk Fill**:
   - Managed by `finally:` deletion blocks in `process_msg` and global `cleanup_stray_temp_files()`.
