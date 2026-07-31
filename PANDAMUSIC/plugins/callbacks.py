import asyncio
import time
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .. import bot, call, rgx

# Kurigram ButtonStyle (Bot API 9.4+ / MTProto colored buttons)
try:
    from pyrogram.enums import ButtonStyle

    _STYLE_PRIMARY = ButtonStyle.PRIMARY
    _STYLE_SUCCESS = ButtonStyle.SUCCESS
    _STYLE_DANGER = ButtonStyle.DANGER
    _HAS_STYLE = True
    print("[buttons] ButtonStyle OK — colored buttons enabled", flush=True)
except Exception as e:
    _STYLE_PRIMARY = "primary"
    _STYLE_SUCCESS = "success"
    _STYLE_DANGER = "danger"
    _HAS_STYLE = False
    print(f"[buttons] ButtonStyle missing ({e}) — upgrade kurigram", flush=True)

_progress_tasks = {}
SEEK_SECONDS = 10


def _btn(text: str, callback_data: str, style=None) -> InlineKeyboardButton:
    """Create button; attach color style when supported."""
    kwargs = {"text": text, "callback_data": callback_data}
    if style is not None:
        try:
            return InlineKeyboardButton(**kwargs, style=style)
        except TypeError:
            pass
        try:
            return InlineKeyboardButton(
                **kwargs, style=str(getattr(style, "name", style)).lower()
            )
        except TypeError:
            pass
    return InlineKeyboardButton(**kwargs)


def _fmt(seconds: int) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _parse_duration(dur) -> int:
    try:
        parts = [int(x) for x in str(dur).split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception:
        pass
    return 0


def _progress_bar(elapsed: int, total: int, width: int = 9) -> str:
    if total <= 0:
        return f"{_fmt(elapsed)} {'─' * width} ●"
    ratio = min(elapsed / max(total, 1), 1.0)
    pos = min(round(ratio * width), width)
    bar = "─" * pos + "●" + "─" * (width - pos)
    return f"{_fmt(elapsed)} {bar} {_fmt(total)}"


def player_markup(chat_id: int, elapsed: int = 0, total: int = 0) -> InlineKeyboardMarkup:
    bar = _progress_bar(elapsed, total)
    return InlineKeyboardMarkup(
        [
            [
                _btn("⏪ -10", f"PLAYER SeekBack|{chat_id}", _STYLE_PRIMARY),
                _btn("▷", f"PLAYER Resume|{chat_id}", _STYLE_PRIMARY),
                _btn("II", f"PLAYER Pause|{chat_id}", _STYLE_SUCCESS),
                _btn("‣‣I", f"PLAYER Skip|{chat_id}", _STYLE_PRIMARY),
                _btn("▢", f"PLAYER Stop|{chat_id}", _STYLE_DANGER),
                _btn("+10 ⏩", f"PLAYER SeekFwd|{chat_id}", _STYLE_PRIMARY),
            ],
            [
                _btn(bar, f"PLAYER Progress|{chat_id}", _STYLE_SUCCESS),
            ],
            [
                _btn("🗑 Close", "close", _STYLE_DANGER),
            ],
        ]
    )


def queue_markup(chat_id: int, index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                _btn("▷ Play Now", f"QUEUE Play|{chat_id}|{index}", _STYLE_PRIMARY),
                _btn("‣‣I Skip", f"PLAYER Skip|{chat_id}", _STYLE_SUCCESS),
            ],
            [
                _btn("🗑 Close", "close", _STYLE_DANGER),
            ],
        ]
    )


def _is_playing(chat_id: int) -> bool:
    if call.queue.get(chat_id):
        return True
    return chat_id in getattr(call, "active_chats", [])


def _get_progress(chat_id: int):
    queued = call.queue.get(chat_id) or []
    if not queued:
        return 0, 0, "Unknown"
    item = queued[0]
    title = str(item.get("title", "Unknown"))[:30]
    total = _parse_duration(item.get("duration", "0:00"))
    start = getattr(call, "start_times", {}).get(chat_id)
    if await_paused(chat_id):
        played = item.get("played", 0)
        elapsed = int(played)
    else:
        elapsed = int(time.time() - start) if start else 0
        item["played"] = elapsed
    if total:
        elapsed = min(elapsed, total)
    return elapsed, total, title


def await_paused(chat_id: int) -> bool:
    return bool(call.paused.get(chat_id))


async def _do_seek(chat_id: int, delta: int):
    """Seek relative by delta seconds. Returns (ok, message)."""
    elapsed, total, _title = _get_progress(chat_id)
    new_pos = max(0, elapsed + delta)
    if total > 0:
        new_pos = min(new_pos, max(0, total - 1))

    if new_pos == elapsed:
        if delta < 0:
            return False, "Already at start"
        return False, "Already at end"

    try:
        await call.seek_stream(chat_id, new_pos)
    except Exception as e:
        return False, f"Seek failed: {type(e).__name__}"

    # Keep progress tracking in sync
    if not hasattr(call, "start_times"):
        call.start_times = {}
    call.start_times[chat_id] = time.time() - new_pos
    queued = call.queue.get(chat_id) or []
    if queued:
        queued[0]["played"] = new_pos

    return True, f"Seeked to {_fmt(new_pos)}"


async def _progress_loop(chat_id: int):
    while True:
        await asyncio.sleep(8)
        try:
            queued = call.queue.get(chat_id)
            if not queued:
                break
            if chat_id not in getattr(call, "active_chats", []):
                break

            panel = queued[0].get("panel")
            if not panel:
                continue

            elapsed, total, _title = _get_progress(chat_id)
            try:
                await panel.edit_reply_markup(
                    reply_markup=player_markup(chat_id, elapsed, total)
                )
            except Exception:
                pass

            if total and elapsed >= total:
                break
        except asyncio.CancelledError:
            break
        except Exception:
            break


def start_progress_task(chat_id: int):
    old = _progress_tasks.get(chat_id)
    if old and not old.done():
        old.cancel()
    task = asyncio.create_task(_progress_loop(chat_id))
    _progress_tasks[chat_id] = task


def stop_progress_task(chat_id: int):
    old = _progress_tasks.pop(chat_id, None)
    if old and not old.done():
        old.cancel()


@bot.on_callback_query(rgx("close"))
async def close_cb(client, query):
    try:
        await query.message.delete()
    except Exception:
        pass


@bot.on_callback_query(rgx(r"^QUEUE "))
async def queue_panel_cb(client, query):
    try:
        parts = query.data.strip().split()
        action_rest = parts[1]
        action, chat_id_s, index_s = action_rest.split("|")
        chat_id = int(chat_id_s)
        index = int(index_s)
        action = action.strip()
    except Exception:
        return await query.answer("Invalid button.", show_alert=True)

    if not _is_playing(chat_id):
        return await query.answer("Nothing playing.", show_alert=True)

    if action == "Play":
        try:
            queued = call.queue.get(chat_id) or []
            if index <= 0 or index >= len(queued):
                return await query.answer("Song not in queue.", show_alert=True)

            item = queued.pop(index)
            queued.insert(1, item)
            call.queue[chat_id] = queued

            await call.change_stream(chat_id)
            if not hasattr(call, "start_times"):
                call.start_times = {}
            call.start_times[chat_id] = time.time()
            await query.answer("Playing now...", show_alert=False)
            try:
                await query.message.delete()
            except Exception:
                pass
        except Exception as e:
            await query.answer(f"Error: {type(e).__name__}", show_alert=True)
    else:
        await query.answer("Unknown action.", show_alert=True)


@bot.on_callback_query(rgx(r"^PLAYER "))
async def player_panel_cb(client, query):
    try:
        data = query.data.strip()
        _, action_chat = data.split(None, 1)
        action, chat_id_s = action_chat.split("|")
        chat_id = int(chat_id_s)
        action = action.strip()
    except Exception:
        return await query.answer("Invalid button.", show_alert=True)

    if not _is_playing(chat_id):
        return await query.answer("Nothing playing.", show_alert=True)

    if action == "Pause":
        try:
            await call.pause_stream(chat_id)
            await call.stream_off(chat_id)
            queued = call.queue.get(chat_id) or []
            if queued:
                start = getattr(call, "start_times", {}).get(chat_id)
                if start:
                    queued[0]["played"] = int(time.time() - start)
            await query.answer("Paused", show_alert=False)
        except Exception as e:
            await query.answer(f"Error: {type(e).__name__}", show_alert=True)

    elif action == "Resume":
        try:
            await call.resume_stream(chat_id)
            await call.stream_on(chat_id)
            queued = call.queue.get(chat_id) or []
            played = int(queued[0].get("played", 0)) if queued else 0
            if not hasattr(call, "start_times"):
                call.start_times = {}
            call.start_times[chat_id] = time.time() - played
            await query.answer("Resumed", show_alert=False)
        except Exception as e:
            await query.answer(f"Error: {type(e).__name__}", show_alert=True)

    elif action == "Skip":
        try:
            queued = call.queue.get(chat_id) or []
            if len(queued) <= 1:
                stop_progress_task(chat_id)
                await call.close_stream(chat_id)
                await query.answer("Stopped (queue empty)", show_alert=True)
                try:
                    await query.message.delete()
                except Exception:
                    pass
            else:
                await call.change_stream(chat_id)
                await query.answer("Skipped", show_alert=False)
        except Exception as e:
            await query.answer(f"Error: {type(e).__name__}", show_alert=True)

    elif action == "Stop":
        try:
            stop_progress_task(chat_id)
            await call.close_stream(chat_id)
            await query.answer("Stopped", show_alert=False)
            try:
                await query.message.delete()
            except Exception:
                pass
            try:
                await bot.send_message(
                    chat_id,
                    f"Streaming stopped by {query.from_user.mention}",
                )
            except Exception:
                pass
        except Exception as e:
            await query.answer(f"Error: {type(e).__name__}", show_alert=True)

    elif action == "Progress":
        try:
            elapsed, total, title = _get_progress(chat_id)
            bar = _progress_bar(elapsed, total)
            await query.answer(f"{title}\n{bar}", show_alert=True)
            try:
                await query.message.edit_reply_markup(
                    reply_markup=player_markup(chat_id, elapsed, total)
                )
            except Exception:
                pass
        except Exception as e:
            await query.answer(f"Error: {type(e).__name__}", show_alert=True)

    elif action in ("SeekBack", "SeekFwd"):
        delta = -SEEK_SECONDS if action == "SeekBack" else SEEK_SECONDS
        ok, msg = await _do_seek(chat_id, delta)
        await query.answer(msg, show_alert=not ok)
        if ok:
            try:
                elapsed, total, _ = _get_progress(chat_id)
                await query.message.edit_reply_markup(
                    reply_markup=player_markup(chat_id, elapsed, total)
                )
            except Exception:
                pass

    else:
        await query.answer("Unknown action.", show_alert=True)
