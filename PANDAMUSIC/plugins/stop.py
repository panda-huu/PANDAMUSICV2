from pyrogram import filters

from .. import bot, call, cdx
from ..modules.helpers import AdminsOnlyWrapper
from .maintenance import block_if_maintenance
from .callbacks import stop_progress_task


@bot.on_message(cdx(["end", "stop"]) & ~filters.private)
@AdminsOnlyWrapper
async def stop_vc_stream(client, message):
    if await block_if_maintenance(message):
        return
    chat_id = message.chat.id
    playing = call.queue.get(chat_id) or (chat_id in getattr(call, "active_chats", []))
    if not playing:
        return await message.reply_text("**Nothing Streaming.**")
    try:
        stop_progress_task(chat_id)
        await call.close_stream(chat_id)
        return await message.reply_text("**Stream Ended.**")
    except Exception:
        return await message.reply_text("**Failed to stop.**")
