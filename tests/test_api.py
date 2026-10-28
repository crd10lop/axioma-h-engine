"""Pruebas de los endpoints de la API."""

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
}
CONJETURAS = {"conjetura_1_eficiencia", "conjetura_2_autorreparacion", "conjetura_3_saber_territorial"}


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

    for modo in ("modo_neuro_simbolico", "modo_temporizador_fijo"):
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
    informativos = datos["detalle_verificacion"]["conjetura_2_autorreparacion"]["indicadores_informativos"]
    assert set(informativos) == {"pulsos_regenerados", "pulsos_totales"}
    assert all(isinstance(valor, int) for valor in informativos.values())

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
