import ntgcalls, pyrogram, pytgcalls
import platform, psutil, shutil


from .. import bot, cdx
from ..modules.database import get_served_chats, get_served_users

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton



def get_ram_usage() -> str:
    vm = psutil.virtual_memory()
    used = vm.used // (1024 ** 2)  # MB
    total = vm.total // (1024 ** 2)  # MB
    return f"{used} MB / {total} MB"


def get_cpu_usage() -> str:
    return f"{psutil.cpu_percent(interval=1)}%"


def get_storage_usage() -> str:
    du = shutil.disk_usage("/")
    used = du.used // (1024 ** 3)
    total = du.total // (1024 ** 3)
    return f"{used} GB / {total} GB"


@bot.on_message(cdx("stats"))
async def stats_handler(client, message):
    try:
        await message.delete()
    except Exception:
        pass
        
    # Versions
    pyro_version = pyrogram.__version__
    tgcalls_version = pytgcalls.__version__ if hasattr(pytgcalls, "__version__") else "Unknown"
    ntgcalls_version = ntgcalls.__version__ if hasattr(ntgcalls, "__version__") else "Unknown"

    # System stats
    ram_usage = get_ram_usage()
    cpu_usage = get_cpu_usage()
    storage_usage = get_storage_usage()
    
    # Platform
    system_info = platform.platform()

    # DB stats
    total_chats = len(await get_served_chats())
    total_users = len(await get_served_users())

    text = (
        "**📊 My Global & System Statistics.**\n\n"
        f"✴️ **Pyrogram Version:** `{pyro_version}`\n"
        f"🎵 **PyTgCalls Version:** `{tgcalls_version}`\n"
        f"🎧 **NTgCalls Version:** `{ntgcalls_version}`\n\n"
        f"💬 **Served Chats:** `{total_chats}`\n"
        f"👥 **Served Users:** `{total_users}`\n\n"
        f"⚡ **CPU Usage:** `{cpu_usage}`\n"
        f"💾 **RAM Usage:** `{ram_usage}`\n"
        f"📂 **Storage Usage:** `{storage_usage}`\n\n"
        f"🖥 **Platform:** `{system_info}`\n"
    )
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="🗑️ Close",
                    callback_data="close",
                ),
            ]
        ]
    )
    try:
        await message.reply_text(text, reply_markup=buttons)
    except Exception:
        pass
