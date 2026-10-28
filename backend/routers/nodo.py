"""Endpoints de control de nodos individuales."""

import logging

from fastapi import APIRouter

from backend.motor_reglas import evaluar_telemetria
from backend.schemas import ControlDecision, TelemetryInput

logger = logging.getLogger("axioma_h.nodo")

router = APIRouter(prefix="/api/v1/nodo", tags=["Control de Nodos"])


@router.post("/evaluar", response_model=ControlDecision)
def evaluar_nodo(telemetria: TelemetryInput) -> ControlDecision:
    """Evalúa la telemetría de un nodo y devuelve la acción de control recomendada."""
    decision = evaluar_telemetria(telemetria)
    logger.info(
        "Evaluación de %s en modo %s: %s -> %s (caudal %.1f %%)",
        telemetria.nodo_id,
        telemetria.modo_operacion.value,
        decision.regla_activada,
        decision.accion_recomendada.value,
        decision.ajuste_caudal_pct,
    )
    return decision
