from datetime import date
from fastapi import APIRouter, Header, HTTPException
from config import INTERNAL_CRON_SECRET
from database import get_pool
from whapi import send_message

router = APIRouter()


def _check_secret(x_cron_secret: str | None):
    if not INTERNAL_CRON_SECRET or x_cron_secret != INTERNAL_CRON_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")


async def _ja_concluiu_hoje(conn, user_id: int) -> bool:
    row = await conn.fetchrow(
        """
        SELECT id FROM checkin_sessions
        WHERE user_id = $1 AND data_referencia = CURRENT_DATE
          AND status = 'concluido'
        LIMIT 1
        """,
        user_id,
    )
    return row is not None


async def _ja_enviado_hoje(conn, idempotency_key: str) -> bool:
    row = await conn.fetchrow(
        "SELECT id FROM event_dispatch_log WHERE idempotency_key = $1 LIMIT 1",
        idempotency_key,
    )
    return row is not None


async def _registrar_envio(conn, user_id: int, tipo_evento: str, idem_key: str):
    await conn.execute(
        """
        INSERT INTO event_dispatch_log
          (user_id, tipo_evento, data_referencia, scheduled_for, sent_at, status, idempotency_key)
        VALUES ($1, $2, CURRENT_DATE, NOW(), NOW(), 'enviado', $3)
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        user_id, tipo_evento, idem_key,
    )


@router.post("/internal/cron/checkin")
async def cron_checkin(x_cron_secret: str | None = Header(default=None)):
    _check_secret(x_cron_secret)
    pool = get_pool()
    async with pool.acquire() as conn:
        usuarios = await conn.fetch("SELECT id, whatsapp FROM usuarios")

    processados = 0
    sent = 0
    skipped_completed = 0
    skipped_already_sent = 0
    today = date.today().isoformat()

    for u in usuarios:
        processados += 1
        idem_key = f"{u['id']}:checkin_22h:{today}"
        async with pool.acquire() as conn:
            if await _ja_concluiu_hoje(conn, u["id"]):
                skipped_completed += 1
                continue
            if await _ja_enviado_hoje(conn, idem_key):
                skipped_already_sent += 1
                continue
            row = await conn.fetchrow(
                "SELECT streak_atual FROM streak WHERE user_id = $1", u["id"]
            )
        streak_atual = row["streak_atual"] if row else 0
        await send_message(u["whatsapp"], f"🔥 {streak_atual} dias seguidos. Hora do check-in de hoje.")
        async with pool.acquire() as conn:
            await _registrar_envio(conn, u["id"], "checkin_22h", idem_key)
        sent += 1

    return {"status": "ok", "processed": processados, "sent": sent,
            "skipped_completed": skipped_completed, "skipped_already_sent": skipped_already_sent}


@router.post("/internal/cron/lembrete1")
async def cron_lembrete1(x_cron_secret: str | None = Header(default=None)):
    _check_secret(x_cron_secret)
    pool = get_pool()
    async with pool.acquire() as conn:
        usuarios = await conn.fetch("SELECT id, whatsapp FROM usuarios")

    processados = 0
    sent = 0
    skipped_completed = 0
    skipped_already_sent = 0
    today = date.today().isoformat()

    for u in usuarios:
        processados += 1
        idem_key = f"{u['id']}:lembrete_22h30:{today}"
        async with pool.acquire() as conn:
            if await _ja_concluiu_hoje(conn, u["id"]):
                skipped_completed += 1
                continue
            if await _ja_enviado_hoje(conn, idem_key):
                skipped_already_sent += 1
                continue
        await send_message(u["whatsapp"], "Ainda dá tempo para registrar hoje. 🙂")
        async with pool.acquire() as conn:
            await _registrar_envio(conn, u["id"], "lembrete_22h30", idem_key)
        sent += 1

    return {"status": "ok", "processed": processados, "sent": sent,
            "skipped_completed": skipped_completed, "skipped_already_sent": skipped_already_sent}


@router.post("/internal/cron/lembrete2")
async def cron_lembrete2(x_cron_secret: str | None = Header(default=None)):
    _check_secret(x_cron_secret)
    pool = get_pool()
    async with pool.acquire() as conn:
        usuarios = await conn.fetch("SELECT id, whatsapp FROM usuarios")

    processados = 0
    sent = 0
    skipped_completed = 0
    skipped_already_sent = 0
    today = date.today().isoformat()

    for u in usuarios:
        processados += 1
        idem_key = f"{u['id']}:lembrete_23h15:{today}"
        async with pool.acquire() as conn:
            if await _ja_concluiu_hoje(conn, u["id"]):
                skipped_completed += 1
                continue
            if await _ja_enviado_hoje(conn, idem_key):
                skipped_already_sent += 1
                continue
            row = await conn.fetchrow(
                "SELECT streak_atual FROM streak WHERE user_id = $1", u["id"]
            )
        streak_atual = row["streak_atual"] if row else 0
        await send_message(
            u["whatsapp"],
            f"⚠️ Última chance hoje.\n{streak_atual} dias. Vai perder por falta de 60 segundos?",
        )
        async with pool.acquire() as conn:
            await _registrar_envio(conn, u["id"], "lembrete_23h15", idem_key)
        sent += 1

    return {"status": "ok", "processed": processados, "sent": sent,
            "skipped_completed": skipped_completed, "skipped_already_sent": skipped_already_sent}


@router.post("/internal/cron/streak")
async def cron_streak(x_cron_secret: str | None = Header(default=None)):
    _check_secret(x_cron_secret)
    pool = get_pool()
    async with pool.acquire() as conn:
        usuarios = await conn.fetch("SELECT id, whatsapp FROM usuarios")

    processados = 0
    sent = 0
    skipped_completed = 0
    skipped_already_sent = 0
    today = date.today().isoformat()

    for u in usuarios:
        processados += 1
        idem_key = f"{u['id']}:streak_loss_23h59:{today}"
        async with pool.acquire() as conn:
            if await _ja_concluiu_hoje(conn, u["id"]):
                skipped_completed += 1
                continue
            if await _ja_enviado_hoje(conn, idem_key):
                skipped_already_sent += 1
                continue
        await send_message(
            u["whatsapp"],
            "Hoje não rolou registrar. Tudo bem.\nSeu histórico continua salvo.\nAmanhã você retoma. 🌙",
        )
        async with pool.acquire() as conn:
            await _registrar_envio(conn, u["id"], "streak_loss_23h59", idem_key)
        sent += 1

    return {"status": "ok", "processed": processados, "sent": sent,
            "skipped_completed": skipped_completed, "skipped_already_sent": skipped_already_sent}


@router.post("/internal/cron/cleanup-sessoes")
async def cron_cleanup(x_cron_secret: str | None = Header(default=None)):
    _check_secret(x_cron_secret)
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE checkin_sessions
            SET status = 'abandonado',
                passo_abandono = passo_atual,
                atualizado_em = NOW()
            WHERE status = 'em_andamento'
              AND atualizado_em < NOW() - INTERVAL '2 hours'
            """,
        )
    afetadas = int(result.split()[-1])
    return {"status": "ok", "sessoes_abandonadas": afetadas}
