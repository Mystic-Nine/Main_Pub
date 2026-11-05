import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UsernameOccupied, UsernameInvalid, MessageNotModified
from config import OWNER_ID
from utils.database import get_all_accounts, delete_account
from utils.client_manager import active_clients, stop_user_client, verify_and_clean_account
from utils.font import small_caps

# Track active listener states to handle "Cancel" button perfectly
listener_states = {}

# ==========================================
# 1. MAIN DASHBOARD HANDLERS
# ==========================================

@Client.on_message(filters.command("accounts") & filters.user(OWNER_ID))
async def accounts_cmd(client, message):
    text, markup = await build_dashboard_ui()
    await message.reply(text, reply_markup=markup)

@Client.on_callback_query(filters.regex("^manage_panel$") & filters.user(OWNER_ID))
async def manage_cb(client, callback_query):
    await callback_query.answer(f"🔄 {small_caps('Refreshing dashboard')}...", show_alert=False)
    text, markup = await build_dashboard_ui()
    try:
        await callback_query.message.edit_text(text, reply_markup=markup)
    except MessageNotModified:
        pass

async def build_dashboard_ui():
    """Builds the main dashboard text and buttons with small_caps."""
    accounts = await get_all_accounts()
    panel_title = small_caps("Live Monitoring Dashboard")
    
    if not accounts:
        no_acc = small_caps("No accounts saved yet")
        text = f"📊 **{panel_title}**\n━━━━━━━━━━━━━━━━━━━━\n\n⚠️ **{no_acc}**.\n👉 {small_caps('Use')} `/login` {small_caps('to add a new account')}."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔄 {small_caps('Refresh')}", callback_data="manage_panel")]])
        return text, kb

    text = f"📊 **{panel_title}**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    buttons = []
    
    valid_count = 0
    for acc in accounts:
        phone = acc['phone']
        is_valid = await verify_and_clean_account(phone)
        
        if not is_valid:
            continue
            
        valid_count += 1
        proxy_status = f"🛡️ {small_caps('Proxy')}" if acc.get('proxy') else f"⚡ {small_caps('Direct')}"
        text += f"**{valid_count}.** `{phone}` ({proxy_status})\n"
        
        manage_btn = small_caps(f"Manage {phone}")
        buttons.append([InlineKeyboardButton(f"⚙️ {manage_btn}", callback_data=f"manage_acc_{phone}")])
    
    if valid_count == 0:
        text += f"⚠️ **{small_caps('All sessions were terminated or invalid')}**.\n👉 {small_caps('Please add a new account using')} `/login`."
    else:
        text += f"\n👇 *{small_caps('Select an account below to manage it')}:*"

    buttons.append([InlineKeyboardButton(f"🔄 {small_caps('Refresh Dashboard')}", callback_data="manage_panel")])
    return text, InlineKeyboardMarkup(buttons)


# ==========================================
# 2. ACCOUNT SUB-MENU HANDLERS
# ==========================================

@Client.on_callback_query(filters.regex(r"^manage_acc_(.+)$") & filters.user(OWNER_ID))
async def manage_acc_cb(client, callback_query):
    phone = callback_query.matches[0].group(1)
    
    # Cancel any active listeners for this chat
    chat_id = callback_query.message.chat.id
    if chat_id in listener_states:
        del listener_states[chat_id]
        
    if phone not in active_clients:
        err_msg = small_caps("Account is not active or offline")
        return await callback_query.answer(f"⚠️ {err_msg}!", show_alert=True)
    
    user_client = active_clients[phone]
    try:
        me = await user_client.get_me()
        name = f"{me.first_name} {me.last_name or ''}".strip()
        uname = f"@{me.username}" if me.username else "None"
        bio = getattr(me, 'bio', 'None') or 'None'
    except Exception:
        name, uname, bio = "Unknown", "Unknown", "Unknown"

    text = (
        f"⚙️ **{small_caps('Account Management')}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 **{small_caps('Phone')}:** `{phone}`\n"
        f"👤 **{small_caps('Name')}:** `{name}`\n"
        f"🌐 **{small_caps('Username')}:** `{uname}`\n"
        f"📝 **{small_caps('Bio')}:** `{bio[:40]}`{'...' if len(bio)>40 else ''}\n\n"
        f"👇 *{small_caps('Select an action to update profile')}:*"
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"✏️ {small_caps('Set Name')}", callback_data=f"set_name_{phone}"),
            InlineKeyboardButton(f"📝 {small_caps('Set Bio')}", callback_data=f"set_bio_{phone}")
        ],
        [
            InlineKeyboardButton(f"🌐 {small_caps('Set Username')}", callback_data=f"set_uname_{phone}"),
            InlineKeyboardButton(f"📸 {small_caps('Set PFP')}", callback_data=f"set_pfp_{phone}")
        ],
        [
            InlineKeyboardButton(f"❌ {small_caps('Logout')}", callback_data=f"logout_acc_{phone}"),
            InlineKeyboardButton(f"🔙 {small_caps('Back to Dashboard')}", callback_data="manage_panel")
        ]
    ]
    
    try:
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        pass


# ==========================================
# 3. INTERACTIVE SETTINGS (NAME, BIO, UNAME, PFP)
# ==========================================

@Client.on_callback_query(filters.regex(r"^set_(name|bio|uname|pfp)_(.+)$") & filters.user(OWNER_ID))
async def prompt_action_cb(client, callback_query):
    action = callback_query.matches[0].group(1)
    phone = callback_query.matches[0].group(2)
    chat_id = callback_query.message.chat.id
    
    if phone not in active_clients:
        err_msg = small_caps("Account not active")
        return await callback_query.answer(f"⚠️ {err_msg}!", show_alert=True)
        
    titles = {
        "name": f"✏️ {small_caps('Update Name')}",
        "bio": f"📝 {small_caps('Update Bio')}",
        "uname": f"🌐 {small_caps('Update Username')}",
        "pfp": f"📸 {small_caps('Update Profile Pic')}"
    }
    
    prompts = {
        "name": f"👉 {small_caps('Send the new First Name & Last Name in the chat.')}\n_(Example: `John | Doe` or just `John`)_",
        "bio": f"👉 {small_caps('Send the new Bio Text in the chat.')}",
        "uname": f"👉 {small_caps('Send the new Username in the chat.')}\n_({small_caps('Or type `none` to remove existing username')})_",
        "pfp": f"👉 {small_caps('Send the new Profile Photo in the chat.')}"
    }
    
    text = (
        f"**{titles[action]}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 **{small_caps('Account')}:** `{phone}`\n\n"
        f"{prompts[action]}\n\n"
        f"⏳ _{small_caps('Waiting for your input... (60s)')}_"
    )
    
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"❌ {small_caps('Cancel')}", callback_data=f"manage_acc_{phone}")]])
    await callback_query.message.edit_text(text, reply_markup=kb)
    
    # Register active state
    state_key = f"{action}_{phone}"
    listener_states[chat_id] = state_key
    
    try:
        # Fixed Listen Method using Explicit kwargs to avoid multiple values error
        response = await client.listen(
            chat_id=chat_id, 
            filters=(filters.text | filters.photo) & filters.user(OWNER_ID), 
            timeout=60
        )
        
        # Check if canceled during wait
        if listener_states.get(chat_id) != state_key:
            return 
            
        # Delete User Input Message to keep the chat absolutely clean
        try:
            await response.delete()
        except Exception:
            pass
            
        user_client = active_clients[phone]
        status_text = text + f"\n\n🔄 *{small_caps('Processing update on Telegram server...')}*"
        await callback_query.message.edit_text(status_text)
        
        # Apply the update
        if action == "name":
            val = response.text.strip() if response.text else ""
            if "|" in val:
                fn, ln = val.split("|", 1)
                await user_client.update_profile(first_name=fn.strip(), last_name=ln.strip())
            else:
                parts = val.split(None, 1)
                await user_client.update_profile(first_name=parts[0], last_name=parts[1] if len(parts) > 1 else "")
                
        elif action == "bio":
            val = response.text.strip() if response.text else ""
            await user_client.update_profile(bio=val)
            
        elif action == "uname":
            val = response.text.strip() if response.text else ""
            uname = None if val.lower() in ["none", "off", "clear", "-"] else val.lower().replace("@", "")
            await user_client.set_username(uname)
            
        elif action == "pfp":
            if not response.photo:
                raise ValueError(small_caps("Please send a valid image format"))
            
            file_path = await response.download()
            try:
                await user_client.set_profile_photo(photo=file_path)
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path) # Cleanup downloaded file
            
        # Success Message Edits
        success_text = (
            f"✅ **{small_caps('Successfully Updated')}!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 **{small_caps('Account')}:** `{phone}`\n"
            f"✨ {small_caps('The update has been applied to Telegram')}."
        )
        kb_success = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔙 {small_caps('Back to Account')}", callback_data=f"manage_acc_{phone}")]])
        await callback_query.message.edit_text(success_text, reply_markup=kb_success)
        
    except asyncio.TimeoutError:
        if listener_states.get(chat_id) == state_key:
            err_text = f"⏳ **{small_caps('Time out')}!**\n{small_caps('No input received within 60 seconds')}."
            kb_err = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔙 {small_caps('Back to Account')}", callback_data=f"manage_acc_{phone}")]])
            try:
                await callback_query.message.edit_text(err_text, reply_markup=kb_err)
            except MessageNotModified:
                pass
                
    except (UsernameOccupied, UsernameInvalid) as e:
        err_text = f"❌ **{small_caps('Username Error')}!**\n`{str(e)}`\n\n{small_caps('Try a different username')}."
        kb_err = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔙 {small_caps('Back to Account')}", callback_data=f"manage_acc_{phone}")]])
        await callback_query.message.edit_text(err_text, reply_markup=kb_err)
        
    except Exception as e:
        err_text = f"❌ **{small_caps('Error')}!**\n`{str(e)}`"
        kb_err = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔙 {small_caps('Back to Account')}", callback_data=f"manage_acc_{phone}")]])
        try:
            await callback_query.message.edit_text(err_text, reply_markup=kb_err)
        except MessageNotModified:
            pass
            
    finally:
        if listener_states.get(chat_id) == state_key:
            del listener_states[chat_id]


# ==========================================
# 4. LOGOUT HANDLER
# ==========================================

@Client.on_callback_query(filters.regex(r"^logout_acc_(.+)$") & filters.user(OWNER_ID))
async def logout_acc_cb(client, callback_query):
    phone = callback_query.matches[0].group(1)
    
    # Stop background client safely and delete credentials from DB
    await stop_user_client(phone)
    await delete_account(phone)
    
    alert_text = small_caps(f"Account logged out successfully")
    await callback_query.answer(f"✨ {alert_text}!", show_alert=True)
    
    # Refresh dashboard
    text, markup = await build_dashboard_ui()
    try:
        await callback_query.message.edit_text(text, reply_markup=markup)
    except MessageNotModified:
        pass
