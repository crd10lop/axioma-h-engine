"""Pruebas del motor de reglas neuro-simbólico."""

from datetime import datetime, timezone

import pytest

from backend import config
from backend.motor_reglas import (
    REGLA_01,
    REGLA_02,
    REGLA_03,
    REGLA_04,
    REGLA_05,
    SIN_REGLAS_TEMPORIZADOR,
    evaluar_telemetria,
)
from backend.schemas import AccionControl, EstadoNodo, ModoOperacion, TelemetryInput

LECTURA_NOMINAL = {
    "nodo_id": "NODO_01",
    "impedancia_ohms": 1100.0,
    "temperatura_celsius": 30.0,
    "reserva_calor_pct": 70.0,
    "humedad_relativa_pct": 80.0,
    "flujo_actual_ml_min": 10.0,
}


def evaluar(**cambios):
    """Evalúa una lectura nominal con los campos indicados modificados."""
    return evaluar_telemetria(TelemetryInput(**{**LECTURA_NOMINAL, **cambios}))


# ---------------------------------------------------------------------------
# Una prueba por regla
# ---------------------------------------------------------------------------
def test_regla_01_corte_termico():
    decision = evaluar(temperatura_celsius=47.0)
    assert decision.regla_activada == REGLA_01
    assert decision.estado_nodo == EstadoNodo.EMERGENCIA_TERMICA
    assert decision.accion_recomendada == AccionControl.CORTE_DE_EMERGENCIA
    assert decision.pulso_termico_activo is False
    assert decision.temperatura_objetivo_c is None
    assert decision.duracion_pulso_seg == 0
    assert decision.ajuste_caudal_pct == 0.0


def test_regla_02_pausa_ecologica():
    decision = evaluar(humedad_relativa_pct=20.0)
    assert decision.regla_activada == REGLA_02
    assert decision.estado_nodo == EstadoNodo.PAUSA_ECOLOGICA
    assert decision.accion_recomendada == AccionControl.PAUSA_ECOLOGICA
    assert decision.pulso_termico_activo is False
    assert decision.ajuste_caudal_pct == 0.0
    assert decision.metricas_conjeturas.preservacion_ecologica_ok is True


def test_regla_04_reserva_critica():
    decision = evaluar(impedancia_ohms=1800.0, reserva_calor_pct=20.0)
    assert decision.regla_activada == REGLA_04
    assert decision.estado_nodo == EstadoNodo.RESERVA_CRITICA
    assert decision.accion_recomendada == AccionControl.REDUCIR_CAUDAL_SIN_PULSO
    assert decision.pulso_termico_activo is False
    assert decision.ajuste_caudal_pct == 50.0


def test_regla_03_pulso_resistivo():
    decision = evaluar(impedancia_ohms=1800.0)
    assert decision.regla_activada == REGLA_03
    assert decision.estado_nodo == EstadoNodo.CRISTALIZACION_DETECTADA
    assert decision.accion_recomendada == AccionControl.APLICAR_PULSO_RESISTIVO
    assert decision.pulso_termico_activo is True
    assert decision.temperatura_objetivo_c == 44.0
    assert decision.duracion_pulso_seg == 90
    assert decision.ajuste_caudal_pct == 80.0


def test_regla_05_operacion_nominal():
    decision = evaluar()
    assert decision.regla_activada == REGLA_05
    assert decision.estado_nodo == EstadoNodo.NOMINAL
    assert decision.accion_recomendada == AccionControl.FILTRACION_PASIVA_CONTINUA
    assert decision.pulso_termico_activo is False
    assert decision.ajuste_caudal_pct == 100.0


# ---------------------------------------------------------------------------
# Casos límite
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cambios, regla_esperada",
    [
        ({"temperatura_celsius": 45.0}, REGLA_01),
        ({"temperatura_celsius": 44.9}, REGLA_05),
        ({"humedad_relativa_pct": 30.0}, REGLA_05),
        ({"humedad_relativa_pct": 29.9}, REGLA_02),
        ({"impedancia_ohms": 1500.0}, REGLA_05),
        ({"impedancia_ohms": 1500.1}, REGLA_03),
        ({"impedancia_ohms": 1800.0, "reserva_calor_pct": 30.0}, REGLA_03),
        ({"impedancia_ohms": 1800.0, "reserva_calor_pct": 29.9}, REGLA_04),
    ],
)
def test_casos_limite(cambios, regla_esperada):
    assert evaluar(**cambios).regla_activada == regla_esperada


# ---------------------------------------------------------------------------
# Prioridad entre reglas
# ---------------------------------------------------------------------------
def test_corte_termico_prevalece_sobre_todas():
    decision = evaluar(
        temperatura_celsius=50.0, humedad_relativa_pct=10.0, impedancia_ohms=2500.0, reserva_calor_pct=5.0
    )
    assert decision.regla_activada == REGLA_01


def test_pausa_ecologica_prevalece_sobre_impedancia_y_reserva():
    decision = evaluar(humedad_relativa_pct=15.0, impedancia_ohms=2500.0, reserva_calor_pct=5.0)
    assert decision.regla_activada == REGLA_02
    decision = evaluar(humedad_relativa_pct=15.0, impedancia_ohms=2500.0)
    assert decision.regla_activada == REGLA_02


def test_reserva_critica_prevalece_sobre_pulso():
    decision = evaluar(impedancia_ohms=2500.0, reserva_calor_pct=10.0)
    assert decision.regla_activada == REGLA_04
    assert decision.pulso_termico_activo is False


def test_reserva_baja_sin_impedancia_alta_es_nominal():
    assert evaluar(reserva_calor_pct=5.0).regla_activada == REGLA_05


# ---------------------------------------------------------------------------
# Payload del PRD y modo temporizador
# ---------------------------------------------------------------------------
def test_payload_prd_activa_regla_03():
    telemetria = TelemetryInput(
        nodo_id="NODO_04",
        impedancia_ohms=1850.5,
        temperatura_celsius=38.2,
        reserva_calor_pct=65.0,
        humedad_relativa_pct=82.0,
        flujo_actual_ml_min=12.5,
        modo_operacion=ModoOperacion.NEURO_SIMBOLICO,
    )
    decision = evaluar_telemetria(telemetria)
    assert decision.regla_activada == REGLA_03
    assert decision.temperatura_objetivo_c == 44.0
    assert decision.nodo_id == "NODO_04"


def test_modo_temporizador_no_evalua_reglas():
    decision = evaluar(
        impedancia_ohms=2500.0, temperatura_celsius=50.0, modo_operacion=ModoOperacion.TEMPORIZADOR_FIJO
    )
    assert decision.regla_activada == SIN_REGLAS_TEMPORIZADOR
    assert decision.accion_recomendada == AccionControl.FILTRACION_PASIVA_CONTINUA
    assert decision.ajuste_caudal_pct == 100.0
    assert decision.pulso_termico_activo is False
    assert "no evalúa sensores" in decision.motivo
    assert decision.metricas_conjeturas.preservacion_ecologica_ok is False


# ---------------------------------------------------------------------------
# Métricas y determinismo
# ---------------------------------------------------------------------------
def test_metricas_acotadas_y_pulso_mejora_recuperacion():
    con_pulso = evaluar(impedancia_ohms=1800.0)
    sin_pulso = evaluar(impedancia_ohms=1800.0, reserva_calor_pct=10.0)
    for decision in (con_pulso, sin_pulso):
        metricas = decision.metricas_conjeturas
        assert 0.0 <= metricas.recuperacion_hidraulica_pct <= 100.0
        assert 0.0 <= metricas.eficiencia_energetica_pct <= 100.0
    assert con_pulso.metricas_conjeturas.recuperacion_hidraulica_pct > (
        sin_pulso.metricas_conjeturas.recuperacion_hidraulica_pct
    )
    assert sin_pulso.metricas_conjeturas.eficiencia_energetica_pct == 100.0
    assert con_pulso.metricas_conjeturas.eficiencia_energetica_pct < 100.0


def test_membrana_limpia_tiene_recuperacion_completa():
    decision = evaluar(impedancia_ohms=config.IMPEDANCIA_NOMINAL_OHMS)
    assert decision.metricas_conjeturas.recuperacion_hidraulica_pct == 100.0


def test_evaluacion_determinista_con_instante_fijo():
    instante = datetime(2026, 1, 1, tzinfo=timezone.utc)
    telemetria = TelemetryInput(**{**LECTURA_NOMINAL, "impedancia_ohms": 1700.0})
    assert evaluar_telemetria(telemetria, instante) == evaluar_telemetria(telemetria, instante)
