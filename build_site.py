"""
build_site.py
-------------
Lee data/predicciones.json y genera docs/index.html: una página simple,
sin frameworks, que GitHub Pages puede servir gratis y que se regenera
sola cada vez que corre el workflow de GitHub Actions.
"""

import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "predicciones.json"
OUT_FILE = Path(__file__).parent / "docs" / "index.html"

PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Predicciones Elo + Goal Index</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background:#0f1115; color:#e6e6e6; }}
  h1 {{ font-size: 1.4rem; }}
  .meta {{ color:#9aa0a6; font-size: 0.85rem; margin-bottom: 20px; }}
  .partido {{ background:#1a1d24; border-radius: 10px; padding: 16px; margin-bottom: 14px; }}
  .titulo {{ font-weight: 600; font-size: 1.05rem; }}
  .badge {{ display:inline-block; background:#2d7a46; color:white; font-size:0.7rem; padding:2px 8px; border-radius: 12px; margin-left:8px; }}
  .probs {{ display:flex; gap:10px; margin: 10px 0; }}
  .prob {{ background:#22262f; border-radius:8px; padding:8px 12px; text-align:center; flex:1; }}
  .prob b {{ display:block; font-size:1.1rem; }}
  .marcadores {{ font-size:0.9rem; color:#c7c9cc; }}
  .marcadores span {{ background:#22262f; padding:3px 8px; border-radius:6px; margin-right:6px; }}
</style>
</head>
<body>
  <h1>⚽ Predicciones (Elo + Goal Index)</h1>
  <div class="meta">
    Generado: {generado_en} &middot;
    Partidos analizados: {total_partidos_analizados} &middot;
    Con Elo y Goal Index alineados: {total_predicciones}
  </div>
  {partidos_html}
</body>
</html>
"""

PARTIDO_TEMPLATE = """
<div class="partido">
  <div class="titulo">{partido} <span class="badge">{confianza}</span></div>
  <div class="probs">
    <div class="prob">Local<b>{prob_local_pct}%</b></div>
    <div class="prob">Empate<b>{prob_empate_pct}%</b></div>
    <div class="prob">Visitante<b>{prob_visitante_pct}%</b></div>
  </div>
  <div class="marcadores">
    Marcadores más probables:
    {marcadores_html}
  </div>
</div>
"""


def render():
    if not DATA_FILE.exists():
        print("No existe data/predicciones.json todavía. Corre engine.py primero.")
        return

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    bloques = []
    for p in data["predicciones"]:
        marcadores_html = " ".join(
            f'<span>{m["marcador"]} ({m["probabilidad"]}%)</span>'
            for m in p["marcadores_probables"]
        )
        bloques.append(PARTIDO_TEMPLATE.format(
            partido=p["partido"],
            confianza="Elo + Goal Index coinciden" if p["confianza_alta"] else "",
            prob_local_pct=p["prob_local_pct"],
            prob_empate_pct=p["prob_empate_pct"],
            prob_visitante_pct=p["prob_visitante_pct"],
            marcadores_html=marcadores_html,
        ))

    html = PLANTILLA.format(
        generado_en=data["generado_en"],
        total_partidos_analizados=data["total_partidos_analizados"],
        total_predicciones=data["total_predicciones_con_alta_confianza"],
        partidos_html="\n".join(bloques) if bloques else "<p>No hay partidos que cumplan el filtro hoy.</p>",
    )

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"Página generada en {OUT_FILE}")


if __name__ == "__main__":
    render()
