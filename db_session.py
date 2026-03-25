from datetime import date
from database import get_pool


async def get_or_create_session(user_id: int, data_ref: date) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM checkin_sessions
            WHERE user_id = $1 AND data_referencia = $2
              AND status = 'em_andamento'
            LIMIT 1
            """,
            user_id, data_ref,
        )
        if row:
            return dict(row)

        row = await conn.fetchrow(
            """
            SELECT * FROM checkin_sessions
            WHERE user_id = $1 AND data_referencia = $2
              AND status IN ('cancelado', 'abandonado')
            LIMIT 1
            """,
            user_id, data_ref,
        )
        if row:
            row = await conn.fetchrow(
                """
                UPDATE checkin_sessions
                SET status = 'em_andamento', passo_atual = 1, atualizado_em = NOW()
                WHERE id = $1
                RETURNING *
                """,
                row["id"],
            )
            return dict(row)

        row = await conn.fetchrow(
            """
            INSERT INTO checkin_sessions (user_id, data_referencia, status, passo_atual)
            VALUES ($1, $2, 'em_andamento', 1)
            RETURNING *
            """,
            user_id, data_ref,
        )
        return dict(row)


async def get_completed_session(user_id: int, data_ref: date) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM checkin_sessions
            WHERE user_id = $1 AND data_referencia = $2
              AND status = 'concluido'
            LIMIT 1
            """,
            user_id, data_ref,
        )
        return dict(row) if row else None


async def get_active_session(user_id: int, data_ref: date) -> dict | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM checkin_sessions
            WHERE user_id = $1 AND status = 'em_andamento'
              AND data_referencia = $2
            ORDER BY atualizado_em DESC
            LIMIT 1
            """,
            user_id, data_ref,
        )
        return dict(row) if row else None
