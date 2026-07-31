# ---------------------------------------------------------------
# PANDAMUSIC — locks.py
# Rose-style content locks | /lock /unlock /locks
# Admin / owner / sudo only
# ---------------------------------------------------------------

print("[locks] loading plugin...", flush=True)

import asyncio
import json
import os
import re

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, MessageEntityType, ParseMode
from pyrogram.types import Message

from .. import bot, console

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOCKS_DB = os.path.join(_BASE_DIR, "locks_db.json")

# Supported lock types (Rose-style)
LOCK_TYPES = {
    "all": "Everything",
    "url": "URLs / links",
    "photo": "Photos",
    "video": "Videos",
    "document": "Documents / files",
    "sticker": "Stickers",
    "gif": "GIFs / animations",
    "voice": "Voice messages",
    "videonote": "Video notes / circles",
    "audio": "Audio files",
    "contact": "Contacts",
    "location": "Locations",
    "poll": "Polls",
    "game": "Games",
    "forward": "Forwarded messages",
    "bot": "Bot messages",
    "command": "Bot commands",
    "text": "Plain text",
    "invitelink": "Invite links",
    "phone": "Phone numbers",
    "email": "Email addresses",
    "emoji": "Emoji-only messages",
    "media": "All media",
}

URL_RE = re.compile(
    r"(?i)\b(?:https?://|www\.|t\.me/|telegram\.me/)\S+",
)
INVITE_RE = re.compile(
    r"(?i)(?:t\.me/\+|t\.me/joinchat/|telegram\.me/joinchat/)\S+",
)
EMAIL_RE = re.compile(
    r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
)
PHONE_RE = re.compile(
    r"(?:\+|00)?\d[\d\s\-().]{7,}\d",
)
EMOJI_ONLY_RE = re.compile(
    r"^[\s"
    r"\U0001F300-\U0001F9FF"
    r"\U0001FA00-\U0001FAFF"
    r"\u2600-\u26FF"
    r"\u2700-\u27BF"
    r"\uFE0F"
    r"\u200D"
    r"]+$"
)


def _load() -> dict:
    try:
        if os.path.exists(_LOCKS_DB):
            with open(_LOCKS_DB, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save(data: dict):
    try:
        with open(_LOCKS_DB, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[locks] save error: {e}", flush=True)


def _key(chat_id: int) -> str:
    return str(chat_id)


def get_locks(chat_id: int) -> set:
    data = _load()
    return set(data.get(_key(chat_id), []))


def set_lock(chat_id: int, lock_type: str, enabled: bool):
    data = _load()
    k = _key(chat_id)
    locks = set(data.get(k, []))
    if enabled:
        locks.add(lock_type)
    else:
        locks.discard(lock_type)
    if locks:
        data[k] = sorted(locks)
    else:
        data.pop(k, None)
    _save(data)


def is_locked(chat_id: int, lock_type: str) -> bool:
    locks = get_locks(chat_id)
    return lock_type in locks or "all" in locks


async def is_privileged(client, chat_id: int, user_id: int) -> bool:
    """Owner, sudo, or group admin — exempt from locks."""
    try:
        if user_id and user_id == getattr(console, "OWNER_ID", 0):
            return True
        if user_id in getattr(console, "sudoers", []):
            return True
    except Exception:
        pass
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )
    except Exception:
        return False


async def _send(client, chat_id, text, reply_to=None):
    try:
        return await client.send_message(
            chat_id,
            text,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=reply_to,
        )
    except Exception:
        try:
            return await client.send_message(chat_id, text)
        except Exception:
            return None


def _has_url_entity(msg: Message) -> bool:
    ents = list(msg.entities or []) + list(msg.caption_entities or [])
    for e in ents:
        if e.type in (
            MessageEntityType.URL,
            MessageEntityType.TEXT_LINK,
        ):
            return True
    text = (msg.text or msg.caption or "")
    return bool(URL_RE.search(text))


def _has_invite(msg: Message) -> bool:
    text = (msg.text or msg.caption or "")
    if INVITE_RE.search(text):
        return True
    ents = list(msg.entities or []) + list(msg.caption_entities or [])
    for e in ents:
        if e.type == MessageEntityType.TEXT_LINK and e.url:
            if INVITE_RE.search(e.url):
                return True
        if e.type == MessageEntityType.URL and msg.text:
            url = msg.text[e.offset : e.offset + e.length]
            if INVITE_RE.search(url):
                return True
    return False


def _has_email(msg: Message) -> bool:
    text = (msg.text or msg.caption or "")
    if EMAIL_RE.search(text):
        return True
    ents = list(msg.entities or []) + list(msg.caption_entities or [])
    for e in ents:
        if e.type == MessageEntityType.EMAIL:
            return True
    return False


def _has_phone(msg: Message) -> bool:
    text = (msg.text or msg.caption or "")
    if PHONE_RE.search(text):
        return True
    ents = list(msg.entities or []) + list(msg.caption_entities or [])
    for e in ents:
        if e.type == MessageEntityType.PHONE_NUMBER:
            return True
    return False


def _is_emoji_only(msg: Message) -> bool:
    text = (msg.text or "").strip()
    if not text:
        return False
    # no other media
    if msg.media:
        return False
    return bool(EMOJI_ONLY_RE.match(text))


def detect_violations(msg: Message, locks: set) -> list:
    """Return list of lock types this message violates."""
    if not locks:
        return []

    hits = []
    check_all = "all" in locks

    def want(t):
        return check_all or t in locks

    # media category
    is_media = bool(
        msg.photo
        or msg.video
        or msg.document
        or msg.sticker
        or msg.animation
        or msg.voice
        or msg.video_note
        or msg.audio
    )

    if want("photo") and msg.photo:
        hits.append("photo")
    if want("video") and msg.video:
        hits.append("video")
    if want("document") and msg.document and not msg.animation:
        hits.append("document")
    if want("sticker") and msg.sticker:
        hits.append("sticker")
    if want("gif") and msg.animation:
        hits.append("gif")
    if want("voice") and msg.voice:
        hits.append("voice")
    if want("videonote") and msg.video_note:
        hits.append("videonote")
    if want("audio") and msg.audio:
        hits.append("audio")
    if want("contact") and msg.contact:
        hits.append("contact")
    if want("location") and (msg.location or msg.venue):
        hits.append("location")
    if want("poll") and msg.poll:
        hits.append("poll")
    if want("game") and msg.game:
        hits.append("game")
    if want("media") and is_media:
        hits.append("media")

    if want("forward") and (
        msg.forward_from
        or msg.forward_from_chat
        or msg.forward_sender_name
        or getattr(msg, "forward_date", None)
    ):
        hits.append("forward")

    if want("bot") and msg.from_user and msg.from_user.is_bot:
        hits.append("bot")

    text = (msg.text or "")
    if want("command") and text.startswith(("/", "!", ".")):
        hits.append("command")

    if want("text") and text and not msg.media:
        hits.append("text")

    if want("url") and _has_url_entity(msg):
        hits.append("url")
    if want("invitelink") and _has_invite(msg):
        hits.append("invitelink")
    if want("email") and _has_email(msg):
        hits.append("email")
    if want("phone") and _has_phone(msg):
        hits.append("phone")
    if want("emoji") and _is_emoji_only(msg):
        hits.append("emoji")

    # "all" already forces hits via want(); ensure at least one hit for pure text
    if check_all and not hits:
        hits.append("all")

    return hits


# ─────────────────── Commands ───────────────────

@bot.on_message(
    filters.command(["lock", "unlock", "locks"], ["/", "!", "."])
    & ~filters.private
    & filters.incoming,
    group=0,
)
async def locks_cmd(client, msg: Message):
    chat_id = msg.chat.id
    cmd = (msg.command[0] if msg.command else "").lower()

    try:
        await msg.delete()
    except Exception:
        pass

    if not msg.from_user:
        return await _send(client, chat_id, "❌ Anonymous admins cannot use this.")

    if not await is_privileged(client, chat_id, msg.from_user.id):
        return await _send(
            client, chat_id, "❌ Only <b>admins / owner / sudo</b> can manage locks."
        )

    args = msg.command or []

    # /locks — list current locks
    if cmd == "locks":
        current = get_locks(chat_id)
        if not current:
            return await _send(
                client,
                chat_id,
                "🔓 <b>No locks active in this chat.</b>\n\n"
                "Use <code>/lock url</code> to lock something.\n"
                f"Types: <code>{', '.join(sorted(LOCK_TYPES.keys()))}</code>",
            )
        lines = [f"• <code>{t}</code> — {LOCK_TYPES.get(t, t)}" for t in sorted(current)]
        return await _send(
            client,
            chat_id,
            "🔒 <b>Active locks:</b>\n\n" + "\n".join(lines),
        )

    # /lock or /unlock need a type
    if len(args) < 2:
        types_list = ", ".join(sorted(LOCK_TYPES.keys()))
        return await _send(
            client,
            chat_id,
            f"<b>Usage:</b>\n"
            f"• <code>/{cmd} url</code>\n"
            f"• <code>/{cmd} photo</code>\n"
            f"• <code>/locks</code> — show active locks\n\n"
            f"<b>Types:</b>\n<code>{types_list}</code>",
        )

    lock_type = args[1].lower().strip()

    # aliases
    aliases = {
        "links": "url",
        "link": "url",
        "urls": "url",
        "pics": "photo",
        "pictures": "photo",
        "videos": "video",
        "docs": "document",
        "file": "document",
        "files": "document",
        "stickers": "sticker",
        "animation": "gif",
        "animations": "gif",
        "gifs": "gif",
        "voices": "voice",
        "circle": "videonote",
        "circles": "videonote",
        "video_note": "videonote",
        "video-note": "videonote",
        "audios": "audio",
        "contacts": "contact",
        "locations": "location",
        "polls": "poll",
        "games": "game",
        "forwards": "forward",
        "fwd": "forward",
        "bots": "bot",
        "cmds": "command",
        "commands": "command",
        "invite": "invitelink",
        "invitelinks": "invitelink",
        "phones": "phone",
        "emails": "email",
        "emojis": "emoji",
    }
    lock_type = aliases.get(lock_type, lock_type)

    if lock_type not in LOCK_TYPES:
        return await _send(
            client,
            chat_id,
            f"❌ Unknown lock type: <code>{lock_type}</code>\n\n"
            f"Valid: <code>{', '.join(sorted(LOCK_TYPES.keys()))}</code>",
        )

    if cmd == "lock":
        set_lock(chat_id, lock_type, True)
        return await _send(
            client,
            chat_id,
            f"🔒 Locked <b>{LOCK_TYPES[lock_type]}</b> (<code>{lock_type}</code>)\n\n"
            f"Non-admin messages of this type will be deleted.",
        )
    else:
        set_lock(chat_id, lock_type, False)
        return await _send(
            client,
            chat_id,
            f"🔓 Unlocked <b>{LOCK_TYPES[lock_type]}</b> (<code>{lock_type}</code>)",
        )


# ─────────────────── Watcher ───────────────────

@bot.on_message(filters.group & filters.incoming, group=-2)
async def locks_watcher(client, msg: Message):
    # skip service messages without a real sender
    if not msg.from_user and not msg.sender_chat:
        return

    chat_id = msg.chat.id
    locks = get_locks(chat_id)
    if not locks:
        return

    # never lock our own bot
    try:
        if msg.from_user and msg.from_user.id == client.me.id:
            return
    except Exception:
        pass

    # admins / owner / sudo exempt
    uid = msg.from_user.id if msg.from_user else None
    if uid and await is_privileged(client, chat_id, uid):
        return

    # channel posts in discussion — still apply if not privileged
    hits = detect_violations(msg, locks)
    if not hits:
        return

    try:
        await msg.delete()
    except Exception as e:
        print(f"[locks] delete failed chat={chat_id}: {e}", flush=True)
        return

    # short warning (auto-delete)
    try:
        who = msg.from_user.mention if msg.from_user else "User"
        types = ", ".join(f"<code>{h}</code>" for h in hits[:3])
        warn = await client.send_message(
            chat_id,
            f"🔒 {who}, this content is locked ({types}).",
            parse_mode=ParseMode.HTML,
        )
        await asyncio.sleep(4)
        await warn.delete()
    except Exception:
        pass


print("[locks] plugin loaded OK", flush=True)
