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
        "GET", f"{config.API_URL}/api/v1/health", json=None, timeout=config.TIMEOUT_SALUD_SEG
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


def test_respuesta_422_con_detalle_que_no_es_lista(request_simulado):
    request_simulado.return_value = respuesta_simulada(422, {"detail": "Cuerpo de la solicitud inválido"})
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.evaluar_nodo(TELEMETRIA)
    assert error.value.codigo_estado == 422
    assert error.value.detalle == ["Cuerpo de la solicitud inválido"]


def test_respuesta_422_con_errores_sin_formato_de_fastapi(request_simulado):
    cuerpo = {"detail": [{"loc": ["body"], "msg": "JSON mal formado"}, "error sin estructura"]}
    request_simulado.return_value = respuesta_simulada(422, cuerpo)
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.evaluar_nodo(TELEMETRIA)
    assert error.value.detalle == ["solicitud: JSON mal formado", "error sin estructura"]


def test_respuesta_422_sin_json_usa_el_texto(request_simulado):
    request_simulado.return_value = respuesta_simulada(422, None, texto="Unprocessable Entity")
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.evaluar_nodo(TELEMETRIA)
    assert error.value.codigo_estado == 422
    assert error.value.detalle == ["Unprocessable Entity"]


def test_error_de_comunicacion_generico(request_simulado):
    request_simulado.side_effect = requests.exceptions.TooManyRedirects("demasiadas redirecciones")
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.verificar_salud()
    assert error.value.mensaje == "Error de comunicación con la API: demasiadas redirecciones"
    assert error.value.codigo_estado is None
    assert isinstance(error.value.__cause__, requests.exceptions.TooManyRedirects)


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


@pytest.mark.parametrize(
    ("funcion", "ruta"),
    [
        (cliente_api.ejecutar_barrido, "/api/v1/analisis/barrido-salinidad"),
        (cliente_api.ejecutar_sensibilidad, "/api/v1/analisis/sensibilidad"),
        (cliente_api.ejecutar_incertidumbre, "/api/v1/analisis/incertidumbre"),
    ],
)
def test_analisis_usa_su_ruta_y_timeout(request_simulado, funcion, ruta):
    cuerpo = {"puntos": []}
    request_simulado.return_value = respuesta_simulada(200, cuerpo)
    carga = {"semillas": [1, 2]}
    assert funcion(carga) == cuerpo
    request_simulado.assert_called_once_with(
        "POST", f"{config.API_URL}{ruta}", json=carga, timeout=config.TIMEOUT_ANALISIS_SEG
    )


def test_analisis_con_semillas_repetidas_reporta_422(request_simulado):
    detalle = [{"loc": ["body", "semillas"], "msg": "Value error, Las semillas no deben repetirse."}]
    request_simulado.return_value = respuesta_simulada(422, {"detail": detalle})
    with pytest.raises(cliente_api.ErrorApiAxioma) as error:
        cliente_api.ejecutar_barrido({"semillas": [1, 1]})
    assert error.value.codigo_estado == 422
    assert error.value.detalle == ["semillas: Value error, Las semillas no deben repetirse."]


def test_timeout_de_analisis_mayor_que_el_de_simulacion():
    assert config.TIMEOUT_ANALISIS_SEG > config.TIMEOUT_SIMULACION_SEG
