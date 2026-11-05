import asyncio
import time
import html
import logging
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ParseMode
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, OWNER_ID
from utils.client_manager import active_clients
from utils.font import small_caps

# --- Suppress Pyrogram Dispatcher Peer ID Logs ---
# এটি সার্ভারের "Peer id invalid" লগ স্প্যাম পুরোপুরি বন্ধ করে দেবে।
logging.getLogger("pyrogram.dispatcher").setLevel(logging.CRITICAL)

# --- Database Setup for AFK ---
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["RareBotsHub_DB"]
afk_col = db["afk_states"]


# --- Dynamic Text Formatter (Replaces Variables) ---
def format_dynamic_text(text, message):
    """Replaces placeholders with actual user details."""
    if not message.from_user:
        return text
    
    user = message.from_user
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    username = f"@{user.username}" if user.username else first_name
    user_id = str(user.id)
    
    # HTML mention format
    mention_name = first_name if first_name else "User"
    mention = f'<a href="tg://user?id={user_id}">{mention_name}</a>'
    
    # Replace variables in the text
    formatted = text.replace("{firstname}", first_name)
    formatted = formatted.replace("{lastname}", last_name)
    formatted = formatted.replace("{username}", username)
    formatted = formatted.replace("{id}", user_id)
    formatted = formatted.replace("{mention}", mention)
    
    return formatted


# --- Tracker: When the Account Owner Replies ---
async def outgoing_tracker(client, message):
    """Tracks when the owner manually sends a message to mute AFK for 5 minutes."""
    try:
        phone = client.name.replace("user_", "")
        user_id = str(message.chat.id)
        current_time = int(time.time())
        
        # Directly update the specific user's timestamp in the owner_replied dictionary
        await afk_col.update_one(
            {"phone": phone},
            {"$set": {f"owner_replied.{user_id}": current_time}}
        )
    except Exception:
        pass


# --- AFK Responder (Private Chats Only) ---
async def afk_responder_private(client, message):
    try:
        phone = client.name.replace("user_", "")
        afk_data = await afk_col.find_one({"phone": phone})
        
        if not afk_data or not afk_data.get("is_afk"):
            return
            
        user_id = str(message.chat.id)
        current_time = int(time.time())
        
        # 1. Check Owner Activity: Did the OWNER reply to this person in the last 5 minutes (300s)?
        owner_replied = afk_data.get("owner_replied", {})
        if user_id in owner_replied:
            if current_time - owner_replied[user_id] < 300:
                return  # Owner is actively chatting, skip AFK
                
        # 2. Check AFK Spam Cooldown: Did the BOT reply in the last 5 minutes?
        afk_replied = afk_data.get("afk_replied", {})
        if user_id in afk_replied:
            if current_time - afk_replied[user_id] < 300:
                return  # AFK already sent recently, skip to prevent spam
                
        # Format the text with dynamic variables
        final_text = format_dynamic_text(afk_data["afk_text"], message)

        # Send the AFK Message exactly as saved (Supporting HTML)
        await message.reply_text(
            final_text,
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML
        )
        
        # Update the timestamp for when the AFK last replied
        await afk_col.update_one(
            {"phone": phone},
            {"$set": {f"afk_replied.{user_id}": current_time}}
        )
    except Exception as e:
        print(f"[-] Private AFK failed for {client.name}: {e}")


# --- Dynamic Handler Injector ---
injected_clients = set()

async def inject_afk_handler():
    while True:
        try:
            for phone, user_client in list(active_clients.items()):
                if phone not in injected_clients:
                    # Injecting independent handlers using different groups
                    # Group 1: Listens to incoming private messages (excluding me and bots)
                    user_client.add_handler(MessageHandler(afk_responder_private, filters.private & ~filters.me & ~filters.bot), group=1)
                    # Group 2: Listens to my own outgoing messages to pause AFK
                    user_client.add_handler(MessageHandler(outgoing_tracker, filters.private & filters.me), group=2)
                    
                    injected_clients.add(phone)
        except Exception:
            pass
        await asyncio.sleep(5)

# Start background injection task
try:
    loop = asyncio.get_event_loop()
    loop.create_task(inject_afk_handler())
except RuntimeError:
    pass


# --- Main Bot Commands ---

@Client.on_message(filters.command("afk") & filters.user(OWNER_ID))
async def set_afk_cmd(client, message):
    if len(message.command) < 2:
        usage = small_caps("Usage: Reply to a message with /afk <phone_number>")
        return await message.reply(f"⚠️ **{usage}**")
    
    if not message.reply_to_message:
        reply_err = small_caps("You must reply to the message you want to set as AFK")
        return await message.reply(f"⚠️ **{reply_err}!**")

    phone = message.command[1]
    
    if phone not in active_clients:
        not_found = small_caps("This account is not active in the bot")
        return await message.reply(f"❌ **{not_found}.**")

    replied_msg = message.reply_to_message
    
    # Extract text from the replied message
    base_text = ""
    if replied_msg.text:
        base_text = replied_msg.text.html if hasattr(replied_msg.text, "html") else replied_msg.text
    elif replied_msg.caption:
        base_text = replied_msg.caption.html if hasattr(replied_msg.caption, "html") else replied_msg.caption
    
    if not base_text:
        return await message.reply(f"⚠️ {small_caps('The replied message must contain text')}.")

    # Fix HTML tags: Unescape manual tags typed by user (e.g., <blockquote>, <a>, <b>)
    # So both Telegram's native formatting AND manually typed HTML tags work perfectly.
    base_text = html.unescape(base_text)

    # Save to Database with reset dictionaries
    await afk_col.update_one(
        {"phone": phone},
        {"$set": {
            "is_afk": True,
            "afk_text": base_text,
            "afk_replied": {},    # Tracks bot's replies
            "owner_replied": {}   # Tracks owner's active typing
        }},
        upsert=True
    )

    success_msg = small_caps("AFK mode activated successfully")
    await message.reply(
        f"✅ **{success_msg}!**\n\n"
        f"📱 **Account:** `{phone}`\n"
        f"📩 **AFK Message Saved:**\n\n`{base_text}`"
    )


@Client.on_message(filters.command(["unafk", "afkoff"]) & filters.user(OWNER_ID))
async def remove_afk_cmd(client, message):
    if len(message.command) < 2:
        usage = small_caps("Usage: /unafk <phone_number>")
        return await message.reply(f"⚠️ **{usage}**")

    phone = message.command[1]

    # Check and Update Database
    result = await afk_col.update_one(
        {"phone": phone},
        {"$set": {
            "is_afk": False, 
            "afk_replied": {}, 
            "owner_replied": {}
        }}
    )

    if result.modified_count > 0 or result.matched_count > 0:
        success_msg = small_caps("AFK mode deactivated successfully")
        await message.reply(f"✅ **{success_msg}** for `{phone}`.")
    else:
        not_found = small_caps("AFK mode is not active for this account")
        await message.reply(f"⚠️ **{not_found}**.")
