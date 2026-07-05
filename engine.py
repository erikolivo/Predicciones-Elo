"""
engine.py
---------
Orquesta todo el proceso:

  1. Descarga fixtures + Elo de ClubElo (clubes).
  2. Descarga resultados recientes de football-data.co.uk para calcular
     el Goal Index de cada club.
  3. Cruza los nombres de equipos entre ambas fuentes.
  4. Filtra los partidos donde el mismo equipo tiene MEJOR Elo Y MEJOR
     Goal Index que el rival (tu criterio de "coincidencia").
  5. Calcula la predicción (1X2 + marcadores probables) con poisson_model.
  6. Guarda todo en data/predicciones.json para que build_site.py
     genere la página.

Nota sobre selecciones nacionales: el mismo patrón aplica, pero football-data.co.uk
no cubre selecciones. Este archivo se enfoca primero en clubes (más fácil de
automatizar con fuentes 100% gratuitas y estables). Ver notes_selecciones.md
para cómo extender esto a selecciones con eloratings.net.
"""

import json
import datetime
from pathlib import Path

from fetch_data import (
    obtener_fixtures_clubelo,
    obtener_resultados_liga,
    obtener_resultados_liga_extra,
    calcular_goal_index,
    buscar_equipo_similar,
    obtener_fixtures_por_fecha,
    LIGAS_FOOTBALL_DATA,
    LIGAS_FOOTBALL_DATA_EXTRA,
)
from poisson_model import predecir_partido

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

GOAL_INDEX_EXTRA_CACHE = DATA_DIR / "goal_index_extra.json"  # lo llena actualizar_ligas_extra.py, 1 vez/semana

# "Distancia considerable" de Elo pedida: el favorito debe superar al rival
# por al menos esta cantidad de puntos de Elo para que el partido entre al
# filtro (además de tener también mejor Goal Index).
ELO_GAP_MINIMO = 100


def construir_goal_index_global():
    """
    Descarga resultados de las 38 ligas/divisiones de football-data.co.uk
    y calcula el Goal Index de cada equipo. Además, si existe el caché
    semanal de API-Football (data/goal_index_extra.json, generado por
    actualizar_ligas_extra.py), lo mezcla para sumar equipos de ligas que
    football-data.co.uk no cubre.
    """
    goal_index = {}

    for codigo in LIGAS_FOOTBALL_DATA:
        try:
            resultados = obtener_resultados_liga(codigo)
            goal_index.update(calcular_goal_index(resultados))
        except Exception as e:
            print(f"[AVISO] No se pudo procesar la liga {codigo}: {e}")

    for codigo in LIGAS_FOOTBALL_DATA_EXTRA:
        try:
            resultados = obtener_resultados_liga_extra(codigo)
            goal_index.update(calcular_goal_index(resultados))
        except Exception as e:
            print(f"[AVISO] No se pudo procesar la liga extra {codigo}: {e}")

    if GOAL_INDEX_EXTRA_CACHE.exists():
        try:
            extra = json.loads(GOAL_INDEX_EXTRA_CACHE.read_text(encoding="utf-8"))
            # No pisamos datos de football-data.co.uk si el equipo ya está ahí;
            # esto solo AGREGA equipos de ligas que no teníamos.
            for equipo, datos in extra.items():
                goal_index.setdefault(equipo, datos)
            print(f"Goal Index extra (API-Football, caché semanal): {len(extra)} equipos añadidos")
        except Exception as e:
            print(f"[AVISO] No se pudo leer el caché de goal_index_extra.json: {e}")

    return goal_index


def emparejar_nombre(nombre_clubelo, nombres_goal_index):
    """Encuentra el nombre equivalente en el diccionario de goal index."""
    if nombre_clubelo in nombres_goal_index:
        return nombre_clubelo
    coincidencias = buscar_equipo_similar(nombre_clubelo, list(nombres_goal_index))
    return coincidencias[0] if coincidencias else None


def generar_predicciones():
    print("Descargando fixtures de ClubElo...")
    fixtures = obtener_fixtures_clubelo()

    print("Descargando resultados recientes para el Goal Index...")
    goal_index = construir_goal_index_global()

    predicciones = []
    sin_datos_goal_index = set()

    for f in fixtures:
        home = f.get("Home") or f.get("HomeTeam")
        away = f.get("Away") or f.get("AwayTeam")
        try:
            elo_home = float(f.get("EloHome") or f.get("HomeElo") or f.get("Elo1"))
            elo_away = float(f.get("EloAway") or f.get("AwayElo") or f.get("Elo2"))
        except (TypeError, ValueError):
            continue  # fila sin datos de Elo usables

        home_gi_key = emparejar_nombre(home, goal_index)
        away_gi_key = emparejar_nombre(away, goal_index)

        if not home_gi_key or not away_gi_key:
            sin_datos_goal_index.add(home if not home_gi_key else away)
            continue

        gi_home = goal_index[home_gi_key]["goal_index"]
        gi_away = goal_index[away_gi_key]["goal_index"]

        diferencia_elo = abs(elo_home - elo_away)

        # --- Filtro pedido: el mismo equipo debe tener MEJOR Elo Y MEJOR
        #     goal index que el rival, Y la diferencia de Elo debe ser
        #     considerable (>= ELO_GAP_MINIMO) ---
        mismo_favorito = (
            (elo_home > elo_away and gi_home > gi_away) or
            (elo_away > elo_home and gi_away > gi_home)
        )
        if not mismo_favorito or diferencia_elo < ELO_GAP_MINIMO:
            continue

        pred = predecir_partido(home, away, elo_home, elo_away, gi_home, gi_away)
        pred["fecha"] = f.get("Date", "")
        pred["liga"] = f.get("Country", "")
        pred["diferencia_elo"] = round(diferencia_elo, 1)
        predicciones.append(pred)

    salida = {
        "generado_en": datetime.datetime.utcnow().isoformat() + "Z",
        "total_partidos_analizados": len(fixtures),
        "total_predicciones_con_alta_confianza": len(predicciones),
        "equipos_sin_goal_index": sorted(sin_datos_goal_index),
        "predicciones": predicciones,
    }

    with open(DATA_DIR / "predicciones.json", "w", encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=2)

    print(f"Listo. {len(predicciones)} partidos con Elo y Goal Index alineados.")
    print(f"Equipos sin goal index encontrado (revisar mapeo de nombres): {len(sin_datos_goal_index)}")
    return salida


def generar_agenda_del_dia():
    """
    Se corre una sola vez, a las 6am (antes de que empiece cualquier partido
    y de que la vigilancia en vivo gaste cupo). Filtra los partidos de
    ClubElo cuya fecha sea la de HOY, aplica el mismo filtro Elo+Goal
    Index, y para cada uno busca su fixture_id en API-Football (para poder
    seguirlo en vivo durante el día). Guarda todo en data/vigilancia.json.

    Por qué a las 6am y no en la noche anterior: si generamos la lista de
    partidos por la noche, esa petición sale del cupo del día anterior, y
    si ese día ya se gastaron muchas peticiones vigilando partidos, la
    generación de la lista de mañana podría fallar por falta de cupo. Al
    correr esto a las 6am del MISMO día (antes de que arranque cualquier
    partido), nos asegura que el primer cupo del día se use para construir
    la lista, sin competir con nada.
    """
    import datetime as dt

    hoy = dt.date.today().isoformat()

    resultado = generar_predicciones()  # reutiliza toda la lógica de filtrado
    partidos_hoy = [
        p for p in resultado["predicciones"] if p.get("fecha", "").startswith(hoy)
    ]

    print(f"Partidos de hoy ({hoy}) que cumplen el filtro: {len(partidos_hoy)}")

    # Buscamos los fixture_id en API-Football (1 sola petición para todo el día)
    try:
        fixtures_api = obtener_fixtures_por_fecha(hoy)
    except Exception as e:
        print(f"[AVISO] No se pudo consultar API-Football para hoy: {e}")
        fixtures_api = []

    nombres_home = {f["teams"]["home"]["name"]: f for f in fixtures_api}
    nombres_away = {f["teams"]["away"]["name"]: f for f in fixtures_api}

    vigilancia = []
    for p in partidos_hoy:
        local, visitante = p["partido"].split(" vs ")
        candidatos_home = buscar_equipo_similar(local, list(nombres_home.keys()))
        candidatos_away = buscar_equipo_similar(visitante, list(nombres_away.keys()))

        fixture_id = None
        kickoff_utc = None
        if candidatos_home and candidatos_away:
            f_home = nombres_home[candidatos_home[0]]
            f_away = nombres_away[candidatos_away[0]]
            if f_home["fixture"]["id"] == f_away["fixture"]["id"]:
                fixture_id = f_home["fixture"]["id"]
                kickoff_utc = f_home["fixture"]["date"]  # ISO 8601, ej. 2026-07-05T19:00:00+00:00

        vigilancia.append({
            "partido": p["partido"],
            "favorito": p["favorito"],
            "prob_local_pct": p["prob_local_pct"],
            "prob_visitante_pct": p["prob_visitante_pct"],
            "marcadores_probables": p["marcadores_probables"],
            "fixture_id": fixture_id,  # None si no se pudo emparejar -> no se podrá vigilar en vivo
            "kickoff_utc": kickoff_utc,  # None si no se pudo emparejar
            "notificado": False,
        })

    with open(DATA_DIR / "vigilancia.json", "w", encoding="utf-8") as fh:
        json.dump({"fecha": hoy, "partidos": vigilancia}, fh, ensure_ascii=False, indent=2)

    sin_fixture_id = sum(1 for v in vigilancia if v["fixture_id"] is None)
    if sin_fixture_id:
        print(f"[AVISO] {sin_fixture_id} partido(s) no se pudieron emparejar con API-Football "
              f"(no se podrán vigilar en vivo). Revisa data/vigilancia.json.")

    return vigilancia


if __name__ == "__main__":
    generar_predicciones()
