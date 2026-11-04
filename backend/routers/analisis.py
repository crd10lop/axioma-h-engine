"""Endpoints del análisis de robustez: barrido de salinidad, sensibilidad e incertidumbre."""

import logging
import time

from fastapi import APIRouter

from backend.analisis import ejecutar_barrido, ejecutar_incertidumbre, ejecutar_sensibilidad
from backend.schemas import (
    BarridoConfig,
    BarridoResultado,
    IncertidumbreConfig,
    IncertidumbreResultado,
    SensibilidadConfig,
    SensibilidadResultado,
)

logger = logging.getLogger("axioma_h.analisis")

router = APIRouter(prefix="/api/v1/analisis", tags=["Análisis de robustez"])


@router.post("/barrido-salinidad")
def barrido_salinidad(configuracion: BarridoConfig) -> BarridoResultado:
    """Compara ambos modos en seis niveles de carga salina, con media y dispersión entre semillas."""
    inicio = time.perf_counter()
    resultado = ejecutar_barrido(configuracion)
    logger.info(
        "Barrido de salinidad con humedad inicial %.1f %%, %d h, %d nodos y %d semillas completado en %.2f s.",
        configuracion.humedad_ambiente_inicial_pct,
        configuracion.duracion_horas,
        configuracion.numero_nodos,
        len(configuracion.semillas),
        time.perf_counter() - inicio,
    )
    return resultado


@router.post("/sensibilidad")
def sensibilidad(configuracion: SensibilidadConfig) -> SensibilidadResultado:
    """Repite la simulación con varios valores de un parámetro supuesto, sin modificar la configuración global."""
    inicio = time.perf_counter()
    resultado = ejecutar_sensibilidad(configuracion)
    logger.info(
        "Sensibilidad de %s con %d valores en %s completada en %.2f s.",
        configuracion.parametro.value,
        len(configuracion.valores),
        configuracion.escenario.value,
        time.perf_counter() - inicio,
    )
    return resultado


@router.post("/incertidumbre")
def incertidumbre(configuracion: IncertidumbreConfig) -> IncertidumbreResultado:
    """Propaga la incertidumbre de la eficacia del pulso y del flujo de niebla, sin modificar la configuración global."""
    inicio = time.perf_counter()
    resultado = ejecutar_incertidumbre(configuracion)
    logger.info(
        "Incertidumbre con %d muestras en %s completada en %.2f s.",
        configuracion.n_muestras,
        configuracion.escenario.value,
        time.perf_counter() - inicio,
    )
    return resultado
