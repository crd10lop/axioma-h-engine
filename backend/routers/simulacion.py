"""Endpoints del simulador comparativo."""

import logging
import time

from fastapi import APIRouter

from backend.schemas import SimulationConfig, SimulationResult
from backend.simulador import ejecutar_simulacion, parametros_de_configuracion

logger = logging.getLogger("axioma_h.simulacion")

router = APIRouter(prefix="/api/v1/simulacion", tags=["Simulación"])


@router.post("/ejecutar")
def ejecutar(configuracion: SimulationConfig) -> SimulationResult:
    """Ejecuta la simulación comparativa entre el control neuro-simbólico y el temporizador fijo."""
    inicio = time.perf_counter()
    # El flujo de niebla del sitio y la eficacia del pulso se aplican sobre una copia de los parámetros.
    parametros = parametros_de_configuracion(configuracion)
    resultado = ejecutar_simulacion(configuracion, parametros=parametros)
    conjeturas = resultado.conjeturas_validadas
    logger.info(
        "Simulación %s de %d h con %d nodos completada en %.2f s (flujo %.2f L/m²/h, eficacia %.2f). "
        "Conjeturas: C1=%s, C2=%s, C3=%s",
        configuracion.escenario.value,
        configuracion.duracion_horas,
        configuracion.numero_nodos,
        time.perf_counter() - inicio,
        parametros.flujo_niebla_maximo_l_m2_h,
        parametros.eficacia_maxima_pulso,
        conjeturas.conjetura_1_eficiencia,
        conjeturas.conjetura_2_autorreparacion,
        conjeturas.conjetura_3_saber_territorial,
    )
    return resultado
