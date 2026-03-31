"""
Processamento de notas via OpenAI — análise de sentimento e resumo.
"""

import json


async def process_nota(texto: str, openai_key: str) -> dict:
    """
    Analisa um relato diário e retorna {resumo, sentimento, categorias, insights}.
    Retorna {} se não houver chave ou texto vazio.
    """
    if not openai_key or not texto.strip():
        return {}
    try:
        from openai import AsyncOpenAI
        ai = AsyncOpenAI(api_key=openai_key)
        resp = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é um psicólogo analista de saúde mental. Analise o relato diário e retorne JSON com: "
                        "resumo (frase curta, acolhedora, 1a pessoa, máx 90 chars), "
                        "sentimento (positivo/neutro/negativo), "
                        "categorias (lista de até 5 temas reutilizáveis em português, "
                        "ex: ansiedade, sono, trabalho, relacionamento, humor, dor, energia, medicação, exercício), "
                        "insights (lista de até 2 observações curtas e úteis do ponto de vista de saúde mental). "
                        "Responda APENAS com JSON válido."
                    ),
                },
                {"role": "user", "content": texto},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {}
