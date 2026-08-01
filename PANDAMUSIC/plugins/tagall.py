# ---------------------------------------------------------------
# PANDAMUSIC — tagall.py
# /tagall <message> — mention all members with a message
# Admin / owner / sudo only
# ---------------------------------------------------------------

print("[tagall] loading plugin...", flush=True)

import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter, ParseMode
from pyrogram.types import Message

from .. import bot, console

# How many mentions per message (Telegram entity limit + rate safety)
BATCH_SIZE = 5
# Delay between batches (seconds)
BATCH_DELAY = 1.2


async def is_privileged(client, chat_id: int, user_id: int) -> bool:
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


def mention_html(user) -> str:
    name = (user.first_name or "User").replace("<", "").replace(">", "")
    if user.last_name:
        name = f"{name} {user.last_name}".replace("<", "").replace(">", "")
    # Keep short to avoid huge messages
    if len(name) > 20:
        name = name[:18] + ".."
    return f'<a href="tg://user?id={user.id}">{name}</a>'


async def _collect_members(client, chat_id: int):
    """Collect non-bot human members."""
    members = []
    try:
        async for member in client.get_chat_members(chat_id):
            user = member.user
            if not user:
                continue
            if user.is_bot:
                continue
            if user.is_deleted:
                continue
            members.append(user)
    except Exception as e:
        print(f"[tagall] get_chat_members error: {e}", flush=True)
        # Fallback: try SEARCH filter if available
        try:
            async for member in client.get_chat_members(
                chat_id, filter=ChatMembersFilter.SEARCH
            ):
                user = member.user
                if not user or user.is_bot or user.is_deleted:
                    continue
                members.append(user)
        except Exception as e2:
            print(f"[tagall] fallback members error: {e2}", flush=True)
    return members


@bot.on_message(
    filters.command(["tagall", "tag", "mentionall"], ["/", "!", "."])
    & ~filters.private
    & filters.incoming,
    group=0,
)
async def tagall_cmd(client, msg: Message):
    chat_id = msg.chat.id

    if not msg.from_user:
        return await msg.reply_text("❌ Anonymous admins cannot use this.")

    if not await is_privileged(client, chat_id, msg.from_user.id):
        return await msg.reply_text(
            "❌ Only <b>admins / owner / sudo</b> can use /tagall.",
            parse_mode=ParseMode.HTML,
        )

    # Message text: /tagall hi  OR  reply to a message + /tagall
    text = ""
    if msg.reply_to_message:
        text = (
            msg.reply_to_message.text
            or msg.reply_to_message.caption
            or ""
        ).strip()
    # Prefer explicit args after command
    args = msg.command or []
    if len(args) > 1:
        # Full original text after command word
        raw = msg.text or msg.caption or ""
        # Strip command prefix (/tagall, !tagall, .tagall)
        parts = raw.split(None, 1)
        if len(parts) > 1:
            text = parts[1].strip()

    if not text:
        return await msg.reply_text(
            "<b>Usage:</b>\n"
            "• <code>/tagall hi everyone</code>\n"
            "• Reply to a message with <code>/tagall</code>\n\n"
            "Bot will tag all members with your message.",
            parse_mode=ParseMode.HTML,
        )

    status = await msg.reply_text("🔄 Collecting members...")

    members = await _collect_members(client, chat_id)
    if not members:
        try:
            await status.edit_text(
                "❌ No members found.\n"
                "Bot needs to be admin to list members."
            )
        except Exception:
            pass
        return

    total = len(members)
    try:
        await status.edit_text(f"📣 Tagging <b>{total}</b> members...", parse_mode=ParseMode.HTML)
    except Exception:
        pass

    sent = 0
    failed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = members[i : i + BATCH_SIZE]
        mentions = " ".join(mention_html(u) for u in batch)
        body = f"{text}\n\n{mentions}"

        try:
            await client.send_message(
                chat_id,
                body,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            sent += len(batch)
        except Exception as e:
            failed += len(batch)
            print(f"[tagall] send batch error: {e}", flush=True)
            # Flood wait
            err = str(e).lower()
            if "flood" in err or "retry" in err:
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(1)

        if i + BATCH_SIZE < total:
            await asyncio.sleep(BATCH_DELAY)

    try:
        await status.edit_text(
            f"✅ <b>Tagall done!</b>\n\n"
            f"👥 Members: <b>{total}</b>\n"
            f"📣 Tagged: <b>{sent}</b>"
            + (f"\n⚠️ Failed: <b>{failed}</b>" if failed else ""),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

    # Auto-delete status after a while
    await asyncio.sleep(8)
    try:
        await status.delete()
    except Exception:
        pass


print("[tagall] plugin loaded OK", flush=True)
