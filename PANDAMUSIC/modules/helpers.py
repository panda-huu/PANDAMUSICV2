from .database import is_admins_only

from pyrogram import enums, filters
from typing import Union, List, Pattern


class AssistantErr(Exception):
    def __init__(self, errr: str):
        super().__init__(errr)


def cdx(commands: Union[str, List[str]]):
    return filters.command(commands, ["/", "!", "."])

def cdz(commands: Union[str, List[str]]):
    return filters.command(commands, ["", "/", "!", "."])

def rgx(pattern: Union[str, Pattern]):
    return filters.regex(pattern)


def AdminsOnlyWrapper(mystic):
    async def wrapper(client, message):
        from .. import console
        try:
            await message.delete()
        except Exception:
            pass

        if message.sender_chat:
            user_id = message.sender_chat.id
        else:
            user_id = message.from_user.id
            
        chat_id = message.chat.id
        
        if await is_admins_only(chat_id):
            if chat_id not in console.chat_admins:
                console.chat_admins[chat_id] = {}
                try:
                    owners = filters.user()
                    admins =  filters.user()
                    async for m in client.get_chat_members(
                        chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS
                    ):
                        if m.status == enums.ChatMemberStatus.OWNER:
                            if m.user.id not in owners:
                                owners.add(m.user.id)
                        if m.user.id not in admins:
                            admins.add(m.user.id)
        
                    console.chat_admins[chat_id]["owners"] = owners
                    console.chat_admins[chat_id]["admins"] = admins
                except Exception:
                    return await message.reply_text(
                        "🤖 **Please do /reload & then try again.**"
                    )
            if (
                user_id not in console.chat_admins[chat_id]["admins"]
                and user_id not in console.sudoers
            ):
                return await message.reply_text(
                    "❎ **Only chat admins can use this command.**"
                )
        
        return await mystic(client, message)

    return wrapper
