import aiofiles, aiohttp, base64, json, os, random, re, requests

from .. import app, bot, call, cdz, console
from urllib.parse import urlparse
from io import BytesIO
import asyncio
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ntgcalls import TelegramServerError
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import MediaStream, ExternalMedia
from pytgcalls.types import AudioQuality, VideoQuality
from youtubesearchpython.__future__ import VideosSearch

from ..modules.formatters import panel_caption, queue_caption
from .maintenance import block_if_maintenance

import tempfile
import os


def parse_query(query: str) -> str:
    if bool(re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/(?:watch\?v=|embed/|v/|shorts/|live/)?([A-Za-z0-9_-]{11})(?:[?&].*)?$', query)):
        match = re.search(r'(?:v=|/(?:embed|v|shorts|live)/|youtu\.be/)([A-Za-z0-9_-]{11})', query)
        if match:
            return f"https://www.youtube.com/watch?v={match.group(1)}"

    return query


def parse_tg_link(link: str):
    parsed = urlparse(link)
    path = parsed.path.strip('/')
    parts = path.split('/')

    if len(parts) >= 2:
        return str(parts[0]), int(parts[1])

    return None, None


async def fetch_song(query: str):
    try:
        search = VideosSearch(query, limit=1)
        result = (await search.next()).get("result", [])

        if not result:
            return {"error": "No video found"}

        vidid = result[0].get("id")
        if not vidid:
            return {"error": "Failed to get video ID"}

        url = "http://46.250.243.52:1470/song"
        params = {"query": vidid}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    try:
                        return await response.json()
                    except Exception:
                        return {"error": "Invalid JSON response"}
                else:
                    return {"error": f"API returned status {response.status}"}

    except Exception as e:
        return {"error": str(e)}


def convert_to_seconds(duration: str) -> int:
    try:
        parts = list(map(int, str(duration).split(":")))
        total = 0
        multiplier = 1
        for value in reversed(parts):
            total += value * multiplier
            multiplier *= 60
        return total
    except Exception:
        return 0


def format_duration(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    sec = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if sec > 0 or not parts:
        parts.append(f"{sec}s")

    return " ".join(parts)


def seconds_to_hhmmss(seconds):
    if seconds < 3600:
        minutes = seconds // 60
        sec = seconds % 60
        return f"{minutes:02}:{sec:02}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        sec = seconds % 60
        return f"{hours:d}:{minutes:02}:{sec:02}"


def random_color():
    return (random.randint(80, 255), random.randint(80, 255), random.randint(80, 255))


def trim_text(draw, text, font, max_width):
    if not text:
        return ""
    original = text
    while True:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            break
        text = text[:-1]
    if text != original:
        while True:
            bbox = draw.textbbox((0, 0), text + "...", font=font)
            if bbox[2] - bbox[0] <= max_width or len(text) == 0:
                break
            text = text[:-1]
        text = text + "..."
    return text


async def create_music_thumbnail(cover_path, title, artist, duration_seconds=None, output_path="thumbnail.png"):
    if not title or title.strip() == "":
        title = "Unknown Title"
    if not artist or artist.strip() == "":
        artist = "Unknown Artist"

    if (
        duration_seconds is None
        or duration_seconds == 0
        or duration_seconds == "live"
    ):
        total_time = "Live"
        tot_sec = None
    else:
        tot_sec = duration_seconds
        total_time = seconds_to_hhmmss(duration_seconds)

    if tot_sec:
        cur_sec = random.randint(0, tot_sec)
        current_time = seconds_to_hhmmss(cur_sec)
    else:
        cur_sec = random.randint(0, 7200)
        current_time = seconds_to_hhmmss(cur_sec)

    cover = Image.open(cover_path).convert("RGBA").resize((500, 500))
    bg = cover.copy().resize((1280, 720))
    bg = bg.filter(ImageFilter.GaussianBlur(25))

    grad_overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad_overlay)
    c1, c2 = random_color(), random_color()
    for i in range(bg.height):
        r = int(c1[0] + (c2[0]-c1[0]) * (i/bg.height))
        g = int(c1[1] + (c2[1]-c1[1]) * (i/bg.height))
        b = int(c1[2] + (c2[2]-c1[2]) * (i/bg.height))
        gdraw.line([(0, i), (bg.width, i)], fill=(r, g, b, 80))
    bg = Image.alpha_composite(bg, grad_overlay)

    card_w, card_h = 700, 380
    border_thickness = 5

    grad = Image.new("RGBA", (card_w + border_thickness*2, card_h + border_thickness*2), (0,0,0,0))
    gdraw = ImageDraw.Draw(grad)
    c1, c2 = random_color(), random_color()
    for i in range(grad.height):
        r = int(c1[0] + (c2[0]-c1[0]) * (i/grad.height))
        g = int(c1[1] + (c2[1]-c1[1]) * (i/grad.height))
        b = int(c1[2] + (c2[2]-c1[2]) * (i/grad.height))
        gdraw.line([(0, i), (grad.width, i)], fill=(r, g, b))

    mask_outer = Image.new("L", grad.size, 0)
    mask_inner = Image.new("L", (card_w, card_h), 0)
    d_outer = ImageDraw.Draw(mask_outer)
    d_inner = ImageDraw.Draw(mask_inner)

    d_outer.rounded_rectangle([0, 0, grad.width, grad.height], 36, fill=255)
    d_inner.rounded_rectangle([0, 0, card_w, card_h], 30, fill=255)

    mask_inner_padded = Image.new("L", grad.size, 0)
    mask_inner_padded.paste(mask_inner, (border_thickness, border_thickness))
    mask_outer.paste(0, (0,0), mask_inner_padded)

    border = Image.composite(grad, Image.new("RGBA", grad.size, (0,0,0,0)), mask_outer)

    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 60))
    mask_card = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask_card).rounded_rectangle([0,0,card_w,card_h], 30, fill=255)

    card_with_border = border.copy()
    card_with_border.paste(card, (border_thickness, border_thickness), mask_card)

    x = (bg.width - card_with_border.width) // 2
    y = (bg.height - card_with_border.height) // 2
    bg.paste(card_with_border, (x,y), card_with_border)

    cover_size = 200
    border_size = 6

    grad_cover = Image.new("RGBA", (cover_size + border_size*2, cover_size + border_size*2), (0,0,0,0))
    gdraw = ImageDraw.Draw(grad_cover)
    c1, c2 = random_color(), random_color()
    for i in range(grad_cover.height):
        r = int(c1[0] + (c2[0]-c1[0]) * (i/grad_cover.height))
        g = int(c1[1] + (c2[1]-c1[1]) * (i/grad_cover.height))
        b = int(c1[2] + (c2[2]-c1[2]) * (i/grad_cover.height))
        gdraw.line([(0, i), (grad_cover.width, i)], fill=(r, g, b))

    mask_outer = Image.new("L", grad_cover.size, 0)
    mask_inner = Image.new("L", (cover_size, cover_size), 0)
    d_outer = ImageDraw.Draw(mask_outer)
    d_inner = ImageDraw.Draw(mask_inner)

    d_outer.rounded_rectangle([0,0,grad_cover.width,grad_cover.height], 30, fill=255)
    d_inner.rounded_rectangle([0,0,cover_size,cover_size], 26, fill=255)

    mask_inner_padded = Image.new("L", grad_cover.size, 0)
    mask_inner_padded.paste(mask_inner, (border_size, border_size))
    mask_outer.paste(0, (0,0), mask_inner_padded)

    border_cover = Image.composite(grad_cover, Image.new("RGBA", grad_cover.size, (0,0,0,0)), mask_outer)

    cover_resized = cover.resize((cover_size, cover_size))
    mask_cover = Image.new("L", (cover_size, cover_size), 0)
    ImageDraw.Draw(mask_cover).rounded_rectangle([0,0,cover_size,cover_size], 26, fill=255)

    cover_with_border = border_cover.copy()
    cover_with_border.paste(cover_resized, (border_size, border_size), mask_cover)

    cover_x = x + border_thickness + 30
    cover_y = y + (card_h - cover_with_border.height)//2 + border_thickness
    bg.paste(cover_with_border, (cover_x, cover_y), cover_with_border)

    draw = ImageDraw.Draw(bg)
    font_path = "PANDAMUSIC/resource/font.ttf"
    try:
        font_title = ImageFont.truetype(font_path, 36)
        font_artist = ImageFont.truetype(font_path, 28)
        font_time = ImageFont.truetype(font_path, 24)
    except Exception:
        font_title = ImageFont.load_default()
        font_artist = ImageFont.load_default()
        font_time = ImageFont.load_default()

    max_width = card_w - 300
    title = trim_text(draw, title, font_title, max_width)
    artist = trim_text(draw, artist, font_artist, max_width)

    text_x = cover_x + cover_with_border.width + 30
    draw.text((text_x, y + 86), title, font=font_title, fill="white")
    draw.text((text_x, y + 146), artist, font=font_artist, fill="white")

    progress_x, progress_y = text_x, y + 206
    bar_w, bar_h = 380, 8
    prog_fill = int((cur_sec / tot_sec) * bar_w) if tot_sec else bar_w

    draw.rounded_rectangle([progress_x, progress_y, progress_x + bar_w, progress_y + bar_h],
                           5, fill=(120, 120, 120, 160))

    c1, c2 = random_color(), random_color()
    for i in range(prog_fill):
        r = int(c1[0] + (c2[0]-c1[0]) * (i/max(1, prog_fill)))
        g = int(c1[1] + (c2[1]-c1[1]) * (i/max(1, prog_fill)))
        b = int(c1[2] + (c2[2]-c1[2]) * (i/max(1, prog_fill)))
        draw.line([(progress_x + i, progress_y), (progress_x + i, progress_y + bar_h)], fill=(r,g,b))

    knob_x = progress_x + prog_fill
    knob_y = progress_y + bar_h // 2
    draw.ellipse([knob_x - 6, knob_y - 6, knob_x + 6, knob_y + 6], fill="white", outline="black", width=2)

    draw.text((progress_x, progress_y + 15), current_time, font=font_time, fill="white")
    total_bbox = draw.textbbox((0, 0), total_time, font=font_time)
    total_x = progress_x + bar_w - (total_bbox[2] - total_bbox[0])
    draw.text((total_x, progress_y + 15), total_time, font=font_time, fill="red" if total_time == "Live" else "white")

    controls_y = progress_y + 70
    num_icons = 7
    step = bar_w // (num_icons - 1)
    icon_positions = [progress_x + i*step for i in range(num_icons)]

    shuffle_x = icon_positions[0]
    draw.line([(shuffle_x-12, controls_y-8), (shuffle_x+8, controls_y+12)], fill=(0,255,120), width=3)
    draw.polygon([(shuffle_x+8, controls_y+12), (shuffle_x+16, controls_y+6), (shuffle_x+2, controls_y+4)], fill=(0,255,120))
    draw.line([(shuffle_x-12, controls_y+8), (shuffle_x-2, controls_y-2)], fill=(0,255,120), width=3)

    repeat_x = icon_positions[1]
    repeat_color = (255, 220, 50)
    draw.arc([repeat_x-14, controls_y-12, repeat_x+14, controls_y+12], start=30, end=300, fill=repeat_color, width=3)
    draw.polygon([(repeat_x+14, controls_y-2), (repeat_x+22, controls_y-6), (repeat_x+14, controls_y-10)], fill=repeat_color)

    sbx = icon_positions[2]
    draw.polygon([(sbx+10, controls_y-10), (sbx+10, controls_y+10), (sbx-12, controls_y)], fill="white")
    draw.rectangle([sbx+14, controls_y-10, sbx+18, controls_y+10], fill="white")

    center_x = icon_positions[3]
    bar_wid, bar_height = 6, 26
    gap = 10
    draw.rectangle([center_x-gap-bar_wid, controls_y-bar_height//2, center_x-gap, controls_y+bar_height//2], fill="white")
    draw.rectangle([center_x+gap, controls_y-bar_height//2, center_x+gap+bar_wid, controls_y+bar_height//2], fill="white")

    sfx = icon_positions[4]
    draw.polygon([(sfx-10, controls_y-10), (sfx-10, controls_y+10), (sfx+12, controls_y)], fill="white")
    draw.rectangle([sfx-18, controls_y-10, sfx-14, controls_y+10], fill="white")

    fav_x = icon_positions[5]
    heart = [(fav_x, controls_y), (fav_x-10, controls_y-10), (fav_x-20, controls_y), (fav_x, controls_y+14),
             (fav_x+20, controls_y), (fav_x+10, controls_y-10)]
    draw.polygon(heart, fill="red")

    ear_x = icon_positions[6]
    draw.arc([ear_x-20, controls_y-20, ear_x+20, controls_y+20], start=200, end=-20, fill="white", width=3)
    draw.rectangle([ear_x-18, controls_y-4, ear_x-10, controls_y+12], fill="white")
    draw.rectangle([ear_x+10, controls_y-4, ear_x+18, controls_y+12], fill="white")

    bg.save(output_path)
    return output_path


async def generate_thumbnail(url: str) -> str:
    try:
        filename = os.path.join("cache", f"thumbnail_{hash(url)}.jpg")
        parsed = urlparse(url)

        if parsed.scheme in ("http", "https"):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return ""
                    data = await resp.read()

                    with Image.open(BytesIO(data)) as img:
                        img = img.resize((1280, 720))
                        buf = BytesIO()
                        img.save(buf, format="JPEG", quality=90)
                        buf.seek(0)

                        async with aiofiles.open(filename, "wb") as f:
                            await f.write(buf.read())

        else:
            if not os.path.isfile(url):
                return "PANDAMUSIC/resource/thumbnail.png"

            with Image.open(url) as img:
                img = img.resize((1280, 720))
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=90)
                buf.seek(0)

                async with aiofiles.open(filename, "wb") as f:
                    await f.write(buf.read())

        return filename

    except Exception:
        return "PANDAMUSIC/resource/thumbnail.png"


async def make_thumbnail(image, title, channel, duration, output):
    return await create_music_thumbnail(image, title, channel, duration, output)


@bot.on_message(cdz(["play", "vplay"]) & ~filters.private)
async def start_stream_in_vc(client, message):
    if await block_if_maintenance(message):
        return

    import traceback
    import time
    from pytgcalls.types import MediaStream, AudioQuality
    from ..platforms import Youtube
    from .callbacks import player_markup, queue_markup, start_progress_task

    chat_id = message.chat.id
    mention = message.from_user.mention if message.from_user else "User"
    is_video = message.command[0] == "vplay"

    try:
        await message.delete()
    except Exception:
        pass

    if len(message.command) < 2:
        return await message.reply_text(f"Usage: /{message.command[0]} <song name>")

    query = " ".join(message.command[1:])
    aux = await message.reply_text("Searching...")

    try:
        info = await Youtube.search(query)
    except Exception as e:
        return await aux.edit(f"Search error: {e}")

    if not info:
        return await aux.edit("Song not found.")

    await aux.edit(f"Downloading {info['title']}...")

    try:
        if is_video:
            file_path = await Youtube.download_video(info["vidid"])
        else:
            file_path = await Youtube.download_song(info["vidid"])
    except Exception as e:
        return await aux.edit(f"Download error: {e}")

    if not file_path:
        return await aux.edit("Download failed - API se file nahi mili.")

    try:
        media_stream = MediaStream(
            media_path=file_path,
            audio_parameters=AudioQuality.HIGH,
            video_flags=(
                MediaStream.Flags.AUTO_DETECT if is_video else MediaStream.Flags.IGNORE
            ),
        )
    except Exception as e:
        return await aux.edit(f"MediaStream error: {e}")

    already_playing = bool(call.queue.get(chat_id)) or (
        chat_id in getattr(call, "active_chats", [])
    )

    if already_playing:
        try:
            pos = await call.add_to_queue(
                chat_id,
                media_stream,
                info["title"],
                info.get("duration_min", "0:00"),
                info.get("thumbnail", ""),
                mention,
            )
            text = queue_caption(
                pos,
                info["title"],
                info.get("duration_min", "0:00"),
                mention,
            )
            buttons = queue_markup(chat_id, pos)
            await aux.edit(text, reply_markup=buttons, parse_mode=ParseMode.HTML)
        except Exception as e:
            await aux.edit(f"Queue error: {e}")
        return

    await aux.edit("Starting Voice Chat stream...")

    try:
        call.queue[chat_id] = []
        await call.add_to_queue(
            chat_id,
            media_stream,
            info["title"],
            info.get("duration_min", "0:00"),
            info.get("thumbnail", ""),
            mention,
        )
        if not hasattr(call, "start_times"):
            call.start_times = {}
        call.start_times[chat_id] = time.time()
        try:
            await call.stream_on(chat_id)
        except Exception:
            call.paused[chat_id] = False

        await call.start_stream(chat_id, media_stream)
    except Exception as e:
        tb = traceback.format_exc()
        return await aux.edit(f"Failed to start stream: {e}\n\n{tb[-500:]}")

    try:
        thumb = await generate_thumbnail(info["thumbnail"])
        caption = panel_caption(
            info["title"],
            info.get("duration_min", "0:00"),
            mention,
            header="sᴛʀᴇᴀᴍɪɴɢ ɪɴ ᴠᴄ",
        )
        total_sec = convert_to_seconds(info.get("duration_min", "0:00"))
        buttons = player_markup(chat_id, 0, total_sec)
        await aux.delete()
        if thumb:
            panel = await message.reply_photo(
                photo=thumb,
                caption=caption,
                reply_markup=buttons,
                parse_mode=ParseMode.HTML,
            )
        else:
            panel = await message.reply_text(
                caption,
                reply_markup=buttons,
                parse_mode=ParseMode.HTML,
            )
        if chat_id in call.queue and call.queue[chat_id]:
            call.queue[chat_id][0]["panel"] = panel
            call.queue[chat_id][0]["played"] = 0
        start_progress_task(chat_id)
    except Exception as e:
        print(f"[PANEL ERROR] {e}", flush=True)
