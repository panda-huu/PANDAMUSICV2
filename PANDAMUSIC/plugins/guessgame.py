# ---------------------------------------------------------------
# PANDAMUSIC — guessgame.py
# Every 5 min: rough-text image → 1 min to guess → first correct wins
# ---------------------------------------------------------------

print("[guessgame] loading plugin...", flush=True)

import asyncio
import io
import json
import os
import re
import secrets
import time

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType, ParseMode
from pyrogram.types import Message

from .. import bot, cdx
from .maintenance import block_if_maintenance

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_GAMES_DB = os.path.join(_BASE, "games_db.json")
_GUESS_DB = os.path.join(_BASE, "guess_chats.json")
_ACTIVE_DB = os.path.join(_BASE, "guess_active.json")
_CACHE = os.path.join(_BASE, "cache")
os.makedirs(_CACHE, exist_ok=True)

_RNG = secrets.SystemRandom()
INTERVAL_SEC = 300
GUESS_TIME = 60
REWARD = 150
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
            "coins": 1000, "xp": 0, "wins": 0, "losses": 0, "kills": 0,
            "inventory": {}, "hp": 100, "alive": True,
        }
    u = data["users"][key]
    u.setdefault("coins", 1000)
    u.setdefault("xp", 0)
    return u


def _load_chats() -> list:
    try:
        if os.path.exists(_GUESS_DB):
            with open(_GUESS_DB, "r") as f:
                data = json.load(f)
                return [int(c) for c in (data.get("chats") or [])]
    except Exception:
        pass
    return []


def _save_chats(chats: list):
    try:
        with open(_GUESS_DB, "w") as f:
            json.dump({"chats": [int(c) for c in chats]}, f)
    except Exception as e:
        print(f"[guessgame] chats save error: {e}", flush=True)


def _load_active() -> dict:
    try:
        if os.path.exists(_ACTIVE_DB):
            with open(_ACTIVE_DB, "r") as f:
                raw = json.load(f) or {}
                return {str(k): v for k, v in raw.items()}
    except Exception:
        pass
    return {}


def _save_active(data: dict):
    try:
        with open(_ACTIVE_DB, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[guessgame] active save error: {e}", flush=True)


def _get_round(chat_id: int):
    return _load_active().get(str(chat_id))


def _set_round(chat_id: int, info: dict):
    data = _load_active()
    data[str(chat_id)] = info
    _save_active(data)


def _clear_round(chat_id: int):
    data = _load_active()
    data.pop(str(chat_id), None)
    _save_active(data)


def _make_image(word: str) -> bytes:
    """Rough captcha — letters tight & centered so none get clipped."""
    w, h = 560, 220
    pad = 50  # safe margin so rotation doesn't hide letters
    bg = (_RNG.randint(18, 55), _RNG.randint(18, 55), _RNG.randint(18, 55))
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    # background noise (lighter density so letters stay readable)
    for _ in range(900):
        x, y = _RNG.randint(0, w - 1), _RNG.randint(0, h - 1)
        draw.point((x, y), fill=(_RNG.randint(0, 255), _RNG.randint(0, 255), _RNG.randint(0, 255)))

    for _ in range(16):
        draw.line(
            (_RNG.randint(0, w), _RNG.randint(0, h), _RNG.randint(0, w), _RNG.randint(0, h)),
            fill=(_RNG.randint(50, 180), _RNG.randint(50, 180), _RNG.randint(50, 180)),
            width=_RNG.randint(1, 3),
        )

    for _ in range(6):
        x0 = _RNG.randint(0, w)
        y0 = _RNG.randint(0, h)
        draw.arc(
            (x0, y0, x0 + _RNG.randint(40, 100), y0 + _RNG.randint(25, 70)),
            start=_RNG.randint(0, 360),
            end=_RNG.randint(0, 360),
            fill=(_RNG.randint(70, 180), _RNG.randint(70, 180), _RNG.randint(70, 180)),
            width=2,
        )

    # one solid font size so spacing is predictable
    font = None
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        try:
            font = ImageFont.truetype(path, 54)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    # measure full word width with tight letter gaps
    letter_gap = 8
    char_widths = []
    for ch in word:
        try:
            bb = draw.textbbox((0, 0), ch, font=font)
            char_widths.append(bb[2] - bb[0])
        except Exception:
            char_widths.append(32)

    text_w = sum(char_widths) + letter_gap * (len(word) - 1)
    # center horizontally inside safe pad
    start_x = max(pad, (w - text_w) // 2)
    base_y = h // 2 - 28

    x = start_x
    for i, ch in enumerate(word):
        # small jitter only — keep letters on canvas
        ox = x + _RNG.randint(-3, 3)
        oy = base_y + _RNG.randint(-10, 10)
        ox = max(pad // 2, min(ox, w - pad))
        oy = max(pad // 2, min(oy, h - pad - 20))

        # ghost
        draw.text(
            (ox + 2, oy + 2),
            ch,
            font=font,
            fill=(_RNG.randint(40, 80), _RNG.randint(40, 80), _RNG.randint(40, 80)),
        )
        # main letter — brighter so visible through noise
        color = (_RNG.randint(190, 255), _RNG.randint(190, 255), _RNG.randint(190, 255))
        draw.text((ox, oy), ch, font=font, fill=color)

        # light strike (not covering whole letter)
        if _RNG.random() < 0.4:
            sy = oy + _RNG.randint(18, 28)
            draw.line(
                (ox, sy, ox + char_widths[i], sy + _RNG.randint(-2, 2)),
                fill=(_RNG.randint(100, 160), _RNG.randint(100, 160), _RNG.randint(100, 160)),
                width=1,
            )

        x += char_widths[i] + letter_gap

    # lines over text (thinner)
    for _ in range(8):
        draw.line(
            (_RNG.randint(0, w), _RNG.randint(0, h), _RNG.randint(0, w), _RNG.randint(0, h)),
            fill=(_RNG.randint(60, 150), _RNG.randint(60, 150), _RNG.randint(60, 150)),
            width=1,
        )

    # light blur only
    img = img.filter(ImageFilter.GaussianBlur(radius=_RNG.uniform(0.3, 0.7)))

    # mild rotate — small angle so edges don't clip letters
    angle = _RNG.uniform(-5, 5)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=0, fillcolor=bg)

    try:
        img = ImageEnhance.Contrast(img).enhance(0.95)
    except Exception:
        pass

    # light final noise
    draw2 = ImageDraw.Draw(img)
    for _ in range(350):
        x, y = _RNG.randint(0, w - 1), _RNG.randint(0, h - 1)
        draw2.point((x, y), fill=(_RNG.randint(0, 255), _RNG.randint(0, 255), _RNG.randint(0, 255)))

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


async def _expire_round(chat_id: int, msg_id: int, word: str):
    await asyncio.sleep(GUESS_TIME)
    active = _get_round(chat_id)
    if not active:
        return
    if active.get("msg_id") != msg_id:
        return
    if active.get("solved"):
        return

    active["solved"] = True
    active["expired"] = True
    _set_round(chat_id, active)

    try:
        await bot.send_message(
            chat_id,
            f"⏰ <b>Time's up!</b> (1 minute)\n"
            f"Word was: <b>{word}</b>\n"
            f"Next round in a few minutes...",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        print(f"[guessgame] expire msg failed: {e}", flush=True)


async def _send_round(client, chat_id: int):
    word = _RNG.choice(WORDS)
    img_bytes = _make_image(word)
    path = os.path.join(_CACHE, f"guess_{chat_id}.png")
    with open(path, "wb") as f:
        f.write(img_bytes)

    caption = (
        "🧠 <b>GUESS THE WORD</b>\n\n"
        "Image me rough text padho aur type karo!\n"
        f"⏱ <b>Only 1 minute</b> to answer\n"
        f"🏆 First correct → <b>${REWARD}</b> coins\n"
        "⚠️ Pehla sahi guess jeetega — uske baad lock"
    )
    try:
        msg = await client.send_photo(
            chat_id,
            photo=path,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
        _set_round(
            chat_id,
            {
                "word": word.upper(),
                "msg_id": msg.id,
                "ts": time.time(),
                "solved": False,
                "expired": False,
                "winner_id": None,
            },
        )
        try:
            asyncio.get_running_loop().create_task(
                _expire_round(chat_id, msg.id, word.upper())
            )
        except Exception:
            pass
        print(f"[guessgame] round in {chat_id}: {word}", flush=True)
    except Exception as e:
        print(f"[guessgame] send failed {chat_id}: {e}", flush=True)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


async def _guess_loop():
    await asyncio.sleep(15)
    print("[guessgame] background loop started", flush=True)
    while True:
        try:
            chats = _load_chats()
            for cid in list(chats):
                active = _get_round(cid)
                if active and not active.get("solved") and time.time() - float(active.get("ts") or 0) < GUESS_TIME:
                    continue
                try:
                    await _send_round(bot, cid)
                except Exception as e:
                    print(f"[guessgame] loop chat error {cid}: {e}", flush=True)
                    if "CHAT_WRITE_FORBIDDEN" in str(e) or "PEER_ID_INVALID" in str(e):
                        chats = [c for c in chats if int(c) != int(cid)]
                        _save_chats(chats)
                        _clear_round(cid)
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
        print("[guessgame] no running loop yet", flush=True)


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
        await message.reply_text("✅ Guess game already ON — naya round bhej raha hoon...")
        await _send_round(client, message.chat.id)
        return

    chats.append(message.chat.id)
    _save_chats(chats)
    await message.reply_text(
        "✅ <b>Guess Game ON</b>\n"
        "Har 5 min me rough image aayegi.\n"
        f"⏱ Sirf <b>1 minute</b> time\n"
        f"🏆 Pehla sahi → ${REWARD} coins",
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
    _clear_round(message.chat.id)
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


def _normalize(text: str) -> str:
    text = (text or "").strip().upper()
    return re.sub(r"[^A-Z0-9]", "", text)


@bot.on_message(
    filters.text & ~filters.private & ~filters.bot & ~filters.service,
    group=50,
)
async def guess_answer(client, message: Message):
    try:
        if not message.from_user or not message.text:
            return

        text = message.text.strip()
        if not text or text.startswith(("/", "!", ".")):
            return

        parts = text.split()
        if len(parts) != 1:
            return

        chat_id = message.chat.id
        active = _get_round(chat_id)
        if not active:
            return

        guess = _normalize(parts[0])
        word = _normalize(active.get("word") or "")
        if not word or not guess:
            return

        if active.get("solved") and not active.get("expired"):
            if guess == word:
                return await message.reply_text(
                    "🔒 <b>Already solved!</b>\nKoi aur user pehle sahi guess kar chuka hai.",
                    parse_mode=ParseMode.HTML,
                )
            return

        age = time.time() - float(active.get("ts") or 0)
        if active.get("expired") or age > GUESS_TIME:
            if not active.get("solved"):
                active["solved"] = True
                active["expired"] = True
                _set_round(chat_id, active)
            if guess == word:
                return await message.reply_text(
                    f"⏰ <b>Time's up!</b>\nWord tha: <b>{word}</b>",
                    parse_mode=ParseMode.HTML,
                )
            return

        if guess != word:
            return

        active["solved"] = True
        active["winner_id"] = message.from_user.id
        active["expired"] = False
        _set_round(chat_id, active)

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
            f"👛 Balance: <b>${u['coins']:,}</b>\n\n"
            f"🔒 Round locked — dusre users guess nahi kar sakte.\n"
            f"Check /bal",
            parse_mode=ParseMode.HTML,
        )
        print(f"[guessgame] WIN chat={chat_id} user={message.from_user.id}", flush=True)
    except Exception as e:
        print(f"[guessgame] answer error: {e}", flush=True)


print("[guessgame] plugin loaded OK", flush=True)
