"""Dashboard simulador del motor Axioma-H.

Ejecutar desde la raíz del proyecto, con el backend en funcionamiento:
    streamlit run frontend/app.py
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Streamlit solo agrega al path la carpeta del script; se incluye la raíz para importar el paquete.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from frontend import cliente_api, config  # noqa: E402
from frontend import transformaciones as tr  # noqa: E402

st.set_page_config(page_title="Axioma-H Engine - Simulador", layout="wide")

NODOS = [f"NODO_{i:02d}" for i in range(1, 9)]
MODOS = {"NEURO_SIMBOLICO": "Neuro-simbólico", "TEMPORIZADOR_FIJO": "Temporizador fijo"}
ESCENARIOS = {
    "DIA_NORMAL": "Día normal",
    "INCRUSTACION_SALINA_RAPIDA": "Incrustación salina rápida",
    "SEQUIA": "Sequía",
    "TORMENTA_DE_ARENA": "Tormenta de arena",
    "TORMENTA_DE_SAL_Y_CALOR_EXTREMO": "Tormenta de sal y calor extremo",
}
VISTA_EVALUACION = "Evaluación manual de nodo"
VISTA_SIMULACION = "Simulación comparativa"

# Clave de session_state de cada control de telemetría.
CONTROLES = {
    "impedancia_ohms": "tel_impedancia",
    "temperatura_celsius": "tel_temperatura",
    "reserva_calor_pct": "tel_reserva",
    "humedad_relativa_pct": "tel_humedad",
    "flujo_actual_ml_min": "tel_flujo",
}
TELEMETRIA_PRD = {
    "impedancia_ohms": 1650.5,
    "temperatura_celsius": 36.2,
    "reserva_calor_pct": 55.0,
    "humedad_relativa_pct": 42.0,
    "flujo_actual_ml_min": 14.5,
}
CASOS_DEMO = {
    "Operación nominal": {
        "impedancia_ohms": 1100.0,
        "temperatura_celsius": 30.0,
        "reserva_calor_pct": 70.0,
        "humedad_relativa_pct": 80.0,
        "flujo_actual_ml_min": 15.0,
    },
    "Cristalización salina": {
        "impedancia_ohms": 1850.0,
        "temperatura_celsius": 36.0,
        "reserva_calor_pct": 65.0,
        "humedad_relativa_pct": 82.0,
        "flujo_actual_ml_min": 9.0,
    },
    "Reserva crítica": {
        "impedancia_ohms": 1850.0,
        "temperatura_celsius": 34.0,
        "reserva_calor_pct": 20.0,
        "humedad_relativa_pct": 78.0,
        "flujo_actual_ml_min": 8.0,
    },
    "Sequía (humedad bajo 30 %)": {
        "impedancia_ohms": 1200.0,
        "temperatura_celsius": 38.0,
        "reserva_calor_pct": 60.0,
        "humedad_relativa_pct": 22.0,
        "flujo_actual_ml_min": 2.0,
    },
    "Sobrecalentamiento (45 °C)": {
        "impedancia_ohms": 1700.0,
        "temperatura_celsius": 45.0,
        "reserva_calor_pct": 60.0,
        "humedad_relativa_pct": 70.0,
        "flujo_actual_ml_min": 10.0,
    },
}
RETARDO_REPRODUCCION_SEG = {"Lenta": 0.5, "Media": 0.2, "Rápida": 0.08, "Muy rápida": 0.02}
COLORES_MODO = alt.Scale(
    domain=[tr.NOMBRES_MODO["neuro"], tr.NOMBRES_MODO["temporizador"]],
    range=["#1f6f8b", "#c27c0e"],
)
COLOR_REFERENCIA = "#a93226"


# ---------------------------------------------------------------------------
# Estado de la sesión y utilidades
# ---------------------------------------------------------------------------
def inicializar_estado() -> None:
    """Define los valores iniciales de session_state una sola vez por sesión.

    Streamlit elimina las claves de los widgets que no se dibujan en una
    ejecución, por ejemplo al cambiar de vista. Reasignarlas al inicio de cada
    ejecución conserva los valores elegidos por el usuario.
    """
    widgets = {
        "tel_nodo": "NODO_04",
        "tel_modo": "NEURO_SIMBOLICO",
        "sim_duracion": 24,
        "sim_humedad": 85.0,
        "sim_tasa": "ALTA",
        "sim_nodos": 8,
        "sim_semilla": 42,
        "velocidad_reproduccion": "Media",
        "minuto_reproduccion": 0,
    }
    widgets.update({CONTROLES[campo]: valor for campo, valor in TELEMETRIA_PRD.items()})
    for clave, valor in widgets.items():
        st.session_state.setdefault(clave, valor)
        st.session_state[clave] = st.session_state[clave]

    valores = {
        "historial": [],
        "ultima_telemetria": None,
        "ultima_decision": None,
        "error_evaluacion": None,
        "resultado_simulacion": None,
        "config_simulacion": None,
        "error_simulacion": None,
        "reproduciendo": False,
        "indice_reproduccion": 0,
    }
    for clave, valor in valores.items():
        st.session_state.setdefault(clave, valor)


def formatear_duracion(segundos: float) -> str:
    """Convierte segundos en un texto 'H h MM min SS s'."""
    total = int(segundos)
    horas, resto = divmod(total, 3600)
    minutos, segs = divmod(resto, 60)
    return f"{horas} h {minutos:02d} min {segs:02d} s"


def mostrar_error(error: cliente_api.ErrorApiAxioma) -> None:
    """Muestra un error de la API y, si existe, su detalle de validación."""
    st.error(error.mensaje)
    if error.detalle:
        st.code("\n".join(error.detalle), language=None)


def cargar_caso(valores: dict) -> None:
    """Callback que precarga los controles de telemetría con un caso de demostración."""
    for campo, valor in valores.items():
        st.session_state[CONTROLES[campo]] = valor


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
def panel_conexion() -> bool:
    """Muestra el estado de la API en la barra lateral y devuelve si está disponible."""
    st.sidebar.header("Conexión con la API")
    st.sidebar.caption(config.API_URL)
    try:
        salud = cliente_api.verificar_salud()
    except cliente_api.ErrorApiAxioma as error:
        st.sidebar.error("API no disponible. Las acciones están deshabilitadas.")
        st.sidebar.write(error.mensaje)
        st.sidebar.write("Para levantarla, ejecute desde la raíz del proyecto:")
        st.sidebar.code(config.COMANDO_BACKEND, language="bash")
        st.sidebar.button("Reintentar conexión", width="stretch")
        return False
    st.sidebar.success(f"Estado: {salud['estado']}")
    st.sidebar.markdown(
        f"**Servicio:** {salud['servicio']}  \n"
        f"**Versión:** {salud['version']}  \n"
        f"**Tiempo de actividad:** {formatear_duracion(salud['tiempo_actividad_seg'])}"
    )
    return True


# ---------------------------------------------------------------------------
# Vista A: evaluación manual de nodo
# ---------------------------------------------------------------------------
def tarjeta_indicador(columna, titulo: str, valor: str, nivel: float, alerta: bool, normal: str, critico: str):
    """Tarjeta con valor, barra de nivel y zona respecto del umbral."""
    with columna.container(border=True):
        st.metric(titulo, valor)
        st.progress(min(1.0, max(0.0, nivel)))
        if alerta:
            st.markdown(f":red[**{critico}**]")
        else:
            st.markdown(f":green[{normal}]")


def panel_decision(decision: dict) -> None:
    """Muestra la decisión del motor con el color semántico de su estado."""
    estado = decision["estado_nodo"]
    resumen = f"Estado del nodo: {estado}. Acción recomendada: {decision['accion_recomendada']}."
    if estado == "NOMINAL":
        st.success(resumen)
    elif estado in ("CRISTALIZACION_DETECTADA", "RESERVA_CRITICA"):
        st.warning(resumen)
    else:
        st.error(resumen)

    if decision["pulso_termico_activo"]:
        pulso = (
            f"Activo. Temperatura objetivo {decision['temperatura_objetivo_c']:.1f} °C "
            f"durante {decision['duracion_pulso_seg']} s"
        )
    else:
        pulso = "Inactivo"
    st.markdown(
        f"**Regla activada:** `{decision['regla_activada']}`  \n"
        f"**Pulso térmico:** {pulso}  \n"
        f"**Ajuste de caudal:** {decision['ajuste_caudal_pct']:.0f} % del tope ecológico"
    )

    metricas = decision["metricas_conjeturas"]
    columnas = st.columns(3)
    columnas[0].metric("Eficiencia energética", f"{metricas['eficiencia_energetica_pct']:.2f} %", border=True)
    columnas[1].metric("Recuperación hidráulica", f"{metricas['recuperacion_hidraulica_pct']:.2f} %", border=True)
    columnas[2].metric(
        "Preservación ecológica",
        "Conforme" if metricas["preservacion_ecologica_ok"] else "No conforme",
        border=True,
    )
    st.markdown("**Motivo**")
    st.markdown(f"> {decision['motivo']}")


def evaluar_si_cambio(telemetria: dict) -> None:
    """Consulta la API solo cuando la telemetría cambió desde la última evaluación."""
    if telemetria == st.session_state.ultima_telemetria:
        return
    try:
        decision = cliente_api.evaluar_nodo(telemetria)
    except cliente_api.ErrorApiAxioma as error:
        st.session_state.error_evaluacion = error
        return
    st.session_state.error_evaluacion = None
    st.session_state.ultima_telemetria = telemetria
    st.session_state.ultima_decision = decision
    entrada = {
        "hora": datetime.now().strftime("%H:%M:%S"),
        "nodo": decision["nodo_id"],
        "regla": decision["regla_activada"],
        "motivo": decision["motivo"],
    }
    st.session_state.historial = (st.session_state.historial + [entrada])[-20:]


def vista_evaluacion(api_disponible: bool) -> None:
    """Panel de telemetría en tiempo real con evaluación automática."""
    st.header("Evaluación manual de nodo")
    st.caption("La decisión del motor se recalcula automáticamente al mover cualquier control.")

    st.markdown("**Casos de demostración**")
    columnas = st.columns(len(CASOS_DEMO))
    for columna, (nombre, valores) in zip(columnas, CASOS_DEMO.items()):
        columna.button(
            nombre,
            key=f"demo_{nombre}",
            on_click=cargar_caso,
            args=(valores,),
            disabled=not api_disponible,
            width="stretch",
        )

    col_controles, col_panel = st.columns([1, 2], gap="large")
    bloqueado = not api_disponible
    with col_controles:
        st.subheader("Telemetría")
        st.selectbox("Nodo", NODOS, key="tel_nodo", disabled=bloqueado)
        st.selectbox(
            "Modo de operación", list(MODOS), format_func=MODOS.get, key="tel_modo", disabled=bloqueado
        )
        st.slider("Impedancia (Ω)", 500.0, 3000.0, step=0.5, key="tel_impedancia", disabled=bloqueado)
        st.slider("Temperatura de la matriz (°C)", 20.0, 60.0, step=0.1, key="tel_temperatura", disabled=bloqueado)
        st.slider("Reserva de calor (%)", 0.0, 100.0, step=0.5, key="tel_reserva", disabled=bloqueado)
        st.slider("Humedad relativa (%)", 0.0, 100.0, step=0.5, key="tel_humedad", disabled=bloqueado)
        st.slider("Flujo actual (ml/min)", 0.0, 30.0, step=0.1, key="tel_flujo", disabled=bloqueado)

    telemetria = {
        "nodo_id": st.session_state.tel_nodo,
        "modo_operacion": st.session_state.tel_modo,
        **{campo: float(st.session_state[clave]) for campo, clave in CONTROLES.items()},
    }
    zonas = tr.zonas_telemetria(telemetria)

    with col_panel:
        tarjetas = st.columns(4)
        tarjeta_indicador(
            tarjetas[0], "Impedancia", f"{telemetria['impedancia_ohms']:.1f} Ω",
            (telemetria["impedancia_ohms"] - 500.0) / 2500.0, zonas["impedancia_ohms"],
            "Zona normal (<= 1500 Ω)", "Sobre 1500 Ω: cristalización",
        )
        tarjeta_indicador(
            tarjetas[1], "Temperatura", f"{telemetria['temperatura_celsius']:.1f} °C",
            (telemetria["temperatura_celsius"] - 20.0) / 40.0, zonas["temperatura_celsius"],
            "Zona normal (< 45 °C)", "En o sobre 45 °C: corte térmico",
        )
        tarjeta_indicador(
            tarjetas[2], "Reserva de Calor", f"{telemetria['reserva_calor_pct']:.1f} %",
            telemetria["reserva_calor_pct"] / 100.0, zonas["reserva_calor_pct"],
            "Zona normal (>= 30 %)", "Bajo 30 %: reserva crítica",
        )
        tarjeta_indicador(
            tarjetas[3], "Humedad Relativa", f"{telemetria['humedad_relativa_pct']:.1f} %",
            telemetria["humedad_relativa_pct"] / 100.0, zonas["humedad_relativa_pct"],
            "Zona normal (>= 30 %)", "Bajo 30 %: límite ecológico",
        )

        st.subheader("Decisión del motor")
        if not api_disponible:
            st.info("La evaluación se habilitará cuando la API esté disponible.")
        else:
            evaluar_si_cambio(telemetria)
            if st.session_state.error_evaluacion is not None:
                mostrar_error(st.session_state.error_evaluacion)
            elif st.session_state.ultima_decision is not None:
                panel_decision(st.session_state.ultima_decision)

    st.subheader("Historial de decisiones")
    st.caption("Últimas 20 decisiones de la sesión, de la más reciente a la más antigua.")
    st.code(tr.historial_a_texto(reversed(st.session_state.historial)), language=None, wrap_lines=True)


# ---------------------------------------------------------------------------
# Vista B: simulación comparativa
# ---------------------------------------------------------------------------
def grafico_comparativo(df: pd.DataFrame, col_neuro: str, col_temp: str, titulo: str, eje_y: str, referencia=None):
    """Gráfico de líneas de ambos modos con línea de referencia opcional."""
    largo = tr.series_formato_largo(df, col_neuro, col_temp)
    lineas = (
        alt.Chart(largo)
        .mark_line()
        .encode(
            x=alt.X("hora_simulada:Q", title="Horas desde el inicio (18:00)"),
            y=alt.Y("valor:Q", title=eje_y, scale=alt.Scale(zero=False)),
            color=alt.Color("Modo:N", scale=COLORES_MODO, legend=alt.Legend(orient="bottom")),
            tooltip=[
                alt.Tooltip("hora_local:N", title="Hora local"),
                alt.Tooltip("Modo:N"),
                alt.Tooltip("valor:Q", title=eje_y, format=".2f"),
            ],
        )
    )
    return _con_referencia(lineas, referencia).properties(title=titulo, height=280)


def grafico_entorno(df: pd.DataFrame, columna: str, titulo: str, eje_y: str, referencia, etiqueta: str):
    """Gráfico de una variable del entorno con su umbral de referencia."""
    lineas = (
        alt.Chart(df)
        .mark_line(color="#4a6572")
        .encode(
            x=alt.X("hora_simulada:Q", title="Horas desde el inicio (18:00)"),
            y=alt.Y(f"{columna}:Q", title=eje_y, scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("hora_local:N", title="Hora local"), alt.Tooltip(f"{columna}:Q", format=".2f")],
        )
    )
    return _con_referencia(lineas, referencia, etiqueta).properties(title=titulo, height=260)


def _con_referencia(grafico, referencia, etiqueta: str = "Umbral"):
    """Superpone una línea horizontal discontinua en el valor de referencia."""
    if referencia is None:
        return grafico
    regla = (
        alt.Chart(pd.DataFrame({"y": [referencia], "etiqueta": [etiqueta]}))
        .mark_rule(color=COLOR_REFERENCIA, strokeDash=[6, 4])
        .encode(y="y:Q", tooltip=[alt.Tooltip("etiqueta:N", title="Referencia"), alt.Tooltip("y:Q", title="Valor")])
    )
    return alt.layer(grafico, regla)


def formatear_valor(clave: str, valor: float) -> str:
    """Formato de las métricas comparativas según su naturaleza."""
    if clave in ("pulsos_termicos_ejecutados", "violaciones_ecologicas"):
        return f"{int(valor)}"
    return f"{valor:,.2f}"


def seccion_comparativa(resultado: dict) -> None:
    """Tarjetas de ambos modos con la diferencia porcentual del neuro-simbólico."""
    st.subheader("Comparativa de modos")
    st.caption("Valor principal: modo neuro-simbólico. La variación se calcula frente al temporizador fijo.")
    filas = tr.comparativa_a_dataframe(resultado).to_dict("records")
    columnas = st.columns(len(filas))
    for columna, fila in zip(columnas, filas):
        diferencia = fila["Diferencia (%)"]
        delta = None if pd.isna(diferencia) else f"{diferencia:+.1f} % frente al temporizador"
        columna.metric(
            fila["Métrica"],
            formatear_valor(fila["clave"], fila[tr.NOMBRES_MODO["neuro"]]),
            delta=delta,
            delta_color="normal" if fila["mayor_es_mejor"] else "inverse",
            border=True,
        )
        columna.caption(
            f"Temporizador fijo: {formatear_valor(fila['clave'], fila[tr.NOMBRES_MODO['temporizador']])}"
        )


def seccion_conjeturas(resultado: dict) -> None:
    """Estado de las tres conjeturas con su tabla de indicadores."""
    st.subheader("Verificación de conjeturas")
    st.caption(
        "Resultados calculados por el modelo con parámetros físicos supuestos. "
        "Una conjetura se valida solo si todos sus indicadores cumplen; los marcados como informativos "
        "no intervienen en la validación. Ver docs/modelo_simulacion.md."
    )
    columnas = st.columns(3)
    for columna, conjetura in zip(columnas, tr.conjeturas_a_lista(resultado)):
        with columna.container(border=True):
            st.markdown(f"**{conjetura['nombre']}**")
            if conjetura["validada"]:
                st.success("VALIDADA")
            else:
                st.error("NO VALIDADA")
            st.dataframe(conjetura["indicadores"], hide_index=True, width="stretch")


def seccion_graficos(df: pd.DataFrame, resultado: dict) -> None:
    """Gráficos temporales comparativos, del entorno y de totales."""
    st.subheader("Evolución temporal")
    fila_1 = st.columns(2)
    fila_1[0].altair_chart(
        grafico_comparativo(df, "litros_acumulados_neuro", "litros_acumulados_temporizador",
                            "Agua captada acumulada", "Litros"),
        width="stretch",
    )
    fila_1[1].altair_chart(
        grafico_comparativo(df, "energia_acumulada_neuro_wh", "energia_acumulada_temporizador_wh",
                            "Energía consumida acumulada", "Wh"),
        width="stretch",
    )
    fila_2 = st.columns(2)
    fila_2[0].altair_chart(
        grafico_comparativo(df, "integridad_promedio_neuro_pct", "integridad_promedio_temporizador_pct",
                            "Integridad promedio de la membrana", "%"),
        width="stretch",
    )
    fila_2[1].altair_chart(
        grafico_comparativo(df, "impedancia_promedio_neuro_ohms", "impedancia_promedio_temporizador_ohms",
                            "Impedancia promedio (referencia 1500 Ω)", "Ω", config.UMBRAL_IMPEDANCIA_OHMS),
        width="stretch",
    )

    st.subheader("Condiciones del entorno")
    fila_3 = st.columns(2)
    fila_3[0].altair_chart(
        grafico_entorno(df, "humedad_relativa_pct", "Humedad relativa promedio (referencia 30 %)", "%",
                        config.UMBRAL_HUMEDAD_ECOLOGICA_PCT, "Límite ecológico"),
        width="stretch",
    )
    fila_3[1].altair_chart(
        grafico_entorno(df, "temperatura_c", "Temperatura ambiente (referencia 45 °C)", "°C",
                        config.UMBRAL_TEMPERATURA_CORTE_C, "Corte térmico de la matriz"),
        width="stretch",
    )
    st.caption(
        "El umbral de 45 °C aplica a la matriz, que se calienta por encima del ambiente con la radiación solar."
    )

    st.subheader("Totales finales")
    totales = tr.totales_a_dataframe(resultado)
    columnas = st.columns(3)
    for columna, metrica in zip(columnas, totales["Métrica"].unique()):
        barras = (
            alt.Chart(totales[totales["Métrica"] == metrica])
            .mark_bar()
            .encode(
                x=alt.X("Modo:N", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Valor:Q", title=metrica),
                color=alt.Color("Modo:N", scale=COLORES_MODO, legend=None),
                tooltip=["Modo:N", alt.Tooltip("Valor:Q", format=".2f")],
            )
            .properties(title=metrica, height=260)
        )
        columna.altair_chart(barras, width="stretch")


def seccion_bitacora(resultado: dict) -> None:
    """Consola de decisiones del modo neuro-simbólico con filtros."""
    st.subheader("Consola de decisiones (modo neuro-simbólico)")
    bitacora = resultado["bitacora"]
    columnas = st.columns(2)
    nodos = sorted({e["nodo_id"] for e in bitacora})
    reglas = sorted({e["regla_activada"] for e in bitacora})
    nodo = columnas[0].selectbox("Filtrar por nodo", ["Todos"] + nodos, key="filtro_nodo")
    regla = columnas[1].selectbox("Filtrar por regla", ["Todas"] + reglas, key="filtro_regla")
    filtro_nodo = None if nodo == "Todos" else nodo
    filtro_regla = None if regla == "Todas" else regla
    cantidad = len(tr.filtrar_bitacora(bitacora, filtro_nodo, filtro_regla))
    st.caption(f"{cantidad} eventos. Se registran solo los cambios de regla de cada nodo; hora local.")
    st.code(tr.bitacora_a_texto(bitacora, filtro_nodo, filtro_regla), language=None, height=360)


def seccion_descargas(resultado: dict, df: pd.DataFrame) -> None:
    """Botones de descarga de las series y de la respuesta completa."""
    escenario = st.session_state.config_simulacion["escenario"].lower()
    columnas = st.columns(2)
    columnas[0].download_button(
        "Descargar series temporales (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"axioma_h_{escenario}_series.csv",
        mime="text/csv",
        width="stretch",
    )
    columnas[1].download_button(
        "Descargar respuesta completa (JSON)",
        data=json.dumps(resultado, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"axioma_h_{escenario}_resultado.json",
        mime="application/json",
        width="stretch",
    )


def iniciar_reproduccion() -> None:
    """Callback del botón Reproducir."""
    st.session_state.reproduciendo = True


def detener_reproduccion() -> None:
    """Callback del botón Detener: fija el slider en el último paso mostrado."""
    st.session_state.reproduciendo = False
    series = st.session_state.resultado_simulacion["series_temporales"]
    indice = min(st.session_state.indice_reproduccion, len(series) - 1)
    st.session_state.minuto_reproduccion = series[indice]["minuto"]


def dibujar_paso(marcador, punto: dict) -> None:
    """Muestra el estado de la red en un paso de la simulación."""
    with marcador.container(border=True):
        st.markdown(f"**{tr.etiqueta_tiempo(punto['minuto'])}** (minuto {punto['minuto']})")
        columnas = st.columns(5)
        columnas[0].metric("Humedad relativa", f"{punto['humedad_relativa_pct']:.1f} %")
        columnas[0].metric("Temperatura ambiente", f"{punto['temperatura_c']:.1f} °C")
        columnas[1].metric("Impedancia neuro", f"{punto['impedancia_promedio_neuro_ohms']:.1f} Ω")
        columnas[1].metric("Impedancia temporizador", f"{punto['impedancia_promedio_temporizador_ohms']:.1f} Ω")
        columnas[2].metric("Agua neuro", f"{punto['litros_acumulados_neuro']:.2f} L")
        columnas[2].metric("Agua temporizador", f"{punto['litros_acumulados_temporizador']:.2f} L")
        columnas[3].metric("Energía neuro", f"{punto['energia_acumulada_neuro_wh']:.1f} Wh")
        columnas[3].metric("Energía temporizador", f"{punto['energia_acumulada_temporizador_wh']:.1f} Wh")
        columnas[4].metric("Integridad neuro", f"{punto['integridad_promedio_neuro_pct']:.3f} %")
        columnas[4].metric("Integridad temporizador", f"{punto['integridad_promedio_temporizador_pct']:.3f} %")


def seccion_reproduccion(resultado: dict) -> None:
    """Reproducción paso a paso de las series temporales.

    Se ubica al final de la página porque el bucle de reproducción bloquea la
    ejecución del script hasta terminar o hasta que se pulse Detener.
    """
    st.subheader("Reproducción paso a paso")
    series = resultado["series_temporales"]
    paso = series[1]["minuto"] - series[0]["minuto"] if len(series) > 1 else 1
    ultimo_minuto = series[-1]["minuto"]
    reproduciendo = st.session_state.reproduciendo

    columnas = st.columns([1, 1, 2])
    columnas[0].button("Reproducir", on_click=iniciar_reproduccion, disabled=reproduciendo, width="stretch")
    columnas[1].button("Detener", on_click=detener_reproduccion, disabled=not reproduciendo, width="stretch")
    velocidad = columnas[2].select_slider(
        "Velocidad", options=list(RETARDO_REPRODUCCION_SEG), key="velocidad_reproduccion"
    )
    if len(series) > 1:
        minuto = st.slider(
            "Minuto de simulación", 0, ultimo_minuto, step=paso, key="minuto_reproduccion", disabled=reproduciendo
        )
    else:
        minuto = 0
    marcador = st.empty()

    indice_actual = min(minuto // paso, len(series) - 1)
    if not reproduciendo:
        dibujar_paso(marcador, series[indice_actual])
        return

    inicio = 0 if indice_actual >= len(series) - 1 else indice_actual
    for indice in range(inicio, len(series)):
        st.session_state.indice_reproduccion = indice
        dibujar_paso(marcador, series[indice])
        time.sleep(RETARDO_REPRODUCCION_SEG[velocidad])
    st.session_state.reproduciendo = False
    st.session_state.minuto_pendiente = ultimo_minuto
    st.rerun()


def ejecutar_escenario(escenario: str, parametros: dict) -> None:
    """Llama a la API y guarda el resultado en session_state."""
    carga = {"escenario": escenario, **parametros}
    with st.spinner(f"Ejecutando la simulación '{ESCENARIOS[escenario]}'..."):
        try:
            resultado = cliente_api.ejecutar_simulacion(carga)
        except cliente_api.ErrorApiAxioma as error:
            st.session_state.error_simulacion = error
            return
    st.session_state.error_simulacion = None
    st.session_state.resultado_simulacion = resultado
    st.session_state.config_simulacion = carga
    st.session_state.reproduciendo = False
    st.session_state.indice_reproduccion = 0
    st.session_state.minuto_reproduccion = 0
    # Los filtros dependen de los nodos y reglas del resultado anterior.
    st.session_state.pop("filtro_nodo", None)
    st.session_state.pop("filtro_regla", None)


def vista_simulacion(api_disponible: bool) -> None:
    """Selector de escenarios, resultados, gráficos y consola de la simulación."""
    st.header("Simulación comparativa")
    st.caption(
        "Ambos modos se ejecutan sobre el mismo entorno y con la misma semilla. "
        "La simulación inicia a las 18:00 hora local."
    )

    # El valor pendiente se aplica antes de crear el slider de reproducción.
    if "minuto_pendiente" in st.session_state:
        st.session_state.minuto_reproduccion = st.session_state.pop("minuto_pendiente")

    with st.expander("Parámetros de simulación"):
        columnas = st.columns(5)
        duracion = columnas[0].slider("Duración (h)", 1, 72, key="sim_duracion")
        humedad = columnas[1].slider("Humedad inicial (%)", 0.0, 100.0, step=0.5, key="sim_humedad")
        tasa = columnas[2].selectbox("Tasa de salinización", ["BAJA", "MEDIA", "ALTA"], key="sim_tasa")
        nodos = columnas[3].slider("Número de nodos", 1, 8, key="sim_nodos")
        semilla = columnas[4].number_input("Semilla", step=1, key="sim_semilla")
    parametros = {
        "duracion_horas": int(duracion),
        "humedad_ambiente_inicial_pct": float(humedad),
        "tasa_salinizacion": tasa,
        "numero_nodos": int(nodos),
        "semilla": int(semilla),
    }

    st.markdown("**Escenario**")
    columnas = st.columns(len(ESCENARIOS))
    seleccionado = None
    for columna, (clave, nombre) in zip(columnas, ESCENARIOS.items()):
        if columna.button(nombre, key=f"escenario_{clave}", disabled=not api_disponible, width="stretch"):
            seleccionado = clave
    if seleccionado:
        ejecutar_escenario(seleccionado, parametros)

    if st.session_state.error_simulacion is not None:
        mostrar_error(st.session_state.error_simulacion)

    resultado = st.session_state.resultado_simulacion
    if resultado is None:
        st.info("Seleccione un escenario para ejecutar la simulación.")
        return

    carga = st.session_state.config_simulacion
    st.markdown(
        f"Resultado de **{ESCENARIOS[carga['escenario']]}**: {carga['duracion_horas']} h, "
        f"{carga['numero_nodos']} nodos, humedad inicial {carga['humedad_ambiente_inicial_pct']:.1f} %, "
        f"salinización {carga['tasa_salinizacion']}, semilla {carga['semilla']}."
    )
    df = tr.series_a_dataframe(resultado)
    seccion_comparativa(resultado)
    seccion_conjeturas(resultado)
    seccion_graficos(df, resultado)
    seccion_bitacora(resultado)
    seccion_descargas(resultado, df)
    seccion_reproduccion(resultado)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def main() -> None:
    """Construye la página según la vista seleccionada."""
    inicializar_estado()
    st.title("Axioma-H Engine")
    st.caption("Simulador del motor de control neuro-simbólico para captación pasiva de agua atmosférica.")

    api_disponible = panel_conexion()
    st.sidebar.divider()
    vista = st.sidebar.radio("Vista", [VISTA_EVALUACION, VISTA_SIMULACION], key="vista")

    if vista == VISTA_EVALUACION:
        vista_evaluacion(api_disponible)
    else:
        vista_simulacion(api_disponible)


main()
