"""Conversión de respuestas de la API en estructuras para el dashboard.

Las funciones de este módulo son puras y no dependen de Streamlit, de modo
que se pueden probar de forma aislada.
"""

import math
from typing import Iterable, List, Optional

import pandas as pd

from frontend import config

# Claves de la comparativa de modos en la respuesta de la API.
MODO_NEURO = "modo_neuro_simbolico"
MODO_TEMPORIZADOR = "modo_temporizador_fijo"
MODO_REFERENCIA = "modo_temporizador_tope_ecologico"
CLAVE_LITROS = "litros_totales_agua"

NOMBRES_MODO = {
    "neuro": "Neuro-simbólico",
    "temporizador": "Temporizador fijo",
}

# Clave en ResultadoModo, etiqueta y si un valor mayor es favorable.
METRICAS_COMPARATIVA = [
    (CLAVE_LITROS, "Agua captada (L)", True),
    ("pulsos_termicos_ejecutados", "Pulsos térmicos", False),
    ("consumo_energia_wh", "Energía consumida (Wh)", False),
    ("integridad_membrana_final_pct", "Integridad final (%)", True),
    ("violaciones_ecologicas", "Violaciones ecológicas", False),
    ("recuperacion_caudal_promedio_pct", "Recuperación tras pulso (%)", True),
    ("degradacion_acumulada_pct", "Degradación acumulada (%)", False),
]

NOMBRES_CONJETURA = {
    "conjetura_1_eficiencia": "Conjetura 1. Eficiencia",
    "conjetura_2_autorreparacion": "Conjetura 2. Autorreparación",
    "conjetura_3_saber_territorial": "Conjetura 3. Saber territorial",
}

NOMBRES_INDICADOR = {
    "recuperacion_caudal_promedio_pct": "Recuperación de caudal tras pulso (%)",
    "ahorro_energia_pulsos_pct": "Ahorro de energía en pulsos (%)",
    "tiempo_regeneracion_promedio_seg": "Tiempo promedio de regeneración (s)",
    "perdida_integridad_termica_pct": "Pérdida de integridad térmica (%)",
    "violaciones_ecologicas": "Violaciones ecológicas (episodios)",
    "rendimiento_nocturno_l_m2_noche": "Rendimiento nocturno (L/m²/noche)",
    "pulsos_regenerados": "Pulsos regenerados (informativo)",
    "pulsos_totales": "Pulsos totales (informativo)",
    "reduccion_degradacion_pct": "Reducción de la degradación frente al temporizador (%, informativo)",
    "tiempo_desprendimiento_t95_promedio_seg": "Tiempo hasta el 95 % de la remoción del pulso (s, informativo)",
    "impedancia_promedio_tras_pulso_ohms": "Impedancia promedio tras el pulso (Ω, informativo)",
    "rendimiento_nocturno_temporizador_l_m2_noche": "Rendimiento nocturno del temporizador (L/m²/noche, informativo)",
}

# Explicación en lenguaje llano de cada causa de no validación que entrega la API.
TEXTO_CAUSA = {
    "SIN_DATOS": "La corrida no generó datos para medir al menos un indicador.",
    "DEPENDE_DE_PARAMETRO_SUPUESTO": (
        "Depende de cuánta sal remueve un pulso, un parámetro supuesto que aún no se ha medido; "
        "no equivale a una refutación."
    ),
    "LIMITE_DEL_RECURSO_ATMOSFERICO": (
        "La niebla disponible no alcanza: el temporizador, sin límites ecológicos, tampoco llega al umbral."
    ),
    "DESEMPENO_DEL_CONTROL": "El control no alcanzó el umbral con los parámetros actuales.",
}

# Los indicadores informativos se muestran a continuación de este indicador.
ANCLA_INDICADORES_INFORMATIVOS = "tiempo_regeneracion_promedio_seg"

COLUMNA_VALOR_OBTENIDO = "Valor obtenido"


def minuto_a_hora_local(minuto: int, hora_inicio: int = config.HORA_INICIO_SIMULACION) -> str:
    """Convierte el minuto de simulación en hora local HH:MM."""
    total = (hora_inicio * 60 + int(minuto)) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def dia_simulacion(minuto: int, hora_inicio: int = config.HORA_INICIO_SIMULACION) -> int:
    """Día calendario de la simulación, empezando en 1; cambia a medianoche."""
    return 1 + (hora_inicio * 60 + int(minuto)) // (24 * 60)


def etiqueta_tiempo(minuto: int, hora_inicio: int = config.HORA_INICIO_SIMULACION) -> str:
    """Etiqueta con día y hora local, por ejemplo 'Día 2 03:15'."""
    return f"Día {dia_simulacion(minuto, hora_inicio)} {minuto_a_hora_local(minuto, hora_inicio)}"


def diferencia_porcentual(valor: Optional[float], referencia: Optional[float]) -> Optional[float]:
    """Diferencia relativa (valor - referencia) / referencia * 100, o None si no es calculable."""
    if valor is None or referencia is None or math.isclose(referencia, 0.0, abs_tol=1e-12):
        return None
    return (valor - referencia) / referencia * 100.0


def series_a_dataframe(resultado: dict) -> pd.DataFrame:
    """Convierte series_temporales en un DataFrame con horas en formato legible."""
    df = pd.DataFrame(resultado.get("series_temporales", []))
    if df.empty:
        return df
    df["hora_simulada"] = df["minuto"] / 60.0
    df["hora_local"] = df["minuto"].map(minuto_a_hora_local)
    return df


def series_formato_largo(df: pd.DataFrame, columna_neuro: str, columna_temporizador: str) -> pd.DataFrame:
    """Reorganiza dos columnas comparables en formato largo para graficar por modo."""
    if df.empty:
        return pd.DataFrame(columns=["minuto", "hora_simulada", "hora_local", "Modo", "valor"])
    largo = df[["minuto", "hora_simulada", "hora_local", columna_neuro, columna_temporizador]].melt(
        id_vars=["minuto", "hora_simulada", "hora_local"], var_name="Modo", value_name="valor"
    )
    largo["Modo"] = largo["Modo"].map(
        {columna_neuro: NOMBRES_MODO["neuro"], columna_temporizador: NOMBRES_MODO["temporizador"]}
    )
    return largo


def comparativa_a_dataframe(resultado: dict) -> pd.DataFrame:
    """Tabla de métricas finales de ambos modos con la diferencia porcentual."""
    comparativa = resultado["comparativa"]
    neuro = comparativa[MODO_NEURO]
    temporizador = comparativa[MODO_TEMPORIZADOR]
    filas = []
    for clave, etiqueta, mayor_es_mejor in METRICAS_COMPARATIVA:
        filas.append(
            {
                "Métrica": etiqueta,
                "clave": clave,
                NOMBRES_MODO["neuro"]: neuro.get(clave),
                NOMBRES_MODO["temporizador"]: temporizador.get(clave),
                "Diferencia (%)": diferencia_porcentual(neuro.get(clave), temporizador.get(clave)),
                "mayor_es_mejor": mayor_es_mejor,
            }
        )
    return pd.DataFrame(filas)


def totales_a_dataframe(resultado: dict) -> pd.DataFrame:
    """Totales finales en formato largo para el gráfico de barras."""
    comparativa = resultado["comparativa"]
    claves = [
        (CLAVE_LITROS, "Agua captada (L)"),
        ("consumo_energia_wh", "Energía consumida (Wh)"),
        ("integridad_membrana_final_pct", "Integridad final (%)"),
    ]
    filas = []
    for clave_modo, nombre_modo in (
        (MODO_NEURO, NOMBRES_MODO["neuro"]),
        (MODO_TEMPORIZADOR, NOMBRES_MODO["temporizador"]),
    ):
        for clave, etiqueta in claves:
            filas.append({"Métrica": etiqueta, "Modo": nombre_modo, "Valor": comparativa[clave_modo][clave]})
    return pd.DataFrame(filas)


def indicadores_a_dataframe(verificacion: dict) -> pd.DataFrame:
    """Tabla de indicadores de una conjetura: valor, umbral y cumplimiento.

    Los valores se entregan como texto para que la columna tenga un tipo
    homogéneo aun cuando un indicador no tenga datos. Los indicadores
    informativos se insertan después del tiempo de regeneración (o al final
    si ese indicador no existe), sin umbral y marcados como "Informativo".
    """
    informativos = [
        {
            "Indicador": NOMBRES_INDICADOR.get(clave, clave),
            COLUMNA_VALOR_OBTENIDO: f"{valor:g}",
            "Umbral": "No aplica",
            "Cumple": "Informativo",
        }
        for clave, valor in verificacion.get("indicadores_informativos", {}).items()
    ]
    filas = []
    for clave, indicador in verificacion.get("indicadores", {}).items():
        valor = indicador.get("valor")
        filas.append(
            {
                "Indicador": NOMBRES_INDICADOR.get(clave, clave),
                COLUMNA_VALOR_OBTENIDO: "Sin datos" if valor is None else f"{valor:.2f}",
                "Umbral": f"{indicador['operador']} {indicador['umbral']:g}",
                "Cumple": "Sí" if indicador["cumple"] else "No",
            }
        )
        if clave == ANCLA_INDICADORES_INFORMATIVOS:
            filas.extend(informativos)
            informativos = []
    filas.extend(informativos)
    return pd.DataFrame(filas, columns=["Indicador", COLUMNA_VALOR_OBTENIDO, "Umbral", "Cumple"])


def conjeturas_a_lista(resultado: dict) -> List[dict]:
    """Lista ordenada de conjeturas con su estado, la tabla de indicadores y las causas de no validación.

    Las causas se traducen con TEXTO_CAUSA; una respuesta sin el campo
    `causas_no_validacion` produce una lista vacía.
    """
    detalle = resultado["detalle_verificacion"]
    return [
        {
            "clave": clave,
            "nombre": nombre,
            "validada": detalle[clave]["validada"],
            "indicadores": indicadores_a_dataframe(detalle[clave]),
            "causas": [TEXTO_CAUSA.get(causa, causa) for causa in detalle[clave].get("causas_no_validacion", [])],
        }
        for clave, nombre in NOMBRES_CONJETURA.items()
    ]


def descomponer_brecha_agua(resultado: dict) -> dict | None:
    """Separa la diferencia de agua entre temporizador y neuro-simbólico en dos partes.

    Con L_temp, L_neuro y L_temp33 (temporizador con tope ecológico):
    - brecha_total_l = L_temp - L_neuro;
    - por_tope_ecologico_l = L_temp - L_temp33;
    - por_logica_control_l = L_temp33 - L_neuro;
    - pct_por_tope = por_tope_ecologico_l / brecha_total_l * 100, o None si la brecha no es positiva.
    Devuelve None si la respuesta no incluye el modo de referencia.
    """
    comparativa = resultado["comparativa"]
    referencia = comparativa.get(MODO_REFERENCIA)
    if referencia is None:
        return None
    litros_neuro = comparativa[MODO_NEURO][CLAVE_LITROS]
    litros_temporizador = comparativa[MODO_TEMPORIZADOR][CLAVE_LITROS]
    litros_referencia = referencia[CLAVE_LITROS]
    brecha_total = litros_temporizador - litros_neuro
    por_tope = litros_temporizador - litros_referencia
    return {
        "brecha_total_l": brecha_total,
        "por_tope_ecologico_l": por_tope,
        "por_logica_control_l": litros_referencia - litros_neuro,
        "pct_por_tope": None if brecha_total <= 0 else por_tope / brecha_total * 100.0,
    }


def texto_brecha_agua(resultado: dict) -> str | None:
    """Frase con la descomposición de la diferencia de agua, o None si no es calculable."""
    brecha = descomponer_brecha_agua(resultado)
    pct_por_tope = None if brecha is None else brecha["pct_por_tope"]
    if pct_por_tope is None:
        return None
    return (
        f"De {brecha['brecha_total_l']:.1f} L de diferencia, {brecha['por_tope_ecologico_l']:.1f} L "
        f"({pct_por_tope:.1f} %) se deben al tope ecológico de 33 % y "
        f"{brecha['por_logica_control_l']:.1f} L a la lógica de control."
    )


def texto_modo_referencia(resultado: dict) -> str | None:
    """Línea con los totales del temporizador con tope ecológico, o None si la respuesta no lo incluye."""
    referencia = resultado["comparativa"].get(MODO_REFERENCIA)
    if referencia is None:
        return None
    return (
        f"Temporizador con tope ecológico (33 %): {referencia[CLAVE_LITROS]:.1f} L, "
        f"{referencia['pulsos_termicos_ejecutados']} pulsos, {referencia['consumo_energia_wh']:.1f} Wh, "
        f"integridad final {referencia['integridad_membrana_final_pct']:.2f} %, "
        f"{referencia['violaciones_ecologicas']} violaciones ecológicas."
    )


def filtrar_bitacora(
    bitacora: Iterable[dict], nodo: Optional[str] = None, regla: Optional[str] = None
) -> List[dict]:
    """Filtra los eventos de la bitácora por nodo y por regla; None no filtra."""
    return [
        evento
        for evento in bitacora
        if (nodo is None or evento["nodo_id"] == nodo) and (regla is None or evento["regla_activada"] == regla)
    ]


def bitacora_a_texto(
    bitacora: Iterable[dict],
    nodo: Optional[str] = None,
    regla: Optional[str] = None,
    hora_inicio: int = config.HORA_INICIO_SIMULACION,
) -> str:
    """Formatea la bitácora como texto de consola: tiempo, nodo, regla y motivo."""
    lineas = [
        f"[{etiqueta_tiempo(e['minuto'], hora_inicio)}] {e['nodo_id']} | {e['regla_activada']} | {e['motivo']}"
        for e in filtrar_bitacora(bitacora, nodo, regla)
    ]
    return "\n".join(lineas) if lineas else "Sin eventos para los filtros seleccionados."


def historial_a_texto(historial: Iterable[dict]) -> str:
    """Formatea el historial de decisiones manuales como texto de consola."""
    lineas = [f"[{h['hora']}] {h['nodo']} | {h['regla']} | {h['motivo']}" for h in historial]
    return "\n".join(lineas) if lineas else "Aún no hay decisiones registradas en esta sesión."


def zonas_telemetria(telemetria: dict) -> dict:
    """Indica, para cada variable, si su valor cruza el umbral de control.

    Devuelve un diccionario con True cuando el valor está fuera de la zona
    normal: impedancia > 1500 Ohm, temperatura >= 45 °C, reserva < 30 % y
    humedad < 30 %.
    """
    return {
        "impedancia_ohms": telemetria["impedancia_ohms"] > config.UMBRAL_IMPEDANCIA_OHMS,
        "temperatura_celsius": telemetria["temperatura_celsius"] >= config.UMBRAL_TEMPERATURA_CORTE_C,
        "reserva_calor_pct": telemetria["reserva_calor_pct"] < config.UMBRAL_RESERVA_CRITICA_PCT,
        "humedad_relativa_pct": telemetria["humedad_relativa_pct"] < config.UMBRAL_HUMEDAD_ECOLOGICA_PCT,
    }
