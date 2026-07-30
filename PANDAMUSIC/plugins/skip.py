from pyrogram import filters

from .. import bot, call, cdx
from ..modules.helpers import AdminsOnlyWrapper
from .maintenance import block_if_maintenance


@bot.on_message(cdx(["skip", "next"]) & ~filters.private)
@AdminsOnlyWrapper
async def skip_vc_stream(client, message):
    if await block_if_maintenance(message):
        return
    chat_id = message.chat.id
    playing = call.queue.get(chat_id) or (chat_id in getattr(call, "active_chats", []))
    if not playing:
        return await message.reply_text("**Nothing Streaming.**")
    try:
        await call.change_stream(chat_id)
        return await message.reply_text("**Skipped.**")
    except Exception:
        return await message.reply_text("**Failed to skip.**")
