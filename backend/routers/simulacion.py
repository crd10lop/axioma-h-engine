"""Endpoints del simulador comparativo."""

import logging
import time

from fastapi import APIRouter

from backend.schemas import SimulationConfig, SimulationResult
from backend.simulador import ejecutar_simulacion

logger = logging.getLogger("axioma_h.simulacion")

router = APIRouter(prefix="/api/v1/simulacion", tags=["Simulación"])


@router.post("/ejecutar", response_model=SimulationResult)
def ejecutar(configuracion: SimulationConfig) -> SimulationResult:
    """Ejecuta la simulación comparativa entre el control neuro-simbólico y el temporizador fijo."""
    inicio = time.perf_counter()
    resultado = ejecutar_simulacion(configuracion)
    conjeturas = resultado.conjeturas_validadas
    logger.info(
        "Simulación %s de %d h con %d nodos completada en %.2f s. Conjeturas: C1=%s, C2=%s, C3=%s",
        configuracion.escenario.value,
        configuracion.duracion_horas,
        configuracion.numero_nodos,
        time.perf_counter() - inicio,
        conjeturas.conjetura_1_eficiencia,
        conjeturas.conjetura_2_autorreparacion,
        conjeturas.conjetura_3_saber_territorial,
    )
    return resultado
