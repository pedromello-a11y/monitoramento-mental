import asyncpg
from pathlib import Path
from config import DATABASE_URL

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global _pool
    if not DATABASE_URL:
        return
    _pool = await asyncpg.create_pool(DATABASE_URL)
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    async with _pool.acquire() as conn:
        await conn.execute(schema)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Pool not initialized")
    return _pool
