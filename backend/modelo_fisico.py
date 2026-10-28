"""Modelo físico compartido por el motor de reglas y el simulador.

Contiene las ecuaciones del efecto del pulso resistivo, el costo energético y
la disponibilidad de recurso hídrico. Mantenerlas en un solo módulo garantiza
que la evaluación individual de un nodo y la simulación usen el mismo modelo.
"""

import math

from backend import config


def conductancia_relativa(impedancia_ohms: float) -> float:
    """Devuelve la conductancia hidráulica relativa a la membrana limpia.

    G = min(1, Z_nominal / Z). Una impedancia menor que la nominal se trata
    como membrana limpia.
    """
    if impedancia_ohms <= 0:
        return 1.0
    return min(1.0, config.IMPEDANCIA_NOMINAL_OHMS / impedancia_ohms)


def factor_temperatura_pulso(temperatura_alcanzada_c: float) -> float:
    """Fracción del efecto de disolución según la temperatura alcanzada.

    g(T) = (T - T_min) / (T_sat - T_min), acotado entre 0 y 1. Por encima de
    la temperatura de saturación el pulso no limpia más, solo degrada.
    """
    rango = config.TEMPERATURA_SATURACION_EFECTO_C - config.TEMPERATURA_MINIMA_EFECTO_C
    g = (temperatura_alcanzada_c - config.TEMPERATURA_MINIMA_EFECTO_C) / rango
    return max(0.0, min(1.0, g))


def eficacia_pulso(temperatura_alcanzada_c: float, impedancia_sal_ohms: float) -> float:
    """Fracción de la impedancia salina que remueve un pulso completo.

    eta = eta_max * g(T) * Z_ref / (Z_ref + Z_sal). A mayor carga salina, menor
    fracción removida en un solo pulso.
    """
    carga = max(0.0, impedancia_sal_ohms)
    factor_carga = config.CARGA_SALINA_REFERENCIA_OHMS / (config.CARGA_SALINA_REFERENCIA_OHMS + carga)
    return config.EFICACIA_MAXIMA_PULSO * factor_temperatura_pulso(temperatura_alcanzada_c) * factor_carga


def impedancia_sal_tras_pulso(temperatura_alcanzada_c: float, impedancia_sal_ohms: float) -> float:
    """Impedancia salina remanente al terminar el pulso: Z_sal * (1 - eta)."""
    eta = eficacia_pulso(temperatura_alcanzada_c, impedancia_sal_ohms)
    return max(0.0, impedancia_sal_ohms) * (1.0 - eta)


def tiempo_hasta_impedancia(
    temperatura_alcanzada_c: float,
    impedancia_sal_ohms: float,
    impedancia_sal_objetivo_ohms: float,
) -> float | None:
    """Segundos de pulso necesarios para bajar la impedancia salina al objetivo.

    Durante el pulso la remoción sigue una cinética exponencial normalizada a
    la duración del pulso:
        Z_sal(t) = Z_sal0 * [1 - eta * (1 - e^(-t/tau)) / (1 - e^(-D/tau))]
    con tau = tau_0 / g(T). Devuelve 0 si ya se cumple el objetivo y None si el
    pulso completo no lo alcanza.
    """
    if impedancia_sal_ohms <= impedancia_sal_objetivo_ohms:
        return 0.0
    if impedancia_sal_objetivo_ohms < 0:
        return None
    g = factor_temperatura_pulso(temperatura_alcanzada_c)
    eta = eficacia_pulso(temperatura_alcanzada_c, impedancia_sal_ohms)
    if g <= 0 or eta <= 0:
        return None
    fraccion_requerida = (impedancia_sal_ohms - impedancia_sal_objetivo_ohms) / impedancia_sal_ohms
    if fraccion_requerida > eta:
        return None
    tau = config.CONSTANTE_TIEMPO_DISOLUCION_SEG / g
    duracion = float(config.DURACION_PULSO_SEG)
    normalizador = 1.0 - math.exp(-duracion / tau)
    argumento = 1.0 - fraccion_requerida * normalizador / eta
    return min(duracion, -tau * math.log(argumento))


def energia_pulso_wh(incremento_temperatura_c: float) -> float:
    """Energía eléctrica de un pulso en Wh.

    E = [C * dT + G_perdidas * dT * D] / 3600, donde C es la capacidad térmica
    de la matriz, G_perdidas la conductancia de pérdidas por convección y D la
    duración del pulso. Si la matriz ya está a la temperatura objetivo, el
    costo es nulo.
    """
    delta = max(0.0, incremento_temperatura_c)
    joules = (
        config.CAPACIDAD_TERMICA_MATRIZ_J_K * delta
        + config.CONDUCTANCIA_PERDIDAS_W_K * delta * config.DURACION_PULSO_SEG
    )
    return joules / 3600.0


def flujo_niebla_disponible_l_m2_h(humedad_relativa_pct: float) -> float:
    """Recurso hídrico atmosférico disponible por m² y hora.

    Q = Q_max * ((HR - HR_min) / (100 - HR_min))^n para HR > HR_min, y 0 en
    otro caso. Representa de forma simplificada el producto entre contenido
    de agua líquida del aire y velocidad del viento.
    """
    rango = 100.0 - config.HUMEDAD_MINIMA_CAPTACION_PCT
    relativo = (humedad_relativa_pct - config.HUMEDAD_MINIMA_CAPTACION_PCT) / rango
    if relativo <= 0:
        return 0.0
    return config.FLUJO_NIEBLA_MAXIMO_L_M2_H * min(1.0, relativo) ** config.EXPONENTE_CAPTACION
