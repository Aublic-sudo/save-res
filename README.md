<h1 align="center">
  Save Restricted Content Bot v3
</h1>

The Save Restricted Content Bot is a stable Telegram bot developed by devgagan and TEAM SPY. It enables users to retrieve restricted messages from Telegram channels and groups, offering features such as custom thumbnail support and the ability to upload files up to 4GB. Additionally, the bot supports downloading videos from platforms like YouTube, Instagram, and Facebook, along with over 100 other sites

[Telegram](https://t.me/save_restricted_content_bots) | [See Recent Updates](https://github.com/devgaganin/Save-Restricted-Content-Bot-V2/tree/v3#updates)

### Star the repo it motivate us to update new features
Please do start and max fork thanks 

## 📚 About This Branch
- This branch is based on `Pyrogram V2` offering enhanced stability and a forced login feature. User are not forced to login in bot for public channels but for public groups and private channel they have to do login.
- for detailed features scroll down to features section

---

## 🔧 Features
- Extract content from both public and private channels/groups.
- Custom bot functionality added use `/setbot`
- 128 bit encryption for data saving use @v3saverbot on telegram to generate `MASTER_KEY`, `IV_KEY`
- Rename and forward content to other channels or users.
- extract restricted content from other bots how to use format link like `https://botusername(without @)/message_id(get it from plus messenger)`
- `/login` method along with `session` based login
- Custom captions and thumbnails.
- Auto-remove default video thumbnails.
- Delete or replace words in filenames and captions.
- Auto-pin messages if enabled.
- download yt/insta/Twitter/fb ect normal ytdlp supported sites that supports best format
- Login via phone number.
- **Supports 4GB file uploads**: The bot can handle large file uploads, up to 4GB in size.
- file splitter if not premium string
- **Enhanced Timer**: Distinct timers for free and paid users to limit usage and improve service.
- **Improved Looping**: Optimized looping for processing multiple files or links, reducing delays and enhancing performance.
- **Premium Access**: Premium users enjoy faster processing speeds and priority queue management.
- ~~ads setup shorlink ads token system~~
- ~~fast uploader via `SpyLib` using Telethon modules and `mautrix bridge repo`~~ 
- Directly upload to `topic` in any topic enabled group
- real time download and uplaod progress, support chats, text , audio, video , video note sticker everything

  
## ⚡ Commands

- **`start`**: 🚀 Start the bot.
- **`batch`**: 🫠 Extract in bulk.
- **`login`**: 🔑 Get into the bot.
- **`single`**: Process single link.
- **`setbot`**: add your custome bot.
- **`logout`**: 🚪 Get out of the bot.
- **`adl`**: 👻 Download audio from 30+ sites.
- **`dl`**: 💀 Download videos from 30+ sites.
- **`transfer`**: 💘 Gift premium to others.
- **`status`**: ⌛ Get your plan details.
- **`add`**: ➕ Add user to premium.
- **`rem`**: ➖ Remove user from premium.
- **`rembot`**: remove your custome bot.
- **`session`**: 🧵 Generate Pyrogramv2 session.
- **`settings`**: ⚙️ Personalize settings.
- **`stats`**: 📊 Get stats of the bot.
- **`plan`**: 🗓️ Check our premium plans.
- **`terms`**: 🥺 Terms and conditions.
- **`help`**: ❓ Help if you're new.
- **`cancel`**: 🚫 Cancel batch process.


## ⚙️ Required Variables

<details>
<summary><b>Click to view required variables</b></summary>

To run the bot, you'll need to configure a few sensitive variables. Here's how to set them up securely:

- **`API_ID`**: Your API ID from [telegram.org](https://my.telegram.org/auth).
- **`API_HASH`**: Your API Hash from [telegram.org](https://my.telegram.org/auth).
- **`BOT_TOKEN`**: Get your bot token from [@BotFather](https://t.me/botfather).
- **`OWNER_ID`**: Use [@missrose_bot](https://t.me/missrose_bot) to get your user ID by sending `/info`.
- **`CHANNEL_ID`**: The ID of the channel for forced subscription.
- **`LOG_GROUP`**: A group or channel where the bot logs messages. Forward a message to [@userinfobot](https://t.me/userinfobot) to get your channel/group ID.
- **`MONGO_DB`**: A MongoDB URL for storing session data (recommended for security).
  
### Additional Configuration Options:
- **`STRING`**: (Optional) Add your **premium account session string** here to allow 4GB file uploads. This is **optional** and can be left empty if not used.
- **`FREEMIUM_LIMIT`**: Default is `0`. Set this to any value you want to allow free users to extract content. If set to `0`, free users will not have access to any extraction features.
- **`PREMIUM_LIMIT`**: Default is `500`. This is the batch limit for premium users. You can customize this to allow premium users to process more links/files in one batch.
- **`YT_COOKIES`**: Yt cookies for downloading yt videos 
- **`INSTA_COOKIES`**: If you want to enable instagram downloading fill cookiesn

**How to get cookies ??** : use mozila firfox if on android or use chrome on desktop and download extension get this cookie or any Netscape Cookies (HTTP Cookies) extractor and use that 

### Monetization (Optional):
- **`WEBSITE_URL`**: (Optional) This is the domain for your monetization short link service. Provide the shortener's domain name, for example: `upshrink.com`. Do **not** include `www` or `https://`. The default link shortener is already set.
- **`AD_API`**: (Optional) The API key from your link shortener service (e.g., **Upshrink**, **AdFly**, etc.) to monetize links. Enter the API provided by your shortener.

> **Important:** Always keep your credentials secure! Never hard-code them in the repository. Use environment variables or a `.env` file.

</details>

---

## 🚀 Deployment Guide

<details>
<summary><b>Deploy on VPS</b></summary>

1. Fork the repo.
2. Update `config.py` with your values.
3. Run the following:
   ```bash
   sudo apt update
   sudo apt install ffmpeg git python3-pip
   git clone your_repo_link
   cd your_repo_name
   pip3 install -r requirements.txt
   python3 main.py
   ```

- To run the bot in the background:
  ```bash
  screen -S gagan
  python3 main.py
  ```
  - Detach: `Ctrl + A`, then `Ctrl + D`
  - To stop: `screen -r gagan` and `screen -S gagan -X quit`

</details>

<details>
<summary><b>Deploy on Heroku</b></summary>

1. Fork and Star the repo.
2. Click [![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://www.heroku.com/deploy).
3. Enter required variables and click deploy ✅.

</details>

<details>
<summary><b>Deploy on Render</b></summary>

1. Fork and star the repo.
2. Edit `config.py` or set environment variables on Render.
3. Go to [render.com](https://render.com), sign up/log in.
4. Create a new web service, select the free plan.
5. Connect your GitHub repo and deploy ✅.

</details>

<details>
<summary><b>Deploy on Koyeb</b></summary>

1. Fork and star the repo.
2. Edit `config.py` or set environment variables on Koyeb.
3. Create a new service, select `Dockerfile` as build type.
4. Connect your GitHub repo and deploy ✅.

</details>

---
### ⚠️ Must Do: Secure Your Sensitive Variables

**Do not expose sensitive variables (e.g., `API_ID`, `API_HASH`, `BOT_TOKEN`) on GitHub. Use environment variables to keep them secure.**

### Configuring Variables Securely:

- **On VPS or Local Machine:**
  - Use a text editor to edit `config.py`:
    ```bash
    nano config.py
    ```
  - Alternatively, export as environment variables:
    ```bash
    export API_ID=your_api_id
    export API_HASH=your_api_hash
    export BOT_TOKEN=your_bot_token
    ```

- **For Cloud Platforms (Heroku, Railway, etc.):**
  - Set environment variables directly in your platform’s dashboard.

- **Using `.env` File:**
  - Create a `.env` file and add your credentials:
    ```
    API_ID=your_api_id
    API_HASH=your_api_hash
    BOT_TOKEN=your_bot_token
    ```
  - Make sure to add `.env` to `.gitignore` to prevent it from being pushed to GitHub.

**Why This is Important?**
Your credentials can be stolen if pushed to a public repository. Always keep them secure by using environment variables or local configuration files.

---

## 🛠️ Terms of Use

Visit the [Terms of Use](https://github.com/devgaganin/Save-Restricted-Content-Bot-Repo/blob/master/TERMS_OF_USE.md) page to review and accept the guidelines.
## Important Note

**Note**: Changing the terms and commands doesn't magically make you a developer. Real development involves understanding the code, writing new functionalities, and debugging issues, not just renaming things. If only it were that easy!


<h3 align="center">
  Developed with ❤️ by <a href="https://t.me/team_spy_pro"> Gagan </a>
</h3>

