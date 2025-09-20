"""
Quick Start Version - Optimized untuk startup cepat
"""
import configparser
from pyrogram import Client
import asyncio

async def main():
    print("🚀 Starting bot (quick mode)...")

    # Load config
    config = configparser.ConfigParser()
    config.read("config.ini")

    api_id = config["Telegram"].get("api_id")
    api_hash = config["Telegram"].get("api_hash")
    bot_token = config["Telegram"].get("bot_token")

    if not all([api_id, api_hash, bot_token]):
        print("❌ Config tidak lengkap!")
        return

    print("✅ Bot ready!")

    # Initialize client
    app = Client("telegram_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

    # Simple start handler
    @app.on_message()
    async def handle_message(client, message):
        if message.text == "/start":
            await message.reply("Bot berjalan! Gunakan /help untuk command lengkap.")
        elif message.text == "/help":
            await message.reply("Bot aktif. Restart dengan bot.py untuk fitur lengkap.")

    print("🔄 Starting Telegram client...")
    await app.start()
    print("✅ Bot connected!")

    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())