"""Modelo físico compartido por el motor de reglas y el simulador.

Contiene las ecuaciones del efecto del pulso resistivo, el costo energético y
la disponibilidad de recurso hídrico. Mantenerlas en un solo módulo garantiza
que la evaluación individual de un nodo y la simulación usen el mismo modelo.
"""

import math
from dataclasses import dataclass, replace

from backend import config


@dataclass(frozen=True)
class ParametrosModelo:
    """Parámetros supuestos del modelo que se pueden variar en un análisis de sensibilidad.

    Es inmutable: cada análisis construye su propia instancia con
    `dataclasses.replace`, en lugar de modificar `backend.config`. Así, dos
    solicitudes simultáneas no comparten estado. Los valores por defecto son
    los de `backend/config.py`.
    """

    eficacia_maxima_pulso: float = config.EFICACIA_MAXIMA_PULSO
    flujo_niebla_maximo_l_m2_h: float = config.FLUJO_NIEBLA_MAXIMO_L_M2_H


PARAMETROS_BASE = ParametrosModelo()


def parametros_desde(
    flujo_niebla_maximo_l_m2_h: float | None = None, eficacia_maxima_pulso: float | None = None
) -> ParametrosModelo:
    """Parámetros del modelo con los valores indicados y los demás de `backend/config.py`.

    Devuelve PARAMETROS_BASE si ambos valores son None; si no, una copia con
    `dataclasses.replace`, sin modificar `backend.config`. Lanza ValueError si
    un valor no es positivo o si la eficacia supera 1.
    """
    cambios: dict[str, float] = {}
    if flujo_niebla_maximo_l_m2_h is not None:
        if flujo_niebla_maximo_l_m2_h <= 0:
            raise ValueError(f"El flujo máximo de niebla debe ser positivo: {flujo_niebla_maximo_l_m2_h}")
        cambios["flujo_niebla_maximo_l_m2_h"] = flujo_niebla_maximo_l_m2_h
    if eficacia_maxima_pulso is not None:
        if not 0 < eficacia_maxima_pulso <= 1:
            raise ValueError(f"La eficacia máxima del pulso debe estar en (0, 1]: {eficacia_maxima_pulso}")
        cambios["eficacia_maxima_pulso"] = eficacia_maxima_pulso
    return replace(PARAMETROS_BASE, **cambios) if cambios else PARAMETROS_BASE


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


def eficacia_pulso(
    temperatura_alcanzada_c: float,
    impedancia_sal_ohms: float,
    *,
    parametros: ParametrosModelo = PARAMETROS_BASE,
) -> float:
    """Fracción de la impedancia salina que remueve un pulso completo.

    eta = eta_max * g(T) * Z_ref / (Z_ref + Z_sal). A mayor carga salina, menor
    fracción removida en un solo pulso.
    """
    carga = max(0.0, impedancia_sal_ohms)
    factor_carga = config.CARGA_SALINA_REFERENCIA_OHMS / (config.CARGA_SALINA_REFERENCIA_OHMS + carga)
    return parametros.eficacia_maxima_pulso * factor_temperatura_pulso(temperatura_alcanzada_c) * factor_carga


def impedancia_sal_tras_pulso(
    temperatura_alcanzada_c: float,
    impedancia_sal_ohms: float,
    *,
    parametros: ParametrosModelo = PARAMETROS_BASE,
) -> float:
    """Impedancia salina remanente al terminar el pulso: Z_sal * (1 - eta)."""
    eta = eficacia_pulso(temperatura_alcanzada_c, impedancia_sal_ohms, parametros=parametros)
    return max(0.0, impedancia_sal_ohms) * (1.0 - eta)


def tiempo_hasta_impedancia(
    temperatura_alcanzada_c: float,
    impedancia_sal_ohms: float,
    impedancia_sal_objetivo_ohms: float,
    *,
    parametros: ParametrosModelo = PARAMETROS_BASE,
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
    eta = eficacia_pulso(temperatura_alcanzada_c, impedancia_sal_ohms, parametros=parametros)
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


def tiempo_fraccion_remocion(
    temperatura_alcanzada_c: float, fraccion: float = config.FRACCION_TIEMPO_DESPRENDIMIENTO
) -> float | None:
    """Segundos que tarda el pulso en lograr la fracción indicada de su remoción total.

    Mide la cinética del desprendimiento, independiente de cuánta sal remueve
    el pulso completo:
        t_f = -tau * ln(1 - f * (1 - e^(-D/tau)))
    con tau = tau_0 / g(T) y D la duración del pulso. Devuelve None si la
    temperatura alcanzada no produce efecto de disolución (g(T) <= 0).
    """
    g = factor_temperatura_pulso(temperatura_alcanzada_c)
    if g <= 0:
        return None
    tau = config.CONSTANTE_TIEMPO_DISOLUCION_SEG / g
    duracion = float(config.DURACION_PULSO_SEG)
    return -tau * math.log(1.0 - fraccion * (1.0 - math.exp(-duracion / tau)))


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


def flujo_niebla_disponible_l_m2_h(
    humedad_relativa_pct: float, *, parametros: ParametrosModelo = PARAMETROS_BASE
) -> float:
    """Recurso hídrico atmosférico disponible por m² y hora.

    Q = Q_max * ((HR - HR_min) / (100 - HR_min))^n para HR > HR_min, y 0 en
    otro caso. Representa de forma simplificada el producto entre contenido
    de agua líquida del aire y velocidad del viento.
    """
    rango = 100.0 - config.HUMEDAD_MINIMA_CAPTACION_PCT
    relativo = (humedad_relativa_pct - config.HUMEDAD_MINIMA_CAPTACION_PCT) / rango
    if relativo <= 0:
        return 0.0
    return parametros.flujo_niebla_maximo_l_m2_h * min(1.0, relativo) ** config.EXPONENTE_CAPTACION
