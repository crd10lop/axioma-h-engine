"""Pruebas de la estimación del impacto comunitario."""

import pytest

from backend import config
from backend.impacto import impacto_comunitario
from backend.schemas import Escenario, SimulationConfig, TasaSalinizacion
from backend.simulador import ejecutar_simulacion

MODO_NEURO = "modo_neuro_simbolico"
MODOS = (MODO_NEURO, "modo_temporizador_fijo", "modo_temporizador_tope_ecologico")
TOLERANCIA = 0.01


def _simular(escenario: Escenario, humedad: float):
    """Simulación de control: 24 h, tasa ALTA y semilla 42."""
    cfg = SimulationConfig(
        duracion_horas=24,
        escenario=escenario,
        humedad_ambiente_inicial_pct=humedad,
        tasa_salinizacion=TasaSalinizacion.ALTA,
        semilla=42,
    )
    return ejecutar_simulacion(cfg)


@pytest.fixture(scope="module")
def dia_normal_85():
    """DIA_NORMAL con humedad inicial de 85 %."""
    return _simular(Escenario.DIA_NORMAL, 85.0)


@pytest.fixture(scope="module")
def tormenta_45():
    """Corrida de referencia del PRD: TORMENTA_DE_SAL_Y_CALOR_EXTREMO con humedad inicial de 45 %."""
    return _simular(Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO, 45.0)


@pytest.fixture
def impacto_48h():
    """240 L en 48 h con 4 nodos: 120 L por día sobre 4 m²."""
    return impacto_comunitario(240.0, 48, 4)


def test_litros_por_dia_normaliza_la_duracion(impacto_48h):
    assert impacto_48h.litros_dia_red == pytest.approx(120.0)


def test_rendimiento_por_m2_usa_el_area_de_la_red(impacto_48h):
    assert impacto_48h.rendimiento_l_m2_dia == pytest.approx(120.0 / (4 * config.AREA_COLECTOR_M2))


@pytest.mark.parametrize(
    ("campo", "consumo"),
    [
        ("personas_supervivencia", config.CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA),
        ("personas_acceso_basico", config.CONSUMO_ACCESO_BASICO_L_PERSONA_DIA),
    ],
)
def test_personas_abastecidas(impacto_48h, campo, consumo):
    assert getattr(impacto_48h, campo) == pytest.approx(120.0 / consumo)


def test_area_por_persona_con_el_rendimiento_maximo_de_la_literatura(impacto_48h):
    assert impacto_48h.area_m2_por_persona_basico_literatura_min == pytest.approx(2.0)


def test_area_por_persona_con_el_rendimiento_minimo_de_la_literatura(impacto_48h):
    assert impacto_48h.area_m2_por_persona_basico_literatura_max == pytest.approx(20.0 / 3.0, abs=1e-4)


def test_valores_redondeados_a_cuatro_decimales():
    impacto = impacto_comunitario(100.0, 24, 3)
    assert impacto.rendimiento_l_m2_dia == pytest.approx(33.3333, abs=1e-9)


@pytest.mark.parametrize(("duracion_horas", "numero_nodos"), [(0, 8), (-24, 8), (24, 0), (24, -1)])
def test_duracion_o_nodos_no_positivos_lanzan_error(duracion_horas, numero_nodos):
    with pytest.raises(ValueError):
        impacto_comunitario(100.0, duracion_horas, numero_nodos)


def test_control_dia_normal_85_rendimiento(dia_normal_85):
    neuro = dia_normal_85.impacto_comunitario[MODO_NEURO]
    assert neuro.rendimiento_l_m2_dia == pytest.approx(31.83, abs=TOLERANCIA)


def test_control_dia_normal_85_personas_acceso_basico(dia_normal_85):
    neuro = dia_normal_85.impacto_comunitario[MODO_NEURO]
    assert neuro.personas_acceso_basico == pytest.approx(12.73, abs=TOLERANCIA)


def test_control_tormenta_45_litros_por_dia(tormenta_45):
    neuro = tormenta_45.impacto_comunitario[MODO_NEURO]
    assert neuro.litros_dia_red == pytest.approx(81.65, abs=TOLERANCIA)


def test_simulacion_incluye_los_tres_modos(dia_normal_85):
    assert set(dia_normal_85.impacto_comunitario) == set(MODOS)


@pytest.mark.parametrize("modo", MODOS)
def test_impacto_parte_de_los_litros_de_la_comparativa(dia_normal_85, modo):
    litros = getattr(dia_normal_85.comparativa, modo).litros_totales_agua
    assert dia_normal_85.impacto_comunitario[modo].litros_dia_red == pytest.approx(litros)


def test_tope_ecologico_reduce_las_personas_abastecidas(dia_normal_85):
    impacto = dia_normal_85.impacto_comunitario
    neuro = impacto[MODO_NEURO].personas_acceso_basico
    temporizador = impacto["modo_temporizador_fijo"].personas_acceso_basico
    assert neuro < temporizador
