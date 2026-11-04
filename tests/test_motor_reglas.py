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
    REGLA_06,
    SIN_REGLAS_TEMPORIZADOR,
    evaluar_telemetria,
)
from backend.schemas import AccionControl, AnulacionManual, EstadoNodo, ModoOperacion, TelemetryInput

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
    assert decision.ajuste_caudal_pct == pytest.approx(0.0)


def test_regla_02_pausa_ecologica():
    decision = evaluar(humedad_relativa_pct=20.0)
    assert decision.regla_activada == REGLA_02
    assert decision.estado_nodo == EstadoNodo.PAUSA_ECOLOGICA
    assert decision.accion_recomendada == AccionControl.PAUSA_ECOLOGICA
    assert decision.pulso_termico_activo is False
    assert decision.ajuste_caudal_pct == pytest.approx(0.0)
    assert decision.metricas_conjeturas.preservacion_ecologica_ok is True


def test_regla_04_reserva_critica():
    decision = evaluar(impedancia_ohms=1800.0, reserva_calor_pct=20.0)
    assert decision.regla_activada == REGLA_04
    assert decision.estado_nodo == EstadoNodo.RESERVA_CRITICA
    assert decision.accion_recomendada == AccionControl.REDUCIR_CAUDAL_SIN_PULSO
    assert decision.pulso_termico_activo is False
    assert decision.ajuste_caudal_pct == pytest.approx(50.0)


def test_regla_03_pulso_resistivo():
    decision = evaluar(impedancia_ohms=1800.0)
    assert decision.regla_activada == REGLA_03
    assert decision.estado_nodo == EstadoNodo.CRISTALIZACION_DETECTADA
    assert decision.accion_recomendada == AccionControl.APLICAR_PULSO_RESISTIVO
    assert decision.pulso_termico_activo is True
    assert decision.temperatura_objetivo_c == pytest.approx(44.0)
    assert decision.duracion_pulso_seg == 90
    assert decision.ajuste_caudal_pct == pytest.approx(80.0)


def test_regla_05_operacion_nominal():
    decision = evaluar()
    assert decision.regla_activada == REGLA_05
    assert decision.estado_nodo == EstadoNodo.NOMINAL
    assert decision.accion_recomendada == AccionControl.FILTRACION_PASIVA_CONTINUA
    assert decision.pulso_termico_activo is False
    assert decision.ajuste_caudal_pct == pytest.approx(100.0)


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
        impedancia_ohms=1650.5,
        temperatura_celsius=36.2,
        reserva_calor_pct=55.0,
        humedad_relativa_pct=42.0,
        flujo_actual_ml_min=14.5,
        modo_operacion=ModoOperacion.NEURO_SIMBOLICO,
    )
    decision = evaluar_telemetria(telemetria)
    assert decision.regla_activada == REGLA_03
    assert decision.temperatura_objetivo_c == pytest.approx(44.0)
    assert decision.nodo_id == "NODO_04"


def test_modo_temporizador_no_evalua_reglas():
    decision = evaluar(
        impedancia_ohms=2500.0, temperatura_celsius=50.0, modo_operacion=ModoOperacion.TEMPORIZADOR_FIJO
    )
    assert decision.regla_activada == SIN_REGLAS_TEMPORIZADOR
    assert decision.accion_recomendada == AccionControl.FILTRACION_PASIVA_CONTINUA
    assert decision.ajuste_caudal_pct == pytest.approx(100.0)
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
    assert sin_pulso.metricas_conjeturas.eficiencia_energetica_pct == pytest.approx(100.0)
    assert con_pulso.metricas_conjeturas.eficiencia_energetica_pct < 100.0


def test_membrana_limpia_tiene_recuperacion_completa():
    decision = evaluar(impedancia_ohms=config.IMPEDANCIA_NOMINAL_OHMS)
    assert decision.metricas_conjeturas.recuperacion_hidraulica_pct == pytest.approx(100.0)


def test_evaluacion_determinista_con_instante_fijo():
    instante = datetime(2026, 1, 1, tzinfo=timezone.utc)
    telemetria = TelemetryInput(**{**LECTURA_NOMINAL, "impedancia_ohms": 1700.0})
    primera = evaluar_telemetria(telemetria, instante)
    segunda = evaluar_telemetria(telemetria, instante)
    assert primera == segunda


# ---------------------------------------------------------------------------
# Supervisión humana (REGLA_06)
# ---------------------------------------------------------------------------
SUSPENDER = AnulacionManual.SUSPENDER_EXTRACCION
INHIBIR = AnulacionManual.INHIBIR_PULSO
# Nombres de los argumentos parametrizados.
ANULACION = "anulacion"
CAMBIOS = "cambios"
CAMBIOS_Y_REGLA = (CAMBIOS, "regla_esperada")
INSTANTE_FIJO = datetime(2026, 1, 1, tzinfo=timezone.utc)
IMPEDANCIA_ALTA = {"impedancia_ohms": 1800.0}
RESERVA_CRITICA = {"impedancia_ohms": 1800.0, "reserva_calor_pct": 20.0}

# Lecturas que activan cada regla automática sin intervención del operador.
CASOS_POR_REGLA = [
    ({"temperatura_celsius": 47.0}, REGLA_01),
    ({"humedad_relativa_pct": 20.0}, REGLA_02),
    (RESERVA_CRITICA, REGLA_04),
    (IMPEDANCIA_ALTA, REGLA_03),
    ({}, REGLA_05),
]
LECTURAS_POR_REGLA = [cambios for cambios, _ in CASOS_POR_REGLA]


def evaluar_fijo(**cambios):
    """Evalúa una lectura nominal modificada con un instante fijo, para comparar decisiones completas."""
    return evaluar_telemetria(TelemetryInput(**{**LECTURA_NOMINAL, **cambios}), INSTANTE_FIJO)


def test_anulacion_por_defecto_es_ninguna():
    assert TelemetryInput(**LECTURA_NOMINAL).anulacion_manual is AnulacionManual.NINGUNA


@pytest.mark.parametrize(CAMBIOS_Y_REGLA, CASOS_POR_REGLA)
def test_anulacion_ninguna_conserva_la_regla(cambios, regla_esperada):
    decision = evaluar(**cambios, anulacion_manual=AnulacionManual.NINGUNA)
    assert decision.regla_activada == regla_esperada


@pytest.mark.parametrize(CAMBIOS, LECTURAS_POR_REGLA)
def test_anulacion_ninguna_conserva_la_decision_completa(cambios):
    explicita = evaluar_fijo(**cambios, anulacion_manual=AnulacionManual.NINGUNA)
    por_defecto = evaluar_fijo(**cambios)
    assert explicita == por_defecto


@pytest.mark.parametrize(CAMBIOS, [{}, IMPEDANCIA_ALTA, RESERVA_CRITICA])
def test_suspender_extraccion(cambios):
    decision = evaluar(**cambios, anulacion_manual=SUSPENDER)
    assert decision.regla_activada == REGLA_06
    assert decision.estado_nodo == EstadoNodo.SUPERVISION_HUMANA
    assert decision.accion_recomendada == AccionControl.SUSPENSION_MANUAL
    assert decision.pulso_termico_activo is False
    assert decision.duracion_pulso_seg == 0
    assert decision.ajuste_caudal_pct == pytest.approx(0.0)


@pytest.mark.parametrize((CAMBIOS, "regla_automatica"), [(IMPEDANCIA_ALTA, REGLA_03), (RESERVA_CRITICA, REGLA_04)])
def test_inhibir_pulso_con_impedancia_alta(cambios, regla_automatica):
    decision = evaluar(**cambios, anulacion_manual=INHIBIR)
    assert decision.regla_activada == REGLA_06
    assert decision.estado_nodo == EstadoNodo.SUPERVISION_HUMANA
    assert decision.accion_recomendada == AccionControl.REDUCIR_CAUDAL_SIN_PULSO
    assert decision.pulso_termico_activo is False
    assert decision.temperatura_objetivo_c is None
    assert decision.ajuste_caudal_pct == pytest.approx(config.CAUDAL_RESERVA_CRITICA_PCT)
    assert regla_automatica in decision.motivo


@pytest.mark.parametrize("impedancia", [1100.0, 1500.0])
def test_inhibir_pulso_sin_impedancia_alta_decide_regla_05(impedancia):
    decision = evaluar(impedancia_ohms=impedancia, anulacion_manual=INHIBIR)
    assert decision.regla_activada == REGLA_05


def test_motivo_identifica_al_operador_y_la_regla_automatica():
    motivo = evaluar(anulacion_manual=SUSPENDER).motivo
    assert "Decisión del operador" in motivo
    assert f"habría aplicado {REGLA_05}" in motivo


@pytest.mark.parametrize(ANULACION, list(AnulacionManual))
@pytest.mark.parametrize(
    CAMBIOS_Y_REGLA,
    [
        ({"temperatura_celsius": 45.0, **IMPEDANCIA_ALTA}, REGLA_01),
        ({"temperatura_celsius": 46.0, "humedad_relativa_pct": 10.0}, REGLA_01),
        ({"humedad_relativa_pct": 29.9, **IMPEDANCIA_ALTA}, REGLA_02),
        ({"humedad_relativa_pct": 20.0, **RESERVA_CRITICA}, REGLA_02),
    ],
)
def test_limites_termico_y_ecologico_prevalecen_sobre_la_anulacion(anulacion, cambios, regla_esperada):
    assert evaluar(**cambios, anulacion_manual=anulacion).regla_activada == regla_esperada


@pytest.mark.parametrize(ANULACION, [SUSPENDER, INHIBIR])
@pytest.mark.parametrize(CAMBIOS_Y_REGLA, CASOS_POR_REGLA)
def test_anulacion_solo_reduce_el_caudal(anulacion, cambios, regla_esperada):
    automatica = evaluar(**cambios)
    anulada = evaluar(**cambios, anulacion_manual=anulacion)
    assert automatica.regla_activada == regla_esperada
    assert anulada.ajuste_caudal_pct <= automatica.ajuste_caudal_pct


@pytest.mark.parametrize(ANULACION, [SUSPENDER, INHIBIR])
@pytest.mark.parametrize(CAMBIOS, LECTURAS_POR_REGLA)
def test_anulacion_nunca_activa_pulso(anulacion, cambios):
    decision = evaluar(**cambios, anulacion_manual=anulacion)
    assert decision.pulso_termico_activo is False


@pytest.mark.parametrize(ANULACION, list(AnulacionManual))
def test_modo_temporizador_ignora_la_anulacion(anulacion):
    decision = evaluar(
        impedancia_ohms=1800.0, modo_operacion=ModoOperacion.TEMPORIZADOR_FIJO, anulacion_manual=anulacion
    )
    assert decision.regla_activada == SIN_REGLAS_TEMPORIZADOR
