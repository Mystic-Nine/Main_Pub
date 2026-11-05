from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI

# Rare Bots Hub - Database Setup
client = AsyncIOMotorClient(MONGO_URI)
db = client["RareBotsHub_DB"]
accounts_col = db["accounts"]

async def save_account(phone_number, session_string, proxy=None):
    await accounts_col.update_one(
        {"phone": phone_number},
        {"$set": {"session": session_string, "proxy": proxy}},
        upsert=True
    )

async def get_all_accounts():
    accounts = []
    async for acc in accounts_col.find({}):
        accounts.append(acc)
    return accounts

async def delete_account(phone_number):
    await accounts_col.delete_one({"phone": phone_number})
