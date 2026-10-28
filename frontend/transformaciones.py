"""Conversión de respuestas de la API en estructuras para el dashboard.

Las funciones de este módulo son puras y no dependen de Streamlit, de modo
que se pueden probar de forma aislada.
"""

from typing import Iterable, List, Optional

import pandas as pd

from frontend import config

NOMBRES_MODO = {
    "neuro": "Neuro-simbólico",
    "temporizador": "Temporizador fijo",
}

# Clave en ResultadoModo, etiqueta y si un valor mayor es favorable.
METRICAS_COMPARATIVA = [
    ("litros_totales_agua", "Agua captada (L)", True),
    ("pulsos_termicos_ejecutados", "Pulsos térmicos", False),
    ("consumo_energia_wh", "Energía consumida (Wh)", False),
    ("integridad_membrana_final_pct", "Integridad final (%)", True),
    ("violaciones_ecologicas", "Violaciones ecológicas", False),
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
}

# Los indicadores informativos se muestran a continuación de este indicador.
ANCLA_INDICADORES_INFORMATIVOS = "tiempo_regeneracion_promedio_seg"


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


def diferencia_porcentual(valor: float, referencia: float) -> Optional[float]:
    """Diferencia relativa (valor - referencia) / referencia * 100, o None si la referencia es 0."""
    if referencia == 0:
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
    neuro = comparativa["modo_neuro_simbolico"]
    temporizador = comparativa["modo_temporizador_fijo"]
    filas = []
    for clave, etiqueta, mayor_es_mejor in METRICAS_COMPARATIVA:
        filas.append(
            {
                "Métrica": etiqueta,
                "clave": clave,
                NOMBRES_MODO["neuro"]: neuro[clave],
                NOMBRES_MODO["temporizador"]: temporizador[clave],
                "Diferencia (%)": diferencia_porcentual(neuro[clave], temporizador[clave]),
                "mayor_es_mejor": mayor_es_mejor,
            }
        )
    return pd.DataFrame(filas)


def totales_a_dataframe(resultado: dict) -> pd.DataFrame:
    """Totales finales en formato largo para el gráfico de barras."""
    comparativa = resultado["comparativa"]
    claves = [
        ("litros_totales_agua", "Agua captada (L)"),
        ("consumo_energia_wh", "Energía consumida (Wh)"),
        ("integridad_membrana_final_pct", "Integridad final (%)"),
    ]
    filas = []
    for clave_modo, nombre_modo in (
        ("modo_neuro_simbolico", NOMBRES_MODO["neuro"]),
        ("modo_temporizador_fijo", NOMBRES_MODO["temporizador"]),
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
            "Valor obtenido": f"{valor:g}",
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
                "Valor obtenido": "Sin datos" if valor is None else f"{valor:.2f}",
                "Umbral": f"{indicador['operador']} {indicador['umbral']:g}",
                "Cumple": "Sí" if indicador["cumple"] else "No",
            }
        )
        if clave == ANCLA_INDICADORES_INFORMATIVOS:
            filas.extend(informativos)
            informativos = []
    filas.extend(informativos)
    return pd.DataFrame(filas, columns=["Indicador", "Valor obtenido", "Umbral", "Cumple"])


def conjeturas_a_lista(resultado: dict) -> List[dict]:
    """Lista ordenada de conjeturas con su estado y la tabla de indicadores."""
    detalle = resultado["detalle_verificacion"]
    return [
        {
            "clave": clave,
            "nombre": nombre,
            "validada": detalle[clave]["validada"],
            "indicadores": indicadores_a_dataframe(detalle[clave]),
        }
        for clave, nombre in NOMBRES_CONJETURA.items()
    ]


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
