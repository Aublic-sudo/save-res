import subprocess
import sys
import os
import signal

os.environ.setdefault("PORT", "5000")

flask_proc = subprocess.Popen([sys.executable, "app.py"])

has_bot_config = os.environ.get("API_ID") and os.environ.get("API_HASH") and os.environ.get("BOT_TOKEN")

bot_proc = None
if has_bot_config:
    bot_proc = subprocess.Popen([sys.executable, "main.py"])
    print("Bot process started.")
else:
    print("Telegram bot credentials not configured. Skipping bot startup.")
    print("Set API_ID, API_HASH, and BOT_TOKEN environment variables to enable the bot.")

def shutdown(signum, frame):
    flask_proc.terminate()
    if bot_proc:
        bot_proc.terminate()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

try:
    if bot_proc:
        bot_proc.wait()
    else:
        flask_proc.wait()
except KeyboardInterrupt:
    pass
finally:
    flask_proc.terminate()
    if bot_proc:
        bot_proc.terminate()
