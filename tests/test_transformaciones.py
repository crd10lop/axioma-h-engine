"""Pruebas de las transformaciones del dashboard."""

import pandas as pd
import pytest

from backend.schemas import Escenario, SimulationConfig, TasaSalinizacion
from backend.simulador import ejecutar_simulacion
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
    assert len(df) == len(verificacion["indicadores"])
    assert set(df["Cumple"]) <= {"Sí", "No"}
    assert all(isinstance(valor, str) for valor in df["Valor obtenido"])


def test_indicadores_informativos_junto_al_tiempo_de_regeneracion(resultado):
    verificacion = resultado["detalle_verificacion"]["conjetura_2_autorreparacion"]
    df = tr.indicadores_a_dataframe(verificacion)
    nombres = list(df["Indicador"])
    posicion = nombres.index("Tiempo promedio de regeneración (s)")
    assert nombres[posicion + 1 : posicion + 3] == [
        "Pulsos regenerados (informativo)",
        "Pulsos totales (informativo)",
    ]
    informativos = df[df["Cumple"] == "Informativo"]
    assert list(informativos["Umbral"]) == ["No aplica", "No aplica"]
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


def test_bitacora_a_texto_con_filtros(resultado):
    bitacora = resultado["bitacora"]
    texto = tr.bitacora_a_texto(bitacora)
    assert len(texto.splitlines()) == len(bitacora)
    assert texto.startswith("[Día 1 18:00]")

    solo_nodo = tr.bitacora_a_texto(bitacora, nodo="NODO_03")
    assert solo_nodo and all("NODO_03" in linea for linea in solo_nodo.splitlines())

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
