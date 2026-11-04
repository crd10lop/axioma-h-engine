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


def _frase_rendimiento_literatura(rendimiento: float) -> str:
    """Sitúa el rendimiento simulado frente al rango de captación de niebla de la literatura."""
    minimo = config.RENDIMIENTO_LITERATURA_MIN_L_M2_DIA
    maximo = config.RENDIMIENTO_LITERATURA_MAX_L_M2_DIA
    inicio = f"El rendimiento simulado, {rendimiento:.1f} L/m² al día,"
    rango = f"rango de {minimo:g} a {maximo:g} L/m² al día que reportan proyectos reales (Klemm et al., 2012)"
    if rendimiento > maximo:
        return (
            f"{inicio} supera el {rango}: equivale a {rendimiento / maximo:.2f} veces su extremo superior. "
            "El flujo de niebla del modelo es un supuesto optimista."
        )
    if rendimiento < minimo:
        return f"{inicio} queda por debajo del {rango}."
    return f"{inicio} está dentro del {rango}."


def resumen_impacto(resultado: dict) -> list[str] | None:
    """Frases en lenguaje llano sobre el impacto comunitario estimado del modo neuro-simbólico.

    Devuelve None si la respuesta no incluye impacto_comunitario, por ejemplo con una API anterior.
    """
    impacto = resultado.get("impacto_comunitario") or {}
    neuro = impacto.get(MODO_NEURO)
    if neuro is None:
        return None
    frases = [
        f"Con el agua captada por el control neuro-simbólico, la red simulada abastecería a "
        f"{neuro['personas_acceso_basico']:.1f} personas al nivel de acceso básico de la OMS "
        f"({config.CONSUMO_ACCESO_BASICO_L_PERSONA_DIA:g} L por persona al día), o a "
        f"{neuro['personas_supervivencia']:.1f} con el mínimo humanitario de Sphere "
        f"({config.CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA:g} L por persona al día).",
    ]
    temporizador = impacto.get(MODO_TEMPORIZADOR)
    if temporizador is not None:
        frases.append(
            f"Como comparación, el temporizador fijo, que extrae por encima del tope ecológico, abastecería "
            f"a {temporizador['personas_acceso_basico']:.1f} personas al mismo nivel."
        )
    frases.append(_frase_rendimiento_literatura(neuro["rendimiento_l_m2_dia"]))
    frases.append(
        f"Con los rendimientos reales de la literatura harían falta entre "
        f"{neuro['area_m2_por_persona_basico_literatura_min']:.1f} y "
        f"{neuro['area_m2_por_persona_basico_literatura_max']:.1f} m² de colector por persona para el "
        "acceso básico."
    )
    return frases


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


# ---------------------------------------------------------------------------
# Análisis de robustez: barrido de salinidad y sensibilidad
# ---------------------------------------------------------------------------
VARIABLE_RECUPERACION = "Recuperación"
CLAVE_CARGA = "carga_salina_ohm_l_m2"
CLAVE_PUNTOS = "puntos"
COLUMNA_VALOR = "valor"
COLUMNA_RECUPERACION = "recuperacion"
COLUMNA_TIEMPO_REGENERACION = "tiempo_regeneracion"
COLUMNA_RENDIMIENTO = "rendimiento_nocturno"
VARIABLE_DEGRADACION = "Degradación"
COLUMNAS_BARRIDO = ["carga", "Modo", "Variable", "media", "desv", "inferior", "superior"]
COLUMNAS_SENSIBILIDAD = [
    COLUMNA_VALOR,
    "C1",
    "C2",
    "C3",
    COLUMNA_RECUPERACION,
    COLUMNA_TIEMPO_REGENERACION,
    COLUMNA_RENDIMIENTO,
]
MAXIMO_SEMILLAS = 5

# Prefijo de los campos de PuntoBarrido para cada variable y sufijo para cada modo.
_PREFIJOS_BARRIDO = {VARIABLE_RECUPERACION: COLUMNA_RECUPERACION, VARIABLE_DEGRADACION: "degradacion"}
_SUFIJOS_MODO = {"neuro": NOMBRES_MODO["neuro"], "temporizador": NOMBRES_MODO["temporizador"]}

# Valores predefinidos y el indicador que se grafica para cada parámetro sensible:
# (columna de sensibilidad_a_dataframe, etiqueta del eje, umbral de la conjetura).
VALORES_SENSIBILIDAD = {
    "EFICACIA_MAXIMA_PULSO": [0.85, 0.90, 0.94, 0.97, 1.00],
    "FLUJO_NIEBLA_MAXIMO": [3.0, 4.5, 6.0, 7.5],
}
NOMBRES_PARAMETRO = {
    "EFICACIA_MAXIMA_PULSO": "Eficacia máxima del pulso",
    "FLUJO_NIEBLA_MAXIMO": "Flujo máximo de niebla (L/m²/h)",
}
# Encabezados legibles de la tabla de sensibilidad.
ETIQUETAS_SENSIBILIDAD = dict(
    zip(
        COLUMNAS_SENSIBILIDAD,
        [
            "Valor",
            "C1 Eficiencia",
            "C2 Autorreparación",
            "C3 Saber territorial",
            "Recuperación (%)",
            "Regeneración (s)",
            "Rendimiento nocturno (L/m²/noche)",
        ],
    )
)
INDICADOR_SENSIBILIDAD = {
    "EFICACIA_MAXIMA_PULSO": (COLUMNA_RECUPERACION, "Recuperación tras pulso (%)", config.RECUPERACION_MINIMA_PCT),
    "FLUJO_NIEBLA_MAXIMO": (
        COLUMNA_RENDIMIENTO,
        "Rendimiento nocturno (L/m²/noche)",
        config.RENDIMIENTO_MINIMO_L_M2_NOCHE,
    ),
}


def configuracion_barrido(humedad: float, numero_semillas: int) -> dict:
    """Carga del barrido con semillas consecutivas desde 1, acotadas entre 1 y 5."""
    cantidad = max(1, min(MAXIMO_SEMILLAS, int(numero_semillas)))
    return {"humedad_ambiente_inicial_pct": float(humedad), "semillas": list(range(1, cantidad + 1))}


def configuracion_sensibilidad(parametro: str, escenario: str, humedad: float, tasa: str = "ALTA") -> dict:
    """Carga del análisis de sensibilidad con los valores predefinidos del parámetro."""
    return {
        "escenario": escenario,
        "humedad_ambiente_inicial_pct": float(humedad),
        "tasa_salinizacion": tasa,
        "parametro": parametro,
        "valores": VALORES_SENSIBILIDAD[parametro],
    }


def barrido_a_dataframe(resultado: dict) -> pd.DataFrame:
    """Barrido en formato largo: una fila por carga, modo y variable.

    Incluye la media, la desviación y los límites de la banda media +/- desviación.
    Se omiten las combinaciones sin datos, por ejemplo la recuperación de un modo
    que no ejecutó pulsos.
    """
    filas = []
    for punto in resultado.get(CLAVE_PUNTOS, []):
        for variable, prefijo in _PREFIJOS_BARRIDO.items():
            for sufijo, modo in _SUFIJOS_MODO.items():
                media = punto.get(f"{prefijo}_{sufijo}_media")
                if media is None:
                    continue
                desv = punto.get(f"{prefijo}_{sufijo}_desv") or 0.0
                filas.append(
                    {
                        "carga": punto[CLAVE_CARGA],
                        "Modo": modo,
                        "Variable": variable,
                        "media": media,
                        "desv": desv,
                        "inferior": media - desv,
                        "superior": media + desv,
                    }
                )
    return pd.DataFrame(filas, columns=COLUMNAS_BARRIDO)


def sensibilidad_a_dataframe(resultado: dict) -> pd.DataFrame:
    """Una fila por valor del parámetro con el estado de las conjeturas y sus indicadores."""
    filas = [
        {
            COLUMNA_VALOR: punto[COLUMNA_VALOR],
            "C1": punto["conjeturas_validadas"]["conjetura_1_eficiencia"],
            "C2": punto["conjeturas_validadas"]["conjetura_2_autorreparacion"],
            "C3": punto["conjeturas_validadas"]["conjetura_3_saber_territorial"],
            COLUMNA_RECUPERACION: punto.get("recuperacion_caudal_promedio_pct"),
            COLUMNA_TIEMPO_REGENERACION: punto.get("tiempo_regeneracion_promedio_seg"),
            COLUMNA_RENDIMIENTO: punto.get("rendimiento_nocturno_l_m2_noche"),
        }
        for punto in resultado.get(CLAVE_PUNTOS, [])
    ]
    return pd.DataFrame(filas, columns=COLUMNAS_SENSIBILIDAD)


def carga_cruce_recuperacion(resultado: dict) -> float | None:
    """Carga salina desde la cual la recuperación neuro-simbólica supera a la del temporizador.

    Recorre los puntos por carga creciente y devuelve el inicio del último tramo
    en que el neuro-simbólico supera al temporizador hasta la carga más alta.
    Los puntos sin datos de recuperación no interrumpen el tramo. Devuelve None
    si en la carga más alta con datos el neuro-simbólico no supera al temporizador.
    """
    cruce = None
    for punto in sorted(resultado.get(CLAVE_PUNTOS, []), key=lambda p: p[CLAVE_CARGA]):
        neuro = punto.get("recuperacion_neuro_media")
        temporizador = punto.get("recuperacion_temporizador_media")
        if neuro is None or temporizador is None:
            continue
        if neuro <= temporizador:
            cruce = None
        elif cruce is None:
            cruce = punto[CLAVE_CARGA]
    return cruce


def lectura_barrido(resultado: dict) -> list[str]:
    """Frases de lectura calculadas desde los datos del barrido."""
    puntos = resultado.get(CLAVE_PUNTOS, [])
    if not puntos:
        return ["El barrido no devolvió puntos."]
    cruce = carga_cruce_recuperacion(resultado)
    if cruce is None:
        frase_recuperacion = (
            "En el rango evaluado, la recuperación del neuro-simbólico no supera a la del temporizador."
        )
    else:
        frase_recuperacion = (
            f"Desde una carga salina de {cruce:g} Ohm por L/m², la recuperación del neuro-simbólico "
            "supera a la del temporizador."
        )
    reducciones = [p["reduccion_desgaste_pct"] for p in puntos if p.get("reduccion_desgaste_pct") is not None]
    if reducciones:
        frase_desgaste = (
            f"La reducción del desgaste del neuro-simbólico frente al temporizador va de "
            f"{min(reducciones):.1f} % a {max(reducciones):.1f} %."
        )
    else:
        frase_desgaste = "No hay datos para calcular la reducción del desgaste."
    semillas = puntos[0].get("n_semillas", 1)
    frase_semillas = (
        f"Cada punto es la media de {semillas} semilla(s); la banda muestra +/- una desviación estándar."
    )
    return [frase_recuperacion, frase_desgaste, frase_semillas]


# ---------------------------------------------------------------------------
# Resumen ejecutivo de una simulación
# ---------------------------------------------------------------------------
_ETIQUETA_CONJETURA_CORTA = {
    "conjetura_1_eficiencia": "C1",
    "conjetura_2_autorreparacion": "C2",
    "conjetura_3_saber_territorial": "C3",
}


def _variacion(valor: float, referencia: float) -> str:
    """Describe la variación relativa de un valor frente a la referencia: "X % menos", "X % más" o "lo mismo"."""
    diferencia = diferencia_porcentual(valor, referencia)
    if diferencia is None or math.isclose(diferencia, 0.0, abs_tol=0.05):
        return "lo mismo"
    sentido = "menos" if diferencia < 0 else "más"
    return f"{abs(diferencia):.1f} % {sentido}"


def _frase_agua(resultado: dict) -> str:
    """Agua captada por ambos modos y, si hay modo de referencia, la descomposición de la brecha."""
    comparativa = resultado["comparativa"]
    neuro = comparativa[MODO_NEURO][CLAVE_LITROS]
    temporizador = comparativa[MODO_TEMPORIZADOR][CLAVE_LITROS]
    frase = (
        f"Agua: el neuro-simbólico captó {neuro:.1f} L, {_variacion(neuro, temporizador)} "
        f"que el temporizador ({temporizador:.1f} L)."
    )
    brecha = texto_brecha_agua(resultado)
    return frase if brecha is None else f"{frase} {brecha}"


def _frase_degradacion(comparativa: dict) -> str:
    """Degradación acumulada de la membrana en ambos modos."""
    clave = "degradacion_acumulada_pct"
    neuro = comparativa[MODO_NEURO][clave]
    temporizador = comparativa[MODO_TEMPORIZADOR][clave]
    return (
        f"Desgaste: la degradación de la membrana fue {neuro:.3f} % con el neuro-simbólico y "
        f"{temporizador:.3f} % con el temporizador ({_variacion(neuro, temporizador)})."
    )


def _frase_energia(comparativa: dict) -> str:
    """Energía consumida por ambos modos."""
    clave = "consumo_energia_wh"
    neuro = comparativa[MODO_NEURO][clave]
    temporizador = comparativa[MODO_TEMPORIZADOR][clave]
    return (
        f"Energía: el neuro-simbólico consumió {neuro:.1f} Wh, {_variacion(neuro, temporizador)} "
        f"que el temporizador ({temporizador:.1f} Wh)."
    )


def _frase_violaciones(comparativa: dict) -> str:
    """Episodios de violación ecológica de ambos modos."""
    clave = "violaciones_ecologicas"
    return (
        f"Límite ecológico: {comparativa[MODO_NEURO][clave]} violaciones del neuro-simbólico y "
        f"{comparativa[MODO_TEMPORIZADOR][clave]} del temporizador."
    )


def _frase_conjeturas(resultado: dict) -> str:
    """Número de conjeturas validadas y cuáles son."""
    validadas = [
        _ETIQUETA_CONJETURA_CORTA[clave]
        for clave in _ETIQUETA_CONJETURA_CORTA
        if resultado["conjeturas_validadas"].get(clave)
    ]
    detalle = f" ({', '.join(validadas)})" if validadas else ""
    return f"Conjeturas validadas: {len(validadas)} de {len(_ETIQUETA_CONJETURA_CORTA)}{detalle}."


def resumen_ejecutivo(resultado: dict) -> list[str]:
    """Cinco frases con lo esencial de una simulación, calculadas desde la respuesta de la API.

    Cubren el agua captada (con la descomposición de la brecha si la respuesta
    incluye el temporizador con tope ecológico), la degradación, la energía,
    las violaciones ecológicas y el número de conjeturas validadas.
    """
    comparativa = resultado["comparativa"]
    return [
        _frase_agua(resultado),
        _frase_degradacion(comparativa),
        _frase_energia(comparativa),
        _frase_violaciones(comparativa),
        _frase_conjeturas(resultado),
    ]


# ---------------------------------------------------------------------------
# Incertidumbre de los parámetros supuestos
# ---------------------------------------------------------------------------
CLAVE_MUESTRAS = "muestras"
CLAVE_VALIDADAS = "conjeturas_validadas"
COLUMNA_ESTADO_C1 = "Estado C1"
COLUMNAS_INCERTIDUMBRE = [
    "eficacia",
    "flujo",
    "C1",
    "C2",
    "C3",
    COLUMNA_ESTADO_C1,
    COLUMNA_RECUPERACION,
    "rendimiento_dia",
    "reduccion_degradacion",
]
ESTADOS_VALIDACION = {True: "Validada", False: "No validada"}
MUESTRAS_INCERTIDUMBRE_POR_DEFECTO = 20
# Clave del resumen en la respuesta, etiqueta y unidad de cada indicador.
INDICADORES_INCERTIDUMBRE = [
    ("recuperacion", "Recuperación tras pulso", "%"),
    ("rendimiento", "Rendimiento del neuro-simbólico", "L/m² al día"),
    ("reduccion_degradacion", "Reducción de la degradación frente al temporizador", "%"),
]


def configuracion_incertidumbre(
    escenario: str, humedad: float, n_muestras: int = MUESTRAS_INCERTIDUMBRE_POR_DEFECTO, tasa: str = "ALTA"
) -> dict:
    """Carga del análisis de incertidumbre con los rangos por defecto de la API."""
    return {
        "escenario": escenario,
        "humedad_ambiente_inicial_pct": float(humedad),
        "tasa_salinizacion": tasa,
        "n_muestras": int(n_muestras),
    }


def incertidumbre_a_dataframe(resultado: dict) -> pd.DataFrame:
    """Una fila por muestra con la eficacia, el flujo, el estado de las conjeturas y sus indicadores."""
    filas = []
    for muestra in resultado.get(CLAVE_MUESTRAS, []):
        validadas = muestra[CLAVE_VALIDADAS]
        c1 = validadas["conjetura_1_eficiencia"]
        filas.append(
            {
                "eficacia": muestra["eficacia"],
                "flujo": muestra["flujo"],
                "C1": c1,
                "C2": validadas["conjetura_2_autorreparacion"],
                "C3": validadas["conjetura_3_saber_territorial"],
                COLUMNA_ESTADO_C1: ESTADOS_VALIDACION[c1],
                COLUMNA_RECUPERACION: muestra.get("recuperacion_caudal_promedio_pct"),
                "rendimiento_dia": muestra.get("rendimiento_l_m2_dia"),
                "reduccion_degradacion": muestra.get("reduccion_degradacion_pct"),
            }
        )
    return pd.DataFrame(filas, columns=COLUMNAS_INCERTIDUMBRE)


def probabilidades_incertidumbre(resultado: dict) -> pd.DataFrame:
    """Tabla con la probabilidad de validar cada conjetura y el número de muestras validadas."""
    muestras = resultado.get(CLAVE_MUESTRAS, [])
    filas = [
        {
            "Conjetura": nombre,
            "Probabilidad": resultado[f"probabilidad_c{indice}"],
            "Muestras validadas": sum(muestra[CLAVE_VALIDADAS][clave] for muestra in muestras),
        }
        for indice, (clave, nombre) in enumerate(NOMBRES_CONJETURA.items(), start=1)
    ]
    return pd.DataFrame(filas, columns=["Conjetura", "Probabilidad", "Muestras validadas"])


def _frase_rango(resumen: dict, etiqueta: str, unidad: str, total: int) -> str:
    """Rango entre los percentiles 5 y 95 de un indicador, o aviso si ninguna muestra tiene datos."""
    if not resumen.get("n_validos"):
        return f"{etiqueta}: ninguna muestra tiene datos."
    return (
        f"{etiqueta}: de {resumen['p5']:.2f} a {resumen['p95']:.2f} {unidad} entre los percentiles 5 y 95 "
        f"(mediana {resumen['p50']:.2f}; {resumen['n_validos']} de {total} muestras con datos)."
    )


def lectura_incertidumbre(resultado: dict) -> list[str]:
    """Frases sobre la probabilidad de validar cada conjetura y el rango p5 a p95 de los indicadores."""
    muestras = resultado.get(CLAVE_MUESTRAS, [])
    if not muestras:
        return ["El análisis no devolvió muestras."]
    total = len(muestras)
    frases = [
        f"{fila['Conjetura']}: se valida en {fila['Muestras validadas']} de {total} muestras "
        f"(probabilidad {fila['Probabilidad']:.2f})."
        for fila in probabilidades_incertidumbre(resultado).to_dict("records")
    ]
    frases.extend(
        _frase_rango(resultado[clave], etiqueta, unidad, total) for clave, etiqueta, unidad in INDICADORES_INCERTIDUMBRE
    )
    sin_pulsos = total - resultado["recuperacion"]["n_validos"]
    if sin_pulsos:
        frases.append(
            f"En {sin_pulsos} de {total} muestras el neuro-simbólico no aplicó pulsos: sin pulsos no hay "
            "recuperación ni tiempo de regeneración que medir, y las Conjeturas 1 y 2 no se validan por "
            "falta de datos, no por un mal resultado."
        )
    return frases
