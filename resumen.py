"""
resumen.py
----------
Se corre una sola vez al día, a las 7am (una hora después de generar la
agenda), y envía a Telegram la lista de partidos que se van a vigilar hoy:
equipo favorito y marcador más probable de cada uno.

No gasta cupo de API-Football (solo lee el vigilancia.json que ya se
generó a las 6am).
"""

import json
from pathlib import Path

from telegram_utils import enviar_mensaje_telegram

VIGILANCIA_FILE = Path(__file__).parent / "data" / "vigilancia.json"


def enviar_resumen():
    if not VIGILANCIA_FILE.exists():
        print("No hay data/vigilancia.json todavía (corre engine.py con "
              "generar_agenda_del_dia() primero).")
        return

    agenda = json.loads(VIGILANCIA_FILE.read_text(encoding="utf-8"))
    partidos = agenda.get("partidos", [])

    if not partidos:
        enviar_mensaje_telegram(
            "📋 Hoy no hay partidos que cumplan el filtro Elo + Goal Index."
        )
        print("Resumen enviado: sin partidos hoy.")
        return

    lineas = [f"📋 <b>Partidos a vigilar hoy ({agenda.get('fecha', '')})</b>"]
    for p in partidos:
        marcador_txt = ""
        if p.get("marcadores_probables"):
            top = p["marcadores_probables"][0]
            marcador_txt = f" · marcador más probable {top['marcador']} ({top['probabilidad']}%)"

        estado = "✅ con vigilancia en vivo" if p["fixture_id"] else "⚠️ sin vigilancia en vivo (no se pudo emparejar)"
        lineas.append(f"• {p['partido']} — favorito: {p['favorito']}{marcador_txt} [{estado}]")

    enviar_mensaje_telegram("\n".join(lineas))
    print(f"Resumen enviado con {len(partidos)} partido(s).")


if __name__ == "__main__":
    enviar_resumen()
