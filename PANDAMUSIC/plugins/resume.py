from pyrogram import filters

from .. import bot, call, cdx
from ..modules.helpers import AdminsOnlyWrapper
from .maintenance import block_if_maintenance


@bot.on_message(cdx("resume") & ~filters.private)
@AdminsOnlyWrapper
async def resume_vc_stream(client, message):
    if await block_if_maintenance(message):
        return
    chat_id = message.chat.id
    playing = call.queue.get(chat_id) or (chat_id in getattr(call, "active_chats", []))
    if not playing:
        return await message.reply_text("**Nothing Streaming.**")
    if not await call.is_stream_off(chat_id):
        return await message.reply_text("**Not Paused.**")
    try:
        await call.resume_stream(chat_id)
        await call.stream_on(chat_id)
        return await message.reply_text("**Stream Resumed.**")
    except Exception:
        return await message.reply_text("**Failed to resume.**")
