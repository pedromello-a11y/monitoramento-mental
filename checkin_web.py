import json as _json
from datetime import datetime, date, timedelta
import zoneinfo
from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse
from database import get_pool

router = APIRouter()

# ─── steps definition (injected as JSON to avoid emoji encoding in JS) ────────

_STEPS = [
    {"f": "dor_fisica",            "q": "\U0001FA7A Dor f\xEDsica hoje",              "h": "0 = nenhuma \xB7 10 = incapacitante",         "t": "scale",   "d": 0},
    {"f": "energia",               "q": "\u26A1 Como est\xE1 sua energia?",           "h": "0 = esgotado \xB7 10 = muita energia",        "t": "scale",   "d": 5},
    {"f": "sono_horas",            "q": "\U0001F634 Horas de sono",                   "h": "Horas reais dormidas",                        "t": "sono",    "d": 7},
    {"f": "sono_qualidade",        "q": "\U0001F634 Qualidade do sono",               "h": "0 = acordou destru\xEDdo \xB7 10 = \xF3timo", "t": "scale",   "d": 5},
    {"f": "saude_mental",          "q": "\U0001F9E0 Sa\xFAde mental hoje",            "h": "0 = dia muito dif\xEDcil \xB7 10 = excelente", "t": "scale",   "d": 5},
    {"f": "stress_trabalho",       "q": "\U0001F4BC Stress no trabalho",              "h": "0 = nenhum \xB7 10 = dia dominado",           "t": "scale",   "d": 0},
    {"f": "stress_relacionamento", "q": "\u2764\uFE0F Stress nos relacionamentos",    "h": "0 = nenhum \xB7 10 = muito pesado",           "t": "scale",   "d": 0},
    {"f": "alcool",                "q": "\U0001F37A \xC1lcool hoje",                  "h": "",                                            "t": "chips",   "d": "Nenhum",
     "o": ["Nenhum", "Pouco", "Moderado", "Muito"]},
    {"f": "cigarros",              "q": "\U0001F6AC Cigarros hoje",                   "h": "N\xFAmero de cigarros",                       "t": "cig",     "d": 2},
    {"f": "exercicio",             "q": "\u25B6 Exerc\xEDcio hoje",                   "h": "",                                            "t": "chips",   "d": "Nenhum",
     "o": ["Nenhum", "Leve", "Moderado", "Intenso"]},
    {"f": "desempenho_social",     "q": "\U0001F465 Desempenho social",               "h": "0 = em casa o dia todo \xB7 10 = muito ativo", "t": "scale",   "d": 5},
    {"f": "remedios_tomados",      "q": "\U0001F48A Rem\xE9dios de hoje",             "h": "Marque o que tomou",                          "t": "remedios", "d": []},
]

# ─── templates ────────────────────────────────────────────────────────────────

_FORM_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Check-in diário</title>
<style>
:root{
  --bg:#121212;--surface:#1E1E1E;--surface2:#272727;
  --primary:#BB86FC;--primary-dark:#9C60DB;
  --text:#E0E0E0;--sub:#9E9E9E;--border:#333;--success:#4CAF50;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{
  background:var(--bg);color:var(--text);
  font-family:Inter,Roboto,'Helvetica Neue',system-ui,sans-serif;
  min-height:100dvh;display:flex;flex-direction:column;align-items:center;
}
.pb{position:fixed;top:0;left:0;right:0;height:3px;background:var(--border);z-index:999;}
.pf{height:100%;background:var(--primary);transition:width .35s cubic-bezier(.4,0,.2,1);border-radius:0 2px 2px 0;}
.wrap{width:100%;max-width:480px;padding:52px 16px 36px;display:flex;flex-direction:column;min-height:100dvh;}
.meta{text-align:center;color:var(--sub);font-size:12px;letter-spacing:.8px;text-transform:uppercase;margin-bottom:18px;font-weight:500;}
.card{background:var(--surface);border-radius:20px;padding:28px 20px 24px;border:1px solid var(--border);}
.question{font-size:20px;font-weight:500;line-height:1.45;margin-bottom:6px;}
.hint{font-size:13px;color:var(--sub);margin-bottom:22px;line-height:1.5;}
.scale-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
.btn{
  background:var(--surface2);border:1.5px solid var(--border);border-radius:12px;
  color:var(--text);font-size:17px;font-weight:500;min-height:52px;width:100%;
  cursor:pointer;transition:background .1s,border-color .1s,transform .08s;
  font-family:inherit;-webkit-tap-highlight-color:transparent;touch-action:manipulation;
}
.btn:active{transform:scale(.93);}
.btn.sel{background:var(--primary);border-color:var(--primary);color:#18003a;font-weight:700;}
.btn.plus{background:transparent;border-style:dashed;color:var(--sub);font-size:22px;line-height:1;}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:4px;}
.chip{
  background:var(--surface2);border:1.5px solid var(--border);border-radius:100px;
  color:var(--text);font-size:15px;font-weight:500;padding:13px 20px;
  cursor:pointer;transition:background .1s,border-color .1s;
  font-family:inherit;flex:1 1 calc(50% - 5px);text-align:center;
  -webkit-tap-highlight-color:transparent;touch-action:manipulation;
}
.chip.sel{background:var(--primary);border-color:var(--primary);color:#18003a;font-weight:700;}
.crow{display:none;align-items:center;gap:8px;margin-top:12px;}
.cin{
  flex:1;background:var(--surface2);border:1.5px solid var(--border);border-radius:12px;
  color:var(--text);font-size:16px;padding:14px;font-family:inherit;outline:none;
  -webkit-appearance:none;
}
.cin:focus{border-color:var(--primary);}
.bok{
  background:var(--primary);border:none;border-radius:12px;
  color:#18003a;font-size:15px;font-weight:700;padding:14px 18px;
  cursor:pointer;font-family:inherit;touch-action:manipulation;
  white-space:nowrap;
}
.nav{display:flex;gap:12px;margin-top:18px;align-items:center;}
#bb{
  background:transparent;border:1.5px solid var(--border);border-radius:14px;
  color:var(--sub);font-size:15px;padding:0 18px;height:54px;
  cursor:pointer;font-family:inherit;white-space:nowrap;
  -webkit-tap-highlight-color:transparent;touch-action:manipulation;flex-shrink:0;
}
#bn{
  flex:1;background:var(--primary);border:none;border-radius:14px;
  color:#18003a;font-size:17px;font-weight:700;height:54px;
  cursor:pointer;font-family:inherit;
  -webkit-tap-highlight-color:transparent;touch-action:manipulation;
}
#bn:active{background:var(--primary-dark);}
.rem-row{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
.rem-toggle{
  flex:1;background:var(--surface2);border:1.5px solid var(--border);border-radius:12px;
  color:var(--text);font-size:15px;font-weight:500;padding:14px 16px;text-align:left;
  cursor:pointer;font-family:inherit;transition:background .1s,border-color .1s;
  -webkit-tap-highlight-color:transparent;touch-action:manipulation;
}
.rem-toggle.sel{background:var(--primary);border-color:var(--primary);color:#18003a;font-weight:700;}
.rem-del{
  background:transparent;border:1.5px solid var(--border);border-radius:10px;
  color:var(--sub);font-size:18px;width:44px;height:44px;flex-shrink:0;
  cursor:pointer;font-family:inherit;touch-action:manipulation;
  display:flex;align-items:center;justify-content:center;
}
.rem-qty{display:flex;gap:6px;margin:0 0 8px 4px;flex-wrap:wrap;}
.btn-q{
  background:var(--surface2);border:1.5px solid var(--border);border-radius:10px;
  color:var(--text);font-size:14px;font-weight:500;padding:8px 16px;
  cursor:pointer;font-family:inherit;touch-action:manipulation;
}
.btn-q.sel{background:var(--primary);border-color:var(--primary);color:#18003a;font-weight:700;}
.rem-add{display:flex;gap:8px;margin-top:14px;}
</style>
</head>
<body>
<div class="pb"><div class="pf" id="pg"></div></div>
<div class="wrap">
  <div class="meta" id="mt"></div>
  <div class="card" id="cd"></div>
  <div class="nav">
    <button id="bb" onclick="bk()">&#8592; Voltar</button>
    <button id="bn" onclick="nx()">Pr&#xF3;ximo &#8594;</button>
  </div>
</div>
<form id="f" method="post" action="/checkin-web" style="display:none">
  <input type="hidden" name="user_id" value="1">
  <input type="hidden" id="v-data_ref"               name="data_ref" value="hoje">
  <input type="hidden" id="v-dor_fisica"             name="dor_fisica">
  <input type="hidden" id="v-energia"                name="energia">
  <input type="hidden" id="v-sono_horas"             name="sono_horas">
  <input type="hidden" id="v-sono_qualidade"         name="sono_qualidade">
  <input type="hidden" id="v-saude_mental"           name="saude_mental">
  <input type="hidden" id="v-stress_trabalho"        name="stress_trabalho">
  <input type="hidden" id="v-stress_relacionamento"  name="stress_relacionamento">
  <input type="hidden" id="v-alcool"                 name="alcool">
  <input type="hidden" id="v-cigarros"               name="cigarros">
  <input type="hidden" id="v-desempenho_social"      name="desempenho_social">
  <input type="hidden" id="v-remedios_tomados"       name="remedios_tomados">
</form>
<script>
/*ST_INJECT*/
/*REMED_INJECT*/
/*DATA_INJECT*/
if(typeof ST==='undefined'){var ST=[];}
if(typeof REMED==='undefined'){var REMED=[];}

var cur=0;
var vals={};
ST.forEach(function(s){
  if(s.t==='remedios'){
    vals[s.f]=REMED.map(function(r){
      return {id:r.id,nome:r.nome,tipo:r.tipo,tomado:false,qtd:r.dose_padrao};
    });
  }else{
    vals[s.f]=s.d;
  }
});

function setDia(v){
  dataRef=v;
  document.getElementById('v-data_ref').value=v;
  render();
}

function render(){
  var n=ST.length, s=ST[cur];
  document.getElementById('pg').style.width=Math.round(cur/n*100)+'%';
  document.getElementById('mt').textContent='Passo '+(cur+1)+' de '+n;

  var diaBar='';
  if(cur===0){
    var sH=dataRef==='hoje'?' sel':'';
    var sO=dataRef==='ontem'?' sel':'';
    diaBar='<div style="display:flex;gap:8px;margin-bottom:18px">'
      +'<button type="button" class="chip'+sH+'" style="flex:1" onclick="setDia(\'hoje\')">Hoje</button>'
      +'<button type="button" class="chip'+sO+'" style="flex:1" onclick="setDia(\'ontem\')">Ontem</button>'
      +'</div>';
  }

  var h=diaBar+'<div class="question">'+s.q+'</div>';
  if(s.h) h+='<div class="hint">'+s.h+'</div>';

  if(s.t==='scale'){
    h+='<div class="scale-grid">';
    for(var i=0;i<=10;i++){
      var sel=vals[s.f]===i?' sel':'';
      h+='<button type="button" class="btn'+sel+'" onclick="pick('+i+')">'+i+'</button>';
    }
    h+='</div>';

  }else if(s.t==='chips'){
    h+='<div class="chips">';
    s.o.forEach(function(op,idx){
      var sel=vals[s.f]===op?' sel':'';
      h+='<button type="button" class="chip'+sel+'" onclick="pickC('+idx+')">'+op+'</button>';
    });
    h+='</div>';

  }else if(s.t==='sono'){
    var presets=[4,5,6,7,8,9,10];
    var isCustom=presets.indexOf(vals[s.f])===-1;
    h+='<div class="scale-grid">';
    presets.forEach(function(v){
      var sel=vals[s.f]===v?' sel':'';
      h+='<button type="button" class="btn'+sel+'" onclick="pick('+v+')">'+v+'h</button>';
    });
    if(isCustom){
      h+='<button type="button" class="btn sel" onclick="showSono()">'+vals[s.f]+'h</button>';
    }else{
      h+='<button type="button" class="btn plus" onclick="showSono()">+</button>';
    }
    h+='</div>';
    h+='<div class="crow" id="sr">';
    h+='<input class="cin" id="sv" type="number" min="0" max="16" step="0.5" placeholder="Ex: 5.5">';
    h+='<button class="bok" type="button" onclick="okSono()">OK</button>';
    h+='</div>';

  }else if(s.t==='cig'){
    var cpresets=[0,1,2,3,5,8,10];
    var isCCustom=cpresets.indexOf(vals[s.f])===-1;
    h+='<div class="scale-grid">';
    cpresets.forEach(function(v){
      var sel=vals[s.f]===v?' sel':'';
      h+='<button type="button" class="btn'+sel+'" onclick="pick('+v+')">'+v+'</button>';
    });
    if(isCCustom){
      h+='<button type="button" class="btn sel" onclick="showCig()">'+vals[s.f]+'</button>';
    }else{
      h+='<button type="button" class="btn plus" onclick="showCig()">+</button>';
    }
    h+='</div>';
    h+='<div class="crow" id="cr">';
    h+='<input class="cin" id="cv" type="number" min="0" max="40" placeholder="Ex: 15">';
    h+='<button class="bok" type="button" onclick="okCig()">OK</button>';
    h+='</div>';

  }else if(s.t==='remedios'){
    var items=vals[s.f];
    if(items.length===0){
      h+='<div class="hint" style="text-align:center;padding:8px 0">Nenhum rem\xE9dio cadastrado.</div>';
    }
    items.forEach(function(r,i){
      var sel=r.tomado?' sel':'';
      h+='<div class="rem-row">';
      h+='<button type="button" class="rem-toggle'+sel+'" onclick="toggleRem('+i+')">'+r.nome+'</button>';
      h+='<button type="button" class="rem-del" onclick="removeRem('+i+')">\xD7</button>';
      h+='</div>';
      if(r.tomado&&r.tipo==='quantidade'){
        h+='<div class="rem-qty">';
        [0.5,1,2,3,4,6,8].forEach(function(q){
          var qsel=r.qtd===q?' sel':'';
          h+='<button type="button" class="btn-q'+qsel+'" onclick="setRemQtd('+i+','+q+')">'+q+'</button>';
        });
        h+='</div>';
      }
    });
    h+='<div class="rem-add">';
    h+='<input class="cin" id="ra" type="text" placeholder="Outro rem\xE9dio...">';
    h+='<button class="bok" type="button" onclick="okAddRem()">+</button>';
    h+='</div>';
  }

  document.getElementById('cd').innerHTML=h;
  document.getElementById('bb').style.visibility=cur>0?'visible':'hidden';
  document.getElementById('bn').textContent=cur===n-1?'Salvar check\u2011in':'Pr\xF3ximo \u2192';
}

function pick(v){vals[ST[cur].f]=v;render();}
function pickC(i){vals[ST[cur].f]=ST[cur].o[i];render();}
function showSono(){var el=document.getElementById('sr');if(el){el.style.display='flex';}}
function showCig(){var el=document.getElementById('cr');if(el){el.style.display='flex';}}

function okSono(){
  var v=parseFloat(document.getElementById('sv').value);
  if(!isNaN(v)&&v>=0&&v<=16){pick(v);}
}

function okCig(){
  var v=parseInt(document.getElementById('cv').value,10);
  if(!isNaN(v)&&v>=0&&v<=40){pick(v);}
}

function toggleRem(i){
  var r=vals['remedios_tomados'][i];
  r.tomado=!r.tomado;
  render();
}

function setRemQtd(i,q){
  vals['remedios_tomados'][i].qtd=q;
  render();
}

function removeRem(i){
  vals['remedios_tomados'].splice(i,1);
  render();
}

function okAddRem(){
  var el=document.getElementById('ra');
  if(!el) return;
  var nome=el.value.trim();
  if(!nome) return;
  vals['remedios_tomados'].push({id:null,nome:nome,tipo:'binario',tomado:true,qtd:1});
  render();
}

function nx(){
  if(cur<ST.length-1){cur++;render();window.scrollTo(0,0);}
  else{submit();}
}

function bk(){
  if(cur>0){cur--;render();window.scrollTo(0,0);}
}

function submit(){
  ST.forEach(function(s){
    if(s.t!=='remedios'){
      document.getElementById('v-'+s.f).value=vals[s.f];
    }
  });
  var taken=vals['remedios_tomados'].filter(function(r){return r.tomado;});
  var out=taken.map(function(r){
    var o={nome:r.nome};
    if(r.tipo==='quantidade') o.qtd=r.qtd;
    return o;
  });
  document.getElementById('v-remedios_tomados').value=JSON.stringify(out);
  document.getElementById('bn').textContent='Salvando...';
  document.getElementById('bn').disabled=true;
  document.getElementById('f').submit();
}

render();
</script>
</body>
</html>"""

# ─── páginas de resposta (dark mode) ──────────────────────────────────────────

_BASE_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Check-in</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#121212;color:#E0E0E0;font-family:Inter,Roboto,system-ui,sans-serif;
min-height:100dvh;display:flex;align-items:center;justify-content:center;padding:24px;}}
.card{{background:#1E1E1E;border:1px solid #333;border-radius:20px;
padding:40px 28px;max-width:400px;width:100%;text-align:center;}}
.icon{{font-size:52px;margin-bottom:20px;}}
.title{{font-size:22px;font-weight:600;margin-bottom:10px;color:#E0E0E0;}}
.body{{font-size:15px;color:#9E9E9E;line-height:1.6;}}
.link{{display:inline-block;margin-top:24px;color:#BB86FC;font-size:14px;text-decoration:none;}}
code{{background:#272727;padding:2px 6px;border-radius:4px;font-size:13px;color:#BB86FC;}}
</style>
</head>
<body><div class="card">{inner}</div></body>
</html>"""

_SUCCESS_HTML = _BASE_PAGE.format(inner="""
<div class="icon">&#127769;</div>
<div class="title">Check-in registrado.</div>
<div class="body">Seus dados de hoje foram salvos.<br>Até amanhã.</div>
""")

_ALREADY_HTML = _BASE_PAGE.format(inner="""
<div class="icon">&#9989;</div>
<div class="title">Já registrado hoje.</div>
<div class="body">O check-in de hoje já foi salvo.<br>Volte amanhã.</div>
""")

_SEM_BANCO_HTML = _BASE_PAGE.format(inner="""
<div class="icon">&#128274;</div>
<div class="title">Banco não configurado</div>
<div class="body">Preencha <code>DATABASE_URL</code> no <code>.env</code> para salvar o check-in.</div>
<a class="link" href="/checkin-web">&#8592; Voltar ao formulário</a>
""")


# ─── rotas ────────────────────────────────────────────────────────────────────

@router.get("/checkin-web", response_class=HTMLResponse)
async def checkin_web_get(data: str = None):
    # data param: YYYY-MM-DD para pré-selecionar dia específico
    import re
    data_inicial = "hoje"
    if data and re.match(r"^\d{4}-\d{2}-\d{2}$", data):
        hoje_str = datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo")).date().isoformat()
        ontem_str = (datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo")).date() - timedelta(days=1)).isoformat()
        if data == ontem_str:
            data_inicial = "ontem"
        elif data == hoje_str:
            data_inicial = "hoje"

    remed = []
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, nome, tipo, dose_padrao FROM remedios WHERE ativo = TRUE ORDER BY id"
            )
        seen: set = set()
        for r in rows:
            if r["nome"] not in seen:
                seen.add(r["nome"])
                remed.append({
                    "id": r["id"],
                    "nome": r["nome"],
                    "tipo": r["tipo"] or "quantidade",
                    "dose_padrao": float(r["dose_padrao"] or 1),
                })
    except Exception:
        pass
    html = _FORM_HTML
    html = html.replace("/*ST_INJECT*/", "var ST=" + _json.dumps(_STEPS) + ";")
    html = html.replace("/*REMED_INJECT*/", "var REMED=" + _json.dumps(remed) + ";")
    html = html.replace("/*DATA_INJECT*/", f"var dataRef={_json.dumps(data_inicial)};")
    return html


_MUITO_CEDO_HTML = _BASE_PAGE.format(inner="""
<div class="icon">&#128336;</div>
<div class="title">Check-in dispon\xedvel ap\xf3s 20h</div>
<div class="body">O check-in di\xe1rio s\xf3 pode ser feito a partir das 20h (hor\xe1rio de Bras\xedlia).<br>Volte mais tarde.</div>
<a class="link" href="/dashboard">\u2190 Voltar ao dashboard</a>
""")


@router.post("/checkin-web", response_class=HTMLResponse)
async def checkin_web_post(
    user_id: int = Form(...),
    dor_fisica: int = Form(...),
    energia: int = Form(...),
    sono_horas: float = Form(...),
    sono_qualidade: int = Form(...),
    saude_mental: int = Form(...),
    stress_trabalho: int = Form(...),
    stress_relacionamento: int = Form(...),
    alcool: str = Form(...),
    exercicio: str = Form(default="Nenhum"),
    cigarros: int = Form(...),
    desempenho_social: int = Form(...),
    remedios_tomados: str = Form(default="[]"),
    data_ref: str = Form(default="hoje"),
):
    try:
        remed_json = _json.dumps(_json.loads(remedios_tomados), ensure_ascii=False)
    except Exception:
        remed_json = "[]"

    try:
        pool = get_pool()
    except RuntimeError:
        return HTMLResponse(_SEM_BANCO_HTML, status_code=503)

    try:
        hoje = datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo")).date()
        ontem = hoje - timedelta(days=1)
        data_alvo = ontem if data_ref == "ontem" else hoje

        async with pool.acquire() as conn:
            existente = await conn.fetchrow(
                "SELECT id FROM checkins WHERE user_id = $1 AND data = $2",
                user_id, data_alvo,
            )
            if existente:
                return HTMLResponse(_ALREADY_HTML)
            await conn.execute(
                """
                INSERT INTO checkins
                  (user_id, data, dor_fisica, energia, sono_horas, sono_qualidade,
                   saude_mental, stress_trabalho, stress_relacionamento, alcool,
                   exercicio, cigarros, desempenho_social, remedios_tomados)
                VALUES ($1, $14, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb)
                ON CONFLICT (user_id, data) DO UPDATE SET
                  dor_fisica = $2, energia = $3, sono_horas = $4, sono_qualidade = $5,
                  saude_mental = $6, stress_trabalho = $7, stress_relacionamento = $8,
                  alcool = $9, exercicio = $10, cigarros = $11, desempenho_social = $12,
                  remedios_tomados = $13::jsonb
                """,
                user_id, dor_fisica, energia, sono_horas, sono_qualidade,
                saude_mental, stress_trabalho, stress_relacionamento, alcool,
                exercicio, cigarros, desempenho_social, remed_json, data_alvo,
            )
            # Registrar sessão concluída (para o cron saber que check-in foi feito)
            await conn.execute(
                """
                INSERT INTO checkin_sessions (user_id, data_referencia, status, concluido_em)
                VALUES ($1, $2, 'concluido', NOW())
                ON CONFLICT (user_id, data_referencia) DO UPDATE SET status='concluido', concluido_em=NOW()
                """,
                user_id, data_alvo,
            )
            # Atualizar streak apenas para check-in de hoje
            if data_alvo == hoje:
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
                    user_id, hoje, ontem,
                )
    except Exception as e:
        err_inner = (
            '<div class="icon">\u26A0\uFE0F</div>'
            '<div class="title">Erro ao salvar</div>'
            '<div class="body">Verifique a conex\xE3o com o banco.<br>'
            '<code>' + str(e)[:120] + '</code></div>'
            '<a class="link" href="/checkin-web">\u2190 Voltar</a>'
        )
        return HTMLResponse(_BASE_PAGE.format(inner=err_inner), status_code=503)

    return HTMLResponse(_SUCCESS_HTML)
