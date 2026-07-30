# ---------------------------------------------------------------
# PANDAMUSIC — noabuse.py
# Auto-delete abusive messages | /noabuse on/off
# ---------------------------------------------------------------

print("[noabuse] loading plugin...", flush=True)

import asyncio
import json
import os
import re

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import Message

from .. import bot

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TOGGLE_DB_PATH = os.path.join(_BASE_DIR, "noabuse_toggle_db.json")
_DB_PATH = os.path.join(_BASE_DIR, "blacklist_db.json")


def _load_toggles() -> dict:
    try:
        if os.path.exists(_TOGGLE_DB_PATH):
            with open(_TOGGLE_DB_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_toggles(data: dict):
    try:
        with open(_TOGGLE_DB_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _key(chat_id: int) -> str:
    return str(chat_id)


def is_enabled(chat_id: int) -> bool:
    return _load_toggles().get(_key(chat_id), False)


def set_enabled(chat_id: int, value: bool):
    data = _load_toggles()
    data[_key(chat_id)] = value
    _save_toggles(data)


_ROOTS = [
    "chut", "bhosad", "bhosd", "bosd", "lund", "lavd", "lawd", "gaand", "gand",
    "rand", "rund", "madar", "mader", "behan", "bhen", "bhencho", "behench",
    "haraam", "haramz", "kameen", "rakhel", "kasb", "gashti", "chinal",
    "jhaat", "jhat", "tatti", "tattu", "pesaab", "pisaab", "muth", "mutth",
    "phudi", "bur", "chod", "chodna", "chodne", "chodu",
    "suar", "suwar", "gadha", "gadhi", "ullu", "kameena", "nikamm", "nalayak",
    "bhadwa", "bhadwe", "dalla", "dalle", "khanki", "pataka",
    "hijra", "hijda", "chhakka", "chakka", "nalli", "fattu", "fuddu",
    "raand", "raandi", "rundi", "randwa",
    "bhain", "lun", "maada", "maadi", "khabees", "chudail",
    "fuck", "fuk", "fck", "phuck", "fcuk", "fvck",
    "shit", "sht", "shyt",
    "bitch", "biatch", "bytch",
    "cunt", "cnt",
    "dick", "dik", "dck",
    "cock", "cok",
    "pussy", "puss", "pussi",
    "ass", "ars", "a55",
    "bastard", "bastad",
    "whore", "hore",
    "slut", "slvt",
    "nigga", "nigger", "nigg",
    "motherfuck", "motherf",
    "retard", "retrd",
    "faggot", "fagot", "fag",
    "wank", "wanker",
    "twat", "tw4t",
    "prick", "prik",
    "bollok", "bollock",
]

_ROOT_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9])("
    + "|".join(re.escape(r) for r in sorted(set(_ROOTS), key=len, reverse=True))
    + r")[a-zA-Z0-9]*(?![a-zA-Z0-9])",
    re.IGNORECASE,
)

RAW_WORDS = [
    "madarchod", "madarcho", "maderchod", "madarchut", "mc",
    "bhosdike", "bhosdika", "bhosdiki", "bhosdi", "bhosda", "bosdi", "bosdike",
    "chutiya", "chutiye", "chutiyapa", "chut", "choot", "chutad",
    "lund", "lode", "loda", "lavda", "lavde", "laude", "lauda",
    "randi", "rand", "randwa", "rundi", "randa", "raand",
    "harami", "haramkhor", "haraamzada", "haramzada", "haramzadi",
    "kamina", "kamine", "kameena", "kameeni",
    "kutte", "kutta", "kutiya", "kutti",
    "saala", "saali", "sala", "sali", "saale",
    "behenchod", "behench", "bc", "behnchod", "bhenchod",
    "gandu", "gaand", "gaandu",
    "gadha", "gadhe", "gadhi",
    "ullu", "bhadwe", "bhadwa", "chakka", "chhakka",
    "hijra", "hijda",
    "maa ki", "teri maa", "maa chod",
    "teri behen", "teri bhen",
    "bkl", "mkc", "mkb",
    "chod", "chodna", "chodu",
    "jhatu", "jhaatu", "jhaat",
    "tatti", "tattu",
    "bsdk", "bsdke",
    "lodu", "lode",
    "fuck", "fucker", "fucking", "fucked", "fck", "fuk",
    "motherfucker", "mf", "mofo",
    "shit", "shitty", "bullshit",
    "bastard", "bitch", "bitches",
    "whore", "slut",
    "cunt", "dick", "cock", "pussy",
    "asshole", "arse",
    "nigga", "nigger",
    "retard", "retarded",
    "idiot", "stupid", "dumbass",
    "wtf", "stfu", "gtfo",
    "wanker", "twat", "bollocks", "faggot",
    "douchebag", "scumbag", "jackass", "dipshit", "shithead",
]

_EXACT_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9])("
    + "|".join(re.escape(w) for w in sorted(set(RAW_WORDS), key=len, reverse=True))
    + r")(?![a-zA-Z0-9])",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\uFEFF]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("@", "a").replace("0", "o").replace("1", "i")
    text = text.replace("3", "e").replace("4", "a").replace("5", "s")
    text = text.replace("$", "s").replace("+", "t").replace("!", "i")
    return text


def contains_abuse(text: str) -> bool:
    if not text:
        return False
    clean = _normalize(text)
    if _ROOT_PATTERN.search(clean):
        return True
    if _EXACT_PATTERN.search(clean):
        return True
    return False


def _get_custom_words(chat_id: int) -> list:
    try:
        if os.path.exists(_DB_PATH):
            with open(_DB_PATH, "r") as f:
                data = json.load(f)
            return data.get(str(chat_id), [])
    except Exception:
        pass
    return []


def _matches_custom(text: str, words: list) -> bool:
    if not text or not words:
        return False
    t = text.lower()
    for w in words:
        if re.search(r"(?<![a-zA-Z0-9])" + re.escape(w) + r"(?![a-zA-Z0-9])", t):
            return True
    return False


async def _send(client, chat_id, text):
    try:
        return await client.send_message(chat_id, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"[noabuse] send error: {e}", flush=True)
        try:
            return await client.send_message(chat_id, text)
        except Exception:
            return None


@bot.on_message(
    filters.command(["noabuse"], ["/", "!", "."])
    & ~filters.private
    & filters.incoming,
    group=0,
)
async def noabuse_cmd(client, msg: Message):
    chat_id = msg.chat.id
    print(f"[noabuse] CMD in {chat_id} from {getattr(msg.from_user, 'id', None)}", flush=True)

    try:
        await msg.delete()
    except Exception:
        pass

    if not msg.from_user:
        return await _send(client, chat_id, "❌ Anonymous admins cannot use this.")

    is_adm = False
    try:
        from .. import console

        if msg.from_user.id == getattr(console, "OWNER_ID", 0):
            is_adm = True
        elif msg.from_user.id in getattr(console, "sudoers", []):
            is_adm = True
    except Exception:
        pass

    if not is_adm:
        try:
            member = await client.get_chat_member(chat_id, msg.from_user.id)
            is_adm = member.status in (
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            )
        except Exception as e:
            print(f"[noabuse] admin check error: {e}", flush=True)
            is_adm = False

    if not is_adm:
        return await _send(client, chat_id, "❌ <b>Only admins can use this!</b>")

    args = msg.command or []
    if len(args) < 2 or args[1].lower() not in ("on", "off"):
        status = "✅ ON" if is_enabled(chat_id) else "❌ OFF"
        return await _send(
            client,
            chat_id,
            f"<b>🚫 No-Abuse Status:</b> {status}\n\n"
            f"➻ /noabuse on  — enable ✅\n"
            f"➻ /noabuse off — disable ❌",
        )

    action = args[1].lower()
    if action == "on":
        set_enabled(chat_id, True)
        await _send(
            client,
            chat_id,
            "✅ <b>No-Abuse mode ENABLED!</b>\n\n"
            "🛡 Ab se abusive messages auto-delete honge.",
        )
    else:
        set_enabled(chat_id, False)
        await _send(client, chat_id, "❌ <b>No-Abuse mode DISABLED!</b>")


@bot.on_message(filters.group & filters.text & filters.incoming, group=-1)
async def abuse_watcher(client, msg: Message):
    if not msg.from_user:
        return

    text = msg.text or ""
    if text.startswith(("/", "!", ".")):
        return

    builtin_hit = is_enabled(msg.chat.id) and contains_abuse(text)
    custom_hit = _matches_custom(text, _get_custom_words(msg.chat.id))

    if not builtin_hit and not custom_hit:
        return

    try:
        await msg.delete()
    except Exception as e:
        print(f"[NOABUSE] Delete failed in {msg.chat.id}: {e}", flush=True)
        return

    try:
        warn = await client.send_message(
            msg.chat.id,
            f"⚠️ {msg.from_user.mention}\n\n"
            "<b>Don't use abusive words in group!</b>",
            parse_mode=ParseMode.HTML,
        )
        await asyncio.sleep(6)
        await warn.delete()
    except Exception as e:
        print(f"[NOABUSE] Warn failed in {msg.chat.id}: {e}", flush=True)


print("[noabuse] plugin loaded OK", flush=True)
