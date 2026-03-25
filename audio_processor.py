import asyncio
import json
import os
import tempfile
from datetime import date, timedelta

import httpx
from openai import AsyncOpenAI

from config import OPENAI_API_KEY, WHAPI_TOKEN
from database import get_pool
from whapi import send_message


async def process_audio(
    audio_id: str,
    sender: str,
    user_id: int,
    session_id: int,
    data_referencia: date,
):
    ogg_path = None
    mp3_path = None
    try:
        # Download audio from Whapi
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://gate.whapi.cloud/media/{audio_id}",
                headers={"Authorization": f"Bearer {WHAPI_TOKEN}"},
                timeout=30,
            )
            r.raise_for_status()

        fd, ogg_path = tempfile.mkstemp(suffix=".ogg")
        with os.fdopen(fd, "wb") as f:
            f.write(r.content)

        mp3_path = ogg_path[:-4] + ".mp3"

        # Convert ogg -> mp3 with ffmpeg
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", ogg_path, mp3_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError("ffmpeg conversion failed")

        # Transcribe with Whisper
        ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        with open(mp3_path, "rb") as f:
            transcription = await ai.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        nota_raw = transcription.text

        # Analyze with GPT-4o-mini
        resp = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Analise o texto e retorne JSON com exatamente estas chaves: "
                        "resumo (string curta), sentimento (positivo/neutro/negativo), "
                        "categorias (lista de strings). Responda APENAS com JSON válido."
                    ),
                },
                {"role": "user", "content": nota_raw},
            ],
            response_format={"type": "json_object"},
        )
        analysis = json.loads(resp.choices[0].message.content)
        resumo = analysis.get("resumo", "")
        sentimento = analysis.get("sentimento", "")
        categorias = analysis.get("categorias", [])

        # Save to checkins
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO checkins (user_id, data, nota_raw, nota_sentimento, nota_categorias)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id, data) DO UPDATE SET
                  nota_raw = $3, nota_sentimento = $4, nota_categorias = $5
                """,
                user_id, data_referencia, nota_raw, sentimento, categorias,
            )
            # Close session
            await conn.execute(
                "UPDATE checkin_sessions "
                "SET status = 'concluido', concluido_em = NOW(), "
                "duracao_segundos = EXTRACT(EPOCH FROM (NOW() - iniciado_em))::INT "
                "WHERE id = $1",
                session_id,
            )
            # Update streak only for today's check-in
            if data_referencia == date.today():
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

        await send_message(sender, f"✅ Check-in concluído.\n\n📝 {resumo}\nSentimento: {sentimento}")

    except Exception:
        await send_message(sender, "Não foi possível processar o áudio. Tente novamente ou escolha Texto.")

    finally:
        if ogg_path and os.path.exists(ogg_path):
            os.remove(ogg_path)
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)
