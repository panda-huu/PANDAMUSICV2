import html

_SMALL_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)


def smallcaps(text) -> str:
    """Convert A-Z/a-z to unicode small-caps style."""
    return str(text or "").translate(_SMALL_MAP)


def panel_caption(
    title: str,
    duration: str,
    requester: str,
    header: str = "sᴛʀᴇᴀᴍɪɴɢ ɪɴ ᴠᴄ",
) -> str:
    t = html.escape(smallcaps(title))
    d = html.escape(smallcaps(str(duration or "0:00")))
    if "<a " in str(requester):
        req = requester
    else:
        req = html.escape(smallcaps(requester))

    return (
        f"<blockquote expandable>"
        f"{html.escape(header)}\n\n"
        f"{smallcaps('title')} : {t}\n"
        f"{smallcaps('duration')} : {d}\n"
        f"{smallcaps('request by')} : {req}"
        f"</blockquote>"
    )


def queue_caption(
    position: int,
    title: str,
    duration: str,
    requester: str,
) -> str:
    header = f"{smallcaps('added to queue')} #{position}"
    t = html.escape(smallcaps(title))
    d = html.escape(smallcaps(str(duration or "0:00")))
    if "<a " in str(requester):
        req = requester
    else:
        req = html.escape(smallcaps(requester))

    return (
        f"<blockquote expandable>"
        f"{html.escape(header)}\n\n"
        f"{smallcaps('title')} : {t}\n"
        f"{smallcaps('duration')} : {d}\n"
        f"{smallcaps('request by')} : {req}"
        f"</blockquote>"
    )
