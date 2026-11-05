"""Conversión de respuestas de la API en estructuras para el dashboard.

Las funciones de este módulo son puras y no dependen de Streamlit, de modo
que se pueden probar de forma aislada.
"""

import math
from typing import Iterable, List, Optional

import pandas as pd

from frontend import config, contenido

# Claves de la comparativa de modos en la respuesta de la API.
MODO_NEURO = "modo_neuro_simbolico"
MODO_TEMPORIZADOR = "modo_temporizador_fijo"
MODO_REFERENCIA = "modo_temporizador_tope_ecologico"
CLAVE_LITROS = "litros_totales_agua"

# Nombre visible del modo NEURO_SIMBOLICO de la API en las frases del dashboard.
CONTROL_REGLAS = "el control basado en reglas"

NOMBRES_MODO = {
    "neuro": "Control basado en reglas",
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
        f"Con el agua captada por {CONTROL_REGLAS}, la red simulada abastecería a "
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


def _configuracion_con_semillas(humedad: float, numero_semillas: int, maximo_semillas: int) -> dict:
    """Carga con humedad inicial y semillas consecutivas desde 1, acotadas entre 1 y el máximo indicado."""
    cantidad = max(1, min(maximo_semillas, int(numero_semillas)))
    return {"humedad_ambiente_inicial_pct": float(humedad), "semillas": list(range(1, cantidad + 1))}


def configuracion_barrido(humedad: float, numero_semillas: int) -> dict:
    """Carga del barrido con semillas consecutivas desde 1, acotadas entre 1 y 5."""
    return _configuracion_con_semillas(humedad, numero_semillas, MAXIMO_SEMILLAS)


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
            f"En el rango evaluado, la recuperación con {CONTROL_REGLAS} no supera a la del temporizador."
        )
    else:
        frase_recuperacion = (
            f"Desde una carga salina de {cruce:g} Ohm por L/m², la recuperación con {CONTROL_REGLAS} "
            "supera a la del temporizador."
        )
    reducciones = [p["reduccion_desgaste_pct"] for p in puntos if p.get("reduccion_desgaste_pct") is not None]
    if reducciones:
        frase_desgaste = (
            f"La reducción del desgaste con {CONTROL_REGLAS} frente al temporizador va de "
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
        f"Agua: {CONTROL_REGLAS} captó {neuro:.1f} L, {_variacion(neuro, temporizador)} "
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
        f"Desgaste: la degradación de la membrana fue {neuro:.3f} % con {CONTROL_REGLAS} y "
        f"{temporizador:.3f} % con el temporizador ({_variacion(neuro, temporizador)})."
    )


def _frase_energia(comparativa: dict) -> str:
    """Energía consumida por ambos modos."""
    clave = "consumo_energia_wh"
    neuro = comparativa[MODO_NEURO][clave]
    temporizador = comparativa[MODO_TEMPORIZADOR][clave]
    return (
        f"Energía: {CONTROL_REGLAS} consumió {neuro:.1f} Wh, {_variacion(neuro, temporizador)} "
        f"que el temporizador ({temporizador:.1f} Wh)."
    )


def _frase_violaciones(comparativa: dict) -> str:
    """Episodios de violación ecológica de ambos modos."""
    clave = "violaciones_ecologicas"
    return (
        f"Límite ecológico: {comparativa[MODO_NEURO][clave]} violaciones con {CONTROL_REGLAS} y "
        f"{comparativa[MODO_TEMPORIZADOR][clave]} con el temporizador."
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
    ("rendimiento", f"Rendimiento con {CONTROL_REGLAS}", "L/m² al día"),
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
            f"En {sin_pulsos} de {total} muestras {CONTROL_REGLAS} no aplicó pulsos: sin pulsos no hay "
            "recuperación ni tiempo de regeneración que medir, y las Conjeturas 1 y 2 no se validan por "
            "falta de datos, no por un mal resultado."
        )
    ventaja = frase_ventaja_incertidumbre(resultado)
    if ventaja is not None:
        frases.append(ventaja)
    return frases


def frase_ventaja_incertidumbre(resultado: dict) -> str | None:
    """Probabilidad de que el control basado en reglas recupere más que el temporizador entre las muestras.

    Devuelve None si la respuesta no incluye el campo, por ejemplo con una API anterior a 0.3.0.
    """
    if "probabilidad_ventaja_recuperacion" not in resultado:
        return None
    probabilidad = resultado["probabilidad_ventaja_recuperacion"]
    if probabilidad is None:
        return "Ninguna muestra tiene pulsos en ambos modos: no se puede estimar la ventaja en recuperación."
    ventajas = [
        muestra["ventaja_recuperacion_pts"]
        for muestra in resultado.get(CLAVE_MUESTRAS, [])
        if muestra.get("ventaja_recuperacion_pts") is not None
    ]
    positivas = sum(ventaja > _TOLERANCIA_CERO for ventaja in ventajas)
    frase = (
        f"El control basado en reglas recupera más que el temporizador en {positivas} de {len(ventajas)} muestras "
        f"con pulsos en ambos modos (probabilidad {probabilidad:.2f})."
    )
    resumen = resultado.get("ventaja_recuperacion") or {}
    if resumen.get("n_validos"):
        frase += (
            f" La ventaja va de {resumen['p5']:.2f} a {resumen['p95']:.2f} puntos entre los percentiles 5 y 95."
        )
    return frase


# ---------------------------------------------------------------------------
# Lenguaje llano y condiciones de cambio de cada conjetura
# ---------------------------------------------------------------------------
_TOLERANCIA_CERO = 1e-9
CLAVE_DETALLE = "detalle_verificacion"

# Qué cambiaría un indicador que no cumple y qué haría fallar uno que cumple.
# Origen: docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md, secciones 6.2, 6.3, 7.4, 8.6 y 8.10.
PALANCAS_INDICADOR: dict[str, tuple[str, str]] = {
    "recuperacion_caudal_promedio_pct": (
        (f"Cambiaría si un pulso remueve más sal: con el flujo supuesto, validarla exige una eficacia del pulso "
        f"de al menos {config.EFICACIA_MINIMA_C1:.2f}, frente a {config.EFICACIA_SUPUESTA:.2f} supuesta "
        "(docs/04, sección 6.2). Lo decide medir qué fracción de la costra remueve un pulso de 90 s a 44 °C "
        "(docs/04, sección 6.3)."),
        "Fallaría si la eficacia medida del pulso resulta menor que la usada en la corrida.",
    ),
    "ahorro_energia_pulsos_pct": (
        ("Cambiaría con menos pulsos o con pulsos de menor costo: depende de la carga salina, que fija cuántas "
        "veces se dispara el pulso, y de la capacidad térmica y las pérdidas de la matriz, todos supuestos."),
        "Fallaría si la carga salina obliga a pulsar casi tantas veces como el temporizador.",
    ),
    "tiempo_regeneracion_promedio_seg": (
        (f"Cambiaría si un pulso deja la membrana bajo 1100 Ω: con el flujo supuesto exige una eficacia de al "
        f"menos {config.EFICACIA_MINIMA_C2:.2f} (docs/04, sección 6.2). Lo decide la misma medición de la "
        "eficacia del pulso (docs/04, sección 6.3)."),
        "Fallaría si la eficacia medida del pulso no alcanza para volver bajo 1100 Ω.",
    ),
    "perdida_integridad_termica_pct": (
        ("Cambiaría si la matriz deja de alcanzar 45 °C: depende de la temperatura del sitio y del "
        "calentamiento solar de la matriz."),
        "Fallaría en un sitio más cálido, donde la matriz supere 45 °C durante la operación.",
    ),
    "violaciones_ecologicas": (
        "Cambiaría si el control deja de pausar la extracción con humedad menor que 30 % (REGLA_02).",
        "Fallaría con una sola extracción con humedad menor que 30 % o por encima del tope de 33 %.",
    ),
    "rendimiento_nocturno_l_m2_noche": (
        ("Cambiaría con más niebla disponible: depende del flujo de niebla supuesto. Lo decide medir el "
        "rendimiento de niebla del sitio y calibrar el flujo (docs/04, secciones 8.6 y 8.10)."),
        ("Fallaría con un flujo de niebla como el de la literatura: con el flujo calibrado no se alcanza "
        "(docs/04, sección 8.6)."),
    ),
}
_PALANCA_GENERICA = ("Depende de los parámetros supuestos del modelo.", "Depende de los parámetros supuestos del modelo.")
_SIN_DATOS_INDICADOR = (
    "no tiene datos: la corrida no aplicó pulsos o no cubrió horas nocturnas, de modo que el indicador no se "
    "puso a prueba. Con más humedad, más salinidad o más horas se podría medir."
)


def etiqueta_llana(codigo: str) -> str:
    """Traduce un código de regla, estado, acción o cruce a lenguaje llano; si no lo conoce, lo devuelve igual."""
    return contenido.ETIQUETAS_LLANAS.get(codigo, codigo)


def _distancia_umbral(indicador: dict) -> float:
    """Distancia positiva entre el valor y el umbral de un indicador con datos."""
    return abs(indicador["valor"] - indicador["umbral"])


def _frase_indicador(clave: str, indicador: dict) -> str:
    """Valor, umbral, distancia y palanca de un indicador: qué lo cambiaría o qué lo haría fallar."""
    nombre = NOMBRES_INDICADOR.get(clave, clave)
    if indicador.get("valor") is None:
        return f"{nombre} {_SIN_DATOS_INDICADOR}"
    si_no_cumple, si_cumple = PALANCAS_INDICADOR.get(clave, _PALANCA_GENERICA)
    comparacion = f"{nombre}: {indicador['valor']:.2f} frente al umbral {indicador['operador']} {indicador['umbral']:g}"
    distancia = _distancia_umbral(indicador)
    if indicador["cumple"]:
        return f"{comparacion}, con un margen de {distancia:.2f}. {si_cumple}"
    return f"{comparacion}, a {distancia:.2f} del umbral. {si_no_cumple}"


def _condicion_conjetura(clave: str, verificacion: dict) -> str:
    """Frase de una conjetura: los indicadores que fallan si no se valida, o todos si se valida."""
    validada = verificacion.get("validada", False)
    indicadores = verificacion.get("indicadores", {})
    seleccion = [
        _frase_indicador(nombre, indicador)
        for nombre, indicador in indicadores.items()
        if validada or not indicador.get("cumple", False)
    ]
    estado = "validada" if validada else "no validada"
    return " ".join([f"{NOMBRES_CONJETURA.get(clave, clave)}, {estado}."] + seleccion)


def condiciones_de_cambio(resultado: dict) -> list[str]:
    """Una frase por conjetura, en el orden de NOMBRES_CONJETURA, sobre qué cambiaría su resultado.

    Para una conjetura no validada se describe cada indicador que no cumple: su valor, el umbral, la
    distancia y la medición o el parámetro que lo cambiaría. Para una validada se describe el margen de
    cada indicador y qué la haría fallar. Devuelve una lista vacía si la respuesta no tiene
    detalle_verificacion.
    """
    detalle = resultado.get(CLAVE_DETALLE) or {}
    return [_condicion_conjetura(clave, detalle[clave]) for clave in NOMBRES_CONJETURA if clave in detalle]


# ---------------------------------------------------------------------------
# Robustez de la respuesta (docs/04, sección 8.8)
# ---------------------------------------------------------------------------
CLAVE_COMBINACIONES = "combinaciones"
CLAVE_CRUCE = "cruce"
CLAVE_INCRUSTACION = "incrustacion_diaria_ohm_media"
ESTADO_INTERPOLADO = "INTERPOLADO"
MAXIMO_SEMILLAS_ROBUSTEZ = 3
COLUMNA_CRUCE = "Cruce"
COLUMNA_FLUJO = "Flujo (L/m²/h)"
COLUMNA_REDUCCION_MIN = "Reducción del desgaste mínima (%)"
COLUMNA_REDUCCION_MAX = "Reducción del desgaste máxima (%)"
COLUMNA_SEPARACION_CRUCE = "Separación de los puntos del cruce (Ohm/día)"
CLAVE_SEPARACION = "separacion_ohm"
COLUMNAS_ROBUSTEZ = [
    COLUMNA_FLUJO,
    "Eficacia",
    COLUMNA_CRUCE,
    "Incrustación diaria del cruce (Ohm/día)",
    "Carga salina del cruce (Ohm por L/m²)",
    COLUMNA_SEPARACION_CRUCE,
    COLUMNA_REDUCCION_MIN,
    COLUMNA_REDUCCION_MAX,
    "Incrustación diaria máxima (Ohm/día)",
]


def configuracion_robustez(humedad: float, numero_semillas: int) -> dict:
    """Carga de la robustez con semillas consecutivas desde 1, acotadas entre 1 y 3."""
    return _configuracion_con_semillas(humedad, numero_semillas, MAXIMO_SEMILLAS_ROBUSTEZ)


def _valores_no_nulos(puntos: list[dict], clave: str) -> list[float]:
    """Valores de un campo de los puntos de un barrido, sin los nulos."""
    return [punto[clave] for punto in puntos if punto.get(clave) is not None]


def _extremos(valores: list[float]) -> tuple[float | None, float | None]:
    """Mínimo y máximo, o (None, None) si no hay valores."""
    return (min(valores), max(valores)) if valores else (None, None)


def _fila_robustez(combinacion: dict) -> dict:
    """Una fila de la tabla de robustez a partir de una combinación de flujo y eficacia."""
    barrido = combinacion.get("barrido", {})
    puntos = barrido.get(CLAVE_PUNTOS, [])
    cruce = barrido.get(CLAVE_CRUCE) or {}
    reduccion_min, reduccion_max = _extremos(_valores_no_nulos(puntos, "reduccion_desgaste_pct"))
    _, incrustacion_max = _extremos(_valores_no_nulos(puntos, CLAVE_INCRUSTACION))
    valores = [
        combinacion.get("flujo_niebla_maximo_l_m2_h"),
        combinacion.get("eficacia_maxima_pulso"),
        etiqueta_llana(cruce.get("estado", "SIN_DATOS")),
        cruce.get("incrustacion_diaria_ohm"),
        cruce.get(CLAVE_CARGA),
        cruce.get(CLAVE_SEPARACION),
        reduccion_min,
        reduccion_max,
        incrustacion_max,
    ]
    return dict(zip(COLUMNAS_ROBUSTEZ, valores))


def tabla_robustez(resultado: dict) -> pd.DataFrame:
    """Una fila por combinación de flujo y eficacia con su cruce y el rango de la reducción del desgaste."""
    filas = [_fila_robustez(combinacion) for combinacion in resultado.get(CLAVE_COMBINACIONES, [])]
    return pd.DataFrame(filas, columns=COLUMNAS_ROBUSTEZ)


def _cruces_interpolados(combinaciones: list[dict]) -> list[dict]:
    """Cruces con estado INTERPOLADO de las combinaciones."""
    cruces = [(combinacion.get("barrido", {}).get(CLAVE_CRUCE) or {}) for combinacion in combinaciones]
    return [cruce for cruce in cruces if cruce.get("estado") == ESTADO_INTERPOLADO]


def _frase_desgaste_robustez(resultado: dict, total: int) -> str:
    """Rango de la reducción del desgaste entre todas las combinaciones."""
    minimo = resultado.get("reduccion_desgaste_min_pct")
    maximo = resultado.get("reduccion_desgaste_max_pct")
    if minimo is None or maximo is None:
        return "No hay datos para calcular la reducción del desgaste."
    if minimo <= 0:
        return (
            f"En las {total} combinaciones, la reducción del desgaste frente al temporizador va de {minimo:.1f} % "
            f"a {maximo:.1f} %: en algún punto {CONTROL_REGLAS} no reduce el desgaste."
        )
    return (
        f"En las {total} combinaciones, {CONTROL_REGLAS} reduce el desgaste entre {minimo:.1f} % y "
        f"{maximo:.1f} % frente al temporizador."
    )


def _frase_dependencia_cruce(cruces: list[dict]) -> str | None:
    """Compara la variación relativa de la carga por litro y de la incrustación diaria en los cruces."""
    cargas = [cruce[CLAVE_CARGA] for cruce in cruces if cruce.get(CLAVE_CARGA)]
    incrustaciones = [cruce["incrustacion_diaria_ohm"] for cruce in cruces if cruce.get("incrustacion_diaria_ohm")]
    if len(cargas) < 2 or len(incrustaciones) < 2:
        return None
    variacion_carga = max(cargas) / min(cargas)
    variacion_incrustacion = max(incrustaciones) / min(incrustaciones)
    inicio = f"La carga salina por litro del cruce va de {min(cargas):.0f} a {max(cargas):.0f} Ohm por L/m²"
    if variacion_carga > variacion_incrustacion:
        return (
            f"{inicio}: varía {variacion_carga:.1f} veces, más que la incrustación diaria del cruce "
            f"({variacion_incrustacion:.2f} veces). Es coherente con H1-Ciclo 3: el cruce depende de la "
            "incrustación diaria y no de la carga por litro."
        )
    return (
        f"{inicio}: varía {variacion_carga:.1f} veces, no más que la incrustación diaria del cruce "
        f"({variacion_incrustacion:.2f} veces). Este resultado no apoya H1-Ciclo 3."
    )


def _frase_resolucion_cruce(cruces: list[dict], minimo: float, maximo: float) -> str | None:
    """Compara la separación de los puntos interpolados con el rango del cruce entre combinaciones.

    Devuelve None si la respuesta no informa la separación (API anterior a 0.4.0).
    """
    con_separacion = [cruce for cruce in cruces if cruce.get(CLAVE_SEPARACION) is not None]
    if not con_separacion:
        return None
    separaciones = [cruce[CLAVE_SEPARACION] for cruce in con_separacion]
    inferior = min(cruce["incrustacion_inferior_ohm"] for cruce in con_separacion)
    superior = max(cruce["incrustacion_superior_ohm"] for cruce in con_separacion)
    rango = maximo - minimo
    inicio = (
        f"Los dos niveles entre los que se interpola cada cruce están separados de {min(separaciones):.0f} a "
        f"{max(separaciones):.0f} Ohm por día"
    )
    if min(separaciones) > rango:
        return (
            f"{inicio}, más que el rango del cruce entre combinaciones ({rango:.0f} Ohm por día): el barrido no "
            f"resuelve esa diferencia, y el cruce real de cada combinación está entre {inferior:.0f} y "
            f"{superior:.0f} Ohm por día."
        )
    return f"{inicio}, no más que el rango del cruce entre combinaciones ({rango:.0f} Ohm por día)."


def _frases_cruce_robustez(resultado: dict, combinaciones: list[dict]) -> list[str]:
    """Combinaciones con cruce, rango de la incrustación diaria del cruce y estados sin cruce."""
    total = len(combinaciones)
    cruces = _cruces_interpolados(combinaciones)
    minimo = resultado.get("incrustacion_diaria_cruce_min_ohm")
    maximo = resultado.get("incrustacion_diaria_cruce_max_ohm")
    if not cruces or minimo is None or maximo is None:
        frases = [f"Ninguna de las {total} combinaciones cruza: {CONTROL_REGLAS} no pasa a recuperar más."]
    else:
        frases = [
            f"{len(cruces)} de {total} combinaciones cruzan: {CONTROL_REGLAS} pasa a recuperar más que el "
            f"temporizador desde una incrustación diaria de {minimo:.0f} a {maximo:.0f} Ohm por día."
        ]
        adicionales = (_frase_dependencia_cruce(cruces), _frase_resolucion_cruce(cruces, minimo, maximo))
        frases.extend(frase for frase in adicionales if frase is not None)
    estados = [(c.get("barrido", {}).get(CLAVE_CRUCE) or {}).get("estado", "SIN_DATOS") for c in combinaciones]
    for estado in sorted(set(estados) - {ESTADO_INTERPOLADO}):
        frases.append(f"{estados.count(estado)} de {total} combinaciones: {etiqueta_llana(estado).lower()}.")
    return frases


def lectura_robustez(resultado: dict) -> list[str]:
    """Frases calculadas con la reducción del desgaste, las combinaciones con cruce y su incrustación diaria."""
    combinaciones = resultado.get(CLAVE_COMBINACIONES, [])
    if not combinaciones:
        return ["La robustez no devolvió combinaciones."]
    return [_frase_desgaste_robustez(resultado, len(combinaciones))] + _frases_cruce_robustez(
        resultado, combinaciones
    )


# ---------------------------------------------------------------------------
# Robustez del desgaste frente a la fatiga y la degradación térmica (docs/04, sección 8.11)
# ---------------------------------------------------------------------------
COLUMNA_PUNTOS_MENOR_DESGASTE = "Puntos con menor desgaste"
COLUMNAS_ROBUSTEZ_DESGASTE = [
    COLUMNA_FLUJO,
    "Fatiga por pulso (%)",
    "Degradación térmica (% por °C y min)",
    COLUMNA_REDUCCION_MIN,
    COLUMNA_REDUCCION_MAX,
    COLUMNA_PUNTOS_MENOR_DESGASTE,
]
CLAVE_FATIGA = "fatiga_por_pulso_pct"
CLAVE_DEGRADACION_TERMICA = "degradacion_termica_pct_por_c_min"
CLAVE_REDUCCION_MIN = "reduccion_desgaste_min_pct"


def configuracion_robustez_desgaste(humedad: float, numero_semillas: int) -> dict:
    """Carga de la robustez del desgaste con semillas consecutivas desde 1, acotadas al máximo del dashboard."""
    return _configuracion_con_semillas(humedad, numero_semillas, config.MAXIMO_SEMILLAS_ROBUSTEZ_DESGASTE)


def _fila_robustez_desgaste(combinacion: dict) -> dict:
    """Una fila de la tabla de robustez del desgaste a partir de una combinación de la grilla."""
    puntos = f"{combinacion.get('puntos_con_menor_desgaste', 0)} de {combinacion.get('puntos_totales', 0)}"
    valores = [
        combinacion.get("flujo_niebla_maximo_l_m2_h"),
        combinacion.get(CLAVE_FATIGA),
        combinacion.get(CLAVE_DEGRADACION_TERMICA),
        combinacion.get(CLAVE_REDUCCION_MIN),
        combinacion.get("reduccion_desgaste_max_pct"),
        puntos,
    ]
    return dict(zip(COLUMNAS_ROBUSTEZ_DESGASTE, valores))


def tabla_robustez_desgaste(resultado: dict) -> pd.DataFrame:
    """Una fila por combinación de flujo, fatiga y degradación térmica con su rango de reducción del desgaste."""
    filas = [_fila_robustez_desgaste(combinacion) for combinacion in resultado.get(CLAVE_COMBINACIONES, [])]
    return pd.DataFrame(filas, columns=COLUMNAS_ROBUSTEZ_DESGASTE)


def _frase_menor_reduccion(combinaciones: list[dict]) -> str | None:
    """Combinación con la menor reducción del desgaste, o None si ninguna la tiene."""
    con_reduccion = [combinacion for combinacion in combinaciones if combinacion.get(CLAVE_REDUCCION_MIN) is not None]
    if not con_reduccion:
        return None
    menor = min(con_reduccion, key=lambda combinacion: combinacion[CLAVE_REDUCCION_MIN])
    return (
        f"La menor reducción ({menor[CLAVE_REDUCCION_MIN]:.1f} %) aparece con una fatiga de {menor[CLAVE_FATIGA]:g} % "
        f"por pulso, una degradación térmica de {menor[CLAVE_DEGRADACION_TERMICA]:g} % por °C y minuto y un flujo "
        f"de {menor['flujo_niebla_maximo_l_m2_h']:g} L/m²/h."
    )


def lectura_robustez_desgaste(resultado: dict) -> list[str]:
    """Frases calculadas con el rango de la reducción del desgaste y las combinaciones que la sostienen."""
    combinaciones = resultado.get(CLAVE_COMBINACIONES, [])
    if not combinaciones:
        return ["La robustez del desgaste no devolvió combinaciones."]
    total = len(combinaciones)
    en_todos = resultado.get("combinaciones_con_menor_desgaste_en_todos_los_puntos", 0)
    if en_todos == total:
        sostiene = (
            f"En las {total} combinaciones, {CONTROL_REGLAS} se degrada menos que el temporizador en todos los "
            "puntos del barrido."
        )
    else:
        sostiene = (
            f"Solo en {en_todos} de {total} combinaciones {CONTROL_REGLAS} se degrada menos en todos los puntos: "
            "en las demás hay niveles de salinidad en que no reduce el desgaste."
        )
    frases = [_frase_desgaste_robustez(resultado, total), sostiene]
    menor = _frase_menor_reduccion(combinaciones)
    if menor is not None:
        frases.append(menor)
    return frases


# ---------------------------------------------------------------------------
# Barrido frente a la incrustación diaria
# ---------------------------------------------------------------------------
COLUMNAS_INCRUSTACION = ["incrustacion", "carga", "Modo", "recuperacion"]


def serie_barrido_por_incrustacion(resultado: dict) -> pd.DataFrame:
    """Recuperación media de ambos modos frente a la incrustación diaria, en formato largo.

    Se omiten los puntos sin incrustación diaria y las combinaciones de punto y modo sin recuperación.
    """
    filas = []
    for punto in resultado.get(CLAVE_PUNTOS, []):
        incrustacion = punto.get(CLAVE_INCRUSTACION)
        if incrustacion is None:
            continue
        for sufijo, modo in _SUFIJOS_MODO.items():
            recuperacion = punto.get(f"{COLUMNA_RECUPERACION}_{sufijo}_media")
            if recuperacion is not None:
                filas.append(
                    {"incrustacion": incrustacion, "carga": punto[CLAVE_CARGA], "Modo": modo, "recuperacion": recuperacion}
                )
    return pd.DataFrame(filas, columns=COLUMNAS_INCRUSTACION)


def incrustacion_cruce(resultado: dict) -> float | None:
    """Incrustación diaria del cruce del barrido, o None si no hay cruce o la respuesta no lo incluye."""
    return (resultado.get(CLAVE_CRUCE) or {}).get("incrustacion_diaria_ohm")


def lectura_cruce(resultado: dict) -> str:
    """Frase con el estado del cruce del barrido y, si existe, su incrustación diaria y su carga."""
    cruce = resultado.get(CLAVE_CRUCE)
    if not cruce:
        return "La respuesta no incluye el cruce; requiere la API 0.3.0 o posterior."
    frase = f"{etiqueta_llana(cruce['estado'])}."
    if cruce.get("incrustacion_diaria_ohm") is None:
        return frase
    frase = (
        f"{frase} El cruce está en una incrustación diaria de {cruce['incrustacion_diaria_ohm']:.0f} Ohm por día "
        f"(carga salina de {cruce[CLAVE_CARGA]:.1f} Ohm por L/m²)."
    )
    if cruce.get(CLAVE_SEPARACION) is None:
        return frase
    return (
        f"{frase} Se interpola entre los niveles de {cruce['incrustacion_inferior_ohm']:.0f} y "
        f"{cruce['incrustacion_superior_ohm']:.0f} Ohm por día, separados {cruce[CLAVE_SEPARACION]:.0f}: el cruce "
        "real puede estar en cualquier punto de ese intervalo."
    )


def etiqueta_sitio(perfil: dict) -> str:
    """Nombre de un perfil de sitio con su flujo máximo de niebla, para un selector."""
    return f"{perfil['nombre']} ({perfil['flujo_niebla_maximo_l_m2_h']:g} L/m²/h)"


def configuracion_barrido_con_flujo(humedad: float, numero_semillas: int, flujo: float | None) -> dict:
    """Carga del barrido con el flujo de niebla del perfil elegido; sin flujo usa el de la API."""
    carga = configuracion_barrido(humedad, numero_semillas)
    if flujo is not None:
        carga["flujo_niebla_maximo_l_m2_h"] = float(flujo)
    return carga


# ---------------------------------------------------------------------------
# Dimensionamiento (docs/04, sección 7.7)
# ---------------------------------------------------------------------------
ESTANDARES_CONSUMO = {
    "OMS_20": f"OMS, acceso básico ({config.CONSUMO_ACCESO_BASICO_L_PERSONA_DIA:g} L por persona al día)",
    "SPHERE_15": f"Sphere, supervivencia ({config.CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA:g} L por persona al día)",
}


def configuracion_dimensionamiento(personas: int, estandar: str, escenario: str, humedad: float) -> dict:
    """Carga del dimensionamiento con la tasa ALTA y la semilla 42 por defecto de la API."""
    return {
        "personas": int(personas),
        "estandar": estandar,
        "escenario": escenario,
        "humedad_ambiente_inicial_pct": float(humedad),
    }


def _frase_dimension(dimension: dict) -> str:
    """Área y nodos necesarios con un flujo de referencia, o aviso si el control no capta agua."""
    inicio = (
        f"Con el {etiqueta_llana(dimension['origen_flujo'])} ({dimension['flujo_niebla_maximo_l_m2_h']:g} L/m²/h)"
    )
    if dimension.get("area_colector_m2") is None:
        return f"{inicio}, {CONTROL_REGLAS} no capta agua y no es posible dimensionar."
    return (
        f"{inicio}, {CONTROL_REGLAS} rinde {dimension['rendimiento_neuro_l_m2_dia']:.2f} L/m² al día: harían "
        f"falta {dimension['area_colector_m2']:.1f} m² de colector, es decir, {dimension['nodos_requeridos']} "
        "nodos de 1 m²."
    )


def resumen_dimensionamiento(resultado: dict) -> list[str]:
    """Frases con el área y los nodos de cada flujo de referencia y el rango de área de la literatura."""
    dimensiones = resultado.get("dimensiones", [])
    if not dimensiones:
        return ["El dimensionamiento no devolvió resultados."]
    frases = [f"Consumo de {resultado['consumo_l_persona_dia']:g} L por persona al día."]
    frases.extend(_frase_dimension(dimension) for dimension in dimensiones)
    minimo = resultado.get("area_literatura_min_m2")
    maximo = resultado.get("area_literatura_max_m2")
    if minimo is not None and maximo is not None:
        frases.append(
            f"Con los rendimientos de {config.RENDIMIENTO_LITERATURA_MIN_L_M2_DIA:g} a "
            f"{config.RENDIMIENTO_LITERATURA_MAX_L_M2_DIA:g} L/m² al día de proyectos reales (Klemm et al., 2012) "
            f"harían falta entre {minimo:.1f} y {maximo:.1f} m²."
        )
    return frases


# ---------------------------------------------------------------------------
# Impacto en distintos entornos (docs/04, sección 7.8)
# ---------------------------------------------------------------------------
ZONA_SOBRE_TRANSICION = "SOBRE_TRANSICION"
PREGUNTA_CICLO_3_ENTORNOS = (
    "Pregunta para el Ciclo 3: ¿Qué rendimiento de niebla y qué carga salina tiene un sitio candidato, "
    "y en qué zona de la incrustación diaria cae?"
)
COLUMNAS_IMPACTO_ENTORNOS = (
    "Régimen de niebla",
    "Carga salina (Ω·m²/L)",
    "Rendimiento (L/m²/día)",
    "Incrustación diaria (Ω/día)",
    "Zona de incrustación",
    "Ventaja en recuperación (puntos)",
    "Reducción del desgaste (%)",
    "Nodos para la comunidad (1 m²)",
    "Litros al mes por nodo (L)",
    "Nodos que igualan 1000 L/mes (ICBF)",
)


def configuracion_impacto_entornos(personas: int, estandar: str, humedad: float) -> dict:
    """Cuerpo JSON de POST /api/v1/analisis/impacto-entornos con la semilla 42 por defecto."""
    return {
        "personas": int(personas),
        "estandar": estandar,
        "humedad_ambiente_inicial_pct": float(humedad),
    }


def tabla_impacto_entornos(resultado: dict) -> pd.DataFrame:
    """Tabla de los 18 entornos con nombres de columna llanos y régimen de niebla y zona en lenguaje llano."""
    entornos = resultado.get("entornos", [])
    filas = [
        {
            COLUMNAS_IMPACTO_ENTORNOS[0]: etiqueta_llana(entorno["origen_flujo"]),
            COLUMNAS_IMPACTO_ENTORNOS[1]: entorno["carga_salina_ohm_l_m2"],
            COLUMNAS_IMPACTO_ENTORNOS[2]: entorno.get("rendimiento_neuro_l_m2_dia"),
            COLUMNAS_IMPACTO_ENTORNOS[3]: entorno.get("incrustacion_diaria_ohm"),
            COLUMNAS_IMPACTO_ENTORNOS[4]: etiqueta_llana(entorno["zona_incrustacion"]),
            COLUMNAS_IMPACTO_ENTORNOS[5]: entorno.get("ventaja_recuperacion_pts"),
            COLUMNAS_IMPACTO_ENTORNOS[6]: entorno.get("reduccion_desgaste_pct"),
            COLUMNAS_IMPACTO_ENTORNOS[7]: entorno.get("nodos_requeridos"),
            COLUMNAS_IMPACTO_ENTORNOS[8]: entorno.get("litros_mes_por_nodo"),
            COLUMNAS_IMPACTO_ENTORNOS[9]: entorno.get("nodos_equivalentes_entrega"),
        }
        for entorno in entornos
    ]
    return pd.DataFrame(filas, columns=list(COLUMNAS_IMPACTO_ENTORNOS))


def _frase_origen_impacto(entorno: dict, personas: int, consumo: float, entrega: float) -> str:
    """Nodos que igualan la entrega del ICBF y nodos para la comunidad con la carga salina más alta."""
    etiqueta = etiqueta_llana(entorno["origen_flujo"])
    carga = entorno["carga_salina_ohm_l_m2"]
    nodos_entrega = entorno.get("nodos_equivalentes_entrega")
    nodos_comunidad = entorno.get("nodos_requeridos")
    if nodos_entrega is None or nodos_comunidad is None:
        return f"{etiqueta} con la carga salina más alta ({carga:g} Ω·m²/L): sin producción de agua para dimensionar."
    return (
        f"{etiqueta} con la carga salina más alta ({carga:g} Ω·m²/L): {nodos_entrega} nodos de 1 m² igualan "
        f"la entrega de {entrega:g} L al mes del ICBF y {nodos_comunidad} nodos abastecen a {personas} "
        f"personas ({consumo:g} L/persona/día)."
    )


def _frases_por_origen_impacto(entornos: list[dict], personas: int, consumo: float, entrega: float) -> list[str]:
    """Una frase por origen de flujo, evaluado en su nivel de carga salina más alto."""
    origenes = list(dict.fromkeys(entorno["origen_flujo"] for entorno in entornos))
    frases = []
    for origen in origenes:
        del_origen = [entorno for entorno in entornos if entorno["origen_flujo"] == origen]
        mayor_carga = max(del_origen, key=lambda entorno: entorno["carga_salina_ohm_l_m2"])
        frases.append(_frase_origen_impacto(mayor_carga, personas, consumo, entrega))
    return frases


def _frase_menor_nodos_con_ventaja(entornos: list[dict], personas: int) -> str:
    """Entorno con ventaja esperada que requiere menos nodos, o aviso si no hay ninguno."""
    candidatos = [
        entorno
        for entorno in entornos
        if entorno.get("zona_incrustacion") == ZONA_SOBRE_TRANSICION and entorno.get("nodos_requeridos") is not None
    ]
    if not candidatos:
        return "Con ninguno de los rendimientos evaluados se espera ventaja en recuperación."
    mejor = min(candidatos, key=lambda entorno: entorno["nodos_requeridos"])
    return (
        f"El entorno con ventaja esperada que requiere menos nodos para {personas} personas es "
        f"{etiqueta_llana(mejor['origen_flujo']).lower()} con carga salina de "
        f"{mejor['carga_salina_ohm_l_m2']:g} Ω·m²/L: {mejor['nodos_requeridos']} nodos de 1 m²."
    )


def lectura_impacto_entornos(resultado: dict) -> list[str]:
    """Frases de lectura del impacto por entorno y su comparación con la entrega por carrotanque del ICBF."""
    entornos = resultado.get("entornos", [])
    if not entornos:
        return ["La estimación de impacto por entorno no devolvió resultados."]
    personas = int(resultado.get("personas", 50))
    consumo = float(resultado.get("consumo_l_persona_dia", config.CONSUMO_ACCESO_BASICO_L_PERSONA_DIA))
    entrega = float(resultado.get("entrega_referencia_l_comunidad_mes", config.ENTREGA_CARROTANQUE_L_COMUNIDAD_MES))
    con_ventaja = resultado.get("entornos_con_ventaja_esperada", 0)
    coherentes = resultado.get("entornos_coherentes_con_simulacion", 0)
    clasificables = resultado.get("entornos_clasificables", 0)
    frases = [
        f"En {con_ventaja} de los {len(entornos)} entornos se espera ventaja en recuperación (zona sobre la "
        f"transición), y la regla de la incrustación coincide con la simulación en {coherentes} de los "
        f"{clasificables} entornos clasificables."
    ]
    frases.extend(_frases_por_origen_impacto(entornos, personas, consumo, entrega))
    frases.append(_frase_menor_nodos_con_ventaja(entornos, personas))
    frases.append(PREGUNTA_CICLO_3_ENTORNOS)
    return frases


# ---------------------------------------------------------------------------
# Explorador de hipótesis
# ---------------------------------------------------------------------------
LONGITUD_MAXIMA_NOMBRE_SITIO = 40
NOMBRE_SITIO_POR_DEFECTO = "SITIO_PROPIO"
_CARACTERES_NOMBRE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
CAMPOS_SITIO = (
    "nombre",
    "flujo_niebla_maximo_l_m2_h",
    "temperatura_media_c",
    "amplitud_temperatura_c",
    "amplitud_humedad_pct",
)
ETIQUETAS_PARAMETROS_USADOS = {
    "nombre_sitio": "Sitio",
    "flujo_niebla_maximo_l_m2_h": "Flujo máximo de niebla (L/m²/h)",
    "eficacia_maxima_pulso": "Eficacia máxima del pulso",
    "temperatura_media_c": "Temperatura media (°C)",
    "amplitud_temperatura_c": "Amplitud térmica diurna (°C)",
    "amplitud_humedad_pct": "Amplitud diurna de humedad (puntos)",
}


def normalizar_nombre_sitio(texto: str) -> str:
    """Convierte un texto en un nombre de sitio válido para la API: mayúsculas, dígitos y guion bajo.

    Los demás caracteres se reemplazan por guion bajo, el resultado se recorta a 40 caracteres y, si queda
    vacío, se usa SITIO_PROPIO.
    """
    nombre = "".join(caracter if caracter in _CARACTERES_NOMBRE else "_" for caracter in texto.strip().upper())
    return nombre[:LONGITUD_MAXIMA_NOMBRE_SITIO] or NOMBRE_SITIO_POR_DEFECTO


def _perfil_sitio(sitio: dict) -> dict:
    """Perfil de sitio para la API: el nombre normalizado y los campos numéricos como float."""
    perfil = {campo: sitio[campo] for campo in CAMPOS_SITIO}
    perfil["nombre"] = normalizar_nombre_sitio(str(perfil["nombre"]))
    for campo in CAMPOS_SITIO[1:]:
        perfil[campo] = float(perfil[campo])
    return perfil


def configuracion_explorador(escenario: str, tasa: str, humedad: float, eficacia: float, sitio: dict) -> dict:
    """Carga de una simulación de 24 h con la eficacia del pulso y el perfil de sitio elegidos."""
    return {
        "duracion_horas": 24,
        "escenario": escenario,
        "humedad_ambiente_inicial_pct": float(humedad),
        "tasa_salinizacion": tasa,
        "eficacia_maxima_pulso": float(eficacia),
        "sitio": _perfil_sitio(sitio),
    }


def configuracion_calibracion(rendimiento: float, escenario: str, humedad: float, sitio: dict) -> dict:
    """Carga de la calibración con el rendimiento medido, el escenario, la humedad inicial y el perfil editado.

    La API usa la temperatura y las amplitudes del perfil y reemplaza su flujo por cada valor evaluado.
    """
    return {
        "rendimiento_objetivo_l_m2_dia": float(rendimiento),
        "escenario": escenario,
        "humedad_ambiente_inicial_pct": float(humedad),
        "sitio": _perfil_sitio(sitio),
    }


def texto_calibracion(resultado: dict) -> str:
    """Frase con el flujo calibrado y el rendimiento que produce en 24 h con tasa de salinización ALTA."""
    nombre = (resultado.get("perfil") or {}).get("nombre", "el sitio")
    return (
        f"Flujo calibrado para {nombre}: {resultado['flujo_calibrado_l_m2_h']:g} L/m²/h. Con él, {CONTROL_REGLAS} "
        f"rinde {resultado['rendimiento_obtenido_l_m2_dia']:.2f} L/m² al día en 24 h con tasa de salinización ALTA. "
        "El flujo se copió en el campo del perfil."
    )


def parametros_usados_a_dataframe(resultado: dict) -> pd.DataFrame:
    """Tabla con el sitio y los parámetros con que se ejecutó la simulación; vacía si la API no los informa."""
    usados = resultado.get("parametros_usados") or {}
    filas = [
        {"Parámetro": etiqueta, "Valor": str(usados[clave])}
        for clave, etiqueta in ETIQUETAS_PARAMETROS_USADOS.items()
        if clave in usados
    ]
    return pd.DataFrame(filas, columns=["Parámetro", "Valor"])


def _pregunta_robustez(robustez: dict | None) -> str:
    """Pregunta sobre el cruce de la ventaja en recuperación, o qué análisis ejecutar."""
    if robustez is None:
        return "Falta la robustez de la respuesta: ejecútela en la vista 4, parte a, para preguntar por el cruce."
    total = len(robustez.get(CLAVE_COMBINACIONES, []))
    minimo = robustez.get("incrustacion_diaria_cruce_min_ohm")
    maximo = robustez.get("incrustacion_diaria_cruce_max_ohm")
    if not robustez.get("combinaciones_con_cruce") or minimo is None or maximo is None:
        return (
            f"Ninguna de las {total} combinaciones cruza: ¿con qué incrustación diaria, mayor que la del barrido, "
            "aparecería la ventaja en recuperación?"
        )
    return (
        f"La ventaja en recuperación aparece desde {minimo:.0f} a {maximo:.0f} Ohm por día en "
        f"{robustez['combinaciones_con_cruce']} de {total} combinaciones: ¿se reproduce ese umbral al medir en "
        "laboratorio la incrustación diaria y la recuperación de membranas con ambos controles (H1-Ciclo 3)?"
    )


def _pregunta_incertidumbre(incertidumbre: dict | None) -> str:
    """Pregunta sobre la probabilidad de ventaja con el flujo calibrado, o qué análisis ejecutar."""
    if incertidumbre is None:
        return "Falta la incertidumbre: ejecútela en la vista 4, parte c, para preguntar por el flujo real."
    probabilidad = incertidumbre.get("probabilidad_ventaja_recuperacion")
    if probabilidad is None:
        return (
            "Ninguna muestra de la incertidumbre tiene pulsos en ambos modos: ¿con qué humedad o salinidad "
            "empiezan los pulsos cuando el flujo de niebla es como el de la literatura?"
        )
    return (
        f"Con el flujo calibrado, {CONTROL_REGLAS} recupera más en una proporción de {probabilidad:.2f} de las "
        "muestras: ¿qué rendimiento de niebla y qué carga salina tiene el sitio real, y quedan por encima o por "
        "debajo del cruce?"
    )


def _pregunta_simulacion(simulacion: dict | None) -> str:
    """Pregunta sobre la carga salina que exigiría la ventaja en el sitio simulado, o qué ejecutar."""
    if simulacion is None:
        return "Falta una simulación: ejecútela en la vista 5 para preguntar por su sitio y su eficacia."
    usados = simulacion.get("parametros_usados") or {}
    rendimiento = ((simulacion.get("impacto_comunitario") or {}).get(MODO_NEURO) or {}).get("rendimiento_l_m2_dia")
    sitio = usados.get("nombre_sitio", "el sitio simulado")
    if not rendimiento or rendimiento <= 0:
        return (
            f"En {sitio}, {CONTROL_REGLAS} no captó agua: ¿qué humedad mínima necesita el sitio para que empiecen "
            "la captación y los pulsos?"
        )
    carga_min = config.INCRUSTACION_CRUCE_MIN_OHM_DIA / rendimiento
    carga_max = config.INCRUSTACION_CRUCE_MAX_OHM_DIA / rendimiento
    return (
        f"En {sitio}, {CONTROL_REGLAS} rinde {rendimiento:.2f} L/m² al día: según H1-Ciclo 3, la ventaja en "
        f"recuperación exigiría una carga salina de unos {carga_min:.0f} a {carga_max:.0f} Ohm por L/m². ¿Es esa "
        "la carga salina de la niebla del sitio?"
    )


def _pregunta_eficacia(simulacion: dict | None) -> str | None:
    """Pregunta sobre la eficacia medida si la simulación no valida la Conjetura 1 o la 2."""
    if simulacion is None:
        return None
    validadas = simulacion.get(CLAVE_VALIDADAS) or {}
    eficacia = (simulacion.get("parametros_usados") or {}).get("eficacia_maxima_pulso")
    falla = not validadas.get("conjetura_1_eficiencia", True) or not validadas.get("conjetura_2_autorreparacion", True)
    if not falla or eficacia is None:
        return None
    return (
        f"Con una eficacia de {eficacia:.2f}, al menos una de las Conjeturas 1 y 2 no se valida: ¿qué fracción de "
        "la costra remueve un pulso real de 90 s a 44 °C (docs/04, sección 6.3)?"
    )


def hipotesis_siguientes(robustez: dict | None, incertidumbre: dict | None, simulacion: dict | None) -> list[str]:
    """Preguntas para el Ciclo 3 calculadas con los análisis disponibles en la sesión.

    Cada análisis aporta una pregunta; si falta, la frase indica cuál ejecutar y en qué vista.
    """
    preguntas = [_pregunta_robustez(robustez), _pregunta_incertidumbre(incertidumbre), _pregunta_simulacion(simulacion)]
    eficacia = _pregunta_eficacia(simulacion)
    if eficacia is not None:
        preguntas.append(eficacia)
    return preguntas
