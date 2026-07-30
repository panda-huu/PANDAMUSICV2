"""
PANDAMUSIC — PostgreSQL Database Layer (asyncpg)
MongoDB completely removed.
"""

import random
from typing import List, Optional

import asyncpg

from .. import console

log = console.logs(__name__)

_pool: Optional[asyncpg.Pool] = None
assistantdict = {}


async def init_db():
    global _pool
    try:
        host = (console.DB_HOST or "").strip().strip('"').strip("'")
        user = (console.DB_USER or "").strip().strip('"').strip("'")
        password = (console.DB_PASSWORD or "").strip().strip('"').strip("'")
        database = (console.DB_NAME or "postgres").strip().strip('"').strip("'")
        port = int(getattr(console, "DB_PORT", 6543) or 6543)

        if not host or not user:
            raise ValueError(
                "DB_HOST ya DB_USER missing hai. Config.env check karo."
            )

        _pool = await asyncpg.create_pool(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            min_size=2,
            max_size=10,
            command_timeout=30,
            ssl="require",
            statement_cache_size=0,
        )
        await _create_tables()
        log.info("✅ PostgreSQL connected successfully!")
    except Exception as e:
        log.error(f"❌ DB connection failed: {e}")
        _pool = None
        raise


async def _create_tables():
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS assistants (
                chat_id BIGINT PRIMARY KEY,
                assistant INT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS served_users (
                user_id BIGINT PRIMARY KEY,
                added_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS served_chats (
                chat_id BIGINT PRIMARY KEY,
                added_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS admins_only (
                chat_id BIGINT PRIMARY KEY,
                value BOOLEAN DEFAULT TRUE
            );

            CREATE TABLE IF NOT EXISTS sudoers (
                id TEXT PRIMARY KEY DEFAULT 'sudo',
                sudoers BIGINT[] DEFAULT '{}'
            );
        """)
    log.info("✅ Tables ready")


def _ok() -> bool:
    return _pool is not None


async def get_client(assistant: int):
    from .. import app
    mapping = {1: app.one, 2: app.two, 3: app.three, 4: app.four, 5: app.five}
    return mapping.get(int(assistant))


async def set_assistant(chat_id: int):
    from .clients import assistants
    ran = random.choice(assistants)
    assistantdict[chat_id] = ran
    if _ok():
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO assistants(chat_id, assistant) VALUES($1, $2)
                   ON CONFLICT(chat_id) DO UPDATE SET assistant=EXCLUDED.assistant""",
                chat_id, ran,
            )
    return await get_client(ran)


async def get_assistant(chat_id: int):
    from .clients import assistants
    assistant = assistantdict.get(chat_id)
    if not assistant:
        if _ok():
            async with _pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT assistant FROM assistants WHERE chat_id=$1", chat_id
                )
            if row and row["assistant"] in assistants:
                assistantdict[chat_id] = row["assistant"]
                return await get_client(row["assistant"])
        return await set_assistant(chat_id)
    if assistant in assistants:
        return await get_client(assistant)
    return await set_assistant(chat_id)


async def set_calls_assistant(chat_id: int) -> int:
    from .clients import assistants
    ran = random.choice(assistants)
    assistantdict[chat_id] = ran
    if _ok():
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO assistants(chat_id, assistant) VALUES($1, $2)
                   ON CONFLICT(chat_id) DO UPDATE SET assistant=EXCLUDED.assistant""",
                chat_id, ran,
            )
    return ran


async def group_assistant(self, chat_id: int):
    from .clients import assistants
    assistant = assistantdict.get(chat_id)
    if not assistant:
        if _ok():
            async with _pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT assistant FROM assistants WHERE chat_id=$1", chat_id
                )
            if row and row["assistant"] in assistants:
                assistantdict[chat_id] = row["assistant"]
                assistant = row["assistant"]
            else:
                assistant = await set_calls_assistant(chat_id)
        else:
            assistant = await set_calls_assistant(chat_id)
    elif assistant not in assistants:
        assistant = await set_calls_assistant(chat_id)

    mapping = {1: self.one, 2: self.two, 3: self.three, 4: self.four, 5: self.five}
    return mapping.get(int(assistant), self.one)


async def is_served_user(user_id: int) -> bool:
    if not _ok():
        return False
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM served_users WHERE user_id=$1", user_id
        )
    return row is not None


async def add_served_user(user_id: int):
    if not _ok() or await is_served_user(user_id):
        return
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO served_users(user_id) VALUES($1) ON CONFLICT DO NOTHING",
            user_id,
        )


async def get_served_users() -> list:
    if not _ok():
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM served_users WHERE user_id > 0")
    return [{"user_id": r["user_id"]} for r in rows]


async def is_served_chat(chat_id: int) -> bool:
    if not _ok():
        return False
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM served_chats WHERE chat_id=$1", chat_id
        )
    return row is not None


async def add_served_chat(chat_id: int):
    if not _ok() or await is_served_chat(chat_id):
        return
    async with _pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO served_chats(chat_id) VALUES($1) ON CONFLICT DO NOTHING",
            chat_id,
        )


async def get_served_chats() -> list:
    if not _ok():
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT chat_id FROM served_chats WHERE chat_id < 0")
    return [{"chat_id": r["chat_id"]} for r in rows]


async def is_admins_only(chat_id: int) -> bool:
    if not _ok():
        return True
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM admins_only WHERE chat_id=$1", chat_id
        )
    if not row:
        return True
    return bool(row["value"])


async def set_admins_only(chat_id: int, value: bool) -> bool:
    if not _ok():
        return bool(value)
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO admins_only(chat_id, value) VALUES($1, $2)
               ON CONFLICT(chat_id) DO UPDATE SET value=EXCLUDED.value""",
            chat_id, bool(value),
        )
    return bool(value)


async def get_sudoers_list() -> List[int]:
    if not _ok():
        return [console.OWNER_ID] if console.OWNER_ID else []
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT sudoers FROM sudoers WHERE id='sudo'")
    if not row or not row["sudoers"]:
        return [console.OWNER_ID] if console.OWNER_ID else []
    return list(row["sudoers"])


async def add_sudo(user_id: int):
    sudos = await get_sudoers_list()
    if user_id not in sudos:
        sudos.append(user_id)
    if _ok():
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO sudoers(id, sudoers) VALUES('sudo', $1)
                   ON CONFLICT(id) DO UPDATE SET sudoers=EXCLUDED.sudoers""",
                sudos,
            )
