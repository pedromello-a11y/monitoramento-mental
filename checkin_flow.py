# Definição estática dos campos do check-in.
# ordem e ativo espelham o seed de campos_config.
# label, tipo_input, opcoes_json e obrigatorio são metadados de UX
# não armazenados no banco.
# Emojis: usar apenas BMP (U+0000-U+FFFF) para compatibilidade com grupos WhatsApp.

PERGUNTAS = [
    {
        "campo": "dor_fisica",
        "label": (
            "\u2764 *Dor f\xedsica*\n\n"
            "Quanto seu corpo doeu hoje?\n\n"
            "*0* = sem dor\n"
            "*10* = dor intensa, dif\xedcil de funcionar\n\n"
            "Escolha um n\xfamero abaixo."
        ),
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 1,
        "ativo": True,
    },
    {
        "campo": "energia",
        "label": (
            "\u26a1 *Energia*\n\n"
            "Como esteve sua energia hoje?\n\n"
            "*0* = sem energia, esgotado\n"
            "*10* = energia no m\xe1ximo\n\n"
            "Escolha um n\xfamero abaixo."
        ),
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 2,
        "ativo": True,
    },
    {
        "campo": "sono_horas",
        "label": (
            "\u2605 *Sono \u2014 horas*\n\n"
            "Quantas horas voc\xea dormiu?\n\n"
            "Conte o total real, incluindo cochilos.\n"
            "Ex: 6, 7.5, 8\n\n"
            "Digite o valor (ex: 6, 7.5, 8)."
        ),
        "tipo_input": "numerico",
        "opcoes_json": [4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 3,
        "ativo": True,
    },
    {
        "campo": "sono_qualidade",
        "label": (
            "\u263d *Qualidade do sono*\n\n"
            "Como foi a qualidade do seu sono?\n\n"
            "*0* = acordou destru\xeddo, sem descanso\n"
            "*10* = dormiu muito bem, acordou renovado\n\n"
            "Escolha um n\xfamero abaixo."
        ),
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 4,
        "ativo": True,
    },
    {
        "campo": "exercicio",
        "label": (
            "\u25b6 *Exerc\xedcio*\n\n"
            "Voc\xea se exercitou hoje?\n\n"
            "*0* = Nenhum\n"
            "*1* = Leve (caminhada, alongamento)\n"
            "*2* = Moderado (corrida, academia)\n"
            "*3* = Intenso (treino pesado, competi\xe7\xe3o)"
        ),
        "tipo_input": "opcoes",
        "opcoes_json": ["Nenhum", "Leve", "Moderado", "Intenso"],
        "mapa_numerico": {"0": "Nenhum", "1": "Leve", "2": "Moderado", "3": "Intenso"},
        "obrigatorio": False,
        "ordem": 5,
        "ativo": True,
    },
    {
        "campo": "saude_mental",
        "label": (
            "\u2728 *Sa\xfade mental*\n\n"
            "Como sua mente esteve hoje no geral?\n\n"
            "Considere ansiedade, clareza, estabilidade e bem-estar.\n\n"
            "*0* = muito mal, funcionamento comprometido\n"
            "*10* = muito bem, mente clara e est\xe1vel\n\n"
            "Escolha um n\xfamero abaixo."
        ),
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 6,
        "ativo": True,
    },
    {
        "campo": "stress_trabalho",
        "label": (
            "\u23f0 *Stress no trabalho*\n\n"
            "O quanto o trabalho pesou hoje?\n\n"
            "*0* = nenhum stress\n"
            "*10* = dia dominado pelo trabalho\n\n"
            "Escolha um n\xfamero abaixo."
        ),
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 7,
        "ativo": True,
    },
    {
        "campo": "stress_relacionamento",
        "label": (
            "\u2665 *Stress nos relacionamentos*\n\n"
            "Teve tens\xe3o ou desgaste com algu\xe9m hoje?\n\n"
            "*0* = nenhum\n"
            "*10* = conflito s\xe9rio, ocupou muito espa\xe7o mental\n\n"
            "Escolha um n\xfamero abaixo."
        ),
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 8,
        "ativo": True,
    },
    {
        "campo": "alcool",
        "label": (
            "\u2615 *\xc1lcool*\n\n"
            "Como foi seu consumo de \xe1lcool hoje?\n\n"
            "*0* = Nenhum\n"
            "*1* = Pouco\n"
            "*2* = Moderado\n"
            "*3* = Muito"
        ),
        "tipo_input": "opcoes",
        "opcoes_json": ["Nenhum", "Pouco", "Moderado", "Muito"],
        "mapa_numerico": {"0": "Nenhum", "1": "Pouco", "2": "Moderado", "3": "Muito"},
        "obrigatorio": True,
        "ordem": 9,
        "ativo": True,
    },
    {
        "campo": "cigarros",
        "label": (
            "\u2716 *Cigarros*\n\n"
            "Quantos cigarros voc\xea fumou hoje?\n\n"
            "Digite o n\xfamero exato (ex: 0, 2, 5)."
        ),
        "tipo_input": "numerico",
        "opcoes_json": [0, 1, 2, 3, 5, 8, 10],
        "obrigatorio": True,
        "ordem": 10,
        "ativo": True,
    },
    {
        "campo": "desempenho_social",
        "label": (
            "\u2600 *Vida social*\n\n"
            "Como foi sua presen\xe7a social hoje?\n\n"
            "*0* = em casa o dia todo, sem contato\n"
            "*10* = muita intera\xe7\xe3o social\n\n"
            "Escolha um n\xfamero abaixo."
        ),
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 11,
        "ativo": True,
    },
    {
        "campo": "remedios",
        "label": "\u2665 *Rem\xe9dios*\n\nO que voc\xea tomou hoje?",
        "tipo_input": "remedios",
        "opcoes_json": [],
        "obrigatorio": False,
        "ordem": 12,
        "ativo": True,
    },
    {
        "campo": "nota",
        "label": (
            "\u270f *Nota do dia*\n\n"
            "Quer registrar algo sobre como foi seu dia?\n\n"
            "* \xc1udio* \u2014 fala por at\xe9 1 minuto, transcrevo pra voc\xea\n"
            "* Texto* \u2014 escreve \xe0 vontade\n"
            "* Pular* \u2014 sem nota hoje\n\n"
            "Responda: \xc1udio, Texto ou Pular."
        ),
        "tipo_input": "nota_livre",
        "opcoes_json": ["\xc1udio", "Texto", "Pular"],
        "obrigatorio": False,
        "ordem": 13,
        "ativo": True,
    },
]


def get_pergunta_inicial() -> dict | None:
    ativos = [p for p in PERGUNTAS if p["ativo"]]
    if not ativos:
        return None
    return min(ativos, key=lambda p: p["ordem"])


def get_pergunta_por_passo(passo: int) -> dict | None:
    for p in PERGUNTAS:
        if p["ativo"] and p["ordem"] == passo:
            return p
    return None


def get_total_passos() -> int:
    return sum(1 for p in PERGUNTAS if p["ativo"])


def get_proximo_passo(passo_atual: int) -> int | None:
    proximos = [p["ordem"] for p in PERGUNTAS if p["ativo"] and p["ordem"] > passo_atual]
    return min(proximos) if proximos else None
