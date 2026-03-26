from datetime import date, timedelta
from fastapi import APIRouter, BackgroundTasks, Request
from config import MY_WHATSAPP
from database import get_pool
from whapi import send_message, send_buttons
from db_session import get_or_create_session, get_active_session, get_completed_session
from checkin_flow import get_pergunta_inicial, get_pergunta_por_passo, get_proximo_passo
router = APIRouter()


def _parse_value(content: str, pergunta: dict):
    if pergunta["tipo_input"] == "escala_0_10":
        try:
            v = int(str(content).strip())
            return v if 0 <= v <= 10 else None
        except (ValueError, TypeError):
            return None
    return content


@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    if not MY_WHATSAPP:
        return {"status": "ignored"}

    body = await request.json()

    # Suporte a chats_updates (self-messages e grupos via Whapi)
    msg = None
    if body.get("messages"):
        msg = body["messages"][0]
    elif body.get("chats_updates"):
        last = (body["chats_updates"][0].get("after_update") or {}).get("last_message")
        if last and last.get("from_me"):
            chat_id = last.get("chat_id", "")
            is_group = "@g.us" in chat_id
            is_self_chat = last.get("from") == MY_WHATSAPP
            if is_group or is_self_chat:
                msg = last
    if not msg:
        return {"status": "ignored"}

    sender = msg.get("from") or msg.get("chat_id", "").split("@")[0]
    reply_to = msg.get("chat_id") or sender  # grupos: chat_id = "...@g.us"

    if sender != MY_WHATSAPP:
        return {"status": "ignored"}

    msg_type = msg.get("type", "outro")

    if msg_type == "text":
        content = msg.get("text", {}).get("body")
    elif msg_type == "button_reply":
        content = msg.get("button_reply", {}).get("title")
    elif msg_type == "list_reply":
        content = msg.get("list_reply", {}).get("title")
    elif msg_type == "audio":
        audio_id = msg.get("audio", {}).get("id")
        if audio_id:
            pool = get_pool()
            async with pool.acquire() as conn:
                _user = await conn.fetchrow(
                    "SELECT id FROM usuarios WHERE whatsapp = $1", sender
                )
            if _user:
                _uid = _user["id"]
                _active = await get_active_session(_uid, date.today())
                if not _active:
                    _active = await get_active_session(_uid, date.today() - timedelta(days=1))
                if _active and _active["passo_atual"] == 13:
                    try:
                        from audio_processor import process_audio
                        await send_message(reply_to, "🎤 Áudio recebido, processando...")
                        background_tasks.add_task(
                            process_audio, audio_id, sender, _uid,
                            _active["id"], _active["data_referencia"],
                        )
                        return {"status": "ok", "type": "audio_processing"}
                    except ImportError:
                        await send_message(reply_to, "Processamento de áudio indisponível no momento. Escolha Texto ou Pular.")
                        return {"status": "ok", "type": "audio_unavailable"}
        return {"status": "ok", "sender": sender, "type": "audio", "content": audio_id}
    else:
        return {"status": "ok", "sender": sender, "type": "outro", "content": None}

    # text, button_reply ou list_reply a partir daqui
    pool = get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM usuarios WHERE whatsapp = $1", sender
        )

    if not user:
        return {"status": "user_not_found"}

    user_id = user["id"]

    cmd = content.strip() if content else ""

    if cmd == "/streak":
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT streak_atual, streak_maximo FROM streak WHERE user_id = $1", user_id
            )
        if row:
            await send_message(reply_to, f"🔥 Sequência atual: {row['streak_atual']} dias | Máximo: {row['streak_maximo']} dias")
        else:
            await send_message(reply_to, "Nenhum streak registrado ainda.")
        return {"status": "comando_streak"}

    if cmd == "/resumo":
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                  COUNT(*)                        AS dias,
                  ROUND(AVG(dor_fisica), 1)       AS dor,
                  ROUND(AVG(energia), 1)          AS energia,
                  ROUND(AVG(sono_horas), 1)       AS sono_h,
                  ROUND(AVG(sono_qualidade), 1)   AS sono_q,
                  ROUND(AVG(saude_mental), 1)     AS mental,
                  ROUND(AVG(stress_trabalho), 1)  AS stress,
                  ROUND(AVG(cigarros), 1)         AS cigarros
                FROM checkins
                WHERE user_id = $1 AND data >= CURRENT_DATE - 6
                """,
                user_id,
            )
        if not row or not row["dias"]:
            await send_message(reply_to, "Nenhum registro nos últimos 7 dias.")
        else:
            msg = (
                f"📊 Últimos 7 dias ({row['dias']} registros)\n\n"
                f"🩺 Dor: {row['dor']}  ⚡ Energia: {row['energia']}\n"
                f"😴 Sono: {row['sono_h']}h / qualidade {row['sono_q']}\n"
                f"🧠 Mental: {row['mental']}  💼 Stress trab: {row['stress']}\n"
                f"🚬 Cigarros: {row['cigarros']}"
            )
            await send_message(reply_to, msg)
        return {"status": "comando_resumo"}

    if cmd == "/remedios":
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT nome, dose, dose_padrao FROM remedios WHERE user_id = $1 AND ativo = TRUE ORDER BY id",
                user_id,
            )
        if not rows:
            await send_message(reply_to, "Nenhum remédio cadastrado.")
        else:
            linhas = []
            for r in rows:
                dose_str = f" ({r['dose']})" if r["dose"] else ""
                linhas.append(f"💊 {r['nome']}{dose_str} — padrão: {r['dose_padrao']}")
            await send_message(reply_to, "Remédios ativos:\n" + "\n".join(linhas))
        return {"status": "comando_remedios"}

    if cmd == "/ontem":
        ontem = date.today() - timedelta(days=1)
        async with pool.acquire() as conn:
            sessao_ontem = await conn.fetchrow(
                "SELECT id, status, passo_atual FROM checkin_sessions "
                "WHERE user_id = $1 AND data_referencia = $2 LIMIT 1",
                user_id, ontem,
            )
        if sessao_ontem:
            if sessao_ontem["status"] == "concluido":
                await send_message(reply_to, "Já existe check-in para ontem. ✅")
                return {"status": "ontem_ja_concluido"}
            if sessao_ontem["status"] == "em_andamento":
                pergunta = get_pergunta_por_passo(sessao_ontem["passo_atual"])
                if pergunta:
                    ok = await send_buttons(reply_to, pergunta["label"], pergunta["opcoes_json"])
                    if not ok:
                        await send_message(reply_to, pergunta["label"])
                return {"status": "ontem_retomado"}
            # cancelado ou abandonado — reativar
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE checkin_sessions SET status = 'em_andamento', passo_atual = 1, "
                    "retroativo_ontem = TRUE, atualizado_em = NOW() WHERE id = $1",
                    sessao_ontem["id"],
                )
        else:
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO checkin_sessions (user_id, data_referencia, status, passo_atual, retroativo_ontem) "
                    "VALUES ($1, $2, 'em_andamento', 1, TRUE)",
                    user_id, ontem,
                )
        pergunta = get_pergunta_inicial()
        if pergunta:
            ok = await send_buttons(reply_to, pergunta["label"], pergunta["opcoes_json"])
            if not ok:
                await send_message(reply_to, pergunta["label"])
        return {"status": "ontem_iniciado"}

    if cmd == "/congelar":
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS total FROM streak_congelamentos
                WHERE user_id = $1
                  AND date_trunc('month', data) = date_trunc('month', CURRENT_DATE)
                """,
                user_id,
            )
        count = row["total"] if row else 0
        if count >= 3:
            await send_message(reply_to, "Você já usou 3 congelamentos este mês.")
            return {"status": "congelar_limite"}
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO streak_congelamentos (user_id, data) VALUES ($1, CURRENT_DATE) "
                "ON CONFLICT DO NOTHING",
                user_id,
            )
        restantes = 2 - count
        await send_message(reply_to, f"Streak congelado hoje. Você tem {restantes} congelamento(s) restante(s) este mês.")
        return {"status": "congelar_ok"}

    if cmd == "/cancelar":
        active = await get_active_session(user_id, date.today())
        if active:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE checkin_sessions SET status = 'cancelado', atualizado_em = NOW() "
                    "WHERE id = $1",
                    active["id"],
                )
            await send_message(reply_to, "Check-in cancelado. Você pode retomar quando quiser com /checkin.")
            return {"status": "cancelled"}
        await send_message(reply_to, "Nenhum check-in em andamento.")
        return {"status": "no_active_session"}

    active = await get_active_session(user_id, date.today())
    if not active:
        active = await get_active_session(user_id, date.today() - timedelta(days=1))

    if active and active["passo_atual"] >= 1:
        pergunta = get_pergunta_por_passo(active["passo_atual"])
        if pergunta and pergunta["tipo_input"] == "remedios":
            proximo_passo = get_proximo_passo(active["passo_atual"])
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE checkin_sessions SET passo_atual = $2, atualizado_em = NOW() "
                    "WHERE id = $1",
                    active["id"], proximo_passo or 0,
                )
            proxima = get_pergunta_por_passo(proximo_passo) if proximo_passo else None
            if proxima:
                ok = await send_buttons(reply_to, proxima["label"], proxima["opcoes_json"])
                if not ok:
                    ok = await send_message(reply_to, proxima["label"])
                return {"status": "ok", "skipped": "remedios"}
            return {"status": "invalid_answer"}

        valor = _parse_value(content, pergunta)
        if valor is not None and pergunta["tipo_input"] == "numerico":
            try:
                float(str(valor).strip())
            except (ValueError, TypeError):
                valor = None
        elif valor is not None and pergunta["tipo_input"] == "opcoes":
            if str(valor) not in [str(o) for o in pergunta["opcoes_json"]]:
                valor = None
        elif pergunta["tipo_input"] == "nota_livre":
            valor = content  # qualquer conteúdo é válido
        if valor is None:
            ok = await send_buttons(reply_to, pergunta["label"], pergunta["opcoes_json"])
            if not ok:
                await send_message(reply_to, pergunta["label"])
            return {"status": "invalid_answer"}

        campo = pergunta["campo"]

        # Seleção de "Áudio" no passo 13 — manter sessão no passo e aguardar o áudio
        if campo == "nota" and str(valor).strip() == "Áudio":
            await send_message(reply_to, "Pode enviar o áudio agora. 🎤")
            return {"status": "ok", "aguardando_audio": True}

        proximo_passo = get_proximo_passo(active["passo_atual"])
        _prox = get_pergunta_por_passo(proximo_passo) if proximo_passo else None
        if _prox and _prox["tipo_input"] == "remedios":
            proximo_passo = get_proximo_passo(proximo_passo)
        async with pool.acquire() as conn:
            if campo == "nota":
                if str(valor).strip() != "Pular":
                    await conn.execute(
                        "INSERT INTO checkins (user_id, data, nota_raw) VALUES ($1, $2, $3) "
                        "ON CONFLICT (user_id, data) DO UPDATE SET nota_raw = $3",
                        user_id, active["data_referencia"], str(valor),
                    )
            else:
                await conn.execute(
                    f"INSERT INTO checkins (user_id, data, {campo}) VALUES ($1, $2, $3) "
                    f"ON CONFLICT (user_id, data) DO UPDATE SET {campo} = $3",
                    user_id, active["data_referencia"], valor,
                )
            await conn.execute(
                "UPDATE checkin_sessions SET passo_atual = $2, atualizado_em = NOW() "
                "WHERE id = $1",
                active["id"], proximo_passo or 0,
            )

        proxima = get_pergunta_por_passo(proximo_passo) if proximo_passo else None

        if proxima:
            ok = await send_buttons(reply_to, proxima["label"], proxima["opcoes_json"])
            if not ok:
                ok = await send_message(reply_to, proxima["label"])
        else:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE checkin_sessions "
                    "SET status = 'concluido', concluido_em = NOW(), "
                    "duracao_segundos = EXTRACT(EPOCH FROM (NOW() - iniciado_em))::INT "
                    "WHERE id = $1",
                    active["id"],
                )
                if active["data_referencia"] == date.today():
                    ontem = date.today() - timedelta(days=1)
                    await conn.execute(
                        """
                        INSERT INTO streak (user_id, streak_atual, streak_maximo, ultimo_checkin, atualizado_em)
                        VALUES ($1, 1, 1, $2, NOW())
                        ON CONFLICT (user_id) DO UPDATE
                        SET streak_atual = CASE
                                WHEN streak.ultimo_checkin = $3 THEN streak.streak_atual + 1
                                ELSE 1
                            END,
                            streak_maximo = GREATEST(streak.streak_maximo,
                                CASE
                                    WHEN streak.ultimo_checkin = $3 THEN streak.streak_atual + 1
                                    ELSE 1
                                END),
                            ultimo_checkin = $2,
                            atualizado_em = NOW()
                        """,
                        user_id, date.today(), ontem,
                    )
            await send_message(reply_to, "✅ Check-in de hoje concluído. Até amanhã!")
            return {"status": "checkin_completed", "session_status": "concluido"}

        return {
            "status": "ok" if ok else "send_failed",
            "user_id": user_id,
            "session_id": active["id"],
            "session_status": active["status"],
            "passo_atual": proximo_passo,
            "resposta_salva": True,
            "campo_salvo": campo,
            "valor_salvo": valor,
            "proximo_passo": proximo_passo,
            "proxima_pergunta_campo": proxima["campo"],
            "proxima_pergunta_label": proxima["label"],
        }

    # sem sessão ativa — verificar se já concluiu hoje antes de criar nova
    if await get_completed_session(user_id, date.today()):
        await send_message(reply_to, "Você já fez o check-in de hoje. ✅")
        return {"status": "already_completed"}

    if not content or content.strip() != "/checkin":
        return {"status": "ignored"}

    session = await get_or_create_session(user_id, date.today())
    pergunta = get_pergunta_inicial()
    if not pergunta:
        return {"status": "no_question"}

    ok = await send_buttons(reply_to, pergunta["label"], pergunta["opcoes_json"])
    if not ok:
        ok = await send_message(reply_to, pergunta["label"])

    return {
        "status": "ok" if ok else "send_failed",
        "user_id": user_id,
        "session_id": session["id"],
        "session_status": session["status"],
        "passo_atual": session["passo_atual"],
        "pergunta_campo": pergunta["campo"],
        "pergunta_label": pergunta["label"],
    }
