"""Pruebas de los endpoints de la API."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

cliente = TestClient(app)

PAYLOAD_TELEMETRIA_PRD = {
    "nodo_id": "NODO_04",
    "impedancia_ohms": 1650.5,
    "temperatura_celsius": 36.2,
    "reserva_calor_pct": 55.0,
    "humedad_relativa_pct": 42.0,
    "flujo_actual_ml_min": 14.5,
    "modo_operacion": "NEURO_SIMBOLICO",
}

PAYLOAD_SIMULACION_PRD = {
    "duracion_horas": 24,
    "escenario": "TORMENTA_DE_SAL_Y_CALOR_EXTREMO",
    "humedad_ambiente_inicial_pct": 45.0,
    "tasa_salinizacion": "ALTA",
}

CAMPOS_RESULTADO_MODO = {
    "litros_totales_agua",
    "pulsos_termicos_ejecutados",
    "consumo_energia_wh",
    "integridad_membrana_final_pct",
    "violaciones_ecologicas",
    "recuperacion_caudal_promedio_pct",
    "degradacion_acumulada_pct",
}
CONJETURAS = {"conjetura_1_eficiencia", "conjetura_2_autorreparacion", "conjetura_3_saber_territorial"}
MODOS_COMPARATIVA = {"modo_neuro_simbolico", "modo_temporizador_fijo", "modo_temporizador_tope_ecologico"}


def test_raiz():
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "OPERATIVO"
    assert datos["documentacion"] == "/docs"


def test_salud():
    respuesta = cliente.get("/api/v1/health")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "SALUDABLE"
    assert datos["tiempo_actividad_seg"] >= 0


def test_evaluar_nodo_valido():
    respuesta = cliente.post("/api/v1/nodo/evaluar", json=PAYLOAD_TELEMETRIA_PRD)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["regla_activada"] == "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA"
    assert datos["temperatura_objetivo_c"] == pytest.approx(44.0)
    assert datos["pulso_termico_activo"] is True
    assert set(datos["metricas_conjeturas"]) == {
        "eficiencia_energetica_pct",
        "recuperacion_hidraulica_pct",
        "preservacion_ecologica_ok",
    }


def test_evaluar_nodo_invalido_devuelve_422():
    invalidos = [
        {**PAYLOAD_TELEMETRIA_PRD, "nodo_id": "NODO_09"},
        {**PAYLOAD_TELEMETRIA_PRD, "impedancia_ohms": 0},
        {**PAYLOAD_TELEMETRIA_PRD, "humedad_relativa_pct": 120},
        {**PAYLOAD_TELEMETRIA_PRD, "modo_operacion": "MANUAL"},
        {key: value for key, value in PAYLOAD_TELEMETRIA_PRD.items() if key != "temperatura_celsius"},
    ]
    for payload in invalidos:
        assert cliente.post("/api/v1/nodo/evaluar", json=payload).status_code == 422


def test_ejecutar_simulacion_payload_prd():
    respuesta = cliente.post("/api/v1/simulacion/ejecutar", json=PAYLOAD_SIMULACION_PRD)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert set(datos["comparativa"]) == MODOS_COMPARATIVA
    assert set(datos["conjeturas_validadas"]) == {
        "conjetura_1_eficiencia",
        "conjetura_2_autorreparacion",
        "conjetura_3_saber_territorial",
    }
    assert all(isinstance(v, bool) for v in datos["conjeturas_validadas"].values())
    assert len(datos["series_temporales"]) == 24 * 60 // 5
    assert datos["bitacora"]


def test_simulacion_payload_prd_estructura_completa():
    """Ejecuta el payload exacto del PRD y valida la estructura, no los valores ilustrativos."""
    respuesta = cliente.post("/api/v1/simulacion/ejecutar", json=PAYLOAD_SIMULACION_PRD)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert set(datos) == {
        "comparativa",
        "conjeturas_validadas",
        "detalle_verificacion",
        "series_temporales",
        "bitacora",
    }

    for modo in MODOS_COMPARATIVA:
        resultado_modo = datos["comparativa"][modo]
        assert set(resultado_modo) == CAMPOS_RESULTADO_MODO
        assert isinstance(resultado_modo["pulsos_termicos_ejecutados"], int)
        assert isinstance(resultado_modo["violaciones_ecologicas"], int)
        for campo in ("litros_totales_agua", "consumo_energia_wh", "integridad_membrana_final_pct"):
            assert isinstance(resultado_modo[campo], (int, float))

    assert set(datos["conjeturas_validadas"]) == CONJETURAS
    assert set(datos["detalle_verificacion"]) == CONJETURAS
    for nombre, verificacion in datos["detalle_verificacion"].items():
        assert verificacion["validada"] == datos["conjeturas_validadas"][nombre]
        assert verificacion["indicadores"]
        for indicador in verificacion["indicadores"].values():
            assert set(indicador) == {"valor", "umbral", "operador", "cumple"}
            assert isinstance(indicador["cumple"], bool)
        assert isinstance(verificacion["causas_no_validacion"], list)
    informativos = datos["detalle_verificacion"]["conjetura_2_autorreparacion"]["indicadores_informativos"]
    assert set(informativos) == {
        "pulsos_regenerados",
        "pulsos_totales",
        "tiempo_desprendimiento_t95_promedio_seg",
        "impedancia_promedio_tras_pulso_ohms",
    }
    assert isinstance(informativos["pulsos_regenerados"], int)
    assert isinstance(informativos["pulsos_totales"], int)

    # 24 h con paso de 5 min.
    assert len(datos["series_temporales"]) == 288
    assert set(datos["series_temporales"][0]) == {
        "minuto",
        "humedad_relativa_pct",
        "temperatura_c",
        "impedancia_promedio_neuro_ohms",
        "impedancia_promedio_temporizador_ohms",
        "litros_acumulados_neuro",
        "litros_acumulados_temporizador",
        "energia_acumulada_neuro_wh",
        "energia_acumulada_temporizador_wh",
        "integridad_promedio_neuro_pct",
        "integridad_promedio_temporizador_pct",
    }
    assert datos["bitacora"]
    assert set(datos["bitacora"][0]) == {"minuto", "nodo_id", "regla_activada", "motivo"}


def test_ejecutar_simulacion_escenario_invalido_devuelve_422():
    payload = {**PAYLOAD_SIMULACION_PRD, "escenario": "HURACAN"}
    assert cliente.post("/api/v1/simulacion/ejecutar", json=payload).status_code == 422


# ---------------------------------------------------------------------------
# Análisis de robustez
# ---------------------------------------------------------------------------
RUTA_BARRIDO = "/api/v1/analisis/barrido-salinidad"
RUTA_SENSIBILIDAD = "/api/v1/analisis/sensibilidad"
PAYLOAD_SENSIBILIDAD = {
    "escenario": "DIA_NORMAL",
    "humedad_ambiente_inicial_pct": 85.0,
    "tasa_salinizacion": "ALTA",
    "parametro": "EFICACIA_MAXIMA_PULSO",
    "valores": [0.90, 0.94],
}


def test_barrido_salinidad():
    respuesta = cliente.post(RUTA_BARRIDO, json={"semillas": [42]})
    assert respuesta.status_code == 200
    puntos = respuesta.json()["puntos"]
    cargas = [punto["carga_salina_ohm_l_m2"] for punto in puntos]
    assert cargas == sorted(cargas)
    assert len(puntos) == 6
    assert puntos[0]["recuperacion_neuro_media"] == pytest.approx(88.85, abs=0.01)


def test_sensibilidad():
    respuesta = cliente.post(RUTA_SENSIBILIDAD, json=PAYLOAD_SENSIBILIDAD)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["parametro"] == "EFICACIA_MAXIMA_PULSO"
    estados = [punto["conjeturas_validadas"]["conjetura_1_eficiencia"] for punto in datos["puntos"]]
    assert estados == [False, True]


@pytest.mark.parametrize("semillas", [[1, 1], [1, 2, 3, 4, 5, 6], []])
def test_barrido_rechaza_semillas_invalidas(semillas):
    assert cliente.post(RUTA_BARRIDO, json={"semillas": semillas}).status_code == 422


@pytest.mark.parametrize("valor", [0.0, 1.2])
def test_sensibilidad_rechaza_eficacia_fuera_de_rango(valor):
    payload = {**PAYLOAD_SENSIBILIDAD, "valores": [valor]}
    assert cliente.post(RUTA_SENSIBILIDAD, json=payload).status_code == 422


def test_endpoints_de_analisis_publicados_en_openapi():
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert RUTA_BARRIDO in rutas
    assert RUTA_SENSIBILIDAD in rutas
