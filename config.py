import os

# Rare Bots Hub - Configuration
API_ID = int(os.environ.get("API_ID", "3074377"))
API_HASH = os.environ.get("API_HASH", "aae29b40946b83e42a78b6a7a4677631")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "")) 
MONGO_URI = os.environ.get("MONGO_URI", "")

START_PIC = os.environ.get("START_PIC", "https://graph.org/file/8271a9c4496166819299c-8a04e1af50359e05ce.jpg")
