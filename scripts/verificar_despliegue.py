"""Verificación del despliegue público de Axioma-H Engine.

Ejecuta un conjunto de comprobaciones contra la API y el dashboard publicados
en Render y resume el resultado en una tabla. Termina con código 0 si todas
las comprobaciones pasan y con código 1 si alguna falla.

Uso:
    python scripts/verificar_despliegue.py [--api URL] [--dashboard URL] [--timeout SEG]

Este script depende de la red y no forma parte de la suite de pytest.
"""

import argparse
import importlib
import math
import os
import sys
import time
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Callable, List, Optional
from urllib.parse import urlsplit

import httpx

# Permite importar el paquete frontend al ejecutar el script desde cualquier directorio.
RAIZ_REPOSITORIO = Path(__file__).resolve().parent.parent
if str(RAIZ_REPOSITORIO) not in sys.path:
    sys.path.insert(0, str(RAIZ_REPOSITORIO))

API_POR_DEFECTO = "https://axioma-h-api.onrender.com"
DASHBOARD_POR_DEFECTO = "https://axioma-h-dashboard.onrender.com"
# El plan gratuito de Render suspende los servicios y la reactivación tarda cerca de un minuto.
TIMEOUT_POR_DEFECTO_SEG = 90.0

RUTA_SALUD = "/api/v1/health"
RUTA_EVALUAR = "/api/v1/nodo/evaluar"
RUTA_SIMULACION = "/api/v1/simulacion/ejecutar"
RUTA_BARRIDO = "/api/v1/analisis/barrido-salinidad"
RUTA_SENSIBILIDAD = "/api/v1/analisis/sensibilidad"
RUTA_INCERTIDUMBRE = "/api/v1/analisis/incertidumbre"
RUTA_ROBUSTEZ = "/api/v1/analisis/robustez-respuesta"
RUTA_DIMENSIONAMIENTO = "/api/v1/analisis/dimensionamiento"
RUTA_SITIOS = "/api/v1/sitios"
RUTA_ROBUSTEZ_DESGASTE = "/api/v1/analisis/robustez-desgaste"
RUTA_CALIBRACION = "/api/v1/analisis/calibracion"
RUTA_IMPACTO_ENTORNOS = "/api/v1/analisis/impacto-entornos"

# Una sola semilla mantiene el barrido (12 simulaciones) dentro del tiempo de espera.
BARRIDO_EJEMPLO = {"humedad_ambiente_inicial_pct": 85.0, "semillas": [42]}
PUNTOS_BARRIDO = 6

# Ejemplo del esquema SensibilidadConfig en backend/schemas.py.
# Condiciones comunes de los ejemplos de sensibilidad e incertidumbre.
CONDICIONES_ANALISIS = {
    "escenario": "DIA_NORMAL",
    "humedad_ambiente_inicial_pct": 85.0,
    "tasa_salinizacion": "ALTA",
}
SENSIBILIDAD_EJEMPLO = {
    **CONDICIONES_ANALISIS,
    "parametro": "EFICACIA_MAXIMA_PULSO",
    "valores": [0.90, 0.94],
}

# Ejemplo del esquema IncertidumbreConfig; 5 muestras, el mínimo, para no exceder el tiempo de espera.
MUESTRAS_INCERTIDUMBRE = 5
INCERTIDUMBRE_EJEMPLO = {**CONDICIONES_ANALISIS, "n_muestras": MUESTRAS_INCERTIDUMBRE}

# Ejemplo del esquema RobustezConfig: una semilla, 9 combinaciones de 6 puntos (108 simulaciones).
ROBUSTEZ_EJEMPLO = {"humedad_ambiente_inicial_pct": 85.0, "semillas": [42]}
COMBINACIONES_ROBUSTEZ = 9

# Robustez del desgaste con el mismo esquema: 2 flujos por 3 fatigas por 3 degradaciones térmicas.
COMBINACIONES_ROBUSTEZ_DESGASTE = 18

# Ejemplo del esquema DimensionamientoConfig; un dimensionamiento por flujo de referencia.
DIMENSIONAMIENTO_EJEMPLO = {**CONDICIONES_ANALISIS, "personas": 50, "estandar": "OMS_20"}
ORIGENES_FLUJO = ["SUPUESTO", "CALIBRADO_MAX", "CALIBRADO_MIN"]
ENTORNOS_IMPACTO = 18
ENTREGA_REFERENCIA_L = 1000.0
ZONAS_INCRUSTACION = {"BAJO_TRANSICION", "TRANSICION", "SOBRE_TRANSICION", "SIN_DATOS"}
IMPACTO_ENTORNOS_INVALIDO = {"personas": 0}

# Perfiles de GET /api/v1/sitios (backend/analisis.py, perfiles_sitio).
SITIOS_ESPERADOS = ["CABO_DE_LA_VELA", "CABO_DE_LA_VELA_CALIBRADO_MAX", "CABO_DE_LA_VELA_CALIBRADO_MIN"]

# Valores de backend/schemas.py (enum Escenario).
ESCENARIOS = [
    "DIA_NORMAL",
    "INCRUSTACION_SALINA_RAPIDA",
    "SEQUIA",
    "TORMENTA_DE_ARENA",
    "TORMENTA_DE_SAL_Y_CALOR_EXTREMO",
]

# Ejemplo del esquema SimulationConfig en backend/schemas.py.
SIMULACION_EJEMPLO = {
    "duracion_horas": 24,
    "escenario": "TORMENTA_DE_SAL_Y_CALOR_EXTREMO",
    "humedad_ambiente_inicial_pct": 45.0,
    "tasa_salinizacion": "ALTA",
}

# Simulación con un perfil de sitio y una eficacia del pulso distintos de los de backend/config.py.
SITIO_EJEMPLO = {
    "nombre": "SITIO_VERIFICACION",
    "flujo_niebla_maximo_l_m2_h": 1.83,
    "temperatura_media_c": 28.0,
    "amplitud_temperatura_c": 5.0,
    "amplitud_humedad_pct": 12.0,
}
EFICACIA_EJEMPLO = 0.95
SIMULACION_SITIO_EJEMPLO = {**SIMULACION_EJEMPLO, "sitio": SITIO_EJEMPLO, "eficacia_maxima_pulso": EFICACIA_EJEMPLO}

# Calibración del flujo con el perfil de ejemplo: 10 L/m²/día es alcanzable y 40, no (respuesta 422).
CAMPO_RENDIMIENTO_OBJETIVO = "rendimiento_objetivo_l_m2_dia"
CALIBRACION_EJEMPLO = {CAMPO_RENDIMIENTO_OBJETIVO: 10.0, "sitio": SITIO_EJEMPLO}
CALIBRACION_INALCANZABLE = {CAMPO_RENDIMIENTO_OBJETIVO: 40.0}
TOLERANCIA_RENDIMIENTO_CALIBRADO = 0.1  # L/m²/día entre el rendimiento obtenido y el objetivo.

# Ejemplo del esquema TelemetryInput en backend/schemas.py.
TELEMETRIA_BASE = {
    "nodo_id": "NODO_04",
    "impedancia_ohms": 1650.5,
    "temperatura_celsius": 36.2,
    "reserva_calor_pct": 55.0,
    "humedad_relativa_pct": 42.0,
    "flujo_actual_ml_min": 14.5,
    "modo_operacion": "NEURO_SIMBOLICO",
}


@dataclass(frozen=True)
class CasoRegla:
    """Telemetría de entrada y decisión esperada según backend/motor_reglas.py."""

    nombre: str
    ajustes: dict
    regla: str
    estado: str
    accion: str
    pulso: bool
    caudal_pct: float


# Anulación manual de un operador usada en los casos de supervisión humana (REGLA_06).
SUSPENSION_MANUAL = {"anulacion_manual": "SUSPENDER_EXTRACCION"}

# Cada caso cumple también las condiciones de las reglas de menor prioridad,
# de modo que se verifica el orden REGLA_01 > 02 > 04 > 03 > 05.
CASOS_REGLAS = [
    CasoRegla(
        nombre="Corte térmico (T >= 45 °C)",
        ajustes={"temperatura_celsius": 45.0, "humedad_relativa_pct": 25.0, "reserva_calor_pct": 20.0},
        regla="REGLA_01_LIMITE_TERMICO_ABSOLUTO",
        estado="EMERGENCIA_TERMICA",
        accion="CORTE_DE_EMERGENCIA",
        pulso=False,
        caudal_pct=0.0,
    ),
    CasoRegla(
        nombre="Límite ecológico (HR < 30 %)",
        ajustes={"humedad_relativa_pct": 29.9, "reserva_calor_pct": 20.0},
        regla="REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL",
        estado="PAUSA_ECOLOGICA",
        accion="PAUSA_ECOLOGICA",
        pulso=False,
        caudal_pct=0.0,
    ),
    CasoRegla(
        nombre="Pulso de limpieza de sal (Z > 1500 Ohm)",
        ajustes={},
        regla="REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA",
        estado="CRISTALIZACION_DETECTADA",
        accion="APLICAR_PULSO_RESISTIVO",
        pulso=True,
        caudal_pct=80.0,
    ),
    CasoRegla(
        nombre="Preservación de reserva (Z > 1500, R < 30 %)",
        ajustes={"reserva_calor_pct": 29.9},
        regla="REGLA_04_PROTECCION_RESERVA_CRITICA",
        estado="RESERVA_CRITICA",
        accion="REDUCIR_CAUDAL_SIN_PULSO",
        pulso=False,
        caudal_pct=50.0,
    ),
    CasoRegla(
        nombre="Control pasivo (nominal)",
        ajustes={"impedancia_ohms": 1000.0},
        regla="REGLA_05_OPERACION_NOMINAL",
        estado="NOMINAL",
        accion="FILTRACION_PASIVA_CONTINUA",
        pulso=False,
        caudal_pct=100.0,
    ),
    # Supervisión humana (REGLA_06): el operador solo puede ser más conservador, y el
    # corte térmico prevalece sobre su decisión.
    CasoRegla(
        nombre="Supervisión humana: suspender la extracción",
        ajustes=dict(impedancia_ohms=1000.0, **SUSPENSION_MANUAL),
        regla="REGLA_06_SUPERVISION_HUMANA",
        estado="SUPERVISION_HUMANA",
        accion="SUSPENSION_MANUAL",
        pulso=False,
        caudal_pct=0.0,
    ),
    CasoRegla(
        nombre="Supervisión humana: el corte térmico prevalece (T = 46 °C)",
        ajustes=dict(temperatura_celsius=46.0, **SUSPENSION_MANUAL),
        regla="REGLA_01_LIMITE_TERMICO_ABSOLUTO",
        estado="EMERGENCIA_TERMICA",
        accion="CORTE_DE_EMERGENCIA",
        pulso=False,
        caudal_pct=0.0,
    ),
]


@dataclass
class ResultadoPrueba:
    """Resultado de una comprobación individual."""

    nombre: str
    exito: bool
    detalle: str
    duracion_seg: float


def prueba(nombre: str) -> Callable:
    """Convierte una función de comprobación en una que retorna ResultadoPrueba.

    La función decorada devuelve el detalle del éxito o lanza una excepción con
    el motivo de la falla; los errores de red, de formato y de claves ausentes
    se registran como falla sin interrumpir las demás comprobaciones.
    """

    def decorador(funcion: Callable[..., str]) -> Callable[..., ResultadoPrueba]:
        @wraps(funcion)
        def envoltura(*args, **kwargs) -> ResultadoPrueba:
            inicio = time.perf_counter()
            try:
                detalle = funcion(*args, **kwargs)
                exito = True
            except httpx.TimeoutException as error:
                detalle, exito = f"Tiempo de espera agotado: {type(error).__name__}", False
            except httpx.HTTPError as error:
                detalle, exito = f"Error HTTP: {type(error).__name__}: {error}", False
            except KeyError as error:
                detalle, exito = f"Campo ausente en la respuesta: {error}", False
            except (ValueError, TypeError) as error:
                detalle, exito = str(error), False
            return ResultadoPrueba(nombre, exito, detalle, time.perf_counter() - inicio)

        return envoltura

    return decorador


def _verificar(condicion: bool, mensaje: str) -> None:
    """Lanza ValueError con el mensaje si la condición no se cumple."""
    if not condicion:
        raise ValueError(mensaje)


def _verificar_codigo(respuesta: httpx.Response, esperado: int = 200) -> None:
    """Comprueba el código de estado e incluye un extracto del cuerpo si difiere."""
    _verificar(
        respuesta.status_code == esperado,
        f"Código {respuesta.status_code} (esperado {esperado}) en {respuesta.request.url}: "
        f"{respuesta.text[:200]}",
    )


# ---------------------------------------------------------------------------
# Comprobaciones de la API
# ---------------------------------------------------------------------------
@prueba("API: salud")
def probar_salud_api(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.get(f"{api}{RUTA_SALUD}")
    _verificar_codigo(respuesta)
    cuerpo = respuesta.json()
    _verificar(cuerpo["estado"] == "SALUDABLE", f"estado = {cuerpo['estado']!r}")
    return f"SALUDABLE, versión {cuerpo.get('version')}, actividad {cuerpo.get('tiempo_actividad_seg')} s"


@prueba("API: documentación y OpenAPI")
def probar_documentacion_api(cliente: httpx.Client, api: str) -> str:
    _verificar_codigo(cliente.get(f"{api}/docs"))
    respuesta = cliente.get(f"{api}/openapi.json")
    _verificar_codigo(respuesta)
    rutas = respuesta.json()["paths"]
    faltantes = [
        ruta
        for ruta in (
            RUTA_EVALUAR,
            RUTA_SIMULACION,
            RUTA_BARRIDO,
            RUTA_SENSIBILIDAD,
            RUTA_INCERTIDUMBRE,
            RUTA_ROBUSTEZ,
            RUTA_DIMENSIONAMIENTO,
            RUTA_SITIOS,
            RUTA_ROBUSTEZ_DESGASTE,
            RUTA_CALIBRACION,
            RUTA_IMPACTO_ENTORNOS,
        )
        if ruta not in rutas
    ]
    _verificar(not faltantes, f"Rutas ausentes en openapi.json: {', '.join(faltantes)}")
    return f"/docs 200; openapi.json con {len(rutas)} rutas"


def probar_regla(cliente: httpx.Client, api: str, caso: CasoRegla) -> ResultadoPrueba:
    """Evalúa una telemetría que debe activar la regla del caso."""

    @prueba(f"API: regla - {caso.nombre}")
    def comprobar() -> str:
        respuesta = cliente.post(f"{api}{RUTA_EVALUAR}", json={**TELEMETRIA_BASE, **caso.ajustes})
        _verificar_codigo(respuesta)
        decision = respuesta.json()
        esperado = {
            "regla_activada": caso.regla,
            "estado_nodo": caso.estado,
            "accion_recomendada": caso.accion,
            "pulso_termico_activo": caso.pulso,
            "ajuste_caudal_pct": caso.caudal_pct,
        }
        diferencias = [
            f"{campo}={decision[campo]!r} (esperado {valor!r})"
            for campo, valor in esperado.items()
            if decision[campo] != valor
        ]
        _verificar(not diferencias, "; ".join(diferencias))
        return f"{caso.accion} por {caso.regla}"

    return comprobar()


@prueba("API: telemetría inválida -> 422")
def probar_payload_invalido(cliente: httpx.Client, api: str) -> str:
    invalido = {**TELEMETRIA_BASE, "nodo_id": "NODO_99", "humedad_relativa_pct": 150.0}
    respuesta = cliente.post(f"{api}{RUTA_EVALUAR}", json=invalido)
    _verificar_codigo(respuesta, 422)
    campos = sorted({str(error["loc"][-1]) for error in respuesta.json()["detail"]})
    _verificar(
        {"nodo_id", "humedad_relativa_pct"} <= set(campos),
        f"Errores de validación inesperados: {campos}",
    )
    return f"422 en campos: {', '.join(campos)}"


def probar_simulacion(cliente: httpx.Client, api: str, configuracion: dict, nombre: str) -> ResultadoPrueba:
    """Ejecuta una simulación y comprueba la estructura del resultado."""

    @prueba(nombre)
    def comprobar() -> str:
        respuesta = cliente.post(f"{api}{RUTA_SIMULACION}", json=configuracion)
        _verificar_codigo(respuesta)
        resultado = respuesta.json()
        comparativa = resultado["comparativa"]
        neuro = comparativa["modo_neuro_simbolico"]
        temporizador = comparativa["modo_temporizador_fijo"]
        conjeturas = resultado["conjeturas_validadas"]
        claves_conjeturas = ("conjetura_1_eficiencia", "conjetura_2_autorreparacion", "conjetura_3_saber_territorial")
        _verificar(
            all(isinstance(conjeturas[clave], bool) for clave in claves_conjeturas),
            f"conjeturas_validadas con valores no booleanos: {conjeturas}",
        )
        _verificar(
            all(clave in resultado["detalle_verificacion"] for clave in claves_conjeturas),
            "detalle_verificacion incompleto",
        )
        _verificar(
            isinstance(comparativa.get("modo_temporizador_tope_ecologico"), dict),
            "comparativa sin modo_temporizador_tope_ecologico",
        )
        _verificar(
            all(
                isinstance(resultado["detalle_verificacion"][clave].get("causas_no_validacion"), list)
                for clave in claves_conjeturas
            ),
            "causas_no_validacion ausente o no es una lista en alguna conjetura",
        )
        claves_impacto = {"modo_neuro_simbolico", "modo_temporizador_fijo", "modo_temporizador_tope_ecologico"}
        impacto = resultado.get("impacto_comunitario") or {}
        _verificar(set(impacto) == claves_impacto, f"impacto_comunitario con claves {sorted(impacto)}")
        serie = resultado["series_temporales"]
        _verificar(isinstance(serie, list) and len(serie) > 0, "series_temporales vacía")
        estado_conjeturas = "".join("V" if conjeturas[clave] else "F" for clave in claves_conjeturas)
        return (
            f"{len(serie)} puntos; agua {neuro['litros_totales_agua']:.1f} L vs "
            f"{temporizador['litros_totales_agua']:.1f} L; conjeturas C1-C3 {estado_conjeturas}"
        )

    return comprobar()


@prueba("API: barrido de salinidad")
def probar_barrido(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_BARRIDO}", json=BARRIDO_EJEMPLO)
    _verificar_codigo(respuesta)
    puntos = respuesta.json()["puntos"]
    cargas = [punto["carga_salina_ohm_l_m2"] for punto in puntos]
    _verificar(len(cargas) == PUNTOS_BARRIDO, f"Se esperaban {PUNTOS_BARRIDO} puntos y llegaron {len(cargas)}")
    _verificar(all(a < b for a, b in zip(cargas, cargas[1:])), f"Cargas salinas no ordenadas: {cargas}")
    _verificar(all(punto["n_semillas"] == 1 for punto in puntos), "n_semillas distinto de 1")
    primero, ultimo = puntos[0], puntos[-1]
    return (
        f"{len(puntos)} puntos; recuperación neuro {primero['recuperacion_neuro_media']:.2f} % a "
        f"{ultimo['recuperacion_neuro_media']:.2f} %"
    )


@prueba("API: sensibilidad de la eficacia del pulso")
def probar_sensibilidad(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_SENSIBILIDAD}", json=SENSIBILIDAD_EJEMPLO)
    _verificar_codigo(respuesta)
    resultado = respuesta.json()
    puntos = resultado["puntos"]
    _verificar(resultado["parametro"] == SENSIBILIDAD_EJEMPLO["parametro"], "Parámetro distinto del solicitado")
    esperados = len(SENSIBILIDAD_EJEMPLO["valores"])
    _verificar(len(puntos) == esperados, f"Se esperaban {esperados} puntos y llegaron {len(puntos)}")
    estados = [punto["conjeturas_validadas"]["conjetura_1_eficiencia"] for punto in puntos]
    _verificar(all(isinstance(estado, bool) for estado in estados), f"Estados no booleanos: {estados}")
    return "C1 con eficacia " + ", ".join(
        f"{punto['valor']:g}: {'V' if estado else 'F'}" for punto, estado in zip(puntos, estados)
    )


@prueba("API: incertidumbre de los parámetros supuestos")
def probar_incertidumbre(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_INCERTIDUMBRE}", json=INCERTIDUMBRE_EJEMPLO)
    _verificar_codigo(respuesta)
    resultado = respuesta.json()
    muestras = resultado["muestras"]
    _verificar(
        len(muestras) == MUESTRAS_INCERTIDUMBRE,
        f"Se esperaban {MUESTRAS_INCERTIDUMBRE} muestras y llegaron {len(muestras)}",
    )
    probabilidades = [resultado[f"probabilidad_c{indice}"] for indice in (1, 2, 3)]
    _verificar(all(0.0 <= valor <= 1.0 for valor in probabilidades), f"Probabilidades fuera de [0, 1]: {probabilidades}")
    rendimiento = resultado["rendimiento"]
    _verificar(
        rendimiento["p5"] <= rendimiento["p50"] <= rendimiento["p95"],
        f"Percentiles del rendimiento no ordenados: {rendimiento}",
    )
    return (
        f"{len(muestras)} muestras; P(C1-C3) = " + ", ".join(f"{valor:.2f}" for valor in probabilidades)
        + f"; rendimiento p50 {rendimiento['p50']:.2f} L/m²/día"
    )


@prueba("API: simulación con perfil de sitio y eficacia")
def probar_simulacion_sitio(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_SIMULACION}", json=SIMULACION_SITIO_EJEMPLO)
    _verificar_codigo(respuesta)
    usados = respuesta.json()["parametros_usados"]
    _verificar(usados["nombre_sitio"] == SITIO_EJEMPLO["nombre"], f"nombre_sitio = {usados['nombre_sitio']!r}")
    esperado = {
        "flujo_niebla_maximo_l_m2_h": SITIO_EJEMPLO["flujo_niebla_maximo_l_m2_h"],
        "eficacia_maxima_pulso": EFICACIA_EJEMPLO,
        "temperatura_media_c": SITIO_EJEMPLO["temperatura_media_c"],
    }
    diferencias = [
        f"{campo}: {usados[campo]!r} en lugar de {valor!r}"
        for campo, valor in esperado.items()
        if not math.isclose(usados[campo], valor)
    ]
    _verificar(not diferencias, "; ".join(diferencias))
    return f"parametros_usados de {usados['nombre_sitio']}: flujo {usados['flujo_niebla_maximo_l_m2_h']} L/m²/h"


@prueba("API: robustez de la respuesta")
def probar_robustez(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_ROBUSTEZ}", json=ROBUSTEZ_EJEMPLO)
    _verificar_codigo(respuesta)
    resultado = respuesta.json()
    combinaciones = resultado["combinaciones"]
    _verificar(
        len(combinaciones) == COMBINACIONES_ROBUSTEZ,
        f"Llegaron {len(combinaciones)} combinaciones de las {COMBINACIONES_ROBUSTEZ} esperadas",
    )
    _verificar(
        all(len(c["barrido"]["puntos"]) == PUNTOS_BARRIDO for c in combinaciones),
        f"Alguna combinación no tiene {PUNTOS_BARRIDO} puntos",
    )
    return (
        f"{len(combinaciones)} combinaciones; {resultado['combinaciones_con_cruce']} con cruce; reducción del "
        f"desgaste {resultado['reduccion_desgaste_min_pct']:.2f} % a {resultado['reduccion_desgaste_max_pct']:.2f} %"
    )


@prueba("API: robustez del desgaste")
def probar_robustez_desgaste(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_ROBUSTEZ_DESGASTE}", json=ROBUSTEZ_EJEMPLO)
    _verificar_codigo(respuesta)
    resultado = respuesta.json()
    combinaciones = resultado["combinaciones"]
    _verificar(
        len(combinaciones) == COMBINACIONES_ROBUSTEZ_DESGASTE,
        f"Llegaron {len(combinaciones)} combinaciones de las {COMBINACIONES_ROBUSTEZ_DESGASTE} esperadas",
    )
    _verificar(
        all(c["puntos_totales"] == PUNTOS_BARRIDO for c in combinaciones),
        f"Alguna combinación no tiene {PUNTOS_BARRIDO} puntos",
    )
    return (
        f"{len(combinaciones)} combinaciones; {resultado['combinaciones_con_menor_desgaste_en_todos_los_puntos']} con "
        f"menor desgaste en todos los puntos; reducción {resultado['reduccion_desgaste_min_pct']:.2f} % a "
        f"{resultado['reduccion_desgaste_max_pct']:.2f} %"
    )


@prueba("API: calibración del flujo con perfil de sitio")
def probar_calibracion(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_CALIBRACION}", json=CALIBRACION_EJEMPLO)
    _verificar_codigo(respuesta)
    resultado = respuesta.json()
    perfil = resultado["perfil"]
    _verificar(perfil["nombre"] == SITIO_EJEMPLO["nombre"], f"perfil.nombre = {perfil['nombre']!r}")
    _verificar(
        math.isclose(perfil["flujo_niebla_maximo_l_m2_h"], resultado["flujo_calibrado_l_m2_h"]),
        "El flujo del perfil no es el flujo calibrado",
    )
    objetivo = CALIBRACION_EJEMPLO[CAMPO_RENDIMIENTO_OBJETIVO]
    _verificar(
        math.isclose(resultado["rendimiento_obtenido_l_m2_dia"], objetivo, abs_tol=TOLERANCIA_RENDIMIENTO_CALIBRADO),
        f"Rendimiento obtenido {resultado['rendimiento_obtenido_l_m2_dia']} lejos del objetivo {objetivo}",
    )
    return (
        f"flujo calibrado {resultado['flujo_calibrado_l_m2_h']} L/m²/h; rendimiento "
        f"{resultado['rendimiento_obtenido_l_m2_dia']:.2f} L/m²/día"
    )


@prueba("API: calibración inalcanzable -> 422")
def probar_calibracion_inalcanzable(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_CALIBRACION}", json=CALIBRACION_INALCANZABLE)
    _verificar_codigo(respuesta, 422)
    detalle = respuesta.json()["detail"]
    _verificar(isinstance(detalle, str) and "intervalo alcanzable" in detalle, f"Detalle inesperado: {detalle!r}")
    return f"422: {detalle[:80]}"


@prueba("API: dimensionamiento del captador")
def probar_dimensionamiento(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_DIMENSIONAMIENTO}", json=DIMENSIONAMIENTO_EJEMPLO)
    _verificar_codigo(respuesta)
    dimensiones = respuesta.json()["dimensiones"]
    origenes = [dimension["origen_flujo"] for dimension in dimensiones]
    _verificar(origenes == ORIGENES_FLUJO, f"Orígenes del flujo inesperados: {origenes}")
    return "nodos para 50 personas: " + ", ".join(
        f"{dimension['origen_flujo']} {dimension['nodos_requeridos']}" for dimension in dimensiones
    )


@prueba("API: perfiles de sitio")
def probar_sitios(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.get(f"{api}{RUTA_SITIOS}")
    _verificar_codigo(respuesta)
    nombres = [perfil["nombre"] for perfil in respuesta.json()]
    _verificar(nombres == SITIOS_ESPERADOS, f"Perfiles inesperados: {nombres}")
    return f"{len(nombres)} perfiles: {', '.join(nombres)}"


@prueba("API: impacto en distintos entornos")
def probar_impacto_entornos(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_IMPACTO_ENTORNOS}", json={})
    _verificar_codigo(respuesta)
    resultado = respuesta.json()
    entornos = resultado["entornos"]
    _verificar(len(entornos) == ENTORNOS_IMPACTO, f"{len(entornos)} entornos (esperados {ENTORNOS_IMPACTO})")
    zonas_invalidas = [e["zona_incrustacion"] for e in entornos if e["zona_incrustacion"] not in ZONAS_INCRUSTACION]
    _verificar(not zonas_invalidas, f"Zonas inesperadas: {zonas_invalidas}")
    entrega = resultado["entrega_referencia_l_comunidad_mes"]
    _verificar(
        math.isclose(entrega, ENTREGA_REFERENCIA_L),
        f"entrega_referencia_l_comunidad_mes = {entrega} (esperado {ENTREGA_REFERENCIA_L})",
    )
    return (
        f"{len(entornos)} entornos; {resultado['entornos_con_ventaja_esperada']} con ventaja esperada; "
        f"{resultado['entornos_coherentes_con_simulacion']}/{resultado['entornos_clasificables']} coherentes"
    )


@prueba("API: impacto en distintos entornos inválido -> 422")
def probar_impacto_entornos_invalido(cliente: httpx.Client, api: str) -> str:
    respuesta = cliente.post(f"{api}{RUTA_IMPACTO_ENTORNOS}", json=IMPACTO_ENTORNOS_INVALIDO)
    _verificar_codigo(respuesta, 422)
    return "422 en personas = 0"


# ---------------------------------------------------------------------------
# Comprobaciones del dashboard
# ---------------------------------------------------------------------------
@prueba("Dashboard: salud de Streamlit")
def probar_salud_dashboard(cliente: httpx.Client, dashboard: str) -> str:
    respuesta = cliente.get(f"{dashboard}/_stcore/health")
    _verificar_codigo(respuesta)
    _verificar(respuesta.text.strip() == "ok", f"Cuerpo inesperado: {respuesta.text[:100]!r}")
    return "ok"


@prueba("Dashboard: página principal")
def probar_inicio_dashboard(cliente: httpx.Client, dashboard: str) -> str:
    respuesta = cliente.get(f"{dashboard}/")
    _verificar_codigo(respuesta)
    return f"200, {len(respuesta.content)} bytes"


@prueba("Integración: cliente del dashboard contra la API")
def probar_integracion_cliente(api: str) -> str:
    # frontend.config lee AXIOMA_API_URL al importarse, por lo que se fija antes.
    os.environ["AXIOMA_API_URL"] = api
    config = importlib.import_module("frontend.config")
    if config.API_URL != api.rstrip("/"):
        config = importlib.reload(config)
    cliente_api = importlib.import_module("frontend.cliente_api")
    _verificar(config.API_URL == api.rstrip("/"), f"frontend.config.API_URL = {config.API_URL!r}")

    try:
        salud = cliente_api.verificar_salud()
        decision = cliente_api.evaluar_nodo(dict(TELEMETRIA_BASE))
        resultado = cliente_api.ejecutar_simulacion(dict(SIMULACION_EJEMPLO))
    except cliente_api.ErrorApiAxioma as error:
        detalle = f" ({'; '.join(error.detalle)})" if error.detalle else ""
        raise ValueError(f"{error.mensaje}{detalle}") from error

    _verificar(salud["estado"] == "SALUDABLE", f"verificar_salud: estado = {salud['estado']!r}")
    _verificar(
        decision["accion_recomendada"] == "APLICAR_PULSO_RESISTIVO",
        f"evaluar_nodo: acción = {decision['accion_recomendada']!r}",
    )
    _verificar(len(resultado["series_temporales"]) > 0, "ejecutar_simulacion: series_temporales vacía")
    return f"verificar_salud, evaluar_nodo y ejecutar_simulacion OK contra {config.API_URL}"


# ---------------------------------------------------------------------------
# Ejecución y reporte
# ---------------------------------------------------------------------------
def ejecutar_pruebas(api: str, dashboard: str, timeout: float) -> List[ResultadoPrueba]:
    """Ejecuta todas las comprobaciones en orden y devuelve sus resultados."""
    resultados: List[ResultadoPrueba] = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as cliente:
        # La salud se consulta primero para reactivar la API si estaba suspendida.
        resultados.append(probar_salud_api(cliente, api))
        resultados.append(probar_documentacion_api(cliente, api))
        resultados.extend(probar_regla(cliente, api, caso) for caso in CASOS_REGLAS)
        resultados.append(probar_payload_invalido(cliente, api))
        resultados.append(
            probar_simulacion(cliente, api, SIMULACION_EJEMPLO, "API: simulación - ejemplo del esquema")
        )
        for escenario in ESCENARIOS:
            configuracion = {**SIMULACION_EJEMPLO, "escenario": escenario}
            resultados.append(probar_simulacion(cliente, api, configuracion, f"API: simulación - {escenario}"))
        resultados.append(probar_barrido(cliente, api))
        resultados.append(probar_sensibilidad(cliente, api))
        resultados.append(probar_incertidumbre(cliente, api))
        resultados.append(probar_simulacion_sitio(cliente, api))
        resultados.append(probar_robustez(cliente, api))
        resultados.append(probar_robustez_desgaste(cliente, api))
        resultados.append(probar_calibracion(cliente, api))
        resultados.append(probar_calibracion_inalcanzable(cliente, api))
        resultados.append(probar_dimensionamiento(cliente, api))
        resultados.append(probar_sitios(cliente, api))
        resultados.append(probar_impacto_entornos(cliente, api))
        resultados.append(probar_impacto_entornos_invalido(cliente, api))
        resultados.append(probar_salud_dashboard(cliente, dashboard))
        resultados.append(probar_inicio_dashboard(cliente, dashboard))
    resultados.append(probar_integracion_cliente(api))
    return resultados


def imprimir_tabla(resultados: List[ResultadoPrueba]) -> None:
    """Imprime los resultados en una tabla de texto."""
    encabezado = ("Prueba", "Resultado", "Duración", "Detalle")
    filas = [
        (r.nombre, "OK" if r.exito else "FALLA", f"{r.duracion_seg:6.2f} s", r.detalle) for r in resultados
    ]
    anchos = [max(len(fila[i]) for fila in [encabezado, *filas]) for i in range(3)]
    formato = f"{{:<{anchos[0]}}}  {{:<{anchos[1]}}}  {{:>{anchos[2]}}}  {{}}"
    print(formato.format(*encabezado))
    print("  ".join("-" * ancho for ancho in anchos) + "  " + "-" * 7)
    for fila in filas:
        print(formato.format(*fila))
    exitosas = sum(r.exito for r in resultados)
    print(f"\n{exitosas}/{len(resultados)} pruebas exitosas.")


def _url_base(valor: str) -> str:
    """Valida una URL base recibida por argumento y la devuelve sin barra final.

    Solo se aceptan los esquemas http y https con un host no vacío; cualquier
    otro valor se rechaza con argparse.ArgumentTypeError.
    """
    partes = urlsplit(valor)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise argparse.ArgumentTypeError(f"URL no válida (se espera http o https con host): {valor!r}")
    return valor.rstrip("/")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verifica la API y el dashboard desplegados de Axioma-H.")
    parser.add_argument(
        "--api",
        type=_url_base,
        default=os.environ.get("AXIOMA_API_URL", API_POR_DEFECTO),
        help="URL base de la API (por defecto AXIOMA_API_URL o %(default)s).",
    )
    parser.add_argument("--dashboard", type=_url_base, default=DASHBOARD_POR_DEFECTO, help="URL base del dashboard.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=TIMEOUT_POR_DEFECTO_SEG,
        help="Espera máxima por solicitud en segundos (por defecto %(default)s).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    # Evita errores de codificación al imprimir tildes en consolas de Windows.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argumentos = construir_parser().parse_args(argv)
    api = argumentos.api.rstrip("/")
    dashboard = argumentos.dashboard.rstrip("/")
    print(f"API: {api}\nDashboard: {dashboard}\nTimeout por solicitud: {argumentos.timeout:.0f} s\n")
    resultados = ejecutar_pruebas(api, dashboard, argumentos.timeout)
    imprimir_tabla(resultados)
    return 0 if all(r.exito for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
