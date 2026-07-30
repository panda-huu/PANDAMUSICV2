from .. import bot, cdx, call, sudoers



@bot.on_message(cdx(["ac", "active"]) & sudoers)
async def active_handler(client, message):
    try:
        await message.delete()
    except Exception:
        pass
    try:
        active_chats = len(call.active_chats)
        if active_chats == 0:
            return await message.reply_text("❎ **No active chats found.**")
    
        return await message.reply_text(f"✅ **Active Chats:** {active_chats}`")
    except Exception:
        pass

