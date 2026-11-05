import urllib.parse
from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from config import API_ID, API_HASH, OWNER_ID
from utils.database import save_account, delete_account
from utils.client_manager import start_user_client, stop_user_client
from utils.font import small_caps

@Client.on_message(filters.command("login") & filters.user(OWNER_ID))
async def login_cmd(client, message):
    await initiate_login(client, message.chat.id)

@Client.on_callback_query(filters.regex("login_panel") & filters.user(OWNER_ID))
async def login_cb(client, callback_query):
    await callback_query.message.delete()
    await initiate_login(client, callback_query.message.chat.id)

async def initiate_login(bot, chat_id):
    # Setup Advanced Keyboard Buttons
    CANCEL_BTN = f"❌ {small_caps('Cancel')}"
    NO_PROXY_BTN = f"🚫 {small_caps('No Proxy')}"
    
    cancel_kb = ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True, one_time_keyboard=True)
    proxy_kb = ReplyKeyboardMarkup([[NO_PROXY_BTN, CANCEL_BTN]], resize_keyboard=True, one_time_keyboard=True)
    remove_kb = ReplyKeyboardRemove()

    try:
        # Step 1: Get Phone Number
        panel_title = small_caps("Rare Bots Hub Login Panel")
        phone_ask = await bot.ask(
            chat_id, 
            f"📱 **{panel_title}**\n\n"
            f"Please enter your Telegram Phone Number (with Country Code, e.g., `+1234567890`):",
            reply_markup=cancel_kb
        )
        phone = phone_ask.text.strip()
        
        if phone == CANCEL_BTN:
            cancel_msg = small_caps("Login process cancelled")
            return await bot.send_message(chat_id, f"🚫 **{cancel_msg}**.", reply_markup=remove_kb)

        # Step 2: Proxy Configuration
        proxy_title = small_caps("Proxy Configuration")
        proxy_ask = await bot.ask(
            chat_id,
            f"🌐 **{proxy_title} (Optional)**\n\n"
            f"To prevent bans, you can connect this account using a Proxy.\n"
            f"**Format:** `socks5://user:pass@host:port` or `http://host:port`\n\n"
            f"Click `{NO_PROXY_BTN}` if you don't want to use a proxy.",
            reply_markup=proxy_kb
        )
        proxy_input = proxy_ask.text.strip()
        
        if proxy_input == CANCEL_BTN:
            cancel_msg = small_caps("Login process cancelled")
            return await bot.send_message(chat_id, f"🚫 **{cancel_msg}**.", reply_markup=remove_kb)

        proxy_dict = None
        if proxy_input != NO_PROXY_BTN:
            try:
                parsed = urllib.parse.urlparse(proxy_input)
                proxy_dict = {
                    "scheme": parsed.scheme,
                    "hostname": parsed.hostname,
                    "port": parsed.port
                }
                if parsed.username:
                    proxy_dict["username"] = parsed.username
                if parsed.password:
                    proxy_dict["password"] = parsed.password
            except Exception:
                await bot.send_message(chat_id, f"⚠️ {small_caps('Invalid proxy format. Proceeding without proxy.')}")
                proxy_dict = None

        # Connecting with or without Proxy
        temp_client = Client(name="temp", api_id=API_ID, api_hash=API_HASH, in_memory=True, proxy=proxy_dict)
        
        try:
            await temp_client.connect()
        except Exception as e:
            await bot.send_message(chat_id, f"❌ {small_caps('Proxy Connection Failed')}: `{e}`\n{small_caps('Try again with a working proxy')}.", reply_markup=remove_kb)
            return

        try:
            code_info = await temp_client.send_code(phone)
        except Exception as e:
            await bot.send_message(chat_id, f"❌ {small_caps('Error sending code')}: `{e}`", reply_markup=remove_kb)
            return await temp_client.disconnect()

        # Step 3: Get OTP
        code_ask = await bot.ask(
            chat_id, 
            f"📩 **{small_caps('An OTP has been sent to your account')}**.\n\n"
            f"**Note:** To prevent Telegram from blocking the code, enter it with spaces between characters (e.g., `1 2 3 4 5`).",
            reply_markup=cancel_kb
        )
        code = code_ask.text.strip()
        
        if code == CANCEL_BTN:
            await temp_client.disconnect()
            cancel_msg = small_caps("Login process cancelled")
            return await bot.send_message(chat_id, f"🚫 **{cancel_msg}**.", reply_markup=remove_kb)
            
        code = code.replace(" ", "")

        try:
            await temp_client.sign_in(phone, code_info.phone_code_hash, code)
        except SessionPasswordNeeded:
            # Step 4: Handle 2FA Password
            pwd_ask = await bot.ask(
                chat_id, 
                f"🔐 **{small_caps('Two-Step Verification is enabled')}**.\n"
                f"Please enter your Cloud Password:",
                reply_markup=cancel_kb
            )
            password = pwd_ask.text.strip()
            
            if password == CANCEL_BTN:
                await temp_client.disconnect()
                cancel_msg = small_caps("Login process cancelled")
                return await bot.send_message(chat_id, f"🚫 **{cancel_msg}**.", reply_markup=remove_kb)
                
            await temp_client.check_password(password)
        except PhoneCodeInvalid:
            await bot.send_message(chat_id, f"❌ {small_caps('Invalid code provided. Please try again')} /login", reply_markup=remove_kb)
            return await temp_client.disconnect()

        # Generate Session and Save
        session_string = await temp_client.export_session_string()
        await temp_client.disconnect()
        
        # Save to DB with proxy config
        await save_account(phone, session_string, proxy_dict)
        
        # Start the client in background to receive future codes
        await start_user_client(phone, session_string, bot, proxy_dict)
        
        success_title = small_caps("Account Added Successfully")
        proxy_status = "✅ Enabled" if proxy_dict else "⚠️ Disabled"
        
        await bot.send_message(
            chat_id, 
            f"✅ **{success_title}!**\n\n"
            f"📱 **Phone:** `{phone}`\n"
            f"🛡️ **Proxy:** {proxy_status}\n\n"
            f"From now on, all official Login Codes (777000) for this account will be intercepted and forwarded here.",
            reply_markup=remove_kb
        )

    except Exception as e:
        await bot.send_message(chat_id, f"⚠️ {small_caps('An unexpected error occurred')}: `{e}`", reply_markup=ReplyKeyboardRemove())

# ----------------- EXTRA FEATURE ADDED ----------------- #

@Client.on_message(filters.command("logout") & filters.user(OWNER_ID))
async def logout_command(client, message):
    logout_title = small_caps("Logout Panel")
    CANCEL_BTN = f"❌ {small_caps('Cancel')}"
    cancel_kb = ReplyKeyboardMarkup([[CANCEL_BTN]], resize_keyboard=True, one_time_keyboard=True)
    remove_kb = ReplyKeyboardRemove()
    
    try:
        phone_ask = await client.ask(
            message.chat.id,
            f"⚙️ **{logout_title}**\n\n"
            f"Please enter the Telegram Phone Number you want to logout (with Country Code, e.g., `+1234567890`):",
            reply_markup=cancel_kb
        )
        phone = phone_ask.text.strip()
        
        if phone == CANCEL_BTN:
            cancel_msg = small_caps("Logout cancelled")
            return await client.send_message(message.chat.id, f"🚫 **{cancel_msg}**.", reply_markup=remove_kb)

        # Stop background client safely
        await stop_user_client(phone)
        # Delete credentials from DB
        await delete_account(phone)
        
        success_msg = small_caps("Account logged out successfully")
        await client.send_message(
            message.chat.id, 
            f"✅ **{success_msg}!**\n📱 **Phone:** `{phone}`",
            reply_markup=remove_kb
        )
    except Exception as e:
        error_msg = small_caps("An unexpected error occurred")
        await client.send_message(message.chat.id, f"⚠️ **{error_msg}:** `{e}`", reply_markup=ReplyKeyboardRemove())
