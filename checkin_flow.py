# Definição estática dos campos do check-in.
# ordem e ativo espelham o seed de campos_config.
# label, tipo_input, opcoes_json e obrigatorio são metadados de UX
# não armazenados no banco.

PERGUNTAS = [
    {
        "campo": "dor_fisica",
        "label": "Dor física",
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 1,
        "ativo": True,
    },
    {
        "campo": "energia",
        "label": "Energia",
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 2,
        "ativo": True,
    },
    {
        "campo": "sono_horas",
        "label": "Sono — horas",
        "tipo_input": "numerico",
        "opcoes_json": [4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 3,
        "ativo": True,
    },
    {
        "campo": "sono_qualidade",
        "label": "Sono — qualidade",
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 4,
        "ativo": True,
    },
    {
        "campo": "exercicio",
        "label": "Exercício",
        "tipo_input": "opcoes",
        "opcoes_json": ["Corrida", "Caminhada", "Natação", "Nenhum"],
        "obrigatorio": False,
        "ordem": 5,
        "ativo": False,
    },
    {
        "campo": "saude_mental",
        "label": "Saúde mental",
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 6,
        "ativo": True,
    },
    {
        "campo": "stress_trabalho",
        "label": "Stress trabalho",
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 7,
        "ativo": True,
    },
    {
        "campo": "stress_relacionamento",
        "label": "Stress relacionamento",
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 8,
        "ativo": True,
    },
    {
        "campo": "alcool",
        "label": "Álcool",
        "tipo_input": "opcoes",
        "opcoes_json": ["Nenhum", "Pouco", "Moderado", "Muito"],
        "obrigatorio": True,
        "ordem": 9,
        "ativo": True,
    },
    {
        "campo": "cigarros",
        "label": "Cigarros",
        "tipo_input": "numerico",
        "opcoes_json": [0, 1, 2, 3, 5, 8, 10],
        "obrigatorio": True,
        "ordem": 10,
        "ativo": True,
    },
    {
        "campo": "desempenho_social",
        "label": "Desempenho social",
        "tipo_input": "escala_0_10",
        "opcoes_json": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "obrigatorio": True,
        "ordem": 11,
        "ativo": True,
    },
    {
        "campo": "remedios",
        "label": "Remédios",
        "tipo_input": "remedios",
        "opcoes_json": [],
        "obrigatorio": False,
        "ordem": 12,
        "ativo": True,
    },
    {
        "campo": "nota",
        "label": "Nota do dia",
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
