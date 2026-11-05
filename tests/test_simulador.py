"""Pruebas del simulador comparativo."""

import pytest

from backend import config
from backend.modelo_fisico import PARAMETROS_BASE, ParametrosModelo, energia_pulso_wh, tiempo_hasta_impedancia
from backend.schemas import (
    CausaNoValidacion,
    Escenario,
    IndicadorVerificacion,
    ModoOperacion,
    PerfilSitio,
    SimulationConfig,
    TasaSalinizacion,
)
from backend.simulador import (
    DiagnosticoModo,
    Entorno,
    _causas_no_validacion,
    _indicador,
    _sitio,
    ejecutar_simulacion,
    ejecutar_simulacion_detallada,
    generar_entorno,
    parametros_de_configuracion,
    rendimiento_nocturno_l_m2,
    simular_modo,
    verificar_conjeturas,
)

RECUPERACION = "recuperacion_caudal_promedio_pct"
REGENERACION = "tiempo_regeneracion_promedio_seg"
RENDIMIENTO = "rendimiento_nocturno_l_m2_noche"
AHORRO = "ahorro_energia_pulsos_pct"


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


def entorno_constante(pasos, humedad=80.0, t_matriz=30.0, radiacion=0.0, hora_inicio=18.0, paso=5):
    """Entorno de un nodo con condiciones constantes, sin incrustación ni polvo."""
    return Entorno(
        paso_minutos=paso,
        minutos=[i * paso for i in range(pasos)],
        horas_locales=[(hora_inicio + i * paso / 60.0) % 24.0 for i in range(pasos)],
        humedad=[[humedad] for _ in range(pasos)],
        temperatura_ambiente=[t_matriz] * pasos,
        temperatura_matriz=[[t_matriz] for _ in range(pasos)],
        radiacion=[radiacion] * pasos,
        factor_captacion=[1.0] * pasos,
        ensuciamiento_ohm_h=[0.0] * pasos,
        incrustacion_ohm_por_l_m2=[0.0],
    )


@pytest.fixture(scope="module")
def corridas():
    """Diagnósticos detallados de los cinco escenarios."""
    return {escenario: ejecutar_simulacion_detallada(configuracion(escenario)) for escenario in Escenario}


def test_reproducibilidad_con_misma_semilla():
    cfg = configuracion(Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO)
    primera = ejecutar_simulacion(cfg).model_dump()
    segunda = ejecutar_simulacion(cfg).model_dump()
    assert primera == segunda


def test_semilla_distinta_cambia_el_entorno():
    a = ejecutar_simulacion(configuracion(semilla=1))
    b = ejecutar_simulacion(configuracion(semilla=2))
    assert a.series_temporales != b.series_temporales


@pytest.mark.parametrize("escenario", list(Escenario))
def test_neuro_simbolico_nunca_supera_45_por_pulso(corridas, escenario):
    _, neuro, _ = corridas[escenario]
    assert all(t < config.UMBRAL_TEMPERATURA_CORTE_C for t in neuro.temperaturas_pulso_c)
    assert neuro.perdida_termica_pulso_pct == pytest.approx(0.0)


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
    assert informativos["pulsos_regenerados"] == neuro.pulsos_regenerados
    assert informativos["pulsos_totales"] == neuro.pulsos
    impedancia_promedio = sum(neuro.impedancias_tras_pulso_ohms) / len(neuro.impedancias_tras_pulso_ohms)
    assert informativos["impedancia_promedio_tras_pulso_ohms"] == pytest.approx(impedancia_promedio, abs=1e-4)
    assert set(detalle.conjetura_1_eficiencia.indicadores_informativos) == {"reduccion_degradacion_pct"}
    assert set(detalle.conjetura_3_saber_territorial.indicadores_informativos) == {
        "rendimiento_nocturno_temporizador_l_m2_noche"
    }
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


def test_degradacion_acumulada_complementa_integridad():
    resultado = ejecutar_simulacion(configuracion())
    for modo in (resultado.comparativa.modo_neuro_simbolico, resultado.comparativa.modo_temporizador_fijo):
        assert modo.degradacion_acumulada_pct == pytest.approx(100.0 - modo.integridad_membrana_final_pct, abs=1e-3)


@pytest.mark.parametrize("tasa", list(TasaSalinizacion))
def test_neuro_simbolico_degrada_menos_que_temporizador(tasa):
    resultado = ejecutar_simulacion(configuracion(Escenario.INCRUSTACION_SALINA_RAPIDA, tasa_salinizacion=tasa))
    neuro = resultado.comparativa.modo_neuro_simbolico
    temporizador = resultado.comparativa.modo_temporizador_fijo
    assert neuro.degradacion_acumulada_pct < temporizador.degradacion_acumulada_pct


def test_recuperacion_nula_sin_pulsos():
    resultado = ejecutar_simulacion(
        configuracion(humedad_ambiente_inicial_pct=45.0, tasa_salinizacion=TasaSalinizacion.BAJA)
    )
    neuro = resultado.comparativa.modo_neuro_simbolico
    assert neuro.pulsos_termicos_ejecutados == 0
    assert neuro.recuperacion_caudal_promedio_pct is None
    assert resultado.comparativa.modo_temporizador_fijo.recuperacion_caudal_promedio_pct is not None


def test_pulsos_se_regeneran_con_eficacia_suficiente():
    # Según el análisis de sensibilidad, eta_max >= 0.97 basta para regenerar cada pulso.
    parametros = ParametrosModelo(eficacia_maxima_pulso=0.97)
    _, neuro, _ = ejecutar_simulacion_detallada(configuracion(), parametros=parametros)
    assert neuro.pulsos > 0
    assert neuro.pulsos_regenerados == neuro.pulsos
    assert neuro.pulsos_no_regenerados == 0
    assert all(t < config.TIEMPO_REGENERACION_MAX_SEG for t in neuro.tiempos_regeneracion_seg)


def test_temporizador_omite_pulsos_sin_reserva_de_energia():
    entorno = entorno_constante(pasos=24 * 12)
    diag = simular_modo(entorno, ModoOperacion.TEMPORIZADOR_FIJO)
    fin_min = entorno.numero_pasos * entorno.paso_minutos
    ordenes = len(range(config.INTERVALO_PULSO_TEMPORIZADOR_MIN, fin_min, config.INTERVALO_PULSO_TEMPORIZADOR_MIN))
    assert diag.pulsos_omitidos_por_energia > 0
    assert diag.pulsos + diag.pulsos_omitidos_por_energia == ordenes
    # Solo los pulsos ejecutados consumen energía de pulso.
    energia_por_pulso = energia_pulso_wh(config.INCREMENTO_TERMICO_TEMPORIZADOR_C)
    assert diag.energia_pulsos_wh == pytest.approx(diag.pulsos * energia_por_pulso)


def test_calor_ambiental_sobre_45_degrada_la_membrana():
    t_matriz = config.UMBRAL_TEMPERATURA_CORTE_C + 2.0
    entorno = entorno_constante(pasos=1, t_matriz=t_matriz)
    diag = simular_modo(entorno, ModoOperacion.NEURO_SIMBOLICO)
    perdida_esperada = 2.0 * entorno.paso_minutos * config.DEGRADACION_TERMICA_PCT_POR_C_MIN
    assert diag.bitacora[0].regla_activada == "REGLA_01_LIMITE_TERMICO_ABSOLUTO"
    assert diag.pulsos == 0
    assert diag.perdida_termica_pulso_pct == pytest.approx(0.0)
    assert diag.perdida_termica_ambiental_pct == pytest.approx(perdida_esperada)
    assert diag.integridad_final_promedio == pytest.approx(100.0 - perdida_esperada)


def test_rendimiento_nocturno_sin_horas_nocturnas():
    entorno = entorno_constante(pasos=12, hora_inicio=8.0)
    diag = simular_modo(entorno, ModoOperacion.NEURO_SIMBOLICO)
    assert diag.horas_nocturnas == pytest.approx(0.0)
    assert rendimiento_nocturno_l_m2(diag, entorno.numero_nodos) is None


def test_indicador_rechaza_operador_no_soportado():
    with pytest.raises(ValueError, match="Operador no soportado: >"):
        _indicador(1.0, 0.0, ">")


# ---------------------------------------------------------------------------
# Temporizador con tope ecológico (modo de referencia)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("escenario", list(Escenario))
def test_modo_referencia_nunca_supera_el_tope_ecologico(escenario):
    entorno = generar_entorno(configuracion(escenario))
    referencia = simular_modo(
        entorno, ModoOperacion.TEMPORIZADOR_FIJO, fraccion_temporizador=config.FRACCION_MAXIMA_EXTRACCION
    )
    assert referencia.fraccion_maxima_extraida <= config.FRACCION_MAXIMA_EXTRACCION


def test_modo_referencia_conserva_la_programacion_del_temporizador():
    entorno = generar_entorno(configuracion(Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO, humedad_ambiente_inicial_pct=45.0))
    temporizador = simular_modo(entorno, ModoOperacion.TEMPORIZADOR_FIJO)
    referencia = simular_modo(
        entorno, ModoOperacion.TEMPORIZADOR_FIJO, fraccion_temporizador=config.FRACCION_MAXIMA_EXTRACCION
    )
    assert referencia.pulsos == temporizador.pulsos
    assert referencia.energia_pulsos_wh == pytest.approx(temporizador.energia_pulsos_wh)
    assert referencia.bitacora == []


def test_payload_prd_conserva_resultados_y_agrega_referencia():
    cfg = configuracion(Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO, humedad_ambiente_inicial_pct=45.0)
    comparativa = ejecutar_simulacion(cfg).comparativa
    assert comparativa.modo_neuro_simbolico.litros_totales_agua == pytest.approx(81.652)
    assert comparativa.modo_temporizador_fijo.litros_totales_agua == pytest.approx(120.408)
    assert comparativa.modo_temporizador_tope_ecologico.litros_totales_agua == pytest.approx(91.8, abs=0.1)


def test_modo_referencia_no_se_agrega_a_las_series():
    resultado = ejecutar_simulacion(configuracion(duracion_horas=1, numero_nodos=1))
    campos = set(resultado.series_temporales[0].model_dump())
    assert not any("tope" in campo for campo in campos)


# ---------------------------------------------------------------------------
# Indicadores informativos nuevos
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("escenario", list(Escenario))
def test_cada_pulso_registra_impedancia_y_desprendimiento(corridas, escenario):
    _, neuro, _ = corridas[escenario]
    assert len(neuro.impedancias_tras_pulso_ohms) == neuro.pulsos
    assert len(neuro.tiempos_desprendimiento_seg) == neuro.pulsos


def test_desprendimiento_t95_del_pulso_a_44_grados():
    detalle = ejecutar_simulacion(configuracion()).detalle_verificacion
    informativos = detalle.conjetura_2_autorreparacion.indicadores_informativos
    assert informativos["tiempo_desprendimiento_t95_promedio_seg"] == pytest.approx(64.4, abs=0.1)


def test_reduccion_degradacion_frente_al_temporizador():
    resultado = ejecutar_simulacion(configuracion())
    neuro = resultado.comparativa.modo_neuro_simbolico.degradacion_acumulada_pct
    temporizador = resultado.comparativa.modo_temporizador_fijo.degradacion_acumulada_pct
    esperado = (temporizador - neuro) / temporizador * 100.0
    informativos = resultado.detalle_verificacion.conjetura_1_eficiencia.indicadores_informativos
    assert informativos["reduccion_degradacion_pct"] == pytest.approx(esperado, abs=1e-2)


def test_informativos_sin_datos_se_omiten():
    neuro = DiagnosticoModo(modo=ModoOperacion.NEURO_SIMBOLICO)
    temporizador = DiagnosticoModo(modo=ModoOperacion.TEMPORIZADOR_FIJO)
    detalle = verificar_conjeturas(neuro, temporizador, numero_nodos=1)
    assert detalle.conjetura_1_eficiencia.indicadores_informativos == {}
    assert set(detalle.conjetura_2_autorreparacion.indicadores_informativos) == {
        "pulsos_regenerados",
        "pulsos_totales",
    }
    assert detalle.conjetura_3_saber_territorial.indicadores_informativos == {}


# ---------------------------------------------------------------------------
# Causas de no validación
# ---------------------------------------------------------------------------
def _ind(valor, cumple, umbral=10.0):
    """Indicador mínimo para probar la clasificación de causas."""
    return IndicadorVerificacion(valor=valor, umbral=umbral, operador=">=", cumple=cumple)


def test_causas_vacias_si_todos_los_indicadores_cumplen():
    causas = _causas_no_validacion({RECUPERACION: _ind(95.0, True), AHORRO: _ind(40.0, True)}, None)
    assert causas == []


def test_causa_sin_datos():
    causas = _causas_no_validacion({RECUPERACION: _ind(None, False)}, None)
    assert causas == [CausaNoValidacion.SIN_DATOS]


@pytest.mark.parametrize("nombre", [RECUPERACION, REGENERACION])
def test_causa_parametro_supuesto(nombre):
    causas = _causas_no_validacion({nombre: _ind(5.0, False)}, None)
    assert causas == [CausaNoValidacion.DEPENDE_DE_PARAMETRO_SUPUESTO]


def test_causa_limite_del_recurso_atmosferico():
    causas = _causas_no_validacion({RENDIMIENTO: _ind(6.0, False, umbral=12.0)}, 8.0)
    assert causas == [CausaNoValidacion.LIMITE_DEL_RECURSO_ATMOSFERICO]


@pytest.mark.parametrize("rendimiento_temporizador", [15.0, None])
def test_causa_desempeno_en_rendimiento(rendimiento_temporizador):
    causas = _causas_no_validacion({RENDIMIENTO: _ind(11.0, False, umbral=12.0)}, rendimiento_temporizador)
    assert causas == [CausaNoValidacion.DESEMPENO_DEL_CONTROL]


def test_causa_desempeno_en_otros_indicadores():
    causas = _causas_no_validacion({AHORRO: _ind(12.0, False)}, None)
    assert causas == [CausaNoValidacion.DESEMPENO_DEL_CONTROL]


def test_causas_en_orden_y_sin_repetir():
    indicadores = {
        AHORRO: _ind(12.0, False),
        RECUPERACION: _ind(85.0, False),
        REGENERACION: _ind(500.0, False),
    }
    causas = _causas_no_validacion(indicadores, None)
    assert causas == [CausaNoValidacion.DESEMPENO_DEL_CONTROL, CausaNoValidacion.DEPENDE_DE_PARAMETRO_SUPUESTO]


@pytest.mark.parametrize("escenario", list(Escenario))
def test_causas_vacias_solo_en_conjeturas_validadas(escenario):
    detalle = ejecutar_simulacion(configuracion(escenario)).detalle_verificacion
    for verificacion in (
        detalle.conjetura_1_eficiencia,
        detalle.conjetura_2_autorreparacion,
        detalle.conjetura_3_saber_territorial,
    ):
        assert verificacion.validada == (verificacion.causas_no_validacion == [])


def test_pulso_sin_efecto_termico_no_registra_desprendimiento():
    # Con la matriz a 15 °C, el pulso del temporizador llega a 27 °C, bajo la temperatura mínima de efecto.
    entorno = entorno_constante(pasos=4 * 12, t_matriz=15.0)
    diag = simular_modo(entorno, ModoOperacion.TEMPORIZADOR_FIJO)
    assert diag.pulsos > 0
    assert diag.tiempos_desprendimiento_seg == []
    assert len(diag.impedancias_tras_pulso_ohms) == diag.pulsos


# ---------------------------------------------------------------------------
# Perfil del sitio y parámetros de la configuración
# ---------------------------------------------------------------------------
SITIO_CALIDO = PerfilSitio(
    nombre="SITIO_PRUEBA",
    flujo_niebla_maximo_l_m2_h=1.83,
    temperatura_media_c=33.0,
    amplitud_temperatura_c=2.0,
    amplitud_humedad_pct=5.0,
)


@pytest.fixture(scope="module")
def corrida_base():
    """DIA_NORMAL con 85 %, sin sitio ni eficacia."""
    return ejecutar_simulacion(configuracion())


def test_sin_sitio_usa_el_perfil_por_defecto():
    sitio = _sitio(configuracion())
    assert sitio == PerfilSitio()
    assert sitio.temperatura_media_c == pytest.approx(config.TEMPERATURA_MEDIA_C)


def test_sin_sitio_ni_eficacia_usa_los_parametros_base():
    assert parametros_de_configuracion(configuracion()) is PARAMETROS_BASE


def test_parametros_de_configuracion_con_sitio_y_eficacia():
    parametros = parametros_de_configuracion(configuracion(sitio=SITIO_CALIDO, eficacia_maxima_pulso=0.95))
    assert parametros == ParametrosModelo(eficacia_maxima_pulso=0.95, flujo_niebla_maximo_l_m2_h=1.83)


def test_resultados_identicos_sin_sitio_ni_eficacia(corrida_base):
    explicitos = ejecutar_simulacion(configuracion(), parametros=PARAMETROS_BASE)
    perfil_por_defecto = ejecutar_simulacion(configuracion(sitio=PerfilSitio()))
    assert explicitos == corrida_base
    assert perfil_por_defecto == corrida_base


def test_resultados_base_reproducen_el_documento_04(corrida_base):
    assert corrida_base.comparativa.modo_neuro_simbolico.litros_totales_agua == pytest.approx(254.603)


def test_parametros_usados_por_defecto(corrida_base):
    usados = corrida_base.parametros_usados
    assert usados.nombre_sitio == "CABO_DE_LA_VELA"
    assert usados.flujo_niebla_maximo_l_m2_h == pytest.approx(config.FLUJO_NIEBLA_MAXIMO_L_M2_H)
    assert usados.eficacia_maxima_pulso == pytest.approx(config.EFICACIA_MAXIMA_PULSO)
    assert usados.amplitud_humedad_pct == pytest.approx(config.AMPLITUD_HUMEDAD_PCT)


def test_parametros_usados_reflejan_el_sitio_y_la_eficacia():
    resultado = ejecutar_simulacion(configuracion(duracion_horas=2, sitio=SITIO_CALIDO, eficacia_maxima_pulso=0.95))
    usados = resultado.parametros_usados
    assert usados.nombre_sitio == "SITIO_PRUEBA"
    assert usados.flujo_niebla_maximo_l_m2_h == pytest.approx(1.83)
    assert usados.eficacia_maxima_pulso == pytest.approx(0.95)
    assert usados.temperatura_media_c == pytest.approx(33.0)
    assert usados.amplitud_temperatura_c == pytest.approx(2.0)


def test_temperatura_del_sitio_define_el_ciclo_termico():
    entorno = generar_entorno(configuracion(sitio=SITIO_CALIDO))
    assert min(entorno.temperatura_ambiente) == pytest.approx(31.0, abs=0.01)
    assert max(entorno.temperatura_ambiente) == pytest.approx(35.0, abs=0.01)


def test_sin_amplitud_de_humedad_la_humedad_base_es_constante():
    # Sin ruido ni desfase por nodo, la humedad del entorno sería el valor inicial en todos los pasos.
    plano = generar_entorno(configuracion(sitio=PerfilSitio(amplitud_humedad_pct=0.0)))
    base = generar_entorno(configuracion())
    rango_plano = max(sum(paso) for paso in plano.humedad) - min(sum(paso) for paso in plano.humedad)
    rango_base = max(sum(paso) for paso in base.humedad) - min(sum(paso) for paso in base.humedad)
    assert rango_plano < rango_base


def test_flujo_del_sitio_cambia_el_agua_captada(corrida_base):
    calibrado = ejecutar_simulacion(configuracion(sitio=PerfilSitio(flujo_niebla_maximo_l_m2_h=1.83)))
    assert calibrado.comparativa.modo_neuro_simbolico.litros_totales_agua < (
        corrida_base.comparativa.modo_neuro_simbolico.litros_totales_agua
    )


def test_eficacia_de_la_configuracion_cambia_la_recuperacion(corrida_base):
    eficaz = ejecutar_simulacion(configuracion(eficacia_maxima_pulso=1.0))
    assert eficaz.comparativa.modo_neuro_simbolico.recuperacion_caudal_promedio_pct > (
        corrida_base.comparativa.modo_neuro_simbolico.recuperacion_caudal_promedio_pct
    )


def test_detallada_sin_parametros_usa_los_de_la_configuracion():
    cfg = configuracion(duracion_horas=6, eficacia_maxima_pulso=1.0)
    _, implicita, _ = ejecutar_simulacion_detallada(cfg)
    _, explicita, _ = ejecutar_simulacion_detallada(cfg, parametros=ParametrosModelo(eficacia_maxima_pulso=1.0))
    assert implicita.recuperaciones_pct == explicita.recuperaciones_pct
