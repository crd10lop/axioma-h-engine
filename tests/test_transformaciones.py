"""Pruebas de las transformaciones del dashboard."""

import copy

import pandas as pd
import pytest

from backend.analisis import (
    ejecutar_barrido,
    ejecutar_dimensionamiento,
    ejecutar_incertidumbre,
    ejecutar_robustez,
    ejecutar_robustez_desgaste,
)
from backend.schemas import (
    BarridoConfig,
    CausaNoValidacion,
    DimensionamientoConfig,
    Escenario,
    IncertidumbreConfig,
    RobustezConfig,
    RobustezDesgasteConfig,
    SimulationConfig,
    TasaSalinizacion,
)
from backend.simulador import ejecutar_simulacion
from frontend import config
from frontend import transformaciones as tr

MODO_REGLAS = "Control basado en reglas"


@pytest.fixture(scope="module")
def resultado():
    """Respuesta de simulación real serializada como la entrega la API."""
    cfg = SimulationConfig(
        duracion_horas=24,
        escenario=Escenario.SEQUIA,
        humedad_ambiente_inicial_pct=85.0,
        tasa_salinizacion=TasaSalinizacion.ALTA,
    )
    return ejecutar_simulacion(cfg).model_dump(mode="json")


def test_minuto_a_hora_local_y_dia():
    assert tr.minuto_a_hora_local(0) == "18:00"
    assert tr.minuto_a_hora_local(365) == "00:05"
    assert tr.minuto_a_hora_local(1440) == "18:00"
    assert tr.dia_simulacion(0) == 1
    assert tr.dia_simulacion(359) == 1
    assert tr.dia_simulacion(360) == 2
    assert tr.etiqueta_tiempo(375) == "Día 2 00:15"


def test_diferencia_porcentual():
    assert tr.diferencia_porcentual(75.0, 100.0) == pytest.approx(-25.0)
    assert tr.diferencia_porcentual(5.0, 0.0) is None


def test_series_a_dataframe(resultado):
    df = tr.series_a_dataframe(resultado)
    assert len(df) == len(resultado["series_temporales"]) == 288
    assert {"minuto", "hora_simulada", "hora_local", "litros_acumulados_neuro"} <= set(df.columns)
    assert df["hora_local"].iloc[0] == "18:00"
    assert df["hora_simulada"].iloc[12] == pytest.approx(1.0)


def test_series_a_dataframe_vacio():
    assert tr.series_a_dataframe({"series_temporales": []}).empty


def test_series_formato_largo_vacio():
    df = tr.series_a_dataframe({"series_temporales": []})
    largo = tr.series_formato_largo(df, "litros_acumulados_neuro", "litros_acumulados_temporizador")
    assert largo.empty
    assert list(largo.columns) == ["minuto", "hora_simulada", "hora_local", "Modo", "valor"]


def test_series_formato_largo(resultado):
    df = tr.series_a_dataframe(resultado)
    largo = tr.series_formato_largo(df, "litros_acumulados_neuro", "litros_acumulados_temporizador")
    assert len(largo) == 2 * len(df)
    assert set(largo["Modo"]) == {MODO_REGLAS, "Temporizador fijo"}
    ultimo_neuro = largo[largo["Modo"] == MODO_REGLAS]["valor"].iloc[-1]
    assert ultimo_neuro == pytest.approx(df["litros_acumulados_neuro"].iloc[-1])


def test_comparativa_a_dataframe(resultado):
    df = tr.comparativa_a_dataframe(resultado)
    assert list(df["clave"]) == [clave for clave, _, _ in tr.METRICAS_COMPARATIVA]
    fila = df[df["clave"] == "litros_totales_agua"].iloc[0]
    neuro = resultado["comparativa"]["modo_neuro_simbolico"]["litros_totales_agua"]
    temporizador = resultado["comparativa"]["modo_temporizador_fijo"]["litros_totales_agua"]
    assert fila[MODO_REGLAS] == neuro
    assert fila["Diferencia (%)"] == pytest.approx((neuro - temporizador) / temporizador * 100.0)


def test_totales_a_dataframe(resultado):
    df = tr.totales_a_dataframe(resultado)
    assert len(df) == 6
    assert set(df["Modo"]) == {MODO_REGLAS, "Temporizador fijo"}
    assert df["Valor"].notna().all()


def test_indicadores_a_dataframe(resultado):
    verificacion = resultado["detalle_verificacion"]["conjetura_3_saber_territorial"]
    df = tr.indicadores_a_dataframe(verificacion)
    assert list(df.columns) == ["Indicador", "Valor obtenido", "Umbral", "Cumple"]
    assert len(df) == len(verificacion["indicadores"]) + len(verificacion["indicadores_informativos"])
    assert set(df["Cumple"]) <= {"Sí", "No", "Informativo"}
    # El rendimiento del temporizador se informa al final, después de los indicadores.
    assert df.iloc[-1]["Indicador"] == "Rendimiento nocturno del temporizador (L/m²/noche, informativo)"
    assert all(isinstance(valor, str) for valor in df["Valor obtenido"])


def test_indicadores_informativos_junto_al_tiempo_de_regeneracion(resultado):
    verificacion = resultado["detalle_verificacion"]["conjetura_2_autorreparacion"]
    df = tr.indicadores_a_dataframe(verificacion)
    nombres = list(df["Indicador"])
    posicion = nombres.index("Tiempo promedio de regeneración (s)")
    assert nombres[posicion + 1 : posicion + 5] == [
        "Pulsos regenerados (informativo)",
        "Pulsos totales (informativo)",
        "Tiempo hasta el 95 % de la remoción del pulso (s, informativo)",
        "Impedancia promedio tras el pulso (Ω, informativo)",
    ]
    informativos = df[df["Cumple"] == "Informativo"]
    assert list(informativos["Umbral"]) == ["No aplica"] * 4
    totales = verificacion["indicadores_informativos"]["pulsos_totales"]
    assert informativos.iloc[1]["Valor obtenido"] == str(totales)


def test_indicadores_informativos_sin_ancla_se_agregan_al_final():
    verificacion = {
        "indicadores": {"violaciones_ecologicas": {"valor": 0.0, "umbral": 0.0, "operador": "<=", "cumple": True}},
        "indicadores_informativos": {"pulsos_totales": 4},
    }
    df = tr.indicadores_a_dataframe(verificacion)
    assert list(df["Cumple"]) == ["Sí", "Informativo"]


def test_indicadores_sin_datos():
    verificacion = {"indicadores": {"ahorro_energia_pulsos_pct": {"valor": None, "umbral": 35.0, "operador": ">=", "cumple": False}}}
    df = tr.indicadores_a_dataframe(verificacion)
    assert df.iloc[0]["Valor obtenido"] == "Sin datos"
    assert df.iloc[0]["Umbral"] == ">= 35"
    assert df.iloc[0]["Cumple"] == "No"


def test_conjeturas_a_lista(resultado):
    conjeturas = tr.conjeturas_a_lista(resultado)
    assert [c["clave"] for c in conjeturas] == list(tr.NOMBRES_CONJETURA)
    for conjetura in conjeturas:
        assert conjetura["validada"] == resultado["conjeturas_validadas"][conjetura["clave"]]
        assert isinstance(conjetura["indicadores"], pd.DataFrame)
        assert conjetura["validada"] == (conjetura["causas"] == [])


def test_bitacora_a_texto_con_filtros(resultado):
    bitacora = resultado["bitacora"]
    texto = tr.bitacora_a_texto(bitacora)
    assert len(texto.splitlines()) == len(bitacora)
    assert texto.startswith("[Día 1 18:00]")

    solo_nodo = tr.bitacora_a_texto(bitacora, nodo="NODO_03")
    assert solo_nodo
    assert all("NODO_03" in linea for linea in solo_nodo.splitlines())

    regla = "REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL"
    solo_regla = tr.bitacora_a_texto(bitacora, regla=regla)
    assert all(regla in linea for linea in solo_regla.splitlines())

    combinado = tr.filtrar_bitacora(bitacora, nodo="NODO_03", regla=regla)
    assert all(e["nodo_id"] == "NODO_03" and e["regla_activada"] == regla for e in combinado)

    assert tr.bitacora_a_texto(bitacora, nodo="NODO_99") == "Sin eventos para los filtros seleccionados."


def test_historial_a_texto():
    historial = [{"hora": "10:00:00", "nodo": "NODO_01", "regla": "REGLA_05_OPERACION_NOMINAL", "motivo": "Normal."}]
    assert tr.historial_a_texto(historial) == "[10:00:00] NODO_01 | REGLA_05_OPERACION_NOMINAL | Normal."
    assert "Aún no hay decisiones" in tr.historial_a_texto([])


@pytest.mark.parametrize(
    "campo, valor, fuera_de_zona",
    [
        ("impedancia_ohms", 1500.0, False),
        ("impedancia_ohms", 1500.1, True),
        ("temperatura_celsius", 44.9, False),
        ("temperatura_celsius", 45.0, True),
        ("reserva_calor_pct", 30.0, False),
        ("reserva_calor_pct", 29.9, True),
        ("humedad_relativa_pct", 30.0, False),
        ("humedad_relativa_pct", 29.9, True),
    ],
)
def test_zonas_telemetria(campo, valor, fuera_de_zona):
    telemetria = {
        "impedancia_ohms": 1000.0,
        "temperatura_celsius": 30.0,
        "reserva_calor_pct": 70.0,
        "humedad_relativa_pct": 80.0,
    }
    telemetria[campo] = valor
    assert tr.zonas_telemetria(telemetria)[campo] is fuera_de_zona


def test_comparativa_tolera_recuperacion_sin_datos(resultado):
    copia = {"comparativa": {modo: dict(valores) for modo, valores in resultado["comparativa"].items()}}
    copia["comparativa"]["modo_neuro_simbolico"]["recuperacion_caudal_promedio_pct"] = None
    df = tr.comparativa_a_dataframe(copia)
    fila = df[df["clave"] == "recuperacion_caudal_promedio_pct"].iloc[0]
    assert pd.isna(fila[MODO_REGLAS])
    assert pd.isna(fila["Diferencia (%)"])


# ---------------------------------------------------------------------------
# Causas de no validación y modo de referencia
# ---------------------------------------------------------------------------
def _respuesta_minima(litros_neuro, litros_temporizador, litros_referencia=None):
    """Respuesta con solo los campos que usan la descomposición y la línea del modo de referencia."""
    def modo(litros):
        return {
            tr.CLAVE_LITROS: litros,
            "pulsos_termicos_ejecutados": 88,
            "consumo_energia_wh": 1065.067,
            "integridad_membrana_final_pct": 97.5,
            "violaciones_ecologicas": 0,
        }

    comparativa = {tr.MODO_NEURO: modo(litros_neuro), tr.MODO_TEMPORIZADOR: modo(litros_temporizador)}
    if litros_referencia is not None:
        comparativa[tr.MODO_REFERENCIA] = modo(litros_referencia)
    return {"comparativa": comparativa}


def test_conjeturas_a_lista_traduce_las_causas(resultado):
    conjeturas = {c["clave"]: c for c in tr.conjeturas_a_lista(resultado)}
    causas_api = resultado["detalle_verificacion"]["conjetura_1_eficiencia"]["causas_no_validacion"]
    esperado = [tr.TEXTO_CAUSA[causa] for causa in causas_api]
    assert conjeturas["conjetura_1_eficiencia"]["causas"] == esperado


def test_texto_causa_cubre_todas_las_causas():
    assert set(tr.TEXTO_CAUSA) == {causa.value for causa in CausaNoValidacion}


def test_conjeturas_a_lista_tolera_respuesta_sin_campos_nuevos(resultado):
    antiguo = copy.deepcopy(resultado)
    for verificacion in antiguo["detalle_verificacion"].values():
        verificacion.pop("causas_no_validacion")
    for conjetura in tr.conjeturas_a_lista(antiguo):
        assert conjetura["causas"] == []


def test_causa_desconocida_se_muestra_sin_traducir(resultado):
    modificado = copy.deepcopy(resultado)
    modificado["detalle_verificacion"]["conjetura_1_eficiencia"]["causas_no_validacion"] = ["OTRA_CAUSA"]
    conjeturas = {c["clave"]: c for c in tr.conjeturas_a_lista(modificado)}
    assert conjeturas["conjetura_1_eficiencia"]["causas"] == ["OTRA_CAUSA"]


def test_descomponer_brecha_agua():
    brecha = tr.descomponer_brecha_agua(_respuesta_minima(81.652, 120.408, 91.784))
    assert brecha["brecha_total_l"] == pytest.approx(38.756)
    assert brecha["por_tope_ecologico_l"] == pytest.approx(28.624)
    assert brecha["por_logica_control_l"] == pytest.approx(10.132)
    assert brecha["pct_por_tope"] == pytest.approx(28.624 / 38.756 * 100.0)


def test_descomponer_brecha_agua_con_respuesta_real(resultado):
    brecha = tr.descomponer_brecha_agua(resultado)
    suma = brecha["por_tope_ecologico_l"] + brecha["por_logica_control_l"]
    assert suma == pytest.approx(brecha["brecha_total_l"])


def test_descomponer_brecha_sin_brecha_positiva():
    brecha = tr.descomponer_brecha_agua(_respuesta_minima(100.0, 100.0, 90.0))
    assert brecha["pct_por_tope"] is None


def test_descomponer_brecha_sin_modo_de_referencia():
    assert tr.descomponer_brecha_agua(_respuesta_minima(81.652, 120.408)) is None


def test_texto_brecha_agua():
    texto = tr.texto_brecha_agua(_respuesta_minima(81.652, 120.408, 91.784))
    assert texto == (
        "De 38.8 L de diferencia, 28.6 L (73.9 %) se deben al tope ecológico de 33 % "
        "y 10.1 L a la lógica de control."
    )


@pytest.mark.parametrize(
    "respuesta",
    [_respuesta_minima(81.652, 120.408), _respuesta_minima(100.0, 100.0, 90.0)],
)
def test_texto_brecha_agua_no_calculable(respuesta):
    assert tr.texto_brecha_agua(respuesta) is None


def test_texto_modo_referencia():
    texto = tr.texto_modo_referencia(_respuesta_minima(81.652, 120.408, 91.784))
    assert texto == (
        "Temporizador con tope ecológico (33 %): 91.8 L, 88 pulsos, 1065.1 Wh, "
        "integridad final 97.50 %, 0 violaciones ecológicas."
    )


def test_texto_modo_referencia_sin_modo():
    assert tr.texto_modo_referencia(_respuesta_minima(81.652, 120.408)) is None


# ---------------------------------------------------------------------------
# Análisis de robustez: barrido y sensibilidad
# ---------------------------------------------------------------------------
TEMPORIZADOR = "Temporizador fijo"


def _punto_barrido(carga, rec_neuro, rec_temp, reduccion=95.0, desv=0.5):
    """Punto de barrido con el formato de PuntoBarrido de la API."""
    return {
        "escenario": "DIA_NORMAL",
        "tasa_salinizacion": "BAJA",
        tr.CLAVE_CARGA: carga,
        "n_semillas": 3,
        "recuperacion_neuro_media": rec_neuro,
        "recuperacion_neuro_desv": None if rec_neuro is None else desv,
        "recuperacion_temporizador_media": rec_temp,
        "recuperacion_temporizador_desv": None if rec_temp is None else desv,
        "degradacion_neuro_media": 0.1,
        "degradacion_neuro_desv": desv,
        "degradacion_temporizador_media": 2.0,
        "degradacion_temporizador_desv": desv,
        "reduccion_desgaste_pct": reduccion,
    }


def _barrido(*puntos):
    """Respuesta de barrido con los puntos indicados."""
    return {tr.CLAVE_PUNTOS: list(puntos)}


@pytest.fixture(scope="module")
def barrido_real():
    """Barrido real con semilla 42 y humedad inicial de 85 %, serializado como lo entrega la API."""
    return ejecutar_barrido(BarridoConfig()).model_dump(mode="json")


def test_configuracion_barrido_usa_semillas_consecutivas():
    carga = tr.configuracion_barrido(85, 3)
    assert carga["semillas"] == [1, 2, 3]
    assert carga["humedad_ambiente_inicial_pct"] == pytest.approx(85.0)


@pytest.mark.parametrize(("solicitadas", "esperadas"), [(0, [1]), (9, [1, 2, 3, 4, 5])])
def test_configuracion_barrido_acota_las_semillas(solicitadas, esperadas):
    assert tr.configuracion_barrido(85.0, solicitadas)["semillas"] == esperadas


@pytest.mark.parametrize("parametro", list(tr.VALORES_SENSIBILIDAD))
def test_configuracion_sensibilidad_usa_valores_predefinidos(parametro):
    carga = tr.configuracion_sensibilidad(parametro, "DIA_NORMAL", 85)
    assert carga["valores"] == tr.VALORES_SENSIBILIDAD[parametro]
    assert carga["tasa_salinizacion"] == "ALTA"


def test_valores_predefinidos_de_sensibilidad():
    assert tr.VALORES_SENSIBILIDAD["EFICACIA_MAXIMA_PULSO"] == pytest.approx([0.85, 0.90, 0.94, 0.97, 1.00])
    assert tr.VALORES_SENSIBILIDAD["FLUJO_NIEBLA_MAXIMO"] == pytest.approx([3.0, 4.5, 6.0, 7.5])


def test_indicadores_de_sensibilidad_usan_umbrales_de_config():
    umbral_eficacia = tr.INDICADOR_SENSIBILIDAD["EFICACIA_MAXIMA_PULSO"][2]
    umbral_flujo = tr.INDICADOR_SENSIBILIDAD["FLUJO_NIEBLA_MAXIMO"][2]
    assert umbral_eficacia == pytest.approx(config.RECUPERACION_MINIMA_PCT)
    assert umbral_flujo == pytest.approx(config.RENDIMIENTO_MINIMO_L_M2_NOCHE)


def test_barrido_a_dataframe(barrido_real):
    df = tr.barrido_a_dataframe(barrido_real)
    assert list(df.columns) == tr.COLUMNAS_BARRIDO
    # 6 cargas, 2 modos y 2 variables.
    assert len(df) == 24
    recuperacion = df[df["Variable"] == tr.VARIABLE_RECUPERACION]
    temporizador = recuperacion[recuperacion["Modo"] == TEMPORIZADOR]
    assert temporizador.iloc[0]["media"] == pytest.approx(95.84, abs=0.01)


def test_barrido_a_dataframe_calcula_la_banda():
    fila = tr.barrido_a_dataframe(_barrido(_punto_barrido(20.0, 88.0, 95.0, desv=0.5))).iloc[0]
    assert fila["inferior"] == pytest.approx(87.5)
    assert fila["superior"] == pytest.approx(88.5)


def test_barrido_a_dataframe_omite_combinaciones_sin_datos():
    df = tr.barrido_a_dataframe(_barrido(_punto_barrido(20.0, None, 95.0)))
    recuperacion = df[df["Variable"] == tr.VARIABLE_RECUPERACION]
    assert list(recuperacion["Modo"]) == [TEMPORIZADOR]
    assert len(df) == 3


def test_barrido_a_dataframe_desviacion_ausente_es_cero():
    punto = _punto_barrido(20.0, 88.0, 95.0)
    punto["recuperacion_neuro_desv"] = None
    fila = tr.barrido_a_dataframe(_barrido(punto)).iloc[0]
    assert fila["desv"] == pytest.approx(0.0)


def test_barrido_a_dataframe_vacio():
    df = tr.barrido_a_dataframe({})
    assert df.empty
    assert list(df.columns) == tr.COLUMNAS_BARRIDO


def test_carga_cruce_con_datos_reales(barrido_real):
    assert tr.carga_cruce_recuperacion(barrido_real) == pytest.approx(60.0)


def test_carga_cruce_sin_cruce():
    resultado = _barrido(_punto_barrido(20.0, 88.0, 95.0), _punto_barrido(40.0, 88.0, 90.0))
    assert tr.carga_cruce_recuperacion(resultado) is None


def test_carga_cruce_se_reinicia_si_el_neuro_vuelve_a_quedar_debajo():
    # Puntos desordenados: por carga, el neuro supera en 20, queda debajo en 40 y vuelve a superar en 80.
    resultado = _barrido(
        _punto_barrido(80.0, 90.0, 85.0),
        _punto_barrido(20.0, 89.0, 88.0),
        _punto_barrido(40.0, 87.0, 88.0),
    )
    assert tr.carga_cruce_recuperacion(resultado) == pytest.approx(80.0)


def test_carga_cruce_ignora_puntos_sin_datos():
    resultado = _barrido(_punto_barrido(20.0, 90.0, 85.0), _punto_barrido(40.0, None, 80.0))
    assert tr.carga_cruce_recuperacion(resultado) == pytest.approx(20.0)


def test_lectura_barrido_con_datos_reales(barrido_real):
    frases = tr.lectura_barrido(barrido_real)
    assert frases[0] == (
        "Desde una carga salina de 60 Ohm por L/m², la recuperación con el control basado en reglas "
        "supera a la del temporizador."
    )
    assert frases[1] == (
        "La reducción del desgaste con el control basado en reglas frente al temporizador va de 73.9 % a 99.0 %."
    )
    assert "1 semilla(s)" in frases[2]


def test_lectura_barrido_sin_cruce_ni_reduccion():
    frases = tr.lectura_barrido(_barrido(_punto_barrido(20.0, 88.0, 95.0, reduccion=None)))
    assert frases[0].startswith("En el rango evaluado")
    assert frases[1] == "No hay datos para calcular la reducción del desgaste."


def test_lectura_barrido_sin_puntos():
    assert tr.lectura_barrido(_barrido()) == ["El barrido no devolvió puntos."]


def test_sensibilidad_a_dataframe():
    resultado = {
        "parametro": "EFICACIA_MAXIMA_PULSO",
        tr.CLAVE_PUNTOS: [
            {
                "valor": 0.94,
                "conjeturas_validadas": {
                    "conjetura_1_eficiencia": True,
                    "conjetura_2_autorreparacion": False,
                    "conjetura_3_saber_territorial": True,
                },
                "recuperacion_caudal_promedio_pct": 90.1218,
                "tiempo_regeneracion_promedio_seg": None,
                "rendimiento_nocturno_l_m2_noche": 17.04,
                "litros_neuro": 256.139,
            }
        ],
    }
    df = tr.sensibilidad_a_dataframe(resultado)
    assert list(df.columns) == tr.COLUMNAS_SENSIBILIDAD
    fila = df.iloc[0]
    assert bool(fila["C1"]) is True
    assert bool(fila["C2"]) is False
    assert fila[tr.COLUMNA_RECUPERACION] == pytest.approx(90.1218)
    assert fila[tr.COLUMNA_TIEMPO_REGENERACION] is None


def test_sensibilidad_a_dataframe_vacio():
    df = tr.sensibilidad_a_dataframe({})
    assert df.empty
    assert list(df.columns) == tr.COLUMNAS_SENSIBILIDAD


def test_etiquetas_cubren_parametros_y_columnas():
    assert set(tr.NOMBRES_PARAMETRO) == set(tr.VALORES_SENSIBILIDAD)
    assert set(tr.ETIQUETAS_SENSIBILIDAD) == set(tr.COLUMNAS_SENSIBILIDAD)


# ---------------------------------------------------------------------------
# Resumen ejecutivo
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def resultado_prd():
    """Payload de ejemplo del PRD: tormenta de sal y calor extremo con humedad inicial de 45 %."""
    cfg = SimulationConfig(
        duracion_horas=24,
        escenario=Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO,
        humedad_ambiente_inicial_pct=45.0,
        tasa_salinizacion=TasaSalinizacion.ALTA,
    )
    return ejecutar_simulacion(cfg).model_dump(mode="json")


def test_resumen_ejecutivo_tiene_entre_3_y_5_frases(resultado_prd):
    frases = tr.resumen_ejecutivo(resultado_prd)
    assert len(frases) >= 3
    assert len(frases) <= 5
    for frase in frases:
        assert frase.strip()


def test_resumen_ejecutivo_con_la_corrida_del_prd(resultado_prd):
    agua, desgaste, energia, violaciones, conjeturas = tr.resumen_ejecutivo(resultado_prd)
    assert agua.startswith(
        "Agua: el control basado en reglas captó 81.7 L, 32.2 % menos que el temporizador (120.4 L)."
    )
    assert "28.6 L (73.9 %) se deben al tope ecológico de 33 %" in agua
    assert desgaste == (
        "Desgaste: la degradación de la membrana fue 0.048 % con el control basado en reglas y "
        "2.906 % con el temporizador (98.4 % menos)."
    )
    assert energia == (
        "Energía: el control basado en reglas consumió 323.2 Wh, 69.7 % menos que el temporizador (1065.1 Wh)."
    )
    assert violaciones == "Límite ecológico: 0 violaciones con el control basado en reglas y 8 con el temporizador."
    assert conjeturas == "Conjeturas validadas: 0 de 3."


def test_resumen_ejecutivo_nombra_las_conjeturas_validadas(resultado_prd):
    modificado = copy.deepcopy(resultado_prd)
    modificado["conjeturas_validadas"]["conjetura_3_saber_territorial"] = True
    assert tr.resumen_ejecutivo(modificado)[-1] == "Conjeturas validadas: 1 de 3 (C3)."


def test_resumen_ejecutivo_sin_modo_de_referencia(resultado_prd):
    antiguo = copy.deepcopy(resultado_prd)
    antiguo["comparativa"].pop(tr.MODO_REFERENCIA)
    agua = tr.resumen_ejecutivo(antiguo)[0]
    assert agua == "Agua: el control basado en reglas captó 81.7 L, 32.2 % menos que el temporizador (120.4 L)."


@pytest.mark.parametrize(
    ("valor", "referencia", "esperado"),
    [(110.0, 100.0, "10.0 % más"), (90.0, 100.0, "10.0 % menos"), (100.0, 100.0, "lo mismo"), (5.0, 0.0, "lo mismo")],
)
def test_variacion(valor, referencia, esperado):
    assert tr._variacion(valor, referencia) == esperado


# ---------------------------------------------------------------------------
# Impacto comunitario
# ---------------------------------------------------------------------------
CLAVE_IMPACTO = "impacto_comunitario"


def _respuesta_impacto(rendimiento: float, con_temporizador: bool = True) -> dict:
    """Respuesta con impacto_comunitario mínimo para el modo neuro-simbólico y, opcionalmente, el temporizador."""
    neuro = {
        "litros_dia_red": rendimiento * 8,
        "rendimiento_l_m2_dia": rendimiento,
        "personas_supervivencia": rendimiento * 8 / 15,
        "personas_acceso_basico": rendimiento * 8 / 20,
        "area_m2_por_persona_basico_literatura_min": 2.0,
        "area_m2_por_persona_basico_literatura_max": 6.6667,
    }
    impacto = {tr.MODO_NEURO: neuro}
    if con_temporizador:
        impacto[tr.MODO_TEMPORIZADOR] = {**neuro, "personas_acceso_basico": 6.33}
    return {CLAVE_IMPACTO: impacto}


def test_resumen_impacto_con_respuesta_real(resultado_prd):
    personas, temporizador, rendimiento, area = tr.resumen_impacto(resultado_prd)
    assert personas == (
        "Con el agua captada por el control basado en reglas, la red simulada abastecería a 4.1 personas "
        "al nivel de acceso básico de la OMS (20 L por persona al día), o a 5.4 con el mínimo humanitario "
        "de Sphere (15 L por persona al día)."
    )
    assert temporizador == (
        "Como comparación, el temporizador fijo, que extrae por encima del tope ecológico, abastecería "
        "a 6.0 personas al mismo nivel."
    )
    assert rendimiento.startswith("El rendimiento simulado, 10.2 L/m² al día, supera el rango de 3 a 10")
    assert "equivale a 1.02 veces su extremo superior" in rendimiento
    assert area == (
        "Con los rendimientos reales de la literatura harían falta entre 2.0 y 6.7 m² de colector por "
        "persona para el acceso básico."
    )


@pytest.mark.parametrize(
    ("rendimiento", "esperado"),
    [
        (31.83, "equivale a 3.18 veces su extremo superior"),
        (6.0, "está dentro del rango de 3 a 10 L/m² al día"),
        (10.0, "está dentro del rango"),
        (2.5, "queda por debajo del rango de 3 a 10 L/m² al día"),
    ],
)
def test_resumen_impacto_frente_a_la_literatura(rendimiento, esperado):
    frases = tr.resumen_impacto(_respuesta_impacto(rendimiento))
    assert esperado in frases[2]


def test_resumen_impacto_sin_temporizador():
    frases = tr.resumen_impacto(_respuesta_impacto(6.0, con_temporizador=False))
    assert len(frases) == 3


@pytest.mark.parametrize("respuesta", [{}, {CLAVE_IMPACTO: {}}, {CLAVE_IMPACTO: None}])
def test_resumen_impacto_sin_campo(respuesta):
    assert tr.resumen_impacto(respuesta) is None


# ---------------------------------------------------------------------------
# Incertidumbre de los parámetros supuestos
# ---------------------------------------------------------------------------
def _incertidumbre_real(escenario: Escenario, n_muestras: int) -> dict:
    """Respuesta real del análisis de incertidumbre serializada como la entrega la API."""
    cfg = IncertidumbreConfig(
        escenario=escenario,
        humedad_ambiente_inicial_pct=85.0,
        tasa_salinizacion=TasaSalinizacion.ALTA,
        n_muestras=n_muestras,
    )
    return ejecutar_incertidumbre(cfg).model_dump(mode="json")


@pytest.fixture(scope="module")
def incertidumbre_dia_normal():
    """DIA_NORMAL con 20 muestras: varias muestras no ejecutan pulsos."""
    return _incertidumbre_real(Escenario.DIA_NORMAL, 20)


@pytest.fixture(scope="module")
def incertidumbre_salina():
    """INCRUSTACION_SALINA_RAPIDA con 5 muestras: todas ejecutan pulsos."""
    return _incertidumbre_real(Escenario.INCRUSTACION_SALINA_RAPIDA, 5)


def test_configuracion_incertidumbre():
    carga = tr.configuracion_incertidumbre("SEQUIA", 85, 10)
    assert carga == {
        "escenario": "SEQUIA",
        "humedad_ambiente_inicial_pct": 85.0,
        "tasa_salinizacion": "ALTA",
        "n_muestras": 10,
    }


def test_configuracion_incertidumbre_usa_20_muestras_por_defecto():
    assert tr.configuracion_incertidumbre("SEQUIA", 85.0)["n_muestras"] == 20


def test_incertidumbre_a_dataframe(incertidumbre_salina):
    df = tr.incertidumbre_a_dataframe(incertidumbre_salina)
    assert list(df.columns) == tr.COLUMNAS_INCERTIDUMBRE
    assert len(df) == 5
    assert set(df[tr.COLUMNA_ESTADO_C1]) <= {"Validada", "No validada"}
    assert df["eficacia"].iloc[0] == pytest.approx(incertidumbre_salina["muestras"][0]["eficacia"])


def test_incertidumbre_a_dataframe_vacio():
    df = tr.incertidumbre_a_dataframe({})
    assert df.empty
    assert list(df.columns) == tr.COLUMNAS_INCERTIDUMBRE


def test_probabilidades_incertidumbre(incertidumbre_dia_normal):
    tabla = tr.probabilidades_incertidumbre(incertidumbre_dia_normal)
    assert list(tabla["Conjetura"]) == list(tr.NOMBRES_CONJETURA.values())
    primera = tabla.iloc[0]
    assert primera["Probabilidad"] == pytest.approx(primera["Muestras validadas"] / 20)


def test_lectura_incertidumbre_con_muestras_sin_pulsos(incertidumbre_dia_normal):
    frases = tr.lectura_incertidumbre(incertidumbre_dia_normal)
    sin_pulsos = 20 - incertidumbre_dia_normal["recuperacion"]["n_validos"]
    assert frases[0].startswith("Conjetura 1. Eficiencia: se valida en ")
    assert "de 20 muestras (probabilidad " in frases[0]
    assert "entre los percentiles 5 y 95" in frases[4]
    assert frases[-2].startswith(f"En {sin_pulsos} de 20 muestras el control basado en reglas no aplicó pulsos")
    assert frases[-1].startswith("El control basado en reglas recupera más que el temporizador en 0 de 8 muestras")


def test_lectura_incertidumbre_sin_muestras_sin_pulsos(incertidumbre_salina):
    frases = tr.lectura_incertidumbre(incertidumbre_salina)
    assert len(frases) == 7
    assert "no aplicó pulsos" not in " ".join(frases)


def test_lectura_incertidumbre_indicador_sin_datos():
    muestra = {
        "eficacia": 0.9,
        "flujo": 1.0,
        "conjeturas_validadas": {
            "conjetura_1_eficiencia": False,
            "conjetura_2_autorreparacion": False,
            "conjetura_3_saber_territorial": False,
        },
    }
    sin_datos = {"p5": None, "p50": None, "p95": None, "n_validos": 0}
    resultado = {
        "probabilidad_c1": 0.0,
        "probabilidad_c2": 0.0,
        "probabilidad_c3": 0.0,
        "recuperacion": sin_datos,
        "rendimiento": {"p5": 2.1, "p50": 3.4, "p95": 5.3, "n_validos": 1},
        "reduccion_degradacion": sin_datos,
        "muestras": [muestra],
    }
    frases = tr.lectura_incertidumbre(resultado)
    assert frases[3] == "Recuperación tras pulso: ninguna muestra tiene datos."
    assert frases[4] == (
        "Rendimiento con el control basado en reglas: de 2.10 a 5.30 L/m² al día entre los percentiles 5 y 95 "
        "(mediana 3.40; 1 de 1 muestras con datos)."
    )
    assert frases[-1].startswith("En 1 de 1 muestras")


def test_lectura_incertidumbre_vacia():
    assert tr.lectura_incertidumbre({"muestras": []}) == ["El análisis no devolvió muestras."]


# ---------------------------------------------------------------------------
# Lenguaje llano y condiciones de cambio
# ---------------------------------------------------------------------------
REGLA_03 = "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA"
CODIGO_DESCONOCIDO = "CODIGO_NUEVO"
CRUCE = "cruce"


def test_etiqueta_llana_traduce_un_codigo_conocido():
    assert tr.etiqueta_llana(REGLA_03) == "Pulso de limpieza: la sal obstruye la membrana"


def test_etiqueta_llana_devuelve_el_codigo_desconocido():
    assert tr.etiqueta_llana(CODIGO_DESCONOCIDO) == CODIGO_DESCONOCIDO


def test_condiciones_de_cambio_una_frase_por_conjetura(resultado_prd):
    frases = tr.condiciones_de_cambio(resultado_prd)
    assert len(frases) == 3
    for frase in frases:
        assert ", no validada." in frase


def test_condiciones_de_cambio_calcula_la_distancia_de_la_recuperacion(resultado_prd):
    frase = tr.condiciones_de_cambio(resultado_prd)[0]
    assert "88.81 frente al umbral >= 90, a 1.19 del umbral." in frase
    assert f"{config.EFICACIA_MINIMA_C1:.2f}" in frase


def test_condiciones_de_cambio_omite_los_indicadores_que_cumplen(resultado_prd):
    frase = tr.condiciones_de_cambio(resultado_prd)[0]
    assert "Ahorro de energía" not in frase


def test_condiciones_de_cambio_del_rendimiento_nocturno(resultado_prd):
    frase = tr.condiciones_de_cambio(resultado_prd)[2]
    assert "5.95 frente al umbral >= 12" in frase
    assert "calibrar el flujo" in frase


def test_condiciones_de_cambio_de_una_conjetura_validada(resultado):
    # SEQUIA con 85 % valida la Conjetura 3.
    frase = tr.condiciones_de_cambio(resultado)[2]
    assert frase.startswith("Conjetura 3. Saber territorial, validada.")
    assert "con un margen de" in frase
    assert "Fallaría" in frase


def test_condiciones_de_cambio_indicador_sin_datos_y_desconocido():
    detalle = {
        "conjetura_1_eficiencia": {
            "validada": False,
            "indicadores": {
                "recuperacion_caudal_promedio_pct": {"valor": None, "umbral": 90.0, "operador": ">=", "cumple": False},
                "indicador_nuevo": {"valor": 2.0, "umbral": 5.0, "operador": ">=", "cumple": False},
            },
        }
    }
    frase = tr.condiciones_de_cambio({tr.CLAVE_DETALLE: detalle})[0]
    assert "no tiene datos" in frase
    assert "indicador_nuevo: 2.00 frente al umbral >= 5, a 3.00 del umbral." in frase
    assert "Depende de los parámetros supuestos del modelo." in frase


@pytest.mark.parametrize("respuesta", [{}, {tr.CLAVE_DETALLE: None}])
def test_condiciones_de_cambio_sin_detalle(respuesta):
    assert tr.condiciones_de_cambio(respuesta) == []


def test_palancas_cubren_los_indicadores_de_las_conjeturas(resultado):
    for verificacion in resultado[tr.CLAVE_DETALLE].values():
        for clave in verificacion["indicadores"]:
            assert clave in tr.PALANCAS_INDICADOR


# ---------------------------------------------------------------------------
# Robustez de la respuesta
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def robustez_real():
    """Robustez real con semilla 42 y humedad inicial de 85 %, como en docs/04, sección 8.8."""
    return ejecutar_robustez(RobustezConfig()).model_dump(mode="json")


def _combinacion(estado, incrustacion=None, carga=None, reduccion=90.0):
    """Combinación sintética de la robustez con un punto y el cruce indicado."""
    punto = {tr.CLAVE_CARGA: 60.0, "reduccion_desgaste_pct": reduccion, tr.CLAVE_INCRUSTACION: 1000.0}
    return {
        "flujo_niebla_maximo_l_m2_h": 1.0,
        "eficacia_maxima_pulso": 0.9,
        "barrido": {
            tr.CLAVE_PUNTOS: [punto],
            CRUCE: {"estado": estado, "incrustacion_diaria_ohm": incrustacion, tr.CLAVE_CARGA: carga},
        },
    }


def test_configuracion_robustez_acota_las_semillas():
    assert tr.configuracion_robustez(85, 9) == {"humedad_ambiente_inicial_pct": 85.0, "semillas": [1, 2, 3]}
    assert tr.configuracion_robustez(85, 0)["semillas"] == [1]


def test_tabla_robustez_con_datos_reales(robustez_real):
    tabla = tr.tabla_robustez(robustez_real)
    assert list(tabla.columns) == tr.COLUMNAS_ROBUSTEZ
    assert len(tabla) == 9
    primera = tabla.iloc[0]
    assert primera[tr.COLUMNA_CRUCE] == tr.etiqueta_llana(tr.ESTADO_INTERPOLADO)
    assert primera["Incrustación diaria del cruce (Ohm/día)"] == pytest.approx(1819.82, abs=0.01)
    assert primera["Reducción del desgaste mínima (%)"] == pytest.approx(73.26, abs=0.01)
    assert primera[tr.COLUMNA_SEPARACION_CRUCE] == pytest.approx(616.63, abs=0.01)


def test_tabla_robustez_sin_cruce_deja_celdas_vacias(robustez_real):
    ultima = tr.tabla_robustez(robustez_real).iloc[-1]
    assert ultima[tr.COLUMNA_CRUCE] == tr.etiqueta_llana("SIN_DATOS")
    assert pd.isna(ultima["Incrustación diaria del cruce (Ohm/día)"])


def test_tabla_robustez_vacia():
    tabla = tr.tabla_robustez({})
    assert tabla.empty
    assert list(tabla.columns) == tr.COLUMNAS_ROBUSTEZ


def test_lectura_robustez_con_datos_reales(robustez_real):
    frases = tr.lectura_robustez(robustez_real)
    assert "reduce el desgaste entre 73.3 % y 100.0 %" in frases[0]
    assert frases[1].startswith("6 de 9 combinaciones cruzan")
    assert "1633 a 1839 Ohm por día" in frases[1]
    assert "Es coherente con H1-Ciclo 3" in frases[2]
    assert "separados de 617 a 1165 Ohm por día, más que el rango del cruce entre combinaciones (206" in frases[3]
    assert "entre 1171 y 2365 Ohm por día" in frases[3]
    assert frases[4].startswith("3 de 9 combinaciones: sin datos suficientes")


def test_lectura_robustez_con_separacion_menor_que_el_rango():
    cruce = {
        "estado": tr.ESTADO_INTERPOLADO,
        "incrustacion_diaria_ohm": 1000.0,
        tr.CLAVE_CARGA: 50.0,
        "incrustacion_inferior_ohm": 950.0,
        "incrustacion_superior_ohm": 1050.0,
        tr.CLAVE_SEPARACION: 100.0,
    }
    combinacion = _combinacion(tr.ESTADO_INTERPOLADO)
    combinacion["barrido"][CRUCE] = cruce
    resultado = {
        tr.CLAVE_COMBINACIONES: [combinacion],
        "incrustacion_diaria_cruce_min_ohm": 1000.0,
        "incrustacion_diaria_cruce_max_ohm": 1500.0,
    }
    frases = tr.lectura_robustez(resultado)
    assert frases[-1] == (
        "Los dos niveles entre los que se interpola cada cruce están separados de 100 a 100 Ohm por día, "
        "no más que el rango del cruce entre combinaciones (500 Ohm por día)."
    )


def test_lectura_robustez_con_reduccion_no_positiva():
    resultado = {
        tr.CLAVE_COMBINACIONES: [_combinacion("SIN_DATOS")],
        "reduccion_desgaste_min_pct": -5.0,
        "reduccion_desgaste_max_pct": 90.0,
    }
    frase = tr.lectura_robustez(resultado)[0]
    assert "va de -5.0 % a 90.0 %" in frase
    assert "no reduce el desgaste" in frase


def test_lectura_robustez_sin_cruce_ni_reduccion():
    resultado = {tr.CLAVE_COMBINACIONES: [_combinacion("SIN_CRUCE_NEURO_INFERIOR")]}
    frases = tr.lectura_robustez(resultado)
    assert frases[0] == "No hay datos para calcular la reducción del desgaste."
    assert frases[1].startswith("Ninguna de las 1 combinaciones cruza")
    assert "el temporizador recupera igual o más" in frases[2]


def test_lectura_robustez_que_no_apoya_la_hipotesis():
    resultado = {
        tr.CLAVE_COMBINACIONES: [
            _combinacion(tr.ESTADO_INTERPOLADO, incrustacion=1000.0, carga=50.0),
            _combinacion(tr.ESTADO_INTERPOLADO, incrustacion=3000.0, carga=60.0),
        ],
        "reduccion_desgaste_min_pct": 80.0,
        "reduccion_desgaste_max_pct": 95.0,
        "combinaciones_con_cruce": 2,
        "incrustacion_diaria_cruce_min_ohm": 1000.0,
        "incrustacion_diaria_cruce_max_ohm": 3000.0,
    }
    frases = tr.lectura_robustez(resultado)
    assert "no apoya H1-Ciclo 3" in frases[2]


def test_lectura_robustez_con_un_solo_cruce_no_compara_la_variacion():
    resultado = {
        tr.CLAVE_COMBINACIONES: [_combinacion(tr.ESTADO_INTERPOLADO, incrustacion=1700.0, carga=55.0)],
        "incrustacion_diaria_cruce_min_ohm": 1700.0,
        "incrustacion_diaria_cruce_max_ohm": 1700.0,
    }
    frases = tr.lectura_robustez(resultado)
    assert len(frases) == 2


def test_lectura_robustez_sin_combinaciones():
    assert tr.lectura_robustez({}) == ["La robustez no devolvió combinaciones."]


# ---------------------------------------------------------------------------
# Robustez del desgaste frente a la fatiga y la degradación térmica
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def robustez_desgaste_real():
    """Robustez del desgaste real con semilla 42 y humedad inicial de 85 %, como en docs/04, sección 8.11."""
    return ejecutar_robustez_desgaste(RobustezDesgasteConfig()).model_dump(mode="json")


def _combinacion_desgaste(reduccion_min, puntos_menor=6):
    """Combinación sintética de la robustez del desgaste con la reducción mínima y los puntos indicados."""
    return {
        "flujo_niebla_maximo_l_m2_h": 6.0,
        tr.CLAVE_FATIGA: 0.02,
        tr.CLAVE_DEGRADACION_TERMICA: 0.05,
        tr.CLAVE_REDUCCION_MIN: reduccion_min,
        "reduccion_desgaste_max_pct": 99.0,
        "puntos_con_menor_desgaste": puntos_menor,
        "puntos_totales": 6,
    }


@pytest.mark.parametrize("numero_semillas", [0, 1, 3])
def test_configuracion_robustez_desgaste_acota_a_una_semilla(numero_semillas):
    carga = tr.configuracion_robustez_desgaste(85, numero_semillas)
    assert carga == {"humedad_ambiente_inicial_pct": 85.0, "semillas": [1]}
    assert isinstance(carga["humedad_ambiente_inicial_pct"], float)


def test_tabla_robustez_desgaste_con_datos_reales(robustez_desgaste_real):
    tabla = tr.tabla_robustez_desgaste(robustez_desgaste_real)
    assert list(tabla.columns) == tr.COLUMNAS_ROBUSTEZ_DESGASTE
    assert len(tabla) == 18
    assert tabla.iloc[0][tr.COLUMNA_REDUCCION_MIN] == pytest.approx(69.15, abs=0.01)
    assert set(tabla[tr.COLUMNA_PUNTOS_MENOR_DESGASTE]) == {"6 de 6"}


def test_tabla_robustez_desgaste_vacia():
    tabla = tr.tabla_robustez_desgaste({})
    assert tabla.empty
    assert list(tabla.columns) == tr.COLUMNAS_ROBUSTEZ_DESGASTE


def test_lectura_robustez_desgaste_con_datos_reales(robustez_desgaste_real):
    frases = tr.lectura_robustez_desgaste(robustez_desgaste_real)
    assert "reduce el desgaste entre 61.5 % y 100.0 %" in frases[0]
    assert frases[1].startswith("En las 18 combinaciones, el control basado en reglas se degrada menos")
    assert "fatiga de 0.04 % por pulso, una degradación térmica de 0.025 %" in frases[2]


def test_lectura_robustez_desgaste_sin_menor_desgaste_en_todos_los_puntos():
    resultado = {
        tr.CLAVE_COMBINACIONES: [_combinacion_desgaste(-3.0, puntos_menor=5), _combinacion_desgaste(None, 0)],
        "reduccion_desgaste_min_pct": -3.0,
        "reduccion_desgaste_max_pct": 99.0,
        "combinaciones_con_menor_desgaste_en_todos_los_puntos": 0,
    }
    frases = tr.lectura_robustez_desgaste(resultado)
    assert "no reduce el desgaste" in frases[0]
    assert frases[1].startswith("Solo en 0 de 2 combinaciones")
    assert "(-3.0 %)" in frases[2]


def test_lectura_robustez_desgaste_sin_reducciones():
    resultado = {tr.CLAVE_COMBINACIONES: [_combinacion_desgaste(None, 0)]}
    frases = tr.lectura_robustez_desgaste(resultado)
    assert frases[0].startswith("No hay datos para calcular")
    assert len(frases) == 2


def test_lectura_robustez_desgaste_sin_combinaciones():
    assert tr.lectura_robustez_desgaste({}) == ["La robustez del desgaste no devolvió combinaciones."]


# ---------------------------------------------------------------------------
# Barrido frente a la incrustación diaria
# ---------------------------------------------------------------------------
def test_serie_barrido_por_incrustacion(barrido_real):
    serie = tr.serie_barrido_por_incrustacion(barrido_real)
    assert list(serie.columns) == tr.COLUMNAS_INCRUSTACION
    assert len(serie) == 12
    assert serie["incrustacion"].min() == pytest.approx(666.6, abs=0.1)


def test_serie_barrido_omite_puntos_sin_incrustacion_o_sin_recuperacion():
    sin_incrustacion = _punto_barrido(20.0, 88.0, 95.0)
    sin_recuperacion = {**_punto_barrido(40.0, None, 92.0), tr.CLAVE_INCRUSTACION: 1200.0}
    serie = tr.serie_barrido_por_incrustacion(_barrido(sin_incrustacion, sin_recuperacion))
    assert len(serie) == 1
    assert serie.iloc[0]["Modo"] == TEMPORIZADOR


def test_serie_barrido_vacia():
    assert tr.serie_barrido_por_incrustacion({}).empty


def test_incrustacion_cruce_del_barrido_real(barrido_real):
    assert tr.incrustacion_cruce(barrido_real) == pytest.approx(1789.12, abs=0.01)


def test_incrustacion_cruce_sin_campo():
    assert tr.incrustacion_cruce({}) is None


def test_lectura_cruce_con_datos_reales(barrido_real):
    frase = tr.lectura_cruce(barrido_real)
    assert frase.startswith("Cruza: el control basado en reglas pasa a recuperar más.")
    assert "1789 Ohm por día" in frase
    assert "55.9 Ohm por L/m²" in frase
    assert "Se interpola entre los niveles de 1290 y 1918 Ohm por día, separados 628" in frase


def test_lectura_cruce_sin_separacion_con_api_0_3_0():
    resultado = {CRUCE: {"estado": tr.ESTADO_INTERPOLADO, "incrustacion_diaria_ohm": 1700.0, tr.CLAVE_CARGA: 55.0}}
    frase = tr.lectura_cruce(resultado)
    assert frase.endswith("(carga salina de 55.0 Ohm por L/m²).")


def test_lectura_cruce_sin_valor():
    resultado = {CRUCE: {"estado": "SIN_DATOS", "incrustacion_diaria_ohm": None, tr.CLAVE_CARGA: None}}
    assert tr.lectura_cruce(resultado) == f"{tr.etiqueta_llana('SIN_DATOS')}."


def test_lectura_cruce_con_api_anterior():
    assert "0.3.0" in tr.lectura_cruce({})


def test_etiqueta_sitio():
    perfil = {"nombre": "CABO_DE_LA_VELA", "flujo_niebla_maximo_l_m2_h": 6.0}
    assert tr.etiqueta_sitio(perfil) == "CABO_DE_LA_VELA (6 L/m²/h)"


def test_configuracion_barrido_con_flujo():
    carga = tr.configuracion_barrido_con_flujo(85, 2, 1.83)
    assert carga["flujo_niebla_maximo_l_m2_h"] == pytest.approx(1.83)
    assert carga["semillas"] == [1, 2]


def test_configuracion_barrido_sin_flujo():
    assert "flujo_niebla_maximo_l_m2_h" not in tr.configuracion_barrido_con_flujo(85, 1, None)


# ---------------------------------------------------------------------------
# Dimensionamiento
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def dimensionamiento_real():
    """Dimensionamiento real para 50 personas en DIA_NORMAL con humedad inicial de 85 %."""
    cfg = DimensionamientoConfig(personas=50, escenario=Escenario.DIA_NORMAL, humedad_ambiente_inicial_pct=85.0)
    return ejecutar_dimensionamiento(cfg).model_dump(mode="json")


def test_configuracion_dimensionamiento():
    assert tr.configuracion_dimensionamiento(50, "OMS_20", "DIA_NORMAL", 85) == {
        "personas": 50,
        "estandar": "OMS_20",
        "escenario": "DIA_NORMAL",
        "humedad_ambiente_inicial_pct": 85.0,
    }


def test_estandares_de_consumo_usan_config():
    assert f"{config.CONSUMO_ACCESO_BASICO_L_PERSONA_DIA:g} L" in tr.ESTANDARES_CONSUMO["OMS_20"]


def test_resumen_dimensionamiento_con_datos_reales(dimensionamiento_real):
    frases = tr.resumen_dimensionamiento(dimensionamiento_real)
    assert frases[0] == "Consumo de 20 L por persona al día."
    assert "flujo supuesto (6 L/m²/h)" in frases[1]
    assert "32 nodos de 1 m²" in frases[1]
    assert "332 nodos" in frases[3]
    assert "entre 100.0 y 333.3 m²" in frases[4]


def test_resumen_dimensionamiento_sin_rendimiento_ni_literatura():
    resultado = {
        "consumo_l_persona_dia": 15.0,
        "dimensiones": [
            {
                "origen_flujo": "CALIBRADO_MIN",
                "flujo_niebla_maximo_l_m2_h": 0.49,
                "rendimiento_neuro_l_m2_dia": 0.0,
                "area_colector_m2": None,
                "nodos_requeridos": None,
            }
        ],
    }
    frases = tr.resumen_dimensionamiento(resultado)
    assert len(frases) == 2
    assert "no capta agua" in frases[1]


def test_resumen_dimensionamiento_sin_resultados():
    assert tr.resumen_dimensionamiento({}) == ["El dimensionamiento no devolvió resultados."]


# ---------------------------------------------------------------------------
# Explorador de hipótesis
# ---------------------------------------------------------------------------
SITIO_EXPLORADOR = {
    "nombre": "mi sitio-1",
    "flujo_niebla_maximo_l_m2_h": 2,
    "temperatura_media_c": 25,
    "amplitud_temperatura_c": 5,
    "amplitud_humedad_pct": 12,
}


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("mi sitio-1", "MI_SITIO_1"),
        ("  ", tr.NOMBRE_SITIO_POR_DEFECTO),
        ("ñandú", "_AND_"),
        ("A" * 50, "A" * 40),
    ],
)
def test_normalizar_nombre_sitio(texto, esperado):
    assert tr.normalizar_nombre_sitio(texto) == esperado


def test_configuracion_explorador():
    carga = tr.configuracion_explorador("DIA_NORMAL", "ALTA", 85, 0.95, SITIO_EXPLORADOR)
    assert carga["duracion_horas"] == 24
    assert carga["eficacia_maxima_pulso"] == pytest.approx(0.95)
    assert carga["sitio"]["nombre"] == "MI_SITIO_1"
    assert isinstance(carga["sitio"]["flujo_niebla_maximo_l_m2_h"], float)
    assert set(carga["sitio"]) == set(tr.CAMPOS_SITIO)


def test_configuracion_calibracion():
    carga = tr.configuracion_calibracion(10, "DIA_NORMAL", 85, SITIO_EXPLORADOR)
    assert carga["rendimiento_objetivo_l_m2_dia"] == pytest.approx(10.0)
    assert carga["escenario"] == "DIA_NORMAL"
    assert carga["humedad_ambiente_inicial_pct"] == pytest.approx(85.0)
    assert carga["sitio"] == tr.configuracion_explorador("DIA_NORMAL", "ALTA", 85, 0.9, SITIO_EXPLORADOR)["sitio"]


def test_texto_calibracion():
    resultado = {
        "flujo_calibrado_l_m2_h": 1.8026,
        "rendimiento_obtenido_l_m2_dia": 10.0016,
        "perfil": {"nombre": "SITIO_VERIFICACION"},
    }
    texto = tr.texto_calibracion(resultado)
    assert texto.startswith("Flujo calibrado para SITIO_VERIFICACION: 1.8026 L/m²/h.")
    assert "rinde 10.00 L/m² al día" in texto


def test_texto_calibracion_sin_perfil():
    texto = tr.texto_calibracion({"flujo_calibrado_l_m2_h": 0.5, "rendimiento_obtenido_l_m2_dia": 3.0})
    assert "para el sitio" in texto


def test_parametros_usados_a_dataframe(resultado):
    tabla = tr.parametros_usados_a_dataframe(resultado)
    assert len(tabla) == 6
    assert tabla.iloc[0]["Valor"] == "CABO_DE_LA_VELA"


def test_parametros_usados_sin_campo():
    tabla = tr.parametros_usados_a_dataframe({})
    assert tabla.empty
    assert list(tabla.columns) == ["Parámetro", "Valor"]


@pytest.fixture(scope="module")
def incertidumbre_explorador():
    """Incertidumbre real en INCRUSTACION_SALINA_RAPIDA con 5 muestras."""
    return _incertidumbre_real(Escenario.INCRUSTACION_SALINA_RAPIDA, 5)


def test_hipotesis_siguientes_sin_analisis():
    preguntas = tr.hipotesis_siguientes(None, None, None)
    assert len(preguntas) == 3
    assert "vista 4, parte a" in preguntas[0]
    assert "vista 4, parte c" in preguntas[1]
    assert "vista 5" in preguntas[2]


def test_hipotesis_siguientes_con_datos_reales(robustez_real, incertidumbre_explorador, resultado_prd):
    preguntas = tr.hipotesis_siguientes(robustez_real, incertidumbre_explorador, resultado_prd)
    assert "1633 a 1839 Ohm por día en 6 de 9 combinaciones" in preguntas[0]
    assert "proporción de 0.00" in preguntas[1]
    assert "En CABO_DE_LA_VELA, el control basado en reglas rinde 10.21 L/m² al día" in preguntas[2]
    assert "160 a 183 Ohm por L/m²" in preguntas[2]
    assert "Con una eficacia de 0.90" in preguntas[3]


def test_hipotesis_siguientes_sin_cruce_ni_muestras_ni_agua():
    robustez = {tr.CLAVE_COMBINACIONES: [_combinacion("SIN_DATOS")], "combinaciones_con_cruce": 0}
    incertidumbre = {"probabilidad_ventaja_recuperacion": None}
    simulacion = {"impacto_comunitario": {tr.MODO_NEURO: {"rendimiento_l_m2_dia": 0.0}}}
    preguntas = tr.hipotesis_siguientes(robustez, incertidumbre, simulacion)
    assert preguntas[0].startswith("Ninguna de las 1 combinaciones cruza")
    assert preguntas[1].startswith("Ninguna muestra de la incertidumbre")
    assert "el sitio simulado" in preguntas[2]
    assert "no captó agua" in preguntas[2]
    assert len(preguntas) == 3


def test_hipotesis_siguientes_sin_pregunta_de_eficacia_si_se_validan():
    simulacion = {
        "conjeturas_validadas": {"conjetura_1_eficiencia": True, "conjetura_2_autorreparacion": True},
        "parametros_usados": {"eficacia_maxima_pulso": 0.97, "nombre_sitio": "SITIO"},
        "impacto_comunitario": {},
    }
    assert len(tr.hipotesis_siguientes(None, None, simulacion)) == 3


def test_frase_ventaja_con_datos_reales(incertidumbre_explorador):
    frase = tr.frase_ventaja_incertidumbre(incertidumbre_explorador)
    assert "en 0 de 5 muestras con pulsos en ambos modos (probabilidad 0.00)" in frase
    assert "entre los percentiles 5 y 95" in frase


def test_frase_ventaja_sin_campo():
    assert tr.frase_ventaja_incertidumbre({}) is None


def test_frase_ventaja_sin_muestras_con_pulsos():
    frase = tr.frase_ventaja_incertidumbre({"probabilidad_ventaja_recuperacion": None})
    assert frase.startswith("Ninguna muestra tiene pulsos en ambos modos")


def test_frase_ventaja_sin_resumen():
    resultado = {
        "probabilidad_ventaja_recuperacion": 1.0,
        tr.CLAVE_MUESTRAS: [{"ventaja_recuperacion_pts": 2.0}, {"ventaja_recuperacion_pts": None}],
    }
    frase = tr.frase_ventaja_incertidumbre(resultado)
    assert "en 1 de 1 muestras" in frase
    assert "percentiles" not in frase


# ---------------------------------------------------------------------------
# Nombre visible único del modo de control
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def barrido_sin_cruce():
    """Barrido sintético en que el temporizador recupera más y no hay reducción del desgaste."""
    return _barrido(_punto_barrido(20.0, 88.0, 95.0, reduccion=None))


@pytest.fixture(scope="module")
def impacto_sintetico():
    """Respuesta con impacto comunitario mínimo, con el temporizador como comparación."""
    return _respuesta_impacto(3.0)


@pytest.mark.parametrize(
    ("funcion", "nombre_fixture"),
    [
        (tr.resumen_ejecutivo, "resultado_prd"),
        (tr.resumen_ejecutivo, "resultado"),
        (tr.lectura_barrido, "barrido_real"),
        (tr.lectura_barrido, "barrido_sin_cruce"),
        (tr.resumen_impacto, "resultado_prd"),
        (tr.resumen_impacto, "impacto_sintetico"),
    ],
)
def test_frases_visibles_no_usan_el_nombre_neuro_simbolico(funcion, nombre_fixture, request):
    texto = " ".join(funcion(request.getfixturevalue(nombre_fixture)))
    assert "neuro-simbólico" not in texto.casefold()
