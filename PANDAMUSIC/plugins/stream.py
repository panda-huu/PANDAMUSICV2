import aiofiles
import aiohttp
import asyncio
import os
import random
import re
import shutil
import subprocess
import time
from io import BytesIO
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from pyrogram import filters
from pyrogram.enums import ParseMode

from youtubesearchpython.__future__ import VideosSearch

from .. import bot, call, cdz
from ..modules.formatters import panel_caption, queue_caption
from .maintenance import block_if_maintenance

CACHE_DIR = "cache"
FONT_PATH = "PANDAMUSIC/resource/font.ttf"
FALLBACK_THUMB = "PANDAMUSIC/resource/thumbnail.png"

POWERED_LINE_1 = "ᴘᴏᴡᴇʀᴇᴅ ʙʏ : ᴘᴀɴᴅᴀ-ʙᴀʙʏ"
POWERED_LINE_2 = "ʏᴛ ᴍᴜsɪᴄ ᴀᴘɪ ᴘᴏᴡᴇʀᴇᴅ ʙʏ : ᴀʀᴜʏᴛ ᴀᴘɪ"


def parse_query(query: str) -> str:
    if bool(
        re.match(
            r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/(?:watch\?v=|embed/|v/|shorts/|live/)?([A-Za-z0-9_-]{11})(?:[?&].*)?$",
            query,
        )
    ):
        match = re.search(
            r"(?:v=|/(?:embed|v|shorts|live)/|youtu\.be/)([A-Za-z0-9_-]{11})", query
        )
        if match:
            return f"https://www.youtube.com/watch?v={match.group(1)}"
    return query


def parse_tg_link(link: str):
    parsed = urlparse(link)
    path = parsed.path.strip("/")
    parts = path.split("/")
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


def seconds_to_hhmmss(seconds):
    seconds = max(0, int(seconds or 0))
    if seconds < 3600:
        minutes = seconds // 60
        sec = seconds % 60
        return f"{minutes}:{sec:02d}"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    sec = seconds % 60
    return f"{hours}:{minutes:02d}:{sec:02d}"


def file_has_video(path: str, retries: int = 2, delay: float = 0.5) -> bool:
    """Check if file contains a video stream via ffprobe.

    Youtube.download_video() already validates this internally before
    returning a path, so this is a safety-net re-check. Retries once so a
    transient ffprobe hiccup (subprocess spawn, momentary CPU load on the
    host) doesn't produce a false "no video" on a file that's actually fine.
    """
    if shutil.which("ffprobe") is None:
        print("[ffprobe video check] ffprobe binary not found on PATH", flush=True)
        return False

    last_err = None
    for attempt in range(retries):
        try:
            out = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_type",
                    "-of",
                    "csv=p=0",
                    path,
                ],
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
            if b"video" in out.lower():
                return True
            last_err = "no video stream reported"
        except Exception as e:
            last_err = e
        if attempt < retries - 1:
            time.sleep(delay)

    print(f"[ffprobe video check] failed after {retries} attempt(s): {last_err}", flush=True)
    return False


def _load_font(size: int):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


def trim_text(draw, text, font, max_width):
    if not text:
        return ""
    original = str(text)
    text = original
    while True:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            break
        if len(text) <= 1:
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


def _rounded_cover(cover: Image.Image, size: int, radius: int = 28) -> Image.Image:
    cover = cover.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=radius, fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(cover, (0, 0), mask)
    return out


def _draw_center_text(draw, text, y, font, fill, canvas_w):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (canvas_w - w) // 2
    draw.text((x, y), text, font=font, fill=fill)


async def create_music_thumbnail(
    cover_path,
    title,
    artist,
    duration_seconds=None,
    output_path="thumbnail.png",
):
    title = (title or "Unknown Title").strip() or "Unknown Title"
    artist = (artist or "Unknown Artist").strip() or "Unknown Artist"

    if duration_seconds is None or duration_seconds == 0 or duration_seconds == "live":
        tot_sec = 0
        cur_sec = 0
        current_time = "0:00"
        remain_time = "Live"
    else:
        tot_sec = int(duration_seconds)
        cur_sec = max(1, min(tot_sec // 20, 12)) if tot_sec else 0
        current_time = seconds_to_hhmmss(cur_sec)
        remain_time = f"-{seconds_to_hhmmss(max(0, tot_sec - cur_sec))}"

    W, H = 1280, 720

    try:
        cover_src = Image.open(cover_path).convert("RGBA")
    except Exception:
        cover_src = Image.new("RGBA", (500, 500), (30, 30, 40, 255))

    bg = cover_src.copy().resize((W, H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 160))
    bg = Image.alpha_composite(bg, dark)

    draw = ImageDraw.Draw(bg)

    font_title = _load_font(36)
    font_artist = _load_font(26)
    font_time = _load_font(22)
    font_power = _load_font(24)
    font_power2 = _load_font(20)

    cover_size = 420
    cover_x = 80
    cover_y = (H - cover_size) // 2 - 20
    cover_img = _rounded_cover(cover_src, cover_size, radius=32)
    bg.paste(cover_img, (cover_x, cover_y), cover_img)

    right_x = cover_x + cover_size + 70
    right_w = W - right_x - 80

    title_draw = trim_text(draw, title, font_title, right_w - 20)
    artist_draw = trim_text(draw, artist, font_artist, right_w - 20)
    title_y = cover_y + 40
    draw.text((right_x, title_y), title_draw, font=font_title, fill=(255, 255, 255, 255))
    draw.text(
        (right_x, title_y + 52),
        artist_draw,
        font=font_artist,
        fill=(200, 200, 210, 255),
    )

    bar_x = right_x
    bar_y = title_y + 130
    bar_w = right_w
    bar_h = 8
    ratio = (cur_sec / tot_sec) if tot_sec else 0.05
    fill_w = max(6, int(bar_w * min(ratio, 1.0)))

    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
        radius=4,
        fill=(255, 255, 255, 55),
    )
    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
        radius=4,
        fill=(255, 255, 255, 230),
    )
    kx = bar_x + fill_w
    ky = bar_y + bar_h // 2
    draw.ellipse([kx - 8, ky - 8, kx + 8, ky + 8], fill=(255, 255, 255, 255))

    draw.text((bar_x, bar_y + 18), current_time, font=font_time, fill=(220, 220, 230, 255))
    rem_bbox = draw.textbbox((0, 0), remain_time, font=font_time)
    rem_w = rem_bbox[2] - rem_bbox[0]
    draw.text(
        (bar_x + bar_w - rem_w, bar_y + 18),
        remain_time,
        font=font_time,
        fill=(220, 220, 230, 255),
    )

    cx = right_x + right_w // 2
    cy = bar_y + 110
    icon_gap = 90
    white = (255, 255, 255, 255)

    px = cx - icon_gap
    draw.polygon([(px + 14, cy - 16), (px + 14, cy + 16), (px - 14, cy)], fill=white)
    draw.rectangle([px - 18, cy - 16, px - 12, cy + 16], fill=white)

    draw.rectangle([cx - 16, cy - 20, cx - 6, cy + 20], fill=white)
    draw.rectangle([cx + 6, cy - 20, cx + 16, cy + 20], fill=white)

    nx = cx + icon_gap
    draw.polygon([(nx - 14, cy - 16), (nx - 14, cy + 16), (nx + 14, cy)], fill=white)
    draw.rectangle([nx + 12, cy - 16, nx + 18, cy + 16], fill=white)

    vol_y = cy + 70
    vol_x = right_x + 40
    vol_w = right_w - 80
    vol_h = 6
    vol_fill = int(vol_w * 0.65)
    sx = vol_x - 30
    draw.polygon(
        [(sx - 6, vol_y - 8), (sx + 6, vol_y - 14), (sx + 6, vol_y + 14), (sx - 6, vol_y + 8)],
        fill=white,
    )
    draw.rectangle([sx - 12, vol_y - 6, sx - 6, vol_y + 6], fill=white)

    draw.rounded_rectangle(
        [vol_x, vol_y - vol_h // 2, vol_x + vol_w, vol_y + vol_h // 2],
        radius=3,
        fill=(255, 255, 255, 50),
    )
    draw.rounded_rectangle(
        [vol_x, vol_y - vol_h // 2, vol_x + vol_fill, vol_y + vol_h // 2],
        radius=3,
        fill=(255, 255, 255, 210),
    )
    draw.ellipse(
        [vol_x + vol_fill - 7, vol_y - 7, vol_x + vol_fill + 7, vol_y + 7],
        fill=white,
    )

    footer_y1 = H - 95
    footer_y2 = H - 58
    _draw_center_text(draw, POWERED_LINE_1, footer_y1, font_power, (255, 255, 255, 230), W)
    _draw_center_text(draw, POWERED_LINE_2, footer_y2, font_power2, (200, 200, 210, 210), W)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final = bg.convert("RGB")
    final.save(output_path, quality=92)
    return output_path


async def _download_cover(url: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    filename = os.path.join(CACHE_DIR, f"cover_{abs(hash(url))}.jpg")
    try:
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return ""
                    data = await resp.read()
                    with open(filename, "wb") as f:
                        f.write(data)
                    return filename
        if os.path.isfile(url):
            return url
    except Exception as e:
        print(f"[cover download] {e}", flush=True)
    return ""


async def generate_player_thumbnail(
    thumb_url: str,
    title: str,
    artist: str,
    duration_min: str,
) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    out = os.path.join(CACHE_DIR, f"panel_{abs(hash(title + str(thumb_url)))}.jpg")
    cover = await _download_cover(thumb_url)
    if not cover or not os.path.isfile(cover):
        if os.path.isfile(FALLBACK_THUMB):
            cover = FALLBACK_THUMB
        else:
            cover = os.path.join(CACHE_DIR, "blank_cover.jpg")
            Image.new("RGB", (500, 500), (40, 40, 50)).save(cover)

    tot = convert_to_seconds(duration_min or "0:00")
    try:
        return await create_music_thumbnail(
            cover, title, artist, tot if tot else None, out
        )
    except Exception as e:
        print(f"[thumbnail draw] {e}", flush=True)
        return cover if cover else ""


async def generate_thumbnail(url: str) -> str:
    return await _download_cover(url)


async def make_thumbnail(image, title, channel, duration, output):
    return await create_music_thumbnail(image, title, channel, duration, output)


def build_media_stream(file_path: str, is_video: bool, start_sec: int = 0):
    """
    Build MediaStream matching working music bots pattern:
    video -> audio_parameters + video_parameters + audio_flags REQUIRED + video_flags AUTO_DETECT/REQUIRED
    audio -> audio_parameters + video_flags IGNORE
    """
    from pytgcalls.types import AudioQuality, MediaStream

    start_sec = max(0, int(start_sec or 0))

    # Resolve video quality enum
    video_param = None
    if is_video:
        try:
            from pytgcalls.types import VideoQuality

            for name in ("HD_720p", "SD_480p", "SD_360p", "FHD_1080p", "HD_1080p"):
                if hasattr(VideoQuality, name):
                    video_param = getattr(VideoQuality, name)
                    break
        except Exception as e:
            print(f"[VideoQuality] {e}", flush=True)

    # Build with progressive fallbacks (different pytgcalls versions)
    attempts = []

    if is_video:
        if video_param is not None:
            attempts.append(
                dict(
                    media_path=file_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=video_param,
                    audio_flags=MediaStream.Flags.REQUIRED,
                    video_flags=MediaStream.Flags.AUTO_DETECT,
                )
            )
            attempts.append(
                dict(
                    media_path=file_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=video_param,
                    audio_flags=MediaStream.Flags.REQUIRED,
                    video_flags=MediaStream.Flags.REQUIRED,
                )
            )
            attempts.append(
                dict(
                    media_path=file_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_parameters=video_param,
                )
            )
        attempts.append(
            dict(
                media_path=file_path,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.AUTO_DETECT,
            )
        )
        attempts.append(
            dict(
                media_path=file_path,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.REQUIRED,
            )
        )
    else:
        attempts.append(
            dict(
                media_path=file_path,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
            )
        )

    last_err = None
    for kwargs in attempts:
        if start_sec > 0:
            kwargs = dict(kwargs)
            kwargs["ffmpeg_parameters"] = f"-ss {start_sec}"
        try:
            stream = MediaStream(**kwargs)
            print(f"[MediaStream OK] video={is_video} keys={list(kwargs.keys())}", flush=True)
            return stream
        except TypeError as e:
            last_err = e
            # retry without ffmpeg_parameters if that was the issue
            if start_sec > 0 and "ffmpeg" in str(e).lower():
                try:
                    kwargs2 = {k: v for k, v in kwargs.items() if k != "ffmpeg_parameters"}
                    stream = MediaStream(**kwargs2)
                    print(f"[MediaStream OK no-ss] video={is_video}", flush=True)
                    return stream
                except Exception as e2:
                    last_err = e2
                    continue
            continue
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"MediaStream build failed: {last_err}")


@bot.on_message(cdz(["play", "vplay"]) & ~filters.private)
async def start_stream_in_vc(client, message):
    if await block_if_maintenance(message):
        return

    import time
    import traceback

    from ..platforms import Youtube
    from .callbacks import player_markup, queue_markup, start_progress_task

    chat_id = message.chat.id
    mention = message.from_user.mention if message.from_user else "User"
    is_video = message.command[0].lower() == "vplay"

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

    await aux.edit(f"Downloading {'video' if is_video else 'audio'}: {info['title']}...")

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
        size = os.path.getsize(file_path)
    except Exception:
        size = 0

    has_vid = False
    if is_video:
        has_vid = await asyncio.get_event_loop().run_in_executor(
            None, file_has_video, file_path
        )
        print(
            f"[stream] vplay path={file_path} size={size} has_video_stream={has_vid}",
            flush=True,
        )
        if not has_vid:
            return await aux.edit(
                "❌ Downloaded file mein video stream nahi hai.\n"
                "API ne audio-only file di — video play nahi ho sakta.\n\n"
                "API/key check karo ya dusra song try karo."
            )
    else:
        print(f"[stream] play path={file_path} size={size}", flush=True)

    try:
        media_stream = build_media_stream(file_path, is_video)
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
                file_path=file_path,
                is_video=is_video,
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
            file_path=file_path,
            is_video=is_video,
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
        thumb = await generate_player_thumbnail(
            info.get("thumbnail", ""),
            info.get("title", "Unknown"),
            info.get("channel") or info.get("uploader") or "YouTube Music",
            info.get("duration_min", "0:00"),
        )
        caption = panel_caption(
            info["title"],
            info.get("duration_min", "0:00"),
            mention,
            header="sᴛʀᴇᴀᴍɪɴɢ ɪɴ ᴠᴄ" + (" (ᴠɪᴅᴇᴏ)" if is_video else ""),
        )
        total_sec = convert_to_seconds(info.get("duration_min", "0:00"))
        buttons = player_markup(chat_id, 0, total_sec)
        await aux.delete()
        if thumb and os.path.isfile(thumb):
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
            call.queue[chat_id][0]["file_path"] = file_path
            call.queue[chat_id][0]["is_video"] = is_video
        start_progress_task(chat_id)
    except Exception as e:
        print(f"[PANEL ERROR] {e}", flush=True)
