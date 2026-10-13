# database.py
# Хранит список каналов, где бот — админ.

import os
import aiosqlite
from datetime import datetime
from config import DB_PATH

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id    INTEGER UNIQUE NOT NULL,
                channel_name  TEXT,
                added_at      TIMESTAMP
            )
        """)
        await db.commit()


async def add_channel(channel_id: int, channel_name: str):
    """Добавляет канал в базу."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO channels (channel_id, channel_name, added_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(channel_id) DO UPDATE SET channel_name = excluded.channel_name",
            (channel_id, channel_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()


async def remove_channel(channel_id: int):
    """Удаляет канал из базы."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await db.commit()


async def get_channels() -> list[tuple]:
    """Список всех каналов."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT channel_id, channel_name, added_at FROM channels ORDER BY id"
        )
        return await cur.fetchall()