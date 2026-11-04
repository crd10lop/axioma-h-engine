"""Dashboard simulador del motor Axioma-H.

Ejecutar desde la raíz del proyecto, con el backend en funcionamiento:
    streamlit run frontend/app.py
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import altair as alt
import pandas as pd
import streamlit as st

# Streamlit solo agrega al path la carpeta del script; se incluye la raíz para importar el paquete.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from frontend import cliente_api, config, contenido  # noqa: E402
from frontend import transformaciones as tr  # noqa: E402

st.set_page_config(page_title="Axioma-H Engine - Simulador", layout="wide")

NODOS = [f"NODO_{i:02d}" for i in range(1, 9)]
MODO_NEURO = "NEURO_SIMBOLICO"
MODOS = {MODO_NEURO: "Neuro-simbólico", "TEMPORIZADOR_FIJO": "Temporizador fijo"}
ESCENARIOS = {
    "DIA_NORMAL": "Día normal",
    "INCRUSTACION_SALINA_RAPIDA": "Incrustación salina rápida",
    "SEQUIA": "Sequía",
    "TORMENTA_DE_ARENA": "Tormenta de arena",
    "TORMENTA_DE_SAL_Y_CALOR_EXTREMO": "Tormenta de sal y calor extremo",
}
VISTA_EVALUACION = "Evaluación manual de nodo"
VISTA_SIMULACION = "Simulación comparativa"
VISTA_INVESTIGACION = contenido.VISTAS[0]
VISTA_RESPUESTA = contenido.VISTAS[3]

# Clave de session_state de cada control de telemetría.
CONTROLES = {
    "impedancia_ohms": "tel_impedancia",
    "temperatura_celsius": "tel_temperatura",
    "reserva_calor_pct": "tel_reserva",
    "humedad_relativa_pct": "tel_humedad",
    "flujo_actual_ml_min": "tel_flujo",
}
# Controles de selección que un caso de demostración puede fijar además de la telemetría.
CAMPO_ANULACION = "anulacion_manual"
CLAVE_ANULACION = "tel_anulacion"
SELECTORES = {"modo_operacion": "tel_modo", CAMPO_ANULACION: CLAVE_ANULACION}
ANULACION_POR_DEFECTO = "NINGUNA"
# Opciones de supervisión humana (REGLA_06), con el valor que espera la API.
ANULACIONES = {
    ANULACION_POR_DEFECTO: "Sin intervención: decide el motor",
    "SUSPENDER_EXTRACCION": "Suspender la extracción",
    "INHIBIR_PULSO": "Impedir el pulso de limpieza",
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
    "Operador inhibe el pulso": {
        "impedancia_ohms": 1850.0,
        "temperatura_celsius": 36.0,
        "reserva_calor_pct": 65.0,
        "humedad_relativa_pct": 82.0,
        "flujo_actual_ml_min": 9.0,
        "modo_operacion": MODO_NEURO,
        CAMPO_ANULACION: "INHIBIR_PULSO",
    },
}
RETARDO_REPRODUCCION_SEG = {"Lenta": 0.5, "Media": 0.2, "Rápida": 0.08, "Muy rápida": 0.02}
COLORES_MODO = alt.Scale(
    domain=[tr.NOMBRES_MODO["neuro"], tr.NOMBRES_MODO["temporizador"]],
    range=["#1f6f8b", "#c27c0e"],
)
COLOR_REFERENCIA = "#a93226"
CAMPO_MODO = "Modo:N"
COLUMNA_METRICA = "Métrica"


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
        "tel_modo": MODO_NEURO,
        CLAVE_ANULACION: ANULACION_POR_DEFECTO,
        "sim_duracion": 24,
        "sim_humedad": 85.0,
        "sim_tasa": "ALTA",
        "sim_nodos": 8,
        "sim_semilla": 42,
        "velocidad_reproduccion": "Media",
        "minuto_reproduccion": 0,
        "resp_humedad": 85.0,
        "resp_semillas": 1,
        "sens_parametro": "EFICACIA_MAXIMA_PULSO",
        "sens_escenario": "DIA_NORMAL",
    }
    widgets.update({CONTROLES[campo]: valor for campo, valor in TELEMETRIA_PRD.items()})
    for clave, valor in widgets.items():
        st.session_state[clave] = st.session_state.get(clave, valor)

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
        "resultado_barrido": None,
        "error_barrido": None,
        "resultado_sensibilidad": None,
        "error_sensibilidad": None,
    }
    for clave, valor in valores.items():
        st.session_state.setdefault(clave, valor)


# Las respuestas se guardan una hora por configuración: repetir una simulación o un análisis
# con los mismos parámetros no vuelve a llamar a la API. Los errores no se guardan.
@st.cache_data(ttl=3600, show_spinner=False)
def simulacion_en_cache(carga: dict) -> dict:
    """Ejecuta la simulación comparativa, o devuelve la respuesta guardada para la misma carga."""
    return cliente_api.ejecutar_simulacion(carga)


@st.cache_data(ttl=3600, show_spinner=False)
def barrido_en_cache(carga: dict) -> dict:
    """Ejecuta el barrido de salinidad, o devuelve la respuesta guardada para la misma carga."""
    return cliente_api.ejecutar_barrido(carga)


@st.cache_data(ttl=3600, show_spinner=False)
def sensibilidad_en_cache(carga: dict) -> dict:
    """Ejecuta el análisis de sensibilidad, o devuelve la respuesta guardada para la misma carga."""
    return cliente_api.ejecutar_sensibilidad(carga)


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
    """Callback que precarga los controles de telemetría con un caso de demostración.

    Los casos que no indican anulación manual la restablecen a NINGUNA, para que muestren la
    decisión automática del motor. El modo de operación solo cambia si el caso lo indica.
    """
    st.session_state[CLAVE_ANULACION] = ANULACION_POR_DEFECTO
    for campo, valor in valores.items():
        st.session_state[CONTROLES.get(campo) or SELECTORES[campo]] = valor


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
def panel_conexion() -> bool:
    """Muestra el estado de la API en la barra lateral y devuelve si está disponible."""
    st.sidebar.header("Conexión con la API")
    st.sidebar.caption(config.API_URL)
    try:
        with st.spinner("Conectando con la API; si está suspendida puede tardar cerca de un minuto..."):
            salud = cliente_api.verificar_salud()
    except cliente_api.ErrorApiAxioma as error:
        st.sidebar.error("API no disponible. Las acciones están deshabilitadas.")
        st.sidebar.write(error.mensaje)
        if config.API_LOCAL:
            st.sidebar.write("Para levantarla, ejecute desde la raíz del proyecto:")
            st.sidebar.code(config.COMANDO_BACKEND, language="bash")
        else:
            st.sidebar.write("Verifique que el servicio de la API esté activo en la plataforma de despliegue.")
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
# Recorrido guiado
# ---------------------------------------------------------------------------
def ir_a_siguiente_vista(actual: str) -> None:
    """Selecciona en la barra lateral la vista que sigue a la actual."""
    st.session_state.vista = contenido.siguiente_vista(actual)


def boton_siguiente_vista(actual: str) -> None:
    """Dibuja el botón hacia la vista siguiente del recorrido; la última vista no lo lleva."""
    siguiente = contenido.siguiente_vista(actual)
    if siguiente is None:
        return
    st.divider()
    st.button(f"Siguiente: {siguiente}", on_click=ir_a_siguiente_vista, args=(actual,), type="primary")


def tabla_textos(filas: list[dict], columnas: dict[str, str]) -> None:
    """Muestra una tabla de textos con encabezados legibles, indexada por la primera columna."""
    df = pd.DataFrame(filas).rename(columns=columnas)
    st.table(df.set_index(df.columns[0]))


# ---------------------------------------------------------------------------
# Vista de investigación y guía
# ---------------------------------------------------------------------------
def vista_investigacion() -> None:
    """Pregunta, conjeturas, reglas, perspectivas y alcance del estudio. No depende de la API."""
    st.header(VISTA_INVESTIGACION)
    st.caption("Contexto del estudio antes de usar el simulador. Las vistas 2 a 4 requieren la API.")

    st.subheader("Pregunta de investigación")
    st.info(contenido.PREGUNTA_INVESTIGACION)
    st.markdown(f"**Versión divulgativa.** {contenido.VERSION_DIVULGATIVA}")
    st.markdown(f"**Hipótesis de trabajo.** {contenido.HIPOTESIS}")

    st.subheader("Respuesta preliminar del simulador")
    st.markdown(contenido.lista_markdown(contenido.RESPUESTA_PRELIMINAR))

    st.subheader("Conjeturas")
    tabla_textos(contenido.CONJETURAS, contenido.COLUMNAS_CONJETURAS)

    st.subheader("Reglas de control")
    tabla_textos(contenido.REGLAS, contenido.COLUMNAS_REGLAS)
    st.caption(contenido.NOTA_REGLAS)

    st.subheader("Perspectivas del estudio")
    columnas = st.columns(len(contenido.PERSPECTIVAS))
    for columna, (clave, texto) in zip(columnas, contenido.PERSPECTIVAS.items()):
        columna.markdown(f"**{contenido.TITULOS_PERSPECTIVAS[clave]}**")
        columna.write(texto)

    st.subheader("Alcance y madurez")
    st.markdown(contenido.MADUREZ)

    with st.expander("Supuestos clave y limitaciones"):
        tabla_textos(contenido.SUPUESTOS_CLAVE, contenido.COLUMNAS_SUPUESTOS)
        st.markdown(contenido.lista_markdown(contenido.LIMITACIONES))
    with st.expander("Glosario"):
        for termino, definicion in contenido.glosario_ordenado():
            st.markdown(f"**{termino}:** {definicion}")
    with st.expander("Referencias"):
        st.markdown(contenido.lista_markdown(contenido.REFERENCIAS))

    boton_siguiente_vista(VISTA_INVESTIGACION)


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
    elif estado in ("CRISTALIZACION_DETECTADA", "RESERVA_CRITICA", "SUPERVISION_HUMANA"):
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
        st.selectbox(
            "Supervisión humana",
            list(ANULACIONES),
            format_func=ANULACIONES.get,
            key=CLAVE_ANULACION,
            disabled=bloqueado,
            help=(
                "El operador solo puede ser más conservador que el motor. El corte térmico y la pausa "
                "ecológica prevalecen sobre su decisión. No aplica en modo temporizador fijo."
            ),
        )

    telemetria = {
        "nodo_id": st.session_state.tel_nodo,
        "modo_operacion": st.session_state.tel_modo,
        CAMPO_ANULACION: st.session_state[CLAVE_ANULACION],
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

    boton_siguiente_vista(VISTA_EVALUACION)


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
            color=alt.Color(CAMPO_MODO, scale=COLORES_MODO, legend=alt.Legend(orient="bottom")),
            tooltip=[
                alt.Tooltip("hora_local:N", title="Hora local"),
                alt.Tooltip(CAMPO_MODO),
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


def formatear_valor(clave: str, valor: Optional[float]) -> str:
    """Formato de las métricas comparativas según su naturaleza."""
    if valor is None or pd.isna(valor):
        return "Sin datos"
    if clave in ("pulsos_termicos_ejecutados", "violaciones_ecologicas"):
        return f"{int(valor)}"
    return f"{valor:,.2f}"


def seccion_comparativa(resultado: dict) -> None:
    """Tarjetas de ambos modos con la diferencia porcentual del neuro-simbólico."""
    st.subheader("Comparativa de modos")
    st.caption("Valor principal: modo neuro-simbólico. La variación se calcula frente al temporizador fijo.")
    filas = tr.comparativa_a_dataframe(resultado).to_dict("records")
    tarjetas_por_fila = 4
    columnas = []
    for _ in range(0, len(filas), tarjetas_por_fila):
        columnas.extend(st.columns(tarjetas_por_fila))
    for columna, fila in zip(columnas, filas):
        diferencia = fila["Diferencia (%)"]
        delta = None if pd.isna(diferencia) else f"{diferencia:+.1f} % frente al temporizador"
        columna.metric(
            fila[COLUMNA_METRICA],
            formatear_valor(fila["clave"], fila[tr.NOMBRES_MODO["neuro"]]),
            delta=delta,
            delta_color="normal" if fila["mayor_es_mejor"] else "inverse",
            border=True,
        )
        columna.caption(
            f"Temporizador fijo: {formatear_valor(fila['clave'], fila[tr.NOMBRES_MODO['temporizador']])}"
        )

    # Referencia con el mismo tope ecológico: separa el efecto del tope del de la lógica de control.
    linea_referencia = tr.texto_modo_referencia(resultado)
    if linea_referencia is not None:
        st.caption(linea_referencia)
    brecha = tr.texto_brecha_agua(resultado)
    if brecha is not None:
        st.info(brecha)


def seccion_impacto(resultado: dict) -> None:
    """Personas abastecidas y rendimiento frente a la literatura; se omite si la API no lo entrega."""
    frases = tr.resumen_impacto(resultado)
    if frases is None:
        return
    st.subheader("Impacto comunitario estimado")
    st.caption(
        "Indicador informativo: no interviene en la validación de las conjeturas. Estándares de la OMS "
        "(Howard et al., 2020), Sphere (2018) y rango de Klemm et al. (2012)."
    )
    st.markdown(contenido.lista_markdown(frases))


def seccion_conjeturas(resultado: dict) -> None:
    """Estado de las tres conjeturas con su tabla de indicadores."""
    st.subheader("Verificación de conjeturas")
    st.caption(
        "Resultados calculados por el modelo con parámetros físicos supuestos. "
        "Una conjetura se valida solo si todos sus indicadores cumplen; los marcados como informativos "
        "no intervienen en la validación. Ver docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md."
    )
    columnas = st.columns(3)
    for columna, conjetura in zip(columnas, tr.conjeturas_a_lista(resultado)):
        with columna.container(border=True):
            st.markdown(f"**{conjetura['nombre']}**")
            if conjetura["validada"]:
                st.success("VALIDADA")
            else:
                st.error("NO VALIDADA")
                for causa in conjetura["causas"]:
                    st.markdown(f"- {causa}")
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

    with st.expander("Condiciones del entorno"):
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
    for columna, metrica in zip(columnas, totales[COLUMNA_METRICA].unique()):
        barras = (
            alt.Chart(totales[totales[COLUMNA_METRICA] == metrica])
            .mark_bar()
            .encode(
                x=alt.X(CAMPO_MODO, title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Valor:Q", title=metrica),
                color=alt.Color(CAMPO_MODO, scale=COLORES_MODO, legend=None),
                tooltip=[CAMPO_MODO, alt.Tooltip("Valor:Q", format=".2f")],
            )
            .properties(title=metrica, height=260)
        )
        columna.altair_chart(barras, width="stretch")


def seccion_bitacora(resultado: dict) -> None:
    """Consola de decisiones del modo neuro-simbólico con filtros."""
    with st.expander("Consola de decisiones (modo neuro-simbólico)"):
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
    with st.expander("Reproducción paso a paso"):
        _contenido_reproduccion(resultado)


def _contenido_reproduccion(resultado: dict) -> None:
    """Controles y bucle de la reproducción; se dibuja dentro del desplegable de seccion_reproduccion."""
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
            resultado = simulacion_en_cache(carga)
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
    st.subheader("Resumen ejecutivo")
    st.markdown(contenido.lista_markdown(tr.resumen_ejecutivo(resultado)))
    seccion_comparativa(resultado)
    seccion_impacto(resultado)
    seccion_conjeturas(resultado)
    seccion_graficos(df, resultado)
    seccion_bitacora(resultado)
    seccion_descargas(resultado, df)
    seccion_reproduccion(resultado)


# ---------------------------------------------------------------------------
# Vista C: respuesta a la pregunta (análisis de robustez)
# ---------------------------------------------------------------------------
def ejecutar_analisis(funcion, carga: dict, clave: str, mensaje: str) -> None:
    """Llama a un endpoint de análisis y guarda el resultado o el error en session_state."""
    with st.spinner(mensaje):
        try:
            st.session_state[f"resultado_{clave}"] = funcion(carga)
            st.session_state[f"error_{clave}"] = None
        except cliente_api.ErrorApiAxioma as error:
            st.session_state[f"error_{clave}"] = error


def grafico_barrido(df: pd.DataFrame, variable: str, titulo: str, eje_y: str, referencia=None):
    """Media por modo frente a la carga salina, con una banda de +/- una desviación estándar."""
    datos = df[df["Variable"] == variable]
    base = alt.Chart(datos).encode(
        x=alt.X("carga:Q", title="Carga salina (Ohm por L/m²)"),
        color=alt.Color(CAMPO_MODO, scale=COLORES_MODO, legend=alt.Legend(orient="bottom")),
    )
    banda = base.mark_area(opacity=0.2).encode(y=alt.Y("inferior:Q", title=eje_y, scale=alt.Scale(zero=False)), y2="superior:Q")
    lineas = base.mark_line(point=True).encode(
        y=alt.Y("media:Q", title=eje_y),
        tooltip=[
            alt.Tooltip(CAMPO_MODO),
            alt.Tooltip("carga:Q", title="Carga salina"),
            alt.Tooltip("media:Q", title="Media", format=".3f"),
            alt.Tooltip("desv:Q", title="Desviación", format=".3f"),
        ],
    )
    return _con_referencia(alt.layer(banda, lineas), referencia).properties(title=titulo, height=300)


def seccion_barrido(api_disponible: bool) -> None:
    """Barrido de salinidad con varias semillas: gráficos de recuperación y degradación y su lectura."""
    st.subheader("Barrido de salinidad")
    columnas = st.columns(3)
    humedad = columnas[0].slider("Humedad inicial (%)", 0.0, 100.0, step=0.5, key="resp_humedad")
    semillas = columnas[1].slider(
        "Número de semillas", 1, tr.MAXIMO_SEMILLAS, key="resp_semillas",
        help="Se usan semillas consecutivas desde 1. Cada semilla genera un clima de referencia distinto.",
    )
    columnas[2].write("")
    if columnas[2].button("Ejecutar barrido", disabled=not api_disponible, type="primary", width="stretch"):
        ejecutar_analisis(
            barrido_en_cache, tr.configuracion_barrido(humedad, semillas), "barrido",
            "Ejecutando el barrido de salinidad...",
        )
    if st.session_state.error_barrido is not None:
        mostrar_error(st.session_state.error_barrido)
    resultado = st.session_state.resultado_barrido
    if resultado is None:
        st.info("Ejecute el barrido para comparar ambos modos en seis niveles de carga salina.")
        return

    df = tr.barrido_a_dataframe(resultado)
    graficos = st.columns(2)
    graficos[0].altair_chart(
        grafico_barrido(df, tr.VARIABLE_RECUPERACION, "Recuperación tras pulso (referencia 90 %)", "%",
                        config.RECUPERACION_MINIMA_PCT),
        width="stretch",
    )
    graficos[1].altair_chart(
        grafico_barrido(df, tr.VARIABLE_DEGRADACION, "Degradación acumulada de la membrana", "%"),
        width="stretch",
    )
    st.markdown(contenido.lista_markdown(tr.lectura_barrido(resultado)))


def seccion_sensibilidad(api_disponible: bool) -> None:
    """Sensibilidad a un parámetro supuesto: indicador frente al valor y estado de las conjeturas."""
    st.subheader("Sensibilidad a un parámetro supuesto")
    columnas = st.columns(3)
    parametro = columnas[0].selectbox(
        "Parámetro", list(tr.VALORES_SENSIBILIDAD), format_func=tr.NOMBRES_PARAMETRO.get, key="sens_parametro"
    )
    escenario = columnas[1].selectbox("Escenario", list(ESCENARIOS), format_func=ESCENARIOS.get, key="sens_escenario")
    columnas[2].write("")
    if columnas[2].button("Ejecutar sensibilidad", disabled=not api_disponible, width="stretch"):
        carga = tr.configuracion_sensibilidad(parametro, escenario, st.session_state.resp_humedad)
        ejecutar_analisis(sensibilidad_en_cache, carga, "sensibilidad", "Ejecutando la sensibilidad...")
    valores = ", ".join(f"{valor:g}" for valor in tr.VALORES_SENSIBILIDAD[parametro])
    st.caption(f"Valores evaluados: {valores}. Humedad inicial del barrido y tasa de salinización ALTA.")
    if st.session_state.error_sensibilidad is not None:
        mostrar_error(st.session_state.error_sensibilidad)
    resultado = st.session_state.resultado_sensibilidad
    if resultado is None:
        st.info("Ejecute la sensibilidad para ver cómo cambia el estado de las conjeturas con el parámetro.")
        return

    parametro_resultado = resultado["parametro"]
    df = tr.sensibilidad_a_dataframe(resultado)
    columna, etiqueta, umbral = tr.INDICADOR_SENSIBILIDAD[parametro_resultado]
    lineas = (
        alt.Chart(df)
        .mark_line(point=True, color="#1f6f8b")
        .encode(
            x=alt.X(f"{tr.COLUMNA_VALOR}:Q", title=tr.NOMBRES_PARAMETRO[parametro_resultado], scale=alt.Scale(zero=False)),
            y=alt.Y(f"{columna}:Q", title=etiqueta, scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip(f"{tr.COLUMNA_VALOR}:Q", title="Valor"), alt.Tooltip(f"{columna}:Q", format=".2f")],
        )
    )
    st.altair_chart(
        _con_referencia(lineas, umbral, "Umbral de la conjetura").properties(title=etiqueta, height=280),
        width="stretch",
    )
    st.dataframe(df.rename(columns=tr.ETIQUETAS_SENSIBILIDAD), hide_index=True, width="stretch")


def vista_respuesta(api_disponible: bool) -> None:
    """Respuesta a la pregunta de investigación con el barrido de salinidad y la sensibilidad."""
    st.header(VISTA_RESPUESTA)
    st.info(contenido.PREGUNTA_INVESTIGACION)
    st.markdown(f"**Hipótesis de trabajo.** {contenido.HIPOTESIS}")
    st.warning(contenido.AVISO_EXPLORATORIO)
    seccion_barrido(api_disponible)
    seccion_sensibilidad(api_disponible)


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
    vista = st.sidebar.radio("Recorrido", contenido.VISTAS, format_func=contenido.etiqueta_vista, key="vista")

    if vista == VISTA_INVESTIGACION:
        vista_investigacion()
    elif vista == VISTA_EVALUACION:
        vista_evaluacion(api_disponible)
    elif vista == VISTA_RESPUESTA:
        vista_respuesta(api_disponible)
    else:
        vista_simulacion(api_disponible)
        # La simulación puede terminar antes de mostrar resultados, por eso el botón se dibuja aquí.
        boton_siguiente_vista(VISTA_SIMULACION)


main()
