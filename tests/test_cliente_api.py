"""Pruebas del cliente HTTP del dashboard con requests simulado."""

from unittest import mock

import pytest
import requests

from frontend import cliente_api, config

TELEMETRIA = {
    "nodo_id": "NODO_04",
    "impedancia_ohms": 1650.5,
    "temperatura_celsius": 36.2,
    "reserva_calor_pct": 55.0,
    "humedad_relativa_pct": 42.0,
    "flujo_actual_ml_min": 14.5,
    "modo_operacion": "NEURO_SIMBOLICO",
}


def respuesta_simulada(codigo: int, cuerpo=None, texto: str = ""):
    """Construye un objeto de respuesta con la interfaz usada por el cliente."""
    respuesta = mock.Mock()
    respuesta.status_code = codigo
    respuesta.ok = 200 <= codigo < 400
    respuesta.text = texto
    if cuerpo is None:
        respuesta.json.side_effect = ValueError("sin JSON")
    else:
        respuesta.json.return_value = cuerpo
    return respuesta


@pytest.fixture
def request_simulado():
    with mock.patch("frontend.cliente_api.requests.request") as simulado:
        yield simulado


def test_verificar_salud_exitosa(request_simulado):
    request_simulado.return_value = respuesta_simulada(200, {"estado": "SALUDABLE"})
    assert cliente_api.verificar_salud() == {"estado": "SALUDABLE"}
    request_simulado.assert_called_once_with(
        "GET", f"{config.API_URL}/api/v1/health", json=None, timeout=config.TIMEOUT_EVALUACION_SEG
    )


def test_evaluar_nodo_exitoso(request_simulado):
    decision = {"regla_activada": "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA"}
    request_simulado.return_value = respuesta_simulada(200, decision)
    assert cliente_api.evaluar_nodo(TELEMETRIA) == decision
    request_simulado.assert_called_once_with(
        "POST", f"{config.API_URL}/api/v1/nodo/evaluar", json=TELEMETRIA, timeout=config.TIMEOUT_EVALUACION_SEG
    )


def test_ejecutar_simulacion_usa_timeout_largo(request_simulado):
    request_simulado.return_value = respuesta_simulada(200, {"comparativa": {}})
    carga = {"escenario": "DIA_NORMAL", "humedad_ambiente_inicial_pct": 85.0, "tasa_salinizacion": "ALTA"}
    cliente_api.ejecutar_simulacion(carga)
    _, kwargs = request_simulado.call_args
    assert kwargs["timeout"] == config.TIMEOUT_SIMULACION_SEG == 60
    assert kwargs["json"] == carga


def test_error_de_conexion(request_simulado):
    request_simulado.side_effect = requests.exceptions.ConnectionError("rechazada")
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.verificar_salud()
    assert "No fue posible conectar" in error.value.mensaje
    assert "uvicorn backend.main:app" in error.value.mensaje
    assert error.value.codigo_estado is None


def test_timeout(request_simulado):
    request_simulado.side_effect = requests.exceptions.ReadTimeout("lento")
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.ejecutar_simulacion({"escenario": "SEQUIA"})
    assert "no respondió en 60 s" in error.value.mensaje


def test_timeout_de_conexion_se_reporta_como_timeout(request_simulado):
    request_simulado.side_effect = requests.exceptions.ConnectTimeout("lento")
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.verificar_salud()
    assert "no respondió" in error.value.mensaje


def test_respuesta_422_incluye_detalle(request_simulado):
    cuerpo = {
        "detail": [
            {"loc": ["body", "nodo_id"], "msg": "String should match pattern '^NODO_0[1-8]$'", "type": "x"},
            {"loc": ["body", "humedad_relativa_pct"], "msg": "Input should be less than or equal to 100", "type": "y"},
        ]
    }
    request_simulado.return_value = respuesta_simulada(422, cuerpo)
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.evaluar_nodo({**TELEMETRIA, "nodo_id": "NODO_09"})
    assert error.value.codigo_estado == 422
    assert "validación" in error.value.mensaje
    assert error.value.detalle == [
        "nodo_id: String should match pattern '^NODO_0[1-8]$'",
        "humedad_relativa_pct: Input should be less than or equal to 100",
    ]


def test_error_http_generico(request_simulado):
    request_simulado.return_value = respuesta_simulada(500, texto="Internal Server Error")
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.verificar_salud()
    assert error.value.codigo_estado == 500
    assert "500" in error.value.mensaje
    assert error.value.detalle == ["Internal Server Error"]


def test_respuesta_sin_json(request_simulado):
    request_simulado.return_value = respuesta_simulada(200, None, texto="<html>")
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.verificar_salud()
    assert "no es JSON" in error.value.mensaje


def test_api_url_se_toma_del_entorno(monkeypatch):
    import importlib

    monkeypatch.setenv("AXIOMA_API_URL", "http://servidor:9000/")
    try:
        recargado = importlib.reload(config)
        assert recargado.API_URL == "http://servidor:9000"
    finally:
        monkeypatch.delenv("AXIOMA_API_URL")
        importlib.reload(config)
