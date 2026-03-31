"""
Funções auxiliares puras — sem I/O, sem HTML inline direto (apenas valores/classes).
"""

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}


def data_formatada(d) -> str:
    """Retorna 'DD de mês' em português. Ex: '29 de março'"""
    if d is None:
        return "sem dados"
    try:
        day = d.day
        month_name = MESES_PT.get(d.month, "")
        return f"{day} de {month_name}"
    except Exception:
        return str(d)


def score_color(v, invert=False) -> str:
    """Retorna cor hex baseada em valor 0-5."""
    if v is None:
        return "#4A4A5A"
    pct = float(v) / 5
    if invert:
        if pct <= 0.3:
            return "#86EFAC"
        if pct <= 0.6:
            return "#FCD34D"
        return "#FCA5A5"
    else:
        if pct >= 0.7:
            return "#86EFAC"
        if pct >= 0.4:
            return "#FCD34D"
        return "#FCA5A5"


def score_color_class(v, baseline=None, invert=False) -> str:
    """Retorna classe CSS: good / warn / low / neutral."""
    if v is None:
        return "neutral"
    v = float(v)
    if baseline is not None:
        try:
            b = float(baseline)
            if b == 0:
                return "neutral"
            pct_diff = (v - b) / b
            if invert:
                pct_diff = -pct_diff
            if pct_diff >= 0.3:
                return "good"
            if pct_diff <= -0.3:
                return "low"
            return "neutral"
        except Exception:
            pass
    pct = v / 5
    if invert:
        if pct <= 0.3:
            return "good"
        if pct <= 0.6:
            return "warn"
        return "low"
    else:
        if pct >= 0.7:
            return "good"
        if pct >= 0.4:
            return "warn"
        return "low"


def trend_arrow(rows, field) -> str:
    """Retorna 'up', 'down' ou 'flat' baseado na tendência dos últimos N registros."""
    vals = [r[field] for r in rows if r.get(field) is not None]
    if len(vals) < 3:
        return "flat"
    mid = len(vals) // 2
    recent = sum(vals[:mid]) / mid
    older = sum(vals[mid:]) / (len(vals) - mid)
    diff = recent - older
    if abs(diff) < 0.3:
        return "flat"
    return "up" if diff > 0 else "down"


def hero_frase(mental, energia, dor) -> str:
    if mental is None:
        return "Seus dados vão aparecer aqui depois do próximo check-in."
    m = float(mental)
    e = float(energia) if energia is not None else 3
    d = float(dor) if dor is not None else 1
    if m >= 4 and e >= 4:
        return "Você esteve bem hoje. Isso importa."
    if m >= 3 and d <= 2:
        return "Um dia razoável. Você está acompanhando."
    if m <= 2 and d >= 4:
        return "Foi um dia mais pesado. Tudo registrado, tudo bem."
    if m <= 2:
        return "Nem todo dia é fácil. Você está aqui, isso já é algo."
    if d >= 4:
        return "Seu corpo pediu atenção hoje. Registrado."
    return "Mais um dia acompanhado. Obrigado por estar aqui."


def saudacao_contextual(hora: int, mental, energia, dor) -> str:
    """Saudação com contexto de saúde: 'Boa noite — energia baixa hoje'."""
    base = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 18 else "Boa noite")
    if mental is None:
        return base
    m = float(mental) if mental is not None else None
    e = float(energia) if energia is not None else None
    d = float(dor) if dor is not None else None
    if e is not None and e <= 2:
        return f"{base} — energia baixa hoje"
    if d is not None and d >= 4:
        return f"{base} — dor registrada hoje"
    if m is not None and m >= 4:
        return f"{base} — você está bem hoje"
    if m is not None and m <= 2:
        return f"{base} — dia mais pesado hoje"
    return base


def streak_frase(atual: int, maximo: int) -> str:
    if atual == 0:
        return "Novo começo. O dia 1 já é progresso."
    if atual == 1:
        return "Começou. Um dia de cada vez."
    if atual >= 30:
        return f"{atual} dias. Um mês inteiro de dados sobre você mesmo."
    if atual >= 14:
        return f"{atual} dias seguidos. Isso já é consistência real."
    if atual >= 7:
        return f"{atual} dias. Uma semana completa."
    return f"{atual} dias seguidos. Você está construindo algo."


def alim_label(v) -> str:
    if v is None:
        return "—"
    v = int(v)
    if v <= 1:
        return "Besteira"
    if v <= 2:
        return "Ruim"
    if v <= 3:
        return "Regular"
    if v <= 4:
        return "Boa"
    return "Saudável"


def sent_badge_class(s: str) -> str:
    """Retorna classe CSS para badge de sentimento."""
    if not s:
        return ""
    m = {"positivo": "sent-pos", "neutro": "sent-neu", "negativo": "sent-neg"}
    return m.get(s.lower(), "")


def dot_color(mental) -> str:
    if mental is None:
        return "#2A2A38"
    v = float(mental)
    if v >= 4:
        return "#86EFAC"
    if v >= 3:
        return "#A78BFA"
    if v >= 2:
        return "#FCD34D"
    return "#FCA5A5"


def calcular_chips_historico(r: dict, baselines: dict) -> list:
    """
    Retorna lista de chips para a linha do histórico.
    Cada chip: {label, value, status_class}
    baselines: {'saude_mental': '7', 'energia': '6', ...}
    """
    chips = []
    me = r.get("saude_mental")
    en = r.get("energia")
    sh = r.get("sono_horas")
    dor = r.get("dor_fisica")
    al = r.get("alcool") or ""
    ex = r.get("exercicio") or ""
    alim = r.get("alimentacao")

    if me is not None:
        sc = score_color_class(me, baselines.get("saude_mental"), invert=False)
        chips.append({"label": "humor", "value": str(me), "status_class": sc})
    if en is not None:
        sc = score_color_class(en, baselines.get("energia"), invert=False)
        chips.append({"label": "energia", "value": str(en), "status_class": sc})
    if sh is not None:
        chips.append({"label": "sono", "value": f"{sh}h", "status_class": "neutral"})
    if dor is not None:
        sc = score_color_class(dor, baselines.get("dor_fisica"), invert=True)
        chips.append({"label": "dor", "value": str(dor), "status_class": sc})
    if al and al != "Nenhum":
        chips.append({"label": "", "value": al, "status_class": "neutral"})
    if ex and ex != "Nenhum":
        chips.append({"label": "", "value": ex, "status_class": "neutral"})
    if alim is not None:
        chips.append({"label": "alim", "value": str(alim), "status_class": "neutral"})
    return chips


def calcular_delta(atual, anterior, invert=False) -> dict:
    """
    Calcula delta entre valor atual e anterior.
    Retorna {valor: str, classe: str, sinal: str}
    """
    if atual is None or anterior is None:
        return {"valor": "", "classe": "neutral", "sinal": ""}
    try:
        diff = float(atual) - float(anterior)
    except Exception:
        return {"valor": "", "classe": "neutral", "sinal": ""}
    if abs(diff) < 0.3:
        return {"valor": f"{diff:+.1f}", "classe": "neutral", "sinal": "→"}
    if diff > 0:
        cls = "low" if invert else "good"
        return {"valor": f"{diff:+.1f}", "classe": cls, "sinal": "↑"}
    else:
        cls = "good" if invert else "low"
        return {"valor": f"{diff:+.1f}", "classe": cls, "sinal": "↓"}


def calcular_desvio_consecutivo(hist_doses: list, baseline: float) -> int:
    """
    Conta quantos dias consecutivos (do mais recente para trás) estão acima do baseline.
    hist_doses: lista de (data_str, qtd) ordenada do mais recente para o mais antigo.
    """
    count = 0
    for _, qtd in hist_doses:
        if float(qtd) > baseline:
            count += 1
        else:
            break
    return count
