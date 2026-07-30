from functools import wraps

from pyrogram import filters
from pyrogram.types import Message, CallbackQuery

try:
    from pyrogram import StopPropagation
except ImportError:
    try:
        from pyrogram.errors import StopPropagation
    except ImportError:

        class StopPropagation(Exception):
            pass

from .. import bot, cdx, console

if not hasattr(console, "MAINTENANCE_MODE"):
    console.MAINTENANCE_MODE = False

MAINTENANCE_MSG = (
    "🛠 **Bot is currently under maintenance.**\n"
    "Please try again later."
)

PREFIXES = ("/", "!", ".")


def is_sudo(user_id: int) -> bool:
    if not user_id:
        return False
    if user_id == getattr(console, "OWNER_ID", 0):
        return True
    try:
        sudoers = console.sudoers
        users = getattr(sudoers, "users", None) or getattr(sudoers, "user_ids", None)
        if users is not None:
            return int(user_id) in {int(x) for x in users}
        return user_id in sudoers
    except Exception:
        return False


def is_maintenance() -> bool:
    return bool(getattr(console, "MAINTENANCE_MODE", False))


async def block_if_maintenance(message: Message) -> bool:
    if not is_maintenance():
        return False
    uid = message.from_user.id if message.from_user else 0
    if is_sudo(uid):
        return False
    try:
        await message.reply_text(MAINTENANCE_MSG)
    except Exception:
        pass
    return True


async def block_cb_if_maintenance(query: CallbackQuery) -> bool:
    if not is_maintenance():
        return False
    uid = query.from_user.id if query.from_user else 0
    if is_sudo(uid):
        return False
    try:
        await query.answer("🛠 Bot under maintenance.", show_alert=True)
    except Exception:
        pass
    return True


def maintenance_guard(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        if await block_if_maintenance(message):
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


@bot.on_message(cdx("maintenance") & filters.private, group=1)
async def maintenance_toggle(client, message: Message):
    if message.from_user is None or not is_sudo(message.from_user.id):
        return await message.reply_text(
            "❌ Yeh command sirf bot owner/sudo users use kar sakte hain."
        )

    args = (message.text or "").split(None, 1)
    if len(args) < 2:
        status = "ON ✅" if is_maintenance() else "OFF ❌"
        return await message.reply_text(
            f"🛠 **Maintenance Mode:** {status}\n\n"
            "Usage:\n"
            "`/maintenance on` - Maintenance mode chalu karein\n"
            "`/maintenance off` - Maintenance mode band karein"
        )

    state = args[1].strip().lower()

    if state in ("on", "true", "enable", "1"):
        console.MAINTENANCE_MODE = True
        await message.reply_text(
            "✅ **Maintenance mode ON.**\n"
            "Ab sirf owner/sudo hi bot use kar sakte hain.\n"
            f"Owner ID: `{console.OWNER_ID}`"
        )
    elif state in ("off", "false", "disable", "0"):
        console.MAINTENANCE_MODE = False
        await message.reply_text(
            "✅ **Maintenance mode OFF.**\nBot ab normal kaam karega."
        )
    else:
        await message.reply_text(
            "⚠️ Galat usage. `/maintenance on` ya `/maintenance off` use karein."
        )


@bot.on_message(filters.text & filters.incoming, group=-999)
async def maintenance_blocker(client, message: Message):
    if not is_maintenance():
        return

    text = (message.text or "").strip()
    if not text.startswith(PREFIXES):
        return

    uid = message.from_user.id if message.from_user else 0
    if is_sudo(uid):
        return

    try:
        await message.reply_text(MAINTENANCE_MSG)
    except Exception:
        pass

    raise StopPropagation


@bot.on_callback_query(group=-999)
async def maintenance_callback_blocker(client, query: CallbackQuery):
    if not is_maintenance():
        return

    uid = query.from_user.id if query.from_user else 0
    if is_sudo(uid):
        return

    try:
        await query.answer("🛠 Bot under maintenance.", show_alert=True)
    except Exception:
        pass

    raise StopPropagation
