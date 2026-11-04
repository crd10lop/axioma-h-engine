"""Pruebas de las transformaciones del dashboard."""

import copy

import pandas as pd
import pytest

from backend.analisis import ejecutar_barrido
from backend.schemas import BarridoConfig, CausaNoValidacion, Escenario, SimulationConfig, TasaSalinizacion
from backend.simulador import ejecutar_simulacion
from frontend import config
from frontend import transformaciones as tr


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
    assert set(largo["Modo"]) == {"Neuro-simbólico", "Temporizador fijo"}
    ultimo_neuro = largo[largo["Modo"] == "Neuro-simbólico"]["valor"].iloc[-1]
    assert ultimo_neuro == pytest.approx(df["litros_acumulados_neuro"].iloc[-1])


def test_comparativa_a_dataframe(resultado):
    df = tr.comparativa_a_dataframe(resultado)
    assert list(df["clave"]) == [clave for clave, _, _ in tr.METRICAS_COMPARATIVA]
    fila = df[df["clave"] == "litros_totales_agua"].iloc[0]
    neuro = resultado["comparativa"]["modo_neuro_simbolico"]["litros_totales_agua"]
    temporizador = resultado["comparativa"]["modo_temporizador_fijo"]["litros_totales_agua"]
    assert fila["Neuro-simbólico"] == neuro
    assert fila["Diferencia (%)"] == pytest.approx((neuro - temporizador) / temporizador * 100.0)


def test_totales_a_dataframe(resultado):
    df = tr.totales_a_dataframe(resultado)
    assert len(df) == 6
    assert set(df["Modo"]) == {"Neuro-simbólico", "Temporizador fijo"}
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
    assert pd.isna(fila["Neuro-simbólico"])
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
        "Desde una carga salina de 60 Ohm por L/m², la recuperación del neuro-simbólico "
        "supera a la del temporizador."
    )
    assert frases[1] == (
        "La reducción del desgaste del neuro-simbólico frente al temporizador va de 73.9 % a 99.0 %."
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
    assert agua.startswith("Agua: el neuro-simbólico captó 81.7 L, 32.2 % menos que el temporizador (120.4 L).")
    assert "28.6 L (73.9 %) se deben al tope ecológico de 33 %" in agua
    assert desgaste == (
        "Desgaste: la degradación de la membrana fue 0.048 % con el neuro-simbólico y "
        "2.906 % con el temporizador (98.4 % menos)."
    )
    assert energia == "Energía: el neuro-simbólico consumió 323.2 Wh, 69.7 % menos que el temporizador (1065.1 Wh)."
    assert violaciones == "Límite ecológico: 0 violaciones del neuro-simbólico y 8 del temporizador."
    assert conjeturas == "Conjeturas validadas: 0 de 3."


def test_resumen_ejecutivo_nombra_las_conjeturas_validadas(resultado_prd):
    modificado = copy.deepcopy(resultado_prd)
    modificado["conjeturas_validadas"]["conjetura_3_saber_territorial"] = True
    assert tr.resumen_ejecutivo(modificado)[-1] == "Conjeturas validadas: 1 de 3 (C3)."


def test_resumen_ejecutivo_sin_modo_de_referencia(resultado_prd):
    antiguo = copy.deepcopy(resultado_prd)
    antiguo["comparativa"].pop(tr.MODO_REFERENCIA)
    agua = tr.resumen_ejecutivo(antiguo)[0]
    assert agua == "Agua: el neuro-simbólico captó 81.7 L, 32.2 % menos que el temporizador (120.4 L)."


@pytest.mark.parametrize(
    ("valor", "referencia", "esperado"),
    [(110.0, 100.0, "10.0 % más"), (90.0, 100.0, "10.0 % menos"), (100.0, 100.0, "lo mismo"), (5.0, 0.0, "lo mismo")],
)
def test_variacion(valor, referencia, esperado):
    assert tr._variacion(valor, referencia) == esperado
