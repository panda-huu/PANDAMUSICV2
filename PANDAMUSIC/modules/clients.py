import sys
import time

from .. import console
from .database import get_assistant, group_assistant
from .helpers import AssistantErr
from .formatters import panel_caption

from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from pytgcalls import PyTgCalls, filters as fl
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import Call, GroupCallConfig, ChatUpdate, Update, StreamEnded


assistants = []
assistantids = []


class Bot(Client):
    def __init__(self):
        super().__init__(
            "PANDAMUSIC_Bot",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            bot_token=console.BOT_TOKEN,
        )

    async def start(self):
        console.logs(__name__).info("Starting Bot ...")
        await super().start()
        get_me = await self.get_me()
        if get_me.last_name:
            self.name = get_me.first_name + " " + get_me.last_name
        else:
            self.name = get_me.first_name
        self.username = get_me.username
        self.mention = get_me.mention
        self.id = get_me.id
        try:
            await self.send_message(console.LOG_GROUP_ID, "**Bot Started.**")
        except Exception:
            console.logs(__name__).error(
                "Bot has failed to access the log Group."
            )
            sys.exit()
        try:
            a = await self.get_chat_member(console.LOG_GROUP_ID, self.id)
        except Exception:
            console.logs(__name__).error(
                "Bot has failed to access the log Group."
            )
            sys.exit()
        if a.status != ChatMemberStatus.ADMINISTRATOR:
            console.logs(__name__).error(
                "Please promote bot as admin in your logger group!"
            )
            sys.exit()
        console.logs(__name__).info(f"Bot Started as {self.name}")


class App(Client):
    def __init__(self):
        self.one = Client(
            "PANDAMUSIC_1",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING1),
            no_updates=True,
        )
        self.two = Client(
            "PANDAMUSIC_2",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING2),
            no_updates=True,
        )
        self.three = Client(
            "PANDAMUSIC_3",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING3),
            no_updates=True,
        )
        self.four = Client(
            "PANDAMUSIC_4",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING4),
            no_updates=True,
        )
        self.five = Client(
            "PANDAMUSIC_5",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING5),
            no_updates=True,
        )

    async def start(self):
        console.logs(__name__).info("Starting Assistant Clients")
        clients = [
            (console.STRING1, self.one, 1),
            (console.STRING2, self.two, 2),
            (console.STRING3, self.three, 3),
            (console.STRING4, self.four, 4),
            (console.STRING5, self.five, 5),
        ]
        for string, client, num in clients:
            if not string:
                continue
            await client.start()
            try:
                await client.join_chat("AdityaServer")
                await client.join_chat("AdityaDiscus")
            except Exception:
                pass
            assistants.append(num)
            try:
                await client.send_message(
                    console.LOG_GROUP_ID, f"**Assistant ({num}) Started.**"
                )
            except Exception:
                console.logs(__name__).error(
                    f"Assistant account {num} has failed to access the log group."
                )
                sys.exit()
            get_me = await client.get_me()
            client.name = (
                (get_me.first_name + " " + get_me.last_name)
                if get_me.last_name
                else get_me.first_name
            )
            client.username = get_me.username
            client.mention = get_me.mention
            client.id = get_me.id
            assistantids.append(get_me.id)
            console.logs(__name__).info(
                f"Assistant ({num}) started as - {client.name}"
            )


class Call(PyTgCalls):
    def __init__(self):
        self.adityaplayer1 = Client(
            "PANDAMUSIC_Player_1",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING1),
        )
        self.one = PyTgCalls(self.adityaplayer1, cache_duration=100)
        self.adityaplayer2 = Client(
            "PANDAMUSIC_Player_2",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING2),
        )
        self.two = PyTgCalls(self.adityaplayer2, cache_duration=100)
        self.adityaplayer3 = Client(
            "PANDAMUSIC_Player_3",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING3),
        )
        self.three = PyTgCalls(self.adityaplayer3, cache_duration=100)
        self.adityaplayer4 = Client(
            "PANDAMUSIC_Player_4",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING4),
        )
        self.four = PyTgCalls(self.adityaplayer4, cache_duration=100)
        self.adityaplayer5 = Client(
            "PANDAMUSIC_Player_5",
            api_id=console.API_ID,
            api_hash=console.API_HASH,
            session_string=str(console.STRING5),
        )
        self.five = PyTgCalls(self.adityaplayer5, cache_duration=100)

    call_config = GroupCallConfig(auto_start=True)
    paused = {}
    queue = {}
    active_chats = []
    start_times = {}

    async def ensure_assistant_in_chat(self, chat_id):
        from .. import bot

        assistant = await get_assistant(chat_id)

        async def try_join():
            chat = await bot.get_chat(chat_id)
            try:
                if chat.username:
                    link_or_username = chat.username
                    chat_link = f"https://t.me/{link_or_username}"
                else:
                    try:
                        link_or_username = await bot.export_chat_invite_link(chat_id)
                        chat_link = link_or_username
                    except errors.ChatAdminRequired:
                        raise AssistantErr(
                            "Bot needs admin rights with Invite Users via Link permission."
                        )

                await assistant.join_chat(link_or_username)
                console.chat_links[chat_id] = chat_link
                return True
            except errors.UserAlreadyParticipant:
                return True
            except Exception as e:
                raise AssistantErr(f"Assistant join error: {e}")

        try:
            member = await bot.get_chat_member(chat_id, assistant.id)
            if member.status in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            ):
                return True
            if member.status == ChatMemberStatus.LEFT:
                return await try_join()
            raise AssistantErr(f"Assistant status: {member.status}")
        except errors.UserNotParticipant:
            return await try_join()
        except Exception as e:
            raise AssistantErr(f"Unexpected error while checking: {e}")

    async def change_stream(self, chat_id: int):
        from .. import bot
        from PANDAMUSIC.plugins.callbacks import (
            player_markup,
            start_progress_task,
            stop_progress_task,
            _parse_duration,
        )

        stop_progress_task(chat_id)
        await self.pop_queue(chat_id)

        queued = self.queue.get(chat_id)
        if not queued:
            await bot.send_message(chat_id, "**Queue is empty, left VC.**")
            return await self.close_stream(chat_id)

        aux = await bot.send_message(chat_id, "**Processing...**")

        item = queued[0]
        file_path = item.get("file_path")
        is_video = bool(item.get("is_video", False))
        media_stream = item.get("media_stream")

        # Rebuild stream properly for video if we have file path
        if file_path:
            try:
                media_stream = self._build_media_stream(file_path, is_video, 0)
                item["media_stream"] = media_stream
            except Exception as e:
                print(f"[change_stream rebuild] {e}", flush=True)

        await self.start_stream(chat_id, media_stream)
        self.start_times[chat_id] = time.time()
        self.paused[chat_id] = False

        thumbnail = item.get("thumbnail") or ""
        title = item.get("title") or "Unknown"
        duration = item.get("duration") or "0:00"
        mention = item.get("requested_by") or "User"
        total_sec = _parse_duration(duration)

        caption = panel_caption(
            title,
            duration,
            mention,
            header="sᴛᴀʀᴛᴇᴅ sᴛʀᴇᴀᴍɪɴɢ ᴏɴ ᴠᴄ"
            + (" (ᴠɪᴅᴇᴏ)" if is_video else ""),
        )
        buttons = player_markup(chat_id, 0, total_sec)

        try:
            await aux.delete()
        except Exception:
            pass

        try:
            if thumbnail and str(thumbnail).startswith("http"):
                panel = await bot.send_photo(
                    chat_id,
                    photo=thumbnail,
                    caption=caption,
                    reply_markup=buttons,
                    parse_mode=ParseMode.HTML,
                )
            else:
                panel = await bot.send_message(
                    chat_id,
                    caption,
                    reply_markup=buttons,
                    parse_mode=ParseMode.HTML,
                )
        except Exception:
            panel = await bot.send_message(
                chat_id,
                caption,
                reply_markup=buttons,
                parse_mode=ParseMode.HTML,
            )

        item["panel"] = panel
        item["played"] = 0
        start_progress_task(chat_id)

    async def start_stream(self, chat_id: int, media_stream):
        assistant = await group_assistant(self, chat_id)
        try:
            await assistant.play(chat_id, media_stream, config=self.call_config)
            if chat_id not in self.active_chats:
                self.active_chats.append(chat_id)
        except NoActiveGroupCall:
            try:
                await self.ensure_assistant_in_chat(chat_id)
            except Exception as e:
                print(f"[ensure_assistant] {e}", flush=True)

            try:
                await assistant.play(
                    chat_id,
                    media_stream,
                    config=GroupCallConfig(auto_start=True),
                )
                if chat_id not in self.active_chats:
                    self.active_chats.append(chat_id)
            except NoActiveGroupCall:
                raise AssistantErr(
                    "No active Voice Chat.\n\n"
                    "Pehle group mein Voice Chat / Video Chat start karo, "
                    "phir /play ya /vplay use karo."
                )

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    async def mute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    async def unmute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.leave_call(chat_id)

    def _build_media_stream(self, file_path: str, is_video: bool, start_sec: int = 0):
        from pytgcalls.types import AudioQuality, MediaStream

        start_sec = max(0, int(start_sec or 0))
        kwargs = {
            "media_path": file_path,
            "audio_parameters": AudioQuality.HIGH,
        }

        if is_video:
            video_param = None
            try:
                from pytgcalls.types import VideoQuality

                for name in ("HD_720p", "SD_480p", "SD_360p", "HD_1080p"):
                    if hasattr(VideoQuality, name):
                        video_param = getattr(VideoQuality, name)
                        break
            except Exception:
                video_param = None

            if video_param is not None:
                kwargs["video_parameters"] = video_param
            else:
                kwargs["video_flags"] = MediaStream.Flags.AUTO_DETECT
        else:
            kwargs["video_flags"] = MediaStream.Flags.IGNORE

        if start_sec > 0:
            ff = f"-ss {start_sec}"
            for key, val in (
                ("ffmpeg_parameters", ff),
                ("ffmpeg_parameters_before", ff),
                ("ffmpeg_parameters", ["-ss", str(start_sec)]),
            ):
                try:
                    return MediaStream(**{**kwargs, key: val})
                except TypeError:
                    continue

        return MediaStream(**kwargs)

    async def seek_stream(self, chat_id: int, position: int):
        """Seek by restarting stream from position (local file + ffmpeg -ss)."""
        position = max(0, int(position))
        queued = self.queue.get(chat_id) or []
        if not queued:
            raise RuntimeError("Nothing playing")

        item = queued[0]
        file_path = item.get("file_path")
        is_video = bool(item.get("is_video", False))

        if not file_path:
            ms = item.get("media_stream")
            file_path = getattr(ms, "media_path", None) or getattr(ms, "path", None)

        if not file_path:
            raise RuntimeError("File path missing — re-play the song")

        assistant = await group_assistant(self, chat_id)

        for method_name in ("seek_stream", "seek"):
            method = getattr(assistant, method_name, None)
            if not callable(method):
                continue
            try:
                await method(chat_id, position)
                return
            except TypeError:
                try:
                    await method(chat_id, position=position)
                    return
                except Exception:
                    pass
            except Exception:
                pass

        media = self._build_media_stream(file_path, is_video, position)
        await assistant.play(chat_id, media, config=self.call_config)
        item["media_stream"] = media

        if chat_id not in self.active_chats:
            self.active_chats.append(chat_id)

        self.paused[chat_id] = False

    async def add_to_queue(
        self,
        chat_id,
        media_stream,
        title,
        duration,
        thumbnail,
        requested_by,
        file_path=None,
        is_video=False,
    ):
        if chat_id not in self.queue:
            self.queue[chat_id] = []

        if not file_path and media_stream is not None:
            file_path = getattr(media_stream, "media_path", None) or getattr(
                media_stream, "path", None
            )

        item = {
            "media_stream": media_stream,
            "title": title,
            "duration": duration,
            "thumbnail": thumbnail,
            "requested_by": requested_by,
            "played": 0,
            "file_path": file_path,
            "is_video": bool(is_video),
        }
        self.queue[chat_id].append(item)
        return len(self.queue[chat_id]) - 1

    async def pop_queue(self, chat_id: int):
        if chat_id in self.queue and self.queue[chat_id]:
            return self.queue[chat_id].pop(0)
        return None

    async def clear_queue(self, chat_id: int):
        if chat_id in self.active_chats:
            self.active_chats.remove(chat_id)
        try:
            from PANDAMUSIC.plugins.callbacks import stop_progress_task

            stop_progress_task(chat_id)
        except Exception:
            pass
        try:
            self.queue.pop(chat_id)
        except Exception:
            pass
        self.start_times.pop(chat_id, None)
        self.paused.pop(chat_id, None)

    async def is_stream_off(self, chat_id: int) -> bool:
        mode = self.paused.get(chat_id)
        if not mode:
            return False
        return mode

    async def stream_on(self, chat_id: int):
        self.paused[chat_id] = False

    async def stream_off(self, chat_id: int):
        self.paused[chat_id] = True

    async def close_stream(self, chat_id: int):
        try:
            await self.stop_stream(chat_id)
        except Exception:
            pass
        await self.clear_queue(chat_id)

    async def ping(self):
        pings = []
        if console.STRING1:
            pings.append(await self.one.ping)
        if console.STRING2:
            pings.append(await self.two.ping)
        if console.STRING3:
            pings.append(await self.three.ping)
        if console.STRING4:
            pings.append(await self.four.ping)
        if console.STRING5:
            pings.append(await self.five.ping)
        if not pings:
            return "0"
        return str(round(sum(pings) / len(pings), 3))

    async def start(self):
        console.logs(__name__).info("Starting PyTgCalls Client\n")
        if console.STRING1:
            await self.one.start()
        if console.STRING2:
            await self.two.start()
        if console.STRING3:
            await self.three.start()
        if console.STRING4:
            await self.four.start()
        if console.STRING5:
            await self.five.start()

    async def decorators(self):
        @self.one.on_update(fl.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT))
        @self.two.on_update(fl.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT))
        @self.three.on_update(fl.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT))
        @self.four.on_update(fl.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT))
        @self.five.on_update(fl.chat_update(ChatUpdate.Status.CLOSED_VOICE_CHAT))
        @self.one.on_update(fl.chat_update(ChatUpdate.Status.KICKED))
        @self.two.on_update(fl.chat_update(ChatUpdate.Status.KICKED))
        @self.three.on_update(fl.chat_update(ChatUpdate.Status.KICKED))
        @self.four.on_update(fl.chat_update(ChatUpdate.Status.KICKED))
        @self.five.on_update(fl.chat_update(ChatUpdate.Status.KICKED))
        @self.one.on_update(fl.chat_update(ChatUpdate.Status.LEFT_GROUP))
        @self.two.on_update(fl.chat_update(ChatUpdate.Status.LEFT_GROUP))
        @self.three.on_update(fl.chat_update(ChatUpdate.Status.LEFT_GROUP))
        @self.four.on_update(fl.chat_update(ChatUpdate.Status.LEFT_GROUP))
        @self.five.on_update(fl.chat_update(ChatUpdate.Status.LEFT_GROUP))
        async def stream_services_handler(_, update: Update):
            return await self.close_stream(update.chat_id)

        @self.one.on_update(fl.stream_end())
        @self.two.on_update(fl.stream_end())
        @self.three.on_update(fl.stream_end())
        @self.four.on_update(fl.stream_end())
        @self.five.on_update(fl.stream_end())
        async def stream_end_handler(_, update: Update):
            return await self.change_stream(update.chat_id)
