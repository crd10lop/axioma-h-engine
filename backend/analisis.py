"""Análisis de robustez del modelo: barrido de salinidad y sensibilidad a parámetros supuestos.

Ningún análisis modifica `backend.config`. El barrido usa los parámetros base
y la sensibilidad construye una instancia inmutable de `ParametrosModelo` por
cada valor, de modo que solicitudes simultáneas en el servidor no comparten
estado. Las corridas individuales se guardan en una caché LRU cuyas claves son
valores inmutables (enumerados, números y `ParametrosModelo`).
"""

import statistics
from dataclasses import replace
from functools import lru_cache

from backend.modelo_fisico import PARAMETROS_BASE, ParametrosModelo
from backend.schemas import (
    BarridoConfig,
    BarridoResultado,
    ConjeturasValidadas,
    Escenario,
    ParametroSensible,
    PuntoBarrido,
    PuntoSensibilidad,
    SensibilidadConfig,
    SensibilidadResultado,
    SimulationConfig,
    TasaSalinizacion,
)
from backend.simulador import ejecutar_simulacion_detallada, tasa_incrustacion_base, verificar_conjeturas

# Combinaciones del barrido: forman un gradiente de carga salina de 20 a 240 Ohm por L/m².
ESCENARIOS_BARRIDO = (Escenario.DIA_NORMAL, Escenario.INCRUSTACION_SALINA_RAPIDA)
TASAS_BARRIDO = (TasaSalinizacion.BAJA, TasaSalinizacion.MEDIA, TasaSalinizacion.ALTA)

# Campo de ParametrosModelo que corresponde a cada parámetro sensible.
CAMPO_PARAMETRO = {
    ParametroSensible.EFICACIA_MAXIMA_PULSO: "eficacia_maxima_pulso",
    ParametroSensible.FLUJO_NIEBLA_MAXIMO: "flujo_niebla_maximo_l_m2_h",
}

_TAMANO_CACHE = 64
_DECIMALES = 4


# ---------------------------------------------------------------------------
# Barrido de salinidad
# ---------------------------------------------------------------------------
@lru_cache(maxsize=_TAMANO_CACHE)
def _metricas_corrida(
    escenario: Escenario,
    tasa: TasaSalinizacion,
    humedad: float,
    duracion_horas: int,
    numero_nodos: int,
    semilla: int,
) -> tuple[float | None, float | None, float, float]:
    """Recuperación y degradación de ambos modos en una corrida con los parámetros base.

    Devuelve una tupla inmutable (recuperación neuro, recuperación temporizador,
    degradación neuro, degradación temporizador). La recuperación es nula si el
    modo no ejecutó pulsos.
    """
    cfg = SimulationConfig(
        duracion_horas=duracion_horas,
        escenario=escenario,
        humedad_ambiente_inicial_pct=humedad,
        tasa_salinizacion=tasa,
        numero_nodos=numero_nodos,
        semilla=semilla,
    )
    _, neuro, temporizador = ejecutar_simulacion_detallada(cfg)
    return (
        _media(neuro.recuperaciones_pct),
        _media(temporizador.recuperaciones_pct),
        100.0 - neuro.integridad_final_promedio,
        100.0 - temporizador.integridad_final_promedio,
    )


def _media(valores: list[float]) -> float | None:
    """Media aritmética, o None si no hay valores."""
    return statistics.fmean(valores) if valores else None


def _estadisticos(valores: list[float | None]) -> tuple[float | None, float | None]:
    """Media y desviación estándar muestral de los valores con datos.

    Con un solo dato la desviación es 0.0; sin datos, ambas son None.
    """
    datos = [valor for valor in valores if valor is not None]
    if not datos:
        return None, None
    desviacion = statistics.stdev(datos) if len(datos) >= 2 else 0.0
    return round(statistics.fmean(datos), _DECIMALES), round(desviacion, _DECIMALES)


def _reduccion_desgaste(degradacion_neuro: float | None, degradacion_temporizador: float | None) -> float | None:
    """(D_temp - D_neuro) / D_temp * 100, o None si el temporizador no se degrada."""
    if degradacion_neuro is None or degradacion_temporizador is None or degradacion_temporizador <= 0:
        return None
    return round((degradacion_temporizador - degradacion_neuro) / degradacion_temporizador * 100.0, _DECIMALES)


def _punto_barrido(cfg: BarridoConfig, escenario: Escenario, tasa: TasaSalinizacion) -> PuntoBarrido:
    """Agrega las corridas de todas las semillas para una combinación de escenario y tasa."""
    corridas = [
        _metricas_corrida(
            escenario, tasa, cfg.humedad_ambiente_inicial_pct, cfg.duracion_horas, cfg.numero_nodos, semilla
        )
        for semilla in cfg.semillas
    ]
    rec_neuro, rec_temp, deg_neuro, deg_temp = (list(columna) for columna in zip(*corridas))
    recuperacion_neuro = _estadisticos(rec_neuro)
    recuperacion_temporizador = _estadisticos(rec_temp)
    degradacion_neuro = _estadisticos(deg_neuro)
    degradacion_temporizador = _estadisticos(deg_temp)
    return PuntoBarrido(
        escenario=escenario,
        tasa_salinizacion=tasa,
        carga_salina_ohm_l_m2=tasa_incrustacion_base(escenario, tasa),
        n_semillas=len(cfg.semillas),
        recuperacion_neuro_media=recuperacion_neuro[0],
        recuperacion_neuro_desv=recuperacion_neuro[1],
        recuperacion_temporizador_media=recuperacion_temporizador[0],
        recuperacion_temporizador_desv=recuperacion_temporizador[1],
        degradacion_neuro_media=degradacion_neuro[0],
        degradacion_neuro_desv=degradacion_neuro[1],
        degradacion_temporizador_media=degradacion_temporizador[0],
        degradacion_temporizador_desv=degradacion_temporizador[1],
        reduccion_desgaste_pct=_reduccion_desgaste(degradacion_neuro[0], degradacion_temporizador[0]),
    )


def ejecutar_barrido(cfg: BarridoConfig) -> BarridoResultado:
    """Barrido de salinidad: DIA_NORMAL e INCRUSTACION_SALINA_RAPIDA con tasas BAJA, MEDIA y ALTA.

    Cada combinación se simula una vez por semilla con los parámetros base, y
    se reportan la media y la desviación estándar muestral de la recuperación
    tras pulso y de la degradación acumulada de ambos modos. Los puntos se
    ordenan por carga salina creciente.
    """
    puntos = [_punto_barrido(cfg, escenario, tasa) for escenario in ESCENARIOS_BARRIDO for tasa in TASAS_BARRIDO]
    return BarridoResultado(puntos=sorted(puntos, key=lambda punto: punto.carga_salina_ohm_l_m2))


# ---------------------------------------------------------------------------
# Sensibilidad a parámetros supuestos
# ---------------------------------------------------------------------------
@lru_cache(maxsize=_TAMANO_CACHE)
def _corrida_sensibilidad(
    escenario: Escenario,
    humedad: float,
    tasa: TasaSalinizacion,
    duracion_horas: int,
    semilla: int,
    parametros: ParametrosModelo,
) -> tuple[bool, bool, bool, float | None, float | None, float | None, float]:
    """Estado de las conjeturas e indicadores principales de una corrida con los parámetros dados.

    Devuelve una tupla inmutable (C1, C2, C3, recuperación, tiempo de
    regeneración, rendimiento nocturno, litros neuro-simbólicos).
    """
    cfg = SimulationConfig(
        duracion_horas=duracion_horas,
        escenario=escenario,
        humedad_ambiente_inicial_pct=humedad,
        tasa_salinizacion=tasa,
        semilla=semilla,
    )
    entorno, neuro, temporizador = ejecutar_simulacion_detallada(cfg, parametros=parametros)
    detalle = verificar_conjeturas(neuro, temporizador, entorno.numero_nodos)
    c1 = detalle.conjetura_1_eficiencia
    c2 = detalle.conjetura_2_autorreparacion
    c3 = detalle.conjetura_3_saber_territorial
    return (
        c1.validada,
        c2.validada,
        c3.validada,
        c1.indicadores["recuperacion_caudal_promedio_pct"].valor,
        c2.indicadores["tiempo_regeneracion_promedio_seg"].valor,
        c3.indicadores["rendimiento_nocturno_l_m2_noche"].valor,
        round(neuro.litros_totales, 3),
    )


def _punto_sensibilidad(cfg: SensibilidadConfig, valor: float) -> PuntoSensibilidad:
    """Simula un valor del parámetro sensible sin modificar la configuración global."""
    parametros = replace(PARAMETROS_BASE, **{CAMPO_PARAMETRO[cfg.parametro]: valor})
    c1, c2, c3, recuperacion, regeneracion, rendimiento, litros = _corrida_sensibilidad(
        cfg.escenario,
        cfg.humedad_ambiente_inicial_pct,
        cfg.tasa_salinizacion,
        cfg.duracion_horas,
        cfg.semilla,
        parametros,
    )
    return PuntoSensibilidad(
        valor=valor,
        conjeturas_validadas=ConjeturasValidadas(
            conjetura_1_eficiencia=c1,
            conjetura_2_autorreparacion=c2,
            conjetura_3_saber_territorial=c3,
        ),
        recuperacion_caudal_promedio_pct=recuperacion,
        tiempo_regeneracion_promedio_seg=regeneracion,
        rendimiento_nocturno_l_m2_noche=rendimiento,
        litros_neuro=litros,
    )


def ejecutar_sensibilidad(cfg: SensibilidadConfig) -> SensibilidadResultado:
    """Repite la simulación con cada valor del parámetro elegido y los demás parámetros base."""
    return SensibilidadResultado(
        parametro=cfg.parametro,
        puntos=[_punto_sensibilidad(cfg, valor) for valor in cfg.valores],
    )
