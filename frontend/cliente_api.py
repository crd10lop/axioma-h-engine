"""Cliente HTTP de la API del motor Axioma-H."""

from typing import Any, Optional

import requests

from frontend import config


class ErrorApiAxioma(Exception):
    """Error al comunicarse con la API, con un mensaje apto para la interfaz."""

    def __init__(self, mensaje: str, codigo_estado: Optional[int] = None, detalle: Optional[list] = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo_estado = codigo_estado
        self.detalle = detalle or []


def _formatear_errores_validacion(detalle: Any) -> list:
    """Convierte el detalle de un error 422 de FastAPI en líneas legibles."""
    if not isinstance(detalle, list):
        return [str(detalle)]
    lineas = []
    for error in detalle:
        if isinstance(error, dict):
            ubicacion = ".".join(str(parte) for parte in error.get("loc", []) if parte != "body")
            lineas.append(f"{ubicacion or 'solicitud'}: {error.get('msg', 'valor no válido')}")
        else:
            lineas.append(str(error))
    return lineas


def _solicitar(metodo: str, ruta: str, timeout: float, cuerpo: Optional[dict] = None) -> dict:
    """Ejecuta una solicitud y devuelve el cuerpo JSON, o lanza ErrorApiAxioma."""
    url = f"{config.API_URL}{ruta}"
    try:
        respuesta = requests.request(metodo, url, json=cuerpo, timeout=timeout)
    # Timeout se captura antes que ConnectionError porque ConnectTimeout hereda de ambas.
    except requests.exceptions.Timeout as error:
        raise ErrorApiAxioma(
            f"La API no respondió en {timeout} s ({url}). Intente de nuevo o reduzca la duración simulada."
        ) from error
    except requests.exceptions.ConnectionError as error:
        raise ErrorApiAxioma(
            f"No fue posible conectar con la API en {config.API_URL}. "
            f"Verifique que el backend esté en ejecución: {config.COMANDO_BACKEND}"
        ) from error
    except requests.exceptions.RequestException as error:
        raise ErrorApiAxioma(f"Error de comunicación con la API: {error}") from error

    if respuesta.status_code == 422:
        try:
            detalle = _formatear_errores_validacion(respuesta.json().get("detail"))
        except ValueError:
            detalle = [respuesta.text]
        raise ErrorApiAxioma(
            "La API rechazó los datos enviados por no superar la validación.",
            codigo_estado=422,
            detalle=detalle,
        )
    if not respuesta.ok:
        raise ErrorApiAxioma(
            f"La API respondió con el código {respuesta.status_code} en {ruta}.",
            codigo_estado=respuesta.status_code,
            detalle=[respuesta.text[:500]] if respuesta.text else [],
        )
    try:
        return respuesta.json()
    except ValueError as error:
        raise ErrorApiAxioma(
            f"La respuesta de {ruta} no es JSON válido.", codigo_estado=respuesta.status_code
        ) from error


def verificar_salud() -> dict:
    """Consulta GET /api/v1/health."""
    return _solicitar("GET", "/api/v1/health", config.TIMEOUT_EVALUACION_SEG)


def evaluar_nodo(telemetria: dict) -> dict:
    """Envía una lectura de telemetría a POST /api/v1/nodo/evaluar."""
    return _solicitar("POST", "/api/v1/nodo/evaluar", config.TIMEOUT_EVALUACION_SEG, telemetria)


def ejecutar_simulacion(configuracion: dict) -> dict:
    """Ejecuta una simulación comparativa en POST /api/v1/simulacion/ejecutar."""
    return _solicitar("POST", "/api/v1/simulacion/ejecutar", config.TIMEOUT_SIMULACION_SEG, configuracion)
