"""
Todas as queries SQL do dashboard — apenas funções async.
"""

import json
from datetime import timedelta


async def get_checkins_semana(pool, user_id=1) -> list:  # TODO: auth
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT data, dor_fisica, energia, sono_horas, sono_qualidade,
                   saude_mental, stress_trabalho, stress_relacionamento,
                   alcool, exercicio, cigarros, desempenho_social,
                   nota_raw, nota_resumo_ia, nota_sentimento, nota_categorias,
                   remedios_tomados, contextos_dia, alimentacao
            FROM checkins WHERE user_id = $1
            ORDER BY data DESC LIMIT 7
            """,
            user_id,
        )
    return [dict(r) for r in rows]


async def get_streak(pool, user_id=1) -> dict:  # TODO: auth
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT streak_atual, streak_maximo FROM streak WHERE user_id = $1",
            user_id,
        )
    if row:
        return dict(row)
    return {"streak_atual": 0, "streak_maximo": 0}


async def get_media_semana(pool, user_id=1) -> dict:  # TODO: auth
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ROUND(AVG(dor_fisica),1) AS dor, ROUND(AVG(energia),1) AS energia,
                   ROUND(AVG(sono_horas),1) AS sono_h, ROUND(AVG(sono_qualidade),1) AS sono_q,
                   ROUND(AVG(saude_mental),1) AS mental, ROUND(AVG(stress_trabalho),1) AS stress_t,
                   ROUND(AVG(stress_relacionamento),1) AS stress_r, ROUND(AVG(cigarros),1) AS cigarros,
                   ROUND(AVG(desempenho_social),1) AS social
            FROM checkins WHERE user_id = $1
              AND data >= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date - 6
            """,
            user_id,
        )
    return dict(row) if row else {}


async def get_media_semana_anterior(pool, user_id=1) -> dict:  # TODO: auth
    """Média dos 7 dias anteriores à semana atual (para calcular deltas)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ROUND(AVG(dor_fisica),1) AS dor, ROUND(AVG(energia),1) AS energia,
                   ROUND(AVG(sono_horas),1) AS sono_h, ROUND(AVG(sono_qualidade),1) AS sono_q,
                   ROUND(AVG(saude_mental),1) AS mental, ROUND(AVG(stress_trabalho),1) AS stress_t,
                   ROUND(AVG(stress_relacionamento),1) AS stress_r, ROUND(AVG(cigarros),1) AS cigarros,
                   ROUND(AVG(desempenho_social),1) AS social
            FROM checkins WHERE user_id = $1
              AND data >= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date - 13
              AND data <  (NOW() AT TIME ZONE 'America/Sao_Paulo')::date - 6
            """,
            user_id,
        )
    return dict(row) if row else {}


async def get_heatmap_30d(pool, user_id=1) -> dict:  # TODO: auth
    """Retorna dict {date: saude_mental} dos últimos 30 dias."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT data, saude_mental FROM checkins
            WHERE user_id = $1 AND data >= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date - 29
            ORDER BY data ASC
            """,
            user_id,
        )
    return {r["data"]: r["saude_mental"] for r in rows}


async def get_remedios(pool, user_id=1) -> list:  # TODO: auth
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT ON (nome) id, nome, dose_padrao, tipo FROM remedios "
            "WHERE user_id = $1 AND ativo = TRUE ORDER BY nome, id",
            user_id,
        )
    return [dict(r) for r in rows]


async def get_contextos(pool, user_id=1) -> list:  # TODO: auth
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, label, ativo FROM contextos_config WHERE user_id = $1 ORDER BY ordem, id",
            user_id,
        )
    return [dict(r) for r in rows]


async def get_campos_config(pool, user_id=1) -> dict:  # TODO: auth
    """Retorna dict {campo: {ativo, baseline, padrao_atual, ...}}."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT campo, ativo, ordem, padrao_atual, baseline, padrao_min, padrao_max "
            "FROM campos_config WHERE user_id = $1 ORDER BY ordem",
            user_id,
        )
    return {r["campo"]: dict(r) for r in rows}


async def get_session_hoje(pool, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM checkin_sessions WHERE user_id=$1 "
            "AND data_referencia=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date "
            "ORDER BY id DESC LIMIT 1",
            user_id,
        )
    return dict(row) if row else None


async def get_checkins_tendencia(pool, user_id=1, dias=30) -> list:  # TODO: auth
    """Retorna checkins dos últimos N dias (ordem cronológica ascendente)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT data, dor_fisica, energia, sono_horas, sono_qualidade,
                   saude_mental, stress_trabalho, stress_relacionamento,
                   desempenho_social, remedios_tomados
            FROM checkins WHERE user_id = $1
              AND data >= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date - $2
            ORDER BY data ASC
            """,
            user_id,
            dias - 1,
        )
    return [dict(r) for r in rows]


async def update_remed_hoje(pool, nome: str, delta: float, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT remedios_tomados FROM checkins WHERE user_id=$1 "
            "AND data=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date",
            user_id,
        )
        if row is None:
            qtd = max(0.0, delta)
            arr = [{"nome": nome, "qtd": qtd, "tomado": qtd > 0}]
            await conn.execute(
                "INSERT INTO checkins (user_id, data, remedios_tomados) "
                "VALUES ($1, (NOW() AT TIME ZONE 'America/Sao_Paulo')::date, $2::jsonb) "
                "ON CONFLICT DO NOTHING",
                user_id,
                json.dumps(arr),
            )
        else:
            rj = row["remedios_tomados"]
            try:
                arr = (rj if isinstance(rj, list) else json.loads(rj)) if rj else []
            except Exception:
                arr = []
            found = False
            for item in arr:
                if item.get("nome") == nome:
                    item["qtd"] = max(0.0, float(item.get("qtd", 0)) + delta)
                    item["tomado"] = item["qtd"] > 0
                    found = True
                    break
            if not found:
                qtd = max(0.0, delta)
                arr.append({"nome": nome, "qtd": qtd, "tomado": qtd > 0})
            await conn.execute(
                "UPDATE checkins SET remedios_tomados=$1::jsonb WHERE user_id=$2 "
                "AND data=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date",
                json.dumps(arr),
                user_id,
            )


async def toggle_contexto_hoje(pool, label: str, user_id=1) -> list:  # TODO: auth
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT contextos_dia FROM checkins WHERE user_id=$1 "
            "AND data=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date",
            user_id,
        )
        if row is None:
            ctx = [label]
            await conn.execute(
                "INSERT INTO checkins (user_id, data, contextos_dia) "
                "VALUES ($1, (NOW() AT TIME ZONE 'America/Sao_Paulo')::date, $2::jsonb) "
                "ON CONFLICT (user_id, data) DO UPDATE SET contextos_dia=$2::jsonb",
                user_id,
                json.dumps(ctx),
            )
        else:
            cd = row["contextos_dia"]
            try:
                ctx = (cd if isinstance(cd, list) else json.loads(cd)) if cd else []
            except Exception:
                ctx = []
            if label in ctx:
                ctx.remove(label)
            else:
                ctx.append(label)
            await conn.execute(
                "UPDATE checkins SET contextos_dia=$1::jsonb WHERE user_id=$2 "
                "AND data=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date",
                json.dumps(ctx),
                user_id,
            )
    return ctx


async def update_alimentacao_hoje(pool, valor: int, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO checkins (user_id, data, alimentacao)
               VALUES ($1, (NOW() AT TIME ZONE 'America/Sao_Paulo')::date, $2)
               ON CONFLICT (user_id, data) DO UPDATE SET alimentacao=$2""",
            user_id,
            valor,
        )


async def save_nota(pool, texto: str, data_alvo, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO checkins (user_id, data, nota_raw)
               VALUES ($1, $2, $3)
               ON CONFLICT (user_id, data) DO UPDATE SET nota_raw=$3""",
            user_id,
            data_alvo,
            texto,
        )


async def save_nota_analysis(pool, sentimento: str, categorias: str, resumo: str, data_alvo, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE checkins SET nota_sentimento=$1, nota_categorias=$2::jsonb, nota_resumo_ia=$3 "
            "WHERE user_id=$4 AND data=$5",
            sentimento,
            categorias,
            resumo,
            user_id,
            data_alvo,
        )


async def editar_checkin(pool, data, campos: dict, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE checkins SET
              dor_fisica=$2, energia=$3, sono_horas=$4, sono_qualidade=$5,
              saude_mental=$6, stress_trabalho=$7, stress_relacionamento=$8,
              alcool=$9, exercicio=$10, cigarros=$11, desempenho_social=$12,
              remedios_tomados=COALESCE($13::jsonb, remedios_tomados),
              alimentacao=$14,
              nota_raw=CASE WHEN $15 != '' THEN $15 ELSE nota_raw END,
              contextos_dia=$16::jsonb
            WHERE user_id=$1 AND data=$17
            """,
            user_id,
            campos.get("dor_fisica"),
            campos.get("energia"),
            campos.get("sono_horas"),
            campos.get("sono_qualidade"),
            campos.get("saude_mental"),
            campos.get("stress_trabalho"),
            campos.get("stress_relacionamento"),
            campos.get("alcool"),
            campos.get("exercicio"),
            campos.get("cigarros"),
            campos.get("desempenho_social"),
            campos.get("remed_json"),
            campos.get("alimentacao"),
            campos.get("nota_raw", ""),
            campos.get("ctx_json", "[]"),
            data,
        )


async def remover_checkin(pool, data, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM checkins WHERE user_id=$1 AND data=$2", user_id, data)
        await conn.execute(
            "DELETE FROM checkin_sessions WHERE user_id=$1 AND data_referencia=$2", user_id, data
        )


# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

async def toggle_campo_config(pool, campo: str, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE campos_config SET ativo = NOT ativo WHERE campo=$1 AND user_id=$2",
            campo,
            user_id,
        )


async def toggle_contexto_config(pool, id: int, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE contextos_config SET ativo = NOT ativo WHERE id=$1 AND user_id=$2",
            id,
            user_id,
        )


async def add_contexto_config(pool, label: str, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO contextos_config (user_id, label, ordem) VALUES ($1, $2, 99) ON CONFLICT DO NOTHING",
            user_id,
            label,
        )


async def remove_contexto_config(pool, id: int, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM contextos_config WHERE id=$1 AND user_id=$2", id, user_id
        )


async def get_campos_custom(pool, user_id=1) -> list:  # TODO: auth
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                "SELECT id, nome, tipo_input, opcoes_texto, ativo FROM campos_custom "
                "WHERE user_id = $1 ORDER BY id",
                user_id,
            )
            return [dict(r) for r in rows]
        except Exception:
            return []


async def add_campo_custom(pool, nome: str, tipo_input: str, opcoes_texto: str, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS campos_custom (
               id SERIAL PRIMARY KEY, user_id INT, nome TEXT NOT NULL,
               tipo_input TEXT DEFAULT 'escala_1_5', opcoes_texto TEXT,
               ativo BOOLEAN DEFAULT TRUE, criado_em TIMESTAMP DEFAULT NOW())"""
        )
        await conn.execute(
            "INSERT INTO campos_custom (user_id, nome, tipo_input, opcoes_texto) VALUES ($1, $2, $3, $4)",
            user_id,
            nome,
            tipo_input,
            opcoes_texto or None,
        )


async def toggle_campo_custom(pool, id: int, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE campos_custom SET ativo = NOT ativo WHERE id=$1 AND user_id=$2", id, user_id
        )


async def editar_campo_custom(pool, id: int, nome: str, tipo_input: str, opcoes_texto: str, user_id=1):  # TODO: auth
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE campos_custom SET nome=$1, tipo_input=$2, opcoes_texto=$3 WHERE id=$4 AND user_id=$5",
            nome,
            tipo_input,
            opcoes_texto or None,
            id,
            user_id,
        )


async def get_contextos_config_all(pool, user_id=1) -> list:  # TODO: auth
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, label, ativo, ordem FROM contextos_config WHERE user_id=$1 ORDER BY ordem, id",
            user_id,
        )
    return [dict(r) for r in rows]
