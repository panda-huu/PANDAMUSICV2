# ---------------------------------------------------------------
# PANDAMUSIC — guessgame.py
# Every 5 min: send rough-text image → users guess → coins reward
# ---------------------------------------------------------------

print("[guessgame] loading plugin...", flush=True)

import asyncio
import io
import json
import os
import random
import secrets
import time

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from pyrogram.types import Message

from .. import bot, cdx
from .maintenance import block_if_maintenance

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_GAMES_DB = os.path.join(_BASE, "games_db.json")
_GUESS_DB = os.path.join(_BASE, "guess_chats.json")
_CACHE = os.path.join(_BASE, "cache")
os.makedirs(_CACHE, exist_ok=True)

_RNG = secrets.SystemRandom()
INTERVAL_SEC = 300  # 5 minutes
REWARD = 150

# active round per chat: chat_id -> {"word": str, "msg_id": int, "ts": float}
_ACTIVE: dict = {}
_TASK_STARTED = False

WORDS = [
    "APPLE", "TIGER", "MUSIC", "PANDA", "CLOUD", "RIVER", "HAPPY",
    "LIGHT", "STONE", "BRAVE", "SMILE", "DREAM", "MAGIC", "STORM",
    "FLAME", "OCEAN", "PEACE", "CROWN", "EAGLE", "HONEY", "LEMON",
    "MANGO", "NIGHT", "POWER", "QUEEN", "ROBOT", "SHARK", "TRAIN",
    "UNITY", "VOICE", "WATER", "ZEBRA", "ANGEL", "BERRY", "CANDY",
    "DANCE", "EARTH", "FROST", "GHOST", "HEART", "IVORY", "JOKER",
    "KITTY", "LUCKY", "MOON", "NOVA", "ORBIT", "PIXEL", "QUICK",
    "RADIO", "SOLAR", "TURBO", "ULTRA", "VIBES", "WAVE", "XENON",
]


def _load_games() -> dict:
    try:
        if os.path.exists(_GAMES_DB):
            with open(_GAMES_DB, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"users": {}, "friends": {}}


def _save_games(data: dict):
    try:
        with open(_GAMES_DB, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[guessgame] games save error: {e}", flush=True)


def _user(data: dict, user_id: int) -> dict:
    key = str(user_id)
    if key not in data.setdefault("users", {}):
        data["users"][key] = {
            "coins": 1000,
            "xp": 0,
            "wins": 0,
            "losses": 0,
            "kills": 0,
            "inventory": {},
            "hp": 100,
            "alive": True,
        }
    u = data["users"][key]
    u.setdefault("coins", 1000)
    return u


def _load_chats() -> list:
    try:
        if os.path.exists(_GUESS_DB):
            with open(_GUESS_DB, "r") as f:
                data = json.load(f)
                return list(data.get("chats") or [])
    except Exception:
        pass
    return []


def _save_chats(chats: list):
    try:
        with open(_GUESS_DB, "w") as f:
            json.dump({"chats": chats}, f)
    except Exception as e:
        print(f"[guessgame] chats save error: {e}", flush=True)


def _make_image(word: str) -> bytes:
    """Rough / hard-to-read captcha-style text image."""
    w, h = 480, 180
    bg = (
        _RNG.randint(20, 60),
        _RNG.randint(20, 60),
        _RNG.randint(20, 60),
    )
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    # noise dots
    for _ in range(400):
        x, y = _RNG.randint(0, w - 1), _RNG.randint(0, h - 1)
        draw.point(
            (x, y),
            fill=(
                _RNG.randint(0, 255),
                _RNG.randint(0, 255),
                _RNG.randint(0, 255),
            ),
        )

    # noise lines
    for _ in range(12):
        draw.line(
            (
                _RNG.randint(0, w),
                _RNG.randint(0, h),
                _RNG.randint(0, w),
                _RNG.randint(0, h),
            ),
            fill=(
                _RNG.randint(80, 200),
                _RNG.randint(80, 200),
                _RNG.randint(80, 200),
            ),
            width=_RNG.randint(1, 3),
        )

    # try default font, fallback
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", 56)
        except Exception:
            font = ImageFont.load_default()

    # measure text
    try:
        bbox = draw.textbbox((0, 0), word, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = len(word) * 28, 40

    tx = (w - tw) // 2 + _RNG.randint(-15, 15)
    ty = (h - th) // 2 + _RNG.randint(-10, 10)

    # shadow
    draw.text((tx + 3, ty + 3), word, font=font, fill=(0, 0, 0))
    # main text with random color
    color = (
        _RNG.randint(180, 255),
        _RNG.randint(180, 255),
        _RNG.randint(180, 255),
    )
    draw.text((tx, ty), word, font=font, fill=color)

    # slight blur / distort feel
    img = img.filter(ImageFilter.SMOOTH)

    # rotate a bit
    angle = _RNG.uniform(-8, 8)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=0, fillcolor=bg)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


async def _is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def _send_round(client, chat_id: int):
    word = _RNG.choice(WORDS)
    img_bytes = _make_image(word)
    path = os.path.join(_CACHE, f"guess_{chat_id}.png")
    with open(path, "wb") as f:
        f.write(img_bytes)

    caption = (
        "🧠 <b>GUESS THE WORD</b>\n\n"
        "Image me jo text likha hai, woh type karke bhejo!\n"
        f"🏆 Winner gets <b>${REWARD}</b> coins\n"
        "⏱ Next round in 5 minutes"
    )
    try:
        msg = await client.send_photo(
            chat_id,
            photo=path,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
        _ACTIVE[chat_id] = {
            "word": word.upper(),
            "msg_id": msg.id,
            "ts": time.time(),
            "solved": False,
        }
        print(f"[guessgame] round in {chat_id}: {word}", flush=True)
    except Exception as e:
        print(f"[guessgame] send failed {chat_id}: {e}", flush=True)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


async def _guess_loop():
    await asyncio.sleep(15)  # let bot fully start
    print("[guessgame] background loop started", flush=True)
    while True:
        try:
            chats = _load_chats()
            for cid in list(chats):
                # skip if unsolved recent round < 2 min (avoid spam)
                active = _ACTIVE.get(cid)
                if active and not active.get("solved") and time.time() - active.get("ts", 0) < 120:
                    continue
                try:
                    await _send_round(bot, cid)
                except Exception as e:
                    print(f"[guessgame] loop chat error {cid}: {e}", flush=True)
                    # leave if bot kicked
                    if "CHAT_WRITE_FORBIDDEN" in str(e) or "PEER_ID_INVALID" in str(e):
                        chats = [c for c in chats if c != cid]
                        _save_chats(chats)
                        _ACTIVE.pop(cid, None)
        except Exception as e:
            print(f"[guessgame] loop error: {e}", flush=True)
        await asyncio.sleep(INTERVAL_SEC)


def _start_task():
    global _TASK_STARTED
    if _TASK_STARTED:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_guess_loop())
        _TASK_STARTED = True
        print("[guessgame] task scheduled", flush=True)
    except RuntimeError:
        print("[guessgame] no running loop yet — will retry", flush=True)


# schedule when plugin imports (import_all_plugins is awaited inside running loop)
_start_task()


@bot.on_message(cdx(["guesson", "startguess"]))
async def guess_on(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply_text("❌ Ye command groups me use karo.")
    if not await _is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins can enable guess game.")

    chats = _load_chats()
    if message.chat.id in chats:
        return await message.reply_text("✅ Guess game already ON in this group.")
    chats.append(message.chat.id)
    _save_chats(chats)
    await message.reply_text(
        "✅ <b>Guess Game ON</b>\n"
        "Har 5 minute me ek rough-text image aayegi.\n"
        "Sahi word type karo → coins milenge!\n"
        "Abhi ek round bhej raha hoon...",
        parse_mode=ParseMode.HTML,
    )
    await _send_round(client, message.chat.id)


@bot.on_message(cdx(["guesstoff", "stopguess"]))
async def guess_off(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply_text("❌ Ye command groups me use karo.")
    if not await _is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins can disable guess game.")

    chats = _load_chats()
    if message.chat.id not in chats:
        return await message.reply_text("📴 Guess game already OFF.")
    chats = [c for c in chats if c != message.chat.id]
    _save_chats(chats)
    _ACTIVE.pop(message.chat.id, None)
    await message.reply_text("🚫 Guess game disabled in this group.")


@bot.on_message(cdx(["newguess", "guessnow"]))
async def guess_now(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if message.chat.type == ChatType.PRIVATE:
        return await message.reply_text("❌ Groups me use karo.")
    if not await _is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins.")

    chats = _load_chats()
    if message.chat.id not in chats:
        chats.append(message.chat.id)
        _save_chats(chats)
    await _send_round(client, message.chat.id)


@bot.on_message(
    filters.group
    & filters.text
    & ~filters.bot
    & ~filters.service
    & ~filters.command(
        [
            "guesson", "startguess", "guesstoff", "stopguess",
            "newguess", "guessnow", "bal", "balance", "wallet",
        ],
        prefixes=["/", "!", "."],
    )
)
async def guess_answer(client, message: Message):
    if not message.from_user or not message.text:
        return

    chat_id = message.chat.id
    active = _ACTIVE.get(chat_id)
    if not active or active.get("solved"):
        return

    # ignore commands
    text = message.text.strip()
    if text.startswith(("/", "!", ".")):
        return

    # only short answers (1 word-ish)
    if len(text) > 20 or " " in text.strip():
        # allow single word only
        parts = text.split()
        if len(parts) != 1:
            return
        text = parts[0]

    guess = text.strip().upper()
    word = active.get("word", "").upper()
    if not word or guess != word:
        return

    # first correct wins
    active["solved"] = True
    _ACTIVE[chat_id] = active

    data = _load_games()
    u = _user(data, message.from_user.id)
    u["coins"] = int(u.get("coins") or 0) + REWARD
    u["xp"] = int(u.get("xp") or 0) + 5
    _save_games(data)

    name = (message.from_user.first_name or "User").replace("<", "").replace(">", "")
    mention = f'<a href="tg://user?id={message.from_user.id}">{name}</a>'

    await message.reply_text(
        f"🎉 <b>Correct!</b>\n\n"
        f"✅ Word: <b>{word}</b>\n"
        f"🏆 Winner: {mention}\n"
        f"💰 Reward: <b>${REWARD}</b>\n"
        f"👛 New balance: <b>${u['coins']:,}</b>\n\n"
        f"Check with /bal",
        parse_mode=ParseMode.HTML,
    )


print("[guessgame] plugin loaded OK", flush=True)
