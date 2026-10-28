"""Pruebas de los endpoints de la API."""

from fastapi.testclient import TestClient

from backend.main import app

cliente = TestClient(app)

PAYLOAD_TELEMETRIA_PRD = {
    "nodo_id": "NODO_04",
    "impedancia_ohms": 1850.5,
    "temperatura_celsius": 38.2,
    "reserva_calor_pct": 65.0,
    "humedad_relativa_pct": 82.0,
    "flujo_actual_ml_min": 12.5,
    "modo_operacion": "NEURO_SIMBOLICO",
}

PAYLOAD_SIMULACION_PRD = {
    "duracion_horas": 24,
    "escenario": "TORMENTA_DE_SAL_Y_CALOR_EXTREMO",
    "humedad_ambiente_inicial_pct": 85.0,
    "tasa_salinizacion": "ALTA",
}


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
    assert datos["temperatura_objetivo_c"] == 44.0
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
    assert set(datos["comparativa"]) == {"modo_neuro_simbolico", "modo_temporizador_fijo"}
    assert set(datos["conjeturas_validadas"]) == {
        "conjetura_1_eficiencia",
        "conjetura_2_autorreparacion",
        "conjetura_3_saber_territorial",
    }
    assert all(isinstance(v, bool) for v in datos["conjeturas_validadas"].values())
    assert len(datos["series_temporales"]) == 24 * 60 // 5
    assert datos["bitacora"]


def test_ejecutar_simulacion_escenario_invalido_devuelve_422():
    payload = {**PAYLOAD_SIMULACION_PRD, "escenario": "HURACAN"}
    assert cliente.post("/api/v1/simulacion/ejecutar", json=payload).status_code == 422
