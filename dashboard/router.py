"""
Router do dashboard — apenas rotas GET/POST, sem HTML inline.
"""

import json
import html as _html_mod
from datetime import date, datetime, timedelta
import zoneinfo

from fastapi import APIRouter, Form, UploadFile, File, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from config import OPENAI_API_KEY
from database import get_pool

from .helpers import (
    data_formatada, score_color, score_color_class,
    trend_arrow, hero_frase, saudacao_contextual, streak_frase,
    alim_label, sent_badge_class, dot_color,
    calcular_chips_historico, calcular_delta, calcular_desvio_consecutivo,
    MESES_PT,
)
from .queries import (
    get_checkins_semana, get_streak, get_media_semana, get_media_semana_anterior,
    get_heatmap_30d, get_remedios, get_contextos, get_campos_config,
    get_session_hoje, get_checkins_tendencia,
    update_remed_hoje, toggle_contexto_hoje, update_alimentacao_hoje,
    save_nota, save_nota_analysis, editar_checkin, remover_checkin,
    toggle_campo_config, toggle_contexto_config, add_contexto_config,
    remove_contexto_config, get_campos_custom, add_campo_custom,
    toggle_campo_custom, editar_campo_custom, get_contextos_config_all,
)
from .nota_processor import process_nota

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Registrar filtros Jinja2
templates.env.filters["score_color"] = score_color
templates.env.filters["data_pt"] = data_formatada
templates.env.filters["alim_label"] = alim_label
templates.env.filters["sent_badge_class"] = sent_badge_class
templates.env.filters["dot_color"] = dot_color
templates.env.filters["score_color_class"] = score_color_class


# ---------------------------------------------------------------------------
# Helpers internos de preparação de contexto
# ---------------------------------------------------------------------------

def _get_sp_tz():
    return zoneinfo.ZoneInfo("America/Sao_Paulo")

REMED_PRIORITARIOS = {"rivotril", "zolpidem"}

EX_CORES = {"Nenhum": "#2A2A38", "Leve": "#FCD34D", "Moderado": "#86EFAC", "Intenso": "#A78BFA"}
EX_ALTURA = {"Nenhum": 4, "Leve": 16, "Moderado": 28, "Intenso": 40}
EX_ICONE = {"Nenhum": "", "Leve": "🚶", "Moderado": "🏃", "Intenso": "🏃🔥"}

HUMOR_EMOJIS = ["😭", "😕", "😐", "🙂", "😄"]
HUMOR_COLORS = ["#EF4444", "#F97316", "#FCD34D", "#86EFAC", "#22C55E"]
HUMOR_LABELS = ["Muito mal", "Mal", "Regular", "Bem", "Muito bem"]

_CAMPOS_FIXOS_META = {
    "dor_fisica":             {"label": "Dor física",                  "tipo": "escala_1_5",  "emoji": "❤",  "invert": True},
    "energia":                {"label": "Energia",                     "tipo": "escala_1_5",  "emoji": "⚡"},
    "sono_horas":             {"label": "Sono (horas)",                "tipo": "numerico",    "emoji": "★"},
    "sono_qualidade":         {"label": "Qualidade do sono",           "tipo": "escala_1_5",  "emoji": "☽"},
    "exercicio":              {"label": "Exercício",                   "tipo": "opcoes",      "emoji": "▶", "opcoes": "Nenhum, Leve, Moderado, Intenso"},
    "saude_mental":           {"label": "Saúde mental",                "tipo": "escala_1_5",  "emoji": "✨"},
    "stress_trabalho":        {"label": "Stress no trabalho",          "tipo": "escala_1_5",  "emoji": "⏰", "invert": True},
    "stress_relacionamento":  {"label": "Stress nos relacionamentos",  "tipo": "escala_1_5",  "emoji": "♥",  "invert": True},
    "alcool":                 {"label": "Álcool",                      "tipo": "opcoes",      "emoji": "☕", "opcoes": "Nenhum, Pouco, Moderado, Muito"},
    "cigarros":               {"label": "Cigarros",                    "tipo": "numerico",    "emoji": "✖"},
    "desempenho_social":      {"label": "Vida social",                 "tipo": "escala_1_5",  "emoji": "☀"},
    "remedios":               {"label": "Remédios",                    "tipo": "opcoes",      "emoji": "♥"},
    "nota":                   {"label": "Nota do dia",                 "tipo": "opcoes",      "emoji": "✏"},
}


def _parse_json_field(raw, default=None):
    if default is None:
        default = []
    if raw is None:
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def _build_hist_doses(rows, remedios_padrao):
    """Constrói hist_doses por nome de remédio."""
    hist_doses = {}
    for r in rows:
        rj = r.get("remedios_tomados")
        data_str_r = r["data"].strftime("%d/%m")
        try:
            itens = _parse_json_field(rj)
            for item in itens:
                if not item.get("tomado"):
                    continue
                nome = item["nome"]
                qtd = item.get("qtd", 1)
                if nome.lower() in REMED_PRIORITARIOS:
                    if nome not in hist_doses:
                        hist_doses[nome] = []
                    hist_doses[nome].append((data_str_r, qtd))
        except Exception:
            pass
    return hist_doses


def _build_remed_cards(hist_doses, checkin_hoje, remedios_padrao):
    """Constrói lista de dicts para os cards de remédios prioritários."""
    cards = []
    for nome_prio in ["Rivotril", "Zolpidem"]:
        doses = hist_doses.get(nome_prio, [])
        dose_hoje_val = None
        if checkin_hoje and checkin_hoje.get("remedios_tomados"):
            try:
                arr_hoje = _parse_json_field(checkin_hoje["remedios_tomados"])
                for item in arr_hoje:
                    if item.get("nome", "").lower() == nome_prio.lower() and item.get("tomado"):
                        dose_hoje_val = item.get("qtd", 0)
                        break
            except Exception:
                pass
        elif doses:
            dose_hoje_val = doses[0][1]

        baseline = next(
            (float(r["dose_padrao"] or 1) for r in remedios_padrao if r["nome"].lower() == nome_prio.lower()),
            1,
        )
        max_dose = max((d[1] for d in doses), default=baseline) or 1
        media_doses = (sum(d[1] for d in doses) / len(doses)) if doses else None

        # delta vs média
        delta_media = None
        if media_doses is not None and dose_hoje_val is not None:
            diff = dose_hoje_val - media_doses
            if abs(diff) < 0.1:
                delta_media = {"tipo": "neutro", "texto": "na média"}
            elif diff > 0:
                delta_media = {"tipo": "alto", "texto": f"↑ +{diff:.1g} vs média"}
            else:
                delta_media = {"tipo": "baixo", "texto": f"↓ {diff:.1g} vs média"}

        # barras históricas
        doses_crono = list(reversed(doses[:7]))
        barras = []
        for i, (ds_r, qtd) in enumerate(doses_crono):
            h = max(4, int((qtd / max_dose) * 40))
            barras.append({
                "data": ds_r,
                "altura": h,
                "is_today": i == len(doses_crono) - 1,
            })

        # alerta desvio consecutivo
        dias_consecutivos = calcular_desvio_consecutivo(doses, baseline)

        cards.append({
            "nome": nome_prio,
            "dose_hoje": f"{dose_hoje_val:g}" if dose_hoje_val is not None else "—",
            "baseline": f"{baseline:g}",
            "media": f"{media_doses:.1f}" if media_doses is not None else "—",
            "delta_media": delta_media,
            "barras": barras,
            "dias_consecutivos": dias_consecutivos,
        })
    return cards


def _build_chart_data(rows_tendencia):
    """Constrói o JSON de dados do gráfico de tendências."""
    labels = [r["data"].strftime("%d/%m") for r in rows_tendencia]

    def _series(field):
        return [float(r[field]) if r.get(field) is not None else None for r in rows_tendencia]

    def _remed_series(nome_remed):
        out = []
        for r in rows_tendencia:
            rj = r.get("remedios_tomados")
            try:
                itens = _parse_json_field(rj)
                val = next(
                    (float(i.get("qtd", 0)) for i in itens
                     if i.get("nome", "").lower() == nome_remed.lower() and i.get("tomado")),
                    None,
                )
            except Exception:
                val = None
            out.append(val)
        return out

    return {
        "labels": labels,
        "mental":   _series("saude_mental"),
        "energia":  _series("energia"),
        "sono":     _series("sono_horas"),
        "sono_q":   _series("sono_qualidade"),
        "dor":      _series("dor_fisica"),
        "stress_t": _series("stress_trabalho"),
        "stress_r": _series("stress_relacionamento"),
        "social":   _series("desempenho_social"),
        "rivotril": _remed_series("Rivotril"),
        "zolpidem": _remed_series("Zolpidem"),
    }


def _build_historico(rows, hoje, contextos_lista, campos_config):
    """Constrói lista de dicts para o histórico dos últimos 7 dias."""
    baselines = {campo: cfg.get("baseline") for campo, cfg in campos_config.items()}
    rows_by_date = {r["data"]: r for r in rows}
    dias_7 = list(reversed([hoje - timedelta(days=i) for i in range(6, -1, -1)]))

    historico = []
    for dia in dias_7:
        r = rows_by_date.get(dia)
        if r is None:
            historico.append({
                "data": dia,
                "data_str": dia.strftime("%d/%m"),
                "data_iso": dia.isoformat(),
                "sem_registro": True,
            })
            continue

        di = r["data"].isoformat()
        ds = r["data"].strftime("%d/%m")
        rj_raw = r.get("remedios_tomados")
        ctx_raw = r.get("contextos_dia")
        nota_cats = _parse_json_field(r.get("nota_categorias"))
        ctx_dia = _parse_json_field(ctx_raw)
        rj_esc = _html_mod.escape(json.dumps(_parse_json_field(rj_raw)))
        ctx_esc = _html_mod.escape(json.dumps(ctx_dia))
        nota_esc = _html_mod.escape(r.get("nota_raw") or "")

        chips = calcular_chips_historico(r, baselines)

        nota_resumo = r.get("nota_resumo_ia") or ""
        nota_raw_h = r.get("nota_raw") or ""
        if not nota_resumo and nota_raw_h:
            nota_resumo = nota_raw_h[:90] + ("…" if len(nota_raw_h) > 90 else "")

        historico.append({
            "data": r["data"],
            "data_str": ds,
            "data_iso": di,
            "sem_registro": False,
            "is_hoje": r["data"] == hoje,
            "me": r.get("saude_mental"),
            "en": r.get("energia"),
            "dor": r.get("dor_fisica"),
            "sh": r.get("sono_horas"),
            "sq": r.get("sono_qualidade"),
            "al": r.get("alcool") or "",
            "ex": r.get("exercicio") or "",
            "st": r.get("stress_trabalho"),
            "sr": r.get("stress_relacionamento"),
            "so": r.get("desempenho_social"),
            "ci": r.get("cigarros"),
            "alim": r.get("alimentacao"),
            "nota_raw": nota_raw_h,
            "nota_resumo": nota_resumo,
            "nota_sent": r.get("nota_sentimento") or "",
            "nota_sent_class": sent_badge_class(r.get("nota_sentimento") or ""),
            "nota_cats": nota_cats,
            "rj_esc": rj_esc,
            "ctx_esc": ctx_esc,
            "nota_esc": nota_esc,
            "ctx_dia": ctx_dia,
            "chips": chips,
            "ex_cor": EX_CORES.get(r.get("exercicio") or "Nenhum", "#2A2A38"),
        })
    return historico


# ---------------------------------------------------------------------------
# GET /dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def dashboard_get(request: Request):
    try:
        pool = get_pool()
        rows = await get_checkins_semana(pool)
        streak = await get_streak(pool)
        media = await get_media_semana(pool)
        media_ant = await get_media_semana_anterior(pool)
        heatmap = await get_heatmap_30d(pool)
        remedios_padrao = await get_remedios(pool)
        contextos_lista = await get_contextos(pool)
        campos_config = await get_campos_config(pool)
        session_hoje = await get_session_hoje(pool)
        rows_tendencia = await get_checkins_tendencia(pool, dias=30)
    except Exception as e:
        return templates.TemplateResponse(request, "dashboard.html", {
            "erro": str(e),
        })

    agora_sp = datetime.now(_get_sp_tz())
    hora_sp = agora_sp.hour
    hoje = agora_sp.date()

    checkin_hoje = rows[0] if rows and rows[0]["data"] == hoje else None
    checkin_hoje_completo = (
        checkin_hoje is not None
        and session_hoje is not None
        and session_hoje["status"] == "concluido"
    )
    ref = next((r for r in rows if r.get("saude_mental") is not None), None)

    mental_hoje = ref["saude_mental"] if ref else None
    energia_hoje = ref["energia"] if ref else None
    dor_hoje = ref["dor_fisica"] if ref else None
    sono_hoje = ref["sono_horas"] if ref else None
    ex_hoje = ref["exercicio"] if ref else None

    # Saudação com contexto
    saudacao = saudacao_contextual(hora_sp, mental_hoje, energia_hoje, dor_hoje)

    # Chips do hero com cor condicional vs baseline
    baselines = {campo: cfg.get("baseline") for campo, cfg in campos_config.items()}
    hero_chips = []
    if energia_hoje is not None:
        sc = score_color_class(energia_hoje, baselines.get("energia"), invert=False)
        hero_chips.append({"valor": str(energia_hoje), "label": "⚡ Energia", "color": "#67E8F9", "status_class": sc})
    if sono_hoje is not None:
        hero_chips.append({"valor": f"{sono_hoje}h", "label": "★ Sono", "color": "#A78BFA", "status_class": "neutral"})
    if dor_hoje is not None:
        sc = score_color_class(dor_hoje, baselines.get("dor_fisica"), invert=True)
        dor_c = score_color(dor_hoje, invert=True)
        hero_chips.append({"valor": str(dor_hoje), "label": "❤ Dor", "color": dor_c, "status_class": sc})
    if ex_hoje and ex_hoje != "Nenhum":
        hero_chips.append({"valor": ex_hoje, "label": "▶ Exercício", "color": "#86EFAC", "status_class": "neutral"})

    # Deltas das médias
    deltas = {
        "mental":   calcular_delta(media.get("mental"), media_ant.get("mental")),
        "energia":  calcular_delta(media.get("energia"), media_ant.get("energia")),
        "sono_h":   calcular_delta(media.get("sono_h"), media_ant.get("sono_h")),
        "sono_q":   calcular_delta(media.get("sono_q"), media_ant.get("sono_q")),
        "dor":      calcular_delta(media.get("dor"), media_ant.get("dor"), invert=True),
        "social":   calcular_delta(media.get("social"), media_ant.get("social")),
        "stress_t": calcular_delta(media.get("stress_t"), media_ant.get("stress_t"), invert=True),
        "stress_r": calcular_delta(media.get("stress_r"), media_ant.get("stress_r"), invert=True),
        "cigarros": calcular_delta(media.get("cigarros"), media_ant.get("cigarros"), invert=True),
    }

    # Heatmap 30 dias
    heatmap_dots = []
    for i in range(29, -1, -1):
        d = hoje - timedelta(days=i)
        mental_val = heatmap.get(d)
        heatmap_dots.append({
            "date": d,
            "date_str": d.strftime("%d/%m"),
            "date_pt": data_formatada(d),
            "mental": mental_val,
            "color": dot_color(mental_val),
        })

    # Exercício 7 dias
    ex_semana = []
    for r in list(reversed(rows))[-7:]:
        ex_val = r.get("exercicio") or "Nenhum"
        ex_semana.append({
            "data_str": r["data"].strftime("%d/%m"),
            "exercicio": ex_val,
            "cor": EX_CORES.get(ex_val, "#2A2A38"),
            "altura": EX_ALTURA.get(ex_val, 4),
            "icone": EX_ICONE.get(ex_val, ""),
        })

    # Remédios
    hist_doses = _build_hist_doses(rows, remedios_padrao)
    remed_cards = _build_remed_cards(hist_doses, checkin_hoje, remedios_padrao)
    remed_secundarios = [r for r in remedios_padrao if r["nome"].lower() not in REMED_PRIORITARIOS]

    # Contextos ativos (hoje)
    ctx_hoje = []
    if checkin_hoje:
        ctx_hoje = _parse_json_field(checkin_hoje.get("contextos_dia"))
    contextos_ativos_labels = [c["label"] for c in contextos_lista if c["ativo"]]

    # Alimentação
    alim_hoje = checkin_hoje.get("alimentacao") if checkin_hoje else None

    # Histórico
    historico = _build_historico(rows, hoje, contextos_lista, campos_config)

    # Chart data (30d)
    chart_data = _build_chart_data(rows_tendencia)

    # Modal: dados para remédios e contextos
    modal_remedios = remedios_padrao
    modal_contextos = [c for c in contextos_lista]

    # Checkin status
    if checkin_hoje_completo:
        checkin_status = "completo"
    elif checkin_hoje:
        checkin_status = "parcial"
    else:
        checkin_status = "pendente"

    # Dados do checkin de hoje para o modal de editar
    checkin_hoje_edit = {}
    if checkin_hoje:
        rj_raw = checkin_hoje.get("remedios_tomados")
        ctx_raw = checkin_hoje.get("contextos_dia")
        checkin_hoje_edit = {
            "data": hoje.isoformat(),
            "dor": checkin_hoje.get("dor_fisica") or "",
            "en": checkin_hoje.get("energia") or "",
            "sh": checkin_hoje.get("sono_horas") or "",
            "sq": checkin_hoje.get("sono_qualidade") or "",
            "me": checkin_hoje.get("saude_mental") or "",
            "st": checkin_hoje.get("stress_trabalho") or "",
            "sr": checkin_hoje.get("stress_relacionamento") or "",
            "al": checkin_hoje.get("alcool") or "",
            "ci": checkin_hoje.get("cigarros") or "",
            "so": checkin_hoje.get("desempenho_social") or "",
            "ex": checkin_hoje.get("exercicio") or "",
            "alim": checkin_hoje.get("alimentacao") if checkin_hoje.get("alimentacao") is not None else "",
            "relato": _html_mod.escape(checkin_hoje.get("nota_raw") or ""),
            "rj": _html_mod.escape(json.dumps(_parse_json_field(rj_raw))),
            "ctx": _html_mod.escape(json.dumps(_parse_json_field(ctx_raw))),
        }

    # Emoji scale
    emoji_scale = []
    for i, (em, col, lbl) in enumerate(zip(HUMOR_EMOJIS, HUMOR_COLORS, HUMOR_LABELS)):
        nivel = i + 1
        is_active = mental_hoje is not None and int(round(float(mental_hoje))) == nivel
        emoji_scale.append({"emoji": em, "color": col, "label": lbl, "nivel": nivel, "active": is_active})

    # Álcool
    alcool_vals = [r.get("alcool") for r in rows if r.get("alcool")]
    alcool_display = max(set(alcool_vals), key=alcool_vals.count) if alcool_vals else "—"

    ctx = {
        "saudacao": saudacao,
        "hoje": hoje,
        "hoje_iso": hoje.isoformat(),
        "hoje_pt": data_formatada(hoje),
        "checkin_status": checkin_status,
        "checkin_hoje": checkin_hoje,
        "checkin_hoje_edit": checkin_hoje_edit,
        "ref": ref,
        "mental_hoje": mental_hoje,
        "energia_hoje": energia_hoje,
        "dor_hoje": dor_hoje,
        "sono_hoje": sono_hoje,
        "ex_hoje": ex_hoje,
        "score_color_val": score_color(mental_hoje) if mental_hoje is not None else "#4A4A5A",
        "frase": hero_frase(mental_hoje, energia_hoje, dor_hoje),
        "hero_chips": hero_chips,
        "emoji_scale": emoji_scale,
        "data_display": data_formatada(ref["data"]) if ref else "sem dados",
        "streak_atual": streak.get("streak_atual", 0),
        "streak_maximo": streak.get("streak_maximo", 0),
        "streak_frase": streak_frase(streak.get("streak_atual", 0), streak.get("streak_maximo", 0)),
        "heatmap_dots": heatmap_dots,
        "media": media,
        "deltas": deltas,
        "alcool_display": alcool_display,
        "ex_semana": ex_semana,
        "remed_cards": remed_cards,
        "remed_secundarios": remed_secundarios,
        "contextos_ativos": contextos_ativos_labels,
        "ctx_hoje": ctx_hoje,
        "alim_hoje": alim_hoje,
        "alim_label_hoje": alim_label(alim_hoje),
        "historico": historico,
        "chart_data": json.dumps(chart_data),
        "chart_data_30d": json.dumps(chart_data),
        "modal_remedios": modal_remedios,
        "modal_contextos": modal_contextos,
        "rows": rows,
        "has_data": bool(rows),
    }
    return templates.TemplateResponse(request, "dashboard.html", ctx)


# ---------------------------------------------------------------------------
# POST /dashboard/relato
# ---------------------------------------------------------------------------

@router.post("/dashboard/relato")
async def dashboard_relato(texto: str = Form(...), data: str = Form(default="")):
    import re
    if data and re.match(r"^\d{4}-\d{2}-\d{2}$", data):
        data_alvo = date.fromisoformat(data)
    else:
        data_alvo = datetime.now(_get_sp_tz()).date()
    try:
        pool = get_pool()
        await save_nota(pool, texto, data_alvo)
        try:
            analysis = await process_nota(texto, OPENAI_API_KEY)
            if analysis:
                await save_nota_analysis(
                    pool,
                    analysis.get("sentimento", ""),
                    json.dumps(analysis.get("categorias", []), ensure_ascii=False),
                    analysis.get("resumo", ""),
                    data_alvo,
                )
        except Exception:
            pass
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# POST /dashboard/relato-audio
# ---------------------------------------------------------------------------

@router.post("/dashboard/relato-audio")
async def dashboard_relato_audio(audio: UploadFile = File(...)):
    if not OPENAI_API_KEY:
        return JSONResponse({"error": "OpenAI não configurado"}, status_code=503)
    try:
        from openai import AsyncOpenAI
        import io
        ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        audio_bytes = await audio.read()
        resp = await ai.audio.transcriptions.create(
            model="whisper-1",
            file=("relato.webm", io.BytesIO(audio_bytes), "audio/webm"),
        )
        texto = resp.text
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    pool = get_pool()
    analysis = await process_nota(texto, OPENAI_API_KEY)
    data_alvo = datetime.now(_get_sp_tz()).date()
    await save_nota(pool, texto, data_alvo)
    if analysis:
        await save_nota_analysis(
            pool,
            analysis.get("sentimento", ""),
            json.dumps(analysis.get("categorias", []), ensure_ascii=False),
            analysis.get("resumo", ""),
            data_alvo,
        )
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# POST /dashboard/editar
# ---------------------------------------------------------------------------

@router.post("/dashboard/editar")
async def dashboard_editar(
    data: str = Form(...),
    dor_fisica: str = Form(default=""),
    energia: str = Form(default=""),
    sono_horas: str = Form(default=""),
    sono_qualidade: str = Form(default=""),
    saude_mental: str = Form(default=""),
    stress_trabalho: str = Form(default=""),
    stress_relacionamento: str = Form(default=""),
    alcool: str = Form(default=""),
    exercicio: str = Form(default=""),
    cigarros: str = Form(default=""),
    desempenho_social: str = Form(default=""),
    alimentacao: str = Form(default=""),
    nota_raw: str = Form(default=""),
    remedios_tomados: str = Form(default=""),
    contextos_dia: str = Form(default=""),
):
    def _int(v):
        return int(v) if str(v).strip() else None

    def _float(v):
        return float(v) if str(v).strip() else None

    try:
        remed_json = json.dumps(json.loads(remedios_tomados), ensure_ascii=False) if remedios_tomados.strip() else None
    except Exception:
        remed_json = None

    try:
        ctx_json = json.dumps(json.loads(contextos_dia), ensure_ascii=False) if contextos_dia.strip() else "[]"
    except Exception:
        ctx_json = "[]"

    campos = {
        "dor_fisica": _int(dor_fisica),
        "energia": _int(energia),
        "sono_horas": _float(sono_horas),
        "sono_qualidade": _int(sono_qualidade),
        "saude_mental": _int(saude_mental),
        "stress_trabalho": _int(stress_trabalho),
        "stress_relacionamento": _int(stress_relacionamento),
        "alcool": alcool.strip() or None,
        "exercicio": exercicio.strip() or None,
        "cigarros": _int(cigarros),
        "desempenho_social": _int(desempenho_social),
        "alimentacao": _int(alimentacao),
        "nota_raw": nota_raw.strip() or "",
        "remed_json": remed_json,
        "ctx_json": ctx_json,
    }
    pool = get_pool()
    await editar_checkin(pool, date.fromisoformat(data), campos)
    return RedirectResponse("/dashboard", status_code=303)


# ---------------------------------------------------------------------------
# POST /dashboard/remed-atualizar
# ---------------------------------------------------------------------------

@router.post("/dashboard/remed-atualizar")
async def dashboard_remed_atualizar(nome: str = Form(...), delta: float = Form(...)):
    pool = get_pool()
    await update_remed_hoje(pool, nome, delta)
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# POST /dashboard/contexto-toggle
# ---------------------------------------------------------------------------

@router.post("/dashboard/contexto-toggle")
async def dashboard_contexto_toggle(label: str = Form(...)):
    pool = get_pool()
    ctx = await toggle_contexto_hoje(pool, label)
    return JSONResponse({"ok": True, "contextos": ctx})


# ---------------------------------------------------------------------------
# POST /dashboard/alimentacao-atualizar
# ---------------------------------------------------------------------------

@router.post("/dashboard/alimentacao-atualizar")
async def dashboard_alimentacao_atualizar(valor: int = Form(...)):
    valor = max(1, min(5, valor))
    pool = get_pool()
    await update_alimentacao_hoje(pool, valor)
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# POST /dashboard/remover
# ---------------------------------------------------------------------------

@router.post("/dashboard/remover")
async def dashboard_remover(data: str = Form(...)):
    pool = get_pool()
    await remover_checkin(pool, date.fromisoformat(data))
    return RedirectResponse("/dashboard", status_code=303)


# ---------------------------------------------------------------------------
# GET/POST /dashboard/contextos-editor
# ---------------------------------------------------------------------------

@router.get("/dashboard/contextos-editor")
async def contextos_editor_get():
    return RedirectResponse("/dashboard/configuracoes?aba=contextos", status_code=302)


@router.get("/dashboard/contextos-editor-legacy")
async def contextos_editor_get_legacy(request: Request):
    pool = get_pool()
    rows = await get_contextos_config_all(pool)
    return templates.TemplateResponse(request, "configuracoes.html", {
        "aba": "contextos",
        "campos_db": {},
        "campos_fixos_meta": _CAMPOS_FIXOS_META,
        "campos_custom": [],
        "contextos_db": rows,
        "legacy": True,
    })


@router.post("/dashboard/contextos-editor/toggle")
async def contextos_editor_toggle(id: int = Form(...)):
    pool = get_pool()
    await toggle_contexto_config(pool, id)
    return RedirectResponse("/dashboard/contextos-editor", status_code=303)


@router.post("/dashboard/contextos-editor/add")
async def contextos_editor_add(label: str = Form(...)):
    label = label.strip()[:60]
    if not label:
        return RedirectResponse("/dashboard/contextos-editor", status_code=303)
    pool = get_pool()
    await add_contexto_config(pool, label)
    return RedirectResponse("/dashboard/contextos-editor", status_code=303)


# ---------------------------------------------------------------------------
# GET /dashboard/configuracoes
# ---------------------------------------------------------------------------

@router.get("/dashboard/configuracoes")
async def configuracoes_get(request: Request, aba: str = "campos"):
    pool = get_pool()
    campos_config = await get_campos_config(pool)
    contextos_db = await get_contextos_config_all(pool)
    campos_custom = await get_campos_custom(pool)

    return templates.TemplateResponse(request, "configuracoes.html", {
        "aba": aba,
        "campos_db": campos_config,
        "campos_fixos_meta": _CAMPOS_FIXOS_META,
        "campos_custom": campos_custom,
        "contextos_db": contextos_db,
        "legacy": False,
    })


@router.post("/dashboard/configuracoes/campo-toggle")
async def cfg_campo_toggle(campo: str = Form(...)):
    pool = get_pool()
    await toggle_campo_config(pool, campo)
    return RedirectResponse("/dashboard/configuracoes?aba=campos", status_code=303)


@router.post("/dashboard/configuracoes/contexto-toggle")
async def cfg_ctx_toggle(id: int = Form(...)):
    pool = get_pool()
    await toggle_contexto_config(pool, id)
    return RedirectResponse("/dashboard/configuracoes?aba=contextos", status_code=303)


@router.post("/dashboard/configuracoes/contexto-add")
async def cfg_ctx_add(label: str = Form(...)):
    label = label.strip()[:60]
    if not label:
        return RedirectResponse("/dashboard/configuracoes?aba=contextos", status_code=303)
    pool = get_pool()
    await add_contexto_config(pool, label)
    return RedirectResponse("/dashboard/configuracoes?aba=contextos", status_code=303)


@router.post("/dashboard/configuracoes/contexto-remover")
async def cfg_ctx_remover(id: int = Form(...)):
    pool = get_pool()
    await remove_contexto_config(pool, id)
    return RedirectResponse("/dashboard/configuracoes?aba=contextos", status_code=303)


@router.post("/dashboard/configuracoes/campo-custom-add")
async def cfg_campo_custom_add(
    nome: str = Form(...),
    tipo_input: str = Form(...),
    opcoes_texto: str = Form(default=""),
):
    nome = nome.strip()[:50]
    tipo_input = tipo_input.strip()
    opcoes_texto = opcoes_texto.strip()[:200]
    if not nome:
        return RedirectResponse("/dashboard/configuracoes?aba=campos", status_code=303)
    pool = get_pool()
    await add_campo_custom(pool, nome, tipo_input, opcoes_texto)
    return RedirectResponse("/dashboard/configuracoes?aba=campos", status_code=303)


@router.post("/dashboard/configuracoes/campo-custom-toggle")
async def cfg_campo_custom_toggle(id: int = Form(...)):
    pool = get_pool()
    await toggle_campo_custom(pool, id)
    return RedirectResponse("/dashboard/configuracoes?aba=campos", status_code=303)


@router.post("/dashboard/configuracoes/campo-custom-editar")
async def cfg_campo_custom_editar(
    id: int = Form(...),
    nome: str = Form(...),
    tipo_input: str = Form(...),
    opcoes_texto: str = Form(default=""),
):
    pool = get_pool()
    await editar_campo_custom(pool, id, nome.strip()[:50], tipo_input.strip(), opcoes_texto.strip()[:200])
    return RedirectResponse("/dashboard/configuracoes?aba=campos", status_code=303)
