import json as _json
from datetime import date
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
    """Retorna cor de estado baseada no valor 0-10."""
    if v is None:
        return "#4A4A5A"
    pct = float(v) / 10
    if invert:
        if pct <= 0.3: return "#86EFAC"
        if pct <= 0.6: return "#FCD34D"
        return "#FCA5A5"
    else:
        if pct >= 0.7: return "#86EFAC"
        if pct >= 0.4: return "#FCD34D"
        return "#FCA5A5"

def _trend(rows, field):
    """Seta de tendência comparando metade mais recente vs mais antiga."""
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
    """Frase humana baseada nos indicadores do dia mais recente."""
    if mental is None:
        return "Seus dados v\xe3o aparecer aqui depois do pr\xf3ximo check-in."
    m, e = float(mental), float(energia) if energia is not None else 5
    d = float(dor) if dor is not None else 0
    if m >= 8 and e >= 7:
        return "Voc\xea esteve bem hoje. Isso importa."
    if m >= 6 and d <= 3:
        return "Um dia razo\xe1vel. Voc\xea est\xe1 acompanhando."
    if m <= 4 and d >= 6:
        return "Foi um dia mais pesado. Tudo registrado, tudo bem."
    if m <= 4:
        return "Nem todo dia \xe9 f\xe1cil. Voc\xea est\xe1 aqui, isso j\xe1 \xe9 algo."
    if d >= 7:
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
        "positivo": ('<span style="background:#14532d;color:#86EFAC;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600">\u2022 positivo</span>'),
        "neutro":   ('<span style="background:#1e293b;color:#94A3B8;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600">\u2022 neutro</span>'),
        "negativo": ('<span style="background:#450a0a;color:#FCA5A5;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600">\u2022 pesado</span>'),
    }
    return m.get(s.lower(), "")

async def _process_nota(nota_raw: str) -> dict:
    if not OPENAI_API_KEY or not nota_raw or nota_raw.strip() in ("Pular", "Texto", ""):
        return {}
    try:
        from openai import AsyncOpenAI
        ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Analise o texto de di\xe1rio de sa\xfade mental e retorne JSON com: "
                    "resumo (frase curta e acolhedora, m\xe1x 90 chars, primeira pessoa), "
                    "sentimento (positivo/neutro/negativo), "
                    "categorias (lista de at\xe9 4 temas curtos em portugu\xeas). "
                    "Responda APENAS com JSON v\xe1lido."
                )},
                {"role": "user", "content": nota_raw},
            ],
            response_format={"type": "json_object"},
        )
        return _json.loads(resp.choices[0].message.content)
    except Exception:
        return {}

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
    if v >= 7: return "#86EFAC"
    if v >= 5: return "#A78BFA"
    if v >= 3: return "#FCD34D"
    return "#FCA5A5"

# ---------------------------------------------------------------------------
# Template HTML
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
  padding:0 0 60px;max-width:860px;margin:0 auto}
a{color:var(--primary);text-decoration:none}

/* Header */
.header{padding:28px 24px 0;display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px}
.header-left h1{font-size:14px;font-weight:600;color:var(--text2);letter-spacing:.5px;text-transform:uppercase}
.header-left .greeting{font-size:26px;font-weight:700;color:var(--text);margin-top:4px;line-height:1.2}
.header-right{text-align:right}
.checkin-btn{background:var(--primary);color:#0F0F14;border:none;border-radius:12px;
  padding:10px 20px;font-size:13px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block}

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

/* Section label */
.sec-label{font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;
  letter-spacing:.8px;padding:28px 24px 12px}

/* Streak + heatmap */
.streak-card{margin:0 24px;background:var(--surface);border-radius:16px;
  padding:20px;border:1px solid var(--border)}
.streak-row{display:flex;align-items:center;gap:20px;margin-bottom:20px;flex-wrap:wrap}
.streak-num{font-size:44px;font-weight:800;color:var(--warm);line-height:1}
.streak-info .streak-frase{font-size:14px;color:var(--text);font-weight:500}
.streak-info .streak-max{font-size:12px;color:var(--text2);margin-top:4px}
.heatmap{display:flex;flex-wrap:wrap;gap:4px}
.dot{width:12px;height:12px;border-radius:3px;flex-shrink:0}

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

/* Histórico — desktop table / mobile cards */
.hist-wrap{margin:0 24px}
.hist-table{width:100%;border-collapse:collapse;font-size:13px}
.hist-table th{text-align:left;color:var(--text3);font-weight:600;font-size:11px;
  text-transform:uppercase;letter-spacing:.6px;padding:0 8px 10px 0;border-bottom:1px solid var(--border)}
.hist-table td{padding:12px 8px 12px 0;border-bottom:1px solid var(--surface2);vertical-align:middle}
.hist-table tr:last-child td{border-bottom:none}
.hist-table tr:hover td{background:rgba(255,255,255,.02)}
.badge{display:inline-block;border-radius:8px;padding:3px 8px;font-size:12px;font-weight:700;min-width:28px;text-align:center}
.act-btn{background:var(--surface2);border:none;border-radius:8px;padding:6px 10px;
  cursor:pointer;color:var(--text2);font-size:13px;transition:background .15s}
.act-btn:hover{background:var(--border)}
.act-btn.del{color:var(--low)}

/* Day cards (mobile) */
.day-cards{display:none;flex-direction:column;gap:10px}
.day-card{background:var(--surface);border-radius:14px;padding:16px;border:1px solid var(--border)}
.day-card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.day-card-date{font-size:14px;font-weight:700}
.day-card-actions{display:flex;gap:8px}
.day-card-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.day-metric{background:var(--surface2);border-radius:10px;padding:8px 10px}
.day-metric .dm-val{font-size:18px;font-weight:700}
.day-metric .dm-lbl{font-size:10px;color:var(--text2);margin-top:2px}

/* Remédios */
.remed-card{margin:0 24px;background:var(--surface);border-radius:16px;
  padding:0;border:1px solid var(--border);overflow:hidden}
.remed-day{border-bottom:1px solid var(--border);padding:14px 18px}
.remed-day:last-child{border-bottom:none}
.remed-day-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.remed-day-date{font-size:12px;color:var(--text2);font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.remed-tag{font-size:10px;color:var(--text3);font-weight:500}
.remed-list{display:flex;flex-direction:column;gap:6px}
.remed-item{display:flex;align-items:center;justify-content:space-between;
  background:var(--surface2);border-radius:10px;padding:8px 12px}
.remed-nome{font-size:13px;font-weight:600;color:var(--text)}
.remed-qtd{font-size:13px;font-weight:700;color:var(--primary);background:rgba(167,139,250,.12);
  border-radius:8px;padding:2px 8px;min-width:28px;text-align:center}

/* Notas */
.notes-wrap{margin:0 24px;display:flex;flex-direction:column;gap:12px}
.note-card{background:var(--surface);border-radius:16px;padding:20px;border:1px solid var(--border)}
.note-header{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.note-date-lbl{font-size:12px;color:var(--text2);font-weight:600}
.note-resumo{font-size:15px;color:var(--text);line-height:1.6;font-weight:500}
.note-cats{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px}
.note-tag{background:rgba(167,139,250,.12);color:var(--primary);border-radius:20px;
  padding:3px 10px;font-size:11px;font-weight:600}
.note-expand{margin-top:12px;padding-top:12px;border-top:1px solid var(--border)}
.note-expand summary{font-size:12px;color:var(--text2);cursor:pointer;user-select:none}
.note-raw-text{font-size:13px;color:var(--text2);line-height:1.6;margin-top:8px}

/* Empty state */
.empty-state{text-align:center;padding:48px 24px}
.empty-state .es-icon{font-size:36px;margin-bottom:12px}
.empty-state .es-title{font-size:16px;font-weight:600;color:var(--text);margin-bottom:6px}
.empty-state .es-sub{font-size:13px;color:var(--text2);line-height:1.6}

/* Modal */
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:200;
  overflow-y:auto;padding:20px}
.modal.open{display:block}
.modal-box{background:var(--surface);border-radius:20px;padding:24px;
  max-width:460px;margin:40px auto;border:1px solid var(--border)}
.modal-title{font-size:16px;font-weight:700;margin-bottom:20px;color:var(--text)}
.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.field label{font-size:11px;color:var(--text2);font-weight:600;display:block;
  text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
.field input{width:100%;background:var(--surface2);border:1px solid var(--border);
  border-radius:10px;padding:10px 12px;color:var(--text);font-size:14px;outline:none}
.field input:focus{border-color:var(--primary)}
.modal-footer{display:flex;gap:10px;margin-top:20px}
.btn-save{flex:1;background:var(--primary);color:#0F0F14;border:none;border-radius:12px;
  padding:12px;font-size:14px;font-weight:700;cursor:pointer}
.btn-cancel{flex:1;background:var(--surface2);color:var(--text2);border:none;
  border-radius:12px;padding:12px;font-size:14px;cursor:pointer}

/* Relato */
.relato-wrap{margin:0 24px}
.relato-card{background:var(--surface);border-radius:16px;padding:20px;border:1px solid var(--border)}
.relato-prompt{font-size:15px;font-weight:600;color:var(--text);margin-bottom:14px}
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
.relato-audio-status{font-size:13px;color:var(--text2);margin:10px 0;padding:8px 12px;
  background:var(--surface2);border-radius:8px}

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
/* Remédios secundários compactos */
.remed-sec{margin:0 24px;background:var(--surface);border-radius:12px;
  padding:12px 16px;border:1px solid var(--border);display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.remed-sec-label{font-size:11px;color:var(--text3);font-weight:600;margin-right:4px}
.remed-sec-item{font-size:12px;color:var(--text2);background:var(--surface2);
  border-radius:8px;padding:4px 10px}

/* Exercício */
.ex-card{margin:0 24px;background:var(--surface);border-radius:16px;padding:18px;border:1px solid var(--border)}
.ex-title{font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:.8px;margin-bottom:14px}
.ex-week{display:flex;gap:6px;align-items:flex-end}
.ex-day{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px}
.ex-bar{width:100%;border-radius:4px 4px 0 0;min-height:4px}
.ex-day-lbl{font-size:9px;color:var(--text3)}
.ex-intensidade{font-size:10px;color:var(--text2);margin-top:2px;font-weight:600}

/* Check-in desabilitado */
.checkin-btn-disabled{background:var(--surface2);color:var(--text3);border:1px solid var(--border);
  border-radius:12px;padding:10px 20px;font-size:13px;font-weight:700;display:inline-block;cursor:not-allowed}

/* Histórico compacto */
.hist-compact{margin:0 24px;display:flex;flex-direction:column;gap:1px}
.hist-row{display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--surface);border-radius:0;font-size:12px}
.hist-row:first-child{border-radius:12px 12px 0 0}
.hist-row:last-child{border-radius:0 0 12px 12px}
.hist-row:only-child{border-radius:12px}
.hist-date{font-weight:700;color:var(--text);min-width:32px}
.hist-vals{display:flex;gap:8px;flex:1;flex-wrap:wrap}
.hist-chip{font-size:11px;color:var(--text2);background:var(--surface2);border-radius:6px;padding:2px 6px}
.hist-acts{display:flex;gap:4px}

@media(max-width:600px){
  .header{padding:20px 16px 0}
  .hero{margin:16px 16px 0;padding:18px}
  .hero-score{font-size:44px}
  .sec-label{padding:22px 16px 10px}
  .streak-card,.remed-card{margin:0 16px}
  .dim-grid{margin:0 16px;grid-template-columns:1fr 1fr;gap:10px}
  .hist-wrap{margin:0 16px}
  .notes-wrap{margin:0 16px}
  .hist-table{display:none}
  .day-cards{display:flex}
  .dim-card{padding:14px}
  .remed-priority-grid{margin:0 16px}
  .remed-sec,.ex-card,.relato-wrap,.hist-compact{margin:0 16px}
}
"""

_HTML_SHELL = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitoramento Mental</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>CSS_PLACEHOLDER</style>
</head>
<body>
BODY_PLACEHOLDER
<script>
function openEdit(d,dor,en,sh,sq,me,st,sr,al,ci,so,rj){
  document.getElementById('ed-data').value=d;
  document.getElementById('ed-dor').value=dor;
  document.getElementById('ed-en').value=en;
  document.getElementById('ed-sh').value=sh;
  document.getElementById('ed-sq').value=sq;
  document.getElementById('ed-me').value=me;
  document.getElementById('ed-st').value=st;
  document.getElementById('ed-sr').value=sr;
  document.getElementById('ed-al').value=al;
  document.getElementById('ed-ci').value=ci;
  document.getElementById('ed-so').value=so;
  // preencher quantidades dos remédios
  var remedios=document.querySelectorAll('.ed-rem-qtd');
  remedios.forEach(function(inp){
    var nome=inp.dataset.nome;
    var qtd=1;
    if(rj){try{var arr=JSON.parse(rj);arr.forEach(function(r){if(r.nome===nome)qtd=r.qtd||1;});}catch(e){}}
    inp.value=qtd;
  });
  document.getElementById('modal').classList.add('open');
}
function closeModal(){document.getElementById('modal').classList.remove('open');}
function buildRemedJson(){
  var arr=[];
  document.querySelectorAll('.ed-rem-qtd').forEach(function(inp){
    var qtd=parseFloat(inp.value)||0;
    arr.push({nome:inp.dataset.nome,qtd:qtd,tomado:qtd>0});
  });
  document.getElementById('ed-remed-json').value=JSON.stringify(arr);
}
function delDay(d){
  if(confirm('Remover o registro de '+d+'? Esta a\xe7\xe3o n\xe3o pode ser desfeita.')){
    document.getElementById('del-data').value=d;
    document.getElementById('form-del').submit();
  }
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
      btn.textContent='\u23f9 Parar grava\xe7\xe3o';
      btn.classList.add('recording');
      document.getElementById('audio-status').textContent='Gravando...';
    });
  } else {
    _rec.stop();_rec.stream.getTracks().forEach(function(t){t.stop();});
    btn.textContent='\u23fa Iniciar grava\xe7\xe3o';
    btn.classList.remove('recording');
    document.getElementById('audio-status').textContent='Grava\xe7\xe3o conclu\xedda. Clique em Enviar.';
  }
}
function enviarRelato(){
  var texto=document.getElementById('relato-input').value.trim();
  if(!texto)return;
  var btn=document.querySelector('.relato-submit');
  btn.textContent='Salvando...';btn.disabled=true;
  var fd=new FormData();
  fd.append('texto',texto);
  fetch('/dashboard/relato',{method:'POST',body:fd})
    .then(function(r){
      if(r.ok||r.redirected){location.reload();}
      else{btn.textContent='Erro — tente novamente';btn.disabled=false;}
    })
    .catch(function(){btn.textContent='Erro de conex\xe3o';btn.disabled=false;});
}
function enviarAudio(){
  var blob=new Blob(_chunks,{type:'audio/webm'});
  var fd=new FormData();
  fd.append('audio',blob,'relato.webm');
  document.getElementById('audio-status').textContent='Enviando e transcrevendo...';
  document.getElementById('btn-send-audio').disabled=true;
  fetch('/dashboard/relato-audio',{method:'POST',body:fd})
    .then(function(r){
      if(r.ok||r.redirected){location.reload();}
      else{document.getElementById('audio-status').textContent='Erro ao transcrever. Tente novamente.';document.getElementById('btn-send-audio').disabled=false;}
    })
    .catch(function(){document.getElementById('audio-status').textContent='Erro de conex\xe3o.';document.getElementById('btn-send-audio').disabled=false;});
}
</script>
<!-- Modal editar -->
<div class="modal" id="modal">
<div class="modal-box">
  <div class="modal-title">\u270f Editar registro</div>
  <form method="post" action="/dashboard/editar">
  <input type="hidden" name="data" id="ed-data">
  <div class="field-grid">
    <div class="field"><label>\u2728 Sa\xfade mental</label><input name="saude_mental" id="ed-me" type="number" min="0" max="10"></div>
    <div class="field"><label>\u26a1 Energia</label><input name="energia" id="ed-en" type="number" min="0" max="10"></div>
    <div class="field"><label>\u2764 Dor f\xedsica</label><input name="dor_fisica" id="ed-dor" type="number" min="0" max="10"></div>
    <div class="field"><label>\u2605 Sono (horas)</label><input name="sono_horas" id="ed-sh" type="number" min="0" max="16" step="0.5"></div>
    <div class="field"><label>\u263d Sono qualidade</label><input name="sono_qualidade" id="ed-sq" type="number" min="0" max="10"></div>
    <div class="field"><label>\u23f0 Stress trabalho</label><input name="stress_trabalho" id="ed-st" type="number" min="0" max="10"></div>
    <div class="field"><label>\u2665 Stress rel.</label><input name="stress_relacionamento" id="ed-sr" type="number" min="0" max="10"></div>
    <div class="field"><label>\u2615 \xc1lcool</label><input name="alcool" id="ed-al" type="text" placeholder="Nenhum / Pouco / Moderado / Muito"></div>
    <div class="field"><label>\u2716 Cigarros</label><input name="cigarros" id="ed-ci" type="number" min="0"></div>
    <div class="field"><label>\u2600 Social</label><input name="desempenho_social" id="ed-so" type="number" min="0" max="10"></div>
  </div>
  <div style="margin-top:14px;border-top:1px solid var(--border);padding-top:14px">
    <div style="font-size:11px;color:var(--text2);font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px">\U0001f48a Rem\xe9dios</div>
    <div style="display:flex;flex-direction:column;gap:8px" id="ed-remed-list">REMED_MODAL_PLACEHOLDER</div>
    <input type="hidden" name="remedios_tomados" id="ed-remed-json">
  </div>
  <div class="modal-footer">
    <button type="button" class="btn-cancel" onclick="closeModal()">Cancelar</button>
    <button type="submit" class="btn-save" onclick="buildRemedJson()">Salvar altera\xe7\xf5es</button>
  </div>
  </form>
</div>
</div>
<form id="form-del" method="post" action="/dashboard/remover" style="display:none">
  <input type="hidden" name="data" id="del-data">
</form>
</body>
</html>"""


def _render(body: str, remed_modal_html: str = "") -> str:
    return (
        _HTML_SHELL
        .replace("CSS_PLACEHOLDER", _CSS)
        .replace("BODY_PLACEHOLDER", body)
        .replace("REMED_MODAL_PLACEHOLDER", remed_modal_html)
    )


def _dim_row(label, val, max_val=10, invert=False):
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


def _badge(val, invert=False):
    if val is None or val == "":
        return '<span style="color:#4A4A5A">\u2014</span>'
    color = _score_color(float(val), invert=invert)
    bg = color + "22"
    return f'<span class="badge" style="background:{bg};color:{color}">{val}</span>'


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
                       nota_raw, nota_sentimento, nota_categorias, remedios_tomados
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
                FROM checkins WHERE user_id = 1 AND data >= CURRENT_DATE - 6
                """,
            )
            heat_rows = await conn.fetch(
                """
                SELECT data, saude_mental FROM checkins
                WHERE user_id = 1 AND data >= CURRENT_DATE - 29
                ORDER BY data ASC
                """,
            )
            remedios_padrao = await conn.fetch(
                "SELECT DISTINCT ON (nome) id, nome, dose_padrao, tipo FROM remedios WHERE user_id = 1 AND ativo = TRUE ORDER BY nome, id"
            )
    except Exception as e:
        return _render(f'<div class="empty-state"><div class="es-icon">\u26a0</div><div class="es-title">Erro ao carregar</div><div class="es-sub">{e}</div></div>')

    body = ""

    # ---- Header ----
    from datetime import datetime
    _sp_tz = zoneinfo.ZoneInfo("America/Sao_Paulo")
    _agora_sp = datetime.now(_sp_tz)
    hora_sp = _agora_sp.hour
    hoje = _agora_sp.date()
    saudacao = "Bom dia" if hora_sp < 12 else ("Boa tarde" if hora_sp < 18 else "Boa noite")
    if hora_sp >= 20:
        checkin_btn = '<a class="checkin-btn" href="/checkin-web">+ Check-in</a>'
    else:
        checkin_btn = '<span class="checkin-btn-disabled">Check-in dispon\xedvel ap\xf3s 20h</span>'
    body += f"""
<div class="header">
  <div class="header-left">
    <div class="header-left h1">{saudacao}</div>
    <div class="greeting">Monitoramento Mental</div>
  </div>
  {checkin_btn}
</div>"""

    # ---- Hero card ----
    checkin_hoje = rows[0] if rows and rows[0]["data"] == hoje else None
    ultimo = rows[0] if rows else None
    mental_hoje = checkin_hoje["saude_mental"] if checkin_hoje else None
    energia_hoje = checkin_hoje["energia"] if checkin_hoje else None
    dor_hoje = checkin_hoje["dor_fisica"] if checkin_hoje else None
    sono_hoje = checkin_hoje["sono_horas"] if checkin_hoje else None
    ex_hoje = checkin_hoje["exercicio"] if checkin_hoje else None
    # Se não tem check-in hoje, usa o último disponível para contexto
    if mental_hoje is None and ultimo:
        mental_hoje = ultimo["saude_mental"]
        energia_hoje = ultimo["energia"]
        dor_hoje = ultimo["dor_fisica"]
        sono_hoje = ultimo["sono_horas"]
        ex_hoje = ultimo["exercicio"]
    frase = _hero_frase(mental_hoje, energia_hoje, dor_hoje)
    score_color = _score_color(mental_hoje) if mental_hoje is not None else "#4A4A5A"
    score_display = mental_hoje if mental_hoje is not None else "\u2014"
    try:
        data_display = ultimo["data"].strftime("%-d de %B") if ultimo else "sem dados"
    except ValueError:
        data_display = ultimo["data"].strftime("%d de %B") if ultimo else "sem dados"

    checkin_status = (
        '<span style="background:#14532d;color:#86EFAC;border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600">\u2713 check-in feito</span>'
        if checkin_hoje else
        '<span style="background:#1e293b;color:#94A3B8;border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600">check-in pendente</span>'
    )

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

    body += f"""
<div class="hero">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
    <div class="hero-label" style="padding:0;margin:0">Sa\xfade mental \u2014 {data_display}</div>
    {checkin_status}
  </div>
  <div class="hero-score" style="color:{score_color}">{score_display}<span> /10</span></div>
  <div class="hero-frase">{frase}</div>
  {f'<div class="hero-meta">{chips}</div>' if chips else ''}
</div>"""

    # ---- Relato do dia ----
    # Verificar se hoje já tem nota (só conta se o check-in mais recente for de hoje)
    nota_hoje_raw = checkin_hoje["nota_raw"] if checkin_hoje else None
    nota_hoje_tem = bool(nota_hoje_raw and nota_hoje_raw.strip() not in ("Pular", "Texto", ""))

    body += '<div class="sec-label">Relato</div><div class="relato-wrap">'

    if not nota_hoje_tem:
        # card de entrada
        body += """
<div class="relato-card" id="relato-card">
  <div class="relato-prompt">Como foi o seu dia?</div>
  <div class="relato-actions" id="relato-actions">
    <button class="relato-btn" onclick="relatoTexto()">&#9999; Escrever</button>
    <button class="relato-btn relato-btn-audio" onclick="relatoAudio()">&#127897; Gravar &aacute;udio</button>
  </div>
  <div id="relato-text-area" style="display:none">
    <textarea id="relato-input" placeholder="Descreva como foi seu dia, o que sentiu, o que aconteceu..."></textarea>
    <button class="relato-submit" onclick="enviarRelato()">Salvar relato</button>
  </div>
  <div id="relato-audio-area" style="display:none">
    <div class="relato-audio-status" id="audio-status">Pronto para gravar</div>
    <button class="relato-btn relato-btn-rec" id="btn-rec" onclick="toggleGravacao()">&#9210; Iniciar grava&ccedil;&atilde;o</button>
    <button class="relato-submit" id="btn-send-audio" style="display:none" onclick="enviarAudio()">Enviar &aacute;udio</button>
  </div>
</div>"""

    # Mostrar todos os relatos dos últimos 7 dias
    notas_exibir = [
        r for r in (rows if rows else [])
        if r["nota_raw"] and r["nota_raw"].strip() not in ("Pular", "Texto", "")
    ]
    for nr in notas_exibir:
        nr_raw = nr["nota_raw"]
        nr_sent = nr["nota_sentimento"]
        nr_cats = nr["nota_categorias"]
        nr_data = nr["data"].strftime("%d/%m")
        is_hoje = nr["data"] == hoje
        if nr_sent:
            nr_resumo = nr_raw[:120] + ("\u2026" if len(nr_raw) > 120 else "")
            sent_b = _sent_badge(nr_sent)
            nr_tags = "".join(f'<span class="note-tag">{c}</span>' for c in (nr_cats or []))
        else:
            an = await _process_nota_completa(nr_raw)
            nr_resumo = an.get("resumo") or nr_raw[:120]
            sent_b = _sent_badge(an.get("sentimento", ""))
            nr_tags = "".join(f'<span class="note-tag">{c}</span>' for c in (an.get("categorias") or []))
        lbl = "Hoje" if is_hoje else nr_data
        body += f"""
<div class="relato-card" style="margin-top:10px">
  <div class="note-header">
    <span class="note-date-lbl">{lbl}</span>
    {sent_b}
  </div>
  <div class="note-resumo">{nr_resumo}</div>
  {f'<div class="note-cats">{nr_tags}</div>' if nr_tags else ''}
  <details class="note-expand"><summary>Ver relato completo</summary><div class="note-raw-text">{nr_raw}</div></details>
</div>"""

    body += '</div>'  # relato-wrap

    # ---- Streak + heatmap ----
    s_atual = streak_row["streak_atual"] if streak_row else 0
    s_max = streak_row["streak_maximo"] if streak_row else 0
    streak_frase = _streak_frase(s_atual, s_max)

    heat_map = {r["data"]: r["saude_mental"] for r in heat_rows}
    dots = ""
    from datetime import timedelta
    for i in range(29, -1, -1):
        d = hoje - timedelta(days=i)
        mental_val = heat_map.get(d)
        color = _dot_color(mental_val)
        title = d.strftime("%d/%m") + (f" \u2014 {mental_val}" if mental_val is not None else " \u2014 sem dado")
        dots += f'<div class="dot" style="background:{color}" title="{title}"></div>'

    # ---- Dimension cards ----
    if not rows:
        body += f"""
<div class="sec-label">Consist\xeancia</div>
<div class="streak-card">
  <div class="streak-row">
    <div class="streak-num">\U0001f525 {s_atual}</div>
    <div class="streak-info">
      <div class="streak-frase">{streak_frase}</div>
      <div class="streak-max">M\xe1ximo: {s_max} dias</div>
    </div>
  </div>
  <div class="heatmap">{dots}</div>
</div>"""
        body += """
<div class="sec-label">Esta semana</div>
<div style="margin:0 24px">
  <div class="empty-state">
    <div class="es-icon">\U0001f4cb</div>
    <div class="es-title">Nenhum registro ainda</div>
    <div class="es-sub">Seus dados v\xe3o aparecer aqui depois do primeiro check-in.<br>Use o bot\xe3o acima ou envie /checkin no WhatsApp.</div>
  </div>
</div>"""
    else:
        m = media
        # Fallback remédios padrão
        _remed_padrao = [
            {"nome": r["nome"], "qtd": float(r["dose_padrao"] or 1), "tomado": True}
            for r in remedios_padrao
        ]

        # ---- Remédios prioritários (Rivotril, Zolpidem) ----
        REMED_PRIORITARIOS = {"rivotril", "zolpidem"}
        hist_doses = {}  # nome -> lista de (data_str, qtd) mais recente primeiro
        for r in rows:
            rj = r["remedios_tomados"]
            data_str_r = r["data"].strftime("%d/%m")
            try:
                itens = (rj if isinstance(rj, list) else _json.loads(rj)) if rj else _remed_padrao
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

        remed_prio_html = ""
        for nome_prio in ["Rivotril", "Zolpidem"]:
            doses = hist_doses.get(nome_prio, [])
            # doses está em ordem: mais recente primeiro (mesma ordem de rows DESC)
            dose_hoje_val = doses[0][1] if doses else None
            dose_display = f'{dose_hoje_val:g}' if dose_hoje_val is not None else "\u2014"
            max_dose = max((d[1] for d in doses), default=1) or 1
            barras = ""
            # mostrar em ordem cronológica (mais antigo → mais recente)
            doses_crono = list(reversed(doses[:7]))
            for i, (ds_r, qtd) in enumerate(doses_crono):
                h = max(4, int((qtd / max_dose) * 40))
                cls = "remed-hist-bar today" if i == len(doses_crono) - 1 else "remed-hist-bar"
                barras += f'<div style="flex:1;display:flex;flex-direction:column;align-items:center"><div class="{cls}" style="height:{h}px;width:100%"></div><div class="remed-hist-label">{ds_r}</div></div>'
            hist_inner = barras if barras else '<span style="font-size:12px;color:var(--text3)">sem hist\xf3rico</span>'
            remed_prio_html += f"""
<div class="remed-priority-card">
  <div class="remed-priority-name">{nome_prio}</div>
  <div class="remed-priority-dose">{dose_display}<span> comp.</span></div>
  <div class="remed-priority-hist">{hist_inner}</div>
</div>"""

        body += '<div class="sec-label">Rem\xe9dios</div>'
        body += f'<div class="remed-priority-grid">{remed_prio_html}</div>'

        # Remédios secundários compactos
        secundarios = [r for r in _remed_padrao if r["nome"].lower() not in REMED_PRIORITARIOS]
        if secundarios:
            sec_items = "".join(f'<span class="remed-sec-item">{s["nome"]}</span>' for s in secundarios)
            body += f'<div class="remed-sec" style="margin-top:8px"><span class="remed-sec-label">Outros</span>{sec_items}</div>'

        # ---- Exercício com destaque ----
        EX_CORES = {"Nenhum": "#2A2A38", "Leve": "#FCD34D", "Moderado": "#86EFAC", "Intenso": "#A78BFA"}
        EX_ALTURA = {"Nenhum": 4, "Leve": 16, "Moderado": 28, "Intenso": 40}
        ex_html = ""
        for r in list(reversed(rows))[-7:]:
            ex_val = r["exercicio"] or "Nenhum"
            cor = EX_CORES.get(ex_val, "#2A2A38")
            altura = EX_ALTURA.get(ex_val, 4)
            ds_ex = r["data"].strftime("%d/%m")
            ex_html += f'<div class="ex-day"><div class="ex-bar" style="height:{altura}px;background:{cor}"></div><div class="ex-day-lbl">{ds_ex}</div><div class="ex-intensidade">{ex_val}</div></div>'

        body += f"""
<div class="sec-label">Exerc\xedcio</div>
<div class="ex-card">
  <div class="ex-title">Intensidade \u2014 7 dias</div>
  <div class="ex-week">{ex_html}</div>
</div>"""

        # ---- Streak + heatmap ----
        body += f"""
<div class="sec-label">Consist\xeancia</div>
<div class="streak-card">
  <div class="streak-row">
    <div class="streak-num">\U0001f525 {s_atual}</div>
    <div class="streak-info">
      <div class="streak-frase">{streak_frase}</div>
      <div class="streak-max">M\xe1ximo: {s_max} dias</div>
    </div>
  </div>
  <div class="heatmap">{dots}</div>
</div>"""

        # ---- Dimension cards (média semana) ----
        alcool_vals = [r["alcool"] for r in rows if r["alcool"]]
        alcool_moda = max(set(alcool_vals), key=alcool_vals.count) if alcool_vals else None
        alcool_display = alcool_moda or "\u2014"

        body += f"""
<div class="sec-label">M\xe9dia da semana</div>
<div class="dim-grid">
  <div class="dim-card">
    <div class="dim-title">\u2728 Mental &amp; Emocional</div>
    {_dim_row("Sa\xfade mental", m["mental"] if m else None)}
    {_dim_row("Stress trabalho", m["stress_t"] if m else None, invert=True)}
    {_dim_row("Stress rel.", m["stress_r"] if m else None, invert=True)}
  </div>
  <div class="dim-card">
    <div class="dim-title">\u26a1 Energia &amp; Sono</div>
    {_dim_row("Energia", m["energia"] if m else None)}
    {_dim_row("Sono (h)", m["sono_h"] if m else None, max_val=10)}
    {_dim_row("Qualidade sono", m["sono_q"] if m else None)}
  </div>
  <div class="dim-card">
    <div class="dim-title">\u2764 F\xedsico &amp; Social</div>
    {_dim_row("Dor f\xedsica", m["dor"] if m else None, invert=True)}
    {_dim_row("Desempenho social", m["social"] if m else None)}
  </div>
  <div class="dim-card">
    <div class="dim-title">\u2615 H\xe1bitos</div>
    {_dim_row("Cigarros/dia", m["cigarros"] if m else None, max_val=10, invert=True)}
    <div class="dim-row"><span class="dim-lbl">\xc1lcool (freq.)</span><span style="font-size:13px;font-weight:600;color:var(--text)">{alcool_display}</span></div>
  </div>
</div>"""

        # ---- Histórico diário compacto ----
        body += '<div class="sec-label" style="padding-top:16px">Hist\xf3rico</div>'
        body += '<div class="hist-compact">'
        for r in rows:
            di = r["data"].isoformat()
            ds = r["data"].strftime("%d/%m")
            me = r["saude_mental"]; en = r["energia"]; dor = r["dor_fisica"]
            sh = r["sono_horas"]; al = r["alcool"] or ""; ex = r["exercicio"] or ""
            sq = r["sono_qualidade"]; st = r["stress_trabalho"]; sr = r["stress_relacionamento"]
            so = r["desempenho_social"]; ci = r["cigarros"]
            rj_raw = r["remedios_tomados"]
            rj_str = _json.dumps(rj_raw if isinstance(rj_raw, list) else (_json.loads(rj_raw) if rj_raw else [])).replace("'", "\\'")
            me_c = _score_color(me) if me is not None else "#4A4A5A"
            chips_h = ""
            if me is not None: chips_h += f'<span class="hist-chip" style="color:{me_c}">mental {me}</span>'
            if en is not None: chips_h += f'<span class="hist-chip">energia {en}</span>'
            if sh is not None: chips_h += f'<span class="hist-chip">sono {sh}h</span>'
            if dor is not None: chips_h += f'<span class="hist-chip">dor {dor}</span>'
            if al: chips_h += f'<span class="hist-chip">{al}</span>'
            if ex and ex != "Nenhum": chips_h += f'<span class="hist-chip">{ex}</span>'
            body += (
                f'<div class="hist-row">'
                f'<span class="hist-date">{ds}</span>'
                f'<div class="hist-vals">{chips_h}</div>'
                f'<div class="hist-acts">'
                f'<button class="act-btn" style="padding:4px 8px;font-size:11px" onclick="openEdit(\'{di}\',\'{dor or ""}\',\'{en or ""}\',\'{sh or ""}\',\'{sq or ""}\',\'{me or ""}\',\'{st or ""}\',\'{sr or ""}\',\'{al}\',\'{ci or ""}\',\'{so or ""}\',\'{rj_str}\')">\u270f</button>'
                f'<button class="act-btn del" style="padding:4px 8px;font-size:11px" onclick="delDay(\'{di}\')">\xd7</button>'
                f'</div></div>'
            )
        body += '</div>'

    # ---- HTML dos remédios no modal de edição ----
    remed_modal_html = ""
    for rp in remedios_padrao:
        nome = rp["nome"]
        dp = float(rp["dose_padrao"] or 1)
        step = "0.5" if rp["tipo"] == "quantidade" else "1"
        remed_modal_html += (
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'background:var(--surface2);border-radius:10px;padding:8px 12px">'
            f'<span style="font-size:13px;font-weight:600;color:var(--text)">{nome}</span>'
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<span style="font-size:11px;color:var(--text3)">qtd</span>'
            f'<input class="ed-rem-qtd" data-nome="{nome}" type="number" min="0" max="20" step="{step}" value="{dp:g}"'
            f' style="width:60px;background:var(--surface);border:1px solid var(--border);border-radius:8px;'
            f'padding:6px 8px;color:var(--text);font-size:14px;font-weight:700;text-align:center;outline:none">'
            f'</div></div>'
        )

    return _render(body, remed_modal_html)


# ---------------------------------------------------------------------------
# POST /dashboard/relato
# ---------------------------------------------------------------------------

@router.post("/dashboard/relato")
async def dashboard_relato(texto: str = Form(...)):
    pool = get_pool()
    analysis = await _process_nota_completa(texto)
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO checkins (user_id, data, nota_raw, nota_sentimento, nota_categorias)
               VALUES (1, CURRENT_DATE, $1, $2, $3::jsonb)
               ON CONFLICT (user_id, data) DO UPDATE SET
               nota_raw=$1, nota_sentimento=$2, nota_categorias=$3::jsonb""",
            texto,
            analysis.get("sentimento", ""),
            _json.dumps(analysis.get("categorias", []), ensure_ascii=False),
        )
    return JSONResponse({"ok": True})


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
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO checkins (user_id, data, nota_raw, nota_sentimento, nota_categorias)
               VALUES (1, CURRENT_DATE, $1, $2, $3::jsonb)
               ON CONFLICT (user_id, data) DO UPDATE SET
               nota_raw=$1, nota_sentimento=$2, nota_categorias=$3::jsonb""",
            texto,
            analysis.get("sentimento", ""),
            _json.dumps(analysis.get("categorias", []), ensure_ascii=False),
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
    cigarros: str = Form(default=""),
    desempenho_social: str = Form(default=""),
    remedios_tomados: str = Form(default=""),
):
    def _int(v): return int(v) if str(v).strip() else None
    def _float(v): return float(v) if str(v).strip() else None

    try:
        remed_json = _json.dumps(_json.loads(remedios_tomados), ensure_ascii=False) if remedios_tomados.strip() else None
    except Exception:
        remed_json = None

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE checkins SET
              dor_fisica=$2, energia=$3, sono_horas=$4, sono_qualidade=$5,
              saude_mental=$6, stress_trabalho=$7, stress_relacionamento=$8,
              alcool=$9, cigarros=$10, desempenho_social=$11,
              remedios_tomados=COALESCE($12::jsonb, remedios_tomados)
            WHERE user_id=1 AND data=$1
            """,
            date.fromisoformat(data),
            _int(dor_fisica), _int(energia), _float(sono_horas), _int(sono_qualidade),
            _int(saude_mental), _int(stress_trabalho), _int(stress_relacionamento),
            alcool.strip() or None, _int(cigarros), _int(desempenho_social),
            remed_json,
        )
    return RedirectResponse("/dashboard", status_code=303)


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
