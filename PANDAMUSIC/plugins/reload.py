from .. import bot, cdx, console
from ..modules.database import add_served_chat

from pyrogram import enums, filters



@bot.on_message(cdx("reload") & ~filters.private)
async def reload_handler(client, message):
    try:
        await message.delete()
    except Exception:
        pass
    chat_id = message.chat.id
    try:
        aux = await message.reply_text("**🥀 Please Wait ✨...**")
    except Exception:
        pass
    await add_served_chat(chat_id)
  
    if message.chat.username:
        chat_link = f"https://t.me/{message.chat.username}"
        console.chat_links[chat_id] = chat_link
    else:
        try:
            chat_link = await client.export_chat_invite_link(chat_id)
            console.chat_links[chat_id] = chat_link
        except Exception:
            pass

    if chat_id not in console.chat_admins:
        console.chat_admins[chat_id] = {}
    try:
        owners = filters.user()
        admins =  filters.user()
        async for m in client.get_chat_members(
            chat_id,filter=enums.ChatMembersFilter.ADMINISTRATORS
        ):
            if m.status == enums.ChatMemberStatus.OWNER:
                if m.user.id not in owners:
                    owners.add(m.user.id)
            if m.user.id not in admins:
                admins.add(m.user.id)
        
        console.chat_admins[chat_id]["owners"] = owners
        console.chat_admins[chat_id]["admins"] = admins
    except Exception:
        pass

    try:
        await aux.edit("✅ **Successfully Reloaded.**")
    except Exception:
        pass

  
