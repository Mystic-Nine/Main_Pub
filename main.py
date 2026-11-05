import asyncio
from pyrogram import Client
from pyromod import listen # Required for conversation handlers
from config import API_ID, API_HASH, BOT_TOKEN
from utils.client_manager import start_all_clients

# Rare Bots Hub - Main Bot Initialization
class RareBotManager(Client):
    def __init__(self):
        super().__init__(
            name="RareBotsManager",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins=dict(root="rarebots") # Loads everything from rarebots folder
        )

    async def start(self):
        await super().start()
        print("[+] Rare Bots Hub Manager Started!")
        
        # Start all saved user accounts in the background
        print("[+] Initializing saved accounts...")
        await start_all_clients(self)

    async def stop(self, *args):
        await super().stop()
        print("[-] Bot Stopped.")

if __name__ == "__main__":
    app = RareBotManager()
    app.run()
