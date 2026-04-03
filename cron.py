import logging
from datetime import date
from fastapi import APIRouter, Header, HTTPException
from config import INTERNAL_CRON_SECRET, APP_URL
from database import get_pool
from whapi import send_message

logger = logging.getLogger(__name__)

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


@router.get("/internal/cron/debug")
async def cron_debug(x_cron_secret: str | None = Header(default=None)):
    """Diagnóstico: retorna estado atual de cada condição do cron sem enviar nada."""
    _check_secret(x_cron_secret)
    pool = get_pool()
    today = date.today().isoformat()
    async with pool.acquire() as conn:
        db_date = await conn.fetchval("SELECT CURRENT_DATE")
        db_tz = await conn.fetchval("SELECT current_setting('TimeZone')")
        usuarios = await conn.fetch("SELECT id, whatsapp FROM usuarios")
        resultado = []
        for u in usuarios:
            idem_key = f"{u['id']}:checkin_22h:{today}"
            concluiu = await _ja_concluiu_hoje(conn, u["id"])
            ja_enviado = await _ja_enviado_hoje(conn, idem_key)
            last_dispatch = await conn.fetchrow(
                "SELECT sent_at, tipo_evento FROM event_dispatch_log WHERE user_id=$1 ORDER BY sent_at DESC LIMIT 1",
                u["id"],
            )
            resultado.append({
                "user_id": u["id"],
                "python_today": today,
                "db_current_date": str(db_date),
                "db_timezone": db_tz,
                "ja_concluiu_hoje": concluiu,
                "ja_enviado_hoje": ja_enviado,
                "idem_key": idem_key,
                "ultimo_dispatch": str(last_dispatch["sent_at"]) if last_dispatch else None,
                "ultimo_dispatch_tipo": last_dispatch["tipo_evento"] if last_dispatch else None,
            })
    return {"status": "ok", "checks": resultado}


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
    logger.info(f"[cron/checkin] iniciando — today={today} usuarios={len(usuarios)}")

    for u in usuarios:
        processados += 1
        idem_key = f"{u['id']}:checkin_22h:{today}"
        async with pool.acquire() as conn:
            concluiu = await _ja_concluiu_hoje(conn, u["id"])
            if concluiu:
                logger.info(f"[cron/checkin] user {u['id']} skip: já concluiu hoje")
                skipped_completed += 1
                continue
            ja_enviado = await _ja_enviado_hoje(conn, idem_key)
            if ja_enviado:
                logger.info(f"[cron/checkin] user {u['id']} skip: já enviado (key={idem_key})")
                skipped_already_sent += 1
                continue
            row = await conn.fetchrow(
                "SELECT streak_atual FROM streak WHERE user_id = $1", u["id"]
            )
        streak_atual = row["streak_atual"] if row else 0
        logger.info(f"[cron/checkin] enviando para user {u['id']} streak={streak_atual}")
        ok = await send_message(u["whatsapp"], f"🔥 {streak_atual} dias seguidos. Hora do check-in de hoje.\n\nResponda */checkin* aqui ou acesse:\n{APP_URL}/checkin-web")
        logger.info(f"[cron/checkin] send_message resultado={ok}")
        async with pool.acquire() as conn:
            await _registrar_envio(conn, u["id"], "checkin_22h", idem_key)
        if ok:
            sent += 1
        else:
            logger.warning(f"[cron/checkin] send_message falhou para user {u['id']} ({u['whatsapp']})")

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
        ok = await send_message(u["whatsapp"], f"Ainda dá tempo para registrar hoje. 🙂\n\n*/checkin* aqui ou pelo site:\n{APP_URL}/checkin-web")
        async with pool.acquire() as conn:
            await _registrar_envio(conn, u["id"], "lembrete_22h30", idem_key)
        if ok:
            sent += 1
        else:
            import logging
            logging.warning(f"[cron/lembrete1] send_message falhou para user {u['id']}")

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
        ok = await send_message(
            u["whatsapp"],
            f"⚠️ Última chance hoje.\n{streak_atual} dias. Vai perder por falta de 60 segundos?\n\n*/checkin* aqui ou:\n{APP_URL}/checkin-web",
        )
        async with pool.acquire() as conn:
            await _registrar_envio(conn, u["id"], "lembrete_23h15", idem_key)
        if ok:
            sent += 1
        else:
            import logging
            logging.warning(f"[cron/lembrete2] send_message falhou para user {u['id']}")

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


@router.post("/internal/migrate/remedios-doses")
async def migrate_remedios_doses(x_cron_secret: str | None = Header(default=None)):
    _check_secret(x_cron_secret)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE remedios SET dose_padrao = 3 WHERE nome ILIKE 'Zolpidem%' AND user_id = 1"
        )
        await conn.execute(
            "UPDATE remedios SET dose = '0,5mg' WHERE nome ILIKE 'Rivotril%' AND user_id = 1"
        )
        rows = await conn.fetch(
            "SELECT nome, dose, dose_padrao FROM remedios WHERE user_id = 1 AND ativo = TRUE ORDER BY id"
        )
    return {"status": "ok", "remedios": [dict(r) for r in rows]}


@router.post("/internal/reprocess/relatos")
async def reprocess_relatos(x_cron_secret: str | None = Header(default=None)):
    """Re-processa com IA todos os relatos que ainda não têm resumo_ia."""
    _check_secret(x_cron_secret)
    from config import OPENAI_API_KEY
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY não configurado"}
    import json as _json
    from openai import AsyncOpenAI
    ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT data, nota_raw FROM checkins
               WHERE user_id=1 AND nota_raw IS NOT NULL AND nota_raw != ''
                 AND (nota_resumo_ia IS NULL OR nota_resumo_ia = '')
               ORDER BY data DESC"""
        )
    processados = 0
    for r in rows:
        try:
            resp = await ai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": (
                        "Você é um psicólogo analista de saúde mental. Analise o relato diário e retorne JSON com: "
                        "resumo (frase curta, acolhedora, 1a pessoa, máx 90 chars), "
                        "sentimento (positivo/neutro/negativo), "
                        "categorias (lista de até 5 temas reutilizáveis em português, ex: ansiedade, sono, trabalho, relacionamento, humor, dor, energia, medicação, exercício). "
                        "Responda APENAS com JSON válido."
                    )},
                    {"role": "user", "content": r["nota_raw"]},
                ],
                response_format={"type": "json_object"},
            )
            analysis = _json.loads(resp.choices[0].message.content)
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE checkins SET nota_sentimento=$1, nota_categorias=$2::jsonb, nota_resumo_ia=$3 WHERE user_id=1 AND data=$4",
                    analysis.get("sentimento", ""),
                    _json.dumps(analysis.get("categorias", []), ensure_ascii=False),
                    analysis.get("resumo", ""),
                    r["data"],
                )
            processados += 1
        except Exception as e:
            pass
    return {"status": "ok", "processados": processados, "total": len(rows)}


@router.post("/internal/migrate/escala-1-5")
async def migrate_escala_1_5(x_cron_secret: str | None = Header(default=None)):
    """Converte dados históricos de escala 0-10 para 1-5 (floor(v/2), mínimo 1)."""
    _check_secret(x_cron_secret)
    pool = get_pool()
    campos = ["dor_fisica", "energia", "sono_qualidade", "saude_mental",
              "stress_trabalho", "stress_relacionamento", "desempenho_social", "alimentacao"]
    async with pool.acquire() as conn:
        for campo in campos:
            await conn.execute(f"""
                UPDATE checkins
                SET {campo} = GREATEST(1, FLOOR({campo}::numeric / 2))
                WHERE user_id = 1
                  AND {campo} IS NOT NULL
                  AND {campo} > 5
            """)
        row = await conn.fetchrow("SELECT COUNT(*) AS total FROM checkins WHERE user_id=1")
    return {"status": "ok", "registros": row["total"], "campos_migrados": campos}


@router.post("/internal/migrate/contextos-seed")
async def migrate_contextos_seed(x_cron_secret: str | None = Header(default=None)):
    _check_secret(x_cron_secret)
    pool = get_pool()
    novos = ["Hora extra", "Terapia"]
    async with pool.acquire() as conn:
        for label in novos:
            await conn.execute(
                "INSERT INTO contextos_config (user_id, label, ordem) VALUES (1, $1, 99) ON CONFLICT DO NOTHING",
                label,
            )
        rows = await conn.fetch("SELECT id, label, ativo FROM contextos_config WHERE user_id=1 ORDER BY ordem, id")
    return {"status": "ok", "contextos": [dict(r) for r in rows]}


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
