# ---------------------------------------------------------------
# PANDAMUSIC — couple.py
# /couple — 2 random members ka DP couple template me
# Koi bhi group member use kar sakta hai
# ---------------------------------------------------------------

print("[couple] loading plugin...", flush=True)

import html
import io
import os
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.errors import ChatAdminRequired
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import bot, console

COUPLE_TEXTS = [
    "💘 ᴀᴀᴊ ᴋᴀ ᴄᴏᴜᴘʟᴇ ᴏꜰ ᴛʜᴇ ᴅᴀʏ",
    "💑 ɢʀᴏᴜᴘ ɴᴇ ᴄʜᴜɴ ʟɪʏᴀ ᴀᴀᴊ ᴋᴀ ᴊᴏᴅᴀ",
    "🌹 ᴅɪʟ ᴍɪʟᴀ ᴅɪʏᴀ ʙʀᴀʜᴍᴀɴᴅ ɴᴇ",
    "💝 ᴋɪꜱᴍᴀᴛ ɴᴇ ᴍɪʟᴀʏᴀ ᴛᴜᴍʜᴇ",
    "🔥 ʏᴇ ᴅᴏɴᴏ ʙᴀɴᴇ ʜᴀɪɴ ᴇᴋ ᴅᴜᴊᴇ ᴋᴇ ʟɪʏᴇ",
]

# Avatar size on the generated canvas
AVATAR_RADIUS = 180


def _load_font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "PANDAMUSIC/resource/font.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_circle_avatar(img_bytes: bytes, radius: int) -> Image.Image:
    size = radius * 2
    try:
        avatar = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    except Exception:
        return make_default_avatar(radius)
    w, h = avatar.size
    min_side = min(w, h)
    left = (w - min_side) // 2
    top = (h - min_side) // 2
    avatar = avatar.crop((left, top, left + min_side, top + min_side))
    avatar = avatar.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    avatar.putalpha(mask)
    return avatar


def make_default_avatar(radius: int) -> Image.Image:
    size = radius * 2
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    fill = Image.new("RGBA", (size, size), (80, 60, 90, 255))
    fill.putalpha(mask)
    img.paste(fill, (0, 0), fill)
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    head_r = size // 7
    draw.ellipse(
        [cx - head_r, cy - size // 3 - head_r, cx + head_r, cy - size // 3 + head_r],
        fill=(180, 160, 190, 255),
    )
    draw.ellipse(
        [cx - size // 4, cy - size // 10, cx + size // 4, cy + size // 3],
        fill=(180, 160, 190, 255),
    )
    return img


async def get_user_avatar(client, user_id: int, radius: int) -> Image.Image:
    tmp_path = f"/tmp/couple_dp_{user_id}.jpg"
    try:
        user = await client.get_users(user_id)
        if not user or not getattr(user, "photo", None):
            return make_default_avatar(radius)

        file_id = None
        try:
            file_id = user.photo.big_file_id
        except Exception:
            try:
                file_id = user.photo.small_file_id
            except Exception:
                pass

        if not file_id:
            return make_default_avatar(radius)

        saved = await client.download_media(file_id, file_name=tmp_path)
        read_path = saved if (saved and os.path.exists(saved)) else tmp_path
        if read_path and os.path.exists(read_path) and os.path.getsize(read_path) > 0:
            with open(read_path, "rb") as f:
                img_bytes = f.read()
            try:
                os.remove(read_path)
            except Exception:
                pass
            return make_circle_avatar(img_bytes, radius)
        return make_default_avatar(radius)
    except Exception as e:
        print(f"[couple] avatar error {user_id}: {e}", flush=True)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return make_default_avatar(radius)


def _draw_heart(draw, cx, cy, size, fill):
    """Simple heart shape at (cx, cy)."""
    r = size // 4
    # two circles + triangle-ish polygon
    draw.ellipse([cx - size // 2, cy - size // 3 - r // 2, cx, cy - size // 3 + r], fill=fill)
    draw.ellipse([cx, cy - size // 3 - r // 2, cx + size // 2, cy - size // 3 + r], fill=fill)
    draw.polygon(
        [
            (cx - size // 2, cy - size // 3 + r // 3),
            (cx + size // 2, cy - size // 3 + r // 3),
            (cx, cy + size // 2),
        ],
        fill=fill,
    )


def build_couple_image(avatar1: Image.Image, avatar2: Image.Image) -> io.BytesIO:
    """Build a romantic couple collage without external template."""
    W, H = 1080, 720

    # Gradient-ish background
    bg = Image.new("RGBA", (W, H), (30, 10, 40, 255))
    draw = ImageDraw.Draw(bg)

    # Soft color blobs
    for _ in range(8):
        x = random.randint(-100, W)
        y = random.randint(-100, H)
        r = random.randint(120, 280)
        color = random.choice(
            [
                (180, 40, 90, 40),
                (120, 30, 140, 35),
                (220, 80, 120, 30),
                (90, 20, 100, 40),
            ]
        )
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(overlay).ellipse([x, y, x + r, y + r], fill=color)
        bg = Image.alpha_composite(bg, overlay)

    bg = bg.filter(ImageFilter.GaussianBlur(18))
    draw = ImageDraw.Draw(bg)

    # Title bar
    font_title = _load_font(42)
    title = "Couple of the Day"
    try:
        bbox = draw.textbbox((0, 0), title, font=font_title)
        tw = bbox[2] - bbox[0]
    except Exception:
        tw = len(title) * 20
    draw.text(((W - tw) // 2, 40), title, font=font_title, fill=(255, 220, 230, 255))

    # Avatar positions
    left_cx, left_cy = W // 4, H // 2 + 20
    right_cx, right_cy = (3 * W) // 4, H // 2 + 20
    r = AVATAR_RADIUS

    # Glow rings
    for ring_r, alpha in ((r + 18, 60), (r + 10, 100)):
        for cx, cy in ((left_cx, left_cy), (right_cx, right_cy)):
            draw.ellipse(
                [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
                outline=(255, 120, 160, alpha),
                width=4,
            )

    # Paste avatars
    bg.paste(avatar1, (left_cx - r, left_cy - r), avatar1)
    bg.paste(avatar2, (right_cx - r, right_cy - r), avatar2)

    # Center heart
    _draw_heart(draw, W // 2, H // 2 + 10, 90, (255, 70, 110, 230))

    # Footer
    font_small = _load_font(24)
    footer = "P A N D A   M U S I C"
    try:
        bbox = draw.textbbox((0, 0), footer, font=font_small)
        fw = bbox[2] - bbox[0]
    except Exception:
        fw = len(footer) * 12
    draw.text(((W - fw) // 2, H - 55), footer, font=font_small, fill=(255, 200, 210, 200))

    out = io.BytesIO()
    bg.convert("RGB").save(out, format="JPEG", quality=92)
    out.name = "couple.jpg"
    out.seek(0)
    return out


@bot.on_message(
    filters.command(["couple", "couples", "ship"], ["/", "!", "."])
    & filters.group
    & filters.incoming,
    group=0,
)
async def couple_cmd(client, msg: Message):
    try:
        await msg.delete()
    except Exception:
        pass

    chat_id = msg.chat.id
    loading = await client.send_message(
        chat_id, "💞 ᴀᴀᴊ ᴋᴀ ᴄᴏᴜᴘʟᴇ ᴅʜᴜɴᴅʜ ʀᴀʜᴀ ʜᴜɴ..."
    )

    members = []
    try:
        async for member in client.get_chat_members(chat_id):
            u = member.user
            if u and not u.is_bot and not u.is_deleted:
                members.append(u)
    except ChatAdminRequired:
        try:
            await loading.delete()
        except Exception:
            pass
        return await client.send_message(
            chat_id,
            "❌ <b>Bot ko admin banao pehle!</b>\nMembers list ke liye admin rights chahiye.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        return await client.send_message(
            chat_id,
            f"❌ <b>Error:</b> <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML,
        )

    if len(members) < 2:
        try:
            await loading.delete()
        except Exception:
            pass
        return await client.send_message(
            chat_id,
            "❌ <b>Itne kam members hain? Couple kaise banega! 😂</b>",
            parse_mode=ParseMode.HTML,
        )

    p1, p2 = random.sample(members, 2)

    avatar1 = await get_user_avatar(client, p1.id, AVATAR_RADIUS)
    avatar2 = await get_user_avatar(client, p2.id, AVATAR_RADIUS)

    try:
        image_buf = build_couple_image(avatar1, avatar2)
    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        return await client.send_message(
            chat_id,
            f"❌ Image error: <code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML,
        )

    name1 = html.escape(p1.first_name or "User")
    name2 = html.escape(p2.first_name or "User")
    chemistry = random.randint(60, 100)
    header = random.choice(COUPLE_TEXTS)

    caption = (
        f"{header}\n\n"
        f"<a href='tg://user?id={p1.id}'>👦 {name1}</a>\n"
        f"        ❤️\n"
        f"<a href='tg://user?id={p2.id}'>👧 {name2}</a>\n\n"
        f"💫 ᴄʜᴇᴍɪsᴛʀʏ ➤ <b>{chemistry}%</b>\n"
        f"🌹 <i>ᴋɪsᴍᴀᴛ ɴᴇ ᴍɪʟᴀʏᴀ, ᴅɪʟ ɴᴇ ᴍᴀɴᴀʏᴀ</i>"
    )

    owner = getattr(console, "OWNER_USERNAME", "") or ""
    if owner:
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("👑 Owner", url=f"https://t.me/{owner}")]]
        )
    else:
        buttons = None

    try:
        await loading.delete()
    except Exception:
        pass

    await client.send_photo(
        chat_id,
        photo=image_buf,
        caption=caption,
        reply_markup=buttons,
        parse_mode=ParseMode.HTML,
    )


print("[couple] plugin loaded OK", flush=True)
