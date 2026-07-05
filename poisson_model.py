"""
poisson_model.py
-----------------
Convierte el Elo + Goal Index de dos equipos en:
  1. Probabilidad de victoria local / empate / victoria visitante
  2. Matriz de probabilidades de marcador exacto (0-0, 1-0, 2-0, 2-1, ...)

Metodología:
  - Elo -> probabilidad de resultado 1X2 (fórmula estándar de Elo + ventaja
    de local).
  - Goal Index (ataque/defensa de cada equipo) -> goles esperados (lambda)
    de cada equipo en ESTE partido concreto.
  - Goles esperados -> distribución de Poisson -> matriz de marcadores.
"""

import math
from functools import lru_cache

VENTAJA_LOCAL_ELO = 70  # puntos de Elo que se le suman al local (valor típico)
PROMEDIO_GOLES_LIGA = 1.35  # goles promedio por equipo por partido (ajustable)


def probabilidad_elo(elo_local, elo_visitante, ventaja_local=VENTAJA_LOCAL_ELO):
    """
    Probabilidad de que gane el local, según la fórmula estándar de Elo.
    Devuelve un valor entre 0 y 1.
    """
    diff = (elo_visitante) - (elo_local + ventaja_local)
    return 1 / (1 + 10 ** (diff / 400))


def goles_esperados(goal_index_local, goal_index_visitante,
                     promedio_liga=PROMEDIO_GOLES_LIGA):
    """
    Traduce el goal_index (goles_favor_prom - goles_contra_prom) de cada
    equipo en goles esperados (lambda de Poisson) para ESTE partido.

    Es una aproximación simple pero razonable: el equipo local anota su
    promedio de liga ajustado por su propio índice de gol y por la
    debilidad/fortaleza defensiva implícita del rival (aproximada aquí por
    el mismo goal_index, ya que no siempre tendremos ataque/defensa por
    separado).
    """
    lambda_local = max(0.15, promedio_liga + goal_index_local / 2 - goal_index_visitante / 4)
    lambda_visitante = max(0.15, promedio_liga + goal_index_visitante / 2 - goal_index_local / 4)
    return lambda_local, lambda_visitante


@lru_cache(maxsize=None)
def _poisson_pmf(k, lam):
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def matriz_marcadores(lambda_local, lambda_visitante, max_goles=6):
    """
    Devuelve un diccionario {(goles_local, goles_visitante): probabilidad}
    para todos los marcadores hasta max_goles-max_goles.
    """
    matriz = {}
    for gl in range(max_goles + 1):
        for gv in range(max_goles + 1):
            p = _poisson_pmf(gl, lambda_local) * _poisson_pmf(gv, lambda_visitante)
            matriz[(gl, gv)] = p
    return matriz


def probabilidades_1x2_desde_matriz(matriz):
    """A partir de la matriz de marcadores, calcula P(local)/P(empate)/P(visitante)."""
    p_local = sum(p for (gl, gv), p in matriz.items() if gl > gv)
    p_empate = sum(p for (gl, gv), p in matriz.items() if gl == gv)
    p_visitante = sum(p for (gl, gv), p in matriz.items() if gl < gv)
    return p_local, p_empate, p_visitante


def top_marcadores(matriz, n=3):
    """Devuelve los n marcadores más probables, ordenados de mayor a menor."""
    ordenado = sorted(matriz.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {"marcador": f"{gl}-{gv}", "probabilidad": round(p * 100, 1)}
        for (gl, gv), p in ordenado[:n]
    ]


def predecir_partido(equipo_local, equipo_visitante,
                      elo_local, elo_visitante,
                      goal_index_local, goal_index_visitante):
    """
    Función principal: junta todo lo anterior en una sola predicción legible.
    """
    p_local_elo = probabilidad_elo(elo_local, elo_visitante)

    lam_local, lam_visitante = goles_esperados(goal_index_local, goal_index_visitante)
    matriz = matriz_marcadores(lam_local, lam_visitante)
    p_local_gi, p_empate_gi, p_visitante_gi = probabilidades_1x2_desde_matriz(matriz)

    # Combinamos Elo (peso 60%) y Goal Index/Poisson (peso 40%) para el 1X2 final.
    # Puedes ajustar estos pesos en función de qué tan bien calibre cada fuente.
    p_local = 0.6 * p_local_elo + 0.4 * p_local_gi
    p_visitante_elo = 1 - p_local_elo
    p_visitante = 0.6 * p_visitante_elo + 0.4 * p_visitante_gi
    p_empate = max(0, 1 - p_local - p_visitante)

    favorito = equipo_local if p_local >= p_visitante else equipo_visitante
    coincide_elo_y_goalindex = (
        (elo_local > elo_visitante and goal_index_local > goal_index_visitante) or
        (elo_visitante > elo_local and goal_index_visitante > goal_index_local)
    )

    return {
        "partido": f"{equipo_local} vs {equipo_visitante}",
        "favorito": favorito,
        "confianza_alta": coincide_elo_y_goalindex,
        "prob_local_pct": round(p_local * 100, 1),
        "prob_empate_pct": round(p_empate * 100, 1),
        "prob_visitante_pct": round(p_visitante * 100, 1),
        "marcadores_probables": top_marcadores(matriz, n=3),
        "goles_esperados_local": round(lam_local, 2),
        "goles_esperados_visitante": round(lam_visitante, 2),
    }
