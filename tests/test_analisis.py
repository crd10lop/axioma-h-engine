"""Pruebas del análisis de robustez: barrido de salinidad y sensibilidad."""

import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from backend import analisis, config
from backend.modelo_fisico import PARAMETROS_BASE, ParametrosModelo
from backend.schemas import (
    BarridoConfig,
    Escenario,
    ParametroSensible,
    SensibilidadConfig,
    SimulationConfig,
    TasaSalinizacion,
)
from backend.simulador import ejecutar_simulacion

EFICACIA = ParametroSensible.EFICACIA_MAXIMA_PULSO
FLUJO = ParametroSensible.FLUJO_NIEBLA_MAXIMO


def _sensibilidad(parametro=EFICACIA, valores=(0.90,), **cambios):
    """Configuración de sensibilidad en DIA_NORMAL con humedad inicial de 85 % y tasa ALTA."""
    datos = {
        "escenario": Escenario.DIA_NORMAL,
        "humedad_ambiente_inicial_pct": 85.0,
        "tasa_salinizacion": TasaSalinizacion.ALTA,
        "parametro": parametro,
        "valores": list(valores),
    }
    datos.update(cambios)
    return SensibilidadConfig(**datos)


def _configuracion_global() -> dict:
    """Copia de todas las constantes de backend/config.py."""
    return {nombre: copy.deepcopy(getattr(config, nombre)) for nombre in dir(config) if nombre.isupper()}


@pytest.fixture(scope="module")
def barrido():
    """Barrido con semilla 42 y humedad inicial de 85 %, como en README."""
    return analisis.ejecutar_barrido(BarridoConfig())


@pytest.fixture(scope="module")
def sensibilidad_eficacia():
    """Sensibilidad a la eficacia del pulso con los valores de modelo_simulacion 5.6 y 5.7."""
    return analisis.ejecutar_sensibilidad(_sensibilidad(valores=(0.90, 0.94, 0.97)))


# ---------------------------------------------------------------------------
# Barrido de salinidad
# ---------------------------------------------------------------------------
def test_barrido_ordenado_por_carga_salina(barrido):
    cargas = [punto.carga_salina_ohm_l_m2 for punto in barrido.puntos]
    assert cargas == pytest.approx([20.0, 40.0, 60.0, 80.0, 120.0, 240.0])


def test_barrido_carga_baja_reproduce_readme(barrido):
    punto = barrido.puntos[0]
    assert punto.escenario == Escenario.DIA_NORMAL
    assert punto.tasa_salinizacion == TasaSalinizacion.BAJA
    assert punto.recuperacion_neuro_media == pytest.approx(88.85, abs=0.01)
    assert punto.recuperacion_temporizador_media == pytest.approx(95.84, abs=0.01)
    assert punto.degradacion_neuro_media == pytest.approx(0.020, abs=0.01)
    assert punto.degradacion_temporizador_media == pytest.approx(2.071, abs=0.01)


def test_barrido_carga_alta_reproduce_readme(barrido):
    punto = barrido.puntos[-1]
    assert punto.escenario == Escenario.INCRUSTACION_SALINA_RAPIDA
    assert punto.tasa_salinizacion == TasaSalinizacion.ALTA
    assert punto.recuperacion_neuro_media == pytest.approx(85.92, abs=0.01)
    assert punto.recuperacion_temporizador_media == pytest.approx(63.21, abs=0.01)
    assert punto.degradacion_neuro_media == pytest.approx(1.073, abs=0.01)
    assert punto.degradacion_temporizador_media == pytest.approx(4.117, abs=0.01)


def test_barrido_con_una_semilla_tiene_dispersion_nula(barrido):
    for punto in barrido.puntos:
        assert punto.n_semillas == 1
        assert punto.degradacion_neuro_desv == pytest.approx(0.0)
        assert punto.degradacion_temporizador_desv == pytest.approx(0.0)


def test_barrido_reduccion_del_desgaste(barrido):
    punto = barrido.puntos[0]
    esperado = (
        (punto.degradacion_temporizador_media - punto.degradacion_neuro_media)
        / punto.degradacion_temporizador_media
        * 100.0
    )
    assert punto.reduccion_desgaste_pct == pytest.approx(esperado, abs=0.01)


def test_barrido_con_varias_semillas_reporta_dispersion():
    resultado = analisis.ejecutar_barrido(BarridoConfig(semillas=[1, 2], duracion_horas=6, numero_nodos=2))
    for punto in resultado.puntos:
        assert punto.n_semillas == 2
        assert punto.degradacion_temporizador_desv is not None
        assert punto.degradacion_temporizador_desv >= 0.0


def test_barrido_sin_pulsos_reporta_recuperacion_nula():
    # Con humedad 0 % no hay captación ni sal, de modo que el neuro-simbólico no pulsa.
    resultado = analisis.ejecutar_barrido(BarridoConfig(humedad_ambiente_inicial_pct=0.0, duracion_horas=1, numero_nodos=1))
    punto = resultado.puntos[0]
    assert punto.recuperacion_neuro_media is None
    assert punto.recuperacion_neuro_desv is None


def test_estadisticos():
    media, desviacion = analisis._estadisticos([1.0, None, 3.0])
    assert media == pytest.approx(2.0)
    assert desviacion == pytest.approx(1.4142, abs=1e-4)


def test_estadisticos_sin_datos():
    assert analisis._estadisticos([None, None]) == (None, None)


@pytest.mark.parametrize(
    ("neuro", "temporizador"),
    [(None, 2.0), (0.1, None), (0.0, 0.0)],
)
def test_reduccion_desgaste_no_calculable(neuro, temporizador):
    assert analisis._reduccion_desgaste(neuro, temporizador) is None


def test_barrido_usa_la_cache():
    cfg = BarridoConfig(duracion_horas=1, numero_nodos=1, semillas=[7])
    analisis.ejecutar_barrido(cfg)
    aciertos_previos = analisis._metricas_corrida.cache_info().hits
    analisis.ejecutar_barrido(cfg)
    aciertos = analisis._metricas_corrida.cache_info().hits
    assert aciertos - aciertos_previos == 6


# ---------------------------------------------------------------------------
# Sensibilidad
# ---------------------------------------------------------------------------
def test_sensibilidad_eficacia_090_no_valida_c1(sensibilidad_eficacia):
    punto = sensibilidad_eficacia.puntos[0]
    assert punto.valor == pytest.approx(0.90)
    assert punto.conjeturas_validadas.conjetura_1_eficiencia is False


def test_sensibilidad_eficacia_094_valida_c1(sensibilidad_eficacia):
    punto = sensibilidad_eficacia.puntos[1]
    assert punto.conjeturas_validadas.conjetura_1_eficiencia is True
    assert punto.recuperacion_caudal_promedio_pct == pytest.approx(90.12, abs=0.01)


def test_sensibilidad_eficacia_097_valida_c2(sensibilidad_eficacia):
    punto = sensibilidad_eficacia.puntos[2]
    assert punto.conjeturas_validadas.conjetura_2_autorreparacion is True
    assert punto.tiempo_regeneracion_promedio_seg < config.TIEMPO_REGENERACION_MAX_SEG


def test_sensibilidad_con_valor_base_reproduce_la_simulacion(sensibilidad_eficacia):
    punto = sensibilidad_eficacia.puntos[0]
    assert punto.litros_neuro == pytest.approx(254.603)
    assert punto.rendimiento_nocturno_l_m2_noche == pytest.approx(16.97, abs=0.01)


def test_sensibilidad_flujo_de_niebla_cambia_el_agua_captada():
    resultado = analisis.ejecutar_sensibilidad(_sensibilidad(FLUJO, (3.0, 6.0), duracion_horas=12))
    assert resultado.parametro == FLUJO
    assert resultado.puntos[0].litros_neuro < resultado.puntos[1].litros_neuro


def test_la_configuracion_global_no_cambia_tras_los_analisis():
    antes = _configuracion_global()
    analisis.ejecutar_sensibilidad(_sensibilidad(EFICACIA, (0.5, 1.0), duracion_horas=2))
    analisis.ejecutar_sensibilidad(_sensibilidad(FLUJO, (1.0, 20.0), duracion_horas=2))
    analisis.ejecutar_barrido(BarridoConfig(duracion_horas=2, numero_nodos=1, semillas=[3]))
    despues = _configuracion_global()
    assert despues == antes
    assert PARAMETROS_BASE == ParametrosModelo()


def test_analisis_simultaneos_no_alteran_simulaciones_base():
    # Sensibilidades con valores extremos en paralelo con simulaciones base: si los
    # análisis modificaran la configuración global, las simulaciones base cambiarían.
    cfg = SimulationConfig(
        duracion_horas=6, escenario=Escenario.DIA_NORMAL, humedad_ambiente_inicial_pct=85.0,
        tasa_salinizacion=TasaSalinizacion.ALTA,
    )
    referencia = ejecutar_simulacion(cfg).model_dump()
    with ThreadPoolExecutor(max_workers=4) as ejecutor:
        tareas_analisis = [
            ejecutor.submit(analisis.ejecutar_sensibilidad, _sensibilidad(EFICACIA, (valor,), duracion_horas=6))
            for valor in (0.1, 0.3, 0.6, 1.0)
        ]
        tareas_base = [ejecutor.submit(ejecutar_simulacion, cfg) for _ in range(4)]
        for tarea in tareas_analisis:
            tarea.result()
        resultados_base = [tarea.result().model_dump() for tarea in tareas_base]
    for resultado in resultados_base:
        assert resultado == referencia


# ---------------------------------------------------------------------------
# Validación de las configuraciones
# ---------------------------------------------------------------------------
def test_semillas_repetidas_se_rechazan():
    with pytest.raises(ValidationError, match="no deben repetirse"):
        BarridoConfig(semillas=[1, 1])


@pytest.mark.parametrize("semillas", [[], [1, 2, 3, 4, 5, 6]])
def test_numero_de_semillas_fuera_de_rango(semillas):
    with pytest.raises(ValidationError):
        BarridoConfig(semillas=semillas)


@pytest.mark.parametrize(
    ("parametro", "valor"),
    [(EFICACIA, 0.0), (EFICACIA, 1.01), (EFICACIA, -0.2), (FLUJO, 0.0), (FLUJO, 20.5)],
)
def test_valores_de_sensibilidad_fuera_de_rango(parametro, valor):
    with pytest.raises(ValidationError, match="Valores fuera de"):
        _sensibilidad(parametro, (valor,))


@pytest.mark.parametrize(("parametro", "valor"), [(EFICACIA, 1.0), (FLUJO, 20.0)])
def test_limite_superior_incluido(parametro, valor):
    assert _sensibilidad(parametro, (valor,)).valores == pytest.approx([valor])


def test_demasiados_valores_de_sensibilidad():
    with pytest.raises(ValidationError):
        _sensibilidad(EFICACIA, [0.5] * 12)
