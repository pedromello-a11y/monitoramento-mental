import json as _json
import html as _html_mod
from datetime import date, timedelta, datetime
import zoneinfo

from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from config import OPENAI_API_KEY
from database import get_pool

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_color(v, invert=False):
    if v is None:
        return "#4A4A5A"
    pct = float(v) / 5
    if invert:
        if pct <= 0.3: return "#86EFAC"
        if pct <= 0.6: return "#FCD34D"
        return "#FCA5A5"
    else:
        if pct >= 0.7: return "#86EFAC"
        if pct >= 0.4: return "#FCD34D"
        return "#FCA5A5"

def _trend(rows, field):
    vals = [r[field] for r in rows if r[field] is not None]
    if len(vals) < 3:
        return ""
    mid = len(vals) // 2
    recent = sum(vals[:mid]) / mid
    older = sum(vals[mid:]) / (len(vals) - mid)
    diff = recent - older
    if abs(diff) < 0.3:
        return '<span style="color:#94A3B8;font-size:13px">\u2192</span>'
    if diff > 0:
        return '<span style="color:#86EFAC;font-size:13px">\u2191</span>'
    return '<span style="color:#FCA5A5;font-size:13px">\u2193</span>'

def _hero_frase(mental, energia, dor):
    if mental is None:
        return "Seus dados v\xe3o aparecer aqui depois do pr\xf3ximo check-in."
    m, e = float(mental), float(energia) if energia is not None else 3
    d = float(dor) if dor is not None else 1
    if m >= 4 and e >= 4:
        return "Voc\xea esteve bem hoje. Isso importa."
    if m >= 3 and d <= 2:
        return "Um dia razo\xe1vel. Voc\xea est\xe1 acompanhando."
    if m <= 2 and d >= 4:
        return "Foi um dia mais pesado. Tudo registrado, tudo bem."
    if m <= 2:
        return "Nem todo dia \xe9 f\xe1cil. Voc\xea est\xe1 aqui, isso j\xe1 \xe9 algo."
    if d >= 4:
        return "Seu corpo pediu aten\xe7\xe3o hoje. Registrado."
    return "Mais um dia acompanhado. Obrigado por estar aqui."

def _streak_frase(atual, maximo):
    if atual == 0:
        return "Novo come\xe7o. O dia 1 j\xe1 \xe9 progresso."
    if atual == 1:
        return "Come\xe7ou. Um dia de cada vez."
    if atual >= 30:
        return f"{atual} dias. Um m\xeas inteiro de dados sobre voc\xea mesmo."
    if atual >= 14:
        return f"{atual} dias seguidos. Isso j\xe1 \xe9 consist\xeancia real."
    if atual >= 7:
        return f"{atual} dias. Uma semana completa."
    return f"{atual} dias seguidos. Voc\xea est\xe1 construindo algo."

def _sent_badge(s):
    if not s:
        return ""
    m = {
        "positivo": '<span style="background:#14532d;color:#86EFAC;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600">\u2022 positivo</span>',
        "neutro":   '<span style="background:#1e293b;color:#94A3B8;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600">\u2022 neutro</span>',
        "negativo": '<span style="background:#450a0a;color:#FCA5A5;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600">\u2022 pesado</span>',
    }
    return m.get(s.lower(), "")

async def _process_nota_completa(nota_raw: str) -> dict:
    if not OPENAI_API_KEY or not nota_raw.strip():
        return {}
    try:
        from openai import AsyncOpenAI
        ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Você é um psicólogo analista de saúde mental. Analise o relato diário e retorne JSON com: "
                    "resumo (frase curta, acolhedora, 1a pessoa, máx 90 chars), "
                    "sentimento (positivo/neutro/negativo), "
                    "categorias (lista de até 5 temas reutilizáveis em português, ex: ansiedade, sono, trabalho, relacionamento, humor, dor, energia, medicação, exercício), "
                    "insights (lista de até 2 observações curtas e úteis do ponto de vista de saúde mental). "
                    "Responda APENAS com JSON válido."
                )},
                {"role": "user", "content": nota_raw},
            ],
            response_format={"type": "json_object"},
        )
        return _json.loads(resp.choices[0].message.content)
    except Exception:
        return {}

def _dot_color(mental):
    if mental is None:
        return "#2A2A38"
    v = float(mental)
    if v >= 4: return "#86EFAC"
    if v >= 3: return "#A78BFA"
    if v >= 2: return "#FCD34D"
    return "#FCA5A5"

def _badge(val, invert=False):
    if val is None or val == "":
        return '<span style="color:#4A4A5A">\u2014</span>'
    color = _score_color(float(val), invert=invert)
    bg = color + "22"
    return f'<span class="badge" style="background:{bg};color:{color}">{val}</span>'

def _dim_row(label, val, max_val=5, invert=False):
    if val is None or val == "":
        return f'<div class="dim-row"><span class="dim-lbl">{label}</span><span style="color:#4A4A5A;font-size:13px">\u2014</span></div>'
    v = float(val)
    pct = int((v / max_val) * 100)
    color = _score_color(v, invert=invert)
    return (
        f'<div class="dim-row">'
        f'<span class="dim-lbl">{label}</span>'
        f'<div class="dim-val">'
        f'<span class="v" style="color:{color}">{val}</span>'
        f'<div class="dim-bar"><div class="dim-bar-fill" style="width:{pct}%;background:{color}"></div></div>'
        f'</div></div>'
    )

def _alim_label(v):
    if v is None:
        return "\u2014"
    if v <= 1: return "Besteira"
    if v <= 2: return "Ruim"
    if v <= 3: return "Regular"
    if v <= 4: return "Boa"
    return "Saud\xe1vel"

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
:root{
  --bg:#0F0F14;--surface:#18181F;--surface2:#22222C;--border:#2A2A38;
  --primary:#A78BFA;--primary-dim:#7C5CBF;
  --warm:#F9A8D4;--cool:#67E8F9;
  --good:#86EFAC;--warn:#FCD34D;--low:#FCA5A5;--neutral:#94A3B8;
  --text:#F1F0F5;--text2:#94A3B8;--text3:#4A4A5A;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;
  padding:0 0 80px;max-width:860px;margin:0 auto}
a{color:var(--primary);text-decoration:none}

/* Header */
.header{padding:28px 24px 0;display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px}
.header-left h1{font-size:14px;font-weight:600;color:var(--text2);letter-spacing:.5px;text-transform:uppercase}
.header-left .greeting{font-size:26px;font-weight:700;color:var(--text);margin-top:4px;line-height:1.2}
.header-right{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.checkin-btn{background:var(--primary);color:#0F0F14;border:none;border-radius:12px;
  padding:10px 20px;font-size:13px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}
.checkin-done{background:#14532d;color:#86EFAC;border:1px solid #166534;border-radius:12px;
  padding:10px 16px;font-size:13px;font-weight:600;display:inline-flex;align-items:center;gap:6px}
.checkin-edit-btn{background:var(--surface2);color:var(--text2);border:1px solid var(--border);
  border-radius:12px;padding:10px 14px;font-size:13px;font-weight:600;cursor:pointer;display:inline-block}

/* Section label */
.sec-label{font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;
  letter-spacing:.8px;padding:28px 24px 12px}

/* Hero card */
.hero{margin:20px 24px 0;background:linear-gradient(135deg,#1E1B2E 0%,#18181F 100%);
  border-radius:20px;padding:24px;border:1px solid var(--border);position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:-40px;right:-40px;width:160px;height:160px;
  background:radial-gradient(circle,rgba(167,139,250,.15) 0%,transparent 70%);border-radius:50%}
.hero-score{font-size:56px;font-weight:800;line-height:1;color:var(--text)}
.hero-score span{font-size:22px;font-weight:400;color:var(--text2)}
.hero-label{font-size:12px;font-weight:600;color:var(--text2);text-transform:uppercase;
  letter-spacing:.8px;margin-bottom:8px}
.hero-frase{font-size:15px;color:var(--text2);margin-top:10px;line-height:1.5}
.hero-meta{display:flex;gap:16px;margin-top:16px;flex-wrap:wrap}
.hero-chip{background:rgba(255,255,255,.06);border-radius:10px;padding:8px 14px;font-size:13px}
.hero-chip .hc-val{font-size:18px;font-weight:700;display:block;line-height:1.2}
.hero-chip .hc-lbl{font-size:11px;color:var(--text2);margin-top:2px}

/* Relato */
.relato-card{margin:0 24px;background:var(--surface);border-radius:16px;padding:20px;border:1px solid var(--border)}
.relato-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;gap:10px;flex-wrap:wrap}
.relato-title{font-size:13px;font-weight:700;color:var(--text);text-transform:uppercase;letter-spacing:.5px}
.relato-resumo{font-size:15px;color:var(--text);line-height:1.6;font-weight:500}
.relato-cats{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px}
.relato-tag{background:rgba(167,139,250,.12);color:var(--primary);border-radius:20px;
  padding:3px 10px;font-size:11px;font-weight:600}
.relato-expand{margin-top:12px;padding-top:12px;border-top:1px solid var(--border)}
.relato-expand summary{font-size:12px;color:var(--text2);cursor:pointer;user-select:none}
.relato-raw-text{font-size:13px;color:var(--text2);line-height:1.6;margin-top:8px;white-space:pre-wrap}
.relato-prompt{font-size:14px;color:var(--text2);margin-bottom:12px}
.relato-actions{display:flex;gap:10px;flex-wrap:wrap}
.relato-btn{background:var(--surface2);border:1px solid var(--border);border-radius:12px;
  padding:10px 18px;font-size:13px;font-weight:600;color:var(--text);cursor:pointer}
.relato-btn-audio{border-color:var(--primary);color:var(--primary)}
.relato-btn-rec{border-color:#FCA5A5;color:#FCA5A5}
.relato-btn-rec.recording{background:#450a0a;border-color:#FCA5A5;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
#relato-input{width:100%;background:var(--surface2);border:1px solid var(--border);
  border-radius:12px;padding:12px;color:var(--text);font-size:14px;
  resize:vertical;min-height:100px;margin:12px 0 8px;outline:none;font-family:inherit}
#relato-input:focus{border-color:var(--primary)}
.relato-submit{background:var(--primary);color:#0F0F14;border:none;border-radius:12px;
  padding:10px 20px;font-size:13px;font-weight:700;cursor:pointer}
.relato-edit-btn{background:var(--surface2);color:var(--text2);border:1px solid var(--border);
  border-radius:8px;padding:4px 12px;font-size:12px;cursor:pointer}
.relato-audio-status{font-size:13px;color:var(--text2);margin:10px 0;padding:8px 12px;
  background:var(--surface2);border-radius:8px}
.relato-insight{font-size:12px;color:var(--text2);background:rgba(167,139,250,.06);
  border-left:2px solid var(--primary-dim);padding:8px 12px;border-radius:0 8px 8px 0;margin-top:8px;line-height:1.5}

/* Remédios prioritários */
.remed-priority-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 24px}
.remed-priority-card{background:var(--surface);border-radius:16px;padding:18px;border:1px solid var(--border)}
.remed-priority-name{font-size:13px;font-weight:700;color:var(--primary);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
.remed-priority-dose{font-size:32px;font-weight:800;color:var(--text);line-height:1}
.remed-priority-dose span{font-size:14px;font-weight:400;color:var(--text2)}
.remed-priority-hist{display:flex;gap:4px;margin-top:12px;align-items:flex-end}
.remed-hist-bar{flex:1;border-radius:3px 3px 0 0;min-height:4px;background:rgba(167,139,250,.3)}
.remed-hist-bar.today{background:var(--primary)}
.remed-hist-label{font-size:9px;color:var(--text3);text-align:center;margin-top:3px}
.remed-baseline{font-size:10px;color:var(--text3);margin-top:6px}
/* Remédios secundários compactos */
.remed-sec{margin:8px 24px 0;background:var(--surface);border-radius:12px;
  padding:12px 16px;border:1px solid var(--border);display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.remed-sec-label{font-size:11px;color:var(--text3);font-weight:600;margin-right:4px}
.remed-sec-item{font-size:12px;color:var(--text2);background:var(--surface2);
  border-radius:8px;padding:4px 10px}
/* Botões de update rápido */
.remed-upd-btn{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
  width:32px;height:32px;font-size:18px;font-weight:700;color:var(--text2);cursor:pointer;
  display:flex;align-items:center;justify-content:center;line-height:1}
.remed-upd-btn:active{background:var(--border)}
.remed-upd-plus{color:var(--primary);border-color:var(--primary-dim)}

/* Exercício */
.ex-card{margin:0 24px;background:var(--surface);border-radius:16px;padding:18px;border:1px solid var(--border)}
.ex-title{font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:14px}
.ex-week{display:flex;gap:6px;align-items:flex-end}
.ex-day{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px}
.ex-bar{width:100%;border-radius:4px 4px 0 0;min-height:4px}
.ex-day-lbl{font-size:9px;color:var(--text3)}
.ex-intensidade{font-size:10px;color:var(--text2);margin-top:2px;font-weight:600}

/* Contextos do dia */
.ctx-wrap{margin:0 24px}
.ctx-grid{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.ctx-chip,.chip{background:var(--surface);border:1px solid var(--border);border-radius:20px;
  padding:8px 14px;font-size:12px;font-weight:600;color:var(--text2);cursor:pointer;
  transition:all .15s;user-select:none;font-family:inherit}
.ctx-chip.active,.chip.sel{background:rgba(167,139,250,.2);border-color:var(--primary);color:var(--primary)}
.ctx-chip:hover,.chip:hover{border-color:var(--neutral)}
.ctx-manage{font-size:11px;color:var(--text3);text-decoration:none;display:inline-block;margin-top:2px}
.ctx-manage:hover{color:var(--primary)}

/* Alimentação */
.alim-card{margin:0 24px;background:var(--surface);border-radius:16px;padding:18px;border:1px solid var(--border)}
.alim-row{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.alim-labels{display:flex;justify-content:space-between;font-size:11px;color:var(--text3);margin-bottom:8px}
.alim-slider{width:100%;-webkit-appearance:none;appearance:none;height:6px;border-radius:3px;
  background:linear-gradient(to right,var(--low),var(--warn),var(--good));outline:none;cursor:pointer}
.alim-slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:20px;height:20px;
  border-radius:50%;background:var(--primary);cursor:pointer;border:2px solid var(--bg)}
.alim-slider::-moz-range-thumb{width:20px;height:20px;border-radius:50%;background:var(--primary);
  cursor:pointer;border:2px solid var(--bg)}
.alim-val{font-size:20px;font-weight:700;color:var(--text);min-width:28px;text-align:center}
.alim-label-val{font-size:12px;color:var(--text2);margin-top:4px;text-align:center}

/* Dimension cards */
.dim-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 24px}
.dim-card{background:var(--surface);border-radius:16px;padding:18px;border:1px solid var(--border)}
.dim-card .dim-title{font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;
  letter-spacing:.8px;margin-bottom:14px}
.dim-row{display:flex;align-items:center;justify-content:space-between;
  padding:7px 0;border-bottom:1px solid var(--border)}
.dim-row:last-child{border-bottom:none}
.dim-lbl{font-size:13px;color:var(--text2)}
.dim-val{display:flex;align-items:center;gap:8px}
.dim-val .v{font-size:16px;font-weight:700}
.dim-bar{width:36px;height:4px;border-radius:2px;background:var(--border);overflow:hidden}
.dim-bar-fill{height:100%;border-radius:2px}

/* Streak + heatmap */
.streak-card{margin:0 24px;background:var(--surface);border-radius:16px;
  padding:20px;border:1px solid var(--border)}
.streak-row{display:flex;align-items:center;gap:20px;margin-bottom:20px;flex-wrap:wrap}
.streak-num{font-size:44px;font-weight:800;color:var(--warm);line-height:1}
.streak-info .streak-frase{font-size:14px;color:var(--text);font-weight:500}
.streak-info .streak-max{font-size:12px;color:var(--text2);margin-top:4px}
.heatmap{display:flex;flex-wrap:wrap;gap:4px}
.dot{width:12px;height:12px;border-radius:3px;flex-shrink:0}

/* Seções colapsáveis (médias, histórico) */
.hist-section{margin:0}
.hist-section-label::-webkit-details-marker{display:none}
.hist-section[open] .hist-toggle-icon{transform:rotate(180deg)}
.hist-toggle-icon{font-size:11px;color:var(--text3);transition:transform .2s}
.medias-section{margin:0}
.medias-section-label::-webkit-details-marker{display:none}
.medias-section[open] .medias-toggle-icon{transform:rotate(180deg)}
.medias-toggle-icon{font-size:11px;color:var(--text3);transition:transform .2s}
.trend-section{margin:0}
.trend-section-label::-webkit-details-marker{display:none}
.trend-section[open] .trend-toggle-icon{transform:rotate(180deg)}
.trend-toggle-icon{font-size:11px;color:var(--text3);transition:transform .2s}

/* Gráfico de tendências */
.chart-card{margin:0 24px;background:var(--surface);border-radius:16px;padding:16px 20px;border:1px solid var(--border)}
.chart-toggles{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.chart-toggle{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid transparent;background:var(--surface2);color:var(--text3);transition:all .15s}
.chart-toggle.on{color:#fff}

/* Histórico compacto */
.hist-compact{margin:0 24px;display:flex;flex-direction:column;gap:1px}
.hist-row-wrap{background:var(--surface);border-radius:0}
.hist-row-wrap:first-child{border-radius:12px 12px 0 0}
.hist-row-wrap:last-child{border-radius:0 0 12px 12px}
.hist-row-wrap:only-child{border-radius:12px}
.hist-row-wrap summary{list-style:none;cursor:pointer}
.hist-row-wrap summary::-webkit-details-marker{display:none}
.hist-row{display:flex;align-items:center;gap:10px;padding:8px 12px;font-size:12px}
.hist-detail{padding:10px 12px 14px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:8px}
.hist-detail-relato{background:var(--surface2);border-radius:10px;padding:12px}
.hist-detail-row{display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap}
.hist-detail-lbl{font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;min-width:72px;padding-top:1px}
.hist-date{font-weight:700;color:var(--text);min-width:32px}
.hist-vals{display:flex;gap:8px;flex:1;flex-wrap:wrap}
.hist-chip{font-size:11px;color:var(--text2);background:var(--surface2);border-radius:6px;padding:2px 6px}
.hist-acts{display:flex;gap:4px}

/* Badge */
.badge{display:inline-block;border-radius:8px;padding:3px 8px;font-size:12px;font-weight:700;min-width:28px;text-align:center}
.act-btn{background:var(--surface2);border:none;border-radius:8px;padding:6px 10px;
  cursor:pointer;color:var(--text2);font-size:13px;transition:background .15s}
.act-btn:hover{background:var(--border)}
.act-btn.del{color:var(--low)}

/* Modal */
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:200;
  overflow-y:auto;padding:20px}
.modal.open{display:block}
.modal-box{background:var(--surface);border-radius:20px;padding:24px;
  max-width:480px;margin:40px auto;border:1px solid var(--border)}
.modal-title{font-size:16px;font-weight:700;margin-bottom:20px;color:var(--text)}
.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.field label{font-size:11px;color:var(--text2);font-weight:600;display:block;
  text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
.field input,.field textarea,.field select{width:100%;background:var(--surface2);border:1px solid var(--border);
  border-radius:10px;padding:10px 12px;color:var(--text);font-size:14px;outline:none;font-family:inherit}
.field input:focus,.field textarea:focus{border-color:var(--primary)}
.field textarea{resize:vertical;min-height:80px}
.modal-footer{display:flex;gap:10px;margin-top:20px}
.btn-save{flex:1;background:var(--primary);color:#0F0F14;border:none;border-radius:12px;
  padding:12px;font-size:14px;font-weight:700;cursor:pointer}
.btn-cancel{flex:1;background:var(--surface2);color:var(--text2);border:none;
  border-radius:12px;padding:12px;font-size:14px;cursor:pointer}
.modal-section{margin-top:14px;border-top:1px solid var(--border);padding-top:14px}
.modal-section-title{font-size:11px;color:var(--text2);font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px}

/* Empty state */
.empty-state{text-align:center;padding:48px 24px}
.empty-state .es-icon{font-size:36px;margin-bottom:12px}
.empty-state .es-title{font-size:16px;font-weight:600;color:var(--text);margin-bottom:6px}
.empty-state .es-sub{font-size:13px;color:var(--text2);line-height:1.6}

/* Editor de contextos */
.editor-wrap{max-width:480px;margin:0 auto;padding:24px}
.editor-item{display:flex;align-items:center;justify-content:space-between;
  background:var(--surface);border-radius:10px;padding:12px 16px;margin-bottom:8px;border:1px solid var(--border)}
.editor-label{font-size:14px;color:var(--text)}
.editor-btn{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
  padding:6px 12px;font-size:12px;color:var(--text2);cursor:pointer}
.editor-btn.desat{color:var(--low);border-color:var(--low)}
.editor-form{margin-top:20px;display:flex;gap:10px}
.editor-input{flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:10px;
  padding:10px 14px;color:var(--text);font-size:14px;outline:none;font-family:inherit}
.editor-input:focus{border-color:var(--primary)}
.editor-submit{background:var(--primary);color:#0F0F14;border:none;border-radius:10px;
  padding:10px 20px;font-size:13px;font-weight:700;cursor:pointer}

@media(max-width:600px){
  .header{padding:20px 16px 0}
  .hero{margin:16px 16px 0;padding:18px}
  .hero-score{font-size:44px}
  .sec-label{padding:22px 16px 10px}
  .relato-card,.remed-priority-grid,.ex-card,.ctx-wrap,.alim-card,.dim-grid,
  .streak-card,.hist-compact,.remed-sec{margin-left:16px;margin-right:16px}
  .remed-priority-grid{margin:0 16px}
  .dim-grid{grid-template-columns:1fr 1fr;gap:10px}
  .dim-card{padding:14px}
}
"""

# ---------------------------------------------------------------------------
# HTML Shell
# ---------------------------------------------------------------------------

_HTML_SHELL = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitoramento Mental</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>CSS_PLACEHOLDER</style>
</head>
<body>
BODY_PLACEHOLDER
<script>
// ── Modal de edição ──────────────────────────────────────────────────────────
function openEdit(btn) {
  var d  = btn.dataset;
  document.getElementById('ed-data').value = d.data;
  document.getElementById('ed-dor').value  = d.dor  || '';
  document.getElementById('ed-en').value   = d.en   || '';
  document.getElementById('ed-sh').value   = d.sh   || '';
  document.getElementById('ed-sq').value   = d.sq   || '';
  document.getElementById('ed-me').value   = d.me   || '';
  document.getElementById('ed-st').value   = d.st   || '';
  document.getElementById('ed-sr').value   = d.sr   || '';
  document.getElementById('ed-al').value   = d.al   || '';
  document.getElementById('ed-ci').value   = d.ci   || '';
  document.getElementById('ed-so').value   = d.so   || '';
  document.getElementById('ed-alim').value = d.alim || '';
  document.getElementById('ed-ex').value   = d.ex   || 'Nenhum';
  document.getElementById('ed-relato').value = d.relato || '';
  // Remédios
  var rj = d.rj || '[]';
  var arr = [];
  try { arr = JSON.parse(rj); } catch(e) {}
  document.querySelectorAll('.ed-rem-qtd').forEach(function(inp){
    var nome = inp.dataset.nome;
    var qtd = 0;
    arr.forEach(function(r){ if(r.nome === nome) qtd = r.qtd || 0; });
    inp.value = qtd;
  });
  // Contextos
  var ctx = d.ctx || '[]';
  var ctxArr = [];
  try { ctxArr = JSON.parse(ctx); } catch(e) {}
  document.querySelectorAll('.ed-ctx-chip').forEach(function(btn){
    btn.classList.toggle('sel', ctxArr.indexOf(btn.dataset.val) !== -1);
  });
  document.getElementById('modal').classList.add('open');
}
function closeModal(){ document.getElementById('modal').classList.remove('open'); }
function buildRemedJson(){
  var arr=[];
  document.querySelectorAll('.ed-rem-qtd').forEach(function(inp){
    var qtd=parseFloat(inp.value)||0;
    arr.push({nome:inp.dataset.nome,qtd:qtd,tomado:qtd>0});
  });
  document.getElementById('ed-remed-json').value=JSON.stringify(arr);
}
function buildCtxJson(){
  var arr=[];
  document.querySelectorAll('.ed-ctx-chip.sel').forEach(function(btn){ arr.push(btn.dataset.val); });
  document.getElementById('ed-ctx-json').value=JSON.stringify(arr);
}
function toggleCtxChip(btn){
  btn.classList.toggle('sel');
}
function delDay(d){
  if(confirm('Remover o registro de '+d+'? Esta ação não pode ser desfeita.')){
    document.getElementById('del-data').value=d;
    document.getElementById('form-del').submit();
  }
}
// ── Relato ──────────────────────────────────────────────────────────────────
function mostrarFormRelato(){
  document.getElementById('relato-saved').style.display='none';
  document.getElementById('relato-form').style.display='block';
  var raw=document.getElementById('relato-saved-raw');
  if(raw){ document.getElementById('relato-input').value=raw.dataset.raw||''; }
}
function relatoTexto(){
  document.getElementById('relato-actions').style.display='none';
  document.getElementById('relato-text-area').style.display='block';
}
var _rec=null,_chunks=[];
function relatoAudio(){
  document.getElementById('relato-actions').style.display='none';
  document.getElementById('relato-audio-area').style.display='block';
}
function toggleGravacao(){
  var btn=document.getElementById('btn-rec');
  if(!_rec||_rec.state==='inactive'){
    navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){
      _chunks=[];
      _rec=new MediaRecorder(stream);
      _rec.ondataavailable=function(e){if(e.data.size>0)_chunks.push(e.data);};
      _rec.onstop=function(){document.getElementById('btn-send-audio').style.display='inline-block';};
      _rec.start();
      btn.textContent='\u23f9 Parar gravação';
      btn.classList.add('recording');
      document.getElementById('audio-status').textContent='Gravando...';
    });
  } else {
    _rec.stop();_rec.stream.getTracks().forEach(function(t){t.stop();});
    btn.textContent='\u23fa Iniciar gravação';
    btn.classList.remove('recording');
    document.getElementById('audio-status').textContent='Gravação concluída. Clique em Enviar.';
  }
}
function enviarRelato(){
  var texto=document.getElementById('relato-input').value.trim();
  if(!texto)return;
  var btn=document.querySelector('.relato-submit');
  btn.textContent='Salvando...';btn.disabled=true;
  var fd=new FormData();fd.append('texto',texto);
  fetch('/dashboard/relato',{method:'POST',body:fd})
    .then(function(r){return r.json().then(function(j){return{ok:r.ok,j:j};});})
    .then(function(res){
      if(res.ok&&res.j.ok){location.reload();}
      else{btn.textContent='Erro: '+(res.j.error||'tente novamente');btn.disabled=false;}
    })
    .catch(function(){btn.textContent='Erro de conexão';btn.disabled=false;});
}
function enviarAudio(){
  var blob=new Blob(_chunks,{type:'audio/webm'});
  var fd=new FormData();fd.append('audio',blob,'relato.webm');
  document.getElementById('audio-status').textContent='Enviando e transcrevendo...';
  document.getElementById('btn-send-audio').disabled=true;
  fetch('/dashboard/relato-audio',{method:'POST',body:fd})
    .then(function(r){
      if(r.ok||r.redirected){location.reload();}
      else{document.getElementById('audio-status').textContent='Erro ao transcrever. Tente novamente.';document.getElementById('btn-send-audio').disabled=false;}
    })
    .catch(function(){document.getElementById('audio-status').textContent='Erro de conexão.';document.getElementById('btn-send-audio').disabled=false;});
}
// ── Relato embutido no histórico ─────────────────────────────────────────────
function abrirRelatoEmbutido(di){
  var form=document.getElementById('relato-'+di+'-form');
  var ta=document.getElementById('relato-'+di+'-textarea');
  if(form){form.style.display=form.style.display==='none'?'block':'none';}
  if(ta){ta.style.display='block';}
}
function salvarRelatoEmbutido(di){
  var inp=document.getElementById('relato-'+di+'-input');
  if(!inp)return;
  var texto=inp.value.trim();
  if(!texto)return;
  var fd=new FormData();fd.append('texto',texto);fd.append('data',di);
  fetch('/dashboard/relato',{method:'POST',body:fd})
    .then(function(r){return r.json().then(function(j){return{ok:r.ok,j:j};});})
    .then(function(res){if(res.ok&&res.j.ok){location.reload();}})
    .catch(function(){});
}
// ── Remédios quick update ────────────────────────────────────────────────────
function remedUpdate(nome,delta){
  var fd=new FormData();fd.append('nome',nome);fd.append('delta',delta);
  fetch('/dashboard/remed-atualizar',{method:'POST',body:fd})
    .then(function(r){if(r.ok)location.reload();});
}
// ── Contextos toggle ─────────────────────────────────────────────────────────
function toggleContexto(el, label){
  el.classList.toggle('active');
  var fd=new FormData();fd.append('label',label);
  fetch('/dashboard/contexto-toggle',{method:'POST',body:fd})
    .catch(function(){ el.classList.toggle('active'); }); // revert on error
}
// ── Alimentação ──────────────────────────────────────────────────────────────
var _alimTimer=null;
function alimInput(v){
  document.getElementById('alim-val-display').textContent=v;
  document.getElementById('alim-label-display').textContent=alimLabel(v);
  clearTimeout(_alimTimer);
  _alimTimer=setTimeout(function(){
    var fd=new FormData();fd.append('valor',v);
    fetch('/dashboard/alimentacao-atualizar',{method:'POST',body:fd});
  },600);
}
function alimLabel(v){
  v=parseInt(v);
  if(v<=1)return'Besteira';if(v<=2)return'Ruim';if(v<=3)return'Regular';if(v<=4)return'Boa';return'Saudável';
}
</script>
<!-- Modal editar -->
<div class="modal" id="modal">
<div class="modal-box">
  <div class="modal-title">&#9998; Editar registro</div>
  <form method="post" action="/dashboard/editar">
  <input type="hidden" name="data" id="ed-data">
  <div class="field-grid">
    <div class="field"><label>&#10024; Humor</label><input name="saude_mental" id="ed-me" type="number" min="1" max="5"></div>
    <div class="field"><label>&#9889; Energia</label><input name="energia" id="ed-en" type="number" min="1" max="5"></div>
    <div class="field"><label>&#10084; Dor física</label><input name="dor_fisica" id="ed-dor" type="number" min="1" max="5"></div>
    <div class="field"><label>&#9733; Sono (horas)</label><input name="sono_horas" id="ed-sh" type="number" min="0" max="16" step="0.5"></div>
    <div class="field"><label>&#9693; Sono qualidade</label><input name="sono_qualidade" id="ed-sq" type="number" min="1" max="5"></div>
    <div class="field"><label>&#9200; Stress trabalho</label><input name="stress_trabalho" id="ed-st" type="number" min="1" max="5"></div>
    <div class="field"><label>&#9829; Stress rel.</label><input name="stress_relacionamento" id="ed-sr" type="number" min="1" max="5"></div>
    <div class="field"><label>&#9749; Álcool</label><input name="alcool" id="ed-al" type="text" placeholder="Nenhum / Pouco / Moderado / Muito"></div>
    <div class="field"><label>&#10006; Cigarros</label><input name="cigarros" id="ed-ci" type="number" min="0"></div>
    <div class="field"><label>&#9728; Social</label><input name="desempenho_social" id="ed-so" type="number" min="1" max="5"></div>
    <div class="field"><label>&#127803; Alimentação (1-5)</label><input name="alimentacao" id="ed-alim" type="number" min="1" max="5"></div>
    <div class="field"><label>&#9654; Exercício</label><select name="exercicio" id="ed-ex" style="width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;padding:10px 12px;font-family:inherit;outline:none"><option value="Nenhum">Nenhum</option><option value="Leve">Leve</option><option value="Moderado">Moderado</option><option value="Intenso">Intenso</option></select></div>
  </div>
  <div class="modal-section">
    <div class="modal-section-title">&#128138; Relato</div>
    <div class="field"><textarea name="nota_raw" id="ed-relato" placeholder="O que marcou esse dia? Gatilhos, momentos, como você se sentiu..."></textarea></div>
  </div>
  <div class="modal-section">
    <div class="modal-section-title">&#128138; Remédios</div>
    <div style="display:flex;flex-direction:column;gap:8px" id="ed-remed-list">REMED_MODAL_PLACEHOLDER</div>
    <input type="hidden" name="remedios_tomados" id="ed-remed-json">
  </div>
  <div class="modal-section">
    <div class="modal-section-title">&#127381; Contextos</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px">CTX_MODAL_PLACEHOLDER</div>
    <input type="hidden" name="contextos_dia" id="ed-ctx-json">
  </div>
  <div class="modal-footer">
    <button type="button" class="btn-cancel" onclick="closeModal()">Cancelar</button>
    <button type="submit" class="btn-save" onclick="buildRemedJson();buildCtxJson()">Salvar alterações</button>
  </div>
  </form>
</div>
</div>
<form id="form-del" method="post" action="/dashboard/remover" style="display:none">
  <input type="hidden" name="data" id="del-data">
</form>
</body>
</html>"""


def _render(body: str, remed_modal_html: str = "", ctx_modal_html: str = "") -> str:
    return (
        _HTML_SHELL
        .replace("CSS_PLACEHOLDER", _CSS)
        .replace("BODY_PLACEHOLDER", body)
        .replace("REMED_MODAL_PLACEHOLDER", remed_modal_html)
        .replace("CTX_MODAL_PLACEHOLDER", ctx_modal_html)
    )


# ---------------------------------------------------------------------------
# Route GET /dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_get():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT data, dor_fisica, energia, sono_horas, sono_qualidade,
                       saude_mental, stress_trabalho, stress_relacionamento,
                       alcool, exercicio, cigarros, desempenho_social,
                       nota_raw, nota_resumo_ia, nota_sentimento, nota_categorias,
                       remedios_tomados, contextos_dia, alimentacao
                FROM checkins WHERE user_id = 1
                ORDER BY data DESC LIMIT 7
                """,
            )
            streak_row = await conn.fetchrow(
                "SELECT streak_atual, streak_maximo FROM streak WHERE user_id = 1"
            )
            media = await conn.fetchrow(
                """
                SELECT ROUND(AVG(dor_fisica),1) AS dor, ROUND(AVG(energia),1) AS energia,
                       ROUND(AVG(sono_horas),1) AS sono_h, ROUND(AVG(sono_qualidade),1) AS sono_q,
                       ROUND(AVG(saude_mental),1) AS mental, ROUND(AVG(stress_trabalho),1) AS stress_t,
                       ROUND(AVG(stress_relacionamento),1) AS stress_r, ROUND(AVG(cigarros),1) AS cigarros,
                       ROUND(AVG(desempenho_social),1) AS social
                FROM checkins WHERE user_id = 1 AND data >= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date - 6
                """,
            )
            heat_rows = await conn.fetch(
                """
                SELECT data, saude_mental FROM checkins
                WHERE user_id = 1 AND data >= (NOW() AT TIME ZONE 'America/Sao_Paulo')::date - 29
                ORDER BY data ASC
                """,
            )
            remedios_padrao = await conn.fetch(
                "SELECT DISTINCT ON (nome) id, nome, dose_padrao, tipo FROM remedios WHERE user_id = 1 AND ativo = TRUE ORDER BY nome, id"
            )
            contextos_lista = await conn.fetch(
                "SELECT label, ativo FROM contextos_config WHERE user_id = 1 ORDER BY ordem, id"
            )
            session_hoje = await conn.fetchrow(
                "SELECT status FROM checkin_sessions WHERE user_id=1 AND data_referencia=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date ORDER BY id DESC LIMIT 1"
            )
    except Exception as e:
        return _render(f'<div class="empty-state"><div class="es-icon">\u26a0</div><div class="es-title">Erro ao carregar</div><div class="es-sub">{e}</div></div>')

    _sp_tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
    _agora_sp = datetime.now(_sp_tz)
    hora_sp = _agora_sp.hour
    hoje = _agora_sp.date()
    saudacao = "Bom dia" if hora_sp < 12 else ("Boa tarde" if hora_sp < 18 else "Boa noite")

    checkin_hoje = rows[0] if rows and rows[0]["data"] == hoje else None
    checkin_hoje_completo = checkin_hoje and (session_hoje is not None and session_hoje["status"] == "concluido")
    ref = next((r for r in rows if r["saude_mental"] is not None), None)

    # Botão check-in contextual
    if checkin_hoje_completo:
        checkin_area = (
            '<div class="header-right">'
            '<span class="checkin-done">&#10003; Check-in feito</span>'
            f'<button class="checkin-edit-btn" onclick="openEdit(this)" '
            f'data-data="{hoje.isoformat()}" '
            f'data-dor="{checkin_hoje["dor_fisica"] or ""}" '
            f'data-en="{checkin_hoje["energia"] or ""}" '
            f'data-sh="{checkin_hoje["sono_horas"] or ""}" '
            f'data-sq="{checkin_hoje["sono_qualidade"] or ""}" '
            f'data-me="{checkin_hoje["saude_mental"] or ""}" '
            f'data-st="{checkin_hoje["stress_trabalho"] or ""}" '
            f'data-sr="{checkin_hoje["stress_relacionamento"] or ""}" '
            f'data-al="{checkin_hoje["alcool"] or ""}" '
            f'data-ci="{checkin_hoje["cigarros"] or ""}" '
            f'data-so="{checkin_hoje["desempenho_social"] or ""}" '
            f'data-ex="{checkin_hoje["exercicio"] or ""}" '
            f'data-alim="{checkin_hoje["alimentacao"] if checkin_hoje["alimentacao"] is not None else ""}" '
            f'data-relato="{_html_mod.escape(checkin_hoje["nota_raw"] or "")}" '
            f'data-rj="{_html_mod.escape(_json.dumps(checkin_hoje["remedios_tomados"] if isinstance(checkin_hoje["remedios_tomados"], list) else (_json.loads(checkin_hoje["remedios_tomados"]) if checkin_hoje["remedios_tomados"] else []))  )}" '
            f'data-ctx="{_html_mod.escape(_json.dumps(checkin_hoje["contextos_dia"] if isinstance(checkin_hoje["contextos_dia"], list) else (_json.loads(checkin_hoje["contextos_dia"]) if checkin_hoje["contextos_dia"] else [])))}"'
            '>&#9998; Editar</button>'
            '</div>'
        )
    elif checkin_hoje:
        checkin_area = (
            '<div class="header-right">'
            '<span class="checkin-done" style="background:#1c1a0e;color:#FCD34D;border-color:#3d3510">\u23f3 Parcial</span>'
            f'<button class="checkin-edit-btn" onclick="openEdit(this)" '
            f'data-data="{hoje.isoformat()}" '
            f'data-dor="{checkin_hoje["dor_fisica"] or ""}" '
            f'data-en="{checkin_hoje["energia"] or ""}" '
            f'data-sh="{checkin_hoje["sono_horas"] or ""}" '
            f'data-sq="{checkin_hoje["sono_qualidade"] or ""}" '
            f'data-me="{checkin_hoje["saude_mental"] or ""}" '
            f'data-st="{checkin_hoje["stress_trabalho"] or ""}" '
            f'data-sr="{checkin_hoje["stress_relacionamento"] or ""}" '
            f'data-al="{checkin_hoje["alcool"] or ""}" '
            f'data-ci="{checkin_hoje["cigarros"] or ""}" '
            f'data-so="{checkin_hoje["desempenho_social"] or ""}" '
            f'data-ex="{checkin_hoje["exercicio"] or ""}" '
            f'data-alim="{checkin_hoje["alimentacao"] if checkin_hoje["alimentacao"] is not None else ""}" '
            f'data-relato="{_html_mod.escape(checkin_hoje["nota_raw"] or "")}" '
            f'data-rj="{_html_mod.escape(_json.dumps(checkin_hoje["remedios_tomados"] if isinstance(checkin_hoje["remedios_tomados"], list) else (_json.loads(checkin_hoje["remedios_tomados"]) if checkin_hoje["remedios_tomados"] else []))  )}" '
            f'data-ctx="{_html_mod.escape(_json.dumps(checkin_hoje["contextos_dia"] if isinstance(checkin_hoje["contextos_dia"], list) else (_json.loads(checkin_hoje["contextos_dia"]) if checkin_hoje["contextos_dia"] else [])))}"'
            '>&#9998; Editar</button>'
            '<a class="checkin-btn" href="/checkin-web" style="background:#1c3a1c;color:#86EFAC;border:1px solid #1a5c1a">\u2714 Completar</a>'
            '</div>'
        )
    else:
        checkin_area = '<div class="header-right"><a class="checkin-btn" href="/checkin-web">+ Check-in</a></div>'

    cfg_btn = '<a href="/dashboard/configuracoes" style="background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:10px 12px;font-size:16px;color:var(--text3);display:inline-flex;align-items:center" title="Configura\u00e7\u00f5es">&#9881;</a>'
    # Inject cfg_btn inside checkin_area's header-right div
    checkin_area_with_cfg = checkin_area.replace('</div>', f'{cfg_btn}</div>', 1)
    body = f"""
<div class="header">
  <div class="header-left">
    <div style="font-size:14px;font-weight:600;color:var(--text2);letter-spacing:.5px;text-transform:uppercase">{saudacao}</div>
    <div class="greeting">Monitoramento Mental</div>
  </div>
  {checkin_area_with_cfg}
</div>"""

    # ---- Hero ----
    mental_hoje = ref["saude_mental"] if ref else None
    energia_hoje = ref["energia"] if ref else None
    dor_hoje = ref["dor_fisica"] if ref else None
    sono_hoje = ref["sono_horas"] if ref else None
    ex_hoje = ref["exercicio"] if ref else None
    frase = _hero_frase(mental_hoje, energia_hoje, dor_hoje)
    score_color = _score_color(mental_hoje) if mental_hoje is not None else "#4A4A5A"
    score_display = mental_hoje if mental_hoje is not None else "\u2014"
    try:
        data_display = ref["data"].strftime("%-d de %B") if ref else "sem dados"
    except ValueError:
        data_display = ref["data"].strftime("%d de %B") if ref else "sem dados"

    if checkin_hoje_completo:
        checkin_status = '<span style="background:#14532d;color:#86EFAC;border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600">\u2713 check-in feito</span>'
    elif checkin_hoje:
        checkin_status = '<span style="background:#1c1a0e;color:#FCD34D;border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600">\u23f3 parcial</span>'
    else:
        checkin_status = '<span style="background:#1e293b;color:#94A3B8;border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600">check-in pendente</span>'

    chips = ""
    if energia_hoje is not None:
        chips += f'<div class="hero-chip"><span class="hc-val" style="color:#67E8F9">{energia_hoje}</span><div class="hc-lbl">\u26a1 Energia</div></div>'
    if sono_hoje is not None:
        chips += f'<div class="hero-chip"><span class="hc-val" style="color:#A78BFA">{sono_hoje}h</span><div class="hc-lbl">\u2605 Sono</div></div>'
    if dor_hoje is not None:
        dor_c = _score_color(dor_hoje, invert=True)
        chips += f'<div class="hero-chip"><span class="hc-val" style="color:{dor_c}">{dor_hoje}</span><div class="hc-lbl">\u2764 Dor</div></div>'
    if ex_hoje and ex_hoje != "Nenhum":
        chips += f'<div class="hero-chip"><span class="hc-val" style="color:#86EFAC;font-size:14px">{ex_hoje}</span><div class="hc-lbl">\u25b6 Exerc\xedcio</div></div>'

    # Emoji scale visual (1-5)
    HUMOR_EMOJIS = ["\U0001f62d", "\U0001f615", "\U0001f610", "\U0001f642", "\U0001f604"]
    HUMOR_COLORS = ["#EF4444", "#F97316", "#FCD34D", "#86EFAC", "#22C55E"]
    HUMOR_LABELS = ["Muito mal", "Mal", "Regular", "Bem", "Muito bem"]
    emoji_scale_html = '<div style="display:flex;gap:6px;margin-top:14px;align-items:flex-end">'
    for i, (em, col, lbl) in enumerate(zip(HUMOR_EMOJIS, HUMOR_COLORS, HUMOR_LABELS)):
        nivel = i + 1
        is_active = mental_hoje is not None and int(round(float(mental_hoje))) == nivel
        if is_active:
            emoji_scale_html += (
                f'<div style="display:flex;flex-direction:column;align-items:center;flex:1">'
                f'<div style="font-size:38px;line-height:1;filter:none">{em}</div>'
                f'<div style="font-size:9px;color:{col};font-weight:700;margin-top:4px;text-align:center;letter-spacing:.3px">{lbl}</div>'
                f'<div style="width:100%;height:3px;background:{col};border-radius:2px;margin-top:4px"></div>'
                f'</div>'
            )
        else:
            emoji_scale_html += (
                f'<div style="display:flex;flex-direction:column;align-items:center;flex:1;opacity:.3">'
                f'<div style="font-size:26px;line-height:1">{em}</div>'
                f'<div style="width:100%;height:3px;background:var(--border);border-radius:2px;margin-top:8px"></div>'
                f'</div>'
            )
    emoji_scale_html += '</div>'

    body += f"""
<div class="hero">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
    <div class="hero-label" style="padding:0;margin:0">Humor \u2014 {data_display}</div>
    {checkin_status}
  </div>
  <div class="hero-score" style="color:{score_color};font-size:80px;font-weight:900;line-height:1">{score_display}<span style="font-size:22px;font-weight:500;opacity:.6"> /5</span></div>
  {emoji_scale_html}
  <div class="hero-frase" style="margin-top:14px">{frase}</div>
  {f'<div class="hero-meta">{chips}</div>' if chips else ''}
</div>"""

    if not rows:
        s_atual = streak_row["streak_atual"] if streak_row else 0
        s_max = streak_row["streak_maximo"] if streak_row else 0
        body += f"""
<div class="sec-label">Consist\xeancia</div>
<div class="streak-card">
  <div class="streak-row">
    <div class="streak-num">\U0001f525 {s_atual}</div>
    <div class="streak-info">
      <div class="streak-frase">{_streak_frase(s_atual, s_max)}</div>
      <div class="streak-max">M\xe1ximo: {s_max} dias</div>
    </div>
  </div>
</div>
<div style="margin:0 24px">
  <div class="empty-state">
    <div class="es-icon">\U0001f4cb</div>
    <div class="es-title">Nenhum registro ainda</div>
    <div class="es-sub">Seus dados v\xe3o aparecer aqui depois do primeiro check-in.</div>
  </div>
</div>"""
        return _render(body)

    # =========================================================================
    # Dashboard com dados
    # =========================================================================
    m = media

    # ---- Consistência + heatmap ----
    s_atual = streak_row["streak_atual"] if streak_row else 0
    s_max = streak_row["streak_maximo"] if streak_row else 0
    heat_map = {r["data"]: r["saude_mental"] for r in heat_rows}
    dots = ""
    for i in range(29, -1, -1):
        d = hoje - timedelta(days=i)
        mental_val = heat_map.get(d)
        color = _dot_color(mental_val)
        title = d.strftime("%d/%m") + (f" \u2014 {mental_val}" if mental_val is not None else " \u2014 sem dado")
        dots += f'<div class="dot" style="background:{color}" title="{title}"></div>'

    body += f"""
<div class="sec-label">Consist\xeancia</div>
<div class="streak-card">
  <div class="streak-row">
    <div class="streak-num">\U0001f525 {s_atual}</div>
    <div class="streak-info">
      <div class="streak-frase">{_streak_frase(s_atual, s_max)}</div>
      <div class="streak-max">M\xe1ximo: {s_max} dias</div>
    </div>
  </div>
  <div class="heatmap">{dots}</div>
</div>"""

    # ---- Médias da semana ----
    alcool_vals = [r["alcool"] for r in rows if r["alcool"]]
    alcool_moda = max(set(alcool_vals), key=alcool_vals.count) if alcool_vals else None
    alcool_display = alcool_moda or "\u2014"

    body += f"""
<details class="medias-section" open>
<summary class="sec-label medias-section-label" style="padding-top:16px;cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between">M\xe9dia da semana<span class="medias-toggle-icon">&#9660;</span></summary>
<div class="dim-grid">
  <div class="dim-card">
    <div class="dim-title">\u2728 Mental &amp; Emocional</div>
    {_dim_row("Humor", m["mental"] if m else None)}
    {_dim_row("Stress trabalho", m["stress_t"] if m else None, invert=True)}
    {_dim_row("Stress rel.", m["stress_r"] if m else None, invert=True)}
  </div>
  <div class="dim-card">
    <div class="dim-title">\u26a1 Energia &amp; Sono</div>
    {_dim_row("Energia", m["energia"] if m else None)}
    {_dim_row("Sono (h)", m["sono_h"] if m else None, max_val=16)}
    {_dim_row("Qualidade sono", m["sono_q"] if m else None)}
  </div>
  <div class="dim-card">
    <div class="dim-title">\u2764 F\xedsico &amp; Social</div>
    {_dim_row("Dor f\xedsica", m["dor"] if m else None, invert=True)}
    {_dim_row("Desempenho social", m["social"] if m else None)}
  </div>
  <div class="dim-card">
    <div class="dim-title">\u2615 H\xe1bitos</div>
    {_dim_row("Cigarros/dia", m["cigarros"] if m else None, max_val=20, invert=True)}
    <div class="dim-row"><span class="dim-lbl">\xc1lcool (freq.)</span><span style="font-size:13px;font-weight:600;color:var(--text)">{alcool_display}</span></div>
  </div>
</div>
</details>"""

    # ---- Remédios prioritários ----
    # ---- Exercício (histórico 7 dias) ----
    EX_CORES = {"Nenhum": "#2A2A38", "Leve": "#FCD34D", "Moderado": "#86EFAC", "Intenso": "#A78BFA"}
    EX_ALTURA = {"Nenhum": 4, "Leve": 16, "Moderado": 28, "Intenso": 40}
    EX_ICONE = {"Nenhum": "", "Leve": "\U0001f6b6", "Moderado": "\U0001f3c3", "Intenso": "\U0001f3c3\U0001f525"}
    ex_html = ""
    for r in list(reversed(rows))[-7:]:
        ex_val = r["exercicio"] or "Nenhum"
        cor = EX_CORES.get(ex_val, "#2A2A38")
        altura = EX_ALTURA.get(ex_val, 4)
        icone = EX_ICONE.get(ex_val, "")
        ds_ex = r["data"].strftime("%d/%m")
        icone_html = f'<div style="font-size:13px;line-height:1">{icone}</div>' if icone else '<div style="font-size:13px;line-height:1;opacity:0">\U0001f6b6</div>'
        ex_html += f'<div class="ex-day">{icone_html}<div class="ex-bar" style="height:{altura}px;background:{cor}"></div><div class="ex-day-lbl">{ds_ex}</div></div>'
    body += f"""
<div class="sec-label">Exerc\xedcio</div>
<div class="ex-card">
  <div class="ex-title">Intensidade \u2014 7 dias</div>
  <div class="ex-week">{ex_html}</div>
</div>"""

    # ---- Gráfico de tendências ----
    import json as _json2
    chart_rows = list(reversed(rows))  # cronológico: mais antigo primeiro
    chart_labels = _json2.dumps([r["data"].strftime("%d/%m") for r in chart_rows])
    def _chart_series(field, rows_=chart_rows):
        return _json2.dumps([float(r[field]) if r[field] is not None else None for r in rows_])
    chart_mental  = _chart_series("saude_mental")
    chart_energia = _chart_series("energia")
    chart_sono    = _chart_series("sono_horas")
    chart_sono_q  = _chart_series("sono_qualidade")
    chart_dor     = _chart_series("dor_fisica")
    chart_stress_t= _chart_series("stress_trabalho")
    chart_stress_r= _chart_series("stress_relacionamento")
    chart_social  = _chart_series("desempenho_social")
    # doses de remédios por dia
    def _remed_series(nome_remed, rows_=chart_rows):
        out = []
        for r in rows_:
            rj = r["remedios_tomados"]
            try:
                itens = (rj if isinstance(rj, list) else _json2.loads(rj)) if rj else []
                val = next((float(i.get("qtd", 0)) for i in itens if i.get("nome","").lower() == nome_remed.lower() and i.get("tomado")), None)
            except Exception:
                val = None
            out.append(val)
        return _json2.dumps(out)
    chart_rivotril = _remed_series("Rivotril")
    chart_zolpidem = _remed_series("Zolpidem")
    body += f"""
<details class="trend-section" open>
<summary class="sec-label trend-section-label" style="padding-top:16px;cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between">Tend\xeancia<span class="trend-toggle-icon">&#9660;</span></summary>
<div class="chart-card">
  <div class="chart-toggles" id="chart-toggles">
    <button class="chart-toggle on" data-serie="mental"    style="border-color:#86EFAC;background:#86EFAC22;color:#86EFAC"  onclick="toggleSerie(this)">Humor</button>
    <button class="chart-toggle on" data-serie="energia"   style="border-color:#FCD34D;background:#FCD34D22;color:#FCD34D"  onclick="toggleSerie(this)">Energia</button>
    <button class="chart-toggle on" data-serie="sono"      style="border-color:#A78BFA;background:#A78BFA22;color:#A78BFA"  onclick="toggleSerie(this)">Sono (h)</button>
    <button class="chart-toggle"    data-serie="sono_q"    style="border-color:#7DD3FC;background:var(--surface2);color:var(--text3)"  onclick="toggleSerie(this)">Sono qual.</button>
    <button class="chart-toggle"    data-serie="dor"       style="border-color:#FCA5A5;background:var(--surface2);color:var(--text3)"  onclick="toggleSerie(this)">Dor</button>
    <button class="chart-toggle"    data-serie="stress_t"  style="border-color:#F97316;background:var(--surface2);color:var(--text3)"  onclick="toggleSerie(this)">Stress trab.</button>
    <button class="chart-toggle"    data-serie="stress_r"  style="border-color:#FB923C;background:var(--surface2);color:var(--text3)"  onclick="toggleSerie(this)">Stress rel.</button>
    <button class="chart-toggle"    data-serie="social"    style="border-color:#34D399;background:var(--surface2);color:var(--text3)"  onclick="toggleSerie(this)">Social</button>
    <button class="chart-toggle"    data-serie="rivotril"  style="border-color:#C084FC;background:var(--surface2);color:var(--text3)"  onclick="toggleSerie(this)">Rivotril</button>
    <button class="chart-toggle"    data-serie="zolpidem"  style="border-color:#67E8F9;background:var(--surface2);color:var(--text3)"  onclick="toggleSerie(this)">Zolpidem</button>
  </div>
  <canvas id="trend-chart" height="160"></canvas>
</div>
<script>
(function(){{
  var labels = {chart_labels};
  var allData = {{
    mental:   {chart_mental},
    energia:  {chart_energia},
    sono:     {chart_sono},
    sono_q:   {chart_sono_q},
    dor:      {chart_dor},
    stress_t: {chart_stress_t},
    stress_r: {chart_stress_r},
    social:   {chart_social},
    rivotril: {chart_rivotril},
    zolpidem: {chart_zolpidem}
  }};
  var colors = {{
    mental:"#86EFAC", energia:"#FCD34D", sono:"#A78BFA", sono_q:"#7DD3FC",
    dor:"#FCA5A5", stress_t:"#F97316", stress_r:"#FB923C", social:"#34D399",
    rivotril:"#C084FC", zolpidem:"#67E8F9"
  }};
  var names = {{
    mental:"Humor", energia:"Energia", sono:"Sono (h)", sono_q:"Sono qual.",
    dor:"Dor", stress_t:"Stress trab.", stress_r:"Stress rel.", social:"Social",
    rivotril:"Rivotril", zolpidem:"Zolpidem"
  }};
  var active = {{"mental":true,"energia":true,"sono":true}};

  function buildDatasets(){{
    return Object.keys(active).filter(k=>active[k]).map(k=>{{
      return {{
        label: names[k],
        data: allData[k],
        borderColor: colors[k],
        backgroundColor: colors[k]+"33",
        borderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 5,
        tension: 0.3,
        spanGaps: true
      }};
    }});
  }}

  var ctx = document.getElementById("trend-chart").getContext("2d");
  var chart = new Chart(ctx, {{
    type: "line",
    data: {{ labels: labels, datasets: buildDatasets() }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ mode: "index", intersect: false }}
      }},
      scales: {{
        x: {{ ticks: {{ color:"#94A3B8", font:{{size:11}} }}, grid:{{ color:"#2A2A38" }} }},
        y: {{ min:0, ticks:{{ color:"#94A3B8", font:{{size:11}}, stepSize:1 }}, grid:{{ color:"#2A2A38" }} }}
      }}
    }}
  }});

  window.toggleSerie = function(btn){{
    var serie = btn.dataset.serie;
    var isOn = active[serie];
    if(isOn){{
      delete active[serie];
      btn.style.background = "var(--surface2)";
      btn.style.color = "var(--text3)";
    }} else {{
      active[serie] = true;
      btn.style.background = colors[serie]+"22";
      btn.style.color = colors[serie];
    }}
    chart.data.datasets = buildDatasets();
    chart.update();
  }};
}})();
</script>
</details>"""

    REMED_PRIORITARIOS = {"rivotril", "zolpidem"}
    hist_doses = {}
    _remed_padrao = [
        {"nome": r["nome"], "qtd": float(r["dose_padrao"] or 1), "tomado": True}
        for r in remedios_padrao
    ]
    for r in rows:
        rj = r["remedios_tomados"]
        data_str_r = r["data"].strftime("%d/%m")
        try:
            itens = (rj if isinstance(rj, list) else _json.loads(rj)) if rj else []
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

    body += '<div class="sec-label">Rem\xe9dios</div>'
    remed_prio_html = ""
    for nome_prio in ["Rivotril", "Zolpidem"]:
        doses = hist_doses.get(nome_prio, [])
        dose_hoje_val = None
        if checkin_hoje and checkin_hoje["remedios_tomados"]:
            try:
                rj_hoje = checkin_hoje["remedios_tomados"]
                arr_hoje = (rj_hoje if isinstance(rj_hoje, list) else _json.loads(rj_hoje)) if rj_hoje else []
                for item in arr_hoje:
                    if item.get("nome", "").lower() == nome_prio.lower() and item.get("tomado"):
                        dose_hoje_val = item.get("qtd", 0)
                        break
            except Exception:
                pass
        elif doses:
            dose_hoje_val = doses[0][1]

        dose_display = f'{dose_hoje_val:g}' if dose_hoje_val is not None else "\u2014"
        baseline = next((float(r["dose_padrao"] or 1) for r in remedios_padrao if r["nome"].lower() == nome_prio.lower()), 1)
        max_dose = max((d[1] for d in doses), default=baseline) or 1

        # média geral e comparação com hoje
        media_doses = (sum(d[1] for d in doses) / len(doses)) if doses else None
        if media_doses is not None and dose_hoje_val is not None:
            diff = dose_hoje_val - media_doses
            if abs(diff) < 0.1:
                comp_html = '<span style="font-size:11px;color:#94A3B8">\u2022 na m\xe9dia</span>'
            elif diff > 0:
                comp_html = f'<span style="font-size:11px;color:#FCA5A5">\u2191 +{diff:.1g} vs m\xe9dia</span>'
            else:
                comp_html = f'<span style="font-size:11px;color:#86EFAC">\u2193 {diff:.1g} vs m\xe9dia</span>'
        else:
            comp_html = ""
        media_display = f'{media_doses:.1f}' if media_doses is not None else "\u2014"

        barras = ""
        doses_crono = list(reversed(doses[:7]))
        for i, (ds_r, qtd) in enumerate(doses_crono):
            h = max(4, int((qtd / max_dose) * 40))
            cls = "remed-hist-bar today" if i == len(doses_crono) - 1 else "remed-hist-bar"
            barras += f'<div style="flex:1;display:flex;flex-direction:column;align-items:center"><div class="{cls}" style="height:{h}px;width:100%"></div><div class="remed-hist-label">{ds_r}</div></div>'
        hist_inner = barras if barras else '<span style="font-size:12px;color:var(--text3)">sem hist\xf3rico</span>'

        remed_prio_html += f"""
<div class="remed-priority-card">
  <div class="remed-priority-name">{nome_prio}</div>
  <div style="display:flex;align-items:center;justify-content:space-between">
    <div class="remed-priority-dose" id="remed-qtd-{nome_prio}">{dose_display}<span> comp.</span></div>
    <div style="display:flex;gap:6px">
      <button class="remed-upd-btn" onclick="remedUpdate('{nome_prio}',-1)">&#8722;</button>
      <button class="remed-upd-btn remed-upd-plus" onclick="remedUpdate('{nome_prio}',1)">+</button>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:8px;margin:4px 0 2px">
    <span style="font-size:11px;color:var(--text3)">m\xe9dia: {media_display} comp.</span>
    {comp_html}
  </div>
  <div class="remed-priority-hist">{hist_inner}</div>
  <div class="remed-baseline">padr\xe3o: {baseline:g} comp.</div>
</div>"""

    body += f'<div class="remed-priority-grid">{remed_prio_html}</div>'

    secundarios = [r for r in _remed_padrao if r["nome"].lower() not in REMED_PRIORITARIOS]
    if secundarios:
        sec_items = "".join(f'<span class="remed-sec-item">{_html_mod.escape(s["nome"])}</span>' for s in secundarios)
        body += f'<div class="remed-sec"><span class="remed-sec-label">Outros</span>{sec_items}</div>'

    # ---- Histórico expandível (com relato, exercício, contextos, alimentação por dia) ----
    EX_CORES = {"Nenhum": "#2A2A38", "Leve": "#FCD34D", "Moderado": "#86EFAC", "Intenso": "#A78BFA"}

    ctx_ativos = [c["label"] for c in contextos_lista if c["ativo"]]

    # Montar mapa de dias com dados e preencher dias faltantes dos últimos 7
    rows_by_date = {r["data"]: r for r in rows}
    dias_7 = [hoje - timedelta(days=i) for i in range(6, -1, -1)]  # 6 dias atrás até hoje, cronológico inverso
    dias_7 = list(reversed(dias_7))  # mais recente primeiro

    body += '<details class="hist-section" id="hist-section"><summary class="sec-label hist-section-label" style="padding-top:16px;cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between">Hist\xf3rico<span class="hist-toggle-icon">&#9660;</span></summary>'
    body += '<div class="hist-compact">'
    for dia in dias_7:
        r = rows_by_date.get(dia)
        if r is None:
            # Dia sem checkin — mostrar linha com link para preencher
            ds = dia.strftime("%d/%m")
            di = dia.isoformat()
            body += (
                f'<div class="hist-row" style="opacity:.5">'
                f'<span class="hist-date">{ds}</span>'
                f'<div class="hist-vals" style="color:var(--text3);font-size:11px">sem registro</div>'
                f'<div class="hist-acts">'
                f'<a href="/checkin-web?data={di}" class="act-btn" style="padding:4px 8px;font-size:11px;text-decoration:none">+ preencher</a>'
                f'</div></div>'
            )
            continue
        di = r["data"].isoformat()
        ds = r["data"].strftime("%d/%m")
        me = r["saude_mental"]; en = r["energia"]; dor = r["dor_fisica"]
        sh = r["sono_horas"]; al = r["alcool"] or ""; ex = r["exercicio"] or ""
        sq = r["sono_qualidade"]; st = r["stress_trabalho"]; sr = r["stress_relacionamento"]
        so = r["desempenho_social"]; ci = r["cigarros"]
        alim = r["alimentacao"]
        nota_raw_h = r["nota_raw"] or ""
        nota_resumo_h = r["nota_resumo_ia"] or ""
        nota_sent_h = r["nota_sentimento"] or ""
        nota_cats_h = r["nota_categorias"] or []
        if isinstance(nota_cats_h, str):
            try: nota_cats_h = _json.loads(nota_cats_h)
            except Exception: nota_cats_h = []
        rj_raw = r["remedios_tomados"]
        ctx_raw = r["contextos_dia"]
        rj_esc = _html_mod.escape(_json.dumps(rj_raw if isinstance(rj_raw, list) else (_json.loads(rj_raw) if rj_raw else [])))
        ctx_esc = _html_mod.escape(_json.dumps(ctx_raw if isinstance(ctx_raw, list) else (_json.loads(ctx_raw) if ctx_raw else [])))
        nota_esc = _html_mod.escape(nota_raw_h)

        me_c = _score_color(me) if me is not None else "#4A4A5A"
        chips_h = ""
        if me is not None: chips_h += f'<span class="hist-chip" style="color:{me_c}">humor {me}</span>'
        if en is not None: chips_h += f'<span class="hist-chip">energia {en}</span>'
        if sh is not None: chips_h += f'<span class="hist-chip">sono {sh}h</span>'
        if dor is not None: chips_h += f'<span class="hist-chip">dor {dor}</span>'
        if al and al != "Nenhum": chips_h += f'<span class="hist-chip">{_html_mod.escape(al)}</span>'
        if ex and ex != "Nenhum": chips_h += f'<span class="hist-chip">{_html_mod.escape(ex)}</span>'
        if alim is not None: chips_h += f'<span class="hist-chip">alim {alim}</span>'

        # -- detalhes expandíveis --
        detail_html = ""

        # relato
        is_hoje = r["data"] == hoje
        relato_id = f"relato-{di}"
        if nota_raw_h:
            resumo_display = nota_resumo_h if nota_resumo_h else (nota_raw_h[:90] + ("…" if len(nota_raw_h) > 90 else ""))
            badge = _sent_badge(nota_sent_h)
            cats = "".join(f'<span class="relato-tag">{_html_mod.escape(str(c))}</span>' for c in nota_cats_h)
            cats_html = f'<div class="relato-cats" style="margin-top:6px">{cats}</div>' if cats else ""
            ver = (
                f'<details class="relato-expand" style="margin-top:6px">'
                f'<summary>ver relato completo</summary>'
                f'<div class="relato-raw-text">{_html_mod.escape(nota_raw_h)}</div>'
                f'</details>'
            ) if len(nota_raw_h) > 5 else ""
            detail_html += f"""
<div class="hist-detail-relato">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
    <span style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.5px">Relato</span>
    <div style="display:flex;gap:6px;align-items:center">{badge}<button class="relato-edit-btn" onclick="abrirRelatoEmbutido('{di}')" style="font-size:11px">\u270f editar</button></div>
  </div>
  <div style="font-size:13px;color:var(--text2)">{_html_mod.escape(resumo_display)}</div>
  {cats_html}{ver}
  <div id="{relato_id}-form" style="display:none;margin-top:10px">
    <textarea id="{relato_id}-input" style="width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px;padding:10px;font-family:inherit;resize:vertical" rows="3">{_html_mod.escape(nota_raw_h)}</textarea>
    <button class="relato-submit" style="margin-top:6px;font-size:13px" onclick="salvarRelatoEmbutido('{di}')">Salvar</button>
  </div>
</div>"""
        elif is_hoje:
            detail_html += f"""
<div class="hist-detail-relato">
  <div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Relato</div>
  <div id="{relato_id}-form">
    <div style="display:flex;gap:8px;margin-bottom:8px">
      <button class="relato-btn" onclick="abrirRelatoEmbutido('{di}')">\u270f\ufe0f Texto</button>
      <button class="relato-btn relato-btn-audio" onclick="relatoAudio()">\U0001f3a4 \xc1udio</button>
    </div>
    <div id="{relato_id}-textarea" style="display:none">
      <textarea id="{relato_id}-input" placeholder="Algo pontual a registrar..." style="width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px;padding:10px;font-family:inherit;resize:vertical" rows="3"></textarea>
      <button class="relato-submit" style="margin-top:6px;font-size:13px" onclick="salvarRelatoEmbutido('{di}')">Salvar</button>
    </div>
  </div>
</div>"""

        # exercício
        ex_cor = EX_CORES.get(ex or "Nenhum", "#2A2A38")
        ex_display = ex if ex else "Nenhum"
        detail_html += f'<div class="hist-detail-row"><span class="hist-detail-lbl">Exerc\xedcio</span><span style="color:{ex_cor};font-size:13px;font-weight:600">{_html_mod.escape(ex_display)}</span></div>'

        # contextos
        try:
            ctx_dia = ctx_raw if isinstance(ctx_raw, list) else (_json.loads(ctx_raw) if ctx_raw else [])
        except Exception:
            ctx_dia = []
        if ctx_dia:
            ctx_chips = "".join(f'<span class="relato-tag">{_html_mod.escape(c)}</span>' for c in ctx_dia)
            detail_html += f'<div class="hist-detail-row"><span class="hist-detail-lbl">Contextos</span><div style="display:flex;flex-wrap:wrap;gap:4px">{ctx_chips}</div></div>'

        # alimentação
        if alim is not None:
            alim_lbl_r = _alim_label(alim)
            detail_html += f'<div class="hist-detail-row"><span class="hist-detail-lbl">Alimenta\xe7\xe3o</span><span style="font-size:13px;font-weight:600;color:var(--text2)">{alim} — {alim_lbl_r}</span></div>'

        body += (
            f'<details class="hist-row-wrap">'
            f'<summary class="hist-row">'
            f'<span class="hist-date">{ds}</span>'
            f'<div class="hist-vals">{chips_h}</div>'
            f'<div class="hist-acts">'
            f'<button class="act-btn" style="padding:4px 8px;font-size:11px" '
            f'onclick="event.preventDefault();openEdit(this)" '
            f'data-data="{di}" data-dor="{dor or ""}" data-en="{en or ""}" '
            f'data-sh="{sh or ""}" data-sq="{sq or ""}" data-me="{me or ""}" '
            f'data-st="{st or ""}" data-sr="{sr or ""}" data-al="{_html_mod.escape(al)}" '
            f'data-ci="{ci or ""}" data-so="{so or ""}" data-ex="{_html_mod.escape(ex)}" '
            f'data-alim="{alim if alim is not None else ""}" '
            f'data-relato="{nota_esc}" data-rj="{rj_esc}" data-ctx="{ctx_esc}">\u270f</button>'
            f'<button class="act-btn del" style="padding:4px 8px;font-size:11px" onclick="event.preventDefault();delDay(\'{di}\')">\xd7</button>'
            f'</div>'
            f'</summary>'
            f'<div class="hist-detail">{detail_html}</div>'
            f'</details>'
        )
    body += '</div></details>'

    # ---- HTML do modal: remédios ----
    remed_modal_html = ""
    for rp in remedios_padrao:
        nome = rp["nome"]
        dp = float(rp["dose_padrao"] or 1)
        step = "1"
        remed_modal_html += (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'background:var(--surface2);border-radius:10px;padding:8px 12px">'
            f'<span style="font-size:13px;font-weight:600;color:var(--text)">{_html_mod.escape(nome)}</span>'
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<span style="font-size:11px;color:var(--text3)">qtd</span>'
            f'<input class="ed-rem-qtd" data-nome="{_html_mod.escape(nome)}" type="number" min="0" max="20" step="{step}" value="0"'
            f' style="width:60px;background:var(--surface);border:1px solid var(--border);border-radius:8px;'
            f'padding:6px 8px;color:var(--text);font-size:14px;font-weight:700;text-align:center;outline:none">'
            f'</div></div>'
        )

    # ---- HTML do modal: contextos ----
    ctx_modal_html = ""
    for c in contextos_lista:
        lbl = c["label"]
        ctx_modal_html += (
            f'<button type="button" class="ed-ctx-chip chip" data-val="{_html_mod.escape(lbl)}" '
            f'onclick="toggleCtxChip(this)">{_html_mod.escape(lbl)}</button>'
        )

    return _render(body, remed_modal_html, ctx_modal_html)


# ---------------------------------------------------------------------------
# POST /dashboard/relato
# ---------------------------------------------------------------------------

@router.post("/dashboard/relato")
async def dashboard_relato(texto: str = Form(...), data: str = Form(default="")):
    import re
    if data and re.match(r"^\d{4}-\d{2}-\d{2}$", data):
        from datetime import date as _date
        data_alvo = _date.fromisoformat(data)
    else:
        data_alvo = datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo")).date()
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO checkins (user_id, data, nota_raw)
                   VALUES (1, $2, $1)
                   ON CONFLICT (user_id, data) DO UPDATE SET nota_raw=$1""",
                texto, data_alvo,
            )
        try:
            analysis = await _process_nota_completa(texto)
            if analysis:
                sentimento = analysis.get("sentimento") or ""
                categorias = _json.dumps(analysis.get("categorias") or [], ensure_ascii=False)
                resumo_ia = analysis.get("resumo") or ""
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE checkins SET nota_sentimento=$1, nota_categorias=$2::jsonb, nota_resumo_ia=$3 "
                        "WHERE user_id=1 AND data=$4",
                        sentimento, categorias, resumo_ia, data_alvo,
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
        return JSONResponse({"error": "OpenAI n\xe3o configurado"}, status_code=503)
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
    analysis = await _process_nota_completa(texto)
    resumo_ia = analysis.get("resumo") or ""
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO checkins (user_id, data, nota_raw, nota_sentimento, nota_categorias, nota_resumo_ia)
               VALUES (1, (NOW() AT TIME ZONE 'America/Sao_Paulo')::date, $1, $2, $3::jsonb, $4)
               ON CONFLICT (user_id, data) DO UPDATE SET
               nota_raw=$1, nota_sentimento=$2, nota_categorias=$3::jsonb, nota_resumo_ia=$4""",
            texto,
            analysis.get("sentimento", ""),
            _json.dumps(analysis.get("categorias", []), ensure_ascii=False),
            resumo_ia,
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
    def _int(v): return int(v) if str(v).strip() else None
    def _float(v): return float(v) if str(v).strip() else None

    try:
        remed_json = _json.dumps(_json.loads(remedios_tomados), ensure_ascii=False) if remedios_tomados.strip() else None
    except Exception:
        remed_json = None

    try:
        ctx_json = _json.dumps(_json.loads(contextos_dia), ensure_ascii=False) if contextos_dia.strip() else "[]"
    except Exception:
        ctx_json = "[]"

    pool = get_pool()
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
            WHERE user_id=1 AND data=$1
            """,
            date.fromisoformat(data),
            _int(dor_fisica), _int(energia), _float(sono_horas), _int(sono_qualidade),
            _int(saude_mental), _int(stress_trabalho), _int(stress_relacionamento),
            alcool.strip() or None, exercicio.strip() or None, _int(cigarros), _int(desempenho_social),
            remed_json, _int(alimentacao), nota_raw.strip() or "", ctx_json,
        )
    return RedirectResponse("/dashboard", status_code=303)


# ---------------------------------------------------------------------------
# POST /dashboard/remed-atualizar
# ---------------------------------------------------------------------------

@router.post("/dashboard/remed-atualizar")
async def dashboard_remed_atualizar(nome: str = Form(...), delta: float = Form(...)):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT remedios_tomados FROM checkins WHERE user_id=1 AND data=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date"
        )
        if row is None:
            qtd = max(0.0, delta)
            arr = [{"nome": nome, "qtd": qtd, "tomado": qtd > 0}]
            await conn.execute(
                "INSERT INTO checkins (user_id, data, remedios_tomados) VALUES (1, (NOW() AT TIME ZONE 'America/Sao_Paulo')::date, $1::jsonb) ON CONFLICT DO NOTHING",
                _json.dumps(arr),
            )
        else:
            rj = row["remedios_tomados"]
            try:
                arr = (rj if isinstance(rj, list) else _json.loads(rj)) if rj else []
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
                "UPDATE checkins SET remedios_tomados=$1::jsonb WHERE user_id=1 AND data=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date",
                _json.dumps(arr),
            )
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# POST /dashboard/contexto-toggle
# ---------------------------------------------------------------------------

@router.post("/dashboard/contexto-toggle")
async def dashboard_contexto_toggle(label: str = Form(...)):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT contextos_dia FROM checkins WHERE user_id=1 AND data=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date"
        )
        if row is None:
            ctx = [label]
            await conn.execute(
                "INSERT INTO checkins (user_id, data, contextos_dia) VALUES (1, (NOW() AT TIME ZONE 'America/Sao_Paulo')::date, $1::jsonb) ON CONFLICT (user_id, data) DO UPDATE SET contextos_dia=$1::jsonb",
                _json.dumps(ctx),
            )
        else:
            cd = row["contextos_dia"]
            try:
                ctx = (cd if isinstance(cd, list) else _json.loads(cd)) if cd else []
            except Exception:
                ctx = []
            if label in ctx:
                ctx.remove(label)
            else:
                ctx.append(label)
            await conn.execute(
                "UPDATE checkins SET contextos_dia=$1::jsonb WHERE user_id=1 AND data=(NOW() AT TIME ZONE 'America/Sao_Paulo')::date",
                _json.dumps(ctx),
            )
    return JSONResponse({"ok": True, "contextos": ctx})


# ---------------------------------------------------------------------------
# POST /dashboard/alimentacao-atualizar
# ---------------------------------------------------------------------------

@router.post("/dashboard/alimentacao-atualizar")
async def dashboard_alimentacao_atualizar(valor: int = Form(...)):
    valor = max(1, min(5, valor))
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO checkins (user_id, data, alimentacao)
               VALUES (1, (NOW() AT TIME ZONE 'America/Sao_Paulo')::date, $1)
               ON CONFLICT (user_id, data) DO UPDATE SET alimentacao=$1""",
            valor,
        )
    return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# GET/POST /dashboard/contextos-editor
# ---------------------------------------------------------------------------

@router.get("/dashboard/contextos-editor", response_class=HTMLResponse)
async def contextos_editor_get():
    return RedirectResponse("/dashboard/configuracoes?aba=contextos", status_code=302)

@router.get("/dashboard/contextos-editor-legacy", response_class=HTMLResponse)
async def contextos_editor_get_legacy():
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, label, ativo, ordem FROM contextos_config WHERE user_id=1 ORDER BY ordem, id"
        )

    items_html = ""
    for r in rows:
        cor = "var(--text)" if r["ativo"] else "var(--text3)"
        btn_lbl = "desativar" if r["ativo"] else "reativar"
        btn_cls = "editor-btn desat" if r["ativo"] else "editor-btn"
        items_html += (
            f'<div class="editor-item">'
            f'<span class="editor-label" style="color:{cor}">{_html_mod.escape(r["label"])}</span>'
            f'<form method="post" action="/dashboard/contextos-editor/toggle" style="display:inline">'
            f'<input type="hidden" name="id" value="{r["id"]}">'
            f'<button type="submit" class="{btn_cls}">{btn_lbl}</button>'
            f'</form>'
            f'</div>'
        )

    page = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gerenciar contextos</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0F0F14;--surface:#18181F;--surface2:#22222C;--border:#2A2A38;--primary:#A78BFA;--text:#F1F0F5;--text2:#94A3B8;--text3:#4A4A5A;--low:#FCA5A5;}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;padding:0 0 60px}}
a{{color:var(--primary);text-decoration:none}}
</style>
</head>
<body>
<div class="editor-wrap" style="max-width:480px;margin:0 auto;padding:24px">
  <div style="display:flex;align-items:center;gap:16px;margin-bottom:24px">
    <a href="/dashboard" style="font-size:13px;color:var(--text2)">\u2190 voltar</a>
    <h1 style="font-size:18px;font-weight:700">Contextos do dia</h1>
  </div>
  {items_html}
  <form method="post" action="/dashboard/contextos-editor/add" style="margin-top:20px;display:flex;gap:10px">
    <input type="text" name="label" placeholder="Novo contexto..." required
      style="flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:10px 14px;color:var(--text);font-size:14px;outline:none;font-family:inherit">
    <button type="submit"
      style="background:var(--primary);color:#0F0F14;border:none;border-radius:10px;padding:10px 20px;font-size:13px;font-weight:700;cursor:pointer">
      + Adicionar
    </button>
  </form>
</div>
</body>
</html>"""
    return page


@router.post("/dashboard/contextos-editor/toggle", response_class=HTMLResponse)
async def contextos_editor_toggle(id: int = Form(...)):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE contextos_config SET ativo = NOT ativo WHERE id=$1 AND user_id=1", id
        )
    return RedirectResponse("/dashboard/contextos-editor", status_code=303)


@router.post("/dashboard/contextos-editor/add", response_class=HTMLResponse)
async def contextos_editor_add(label: str = Form(...)):
    label = label.strip()[:60]
    if not label:
        return RedirectResponse("/dashboard/contextos-editor", status_code=303)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO contextos_config (user_id, label, ordem) VALUES (1, $1, 99) ON CONFLICT DO NOTHING",
            label,
        )
    return RedirectResponse("/dashboard/contextos-editor", status_code=303)


# ---------------------------------------------------------------------------
# POST /dashboard/remover
# ---------------------------------------------------------------------------

@router.post("/dashboard/remover")
async def dashboard_remover(data: str = Form(...)):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM checkins WHERE user_id=1 AND data=$1", date.fromisoformat(data))
        await conn.execute("DELETE FROM checkin_sessions WHERE user_id=1 AND data_referencia=$1", date.fromisoformat(data))
    return RedirectResponse("/dashboard", status_code=303)


# ---------------------------------------------------------------------------
# GET /dashboard/configuracoes  (abas: campos + contextos)
# ---------------------------------------------------------------------------

_CFG_CSS = """
:root{--bg:#0F0F14;--surface:#18181F;--surface2:#22222C;--border:#2A2A38;
  --primary:#A78BFA;--primary-dim:#7C5CBF;--good:#86EFAC;--warn:#FCD34D;
  --low:#FCA5A5;--text:#F1F0F5;--text2:#94A3B8;--text3:#4A4A5A;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,sans-serif;padding:0 0 80px;max-width:600px;margin:0 auto}
a{color:var(--primary);text-decoration:none}
.cfg-header{padding:24px 24px 0;display:flex;align-items:center;gap:16px;margin-bottom:0}
.cfg-tabs{display:flex;gap:0;border-bottom:1px solid var(--border);margin:20px 24px 0;padding:0}
.cfg-tab{padding:10px 20px;font-size:13px;font-weight:600;color:var(--text3);cursor:pointer;
  border-bottom:2px solid transparent;background:none;border-top:none;border-left:none;border-right:none;
  font-family:inherit;transition:all .15s}
.cfg-tab.active{color:var(--primary);border-bottom-color:var(--primary)}
.cfg-tab:hover{color:var(--text2)}
.cfg-panel{display:none;padding:20px 24px}
.cfg-panel.active{display:block}
.cfg-item{display:flex;align-items:center;justify-content:space-between;
  background:var(--surface);border-radius:10px;padding:14px 16px;margin-bottom:8px;
  border:1px solid var(--border);gap:12px}
.cfg-item-left{display:flex;flex-direction:column;gap:3px;flex:1;min-width:0}
.cfg-item-name{font-size:14px;font-weight:600;color:var(--text)}
.cfg-item-meta{font-size:11px;color:var(--text3)}
.cfg-item-right{display:flex;gap:8px;align-items:center;flex-shrink:0}
.cfg-btn{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
  padding:6px 14px;font-size:12px;font-weight:600;color:var(--text2);cursor:pointer;font-family:inherit}
.cfg-btn:hover{border-color:var(--primary);color:var(--primary)}
.cfg-btn.danger{color:var(--low);border-color:#450a0a}
.cfg-btn.danger:hover{background:#450a0a}
.cfg-toggle{position:relative;width:40px;height:22px;flex-shrink:0}
.cfg-toggle input{opacity:0;width:0;height:0}
.cfg-slider{position:absolute;cursor:pointer;inset:0;background:var(--border);border-radius:11px;transition:.2s}
.cfg-slider:before{content:'';position:absolute;height:16px;width:16px;left:3px;bottom:3px;
  background:var(--text3);border-radius:50%;transition:.2s}
.cfg-toggle input:checked+.cfg-slider{background:var(--primary-dim)}
.cfg-toggle input:checked+.cfg-slider:before{background:var(--primary);transform:translateX(18px)}
.cfg-add-form{display:flex;flex-direction:column;gap:12px;background:var(--surface);
  border-radius:12px;padding:18px;border:1px solid var(--border);margin-top:16px}
.cfg-add-title{font-size:12px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.5px}
.cfg-row{display:flex;gap:10px;flex-wrap:wrap}
.cfg-field{display:flex;flex-direction:column;gap:5px;flex:1;min-width:140px}
.cfg-label{font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.5px}
.cfg-input,.cfg-select{background:var(--surface2);border:1px solid var(--border);border-radius:8px;
  padding:9px 12px;color:var(--text);font-size:13px;outline:none;font-family:inherit;width:100%}
.cfg-input:focus,.cfg-select:focus{border-color:var(--primary)}
.cfg-submit{background:var(--primary);color:#0F0F14;border:none;border-radius:10px;
  padding:10px 20px;font-size:13px;font-weight:700;cursor:pointer;align-self:flex-start}
.cfg-type-badge{font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;text-transform:uppercase;letter-spacing:.5px}
.type-escala{background:rgba(167,139,250,.15);color:var(--primary)}
.type-numerico{background:rgba(103,232,249,.15);color:#67E8F9}
.type-opcoes{background:rgba(134,239,172,.15);color:var(--good)}
.type-custom{background:rgba(249,168,212,.15);color:#F9A8D4}
.cfg-modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:200;padding:20px;overflow-y:auto}
.cfg-modal.open{display:block}
.cfg-modal-box{background:var(--surface);border-radius:16px;padding:24px;max-width:440px;margin:40px auto;border:1px solid var(--border)}
.cfg-modal-title{font-size:15px;font-weight:700;margin-bottom:18px}
.cfg-modal-footer{display:flex;gap:10px;margin-top:20px}
.cfg-modal-save{flex:1;background:var(--primary);color:#0F0F14;border:none;border-radius:10px;padding:11px;font-size:13px;font-weight:700;cursor:pointer}
.cfg-modal-cancel{flex:1;background:var(--surface2);color:var(--text2);border:none;border-radius:10px;padding:11px;font-size:13px;cursor:pointer}
"""

def _cfg_type_badge(tipo):
    cls_map = {"escala_1_5": "type-escala", "numerico": "type-numerico", "opcoes": "type-opcoes", "custom": "type-custom"}
    label_map = {"escala_1_5": "Escala 1-5", "numerico": "Numérico", "opcoes": "Opções", "custom": "Personalizado"}
    cls = cls_map.get(tipo, "type-custom")
    lbl = label_map.get(tipo, tipo)
    return f'<span class="cfg-type-badge {cls}">{lbl}</span>'

# Mapeamento dos campos fixos com seus tipos
_CAMPOS_FIXOS_META = {
    "dor_fisica":             {"label": "Dor física", "tipo": "escala_1_5", "emoji": "❤"},
    "energia":                {"label": "Energia", "tipo": "escala_1_5", "emoji": "⚡"},
    "sono_horas":             {"label": "Sono (horas)", "tipo": "numerico", "emoji": "★"},
    "sono_qualidade":         {"label": "Qualidade do sono", "tipo": "escala_1_5", "emoji": "☽"},
    "exercicio":              {"label": "Exercício", "tipo": "opcoes", "emoji": "▶", "opcoes": "Nenhum, Leve, Moderado, Intenso"},
    "saude_mental":           {"label": "Saúde mental", "tipo": "escala_1_5", "emoji": "✨"},
    "stress_trabalho":        {"label": "Stress no trabalho", "tipo": "escala_1_5", "emoji": "⏰"},
    "stress_relacionamento":  {"label": "Stress nos relacionamentos", "tipo": "escala_1_5", "emoji": "♥"},
    "alcool":                 {"label": "Álcool", "tipo": "opcoes", "emoji": "☕", "opcoes": "Nenhum, Pouco, Moderado, Muito"},
    "cigarros":               {"label": "Cigarros", "tipo": "numerico", "emoji": "✖"},
    "desempenho_social":      {"label": "Vida social", "tipo": "escala_1_5", "emoji": "☀"},
    "remedios":               {"label": "Remédios", "tipo": "opcoes", "emoji": "♥"},
    "nota":                   {"label": "Nota do dia", "tipo": "opcoes", "emoji": "✏"},
}


@router.get("/dashboard/configuracoes", response_class=HTMLResponse)
async def configuracoes_get(aba: str = "campos"):
    pool = get_pool()
    async with pool.acquire() as conn:
        campos_db = await conn.fetch(
            "SELECT campo, ativo, ordem FROM campos_config WHERE user_id=1 ORDER BY ordem, id"
        )
        contextos_db = await conn.fetch(
            "SELECT id, label, ativo, ordem FROM contextos_config WHERE user_id=1 ORDER BY ordem, id"
        )
        # Campos custom (se tabela existir)
        try:
            campos_custom = await conn.fetch(
                "SELECT id, nome, tipo_input, opcoes_texto, ativo FROM campos_custom WHERE user_id=1 ORDER BY id"
            )
        except Exception:
            campos_custom = []

    campos_map = {r["campo"]: dict(r) for r in campos_db}

    # --- Aba Campos ---
    campos_html = ""
    for campo, meta in _CAMPOS_FIXOS_META.items():
        db = campos_map.get(campo, {})
        ativo = db.get("ativo", True)
        checked = "checked" if ativo else ""
        tipo_badge = _cfg_type_badge(meta["tipo"])
        opcoes_info = f' &bull; {_html_mod.escape(meta["opcoes"])}' if meta.get("opcoes") else ""
        campos_html += f"""
<div class="cfg-item">
  <div class="cfg-item-left">
    <div class="cfg-item-name">{meta["emoji"]} {_html_mod.escape(meta["label"])}</div>
    <div class="cfg-item-meta">{tipo_badge}{opcoes_info}</div>
  </div>
  <div class="cfg-item-right">
    <form method="post" action="/dashboard/configuracoes/campo-toggle">
      <input type="hidden" name="campo" value="{campo}">
      <label class="cfg-toggle" title="{'Ativo' if ativo else 'Inativo'}">
        <input type="checkbox" {checked} onchange="this.form.submit()">
        <span class="cfg-slider"></span>
      </label>
    </form>
  </div>
</div>"""

    # Campos custom
    for cc in campos_custom:
        ativo_cc = cc["ativo"]
        checked_cc = "checked" if ativo_cc else ""
        tipo_cc = cc["tipo_input"] or "custom"
        tipo_badge_cc = _cfg_type_badge(tipo_cc)
        opcoes_cc = f' &bull; {_html_mod.escape(cc["opcoes_texto"] or "")}' if cc.get("opcoes_texto") else ""
        campos_html += f"""
<div class="cfg-item">
  <div class="cfg-item-left">
    <div class="cfg-item-name">&#10022; {_html_mod.escape(cc["nome"])}</div>
    <div class="cfg-item-meta">{tipo_badge_cc}{opcoes_cc} <span style="color:#F9A8D4;font-size:10px">personalizado</span></div>
  </div>
  <div class="cfg-item-right">
    <button class="cfg-btn" onclick="openEditCampo({cc['id']}, '{_html_mod.escape(cc['nome'])}', '{tipo_cc}', '{_html_mod.escape(cc['opcoes_texto'] or '')}')">editar</button>
    <form method="post" action="/dashboard/configuracoes/campo-custom-toggle" style="display:inline">
      <input type="hidden" name="id" value="{cc['id']}">
      <label class="cfg-toggle">
        <input type="checkbox" {checked_cc} onchange="this.form.submit()">
        <span class="cfg-slider"></span>
      </label>
    </form>
  </div>
</div>"""

    # Form adicionar campo custom
    campos_html += """
<div class="cfg-add-form">
  <div class="cfg-add-title">&#43; Novo campo personalizado</div>
  <form method="post" action="/dashboard/configuracoes/campo-custom-add">
    <div class="cfg-row">
      <div class="cfg-field">
        <label class="cfg-label">Nome do campo</label>
        <input class="cfg-input" type="text" name="nome" placeholder="Ex: Ansiedade, Foco..." required maxlength="50">
      </div>
      <div class="cfg-field">
        <label class="cfg-label">Tipo</label>
        <select class="cfg-select" name="tipo_input" id="tipo-select" onchange="tipoChange(this.value)">
          <option value="escala_1_5">Escala 1-5</option>
          <option value="numerico">Numérico (texto livre)</option>
          <option value="opcoes">Opções (múltipla escolha)</option>
        </select>
      </div>
    </div>
    <div class="cfg-field" id="opcoes-field" style="display:none;margin-top:10px">
      <label class="cfg-label">Opções (separadas por vírgula)</label>
      <input class="cfg-input" type="text" name="opcoes_texto" id="opcoes-input" placeholder="Ex: Sim, Não, Às vezes">
    </div>
    <button type="submit" class="cfg-submit" style="margin-top:14px">Adicionar campo</button>
  </form>
</div>"""

    # --- Aba Contextos ---
    ctx_html = ""
    for r in contextos_db:
        cor = "var(--text)" if r["ativo"] else "var(--text3)"
        btn_lbl = "desativar" if r["ativo"] else "reativar"
        btn_cls = "cfg-btn danger" if r["ativo"] else "cfg-btn"
        ctx_html += f"""
<div class="cfg-item">
  <div class="cfg-item-left">
    <div class="cfg-item-name" style="color:{cor}">{_html_mod.escape(r["label"])}</div>
  </div>
  <div class="cfg-item-right">
    <form method="post" action="/dashboard/configuracoes/contexto-toggle" style="display:inline">
      <input type="hidden" name="id" value="{r['id']}">
      <button type="submit" class="{btn_cls}">{btn_lbl}</button>
    </form>
    <form method="post" action="/dashboard/configuracoes/contexto-remover" style="display:inline"
      onsubmit="return confirm('Remover contexto \\\"{_html_mod.escape(r["label"])}\\\"?')">
      <input type="hidden" name="id" value="{r['id']}">
      <button type="submit" class="cfg-btn danger">remover</button>
    </form>
  </div>
</div>"""

    ctx_html += """
<div class="cfg-add-form">
  <div class="cfg-add-title">&#43; Novo contexto</div>
  <form method="post" action="/dashboard/configuracoes/contexto-add" style="display:flex;gap:10px;flex-wrap:wrap">
    <input class="cfg-input" type="text" name="label" placeholder="Ex: reunião, viagem, dor de cabeça..." required maxlength="60" style="flex:1;min-width:180px">
    <button type="submit" class="cfg-submit">Adicionar</button>
  </form>
</div>"""

    aba_campos_active = "active" if aba != "contextos" else ""
    aba_ctx_active = "active" if aba == "contextos" else ""

    page = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Configurações</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>{_CFG_CSS}</style>
</head>
<body>
<div class="cfg-header">
  <a href="/dashboard" style="font-size:13px;color:var(--text2)">&#8592; voltar</a>
  <h1 style="font-size:20px;font-weight:700">Configurações</h1>
</div>
<div class="cfg-tabs">
  <button class="cfg-tab {aba_campos_active}" onclick="showAba('campos')">&#10064; Campos</button>
  <button class="cfg-tab {aba_ctx_active}" onclick="showAba('contextos')">&#127381; Contextos</button>
</div>
<div class="cfg-panel {aba_campos_active}" id="panel-campos">
{campos_html}
</div>
<div class="cfg-panel {aba_ctx_active}" id="panel-contextos">
{ctx_html}
</div>

<!-- Modal editar campo custom -->
<div class="cfg-modal" id="modal-campo">
<div class="cfg-modal-box">
  <div class="cfg-modal-title">&#9998; Editar campo</div>
  <form method="post" action="/dashboard/configuracoes/campo-custom-editar">
    <input type="hidden" name="id" id="edit-campo-id">
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="cfg-field">
        <label class="cfg-label">Nome</label>
        <input class="cfg-input" type="text" name="nome" id="edit-campo-nome" required maxlength="50">
      </div>
      <div class="cfg-field">
        <label class="cfg-label">Tipo</label>
        <select class="cfg-select" name="tipo_input" id="edit-campo-tipo" onchange="editTipoChange(this.value)">
          <option value="escala_1_5">Escala 1-5</option>
          <option value="numerico">Numérico</option>
          <option value="opcoes">Opções</option>
        </select>
      </div>
      <div class="cfg-field" id="edit-opcoes-field">
        <label class="cfg-label">Opções (separadas por vírgula)</label>
        <input class="cfg-input" type="text" name="opcoes_texto" id="edit-campo-opcoes" placeholder="Ex: Sim, Não, Às vezes">
      </div>
    </div>
    <div class="cfg-modal-footer">
      <button type="button" class="cfg-modal-cancel" onclick="closeCampoModal()">Cancelar</button>
      <button type="submit" class="cfg-modal-save">Salvar</button>
    </div>
  </form>
</div>
</div>

<script>
function showAba(aba) {{
  document.querySelectorAll('.cfg-tab').forEach(function(t){{t.classList.remove('active');}});
  document.querySelectorAll('.cfg-panel').forEach(function(p){{p.classList.remove('active');}});
  document.querySelector('.cfg-tab[onclick="showAba(\\''+aba+'\\')"]').classList.add('active');
  document.getElementById('panel-'+aba).classList.add('active');
}}
function tipoChange(v) {{
  document.getElementById('opcoes-field').style.display = v === 'opcoes' ? 'block' : 'none';
  document.getElementById('opcoes-input').required = v === 'opcoes';
}}
function editTipoChange(v) {{
  document.getElementById('edit-opcoes-field').style.display = v === 'opcoes' ? 'block' : 'none';
}}
function openEditCampo(id, nome, tipo, opcoes) {{
  document.getElementById('edit-campo-id').value = id;
  document.getElementById('edit-campo-nome').value = nome;
  document.getElementById('edit-campo-tipo').value = tipo;
  document.getElementById('edit-campo-opcoes').value = opcoes;
  editTipoChange(tipo);
  document.getElementById('modal-campo').classList.add('open');
}}
function closeCampoModal() {{
  document.getElementById('modal-campo').classList.remove('open');
}}
</script>
</body>
</html>"""
    return page


@router.post("/dashboard/configuracoes/campo-toggle")
async def cfg_campo_toggle(campo: str = Form(...)):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE campos_config SET ativo = NOT ativo WHERE campo=$1 AND user_id=1", campo
        )
    return RedirectResponse("/dashboard/configuracoes?aba=campos", status_code=303)


@router.post("/dashboard/configuracoes/contexto-toggle")
async def cfg_ctx_toggle(id: int = Form(...)):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE contextos_config SET ativo = NOT ativo WHERE id=$1 AND user_id=1", id
        )
    return RedirectResponse("/dashboard/configuracoes?aba=contextos", status_code=303)


@router.post("/dashboard/configuracoes/contexto-add")
async def cfg_ctx_add(label: str = Form(...)):
    label = label.strip()[:60]
    if not label:
        return RedirectResponse("/dashboard/configuracoes?aba=contextos", status_code=303)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO contextos_config (user_id, label, ordem) VALUES (1, $1, 99) ON CONFLICT DO NOTHING",
            label,
        )
    return RedirectResponse("/dashboard/configuracoes?aba=contextos", status_code=303)


@router.post("/dashboard/configuracoes/contexto-remover")
async def cfg_ctx_remover(id: int = Form(...)):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM contextos_config WHERE id=$1 AND user_id=1", id)
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
    async with pool.acquire() as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS campos_custom (
               id SERIAL PRIMARY KEY, user_id INT, nome TEXT NOT NULL,
               tipo_input TEXT DEFAULT 'escala_1_5', opcoes_texto TEXT,
               ativo BOOLEAN DEFAULT TRUE, criado_em TIMESTAMP DEFAULT NOW())"""
        )
        await conn.execute(
            "INSERT INTO campos_custom (user_id, nome, tipo_input, opcoes_texto) VALUES (1, $1, $2, $3)",
            nome, tipo_input, opcoes_texto or None,
        )
    return RedirectResponse("/dashboard/configuracoes?aba=campos", status_code=303)


@router.post("/dashboard/configuracoes/campo-custom-toggle")
async def cfg_campo_custom_toggle(id: int = Form(...)):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE campos_custom SET ativo = NOT ativo WHERE id=$1 AND user_id=1", id)
    return RedirectResponse("/dashboard/configuracoes?aba=campos", status_code=303)


@router.post("/dashboard/configuracoes/campo-custom-editar")
async def cfg_campo_custom_editar(
    id: int = Form(...),
    nome: str = Form(...),
    tipo_input: str = Form(...),
    opcoes_texto: str = Form(default=""),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE campos_custom SET nome=$1, tipo_input=$2, opcoes_texto=$3 WHERE id=$4 AND user_id=1",
            nome.strip()[:50], tipo_input.strip(), opcoes_texto.strip()[:200] or None, id,
        )
    return RedirectResponse("/dashboard/configuracoes?aba=campos", status_code=303)
