import logging
import os
import sys
import time

from os import getenv
from pyrogram import filters
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s:\n%(message)s\n",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("logs.txt", maxBytes=5000000, backupCount=10),
        logging.StreamHandler(),
    ],
)

logging.getLogger("asyncio").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)


def logs(name: str) -> logging.Logger:
    return logging.getLogger(name)


_boot_ = time.time()
plugs = {}
chat_admins = {}
chat_links = {}
sudoers = filters.user()


if os.path.exists("Config.env"):
    load_dotenv("Config.env")


try:
    API_ID = int(getenv("API_ID", 0))
    API_HASH = getenv("API_HASH", None)
    BOT_TOKEN = getenv("BOT_TOKEN", None)
    OWNER_ID = int(getenv("OWNER_ID", 0))
    LOG_GROUP_ID = int(getenv("LOG_GROUP_ID", 0))

    DB_HOST = getenv("DB_HOST", None)
    DB_PORT = int(getenv("DB_PORT", "6543"))
    DB_USER = getenv("DB_USER", None)
    DB_PASSWORD = getenv("DB_PASSWORD", None)
    DB_NAME = getenv("DB_NAME", "postgres")

    SHRUTI_API_URL = getenv("SHRUTI_API_URL", "https://aruyt.up.railway.app")
    SHRUTI_API_KEY = getenv("SHRUTI_API_KEY", "")
except Exception as e:
    logs(__name__).error(f"Variable Error: {e}")
    sys.exit(1)


STRING1 = getenv("STRING_SESSION", None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)

DURATION_LIMIT = int(getenv("DURATION_LIMIT", "60"))
START_IMAGE_URL = getenv(
    "START_IMAGE_URL",
    "https://graph.org/file/918101d0ad6b1207e6201.png",
)

# Start menu links
OWNER_USERNAME = getenv("OWNER_USERNAME", "").lstrip("@")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "").lstrip("@")
SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "").lstrip("@")  # UPDATE button


async def sudo_users():
    from .modules.database import get_sudoers_list, add_sudo

    global sudoers

    if OWNER_ID != 0:
        if OWNER_ID not in sudoers:
            sudoers.add(OWNER_ID)
        try:
            await add_sudo(OWNER_ID)
        except Exception:
            pass

    try:
        sudousers = await get_sudoers_list()
    except Exception:
        sudousers = [OWNER_ID] if OWNER_ID else []

    for user_id in sudousers:
        if user_id and user_id not in sudoers:
            sudoers.add(user_id)

    logs(__name__).info("All Sudo Users Loaded.")
