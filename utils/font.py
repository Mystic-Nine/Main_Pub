def small_caps(text: str) -> str:
    """
    Converts normal English text into Small Caps (ᴏᴡɴ) font style.
    """
    normal_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    styled_chars = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    
    trans_table = str.maketrans(normal_chars, styled_chars)
    return text.translate(trans_table)
