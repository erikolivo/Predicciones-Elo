"""
actualizar_ligas_extra.py
--------------------------
Se corre 1 VEZ POR SEMANA (no todos los días), para no competir por cupo
de API-Football con la vigilancia en vivo.

Descarga la tabla de posiciones (1 petición por liga) de las ligas
configuradas en LIGAS_API_FOOTBALL_EXTRA (fetch_data.py) -ligas que
ClubElo mide pero que football-data.co.uk no cubre- y guarda el Goal
Index resultante en data/goal_index_extra.json, que engine.py mezcla
automáticamente con el de football-data.co.uk.

Antes de usar esto, llena LIGAS_API_FOOTBALL_EXTRA en fetch_data.py con
los league_id que te interesen. Para encontrarlos:

    python3 -c "from fetch_data import buscar_id_liga_api_football as b; print(b('Ecuador'))"
"""

import json
from pathlib import Path

from fetch_data import (
    LIGAS_API_FOOTBALL_EXTRA,
    obtener_standings_liga,
    calcular_goal_index_desde_standings,
)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SALIDA = DATA_DIR / "goal_index_extra.json"


def actualizar():
    if not LIGAS_API_FOOTBALL_EXTRA:
        print("LIGAS_API_FOOTBALL_EXTRA está vacío en fetch_data.py. "
              "No hay nada que actualizar (esto es opcional).")
        return

    goal_index = {}
    for league_id, nombre in LIGAS_API_FOOTBALL_EXTRA.items():
        try:
            standings = obtener_standings_liga(league_id)
            nuevos = calcular_goal_index_desde_standings(standings)
            goal_index.update(nuevos)
            print(f"{nombre} (id {league_id}): {len(nuevos)} equipos")
        except Exception as e:
            print(f"[AVISO] No se pudo procesar la liga '{nombre}' (id {league_id}): {e}")

    SALIDA.write_text(json.dumps(goal_index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Listo: {len(goal_index)} equipos guardados en {SALIDA}")


if __name__ == "__main__":
    actualizar()
