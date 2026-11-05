from pyrogram import Client, filters
from pyrogram.errors import (
    UserAlreadyParticipant,
    UserNotParticipant,
    FloodWait,
    InviteHashExpired,
    InviteHashInvalid,
    ChatAdminRequired,
    PeerIdInvalid,
    UsernameInvalid
)
from config import OWNER_ID
from utils.client_manager import active_clients
from utils.font import small_caps
import asyncio

# --- SMART LINK CLEANER ---
def clean_target(link: str) -> str:
    """Extracts valid username or keeps private invite link format."""
    link = link.strip().rstrip("/")
    
    # Keep private invite links exactly as they are
    if "+" in link or "joinchat/" in link:
        return link
        
    # For public links, strip out the URL parts to extract just the username
    link = link.replace("https://", "").replace("http://", "").replace("www.", "")
    if link.startswith("t.me/"):
        link = link.replace("t.me/", "")
    if link.startswith("@"):
        link = link[1:]
        
    return link


@Client.on_message(filters.command("join") & filters.user(OWNER_ID))
async def join_channel_cmd(client, message):
    if len(message.command) < 2:
        usage = small_caps("Usage: /join <channel_link>")
        return await message.reply(f"⚠️ {usage}")
    
    raw_link = message.command[1]
    cleaned_link = clean_target(raw_link)
    
    if not active_clients:
        no_acc = small_caps("No active accounts found")
        return await message.reply(f"⚠️ {no_acc}")

    msg = await message.reply(small_caps("Processing join request... please wait."))
    
    success = 0
    already_joined = 0
    requested = 0
    failed = 0
    
    for phone, user_client in active_clients.items():
        try:
            # Join using the smartly cleaned link
            await user_client.join_chat(cleaned_link)
            success += 1
        except UserAlreadyParticipant:
            already_joined += 1
        except Exception as e:
            err_str = str(e).upper()
            # Catching Join Request Sent specific exception from Telegram API response
            if "INVITE_REQUEST_SENT" in err_str:
                requested += 1
            else:
                failed += 1
                print(f"[-] Join failed for {phone}: {e}")
        
        await asyncio.sleep(1.5) # API লিমিট এড়াতে ডিলে

    # Formatting Detailed Output
    result_text = (
        f"✅ **{small_caps('Join Operation Finished')}**\n\n"
        f"🔗 **Target:** `{cleaned_link}`\n"
        f"🟢 **{small_caps('Success')}**: {success}\n"
        f"🟡 **{small_caps('Already Joined')}**: {already_joined}\n"
        f"⏳ **{small_caps('Request Sent')}**: {requested}\n"
        f"🔴 **{small_caps('Failed')}**: {failed}"
    )
    await msg.edit(result_text)


@Client.on_message(filters.command("leave") & filters.user(OWNER_ID))
async def leave_channel_cmd(client, message):
    if len(message.command) < 2:
        usage = small_caps("Usage: /leave <channel_link_or_id>")
        return await message.reply(f"⚠️ {usage}")
    
    raw_link = message.command[1]
    cleaned_link = clean_target(raw_link)
    
    if not active_clients:
        no_acc = small_caps("No active accounts found")
        return await message.reply(f"⚠️ {no_acc}")

    msg = await message.reply(small_caps("Processing leave request... please wait."))
    
    success = 0
    not_joined = 0
    failed = 0

    for phone, user_client in active_clients.items():
        try:
            target_chat = cleaned_link
            
            # If the user provides a numeric Chat ID
            if cleaned_link.lstrip('-').isdigit():
                target_chat = int(cleaned_link)
            else:
                # 💡 SMART RESOLVER: Resolves cleaned invite link/username into a Chat ID
                try:
                    chat = await user_client.get_chat(cleaned_link)
                    target_chat = chat.id
                except Exception:
                    # Fallback to the string itself if resolving fails
                    pass

            await user_client.leave_chat(target_chat)
            success += 1
        except UserNotParticipant:
            not_joined += 1
        except Exception as e:
            failed += 1
            print(f"[-] Leave failed for {phone}: {e}")
            
        await asyncio.sleep(1.5) # API লিমিট এড়াতে ডিলে

    # Formatting Detailed Output
    result_text = (
        f"✅ **{small_caps('Leave Operation Finished')}**\n\n"
        f"🔗 **Target:** `{cleaned_link}`\n"
        f"🟢 **{small_caps('Success')}**: {success}\n"
        f"🟡 **{small_caps('Not a Member')}**: {not_joined}\n"
        f"🔴 **{small_caps('Failed')}**: {failed}"
    )
    await msg.edit(result_text)
