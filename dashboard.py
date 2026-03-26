from fastapi import APIRouter
from fastapi.responses import HTMLResponse
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
body{background:#121212;color:#E0E0E0;font-family:Inter,system-ui,sans-serif;padding:24px 16px}
h1{font-size:20px;font-weight:600;margin-bottom:4px;color:#BB86FC}
.sub{font-size:13px;color:#9E9E9E;margin-bottom:24px}
.card{background:#1E1E1E;border-radius:12px;padding:16px;margin-bottom:16px}
.card h2{font-size:13px;color:#9E9E9E;font-weight:500;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:#9E9E9E;font-weight:500;padding:4px 8px 8px 0;border-bottom:1px solid #2C2C2C}
td{padding:8px 8px 8px 0;border-bottom:1px solid #1a1a1a;vertical-align:top}
tr:last-child td{border-bottom:none}
.val{font-weight:600;color:#BB86FC}
.ok{color:#4CAF50}
.bad{color:#CF6679}
.label{font-size:11px;color:#9E9E9E}
.streak{font-size:32px;font-weight:700;color:#BB86FC}
.streak-sub{font-size:13px;color:#9E9E9E;margin-top:4px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.stat{background:#2C2C2C;border-radius:8px;padding:12px}
.stat-val{font-size:22px;font-weight:700;color:#E0E0E0}
.stat-lbl{font-size:11px;color:#9E9E9E;margin-top:2px}
.empty{color:#9E9E9E;font-size:13px;text-align:center;padding:24px}
</style>
</head>
<body>
<h1>Monitoramento Mental</h1>
<div class="sub">Seus dados dos últimos 7 dias</div>

<!--CONTENT-->

</body>
</html>"""


def _bar(val, max_val=10):
    if val is None:
        return "—"
    pct = int((float(val) / max_val) * 100)
    color = "#4CAF50" if pct >= 60 else ("#FF9800" if pct >= 30 else "#CF6679")
    return f'<span class="val">{val}</span> <span style="display:inline-block;width:{pct}px;max-width:80px;height:6px;background:{color};border-radius:3px;vertical-align:middle"></span>'


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT data, dor_fisica, energia, sono_horas, sono_qualidade,
                       saude_mental, stress_trabalho, stress_relacionamento,
                       alcool, cigarros, desempenho_social, nota_raw
                FROM checkins
                WHERE user_id = 1
                ORDER BY data DESC
                LIMIT 7
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
                  ROUND(AVG(cigarros),1) AS cigarros
                FROM checkins
                WHERE user_id = 1 AND data >= CURRENT_DATE - 6
                """,
            )
    except Exception as e:
        return _HTML.replace("<!--CONTENT-->", f'<div class="empty">Erro ao carregar dados: {e}</div>')

    content = ""

    # Streak
    s_atual = streak["streak_atual"] if streak else 0
    s_max = streak["streak_maximo"] if streak else 0
    content += f"""
<div class="card">
  <h2>Sequência</h2>
  <div class="streak">\U0001f525 {s_atual} dias</div>
  <div class="streak-sub">Máximo: {s_max} dias</div>
</div>"""

    # Médias
    if media and media["mental"] is not None:
        content += f"""
<div class="card">
  <h2>Média — últimos 7 dias</h2>
  <div class="grid">
    <div class="stat"><div class="stat-val">{media['mental']}</div><div class="stat-lbl">Saúde mental</div></div>
    <div class="stat"><div class="stat-val">{media['energia']}</div><div class="stat-lbl">Energia</div></div>
    <div class="stat"><div class="stat-val">{media['dor']}</div><div class="stat-lbl">Dor física</div></div>
    <div class="stat"><div class="stat-val">{media['sono_h']}h</div><div class="stat-lbl">Sono</div></div>
    <div class="stat"><div class="stat-val">{media['stress_t']}</div><div class="stat-lbl">Stress trabalho</div></div>
    <div class="stat"><div class="stat-val">{media['cigarros']}</div><div class="stat-lbl">Cigarros/dia</div></div>
  </div>
</div>"""

    # Histórico diário
    if not rows:
        content += '<div class="card"><div class="empty">Nenhum registro ainda.</div></div>'
    else:
        content += '<div class="card"><h2>Histórico diário</h2><table>'
        content += "<tr><th>Data</th><th>Mental</th><th>Energia</th><th>Dor</th><th>Sono</th><th>Stress T</th><th>Cigarros</th></tr>"
        for r in rows:
            data = r["data"].strftime("%d/%m")
            content += (
                f"<tr>"
                f"<td>{data}</td>"
                f"<td>{_bar(r['saude_mental'])}</td>"
                f"<td>{_bar(r['energia'])}</td>"
                f"<td>{_bar(r['dor_fisica'])}</td>"
                f"<td><span class='val'>{r['sono_horas'] or '—'}</span></td>"
                f"<td>{_bar(r['stress_trabalho'])}</td>"
                f"<td><span class='val'>{r['cigarros'] if r['cigarros'] is not None else '—'}</span></td>"
                f"</tr>"
            )
        content += "</table></div>"

        # Notas
        notas = [(r["data"].strftime("%d/%m"), r["nota_raw"]) for r in rows if r["nota_raw"] and r["nota_raw"] != "Pular"]
        if notas:
            content += '<div class="card"><h2>Notas recentes</h2>'
            for data, nota in notas:
                content += f'<div style="margin-bottom:12px"><div class="label">{data}</div><div style="margin-top:4px;font-size:14px">{nota}</div></div>'
            content += "</div>"

    return _HTML.replace("<!--CONTENT-->", content)
