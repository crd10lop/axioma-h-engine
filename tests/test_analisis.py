"""Pruebas del análisis de robustez: barrido, robustez, sensibilidad, calibración, incertidumbre y dimensionamiento."""

import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from backend import analisis, config
from backend.modelo_fisico import PARAMETROS_BASE, ParametrosModelo
from backend.schemas import (
    BarridoConfig,
    BarridoResultado,
    CalibracionConfig,
    DimensionamientoConfig,
    Escenario,
    EstadoCruce,
    EstandarConsumo,
    IncertidumbreConfig,
    ParametroSensible,
    PerfilSitio,
    PuntoBarrido,
    RobustezConfig,
    RobustezDesgasteConfig,
    SensibilidadConfig,
    SimulationConfig,
    ImpactoEntornosConfig,
    TasaSalinizacion,
    ZonaIncrustacion,
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
    """Sensibilidad a la eficacia del pulso con los valores del documento 04, secciones 5.6 y 5.7."""
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


# ---------------------------------------------------------------------------
# Calibración inversa del flujo de niebla
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("objetivo", "flujo_esperado"), [(3.0, 0.487), (10.0, 1.826)])
def test_calibracion_valores_de_control(objetivo, flujo_esperado):
    assert analisis.calibrar_flujo_niebla(objetivo) == pytest.approx(flujo_esperado, abs=0.01)


@pytest.mark.parametrize(
    ("objetivo", "constante"),
    [
        (config.RENDIMIENTO_LITERATURA_MIN_L_M2_DIA, config.FLUJO_NIEBLA_CALIBRADO_MIN_L_M2_H),
        (config.RENDIMIENTO_LITERATURA_MAX_L_M2_DIA, config.FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H),
    ],
)
def test_constantes_calibradas_coinciden_con_la_calibracion(objetivo, constante):
    assert analisis.calibrar_flujo_niebla(objetivo) == pytest.approx(constante, abs=0.01)


def test_calibracion_respeta_la_tolerancia():
    gruesa = analisis.calibrar_flujo_niebla(3.0, tolerancia=0.5)
    assert gruesa == pytest.approx(0.487, abs=0.5)


@pytest.mark.parametrize("objetivo", [0.1, 40.0])
def test_calibracion_fuera_del_intervalo_alcanzable(objetivo):
    with pytest.raises(ValueError, match="no está en el intervalo alcanzable"):
        analisis.calibrar_flujo_niebla(objetivo)


@pytest.mark.parametrize("tolerancia", [0.0, -0.1])
def test_calibracion_con_tolerancia_no_positiva(tolerancia):
    with pytest.raises(ValueError, match="tolerancia"):
        analisis.calibrar_flujo_niebla(3.0, tolerancia=tolerancia)


def test_valores_por_defecto_del_modelo_no_cambian():
    assert config.EFICACIA_MAXIMA_PULSO == pytest.approx(0.90)
    assert config.FLUJO_NIEBLA_MAXIMO_L_M2_H == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# Propagación de la incertidumbre
# ---------------------------------------------------------------------------
def _incertidumbre(**cambios) -> IncertidumbreConfig:
    """Configuración de incertidumbre en DIA_NORMAL con humedad inicial de 85 % y tasa ALTA."""
    datos = {
        "escenario": Escenario.DIA_NORMAL,
        "humedad_ambiente_inicial_pct": 85.0,
        "tasa_salinizacion": TasaSalinizacion.ALTA,
    }
    datos.update(cambios)
    return IncertidumbreConfig(**datos)


@pytest.fixture(scope="module")
def incertidumbre():
    """Incertidumbre con los rangos por defecto y 20 muestras, como en el documento 04."""
    return analisis.ejecutar_incertidumbre(_incertidumbre())


@pytest.fixture(scope="module")
def incertidumbre_salina():
    """Incertidumbre en INCRUSTACION_SALINA_RAPIDA, donde todas las muestras ejecutan pulsos."""
    return analisis.ejecutar_incertidumbre(_incertidumbre(escenario=Escenario.INCRUSTACION_SALINA_RAPIDA))


def test_incertidumbre_usa_los_rangos_de_config():
    cfg = _incertidumbre()
    assert cfg.eficacia_min == pytest.approx(config.EFICACIA_PULSO_RANGO_MIN)
    assert cfg.eficacia_max == pytest.approx(config.EFICACIA_PULSO_RANGO_MAX)
    assert cfg.flujo_min == pytest.approx(config.FLUJO_NIEBLA_CALIBRADO_MIN_L_M2_H)
    assert cfg.flujo_max == pytest.approx(config.FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H)


def test_incertidumbre_genera_el_numero_de_muestras(incertidumbre):
    assert len(incertidumbre.muestras) == 20


def test_muestras_dentro_de_los_rangos(incertidumbre):
    for muestra in incertidumbre.muestras:
        assert config.EFICACIA_PULSO_RANGO_MIN <= muestra.eficacia <= config.EFICACIA_PULSO_RANGO_MAX
        assert config.FLUJO_NIEBLA_CALIBRADO_MIN_L_M2_H <= muestra.flujo <= config.FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H


def test_incertidumbre_determinista_con_la_misma_semilla(incertidumbre):
    repetida = analisis.ejecutar_incertidumbre(_incertidumbre())
    assert repetida == incertidumbre


def test_otra_semilla_de_muestreo_cambia_las_muestras(incertidumbre):
    otra = analisis.ejecutar_incertidumbre(_incertidumbre(semilla_muestreo=8, n_muestras=5))
    assert otra.muestras[0].eficacia != pytest.approx(incertidumbre.muestras[0].eficacia)


@pytest.mark.parametrize("campo", ["probabilidad_c1", "probabilidad_c2", "probabilidad_c3"])
def test_probabilidades_entre_cero_y_uno(incertidumbre_salina, campo):
    assert 0.0 <= getattr(incertidumbre_salina, campo) <= 1.0


def test_probabilidad_es_la_proporcion_de_muestras_validadas(incertidumbre_salina):
    validadas = sum(m.conjeturas_validadas.conjetura_1_eficiencia for m in incertidumbre_salina.muestras)
    assert incertidumbre_salina.probabilidad_c1 == pytest.approx(validadas / len(incertidumbre_salina.muestras))


@pytest.mark.parametrize("indicador", ["recuperacion", "rendimiento", "reduccion_degradacion"])
def test_percentiles_ordenados(incertidumbre_salina, indicador):
    resumen = getattr(incertidumbre_salina, indicador)
    assert resumen.p5 <= resumen.p50
    assert resumen.p50 <= resumen.p95


def test_percentiles_ignoran_las_muestras_sin_datos(incertidumbre):
    con_datos = [m for m in incertidumbre.muestras if m.recuperacion_caudal_promedio_pct is not None]
    assert incertidumbre.recuperacion.n_validos == len(con_datos)


def test_resumen_sin_datos():
    resumen = analisis._resumen([None, None])
    assert resumen.n_validos == 0
    assert resumen.p50 is None


def test_resumen_con_un_dato():
    resumen = analisis._resumen([None, 87.5])
    assert resumen.p5 == pytest.approx(87.5)
    assert resumen.p95 == pytest.approx(87.5)


def test_resumen_con_varios_datos():
    resumen = analisis._resumen([float(valor) for valor in range(1, 22)])
    assert resumen.p5 == pytest.approx(2.0)
    assert resumen.p50 == pytest.approx(11.0)
    assert resumen.p95 == pytest.approx(20.0)


def test_incertidumbre_no_cambia_la_configuracion_global():
    antes = _configuracion_global()
    analisis.ejecutar_incertidumbre(_incertidumbre(n_muestras=5, duracion_horas=2, eficacia_min=0.1, flujo_max=20.0))
    despues = _configuracion_global()
    assert despues == antes
    assert PARAMETROS_BASE == ParametrosModelo()


@pytest.mark.parametrize(
    "cambios",
    [
        {"eficacia_min": 0.95, "eficacia_max": 0.90},
        {"eficacia_min": 0.90, "eficacia_max": 0.90},
        {"flujo_min": 2.0, "flujo_max": 1.0},
        {"eficacia_min": 0.0},
        {"eficacia_max": 1.01},
        {"flujo_min": 0.0},
        {"flujo_max": 20.5},
        {"n_muestras": 4},
        {"n_muestras": 31},
    ],
)
def test_configuracion_de_incertidumbre_invalida(cambios):
    with pytest.raises(ValidationError):
        _incertidumbre(**cambios)


# ---------------------------------------------------------------------------
# Barrido con parámetros, incrustación diaria y cruce de la ventaja
# ---------------------------------------------------------------------------
def _punto(incrustacion, ventaja, carga=60.0):
    """Punto de barrido sintético con la incrustación diaria, la ventaja y la carga salina dadas."""
    return PuntoBarrido(
        escenario=Escenario.DIA_NORMAL,
        tasa_salinizacion=TasaSalinizacion.ALTA,
        carga_salina_ohm_l_m2=carga,
        n_semillas=1,
        incrustacion_diaria_ohm_media=incrustacion,
        ventaja_recuperacion_pts=ventaja,
    )


def test_barrido_por_defecto_informa_los_parametros_base(barrido):
    assert barrido.flujo_niebla_maximo_l_m2_h == pytest.approx(config.FLUJO_NIEBLA_MAXIMO_L_M2_H)
    assert barrido.eficacia_maxima_pulso == pytest.approx(config.EFICACIA_MAXIMA_PULSO)


def test_barrido_ventaja_es_la_diferencia_de_recuperaciones(barrido):
    punto = barrido.puntos[-1]
    esperado = punto.recuperacion_neuro_media - punto.recuperacion_temporizador_media
    assert punto.ventaja_recuperacion_pts == pytest.approx(esperado, abs=1e-3)


def test_barrido_incrustacion_diaria_es_carga_por_rendimiento(barrido):
    punto = barrido.puntos[3]
    esperado = punto.carga_salina_ohm_l_m2 * punto.rendimiento_neuro_l_m2_dia_media
    assert punto.incrustacion_diaria_ohm_media == pytest.approx(esperado, abs=1e-2)


def test_barrido_carga_alta_reporta_pulsos_y_rendimiento(barrido):
    punto = barrido.puntos[-1]
    assert punto.pulsos_neuro_media == pytest.approx(97.0)
    assert punto.rendimiento_neuro_l_m2_dia_media == pytest.approx(23.17, abs=0.01)


def test_barrido_por_defecto_cruza_entre_40_y_60_ohm_por_litro(barrido):
    cruce = barrido.cruce
    assert cruce.estado == EstadoCruce.INTERPOLADO
    assert 40.0 < cruce.carga_salina_ohm_l_m2 < 60.0


def test_barrido_sin_pulsos_no_tiene_ventaja():
    resultado = analisis.ejecutar_barrido(BarridoConfig(humedad_ambiente_inicial_pct=0.0, duracion_horas=1, numero_nodos=1))
    punto = resultado.puntos[0]
    assert punto.ventaja_recuperacion_pts is None
    assert resultado.cruce.estado == EstadoCruce.SIN_DATOS


def test_barrido_con_flujo_no_modifica_la_configuracion():
    antes = _configuracion_global()
    resultado = analisis.ejecutar_barrido(
        BarridoConfig(duracion_horas=2, numero_nodos=1, flujo_niebla_maximo_l_m2_h=1.83, eficacia_maxima_pulso=0.8)
    )
    despues = _configuracion_global()
    assert despues == antes
    assert PARAMETROS_BASE == ParametrosModelo()
    assert resultado.flujo_niebla_maximo_l_m2_h == pytest.approx(1.83)
    assert resultado.eficacia_maxima_pulso == pytest.approx(0.8)


def test_barrido_con_flujo_menor_reduce_el_rendimiento(barrido):
    calibrado = analisis.ejecutar_barrido(BarridoConfig(flujo_niebla_maximo_l_m2_h=1.83))
    assert calibrado.puntos[0].rendimiento_neuro_l_m2_dia_media < barrido.puntos[0].rendimiento_neuro_l_m2_dia_media


@pytest.mark.parametrize(
    "puntos",
    [[], [_punto(100.0, 1.0)], [_punto(100.0, 1.0), _punto(None, 2.0), _punto(300.0, None)]],
)
def test_cruce_sin_datos(puntos):
    cruce = analisis._cruce(puntos)
    assert cruce.estado == EstadoCruce.SIN_DATOS
    assert cruce.incrustacion_diaria_ohm is None


def test_cruce_sin_cambio_de_signo_neuro_superior():
    cruce = analisis._cruce([_punto(300.0, 2.0), _punto(100.0, 0.5)])
    assert cruce.estado == EstadoCruce.SIN_CRUCE_NEURO_SUPERIOR
    assert cruce.carga_salina_ohm_l_m2 is None


@pytest.mark.parametrize("ventajas", [(-3.0, -1.0), (0.0, 0.0), (-2.0, 0.0)])
def test_cruce_sin_cambio_de_signo_neuro_inferior(ventajas):
    cruce = analisis._cruce([_punto(100.0, ventajas[0]), _punto(300.0, ventajas[1])])
    assert cruce.estado == EstadoCruce.SIN_CRUCE_NEURO_INFERIOR


def test_cruce_interpolacion_exacta():
    # La ventaja pasa de -1 a 3: vale 0 a un cuarto del intervalo.
    puntos = [_punto(2000.0, 3.0, carga=100.0), _punto(1000.0, -1.0, carga=50.0)]
    cruce = analisis._cruce(puntos)
    assert cruce.estado == EstadoCruce.INTERPOLADO
    assert cruce.incrustacion_diaria_ohm == pytest.approx(1250.0)
    assert cruce.carga_salina_ohm_l_m2 == pytest.approx(62.5)


def test_cruce_con_ventaja_nula_en_el_extremo_inferior():
    cruce = analisis._cruce([_punto(100.0, 0.0, carga=20.0), _punto(200.0, 4.0, carga=40.0)])
    assert cruce.incrustacion_diaria_ohm == pytest.approx(100.0)
    assert cruce.carga_salina_ohm_l_m2 == pytest.approx(20.0)


def test_cruce_toma_el_primer_paso_ascendente():
    puntos = [_punto(100.0, -1.0), _punto(200.0, 1.0), _punto(300.0, -1.0), _punto(400.0, 1.0)]
    cruce = analisis._cruce(puntos)
    assert cruce.estado == EstadoCruce.INTERPOLADO
    assert cruce.incrustacion_diaria_ohm == pytest.approx(150.0)


def test_cruce_descendente():
    cruce = analisis._cruce([_punto(100.0, 2.0, carga=20.0), _punto(300.0, -2.0, carga=60.0)])
    assert cruce.estado == EstadoCruce.CRUCE_DESCENDENTE
    assert cruce.incrustacion_diaria_ohm == pytest.approx(200.0)
    assert cruce.carga_salina_ohm_l_m2 == pytest.approx(40.0)


@pytest.mark.parametrize(
    ("ventajas", "estado"),
    [((-1.0, 3.0), EstadoCruce.INTERPOLADO), ((2.0, -2.0), EstadoCruce.CRUCE_DESCENDENTE)],
)
def test_cruce_informa_los_puntos_interpolados_y_su_separacion(ventajas, estado):
    cruce = analisis._cruce([_punto(1000.0, ventajas[0]), _punto(1600.0, ventajas[1]), _punto(2500.0, ventajas[1])])
    assert cruce.estado == estado
    assert cruce.incrustacion_inferior_ohm == pytest.approx(1000.0)
    assert cruce.incrustacion_superior_ohm == pytest.approx(1600.0)
    assert cruce.separacion_ohm == pytest.approx(600.0)


@pytest.mark.parametrize(
    "puntos",
    [[_punto(100.0, 1.0)], [_punto(100.0, 1.0), _punto(200.0, 2.0)], [_punto(100.0, -1.0), _punto(200.0, -2.0)]],
)
def test_cruce_sin_interpolacion_no_informa_separacion(puntos):
    cruce = analisis._cruce(puntos)
    assert cruce.separacion_ohm is None
    assert cruce.incrustacion_inferior_ohm is None


def test_barrido_por_defecto_separacion_del_cruce(barrido):
    cruce = barrido.cruce
    assert cruce.incrustacion_inferior_ohm == pytest.approx(1290.48, abs=0.01)
    assert cruce.incrustacion_superior_ohm == pytest.approx(1918.13, abs=0.01)
    assert cruce.separacion_ohm == pytest.approx(627.65, abs=0.01)
    assert cruce.incrustacion_inferior_ohm < cruce.incrustacion_diaria_ohm < cruce.incrustacion_superior_ohm


def test_barrido_con_parametros_explicitos_ignora_los_de_la_configuracion():
    parametros = ParametrosModelo(eficacia_maxima_pulso=0.8, flujo_niebla_maximo_l_m2_h=1.83)
    cfg = BarridoConfig(duracion_horas=2, numero_nodos=1, eficacia_maxima_pulso=0.95)
    resultado = analisis.ejecutar_barrido(cfg, parametros=parametros)
    assert resultado.eficacia_maxima_pulso == pytest.approx(0.8)
    assert resultado.flujo_niebla_maximo_l_m2_h == pytest.approx(1.83)


# ---------------------------------------------------------------------------
# Robustez de la respuesta
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def robustez():
    """Robustez con semilla 42 y humedad inicial de 85 %, como en el documento 04, sección 8.8."""
    return analisis.ejecutar_robustez(RobustezConfig())


def test_robustez_tiene_nueve_combinaciones(robustez):
    pares = [(c.flujo_niebla_maximo_l_m2_h, c.eficacia_maxima_pulso) for c in robustez.combinaciones]
    assert len(pares) == 9
    assert len(set(pares)) == 9


def test_robustez_combinaciones_en_orden_de_flujo_y_eficacia(robustez):
    primera, ultima = robustez.combinaciones[0], robustez.combinaciones[-1]
    assert primera.flujo_niebla_maximo_l_m2_h == pytest.approx(config.FLUJO_NIEBLA_MAXIMO_L_M2_H)
    assert primera.eficacia_maxima_pulso == pytest.approx(config.EFICACIA_PULSO_RANGO_MIN)
    assert ultima.flujo_niebla_maximo_l_m2_h == pytest.approx(config.FLUJO_NIEBLA_CALIBRADO_MIN_L_M2_H)
    assert ultima.eficacia_maxima_pulso == pytest.approx(config.EFICACIA_PULSO_RANGO_MAX)


def test_robustez_cada_barrido_usa_sus_parametros(robustez):
    for combinacion in robustez.combinaciones:
        assert combinacion.barrido.flujo_niebla_maximo_l_m2_h == pytest.approx(combinacion.flujo_niebla_maximo_l_m2_h)
        assert combinacion.barrido.eficacia_maxima_pulso == pytest.approx(combinacion.eficacia_maxima_pulso)


def test_robustez_combinacion_base_coincide_con_el_barrido(robustez, barrido):
    base = robustez.combinaciones[1].barrido
    assert base.puntos == barrido.puntos


def test_robustez_rango_de_reduccion_coherente_con_los_barridos(robustez):
    reducciones = [p.reduccion_desgaste_pct for c in robustez.combinaciones for p in c.barrido.puntos]
    assert robustez.reduccion_desgaste_min_pct == pytest.approx(min(reducciones))
    assert robustez.reduccion_desgaste_max_pct == pytest.approx(max(reducciones))


def test_robustez_cuenta_las_combinaciones_con_cruce(robustez):
    cruces = [
        c.barrido.cruce.incrustacion_diaria_ohm
        for c in robustez.combinaciones
        if c.barrido.cruce.estado == EstadoCruce.INTERPOLADO
    ]
    assert robustez.combinaciones_con_cruce == len(cruces)
    assert robustez.incrustacion_diaria_cruce_min_ohm == pytest.approx(min(cruces))
    assert robustez.incrustacion_diaria_cruce_max_ohm == pytest.approx(max(cruces))


def test_robustez_reproduce_el_documento_04(robustez):
    assert robustez.combinaciones_con_cruce == 6
    assert robustez.incrustacion_diaria_cruce_min_ohm == pytest.approx(1632.87, abs=0.01)
    assert robustez.incrustacion_diaria_cruce_max_ohm == pytest.approx(1839.21, abs=0.01)
    assert robustez.reduccion_desgaste_min_pct == pytest.approx(73.26, abs=0.01)


def test_robustez_no_modifica_la_configuracion():
    antes = _configuracion_global()
    analisis.ejecutar_robustez(RobustezConfig(numero_nodos=1))
    despues = _configuracion_global()
    assert despues == antes
    assert PARAMETROS_BASE == ParametrosModelo()


def test_extremos_sin_valores():
    assert analisis._extremos([]) == (None, None)


def test_robustez_informa_la_separacion_de_cada_cruce(robustez):
    separaciones = [
        c.barrido.cruce.separacion_ohm for c in robustez.combinaciones if c.barrido.cruce.estado == EstadoCruce.INTERPOLADO
    ]
    rango = robustez.incrustacion_diaria_cruce_max_ohm - robustez.incrustacion_diaria_cruce_min_ohm
    assert min(separaciones) == pytest.approx(616.63, abs=0.01)
    assert max(separaciones) == pytest.approx(1164.64, abs=0.01)
    assert min(separaciones) > rango


# ---------------------------------------------------------------------------
# Robustez del desgaste frente a la fatiga y la degradación térmica
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def robustez_desgaste():
    """Robustez del desgaste con semilla 42 y humedad inicial de 85 %, como en el documento 04, sección 8.11."""
    return analisis.ejecutar_robustez_desgaste(RobustezDesgasteConfig())


def test_grilla_de_fatiga_y_degradacion_alrededor_del_supuesto():
    assert config.FATIGAS_ROBUSTEZ_PCT == pytest.approx((0.01, 0.02, 0.04))
    assert config.DEGRADACIONES_TERMICAS_ROBUSTEZ == pytest.approx((0.025, 0.05, 0.10))
    assert config.FATIGA_POR_PULSO_PCT in config.FATIGAS_ROBUSTEZ_PCT
    assert config.DEGRADACION_TERMICA_PCT_POR_C_MIN in config.DEGRADACIONES_TERMICAS_ROBUSTEZ


def test_robustez_desgaste_tiene_dieciocho_combinaciones_ordenadas(robustez_desgaste):
    ternas = [
        (c.flujo_niebla_maximo_l_m2_h, c.fatiga_por_pulso_pct, c.degradacion_termica_pct_por_c_min)
        for c in robustez_desgaste.combinaciones
    ]
    assert len(set(ternas)) == 18
    assert ternas[0] == pytest.approx((config.FLUJO_NIEBLA_MAXIMO_L_M2_H, 0.01, 0.025))
    assert ternas[-1] == pytest.approx((config.FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H, 0.04, 0.10))


def test_robustez_desgaste_combinacion_base_coincide_con_el_barrido(robustez_desgaste, barrido):
    base = robustez_desgaste.combinaciones[4]
    reducciones = [punto.reduccion_desgaste_pct for punto in barrido.puntos]
    assert base.fatiga_por_pulso_pct == pytest.approx(config.FATIGA_POR_PULSO_PCT)
    assert base.degradacion_termica_pct_por_c_min == pytest.approx(config.DEGRADACION_TERMICA_PCT_POR_C_MIN)
    assert base.reduccion_desgaste_min_pct == pytest.approx(min(reducciones))
    assert base.reduccion_desgaste_max_pct == pytest.approx(max(reducciones))


def test_robustez_desgaste_rango_coherente_con_las_combinaciones(robustez_desgaste):
    minimos = [c.reduccion_desgaste_min_pct for c in robustez_desgaste.combinaciones]
    maximos = [c.reduccion_desgaste_max_pct for c in robustez_desgaste.combinaciones]
    assert robustez_desgaste.reduccion_desgaste_min_pct == pytest.approx(min(minimos))
    assert robustez_desgaste.reduccion_desgaste_max_pct == pytest.approx(max(maximos))


def test_robustez_desgaste_reproduce_el_documento_04(robustez_desgaste):
    assert robustez_desgaste.combinaciones_con_menor_desgaste_en_todos_los_puntos == 18
    assert robustez_desgaste.reduccion_desgaste_min_pct == pytest.approx(61.47, abs=0.01)
    assert robustez_desgaste.reduccion_desgaste_max_pct == pytest.approx(100.0)
    menor = min(robustez_desgaste.combinaciones, key=lambda c: c.reduccion_desgaste_min_pct)
    assert (menor.fatiga_por_pulso_pct, menor.degradacion_termica_pct_por_c_min) == pytest.approx((0.04, 0.025))


def test_robustez_desgaste_mas_fatiga_reduce_menos_y_mas_degradacion_reduce_mas(robustez_desgaste):
    por_terna = {
        (c.fatiga_por_pulso_pct, c.degradacion_termica_pct_por_c_min): c.reduccion_desgaste_min_pct
        for c in robustez_desgaste.combinaciones
        if c.flujo_niebla_maximo_l_m2_h == pytest.approx(config.FLUJO_NIEBLA_MAXIMO_L_M2_H)
    }
    assert por_terna[(0.04, 0.05)] < por_terna[(0.02, 0.05)] < por_terna[(0.01, 0.05)]
    assert por_terna[(0.02, 0.025)] < por_terna[(0.02, 0.05)] < por_terna[(0.02, 0.10)]


def test_combinacion_desgaste_cuenta_solo_las_reducciones_positivas(monkeypatch):
    puntos = [
        PuntoBarrido(**{**_punto(100.0, 1.0).model_dump(), "reduccion_desgaste_pct": reduccion})
        for reduccion in (50.0, 0.0, -10.0, None)
    ]
    monkeypatch.setattr(analisis, "ejecutar_barrido", lambda *_args, **_kwargs: BarridoResultado(puntos=puntos))
    combinacion = analisis._combinacion_desgaste(RobustezDesgasteConfig(), 6.0, 0.02, 0.05)
    assert combinacion.puntos_con_menor_desgaste == 1
    assert combinacion.puntos_totales == 4
    assert combinacion.reduccion_desgaste_min_pct == pytest.approx(-10.0)


def test_robustez_desgaste_sin_menor_desgaste_en_todos_los_puntos(monkeypatch):
    puntos = [PuntoBarrido(**{**_punto(100.0, 1.0).model_dump(), "reduccion_desgaste_pct": None})]
    monkeypatch.setattr(analisis, "ejecutar_barrido", lambda *_args, **_kwargs: BarridoResultado(puntos=puntos))
    resultado = analisis.ejecutar_robustez_desgaste(RobustezDesgasteConfig())
    assert resultado.combinaciones_con_menor_desgaste_en_todos_los_puntos == 0
    assert resultado.reduccion_desgaste_min_pct is None


def test_robustez_desgaste_no_modifica_la_configuracion():
    antes = _configuracion_global()
    analisis.ejecutar_robustez_desgaste(RobustezDesgasteConfig(numero_nodos=1))
    despues = _configuracion_global()
    assert despues == antes
    assert PARAMETROS_BASE == ParametrosModelo()


@pytest.mark.parametrize("cambios", [{"duracion_horas": 23}, {"semillas": [1, 2, 3, 4]}, {"semillas": [5, 5]}])
def test_configuracion_de_robustez_desgaste_invalida(cambios):
    with pytest.raises(ValidationError):
        RobustezDesgasteConfig(**cambios)


# ---------------------------------------------------------------------------
# Calibración del flujo para otro sitio
# ---------------------------------------------------------------------------
CAMPO_RENDIMIENTO = "rendimiento_objetivo_l_m2_dia"
SITIO_CALIBRACION = PerfilSitio(
    nombre="SITIO_VERIFICACION",
    flujo_niebla_maximo_l_m2_h=1.83,
    temperatura_media_c=28.0,
    amplitud_temperatura_c=5.0,
    amplitud_humedad_pct=12.0,
)


def test_calibracion_con_el_perfil_por_defecto_es_identica_a_sin_sitio():
    sin_sitio = analisis.calibrar_flujo_niebla(10.0)
    con_perfil = analisis.calibrar_flujo_niebla(10.0, sitio=PerfilSitio(flujo_niebla_maximo_l_m2_h=1.0))
    assert con_perfil == pytest.approx(sin_sitio)


def test_calibracion_con_otro_sitio_usa_su_clima():
    assert analisis.calibrar_flujo_niebla(10.0, sitio=SITIO_CALIBRACION) == pytest.approx(1.8026, abs=1e-4)


def test_ejecutar_calibracion_sin_sitio():
    resultado = analisis.ejecutar_calibracion(CalibracionConfig(rendimiento_objetivo_l_m2_dia=10.0))
    assert resultado.flujo_calibrado_l_m2_h == pytest.approx(1.8256, abs=1e-4)
    assert resultado.rendimiento_obtenido_l_m2_dia == pytest.approx(9.9961, abs=1e-4)
    assert resultado.perfil.nombre == "CABO_DE_LA_VELA"
    assert resultado.perfil.flujo_niebla_maximo_l_m2_h == pytest.approx(resultado.flujo_calibrado_l_m2_h)


def test_ejecutar_calibracion_con_sitio_conserva_su_clima():
    cfg = CalibracionConfig(rendimiento_objetivo_l_m2_dia=3.0, sitio=SITIO_CALIBRACION)
    resultado = analisis.ejecutar_calibracion(cfg)
    assert resultado.perfil.nombre == SITIO_CALIBRACION.nombre
    assert resultado.perfil.temperatura_media_c == pytest.approx(SITIO_CALIBRACION.temperatura_media_c)
    assert resultado.flujo_calibrado_l_m2_h == pytest.approx(0.4832, abs=1e-4)
    assert resultado.rendimiento_obtenido_l_m2_dia == pytest.approx(3.0, abs=0.05)
    assert SITIO_CALIBRACION.flujo_niebla_maximo_l_m2_h == pytest.approx(1.83)


def test_ejecutar_calibracion_inalcanzable():
    cfg = CalibracionConfig(rendimiento_objetivo_l_m2_dia=40.0)
    with pytest.raises(ValueError, match="no está en el intervalo alcanzable"):
        analisis.ejecutar_calibracion(cfg)


@pytest.mark.parametrize(
    "cambios",
    [{CAMPO_RENDIMIENTO: 0.0}, {CAMPO_RENDIMIENTO: 41.0}, {"humedad_ambiente_inicial_pct": -1.0}],
)
def test_configuracion_de_calibracion_invalida(cambios):
    datos = {CAMPO_RENDIMIENTO: 10.0, **cambios}
    with pytest.raises(ValidationError):
        CalibracionConfig(**datos)


@pytest.mark.parametrize(
    "cambios",
    [{"duracion_horas": 23}, {"duracion_horas": 73}, {"semillas": [1, 2, 3, 4]}, {"semillas": [5, 5]}, {"semillas": []}],
)
def test_configuracion_de_robustez_invalida(cambios):
    with pytest.raises(ValidationError):
        RobustezConfig(**cambios)


# ---------------------------------------------------------------------------
# Perfiles de sitio y dimensionamiento
# ---------------------------------------------------------------------------
def test_perfiles_de_sitio_de_referencia():
    perfiles = analisis.perfiles_sitio()
    assert [perfil.nombre for perfil in perfiles] == [
        "CABO_DE_LA_VELA",
        "CABO_DE_LA_VELA_CALIBRADO_MAX",
        "CABO_DE_LA_VELA_CALIBRADO_MIN",
    ]
    assert [perfil.flujo_niebla_maximo_l_m2_h for perfil in perfiles] == pytest.approx([6.0, 1.83, 0.49])


def test_perfiles_de_sitio_conservan_el_clima_de_config():
    for perfil in analisis.perfiles_sitio():
        assert perfil.temperatura_media_c == pytest.approx(config.TEMPERATURA_MEDIA_C)
        assert perfil.amplitud_humedad_pct == pytest.approx(config.AMPLITUD_HUMEDAD_PCT)


def _dimensionamiento(**cambios) -> DimensionamientoConfig:
    """Dimensionamiento para 50 personas en DIA_NORMAL con humedad inicial de 85 %."""
    datos = {"personas": 50, "escenario": Escenario.DIA_NORMAL, "humedad_ambiente_inicial_pct": 85.0}
    datos.update(cambios)
    return DimensionamientoConfig(**datos)


@pytest.fixture(scope="module")
def dimensionamiento():
    """Dimensionamiento para 50 personas con el estándar OMS de 20 L por persona al día."""
    return analisis.ejecutar_dimensionamiento(_dimensionamiento())


def test_dimensionamiento_usa_los_tres_flujos(dimensionamiento):
    origenes = [dimension.origen_flujo for dimension in dimensionamiento.dimensiones]
    assert origenes == ["SUPUESTO", "CALIBRADO_MAX", "CALIBRADO_MIN"]


def test_dimensionamiento_con_flujo_supuesto_reproduce_el_impacto(dimensionamiento):
    supuesto = dimensionamiento.dimensiones[0]
    assert supuesto.rendimiento_neuro_l_m2_dia == pytest.approx(31.83, abs=0.01)
    assert supuesto.area_colector_m2 == pytest.approx(50 * 20.0 / supuesto.rendimiento_neuro_l_m2_dia, abs=1e-3)
    assert supuesto.nodos_requeridos == 32


def test_dimensionamiento_con_flujo_calibrado_requiere_mas_area(dimensionamiento):
    areas = [dimension.area_colector_m2 for dimension in dimensionamiento.dimensiones]
    assert areas[0] < areas[1]
    assert areas[1] < areas[2]


def test_dimensionamiento_rango_de_la_literatura(dimensionamiento):
    assert dimensionamiento.consumo_l_persona_dia == pytest.approx(config.CONSUMO_ACCESO_BASICO_L_PERSONA_DIA)
    assert dimensionamiento.area_literatura_min_m2 == pytest.approx(100.0)
    assert dimensionamiento.area_literatura_max_m2 == pytest.approx(1000.0 / 3.0, abs=1e-3)


def test_dimensionamiento_con_estandar_sphere():
    resultado = analisis.ejecutar_dimensionamiento(_dimensionamiento(estandar=EstandarConsumo.SPHERE_15))
    assert resultado.consumo_l_persona_dia == pytest.approx(config.CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA)
    assert resultado.area_literatura_min_m2 == pytest.approx(75.0)


def test_dimensionamiento_sin_rendimiento():
    resultado = analisis.ejecutar_dimensionamiento(_dimensionamiento(humedad_ambiente_inicial_pct=0.0))
    for dimension in resultado.dimensiones:
        assert dimension.area_colector_m2 is None
        assert dimension.nodos_requeridos is None


@pytest.mark.parametrize("cambios", [{"personas": 0}, {"personas": 1001}, {"estandar": "OMS_50"}])
def test_configuracion_de_dimensionamiento_invalida(cambios):
    with pytest.raises(ValidationError):
        _dimensionamiento(**cambios)


# ---------------------------------------------------------------------------
# Ventaja en recuperación en la propagación de la incertidumbre
# ---------------------------------------------------------------------------
def test_incertidumbre_ventaja_por_muestra(incertidumbre_salina):
    for muestra in incertidumbre_salina.muestras:
        esperado = muestra.recuperacion_caudal_promedio_pct - muestra.recuperacion_temporizador_pct
        assert muestra.ventaja_recuperacion_pts == pytest.approx(esperado, abs=1e-3)


def test_incertidumbre_probabilidad_de_ventaja(incertidumbre_salina):
    ventajas = [m.ventaja_recuperacion_pts for m in incertidumbre_salina.muestras]
    positivas = sum(ventaja > 0 for ventaja in ventajas)
    assert incertidumbre_salina.probabilidad_ventaja_recuperacion == pytest.approx(positivas / len(ventajas))
    assert incertidumbre_salina.ventaja_recuperacion.n_validos == len(ventajas)


def test_incertidumbre_reproduce_el_documento_04(incertidumbre_salina):
    assert incertidumbre_salina.probabilidad_ventaja_recuperacion == pytest.approx(0.15)


def test_incertidumbre_sin_pulsos_no_tiene_ventaja():
    resultado = analisis.ejecutar_incertidumbre(_incertidumbre(escenario=Escenario.SEQUIA, n_muestras=5))
    assert resultado.probabilidad_ventaja_recuperacion is None
    assert resultado.ventaja_recuperacion.n_validos == 0
    assert resultado.muestras[0].ventaja_recuperacion_pts is None


def test_probabilidad_de_ventaja_ignora_nulos_y_ventaja_cero():
    assert analisis._probabilidad_ventaja([None, 0.0, 2.0, -1.0, 3.0]) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Impacto en distintos entornos y comparación con entrega por carrotanque (0.5.0)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def impacto_entornos():
    """Impacto en los 18 entornos de referencia con la configuración por defecto."""
    return analisis.ejecutar_impacto_entornos(ImpactoEntornosConfig())


@pytest.mark.parametrize(
    ("incrustacion", "zona"),
    [
        (None, ZonaIncrustacion.SIN_DATOS),
        (0.0, ZonaIncrustacion.BAJO_TRANSICION),
        (1171.05, ZonaIncrustacion.BAJO_TRANSICION),
        (1171.06, ZonaIncrustacion.TRANSICION),
        (2000.0, ZonaIncrustacion.TRANSICION),
        (2365.33, ZonaIncrustacion.TRANSICION),
        (2365.34, ZonaIncrustacion.SOBRE_TRANSICION),
        (5000.0, ZonaIncrustacion.SOBRE_TRANSICION),
    ],
)
def test_clasificar_incrustacion(incrustacion, zona):
    assert analisis.clasificar_incrustacion(incrustacion) == zona


def test_impacto_entornos_recorre_los_18_entornos_y_tres_origenes(impacto_entornos):
    assert len(impacto_entornos.entornos) == 18
    origenes = [entorno.origen_flujo for entorno in impacto_entornos.entornos]
    assert set(origenes) == {"SUPUESTO", "CALIBRADO_MAX", "CALIBRADO_MIN"}
    assert impacto_entornos.entrega_referencia_l_comunidad_mes == pytest.approx(
        config.ENTREGA_CARROTANQUE_L_COMUNIDAD_MES
    )


def test_impacto_entornos_calibrado_min_sin_ventaja_esperada(impacto_entornos):
    calibrado_min = [e for e in impacto_entornos.entornos if e.origen_flujo == "CALIBRADO_MIN"]
    assert len(calibrado_min) == 6
    for entorno in calibrado_min:
        assert entorno.zona_incrustacion != ZonaIncrustacion.SOBRE_TRANSICION


def test_impacto_entornos_contadores_coherentes(impacto_entornos):
    assert impacto_entornos.entornos_con_ventaja_esperada == 3
    assert impacto_entornos.entornos_clasificables == 7
    assert impacto_entornos.entornos_coherentes_con_simulacion == 7
    assert impacto_entornos.entornos_coherentes_con_simulacion <= impacto_entornos.entornos_clasificables


def test_impacto_entornos_nodos_equivalentes_coherentes_con_litros_mes(impacto_entornos):
    primero = impacto_entornos.entornos[0]
    assert primero.litros_mes_por_nodo == pytest.approx(
        primero.rendimiento_neuro_l_m2_dia * config.AREA_COLECTOR_M2 * config.DIAS_POR_MES,
        abs=1e-3,
    )
    assert primero.nodos_equivalentes_entrega == 2
    assert (primero.nodos_equivalentes_entrega - 1) * primero.litros_mes_por_nodo < (
        config.ENTREGA_CARROTANQUE_L_COMUNIDAD_MES
    )
    assert primero.nodos_equivalentes_entrega * primero.litros_mes_por_nodo >= (
        config.ENTREGA_CARROTANQUE_L_COMUNIDAD_MES
    )


def test_entorno_impacto_sin_rendimiento_devuelve_nulos():
    punto = PuntoBarrido(**{**_punto(100.0, 1.0).model_dump(), "rendimiento_neuro_l_m2_dia_media": None})
    entorno = analisis._entorno_impacto("SUPUESTO", 6.0, punto, 50, 20.0)
    assert entorno.area_colector_m2 is None
    assert entorno.nodos_requeridos is None
    assert entorno.litros_mes_por_nodo is None
    assert entorno.nodos_equivalentes_entrega is None


def test_trazabilidad_constantes_de_transicion_con_robustez(robustez):
    cruces = [
        c.barrido.cruce
        for c in robustez.combinaciones
        if c.barrido.cruce.estado == EstadoCruce.INTERPOLADO
    ]
    minimo_inferior = min(c.incrustacion_inferior_ohm for c in cruces)
    maximo_superior = max(c.incrustacion_superior_ohm for c in cruces)
    assert minimo_inferior == pytest.approx(config.INCRUSTACION_TRANSICION_MIN_OHM_DIA, abs=0.01)
    assert maximo_superior == pytest.approx(config.INCRUSTACION_TRANSICION_MAX_OHM_DIA, abs=0.01)
