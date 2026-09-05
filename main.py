
import utils.crypto_patch
import asyncio
from shared_client import start_client, app, client, userbot
from pyrogram import idle
import importlib
import os
import sys

async def periodic_storage_cleaner():
    """Background watchdog that runs every 60s to ensure Render VPS storage never gets full."""
    from utils.func import cleanup_stray_temp_files
    while True:
        try:
            await asyncio.sleep(60)
            cleanup_stray_temp_files()
        except Exception:
            pass

async def load_and_run_plugins():
    await start_client()
    plugin_dir = "plugins"
    plugins = [f[:-3] for f in os.listdir(plugin_dir) if f.endswith(".py") and f != "__init__.py"]

    for plugin in plugins:
        module = importlib.import_module(f"plugins.{plugin}")
        if hasattr(module, f"run_{plugin}_plugin"):
            print(f"Running {plugin} plugin...")
            await getattr(module, f"run_{plugin}_plugin")()  

async def main():
    asyncio.create_task(periodic_storage_cleaner())
    await load_and_run_plugins()
    print("Bot is up and running!")
    await idle()
    print("Shutting down clients gracefully...")
    try:
        await app.stop()
    except Exception:
        pass
    try:
        await client.disconnect()
    except Exception:
        pass
    if userbot:
        try:
            if getattr(userbot, 'is_connected', False):
                await userbot.stop()
        except Exception:
            pass

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    print("Starting clients ...")
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
