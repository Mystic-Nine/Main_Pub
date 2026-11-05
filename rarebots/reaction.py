from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ReactionInvalid, ChatWriteForbidden, UserNotParticipant
from config import OWNER_ID
from utils.client_manager import active_clients
from utils.font import small_caps
import asyncio
import random

# Temp storage for reaction selection
# Format: {user_id: {"reactions": [], "link": str}}
temp_data = {}

# Screenshot থেকে সংগৃহীত টেলিগ্রামের সমস্ত রিঅ্যাকশন (Total 71)
SUPPORTED_EMOJIS = [
    "❤️", "👍", "👎", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "🤬", 
    "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊️", "🤡", "🥱", 
    "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", 
    "🏆", "💔", "🤨", "🍓", "🍾", "💋", "🖕", "😈", "😴", "😭", 
    "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨", "🤝", "✍️", 
    "🤗", "🫡", "🎅", "🎄", "☃️", "💅", "🤪", "🗿", "🆒", "💘", 
    "🙉", "🦄", "🤫", "💊", "🙊", "😎", "👾", "🤷‍♂️", "🤷", "🤷‍♀️", "😡"
]

@Client.on_message(filters.command("react") & filters.user(OWNER_ID))
async def react_command(client, message):
    if len(message.command) < 2:
        return await message.reply(f"⚠️ {small_caps('Usage: /react <post_link>')}")
    
    # Clean the link (remove query parameters like ?single)
    link = message.command[1].split("?")[0]
    user_id = message.from_user.id
    
    temp_data[user_id] = {"reactions": [], "link": link}
    
    keyboard = []
    row = []
    
    # Callback data issue এড়াতে আমরা ইমোজির বদলে Index (r_0, r_1) ব্যবহার করছি
    for i, emoji in enumerate(SUPPORTED_EMOJIS):
        row.append(InlineKeyboardButton(f"{emoji}", callback_data=f"r_{i}"))
        if len(row) == 5: # প্রতি সারিতে ৫টি ইমোজি
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(f"✅ {small_caps('Confirm Reaction')}", callback_data="conf_react")])
    
    text = (
        f"📊 **{small_caps('Select reactions for post')} (Max 10):**\n\n"
        f"🔗 **Link:** `{link}`\n"
        f"✅ **{small_caps('Selected')}:** None"
    )
    
    await message.reply(text, reply_markup=InlineKeyboardMarkup(keyboard))


@Client.on_callback_query(filters.regex(r"^r_"))
async def select_reaction(client, callback_query):
    user_id = callback_query.from_user.id
    
    if user_id not in temp_data:
        return await callback_query.answer("Session expired, use /react again.", show_alert=True)
        
    idx = int(callback_query.data.split("_")[1])
    emoji = SUPPORTED_EMOJIS[idx]
    
    # Toggle Logic (Add/Remove)
    if emoji in temp_data[user_id]["reactions"]:
        temp_data[user_id]["reactions"].remove(emoji)
        await callback_query.answer(f"Removed {emoji}")
    else:
        if len(temp_data[user_id]["reactions"]) >= 10:
            return await callback_query.answer("⚠️ You can select a maximum of 10 emojis!", show_alert=True)
        temp_data[user_id]["reactions"].append(emoji)
        await callback_query.answer(f"Added {emoji}")
    
    # Update the message text to show selected emojis dynamically
    selected_list = temp_data[user_id]["reactions"]
    selected_text = " ".join(selected_list) if selected_list else "None"
    link = temp_data[user_id]["link"]
    
    text = (
        f"📊 **{small_caps('Select reactions for post')} (Max 10):**\n\n"
        f"🔗 **Link:** `{link}`\n"
        f"✅ **{small_caps('Selected')} ({len(selected_list)}/10):** {selected_text}"
    )
    
    # Edit text only, keep the exact same markup
    try:
        await callback_query.message.edit_text(text, reply_markup=callback_query.message.reply_markup)
    except Exception:
        pass # Ignore message not modified errors


@Client.on_callback_query(filters.regex(r"^conf_react"))
async def confirm_reaction(client, callback_query):
    user_id = callback_query.from_user.id
    data = temp_data.get(user_id)
    
    if not data or not data["reactions"]:
        return await callback_query.answer("⚠️ Select at least one reaction before confirming!", show_alert=True)
    
    link = data["link"]
    reactions = data["reactions"]
    
    await callback_query.message.edit_text(f"🚀 {small_caps('Executing random reactions... please wait.')}")
    
    # Link Parsing
    try:
        if "t.me/c/" in link:
            # Private channel: t.me/c/12345/67
            parts = link.split("/")
            chat_id = int("-100" + parts[parts.index("c") + 1])
            msg_id = int(parts[-1])
        else:
            # Public channel: t.me/username/67
            parts = link.split("/")
            chat_id = parts[-2]
            msg_id = int(parts[-1])
    except Exception:
        return await callback_query.message.edit_text(f"❌ {small_caps('Invalid link format')}")

    success = 0
    failed = 0
    
    for phone, user_client in active_clients.items():
        try:
            # AI Logic: Pick ONE random emoji from the user's selected list for this specific account
            chosen_emoji = random.choice(reactions)
            
            try:
                await user_client.send_reaction(chat_id=chat_id, message_id=msg_id, emoji=chosen_emoji)
                success += 1
            except ReactionInvalid:
                # If this specific emoji is banned in the channel, it counts as failed for this account
                failed += 1
            except Exception:
                failed += 1
                
            await asyncio.sleep(1.2) # API Limit এড়াতে অ্যাকাউন্টের মাঝে ডিলে
        except Exception:
            failed += 1
            
    # Final Result Text
    selected_text = " ".join(reactions)
    await callback_query.message.edit_text(
        f"✅ **{small_caps('Reaction Operation Finished')}**\n\n"
        f"🎭 **{small_caps('Pool')}**: {selected_text}\n"
        f"🟢 **{small_caps('Success')}**: {success}\n"
        f"🔴 **{small_caps('Failed')}**: {failed}\n\n"
        f"ℹ️ _{small_caps('Note: Check if accounts are members of the channel/group.')}_"
    )
    
    if user_id in temp_data:
        del temp_data[user_id]
