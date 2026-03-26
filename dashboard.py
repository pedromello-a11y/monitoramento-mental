import json as _json
from datetime import date, timedelta

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from config import OPENAI_API_KEY
from database import get_pool

router = APIRouter()

_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#121212;color:#E0E0E0;font-family:Inter,system-ui,sans-serif;padding:20px 16px 48px}
h1{font-size:22px;font-weight:700;color:#BB86FC;margin-bottom:2px}
.sub{font-size:13px;color:#9E9E9E;margin-bottom:24px}
.card{background:#1E1E1E;border-radius:14px;padding:18px;margin-bottom:16px}
.card h2{font-size:11px;color:#9E9E9E;font-weight:600;margin-bottom:14px;text-transform:uppercase;letter-spacing:.8px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:#9E9E9E;font-weight:500;padding:4px 6px 8px 0;border-bottom:1px solid #2C2C2C;white-space:nowrap}
td{padding:9px 6px 9px 0;border-bottom:1px solid #222;vertical-align:middle;white-space:nowrap}
tr:last-child td{border-bottom:none}
tr:hover td{background:#242424}
.val{font-weight:600;color:#E0E0E0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.stat{background:#2C2C2C;border-radius:10px;padding:14px 12px}
.stat-val{font-size:24px;font-weight:700;color:#BB86FC}
.stat-lbl{font-size:11px;color:#9E9E9E;margin-top:3px}
.empty{color:#9E9E9E;font-size:13px;text-align:center;padding:24px}
.streak-n{font-size:40px;font-weight:800;color:#BB86FC;line-height:1}
.streak-sub{font-size:13px;color:#9E9E9E;margin-top:6px}
.tag{display:inline-block;background:#2C2C2C;border-radius:20px;padding:3px 10px;font-size:11px;margin:2px 2px 2px 0;color:#BB86FC}
.sent-pos{color:#4CAF50}
.sent-neu{color:#9E9E9E}
.sent-neg{color:#CF6679}
.note-card{background:#242424;border-radius:10px;padding:12px;margin-bottom:10px}
.note-date{font-size:11px;color:#9E9E9E;margin-bottom:4px}
.note-resumo{font-size:14px;font-weight:500;margin-bottom:6px}
.note-raw{font-size:12px;color:#9E9E9E;margin-top:6px;line-height:1.5}
.bar-wrap{display:inline-flex;align-items:center;gap:6px}
.bar{height:5px;border-radius:3px;display:inline-block;vertical-align:middle}
.actions{display:flex;gap:8px;margin-top:10px}
.btn{padding:6px 14px;border-radius:8px;border:none;cursor:pointer;font-size:12px;font-weight:600}
.btn-edit{background:#BB86FC;color:#121212}
.btn-del{background:#2C2C2C;color:#CF6679}
.btn-del:hover{background:#3a1a1a}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.7);z-index:100;overflow-y:auto;padding:20px}
.modal.open{display:block}
.modal-box{background:#1E1E1E;border-radius:14px;padding:20px;max-width:480px;margin:40px auto}
.modal-box h3{font-size:16px;font-weight:600;margin-bottom:16px;color:#BB86FC}
.field{margin-bottom:14px}
.field label{font-size:12px;color:#9E9E9E;display:block;margin-bottom:4px}
.field input{width:100%;background:#2C2C2C;border:1px solid #333;border-radius:8px;padding:8px 10px;color:#E0E0E0;font-size:14px}
.field input:focus{outline:none;border-color:#BB86FC}
.modal-actions{display:flex;gap:8px;margin-top:18px}
.btn-save{background:#BB86FC;color:#121212;padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-size:13px;font-weight:700;flex:1}
.btn-cancel{background:#2C2C2C;color:#9E9E9E;padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-size:13px;flex:1}
</style>
</head>
<body>
<h1>\U0001f9e0 Dashboard</h1>
<div class="sub">Seus dados de sa\xfade — \xfaltimos 7 dias</div>
<!--CONTENT-->
<script>
function openEdit(data,dor,energia,sono_h,sono_q,mental,stress_t,stress_r,alcool,cigarros,social){
  document.getElementById('edit-data').value=data;
  document.getElementById('f-dor').value=dor;
  document.getElementById('f-energia').value=energia;
  document.getElementById('f-sono_horas').value=sono_h;
  document.getElementById('f-sono_qualidade').value=sono_q;
  document.getElementById('f-mental').value=mental;
  document.getElementById('f-stress_t').value=stress_t;
  document.getElementById('f-stress_r').value=stress_r;
  document.getElementById('f-alcool').value=alcool;
  document.getElementById('f-cigarros').value=cigarros;
  document.getElementById('f-social').value=social;
  document.getElementById('modal-edit').classList.add('open');
}
function closeEdit(){document.getElementById('modal-edit').classList.remove('open');}
function confirmDel(data){
  if(confirm('Remover registro de '+data+'?')){
    document.getElementById('del-data').value=data;
    document.getElementById('form-del').submit();
  }
}
</script>
<!-- Modal editar -->
<div class="modal" id="modal-edit">
<div class="modal-box">
  <h3>\u270f Editar registro</h3>
  <form method="post" action="/dashboard/editar">
  <input type="hidden" name="data" id="edit-data">
  <div class="grid">
    <div class="field"><label>\U0001fa7a Dor f\xedsica (0-10)</label><input name="dor_fisica" id="f-dor" type="number" min="0" max="10"></div>
    <div class="field"><label>\u26a1 Energia (0-10)</label><input name="energia" id="f-energia" type="number" min="0" max="10"></div>
    <div class="field"><label>\u2605 Sono horas</label><input name="sono_horas" id="f-sono_horas" type="number" min="0" max="16" step="0.5"></div>
    <div class="field"><label>\u263d Sono qualidade (0-10)</label><input name="sono_qualidade" id="f-sono_qualidade" type="number" min="0" max="10"></div>
    <div class="field"><label>\u2728 Sa\xfade mental (0-10)</label><input name="saude_mental" id="f-mental" type="number" min="0" max="10"></div>
    <div class="field"><label>\u23f0 Stress trabalho (0-10)</label><input name="stress_trabalho" id="f-stress_t" type="number" min="0" max="10"></div>
    <div class="field"><label>\u2665 Stress rel. (0-10)</label><input name="stress_relacionamento" id="f-stress_r" type="number" min="0" max="10"></div>
    <div class="field"><label>\u2615 \xc1lcool</label><input name="alcool" id="f-alcool" type="text" placeholder="Nenhum/Pouco/Moderado/Muito"></div>
    <div class="field"><label>\u2716 Cigarros</label><input name="cigarros" id="f-cigarros" type="number" min="0"></div>
    <div class="field"><label>\u2600 Social (0-10)</label><input name="desempenho_social" id="f-social" type="number" min="0" max="10"></div>
  </div>
  <div class="modal-actions">
    <button type="button" class="btn-cancel" onclick="closeEdit()">Cancelar</button>
    <button type="submit" class="btn-save">Salvar</button>
  </div>
  </form>
</div>
</div>
<!-- Form delete (hidden) -->
<form id="form-del" method="post" action="/dashboard/remover" style="display:none">
  <input type="hidden" name="data" id="del-data">
</form>
</body>
</html>"""


def _bar(val, max_val=10, invert=False):
    if val is None:
        return "<span style='color:#555'>—</span>"
    v = float(val)
    pct = int((v / max_val) * 100)
    if invert:
        color = "#4CAF50" if pct <= 30 else ("#FF9800" if pct <= 60 else "#CF6679")
    else:
        color = "#CF6679" if pct <= 30 else ("#FF9800" if pct <= 60 else "#4CAF50")
    w = max(4, int(pct * 0.6))
    return f'<span class="bar-wrap"><span class="val">{val}</span><span class="bar" style="width:{w}px;background:{color}"></span></span>'


def _sent_class(s):
    if not s:
        return "sent-neu", "—"
    m = {"positivo": ("sent-pos", "\U0001f7e2 positivo"),
         "neutro": ("sent-neu", "\u26aa neutro"),
         "negativo": ("sent-neg", "\U0001f534 negativo")}
    return m.get(s.lower(), ("sent-neu", s))


async def _process_nota(nota_raw: str) -> dict:
    if not OPENAI_API_KEY or not nota_raw or nota_raw.strip() in ("Pular", ""):
        return {}
    try:
        from openai import AsyncOpenAI
        ai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Analise o texto de di\xe1rio de sa\xfade mental e retorne JSON com: "
                    "resumo (frase curta e acolhedora, m\xe1x 80 chars), "
                    "sentimento (positivo/neutro/negativo), "
                    "categorias (lista de at\xe9 4 strings curtas em portugu\xeas). "
                    "Responda APENAS com JSON v\xe1lido."
                )},
                {"role": "user", "content": nota_raw},
            ],
            response_format={"type": "json_object"},
        )
        return _json.loads(resp.choices[0].message.content)
    except Exception:
        return {}


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_get():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT data, dor_fisica, energia, sono_horas, sono_qualidade,
                       saude_mental, stress_trabalho, stress_relacionamento,
                       alcool, cigarros, desempenho_social,
                       nota_raw, nota_sentimento, nota_categorias,
                       remedios_tomados
                FROM checkins WHERE user_id = 1
                ORDER BY data DESC LIMIT 7
                """,
            )
            streak = await conn.fetchrow(
                "SELECT streak_atual, streak_maximo FROM streak WHERE user_id = 1"
            )
            media = await conn.fetchrow(
                """
                SELECT
                  ROUND(AVG(dor_fisica),1) AS dor,
                  ROUND(AVG(energia),1) AS energia,
                  ROUND(AVG(sono_horas),1) AS sono_h,
                  ROUND(AVG(sono_qualidade),1) AS sono_q,
                  ROUND(AVG(saude_mental),1) AS mental,
                  ROUND(AVG(stress_trabalho),1) AS stress_t,
                  ROUND(AVG(stress_relacionamento),1) AS stress_r,
                  ROUND(AVG(cigarros),1) AS cigarros
                FROM checkins WHERE user_id = 1 AND data >= CURRENT_DATE - 6
                """,
            )
    except Exception as e:
        return _HTML.replace("<!--CONTENT-->", f'<div class="empty">Erro: {e}</div>')

    content = ""

    # Streak
    s_atual = streak["streak_atual"] if streak else 0
    s_max = streak["streak_maximo"] if streak else 0
    content += f"""
<div class="card">
  <h2>\U0001f525 Sequ\xeancia</h2>
  <div class="streak-n">{s_atual} dias</div>
  <div class="streak-sub">M\xe1ximo: {s_max} dias</div>
</div>"""

    # Médias
    if media and media["mental"] is not None:
        content += f"""
<div class="card">
  <h2>\U0001f4ca M\xe9dia \u2014 \xfaltimos 7 dias</h2>
  <div class="grid3">
    <div class="stat"><div class="stat-val">{media['mental']}</div><div class="stat-lbl">\u2728 Sa\xfade mental</div></div>
    <div class="stat"><div class="stat-val">{media['energia']}</div><div class="stat-lbl">\u26a1 Energia</div></div>
    <div class="stat"><div class="stat-val">{media['dor']}</div><div class="stat-lbl">\U0001fa7a Dor</div></div>
    <div class="stat"><div class="stat-val">{media['sono_h']}h</div><div class="stat-lbl">\u2605 Sono</div></div>
    <div class="stat"><div class="stat-val">{media['stress_t']}</div><div class="stat-lbl">\u23f0 Stress trab.</div></div>
    <div class="stat"><div class="stat-val">{media['stress_r']}</div><div class="stat-lbl">\u2665 Stress rel.</div></div>
    <div class="stat"><div class="stat-val">{media['cigarros']}</div><div class="stat-lbl">\u2716 Cigarros/dia</div></div>
  </div>
</div>"""

    # Histórico diário
    if not rows:
        content += '<div class="card"><div class="empty">Nenhum registro ainda.</div></div>'
    else:
        content += '<div class="card"><h2>\U0001f4c5 Hist\xf3rico di\xe1rio</h2><div style="overflow-x:auto"><table>'
        content += "<tr><th>Data</th><th>\u2728 Mental</th><th>\u26a1 Energia</th><th>\U0001fa7a Dor</th><th>\u2605 Sono h</th><th>\u263d Sono q</th><th>\u23f0 Stress T</th><th>\u2665 Stress R</th><th>\u2615 \xc1lcool</th><th>\u2716 Cig.</th><th>\u2600 Social</th><th>A\xe7\xf5es</th></tr>"
        for r in rows:
            data_str = r["data"].strftime("%d/%m")
            data_iso = r["data"].isoformat()
            dor = r["dor_fisica"] if r["dor_fisica"] is not None else ""
            energia = r["energia"] if r["energia"] is not None else ""
            sono_h = r["sono_horas"] if r["sono_horas"] is not None else ""
            sono_q = r["sono_qualidade"] if r["sono_qualidade"] is not None else ""
            mental = r["saude_mental"] if r["saude_mental"] is not None else ""
            stress_t = r["stress_trabalho"] if r["stress_trabalho"] is not None else ""
            stress_r = r["stress_relacionamento"] if r["stress_relacionamento"] is not None else ""
            alcool = r["alcool"] or ""
            cigarros = r["cigarros"] if r["cigarros"] is not None else ""
            social = r["desempenho_social"] if r["desempenho_social"] is not None else ""
            content += (
                f"<tr>"
                f"<td><b>{data_str}</b></td>"
                f"<td>{_bar(mental)}</td>"
                f"<td>{_bar(energia)}</td>"
                f"<td>{_bar(dor, invert=True)}</td>"
                f"<td><span class='val'>{sono_h}</span></td>"
                f"<td>{_bar(sono_q)}</td>"
                f"<td>{_bar(stress_t, invert=True)}</td>"
                f"<td>{_bar(stress_r, invert=True)}</td>"
                f"<td><span class='val'>{alcool}</span></td>"
                f"<td><span class='val'>{cigarros}</span></td>"
                f"<td>{_bar(social)}</td>"
                f"<td>"
                f"<button class='btn btn-edit' onclick=\"openEdit('{data_iso}','{dor}','{energia}','{sono_h}','{sono_q}','{mental}','{stress_t}','{stress_r}','{alcool}','{cigarros}','{social}')\">&#9998;</button> "
                f"<button class='btn btn-del' onclick=\"confirmDel('{data_iso}')\">&#215;</button>"
                f"</td>"
                f"</tr>"
            )
        content += "</table></div></div>"

        # Remédios
        remed_rows = [(r["data"].strftime("%d/%m"), r["remedios_tomados"]) for r in rows if r["remedios_tomados"]]
        if remed_rows:
            content += '<div class="card"><h2>\u2665 Rem\xe9dios tomados</h2>'
            for data_str, remed_json in remed_rows:
                try:
                    itens = remed_json if isinstance(remed_json, list) else _json.loads(remed_json)
                    tomados = [i for i in itens if i.get("tomado")]
                    if not tomados:
                        continue
                    content += f'<div style="margin-bottom:10px"><span class="note-date">{data_str}</span><br>'
                    for item in tomados:
                        qtd = f' \xd7 {item["qtd"]}' if item.get("qtd") else ""
                        content += f'<span class="tag">{item["nome"]}{qtd}</span>'
                    content += "</div>"
                except Exception:
                    pass
            content += "</div>"

        # Notas com IA
        notas = [(r["data"].strftime("%d/%m"), r["nota_raw"], r["nota_sentimento"], r["nota_categorias"])
                 for r in rows if r["nota_raw"] and r["nota_raw"] not in ("Pular", "Texto", "")]
        if notas:
            content += '<div class="card"><h2>\U0001f4dd Notas processadas</h2>'
            for data_str, nota_raw, sentimento, categorias in notas:
                # Tenta usar dados já salvos, senão processa
                if not sentimento:
                    analysis = await _process_nota(nota_raw)
                    resumo = analysis.get("resumo", nota_raw[:80])
                    sentimento = analysis.get("sentimento", "")
                    categorias = analysis.get("categorias", [])
                else:
                    resumo = nota_raw[:80] + ("..." if len(nota_raw) > 80 else "")

                sc, sl = _sent_class(sentimento)
                tags = "".join(f'<span class="tag">{c}</span>' for c in (categorias or []))
                content += f"""
<div class="note-card">
  <div class="note-date">{data_str} &nbsp; <span class="{sc}">{sl}</span></div>
  <div class="note-resumo">{resumo}</div>
  {tags}
  <details style="margin-top:8px"><summary style="font-size:11px;color:#9E9E9E;cursor:pointer">ver nota original</summary>
  <div class="note-raw">{nota_raw}</div></details>
</div>"""
            content += "</div>"

    return _HTML.replace("<!--CONTENT-->", content)


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
):
    def _int(v): return int(v) if v.strip() else None
    def _float(v): return float(v) if v.strip() else None

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE checkins SET
              dor_fisica = $2, energia = $3, sono_horas = $4, sono_qualidade = $5,
              saude_mental = $6, stress_trabalho = $7, stress_relacionamento = $8,
              alcool = $9, cigarros = $10, desempenho_social = $11
            WHERE user_id = 1 AND data = $1
            """,
            date.fromisoformat(data),
            _int(dor_fisica), _int(energia), _float(sono_horas), _int(sono_qualidade),
            _int(saude_mental), _int(stress_trabalho), _int(stress_relacionamento),
            alcool.strip() or None, _int(cigarros), _int(desempenho_social),
        )
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/dashboard/remover")
async def dashboard_remover(data: str = Form(...)):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM checkins WHERE user_id = 1 AND data = $1",
            date.fromisoformat(data),
        )
        await conn.execute(
            "DELETE FROM checkin_sessions WHERE user_id = 1 AND data_referencia = $1",
            date.fromisoformat(data),
        )
    return RedirectResponse("/dashboard", status_code=303)
