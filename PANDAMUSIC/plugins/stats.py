# ---------------------------------------------------------------
# PANDAMUSIC — stats.py
# /stats — GENERAL & OVERALL buttons (real-time, this bot only)
# ---------------------------------------------------------------

print("[stats] loading plugin...", flush=True)

import os
import platform
import shutil
import sys

import psutil

try:
    import pyrogram
except Exception:
    pyrogram = None
try:
    import pytgcalls
except Exception:
    pytgcalls = None
try:
    import ntgcalls
except Exception:
    ntgcalls = None

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import bot, call, console, cdx, rgx
from ..modules.database import (
    count_served_chats,
    count_served_users,
    count_sudoers,
    add_served_user,
    add_served_chat,
)
from .maintenance import block_if_maintenance

try:
    from pyrogram.enums import ButtonStyle
    _PRIMARY = ButtonStyle.PRIMARY
    _SUCCESS = ButtonStyle.SUCCESS
    _DANGER = ButtonStyle.DANGER
except Exception:
    _PRIMARY = "primary"
    _SUCCESS = "success"
    _DANGER = "danger"


def _btn(text, style=None, **kwargs):
    if style is not None:
        try:
            return InlineKeyboardButton(text, style=style, **kwargs)
        except TypeError:
            pass
        try:
            return InlineKeyboardButton(
                text, style=str(getattr(style, "name", style)).lower(), **kwargs
            )
        except TypeError:
            pass
    return InlineKeyboardButton(text, **kwargs)


def stats_home_markup():
    return InlineKeyboardMarkup(
        [
            [
                _btn("❖ GENERAL ❖", _PRIMARY, callback_data="stats_general"),
                _btn("❖ OVERALL ❖", _SUCCESS, callback_data="stats_overall"),
            ],
            [_btn("CLOSE", _DANGER, callback_data="close")],
        ]
    )


def stats_back_markup():
    return InlineKeyboardMarkup(
        [
            [
                _btn("❖ GENERAL ❖", _PRIMARY, callback_data="stats_general"),
                _btn("❖ OVERALL ❖", _SUCCESS, callback_data="stats_overall"),
            ],
            [_btn("CLOSE", _DANGER, callback_data="close")],
        ]
    )


def _gib(bytes_val: float) -> str:
    return f"{bytes_val / (1024 ** 3):.2f}"


def _count_modules() -> int:
    try:
        from ..plugins import ALL_PLUGINS

        return len(ALL_PLUGINS)
    except Exception:
        try:
            plugin_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "plugins"
            )
            return len(
                [
                    f
                    for f in os.listdir(plugin_dir)
                    if f.endswith(".py") and not f.startswith("_")
                ]
            )
        except Exception:
            return 0


def _assistant_count() -> int:
    try:
        from ..modules.clients import assistants

        return len(assistants) or (1 if console.STRING1 else 0)
    except Exception:
        return 1 if console.STRING1 else 0


async def build_overall_text(username: str) -> str:
    users = await count_served_users()
    chats = await count_served_chats()
    sudos = await count_sudoers()
    modules = _count_modules()
    assistants_n = _assistant_count()
    duration = getattr(console, "DURATION_LIMIT", 60)

    return (
        f"❖ <b>@{username}</b> sᴛᴀᴛs ᴀɴᴅ ɪɴғᴏʀᴍᴀᴛɪᴏɴ :\n\n"
        f"ᴀssɪsᴛᴀɴᴛs : <code>{assistants_n}</code>\n"
        f"ʙʟᴏᴄᴋᴇᴅ : <code>0</code>\n"
        f"ᴄʜᴀᴛs: <code>{chats}</code>\n"
        f"ᴜsᴇʀs : <code>{users}</code>\n"
        f"ᴍᴏᴅᴜʟᴇs : <code>{modules}</code>\n"
        f"sᴜᴅᴏᴇʀs : <code>{sudos}</code>\n\n"
        f"ᴀᴜᴛᴏ ʟᴇᴀᴠɪɴɢ ᴀssɪsᴛᴀɴᴛ : <code>False</code>\n"
        f"ᴘʟᴀʏ ᴅᴜʀᴀᴛɪᴏɴ ʟɪᴍɪᴛ : <code>{duration}</code> ᴍɪɴᴜᴛᴇs"
    )


async def build_general_text(username: str) -> str:
    users = await count_served_users()
    chats = await count_served_chats()
    sudos = await count_sudoers()
    modules = _count_modules()

    # System
    plat = platform.system()
    vm = psutil.virtual_memory()
    ram = f"{_gib(vm.used)} / {_gib(vm.total)} GiB"
    try:
        physical = psutil.cpu_count(logical=False) or 0
    except Exception:
        physical = 0
    total_cores = psutil.cpu_count(logical=True) or 0
    try:
        freq = psutil.cpu_freq()
        cpu_mhz = f"{int(freq.current)} MHz" if freq else "N/A"
    except Exception:
        cpu_mhz = "N/A"

    py_ver = platform.python_version()
    pyro_ver = getattr(pyrogram, "__version__", "N/A") if pyrogram else "N/A"
    pytg_ver = getattr(pytgcalls, "__version__", "N/A") if pytgcalls else "N/A"

    du = shutil.disk_usage("/")
    storage_avail = _gib(du.total)
    storage_used = _gib(du.used)
    storage_left = _gib(du.free)

    return (
        f"❖ <b>@{username}</b> sᴛᴀᴛs ᴀɴᴅ ɪɴғᴏʀᴍᴀᴛɪᴏɴ :\n\n"
        f"❖ ᴍᴏᴅᴜʟᴇs : <code>{modules}</code>\n"
        f"ᴘʟᴀᴛғᴏʀᴍ : <code>{plat}</code>\n"
        f"ʀᴀᴍ : <code>{ram}</code>\n"
        f"ᴘʜʏsɪᴄᴀʟ ᴄᴏʀᴇs : <code>{physical}</code>\n"
        f"ᴛᴏᴛᴀʟ ᴄᴏʀᴇs : <code>{total_cores}</code>\n"
        f"ᴄᴘᴜ ғʀᴇǫᴜᴇɴᴄʏ : <code>{cpu_mhz}</code>\n\n"
        f"ᴘʏᴛʜᴏɴ : <code>{py_ver}</code>\n"
        f"ᴘʏʀᴏɢʀᴀᴍ : <code>{pyro_ver}</code>\n"
        f"ᴘʏ-ᴛɢᴄᴀʟʟs : <code>{pytg_ver}</code>\n\n"
        f"sᴛᴏʀᴀɢᴇ ᴀᴠᴀɪʟᴀʙʟᴇ : <code>{storage_avail}</code> ɢɪʙ\n"
        f"sᴛᴏʀᴀɢᴇ ᴜsᴇᴅ : <code>{storage_used}</code> ɢɪʙ\n"
        f"sᴛᴏʀᴀɢᴇ ʟᴇғᴛ : <code>{storage_left}</code> ɢɪʙ\n\n"
        f"sᴇʀᴠᴇᴅ ᴄʜᴀᴛs : <code>{chats}</code>\n"
        f"sᴇʀᴠᴇᴅ ᴜsᴇʀs : <code>{users}</code>\n"
        f"ʙʟᴏᴄᴋᴇᴅ ᴜsᴇʀs : <code>0</code>\n"
        f"sᴜᴅᴏ ᴜsᴇʀs : <code>{sudos}</code>\n\n"
        f"ᴛᴏᴛᴀʟ ᴅʙ sɪᴢᴇ : <code>N/A</code> ᴍʙ\n"
        f"ᴛᴏᴛᴀʟ ᴅʙ sᴛᴏʀᴀɢᴇ : <code>N/A</code> ᴍʙ\n"
        f"ᴛᴏᴛᴀʟ ᴅʙ ᴄᴏʟʟᴇᴄᴛɪᴏɴs : <code>N/A</code>\n"
        f"ᴛᴏᴛᴀʟ ᴅʙ ᴋᴇʏs : <code>N/A</code>"
    )


@bot.on_message(cdx("stats") & filters.incoming)
async def stats_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return

    try:
        if message.from_user:
            await add_served_user(message.from_user.id)
        if message.chat and message.chat.type.name != "PRIVATE":
            await add_served_chat(message.chat.id)
    except Exception:
        pass

    try:
        await message.delete()
    except Exception:
        pass

    me = client.me or await client.get_me()
    uname = me.username or "PANDAMUSIC"

    photo = getattr(console, "START_IMAGE_URL", None)
    caption = (
        f"❖ <b>CLICK ON THE BUTTONS</b>\n"
        f"<b>BELOW TO CHECK THE STATS OF</b>\n"
        f"<b>@{uname}</b>"
    )
    markup = stats_home_markup()

    try:
        if photo:
            await message.reply_photo(
                photo=photo,
                caption=caption,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.reply_text(
                caption, reply_markup=markup, parse_mode=ParseMode.HTML
            )
    except Exception:
        await message.reply_text(
            caption, reply_markup=markup, parse_mode=ParseMode.HTML
        )


@bot.on_callback_query(rgx("stats_overall"))
async def stats_overall_cb(client, query):
    try:
        me = client.me or await client.get_me()
        uname = me.username or "PANDAMUSIC"
        text = await build_overall_text(uname)
        try:
            await query.message.edit_caption(
                caption=text, reply_markup=stats_back_markup(), parse_mode=ParseMode.HTML
            )
        except Exception:
            await query.message.edit_text(
                text, reply_markup=stats_back_markup(), parse_mode=ParseMode.HTML
            )
    except Exception as e:
        print(f"[stats] overall error: {e}", flush=True)
    await query.answer()


@bot.on_callback_query(rgx("stats_general"))
async def stats_general_cb(client, query):
    try:
        me = client.me or await client.get_me()
        uname = me.username or "PANDAMUSIC"
        text = await build_general_text(uname)
        try:
            await query.message.edit_caption(
                caption=text, reply_markup=stats_back_markup(), parse_mode=ParseMode.HTML
            )
        except Exception:
            await query.message.edit_text(
                text, reply_markup=stats_back_markup(), parse_mode=ParseMode.HTML
            )
    except Exception as e:
        print(f"[stats] general error: {e}", flush=True)
    await query.answer()


# Track served users/chats on any group message (lightweight)
@bot.on_message(filters.group & filters.incoming, group=50)
async def track_served(client, message: Message):
    try:
        if message.from_user and not message.from_user.is_bot:
            await add_served_user(message.from_user.id)
        if message.chat:
            await add_served_chat(message.chat.id)
    except Exception:
        pass


print("[stats] plugin loaded OK", flush=True)
