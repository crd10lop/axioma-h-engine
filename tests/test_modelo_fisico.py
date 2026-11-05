"""Pruebas de los casos límite del modelo físico."""

import pytest

from backend import config
from backend.modelo_fisico import (
    PARAMETROS_BASE,
    ParametrosModelo,
    conductancia_relativa,
    flujo_niebla_disponible_l_m2_h,
    parametros_desde,
    tiempo_fraccion_remocion,
    tiempo_hasta_impedancia,
)


@pytest.mark.parametrize("impedancia", [0.0, -50.0])
def test_conductancia_con_impedancia_no_positiva_es_la_de_membrana_limpia(impedancia):
    assert conductancia_relativa(impedancia) == pytest.approx(1.0)


def test_conductancia_relativa_acotada_y_proporcional():
    assert conductancia_relativa(config.IMPEDANCIA_NOMINAL_OHMS / 2) == pytest.approx(1.0)
    assert conductancia_relativa(config.IMPEDANCIA_NOMINAL_OHMS * 2) == pytest.approx(0.5)


@pytest.mark.parametrize("impedancia_sal", [80.0, 100.0])
def test_tiempo_nulo_si_el_objetivo_ya_se_cumple(impedancia_sal):
    assert tiempo_hasta_impedancia(config.TEMPERATURA_OBJETIVO_PULSO_C, impedancia_sal, 100.0) == pytest.approx(0.0)


@pytest.mark.parametrize("temperatura", [config.TEMPERATURA_MINIMA_EFECTO_C, 25.0])
def test_pulso_sin_efecto_termico_no_alcanza_el_objetivo(temperatura):
    assert tiempo_hasta_impedancia(temperatura, 500.0, 100.0) is None


@pytest.mark.parametrize("humedad", [config.HUMEDAD_MINIMA_CAPTACION_PCT, 10.0, 0.0])
def test_sin_recurso_hidrico_bajo_la_humedad_minima(humedad):
    assert flujo_niebla_disponible_l_m2_h(humedad) == pytest.approx(0.0)


def test_recurso_hidrico_maximo_con_aire_saturado():
    assert flujo_niebla_disponible_l_m2_h(100.0) == pytest.approx(config.FLUJO_NIEBLA_MAXIMO_L_M2_H)


def test_tiempo_fraccion_remocion_a_44_grados():
    assert tiempo_fraccion_remocion(config.TEMPERATURA_OBJETIVO_PULSO_C) == pytest.approx(64.4, abs=0.1)


@pytest.mark.parametrize("temperatura", [config.TEMPERATURA_MINIMA_EFECTO_C, 25.0])
def test_tiempo_fraccion_remocion_sin_efecto_termico(temperatura):
    assert tiempo_fraccion_remocion(temperatura) is None


def test_tiempo_fraccion_remocion_crece_con_la_fraccion():
    t50 = tiempo_fraccion_remocion(config.TEMPERATURA_OBJETIVO_PULSO_C, fraccion=0.5)
    t95 = tiempo_fraccion_remocion(config.TEMPERATURA_OBJETIVO_PULSO_C)
    assert t50 < t95
    assert t95 < config.DURACION_PULSO_SEG


def test_parametros_desde_sin_valores_devuelve_los_parametros_base():
    assert parametros_desde() is PARAMETROS_BASE


@pytest.mark.parametrize(
    ("flujo", "eficacia", "esperado"),
    [
        (1.83, None, ParametrosModelo(flujo_niebla_maximo_l_m2_h=1.83)),
        (None, 0.8, ParametrosModelo(eficacia_maxima_pulso=0.8)),
        (0.49, 1.0, ParametrosModelo(eficacia_maxima_pulso=1.0, flujo_niebla_maximo_l_m2_h=0.49)),
    ],
)
def test_parametros_desde_con_valores(flujo, eficacia, esperado):
    assert parametros_desde(flujo, eficacia) == esperado


def test_parametros_desde_no_modifica_los_parametros_base():
    parametros_desde(0.5, 0.5)
    assert PARAMETROS_BASE == ParametrosModelo()
    assert config.FLUJO_NIEBLA_MAXIMO_L_M2_H == pytest.approx(6.0)


@pytest.mark.parametrize(
    ("flujo", "eficacia", "mensaje"),
    [
        (0.0, None, "flujo"),
        (-1.0, None, "flujo"),
        (None, 0.0, "eficacia"),
        (None, -0.1, "eficacia"),
        (None, 1.01, "eficacia"),
    ],
)
def test_parametros_desde_rechaza_valores_invalidos(flujo, eficacia, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        parametros_desde(flujo, eficacia)
