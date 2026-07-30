# ---------------------------------------------------------------
# PANDAMUSIC — moderation.py
# /mute /unmute /ban /unban /kick
# ---------------------------------------------------------------

print("[moderation] loading plugin...", flush=True)

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import Message, ChatPermissions

from .. import bot


async def is_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        from .. import console

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
    except Exception as e:
        print(f"[moderation] is_admin error: {e}", flush=True)
        return False


async def get_target(client, msg: Message):
    if msg.reply_to_message and msg.reply_to_message.from_user:
        reason = None
        parts = (msg.text or "").split(None, 1)
        if len(parts) > 1:
            reason = parts[1].strip()
        return msg.reply_to_message.from_user, reason

    cmd = msg.command or []
    if len(cmd) > 1:
        try:
            user = await client.get_users(cmd[1])
            reason = None
            parts = (msg.text or "").split(None, 2)
            if len(parts) > 2:
                reason = parts[2].strip()
            return user, reason
        except Exception as e:
            print(f"[moderation] get_users error: {e}", flush=True)
    return None, None


def tag(u):
    name = (u.first_name or "User").replace("<", "").replace(">", "")
    return f'<a href="tg://user?id={u.id}">{name}</a>'


async def send(client, chat_id, text, reply_to=None):
    try:
        return await client.send_message(
            chat_id,
            text,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=reply_to,
        )
    except Exception as e1:
        print(f"[moderation] send error1: {e1}", flush=True)
        try:
            return await client.send_message(chat_id, text)
        except Exception as e2:
            print(f"[moderation] send error2: {e2}", flush=True)


def mute_perms():
    try:
        return ChatPermissions(all_perms=False)
    except Exception:
        try:
            return ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            )
        except Exception:
            return ChatPermissions(can_send_messages=False)


def unmute_perms():
    try:
        return ChatPermissions(all_perms=True)
    except Exception:
        try:
            return ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
        except Exception:
            return ChatPermissions(can_send_messages=True)


@bot.on_message(
    filters.command(["mute", "unmute", "ban", "unban", "kick"], ["/", "!", "."])
    & ~filters.private
    & filters.incoming,
    group=0,
)
async def moderation_cmds(client, msg: Message):
    cmd = (msg.command[0] if msg.command else "").lower()
    chat_id = msg.chat.id
    reply_to = msg.reply_to_message.id if msg.reply_to_message else None

    print(f"[moderation] CMD /{cmd} in {chat_id} from {getattr(msg.from_user, 'id', None)}", flush=True)

    try:
        await msg.delete()
    except Exception:
        pass

    if not msg.from_user:
        return await send(client, chat_id, "❌ Anonymous admins cannot use this.")

    if not await is_admin(client, chat_id, msg.from_user.id):
        return await send(client, chat_id, "❌ Only group admins can use this command.", reply_to)

    target, reason = await get_target(client, msg)
    if not target:
        return await send(
            client,
            chat_id,
            f"❌ Reply to a user message or use:\n<code>/{cmd} @username reason</code>",
            reply_to,
        )

    if target.id == msg.from_user.id and cmd in ("mute", "ban", "kick"):
        return await send(client, chat_id, f"❌ You cannot {cmd} yourself.", reply_to)

    reason_line = f"\n📋 Reason: {reason}" if reason else ""

    try:
        if cmd == "mute":
            await client.restrict_chat_member(chat_id, target.id, mute_perms())
            await send(
                client,
                chat_id,
                f"🔇 {tag(target)} has been muted!\n👮 By: {tag(msg.from_user)}{reason_line}",
                reply_to,
            )

        elif cmd == "unmute":
            await client.restrict_chat_member(chat_id, target.id, unmute_perms())
            await send(
                client,
                chat_id,
                f"🔊 {tag(target)} has been unmuted!\n👮 By: {tag(msg.from_user)}{reason_line}",
                reply_to,
            )

        elif cmd == "ban":
            await client.ban_chat_member(chat_id, target.id)
            await send(
                client,
                chat_id,
                f"🚫 {tag(target)} has been banned!\n👮 By: {tag(msg.from_user)}{reason_line}",
                reply_to,
            )

        elif cmd == "unban":
            await client.unban_chat_member(chat_id, target.id)
            await send(
                client,
                chat_id,
                f"✅ {tag(target)} has been unbanned!\n👮 By: {tag(msg.from_user)}{reason_line}",
                reply_to,
            )

        elif cmd == "kick":
            await client.ban_chat_member(chat_id, target.id)
            await client.unban_chat_member(chat_id, target.id)
            await send(
                client,
                chat_id,
                f"👟 {tag(target)} has been kicked!\n👮 By: {tag(msg.from_user)}{reason_line}",
                reply_to,
            )

    except Exception as e:
        print(f"[moderation] action error: {e}", flush=True)
        err = str(e)
        if "CHAT_ADMIN_REQUIRED" in err.upper() or "right" in err.lower():
            await send(
                client,
                chat_id,
                "❌ Bot must be admin with Ban/Restrict permission!",
                reply_to,
            )
        elif "USER_ADMIN" in err.upper() or "can't" in err.lower():
            await send(client, chat_id, f"❌ Cannot {cmd} an admin!", reply_to)
        else:
            await send(
                client,
                chat_id,
                f"❌ Error: <code>{type(e).__name__}: {e}</code>",
                reply_to,
            )


print("[moderation] plugin loaded OK", flush=True)
