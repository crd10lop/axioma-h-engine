"""Pruebas del simulador comparativo."""

import pytest

from backend import config
from backend.modelo_fisico import tiempo_hasta_impedancia
from backend.schemas import Escenario, SimulationConfig, TasaSalinizacion
from backend.simulador import ejecutar_simulacion, ejecutar_simulacion_detallada


def configuracion(escenario=Escenario.DIA_NORMAL, **cambios):
    """Configuración base de 24 h con 8 nodos y semilla 42."""
    datos = {
        "duracion_horas": 24,
        "escenario": escenario,
        "humedad_ambiente_inicial_pct": 85.0,
        "tasa_salinizacion": TasaSalinizacion.ALTA,
    }
    datos.update(cambios)
    return SimulationConfig(**datos)


@pytest.fixture(scope="module")
def corridas():
    """Diagnósticos detallados de los cinco escenarios."""
    return {escenario: ejecutar_simulacion_detallada(configuracion(escenario)) for escenario in Escenario}


def test_reproducibilidad_con_misma_semilla():
    cfg = configuracion(Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO)
    assert ejecutar_simulacion(cfg).model_dump() == ejecutar_simulacion(cfg).model_dump()


def test_semilla_distinta_cambia_el_entorno():
    a = ejecutar_simulacion(configuracion(semilla=1))
    b = ejecutar_simulacion(configuracion(semilla=2))
    assert a.series_temporales != b.series_temporales


@pytest.mark.parametrize("escenario", list(Escenario))
def test_neuro_simbolico_nunca_supera_45_por_pulso(corridas, escenario):
    _, neuro, _ = corridas[escenario]
    assert all(t < config.UMBRAL_TEMPERATURA_CORTE_C for t in neuro.temperaturas_pulso_c)
    assert neuro.perdida_termica_pulso_pct == 0.0


@pytest.mark.parametrize("escenario", list(Escenario))
def test_neuro_simbolico_no_extrae_con_humedad_baja(corridas, escenario):
    _, neuro, _ = corridas[escenario]
    assert neuro.pasos_extraccion_humedad_baja == 0
    assert neuro.fraccion_maxima_extraida <= config.FRACCION_MAXIMA_EXTRACCION + 1e-9


def test_sequia_activa_la_pausa_ecologica(corridas):
    _, neuro, temporizador = corridas[Escenario.SEQUIA]
    assert any(e.regla_activada == "REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL" for e in neuro.bitacora)
    assert temporizador.pasos_extraccion_humedad_baja > 0


@pytest.mark.parametrize("escenario", list(Escenario))
def test_integridad_acotada(corridas, escenario):
    _, neuro, temporizador = corridas[escenario]
    for diag in (neuro, temporizador):
        assert all(0.0 <= v <= 100.0 for v in diag.integridad_promedio)
        assert 0.0 <= diag.integridad_minima <= 100.0


@pytest.mark.parametrize("escenario", list(Escenario))
def test_cada_escenario_se_ejecuta(escenario):
    resultado = ejecutar_simulacion(configuracion(escenario))
    assert len(resultado.series_temporales) == 24 * 60 // 5
    assert resultado.comparativa.modo_neuro_simbolico.litros_totales_agua >= 0


@pytest.mark.parametrize("escenario", list(Escenario))
def test_conjeturas_se_derivan_de_indicadores(escenario):
    resultado = ejecutar_simulacion(configuracion(escenario))
    detalle = resultado.detalle_verificacion
    validadas = resultado.conjeturas_validadas
    for nombre in ("conjetura_1_eficiencia", "conjetura_2_autorreparacion", "conjetura_3_saber_territorial"):
        verificacion = getattr(detalle, nombre)
        assert verificacion.validada == all(i.cumple for i in verificacion.indicadores.values())
        assert getattr(validadas, nombre) == verificacion.validada


def test_criterio_regeneracion_exige_volver_a_1100_ohm():
    objetivo_sal = config.FACTOR_IMPEDANCIA_REGENERADA * config.IMPEDANCIA_NOMINAL_OHMS - config.IMPEDANCIA_NOMINAL_OHMS
    assert objetivo_sal == pytest.approx(100.0)
    # Con 505 Ohm de carga salina, cruzar el umbral de 1500 Ohm es casi inmediato,
    # pero el criterio de 1100 Ohm no se alcanza en un solo pulso.
    assert tiempo_hasta_impedancia(44.0, 505.0, 500.0) < 5.0
    assert tiempo_hasta_impedancia(44.0, 505.0, objetivo_sal) is None
    assert tiempo_hasta_impedancia(44.0, 150.0, objetivo_sal) <= config.DURACION_PULSO_SEG


@pytest.mark.parametrize("escenario", list(Escenario))
def test_cada_pulso_neuro_genera_un_evento_de_regeneracion(corridas, escenario):
    _, neuro, _ = corridas[escenario]
    assert neuro.pulsos_regenerados + neuro.pulsos_no_regenerados == neuro.pulsos
    assert len(neuro.tiempos_regeneracion_seg) == neuro.pulsos


@pytest.mark.parametrize("escenario", list(Escenario))
def test_pulsos_no_regenerados_duran_al_menos_un_pulso(corridas, escenario):
    _, neuro, _ = corridas[escenario]
    tiempos = sorted(neuro.tiempos_regeneracion_seg)
    assert all(t <= config.DURACION_PULSO_SEG for t in tiempos[: neuro.pulsos_regenerados])
    assert all(t >= config.DURACION_PULSO_SEG for t in tiempos[neuro.pulsos_regenerados :])


@pytest.mark.parametrize("escenario", list(Escenario))
def test_indicadores_informativos_de_conjetura_2(corridas, escenario):
    _, neuro, _ = corridas[escenario]
    detalle = ejecutar_simulacion(configuracion(escenario)).detalle_verificacion
    informativos = detalle.conjetura_2_autorreparacion.indicadores_informativos
    assert informativos == {"pulsos_regenerados": neuro.pulsos_regenerados, "pulsos_totales": neuro.pulsos}
    assert detalle.conjetura_1_eficiencia.indicadores_informativos == {}
    assert detalle.conjetura_3_saber_territorial.indicadores_informativos == {}
    # Los informativos no forman parte de los indicadores que deciden la validación.
    assert not set(informativos) & set(detalle.conjetura_2_autorreparacion.indicadores)


def test_bitacora_registra_solo_cambios_de_regla():
    resultado = ejecutar_simulacion(configuracion())
    ultima_regla = {}
    for evento in resultado.bitacora:
        assert ultima_regla.get(evento.nodo_id) != evento.regla_activada
        ultima_regla[evento.nodo_id] = evento.regla_activada


def test_series_acumuladas_no_decrecen():
    resultado = ejecutar_simulacion(configuracion())
    series = resultado.series_temporales
    for previo, actual in zip(series, series[1:]):
        assert actual.litros_acumulados_neuro >= previo.litros_acumulados_neuro
        assert actual.energia_acumulada_temporizador_wh >= previo.energia_acumulada_temporizador_wh


def test_simulacion_corta_reporta_indicadores_sin_datos():
    resultado = ejecutar_simulacion(configuracion(duracion_horas=1, numero_nodos=1))
    indicador = resultado.detalle_verificacion.conjetura_1_eficiencia.indicadores["ahorro_energia_pulsos_pct"]
    assert indicador.valor is None
    assert indicador.cumple is False
