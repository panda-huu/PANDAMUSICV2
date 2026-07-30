import asyncio
import os
import subprocess
from typing import Optional, Dict, Any

import aiohttp

from .. import console

API_URL = getattr(console, "SHRUTI_API_URL", None) or "https://aruyt.up.railway.app"
API_KEY = getattr(console, "SHRUTI_API_KEY", None) or ""
DOWNLOAD_DIR = "downloads"


def check_duration(file_path: str) -> float:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return float(out.strip())
    except Exception:
        return 0.0


def _to_vidid(value: str) -> str:
    value = str(value or "").strip()
    if "v=" in value:
        value = value.split("v=")[-1].split("&")[0]
    if "youtu.be/" in value:
        value = value.split("youtu.be/")[-1].split("?")[0]
    return value.strip()


def _safe_str(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _parse_thumb(r: dict) -> str:
    thumbs = r.get("thumbnails")
    if isinstance(thumbs, list) and thumbs:
        first = thumbs[0] if isinstance(thumbs[0], dict) else {}
        url = first.get("url")
        if url:
            return _safe_str(url).split("?")[0]
    # common alt keys
    for key in ("thumbnail", "thumb", "image"):
        val = r.get(key)
        if isinstance(val, str) and val:
            return val.split("?")[0]
        if isinstance(val, dict) and val.get("url"):
            return _safe_str(val.get("url")).split("?")[0]
    vidid = _safe_str(r.get("id") or r.get("vidid"))
    if vidid:
        return f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"
    return ""


def _parse_channel(r: dict) -> str:
    ch = r.get("channel")
    if isinstance(ch, dict):
        return _safe_str(ch.get("name") or ch.get("title"), "YouTube Music")
    if isinstance(ch, str) and ch.strip():
        return ch.strip()
    for key in ("channelName", "uploader", "artist"):
        val = r.get(key)
        if val:
            return _safe_str(val, "YouTube Music")
    return "YouTube Music"


def _normalize_result(r: dict) -> Optional[Dict[str, Any]]:
    if not isinstance(r, dict):
        return None

    vidid = _safe_str(r.get("id") or r.get("vidid") or r.get("video_id"))
    if not vidid and r.get("link"):
        vidid = _to_vidid(_safe_str(r.get("link")))
    if not vidid and r.get("url"):
        vidid = _to_vidid(_safe_str(r.get("url")))
    if not vidid or len(vidid) < 5:
        return None

    title = _safe_str(r.get("title"), "Unknown")
    duration = _safe_str(r.get("duration") or r.get("duration_min") or r.get("duration_string"), "0:00")
    # yt-dlp sometimes gives seconds as int
    if isinstance(r.get("duration"), (int, float)) and r.get("duration"):
        secs = int(r["duration"])
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        duration = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    link = _safe_str(r.get("link") or r.get("url")) or f"https://www.youtube.com/watch?v={vidid}"

    return {
        "title": title,
        "link": link,
        "vidid": vidid,
        "duration_min": duration,
        "thumbnail": _parse_thumb({**r, "id": vidid}),
        "channel": _parse_channel(r),
    }


async def _search_yts(query: str) -> Optional[Dict[str, Any]]:
    """Primary: youtube-search-python (may break when YT HTML changes)."""
    try:
        from youtubesearchpython.__future__ import VideosSearch

        results = VideosSearch(str(query).strip(), limit=5)
        data = await results.next()
        items = data.get("result") or []
        for item in items:
            parsed = _normalize_result(item)
            if parsed:
                return parsed
    except Exception as e:
        print(f"[Youtube.search yts] {e}", flush=True)
    return None


async def _search_ytdlp(query: str) -> Optional[Dict[str, Any]]:
    """Fallback: yt-dlp ytsearch — more reliable."""
    try:
        import yt_dlp

        def _run():
            opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "skip_download": True,
                "default_search": "ytsearch",
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
                return info

        info = await asyncio.to_thread(_run)
        entries = (info or {}).get("entries") or []
        for entry in entries:
            if not entry:
                continue
            # flat entries use 'id' / 'title' / 'duration' / 'url'
            parsed = _normalize_result(
                {
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "duration": entry.get("duration"),
                    "url": entry.get("url") or entry.get("webpage_url"),
                    "link": entry.get("webpage_url") or entry.get("url"),
                    "channel": entry.get("channel") or entry.get("uploader"),
                    "thumbnails": entry.get("thumbnails") or [],
                    "thumbnail": entry.get("thumbnail"),
                }
            )
            if parsed:
                return parsed
    except Exception as e:
        print(f"[Youtube.search ytdlp] {e}", flush=True)
    return None


async def search(query: str) -> Optional[Dict[str, Any]]:
    if not query or not str(query).strip():
        return None

    q = str(query).strip()

    # Direct YouTube URL / video id
    if "youtube.com" in q or "youtu.be" in q or (len(q) == 11 and " " not in q):
        vidid = _to_vidid(q)
        if vidid and len(vidid) >= 10:
            return {
                "title": "YouTube Video",
                "link": f"https://www.youtube.com/watch?v={vidid}",
                "vidid": vidid,
                "duration_min": "0:00",
                "thumbnail": f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg",
                "channel": "YouTube Music",
            }

    # 1) youtube-search-python
    result = await _search_yts(q)
    if result:
        return result

    # 2) yt-dlp fallback
    result = await _search_ytdlp(q)
    if result:
        return result

    print(f"[Youtube.search] No results for: {q}", flush=True)
    return None


async def _download(vidid: str, media_type: str, ext: str, timeout_total: int) -> Optional[str]:
    vidid = _to_vidid(vidid)
    if not vidid or len(vidid) < 3:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{vidid}.{ext}")
    loop = asyncio.get_event_loop()

    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 1024:
            dur = await loop.run_in_executor(None, check_duration, file_path)
            if dur and dur > 2:
                return file_path
            try:
                os.remove(file_path)
            except Exception:
                pass
    except Exception:
        pass

    if not API_KEY:
        print("[Youtube] API_KEY missing — download skip", flush=True)
        return None

    full_url = f"https://www.youtube.com/watch?v={vidid}"
    url_variants = [full_url, vidid]

    for attempt in range(4):
        use_url = url_variants[attempt % len(url_variants)]
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_total, connect=25)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{API_URL.rstrip('/')}/download",
                    params={
                        "url": use_url,
                        "type": media_type,
                        "api_key": API_KEY,
                    },
                ) as resp:

                    if resp.status == 429:
                        wait = min(20, 3 * (attempt + 1))
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after and str(retry_after).isdigit():
                            wait = float(retry_after)
                        print(
                            f"[Youtube] {media_type} 429 — wait {wait}s (try {attempt+1})",
                            flush=True,
                        )
                        await asyncio.sleep(wait)
                        continue

                    if resp.status in (500, 502, 503, 504):
                        body = (await resp.text())[:250]
                        wait = min(15, 2 ** attempt)
                        print(
                            f"[Youtube] {media_type} HTTP {resp.status}: {body} "
                            f"(try {attempt+1}, wait {wait}s)",
                            flush=True,
                        )
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        body = (await resp.text())[:250]
                        print(
                            f"[Youtube] {media_type} HTTP {resp.status}: {body} "
                            f"(try {attempt+1})",
                            flush=True,
                        )
                        await asyncio.sleep(1.5)
                        continue

                    with open(file_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(131072):
                            f.write(chunk)

            if not (os.path.exists(file_path) and os.path.getsize(file_path) > 1024):
                await asyncio.sleep(1)
                continue

            dur = await loop.run_in_executor(None, check_duration, file_path)
            if dur and dur > 2:
                return file_path

            print(
                f"[Youtube] {media_type} invalid duration ({dur}s) — retry",
                flush=True,
            )
            try:
                os.remove(file_path)
            except Exception:
                pass

        except asyncio.TimeoutError:
            print(f"[Youtube] {media_type} timeout (try {attempt+1})", flush=True)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
        except Exception as e:
            print(
                f"[Youtube] {media_type} error (try {attempt+1}): {e}",
                flush=True,
            )
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

        await asyncio.sleep(1.5)

    print(
        f"[Youtube] {media_type} FAILED after retries for {vidid}",
        flush=True,
    )
    return None


async def download_song(vidid: str) -> Optional[str]:
    try:
        return await _download(vidid, "audio", "mp3", 100)
    except Exception as e:
        print(f"[Youtube.download_song] {e}", flush=True)
        return None


async def download_video(vidid: str) -> Optional[str]:
    try:
        return await _download(vidid, "video", "mp4", 160)
    except Exception as e:
        print(f"[Youtube.download_video] {e}", flush=True)
        return None
