"""
monitor.py
----------
Se corre cada 15 minutos (vía GitHub Actions) durante el día del partido.

Lógica de la alerta (en este orden):
  1. Filtro de marcador: el equipo FAVORITO va empatando o perdiendo por
     máximo 1 gol (nunca se alerta si va ganando).
  2. Condición principal: ese mismo favorito está "atacando constantemente",
     aproximado con tiros totales + córners claramente por encima del rival
     (ver PRESION_MINIMA_* más abajo).

Solo si se cumplen las dos, se envía UNA alerta por partido (para no
espamear). Está diseñado para gastar el mínimo de peticiones posibles del
plan gratuito de API-Football (100/día):
  - 1 petición para ver TODOS los partidos en vivo del mundo.
  - Solo pide estadísticas (1 petición extra) para los partidos que YA
    cumplieron el filtro de marcador.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fetch_data import obtener_partidos_en_vivo, obtener_estadisticas_fixture
from telegram_utils import enviar_mensaje_telegram

DATA_DIR = Path(__file__).parent / "data"
VIGILANCIA_FILE = DATA_DIR / "vigilancia.json"

# Qué tan por encima debe estar el favorito en tiros/córners para
# considerarlo "atacando constantemente". Ajusta estos números con el
# tiempo según qué tan sensible/ruidosa quieras la alerta.
PRESION_MINIMA_TIROS = 3       # tiros totales de diferencia
PRESION_MINIMA_CORNERS = 2     # córners de diferencia

# Ventana horaria en la que SÍ vale la pena gastar una petición para ver si
# un partido ya está en vivo. Fuera de esta ventana, no se consulta nada
# (0 peticiones), para no gastar cupo revisando partidos que ni han
# empezado o que ya hace rato terminaron.
MINUTOS_ANTES_DEL_INICIO = 10   # empieza a mirar 10 min antes del pitazo inicial
MINUTOS_DURACION_MAXIMA = 130   # 90 min + entretiempo + alargue, con margen


def _en_ventana_de_partido(kickoff_utc_iso, ahora=None):
    """True si 'ahora' está dentro de la ventana probable del partido."""
    if not kickoff_utc_iso:
        return False
    ahora = ahora or datetime.now(timezone.utc)
    kickoff = datetime.fromisoformat(kickoff_utc_iso.replace("Z", "+00:00"))
    inicio_ventana = kickoff - timedelta(minutes=MINUTOS_ANTES_DEL_INICIO)
    fin_ventana = kickoff + timedelta(minutes=MINUTOS_DURACION_MAXIMA)
    return inicio_ventana <= ahora <= fin_ventana


def _valor_stat(stats_equipo, nombre_stat):
    for item in stats_equipo.get("statistics", []):
        if item.get("type") == nombre_stat:
            v = item.get("value")
            if v is None:
                return 0
            if isinstance(v, str) and v.endswith("%"):
                return float(v.replace("%", ""))
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0
    return 0


def _esta_atacando_constantemente(stats_favorito, stats_rival):
    tiros_fav = _valor_stat(stats_favorito, "Total Shots")
    tiros_rival = _valor_stat(stats_rival, "Total Shots")
    corners_fav = _valor_stat(stats_favorito, "Corner Kicks")
    corners_rival = _valor_stat(stats_rival, "Corner Kicks")

    domina_tiros = (tiros_fav - tiros_rival) >= PRESION_MINIMA_TIROS
    domina_corners = (corners_fav - corners_rival) >= PRESION_MINIMA_CORNERS
    return domina_tiros or domina_corners


def revisar():
    if not VIGILANCIA_FILE.exists():
        print("No hay data/vigilancia.json todavía (corre engine.py con "
              "generar_agenda_de_manana() la noche anterior).")
        return

    agenda = json.loads(VIGILANCIA_FILE.read_text(encoding="utf-8"))
    partidos_vigilar = [p for p in agenda["partidos"]
                         if p["fixture_id"] is not None and not p["notificado"]]

    if not partidos_vigilar:
        print("Nada que vigilar (ya se notificaron todos, o no hay fixture_id).")
        return

    # Filtro clave para no gastar cupo: solo seguimos si AL MENOS un
    # partido está dentro de su ventana horaria real en este momento.
    partidos_en_ventana = [p for p in partidos_vigilar
                            if _en_ventana_de_partido(p.get("kickoff_utc"))]

    if not partidos_en_ventana:
        print("Ningún partido vigilado está en su ventana horaria todavía "
              "(0 peticiones gastadas).")
        return

    print("Consultando partidos en vivo (1 petición)...")
    en_vivo = obtener_partidos_en_vivo()
    en_vivo_por_id = {f["fixture"]["id"]: f for f in en_vivo}

    cambios = False

    for p in partidos_en_ventana:
        fixture = en_vivo_por_id.get(p["fixture_id"])
        if not fixture:
            continue  # ese partido no está en vivo en este momento

        goles_home = fixture["goals"]["home"] or 0
        goles_away = fixture["goals"]["away"] or 0
        nombre_home = fixture["teams"]["home"]["name"]
        nombre_away = fixture["teams"]["away"]["name"]

        favorito = p["favorito"]
        es_favorito_local = favorito in nombre_home or nombre_home in favorito
        goles_favorito = goles_home if es_favorito_local else goles_away
        goles_rival = goles_away if es_favorito_local else goles_home

        diferencia = goles_favorito - goles_rival  # negativo = va perdiendo
        cumple_marcador = diferencia == 0 or diferencia == -1

        if not cumple_marcador:
            continue

        # Solo si el marcador ya califica, gastamos 1 petición extra en estadísticas
        try:
            stats = obtener_estadisticas_fixture(p["fixture_id"])
        except Exception as e:
            print(f"[AVISO] No se pudieron obtener estadísticas de {p['partido']}: {e}")
            continue

        if len(stats) != 2:
            continue

        stats_home, stats_away = stats[0], stats[1]
        stats_favorito = stats_home if es_favorito_local else stats_away
        stats_rival = stats_away if es_favorito_local else stats_home

        if not _esta_atacando_constantemente(stats_favorito, stats_rival):
            continue

        minuto = fixture["fixture"]["status"].get("elapsed", "?")
        situacion = "empatando" if diferencia == 0 else "perdiendo por 1 gol"
        mensaje = (
            f"⚠️ <b>{p['partido']}</b>\n"
            f"Minuto {minuto}': {nombre_home} {goles_home} - {goles_away} {nombre_away}\n"
            f"{favorito} (tu favorito) va {situacion} pero está atacando "
            f"constantemente. Puede llegar el gol."
        )
        enviado = enviar_mensaje_telegram(mensaje)
        if enviado:
            p["notificado"] = True
            cambios = True
            print(f"Alerta enviada: {p['partido']}")

    if cambios:
        VIGILANCIA_FILE.write_text(json.dumps(agenda, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print("Ninguna alerta nueva en esta revisión.")


if __name__ == "__main__":
    revisar()
