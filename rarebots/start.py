from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import OWNER_ID, START_PIC
from utils.font import small_caps

@Client.on_message(filters.command("start") & filters.user(OWNER_ID))
async def start_cmd(client, message):
    # Generating customized title text with custom font style
    welcome_title = small_caps("Welcome to Rare Bots Hub")
    account_mgr = small_caps("Account Manager")
    
    caption_text = (
        f"✨ **{welcome_title} - {account_mgr}** ✨\n\n"
        "I can securely manage your personal Telegram accounts. "
        "Even if you lose your phone, your accounts will remain safe here, "
        "and I will forward all your Telegram Login Codes instantly!\n\n"
        "**🤖 Available Commands:**\n"
        "🔹 `/login` - Add a new account\n"
        "🔹 `/accounts` - View all active accounts\n"
        "🔹 `/logout` - Remove an account"
    )
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(small_caps("➕ Add Account"), callback_data="login_panel")
        ],
        [
            InlineKeyboardButton(small_caps("⚙️ Manage Accounts"), callback_data="manage_panel")
        ]
    ])
    
    # Sending as a Photo with Caption using the link from config.py
    if START_PIC:
        try:
            await message.reply_photo(
                photo=START_PIC,
                caption=caption_text,
                reply_markup=buttons
            )
        except Exception:
            # Fallback to Text Message if the Photo link is invalid or fails
            await message.reply_text(caption_text, reply_markup=buttons)
    else:
        await message.reply_text(caption_text, reply_markup=buttons)
