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
MODOS = {MODO_NEURO: "Control basado en reglas", "TEMPORIZADOR_FIJO": "Temporizador fijo"}
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
VISTA_EXPLORADOR = contenido.VISTAS[4]
LECTURA_BREVE = "Lectura breve"
LECTURA_COMPLETA = "Lectura completa"
NIVELES_LECTURA = [LECTURA_BREVE, LECTURA_COMPLETA]
TASAS = ["BAJA", "MEDIA", "ALTA"]
ETIQUETA_ESCENARIO = "Escenario"
# Clave de session_state de cada campo editable del perfil de sitio en el explorador.
CAMPOS_EXPLORADOR = {
    "nombre": "exp_nombre",
    "flujo_niebla_maximo_l_m2_h": "exp_flujo",
    "temperatura_media_c": "exp_temperatura",
    "amplitud_temperatura_c": "exp_amplitud_temperatura",
    "amplitud_humedad_pct": "exp_amplitud_humedad",
}

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
COLOR_NEURO = "#1f6f8b"
COLOR_TEMPORIZADOR = "#c27c0e"
COLORES_MODO = alt.Scale(
    domain=[tr.NOMBRES_MODO["neuro"], tr.NOMBRES_MODO["temporizador"]],
    range=[COLOR_NEURO, COLOR_TEMPORIZADOR],
)
ESCENARIO_INICIAL = "DIA_NORMAL"
ETIQUETA_HUMEDAD = "Humedad inicial (%)"
COLOR_REFERENCIA = "#a93226"
CAMPO_MODO = "Modo:N"
CAMPO_CARGA = "carga:Q"
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
        "sens_escenario": ESCENARIO_INICIAL,
        "inc_escenario": ESCENARIO_INICIAL,
        "inc_humedad": 85.0,
        "inc_muestras": tr.MUESTRAS_INCERTIDUMBRE_POR_DEFECTO,
        "rob_humedad": 85.0,
        "rob_semillas": 1,
        "resp_perfil": config.PERFIL_SITIO_POR_DEFECTO["nombre"],
        "dim_personas": 50,
        "dim_estandar": "OMS_20",
        "dim_escenario": ESCENARIO_INICIAL,
        "dim_humedad": 85.0,
        "imp_personas": 50,
        "imp_estandar": "OMS_20",
        "imp_humedad": 85.0,
        "exp_escenario": ESCENARIO_INICIAL,
        "exp_tasa": "ALTA",
        "exp_humedad": 85.0,
        "exp_eficacia": config.EFICACIA_SUPUESTA,
        "exp_perfil": config.PERFIL_SITIO_POR_DEFECTO["nombre"],
        "exp_rendimiento": config.RENDIMIENTO_LITERATURA_MAX_L_M2_DIA,
        "nivel_lectura": LECTURA_COMPLETA,
    }
    widgets.update({CONTROLES[campo]: valor for campo, valor in TELEMETRIA_PRD.items()})
    widgets.update(
        {clave: config.PERFIL_SITIO_POR_DEFECTO[campo] for campo, clave in CAMPOS_EXPLORADOR.items()}
    )
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
        "resultado_incertidumbre": None,
        "error_incertidumbre": None,
        "resultado_robustez": None,
        "error_robustez": None,
        "resultado_robustez_desgaste": None,
        "error_robustez_desgaste": None,
        "resultado_calibracion": None,
        "error_calibracion": None,
        "resultado_dimensionamiento": None,
        "error_dimensionamiento": None,
        "resultado_impacto_entornos": None,
        "error_impacto_entornos": None,
        "resultado_explorador": None,
        "error_explorador": None,
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


@st.cache_data(ttl=3600, show_spinner=False)
def incertidumbre_en_cache(carga: dict) -> dict:
    """Ejecuta la propagación de la incertidumbre, o devuelve la respuesta guardada para la misma carga."""
    return cliente_api.ejecutar_incertidumbre(carga)


@st.cache_data(ttl=3600, show_spinner=False)
def robustez_en_cache(carga: dict) -> dict:
    """Ejecuta la robustez de la respuesta, o devuelve la respuesta guardada para la misma carga."""
    return cliente_api.ejecutar_robustez(carga)


@st.cache_data(ttl=3600, show_spinner=False)
def robustez_desgaste_en_cache(carga: dict) -> dict:
    """Ejecuta la robustez del desgaste, o devuelve la respuesta guardada para la misma carga."""
    return cliente_api.ejecutar_robustez_desgaste(carga)


@st.cache_data(ttl=3600, show_spinner=False)
def calibracion_en_cache(carga: dict) -> dict:
    """Calibra el flujo de niebla, o devuelve la respuesta guardada para la misma carga."""
    return cliente_api.calibrar_flujo(carga)


@st.cache_data(ttl=3600, show_spinner=False)
def dimensionamiento_en_cache(carga: dict) -> dict:
    """Ejecuta el dimensionamiento, o devuelve la respuesta guardada para la misma carga."""
    return cliente_api.dimensionar(carga)


@st.cache_data(ttl=3600, show_spinner=False)
def impacto_entornos_en_cache(carga: dict) -> dict:
    """Estima el impacto por entorno, o devuelve la respuesta guardada para la misma carga."""
    return cliente_api.ejecutar_impacto_entornos(carga)


@st.cache_data(ttl=3600, show_spinner=False)
def sitios_en_cache() -> list[dict]:
    """Consulta los perfiles de sitio, o devuelve la respuesta guardada durante una hora."""
    return cliente_api.obtener_sitios()


def obtener_perfiles(api_disponible: bool) -> list[dict]:
    """Perfiles de sitio de la API; lista vacía, con un aviso, si la API no los entrega."""
    if not api_disponible:
        return []
    try:
        return sitios_en_cache()
    except cliente_api.ErrorApiAxioma as error:
        st.warning(f"No fue posible consultar los perfiles de sitio. {error.mensaje}")
        return []


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


def es_lectura_breve() -> bool:
    """Indica si el nivel de lectura elegido en la barra lateral es el breve."""
    return st.session_state.get("nivel_lectura") == LECTURA_BREVE


# ---------------------------------------------------------------------------
# Vista de investigación y guía
# ---------------------------------------------------------------------------
def _contenido_investigacion_breve() -> None:
    """Resumen en lenguaje llano de la pregunta, el hallazgo, la certeza, la comunidad y lo pendiente."""
    for clave, titulo in contenido.TITULOS_LECTURA_BREVE.items():
        st.subheader(titulo)
        st.markdown(contenido.LECTURA_BREVE[clave])


def _contenido_investigacion_completo() -> None:
    """Contenido completo de la vista de investigación y guía."""
    st.subheader("Pregunta de investigación")
    st.info(contenido.PREGUNTA_INVESTIGACION)
    st.markdown(f"**Versión divulgativa.** {contenido.VERSION_DIVULGATIVA}")
    st.markdown(f"**Hipótesis de trabajo.** {contenido.HIPOTESIS}")
    st.success(f"**Tesis actual.** {contenido.TESIS}")
    st.info(f"**Hipótesis derivada.** {contenido.HIPOTESIS_DERIVADA}")
    with st.expander("Detalle de la respuesta por análisis"):
        st.markdown("**Respuesta preliminar del simulador**")
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

    st.subheader("Supuestos clave y qué los reemplazaría")
    tabla_textos(contenido.SUPUESTOS_CLAVE, contenido.COLUMNAS_SUPUESTOS)

    with st.expander("Guía de lectura por disciplina"):
        filas = [{"disciplina": nombre, **guia} for nombre, guia in contenido.GUIA_DISCIPLINAS.items()]
        tabla_textos(filas, {"disciplina": "Disciplina", **contenido.COLUMNAS_GUIA})
    with st.expander("Limitaciones"):
        st.markdown(contenido.lista_markdown(contenido.LIMITACIONES))
    with st.expander("Glosario"):
        for termino, definicion in contenido.glosario_ordenado():
            st.markdown(f"**{termino}:** {definicion}")
    with st.expander("Referencias"):
        st.markdown(contenido.lista_markdown(contenido.REFERENCIAS))


def vista_investigacion() -> None:
    """Pregunta, conjeturas, reglas, perspectivas y alcance del estudio. No depende de la API."""
    st.header(VISTA_INVESTIGACION)
    st.caption("Contexto del estudio antes de usar el simulador. Las vistas 2 a 5 requieren la API.")
    with st.expander("¿A quién se dirige cada nivel de lectura?"):
        tabla_textos(contenido.PUBLICOS, contenido.COLUMNAS_PUBLICOS)

    if es_lectura_breve():
        _contenido_investigacion_breve()
        with st.expander("Ver la lectura completa"):
            _contenido_investigacion_completo()
    else:
        _contenido_investigacion_completo()

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
    accion = decision["accion_recomendada"]
    resumen = f"Estado del nodo: {tr.etiqueta_llana(estado)}. Acción recomendada: {tr.etiqueta_llana(accion)}."
    if estado == "NOMINAL":
        st.success(resumen)
    elif estado in ("CRISTALIZACION_DETECTADA", "RESERVA_CRITICA", "SUPERVISION_HUMANA"):
        st.warning(resumen)
    else:
        st.error(resumen)
    st.caption(f"Códigos de la API: estado {estado}, acción {accion}.")

    if decision["pulso_termico_activo"]:
        pulso = (
            f"Activo. Temperatura objetivo {decision['temperatura_objetivo_c']:.1f} °C "
            f"durante {decision['duracion_pulso_seg']} s"
        )
    else:
        pulso = "Inactivo"
    st.markdown(f"**Regla activada:** {tr.etiqueta_llana(decision['regla_activada'])}")
    st.caption(f"Código de la regla: {decision['regla_activada']}")
    st.markdown(
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
    """Tarjetas de ambos modos con la diferencia porcentual del control basado en reglas."""
    st.subheader("Comparativa de modos")
    st.caption("Valor principal: control basado en reglas. La variación se calcula frente al temporizador fijo.")
    st.caption(contenido.NOTA_CODIGO_MODO)
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
    condiciones = tr.condiciones_de_cambio(resultado)
    for indice, (columna, conjetura) in enumerate(zip(columnas, tr.conjeturas_a_lista(resultado))):
        with columna.container(border=True):
            st.markdown(f"**{conjetura['nombre']}**")
            if conjetura["validada"]:
                st.success("VALIDADA")
            else:
                st.error("NO VALIDADA")
                for causa in conjetura["causas"]:
                    st.markdown(f"- {causa}")
            st.dataframe(conjetura["indicadores"], hide_index=True, width="stretch")
            if indice < len(condiciones):
                with st.expander("Qué cambiaría este resultado"):
                    st.markdown(condiciones[indice])


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
    """Consola de decisiones del control basado en reglas con filtros."""
    with st.expander("Consola de decisiones (control basado en reglas)"):
        bitacora = resultado["bitacora"]
        columnas = st.columns(2)
        nodos = sorted({e["nodo_id"] for e in bitacora})
        reglas = sorted({e["regla_activada"] for e in bitacora})
        nodo = columnas[0].selectbox("Filtrar por nodo", ["Todos"] + nodos, key="filtro_nodo")
        regla = columnas[1].selectbox(
            "Filtrar por regla", ["Todas"] + reglas, format_func=tr.etiqueta_llana, key="filtro_regla"
        )
        filtro_nodo = None if nodo == "Todos" else nodo
        filtro_regla = None if regla == "Todas" else regla
        if filtro_regla is not None:
            columnas[1].caption(f"Código de la regla: {filtro_regla}")
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
        columnas[1].metric("Impedancia con reglas", f"{punto['impedancia_promedio_neuro_ohms']:.1f} Ω")
        columnas[1].metric("Impedancia temporizador", f"{punto['impedancia_promedio_temporizador_ohms']:.1f} Ω")
        columnas[2].metric("Agua con reglas", f"{punto['litros_acumulados_neuro']:.2f} L")
        columnas[2].metric("Agua temporizador", f"{punto['litros_acumulados_temporizador']:.2f} L")
        columnas[3].metric("Energía con reglas", f"{punto['energia_acumulada_neuro_wh']:.1f} Wh")
        columnas[3].metric("Energía temporizador", f"{punto['energia_acumulada_temporizador_wh']:.1f} Wh")
        columnas[4].metric("Integridad con reglas", f"{punto['integridad_promedio_neuro_pct']:.3f} %")
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
        humedad = columnas[1].slider(ETIQUETA_HUMEDAD, 0.0, 100.0, step=0.5, key="sim_humedad")
        tasa = columnas[2].selectbox("Tasa de salinización", TASAS, key="sim_tasa")
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


def tablero_veredictos() -> None:
    """Tablero de veredictos en cuatro columnas al inicio de la vista 4."""
    columnas = st.columns(len(contenido.VEREDICTOS))
    for columna, item in zip(columnas, contenido.VEREDICTOS):
        with columna.container(border=True):
            st.metric(
                label=contenido.PARTES_RESPUESTA[item["parte"]]["titulo"],
                value=item["veredicto"],
                help=item["falta_medir"],
            )
            st.caption(item["cifra"])


def encabezado_parte(clave: str) -> None:
    """Título de una parte de la respuesta y la frase que dice qué parte de la pregunta responde."""
    parte = contenido.PARTES_RESPUESTA[clave]
    st.subheader(parte["titulo"])
    if es_lectura_breve():
        st.info(contenido.LECTURA_BREVE_PARTES[clave])
    st.markdown(parte["frase"])


def grafico_robustez_desgaste(df: pd.DataFrame):
    """Reducción mínima del desgaste frente a la fatiga por pulso, por degradación térmica y flujo."""
    return (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                field=tr.COLUMNA_FATIGA_DESGASTE,
                type="quantitative",
                title=tr.COLUMNA_FATIGA_DESGASTE,
            ),
            y=alt.Y(
                field=tr.COLUMNA_REDUCCION_MIN_GRAFICO_DESGASTE,
                type="quantitative",
                title=tr.COLUMNA_REDUCCION_MIN_GRAFICO_DESGASTE,
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color(
                field=tr.COLUMNA_DEGRADACION_TERMICA_DESGASTE,
                type="nominal",
                title=tr.COLUMNA_DEGRADACION_TERMICA_DESGASTE,
                legend=alt.Legend(orient="bottom"),
            ),
            column=alt.Column(
                field=tr.COLUMNA_FLUJO_GRAFICO_DESGASTE,
                type="nominal",
                title=tr.COLUMNA_FLUJO_GRAFICO_DESGASTE,
            ),
            tooltip=[
                alt.Tooltip(field=tr.COLUMNA_FLUJO_GRAFICO_DESGASTE, type="quantitative", format=".2f"),
                alt.Tooltip(field=tr.COLUMNA_FATIGA_DESGASTE, type="quantitative", format=".2f"),
                alt.Tooltip(field=tr.COLUMNA_DEGRADACION_TERMICA_DESGASTE, type="quantitative", format=".3f"),
                alt.Tooltip(field=tr.COLUMNA_REDUCCION_MIN_GRAFICO_DESGASTE, type="quantitative", format=".2f"),
            ],
        )
        .properties(height=260)
    )


def grafico_incrustacion(serie: pd.DataFrame, cruce: float | None):
    """Recuperación de ambos modos frente a la incrustación diaria, con una línea vertical en el cruce."""
    lineas = (
        alt.Chart(serie)
        .mark_line(point=True)
        .encode(
            x=alt.X("incrustacion:Q", title="Incrustación diaria (Ohm por día)"),
            y=alt.Y("recuperacion:Q", title="Recuperación tras pulso (%)", scale=alt.Scale(zero=False)),
            color=alt.Color(CAMPO_MODO, scale=COLORES_MODO, legend=alt.Legend(orient="bottom")),
            tooltip=[
                alt.Tooltip(CAMPO_MODO),
                alt.Tooltip("incrustacion:Q", title="Incrustación diaria", format=".0f"),
                alt.Tooltip(CAMPO_CARGA, title="Carga salina"),
                alt.Tooltip("recuperacion:Q", title="Recuperación (%)", format=".2f"),
            ],
        )
    )
    grafico = _con_referencia(lineas, config.RECUPERACION_MINIMA_PCT)
    if cruce is not None:
        vertical = (
            alt.Chart(pd.DataFrame({"x": [cruce], "etiqueta": ["Cruce"]}))
            .mark_rule(color=COLOR_REFERENCIA)
            .encode(x="x:Q", tooltip=[alt.Tooltip("etiqueta:N", title="Referencia"), alt.Tooltip("x:Q", format=".0f")])
        )
        grafico = alt.layer(grafico, vertical)
    return grafico.properties(title="Recuperación frente a la incrustación diaria (referencia 90 %)", height=300)


def seccion_robustez(api_disponible: bool) -> None:
    """Robustez de la respuesta: tabla de las nueve combinaciones de flujo y eficacia y su lectura."""
    columnas = st.columns(3)
    humedad = columnas[0].slider(ETIQUETA_HUMEDAD, 0.0, 100.0, step=0.5, key="rob_humedad")
    semillas = columnas[1].slider("Número de semillas", 1, tr.MAXIMO_SEMILLAS_ROBUSTEZ, key="rob_semillas")
    columnas[2].write("")
    if columnas[2].button("Ejecutar robustez", disabled=not api_disponible, type="primary", width="stretch"):
        ejecutar_analisis(
            robustez_en_cache, tr.configuracion_robustez(humedad, semillas), "robustez",
            "Repitiendo el barrido con nueve combinaciones de parámetros...",
        )
    if st.session_state.error_robustez is not None:
        mostrar_error(st.session_state.error_robustez)
    resultado = st.session_state.resultado_robustez
    if resultado is None:
        st.info("Ejecute la robustez para ver si la reducción del desgaste depende de los parámetros supuestos.")
        return
    st.dataframe(tr.tabla_robustez(resultado), hide_index=True, width="stretch")
    st.markdown(contenido.lista_markdown(tr.lectura_robustez(resultado)))


def seccion_robustez_desgaste(api_disponible: bool) -> None:
    """Robustez del desgaste: tabla de las 18 combinaciones de flujo, fatiga por pulso y degradación térmica."""
    st.markdown("**Robustez del desgaste frente a la fatiga y la degradación térmica**")
    st.caption(
        "Repite el barrido con el flujo supuesto y el calibrado máximo, y con la mitad, el valor supuesto y el "
        "doble de la fatiga por pulso y de la degradación térmica. Usa la humedad inicial de la robustez y una "
        "semilla, para respetar el tiempo de espera del despliegue; las semillas 1 a 3 se pueden ejecutar con la "
        "API (docs/04, sección 8.11)."
    )
    if st.button("Ejecutar robustez del desgaste", disabled=not api_disponible):
        carga = tr.configuracion_robustez_desgaste(st.session_state.rob_humedad, st.session_state.rob_semillas)
        ejecutar_analisis(
            robustez_desgaste_en_cache, carga, "robustez_desgaste",
            "Repitiendo el barrido con 18 combinaciones de fatiga y degradación térmica...",
        )
    if st.session_state.error_robustez_desgaste is not None:
        mostrar_error(st.session_state.error_robustez_desgaste)
    resultado = st.session_state.resultado_robustez_desgaste
    if resultado is None:
        st.info("Ejecute la robustez del desgaste para ver si la reducción depende de la fatiga y la degradación supuestas.")
        return
    st.altair_chart(grafico_robustez_desgaste(tr.datos_grafico_robustez_desgaste(resultado)))
    st.dataframe(tr.tabla_robustez_desgaste(resultado), hide_index=True, width="stretch")
    st.markdown(contenido.lista_markdown(tr.lectura_robustez_desgaste(resultado)))


def seccion_dimensionamiento(api_disponible: bool) -> None:
    """Dimensionamiento: área de colector y nodos para un número de personas."""
    columnas = st.columns(5)
    personas = columnas[0].number_input("Personas", 1, 1000, step=1, key="dim_personas")
    estandar = columnas[1].selectbox(
        "Consumo", list(tr.ESTANDARES_CONSUMO), format_func=tr.ESTANDARES_CONSUMO.get, key="dim_estandar"
    )
    escenario = columnas[2].selectbox(ETIQUETA_ESCENARIO, list(ESCENARIOS), format_func=ESCENARIOS.get, key="dim_escenario")
    humedad = columnas[3].slider(ETIQUETA_HUMEDAD, 0.0, 100.0, step=0.5, key="dim_humedad")
    columnas[4].write("")
    if columnas[4].button("Dimensionar", disabled=not api_disponible, width="stretch"):
        carga = tr.configuracion_dimensionamiento(personas, estandar, escenario, humedad)
        ejecutar_analisis(dimensionamiento_en_cache, carga, "dimensionamiento", "Dimensionando el captador...")
    if st.session_state.error_dimensionamiento is not None:
        mostrar_error(st.session_state.error_dimensionamiento)
    resultado = st.session_state.resultado_dimensionamiento
    if resultado is None:
        st.info("Indique el número de personas y presione Dimensionar.")
        return
    st.markdown(contenido.lista_markdown(tr.resumen_dimensionamiento(resultado)))


def seccion_impacto_entornos(api_disponible: bool) -> None:
    """Impacto en distintos entornos de niebla y salinidad y comparación con entrega por carrotanque."""
    st.markdown("**Impacto en distintos entornos**")
    st.caption(
        "Combina tres regímenes de niebla y seis niveles de salinidad. La entrega de referencia es la del ICBF "
        "por carrotanque en La Guajira: 1000 L al mes por comunidad (ICBF, 2025)."
    )
    columnas = st.columns(4)
    personas = columnas[0].number_input("Personas", 1, 1000, step=1, key="imp_personas")
    estandar = columnas[1].selectbox(
        "Consumo", list(tr.ESTANDARES_CONSUMO), format_func=tr.ESTANDARES_CONSUMO.get, key="imp_estandar"
    )
    humedad = columnas[2].slider(ETIQUETA_HUMEDAD, 0.0, 100.0, step=0.5, key="imp_humedad")
    columnas[3].write("")
    if columnas[3].button("Estimar impacto por entorno", disabled=not api_disponible, width="stretch"):
        carga = tr.configuracion_impacto_entornos(personas, estandar, humedad)
        ejecutar_analisis(
            impacto_entornos_en_cache, carga, "impacto_entornos", "Estimando el impacto en los 18 entornos..."
        )
    if st.session_state.error_impacto_entornos is not None:
        mostrar_error(st.session_state.error_impacto_entornos)
    resultado = st.session_state.resultado_impacto_entornos
    if resultado is None:
        st.info("Indique el número de personas y presione Estimar impacto por entorno.")
        return
    st.dataframe(tr.tabla_impacto_entornos(resultado), hide_index=True, width="stretch")
    st.markdown(contenido.lista_markdown(tr.lectura_impacto_entornos(resultado)))


def grafico_barrido(df: pd.DataFrame, variable: str, titulo: str, eje_y: str, referencia=None):
    """Media por modo frente a la carga salina, con una banda de +/- una desviación estándar."""
    datos = df[df["Variable"] == variable]
    base = alt.Chart(datos).encode(
        x=alt.X(CAMPO_CARGA, title="Carga salina (Ohm por L/m²)"),
        color=alt.Color(CAMPO_MODO, scale=COLORES_MODO, legend=alt.Legend(orient="bottom")),
    )
    banda = base.mark_area(opacity=0.2).encode(y=alt.Y("inferior:Q", title=eje_y, scale=alt.Scale(zero=False)), y2="superior:Q")
    lineas = base.mark_line(point=True).encode(
        y=alt.Y("media:Q", title=eje_y),
        tooltip=[
            alt.Tooltip(CAMPO_MODO),
            alt.Tooltip(CAMPO_CARGA, title="Carga salina"),
            alt.Tooltip("media:Q", title="Media", format=".3f"),
            alt.Tooltip("desv:Q", title="Desviación", format=".3f"),
        ],
    )
    return _con_referencia(alt.layer(banda, lineas), referencia).properties(title=titulo, height=300)


def seccion_barrido(api_disponible: bool) -> None:
    """Barrido de salinidad con el flujo de un perfil de sitio: recuperación frente a la incrustación diaria."""
    perfiles = {perfil["nombre"]: perfil for perfil in obtener_perfiles(api_disponible)}
    columnas = st.columns(4)
    humedad = columnas[0].slider(ETIQUETA_HUMEDAD, 0.0, 100.0, step=0.5, key="resp_humedad")
    semillas = columnas[1].slider(
        "Número de semillas", 1, tr.MAXIMO_SEMILLAS, key="resp_semillas",
        help="Se usan semillas consecutivas desde 1. Cada semilla genera un clima de referencia distinto.",
    )
    flujo = None
    if perfiles:
        if st.session_state.resp_perfil not in perfiles:
            st.session_state.resp_perfil = next(iter(perfiles))
        nombre = columnas[2].selectbox(
            "Flujo de niebla", list(perfiles), format_func=lambda clave: tr.etiqueta_sitio(perfiles[clave]),
            key="resp_perfil", help="Flujo supuesto o extremos calibrados contra la literatura (GET /api/v1/sitios).",
        )
        flujo = perfiles[nombre]["flujo_niebla_maximo_l_m2_h"]
    columnas[3].write("")
    if columnas[3].button("Ejecutar barrido", disabled=not api_disponible, type="primary", width="stretch"):
        ejecutar_analisis(
            barrido_en_cache, tr.configuracion_barrido_con_flujo(humedad, semillas, flujo), "barrido",
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
        grafico_incrustacion(tr.serie_barrido_por_incrustacion(resultado), tr.incrustacion_cruce(resultado)),
        width="stretch",
    )
    graficos[1].altair_chart(
        grafico_barrido(df, tr.VARIABLE_DEGRADACION, "Degradación acumulada frente a la carga salina", "%"),
        width="stretch",
    )
    st.markdown(contenido.lista_markdown([tr.lectura_cruce(resultado)] + tr.lectura_barrido(resultado)))


def seccion_sensibilidad(api_disponible: bool) -> None:
    """Sensibilidad a un parámetro supuesto: indicador frente al valor y estado de las conjeturas."""
    st.markdown("**Sensibilidad a un parámetro supuesto**")
    columnas = st.columns(3)
    parametro = columnas[0].selectbox(
        "Parámetro", list(tr.VALORES_SENSIBILIDAD), format_func=tr.NOMBRES_PARAMETRO.get, key="sens_parametro"
    )
    escenario = columnas[1].selectbox(ETIQUETA_ESCENARIO, list(ESCENARIOS), format_func=ESCENARIOS.get, key="sens_escenario")
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
        .mark_line(point=True, color=COLOR_NEURO)
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


def grafico_incertidumbre(df: pd.DataFrame):
    """Dispersión de las muestras: eficacia del pulso frente a flujo de niebla, coloreada por la validación de C1."""
    return (
        alt.Chart(df)
        .mark_circle(size=90, opacity=0.85)
        .encode(
            x=alt.X("eficacia:Q", title="Eficacia máxima del pulso", scale=alt.Scale(zero=False)),
            y=alt.Y("flujo:Q", title="Flujo máximo de niebla (L/m²/h)", scale=alt.Scale(zero=False)),
            color=alt.Color(
                f"{tr.COLUMNA_ESTADO_C1}:N",
                title="Conjetura 1",
                scale=alt.Scale(domain=list(tr.ESTADOS_VALIDACION.values())[::-1], range=[COLOR_NEURO, COLOR_TEMPORIZADOR]),
                legend=alt.Legend(orient="bottom"),
            ),
            tooltip=[
                alt.Tooltip("eficacia:Q", title="Eficacia", format=".3f"),
                alt.Tooltip("flujo:Q", title="Flujo", format=".3f"),
                alt.Tooltip(f"{tr.COLUMNA_RECUPERACION}:Q", title="Recuperación (%)", format=".2f"),
                alt.Tooltip("rendimiento_dia:Q", title="Rendimiento (L/m²/día)", format=".2f"),
            ],
        )
        .properties(title="Muestras de los parámetros supuestos", height=320)
    )


def seccion_incertidumbre(api_disponible: bool) -> None:
    """Propagación de la incertidumbre de la eficacia del pulso y del flujo de niebla."""
    st.markdown("**Incertidumbre de los parámetros supuestos**")
    st.caption(
        "Cada muestra toma una eficacia del pulso entre 0.80 y 1.00 y un flujo de niebla entre 0.49 y "
        "1.83 L/m²/h (calibrado contra el rendimiento de 3 a 10 L/m² al día de la literatura), con "
        "distribución uniforme, y simula 24 h con tasa de salinización ALTA."
    )
    columnas = st.columns(4)
    escenario = columnas[0].selectbox(ETIQUETA_ESCENARIO, list(ESCENARIOS), format_func=ESCENARIOS.get, key="inc_escenario")
    humedad = columnas[1].slider(ETIQUETA_HUMEDAD, 0.0, 100.0, step=0.5, key="inc_humedad")
    muestras = columnas[2].slider("Número de muestras", 5, 30, key="inc_muestras")
    columnas[3].write("")
    if columnas[3].button("Ejecutar incertidumbre", disabled=not api_disponible, width="stretch"):
        carga = tr.configuracion_incertidumbre(escenario, humedad, muestras)
        ejecutar_analisis(incertidumbre_en_cache, carga, "incertidumbre", "Propagando la incertidumbre...")
    st.caption(contenido.AVISO_EXPLORATORIO)
    if st.session_state.error_incertidumbre is not None:
        mostrar_error(st.session_state.error_incertidumbre)
    resultado = st.session_state.resultado_incertidumbre
    if resultado is None:
        st.info("Ejecute el análisis para estimar la probabilidad de validar cada conjetura.")
        return

    graficos = st.columns([3, 2])
    graficos[0].altair_chart(grafico_incertidumbre(tr.incertidumbre_a_dataframe(resultado)), width="stretch")
    graficos[1].dataframe(
        tr.probabilidades_incertidumbre(resultado),
        hide_index=True,
        width="stretch",
        column_config={"Probabilidad": st.column_config.NumberColumn(format="%.2f")},
    )
    st.markdown(contenido.lista_markdown(tr.lectura_incertidumbre(resultado)))


def vista_respuesta(api_disponible: bool) -> None:
    """Respuesta a la pregunta por partes: desgaste, recuperación, seguridad y personas abastecidas."""
    st.header(VISTA_RESPUESTA)
    st.info(contenido.PREGUNTA_INVESTIGACION)
    st.markdown(f"**Hipótesis de trabajo.** {contenido.HIPOTESIS}")
    tablero_veredictos()
    st.warning(contenido.AVISO_EXPLORATORIO)
    encabezado_parte("desgaste")
    seccion_robustez(api_disponible)
    seccion_robustez_desgaste(api_disponible)
    encabezado_parte("recuperacion")
    seccion_barrido(api_disponible)
    encabezado_parte("seguridad")
    seccion_incertidumbre(api_disponible)
    seccion_sensibilidad(api_disponible)
    encabezado_parte("personas")
    seccion_dimensionamiento(api_disponible)
    seccion_impacto_entornos(api_disponible)
    boton_siguiente_vista(VISTA_RESPUESTA)


# ---------------------------------------------------------------------------
# Vista D: explorador de hipótesis
# ---------------------------------------------------------------------------
def cargar_perfil(perfiles: dict[str, dict]) -> None:
    """Callback que copia el perfil elegido en los cinco campos editables del explorador."""
    perfil = perfiles.get(st.session_state.exp_perfil)
    if perfil is None:
        return
    for campo, clave in CAMPOS_EXPLORADOR.items():
        st.session_state[clave] = perfil[campo]


def perfil_editado() -> dict:
    """Perfil de sitio con los valores actuales de los cinco campos editables del explorador."""
    return {campo: st.session_state[clave] for campo, clave in CAMPOS_EXPLORADOR.items()}


def calibrar_perfil() -> None:
    """Callback que calibra el flujo con el rendimiento medido y lo copia en el campo de flujo del perfil.

    Se ejecuta antes de dibujar los campos, por eso puede cambiar el valor del campo de flujo.
    """
    carga = tr.configuracion_calibracion(
        st.session_state.exp_rendimiento, st.session_state.exp_escenario, st.session_state.exp_humedad, perfil_editado()
    )
    try:
        resultado = calibracion_en_cache(carga)
    except cliente_api.ErrorApiAxioma as error:
        st.session_state.error_calibracion = error
        return
    st.session_state.resultado_calibracion = resultado
    st.session_state.error_calibracion = None
    st.session_state[CAMPOS_EXPLORADOR["flujo_niebla_maximo_l_m2_h"]] = resultado["flujo_calibrado_l_m2_h"]


def controles_calibracion(bloqueado: bool) -> None:
    """Rendimiento medido y botón que calibra el flujo del perfil con POST /api/v1/analisis/calibracion."""
    columnas = st.columns([2, 1, 4])
    columnas[0].number_input(
        "Rendimiento medido (L/m²/día)", config.RENDIMIENTO_MEDIDO_MIN_L_M2_DIA, config.RENDIMIENTO_MEDIDO_MAX_L_M2_DIA,
        step=0.5, key="exp_rendimiento",
        help=(
            "Rendimiento de un colector en el sitio. La calibración busca el flujo de niebla con que el control "
            "basado en reglas lo alcanza en 24 h, con el escenario, la humedad inicial y el clima del perfil."
        ),
    )
    columnas[1].write("")
    columnas[1].button("Calibrar flujo", on_click=calibrar_perfil, disabled=bloqueado, width="stretch")
    with columnas[2]:
        if st.session_state.error_calibracion is not None:
            mostrar_error(st.session_state.error_calibracion)
        elif st.session_state.resultado_calibracion is not None:
            st.caption(tr.texto_calibracion(st.session_state.resultado_calibracion))


def controles_perfil(perfiles: dict[str, dict], bloqueado: bool) -> dict:
    """Selector de perfil, sus cinco campos acotados a los límites de PerfilSitio y la calibración del flujo.

    Devuelve el perfil editado.
    """
    if perfiles:
        if st.session_state.exp_perfil not in perfiles:
            st.session_state.exp_perfil = next(iter(perfiles))
        st.selectbox(
            "Perfil de sitio", list(perfiles), format_func=lambda clave: tr.etiqueta_sitio(perfiles[clave]),
            key="exp_perfil", on_change=cargar_perfil, args=(perfiles,), disabled=bloqueado,
        )
    columnas = st.columns(5)
    columnas[0].text_input(
        "Nombre del sitio", key=CAMPOS_EXPLORADOR["nombre"], max_chars=tr.LONGITUD_MAXIMA_NOMBRE_SITIO,
        help="Mayúsculas, dígitos y guion bajo; los demás caracteres se reemplazan por guion bajo.",
    )
    columnas[1].number_input(
        "Flujo de niebla (L/m²/h)", config.FLUJO_NIEBLA_MIN_L_M2_H, config.FLUJO_NIEBLA_MAX_L_M2_H,
        step=0.01, key=CAMPOS_EXPLORADOR["flujo_niebla_maximo_l_m2_h"],
    )
    columnas[2].number_input(
        "Temperatura media (°C)", config.TEMPERATURA_MEDIA_MIN_C, config.TEMPERATURA_MEDIA_MAX_C,
        step=0.5, key=CAMPOS_EXPLORADOR["temperatura_media_c"],
    )
    columnas[3].number_input(
        "Amplitud térmica (°C)", 0.0, config.AMPLITUD_TEMPERATURA_MAX_C, step=0.5,
        key=CAMPOS_EXPLORADOR["amplitud_temperatura_c"],
    )
    columnas[4].number_input(
        "Amplitud de humedad (puntos)", 0.0, config.AMPLITUD_HUMEDAD_MAX_PCT, step=0.5,
        key=CAMPOS_EXPLORADOR["amplitud_humedad_pct"],
    )
    controles_calibracion(bloqueado)
    return perfil_editado()


def mostrar_resultado_explorador(resultado: dict) -> None:
    """Conjeturas, qué cambiaría cada una y parámetros usados de la simulación del explorador."""
    st.subheader("Conjeturas")
    columnas = st.columns(3)
    condiciones = tr.condiciones_de_cambio(resultado)
    for indice, (columna, conjetura) in enumerate(zip(columnas, tr.conjeturas_a_lista(resultado))):
        with columna.container(border=True):
            st.markdown(f"**{conjetura['nombre']}**")
            if conjetura["validada"]:
                st.success("VALIDADA")
            else:
                st.error("NO VALIDADA")
            if indice < len(condiciones):
                st.markdown(condiciones[indice])
    st.subheader("Parámetros usados")
    st.dataframe(tr.parametros_usados_a_dataframe(resultado), hide_index=True, width="stretch")


def vista_explorador(api_disponible: bool) -> None:
    """Simulación con eficacia y perfil de sitio propios, condiciones de cambio y preguntas para el Ciclo 3."""
    st.header(VISTA_EXPLORADOR)
    st.markdown(contenido.INTRO_EXPLORADOR)
    bloqueado = not api_disponible
    perfiles = {perfil["nombre"]: perfil for perfil in obtener_perfiles(api_disponible)}
    columnas = st.columns(4)
    escenario = columnas[0].selectbox(ETIQUETA_ESCENARIO, list(ESCENARIOS), format_func=ESCENARIOS.get, key="exp_escenario")
    tasa = columnas[1].selectbox("Tasa de salinización", TASAS, key="exp_tasa")
    humedad = columnas[2].slider(ETIQUETA_HUMEDAD, 0.0, 100.0, step=0.5, key="exp_humedad")
    eficacia = columnas[3].slider(
        "Eficacia del pulso", config.EFICACIA_EXPLORADOR_MIN, config.EFICACIA_EXPLORADOR_MAX, step=0.01,
        key="exp_eficacia",
    )
    sitio = controles_perfil(perfiles, bloqueado)
    if st.button("Ejecutar simulación", disabled=bloqueado, type="primary"):
        carga = tr.configuracion_explorador(escenario, tasa, humedad, eficacia, sitio)
        ejecutar_analisis(simulacion_en_cache, carga, "explorador", "Ejecutando la simulación con su hipótesis...")
    if st.session_state.error_explorador is not None:
        mostrar_error(st.session_state.error_explorador)
    resultado = st.session_state.resultado_explorador
    if resultado is None:
        st.info("Ajuste los parámetros y presione Ejecutar simulación.")
    else:
        mostrar_resultado_explorador(resultado)
    st.subheader("Preguntas para el Ciclo 3")
    preguntas = tr.hipotesis_siguientes(
        st.session_state.resultado_robustez, st.session_state.resultado_incertidumbre, resultado
    )
    st.markdown(contenido.lista_markdown(preguntas))


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def main() -> None:
    """Construye la página según la vista seleccionada."""
    inicializar_estado()
    st.title("Axioma-H Engine")
    st.caption(
        "Simulador del control basado en reglas (primera etapa de una arquitectura neuro-simbólica) para "
        "captación pasiva de agua atmosférica."
    )

    api_disponible = panel_conexion()
    st.sidebar.divider()
    vista = st.sidebar.radio("Recorrido", contenido.VISTAS, format_func=contenido.etiqueta_vista, key="vista")
    st.sidebar.radio("Nivel de lectura", NIVELES_LECTURA, key="nivel_lectura")

    if vista == VISTA_INVESTIGACION:
        vista_investigacion()
    elif vista == VISTA_EVALUACION:
        vista_evaluacion(api_disponible)
    elif vista == VISTA_RESPUESTA:
        vista_respuesta(api_disponible)
    elif vista == VISTA_EXPLORADOR:
        vista_explorador(api_disponible)
    else:
        vista_simulacion(api_disponible)
        # La simulación puede terminar antes de mostrar resultados, por eso el botón se dibuja aquí.
        boton_siguiente_vista(VISTA_SIMULACION)


main()
