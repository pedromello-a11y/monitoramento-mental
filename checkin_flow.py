# Definição estática dos campos do check-in.
# ordem e ativo espelham o seed de campos_config.
# label, tipo_input, opcoes_json e obrigatorio são metadados de UX
# não armazenados no banco.

PERGUNTAS = [
    {
        "campo": "dor_fisica",
        "label": (
            "🩺 *Dor física*\n\n"
            "Quanto seu corpo doeu hoje?\n\n"
            "*0* = sem dor\n"
            "*10* = dor intensa, difícil de funcionar\n\n"
            "Escolha um número abaixo."
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
            "⚡ *Energia*\n\n"
            "Como esteve sua energia hoje?\n\n"
            "*0* = sem energia, esgotado\n"
            "*10* = energia no máximo\n\n"
            "Escolha um número abaixo."
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
            "😴 *Sono — horas*\n\n"
            "Quantas horas você dormiu?\n\n"
            "Conte o total real, incluindo cochilos.\n"
            "Ex: 6, 7.5, 8\n\n"
            "Escolha ou digite o valor abaixo."
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
            "🌙 *Qualidade do sono*\n\n"
            "Como foi a qualidade do seu sono?\n\n"
            "*0* = acordou destruído, sem descanso\n"
            "*10* = dormiu muito bem, acordou renovado\n\n"
            "Escolha um número abaixo."
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
            "🏃 *Exercício*\n\n"
            "Você se exercitou hoje?\n\n"
            "Corrida · Caminhada · Natação · Nenhum"
        ),
        "tipo_input": "opcoes",
        "opcoes_json": ["Corrida", "Caminhada", "Natação", "Nenhum"],
        "obrigatorio": False,
        "ordem": 5,
        "ativo": False,
    },
    {
        "campo": "saude_mental",
        "label": (
            "🧠 *Saúde mental*\n\n"
            "Como sua mente esteve hoje no geral?\n\n"
            "Considere ansiedade, clareza, estabilidade e bem-estar.\n\n"
            "*0* = muito mal, funcionamento comprometido\n"
            "*10* = muito bem, mente clara e estável\n\n"
            "Escolha um número abaixo."
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
            "💼 *Stress no trabalho*\n\n"
            "O quanto o trabalho pesou hoje?\n\n"
            "*0* = nenhum stress\n"
            "*10* = dia dominado pelo trabalho\n\n"
            "Escolha um número abaixo."
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
            "❤️ *Stress nos relacionamentos*\n\n"
            "Teve tensão ou desgaste com alguém hoje?\n\n"
            "*0* = nenhum\n"
            "*10* = conflito sério, ocupou muito espaço mental\n\n"
            "Escolha um número abaixo."
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
            "🍺 *Álcool*\n\n"
            "Como foi seu consumo de álcool hoje?\n\n"
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
            "🚬 *Cigarros*\n\n"
            "Quantos cigarros você fumou hoje?\n\n"
            "Digite ou escolha o número exato abaixo."
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
            "👥 *Vida social*\n\n"
            "Como foi sua presença social hoje?\n\n"
            "*0* = em casa o dia todo, sem contato\n"
            "*10* = muita interação social\n\n"
            "Escolha um número abaixo."
        ),
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 11,
        "ativo": True,
    },
    {
        "campo": "remedios",
        "label": "💊 *Remédios*\n\nO que você tomou hoje?",
        "tipo_input": "remedios",
        "opcoes_json": [],
        "obrigatorio": False,
        "ordem": 12,
        "ativo": True,
    },
    {
        "campo": "nota",
        "label": (
            "📝 *Nota do dia*\n\n"
            "Quer registrar algo sobre como foi seu dia?\n\n"
            "🎤 *Áudio* — fala por até 1 minuto, transcrevo pra você\n"
            "✏️ *Texto* — escreve à vontade\n"
            "⏭️ *Pular* — sem nota hoje\n\n"
            "Responda: Áudio, Texto ou Pular."
        ),
        "tipo_input": "nota_livre",
        "opcoes_json": ["Áudio", "Texto", "Pular"],
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
