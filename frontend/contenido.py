"""Contenido de la vista de investigación y del recorrido guiado del dashboard.

Los textos resumen README.md y docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md
(secciones 2, 2.7 y 2.8). Los umbrales de las reglas se toman de frontend/config.py para
que los textos no se desalineen de los valores mostrados en el resto del dashboard.
"""

from frontend import config

# Parámetros del pulso y tope ecológico; deben coincidir con backend/config.py.
TEMPERATURA_OBJETIVO_PULSO_C = 44.0
DURACION_PULSO_SEG = 90
FRACCION_MAXIMA_EXTRACCION_PCT = 33.0

URL_REPOSITORIO = "https://github.com/crd10lop/axioma-h-engine"

# ---------------------------------------------------------------------------
# Pregunta, hipótesis y respuesta preliminar (docs/01, secciones 2.1, 2.5 y 2.6)
# ---------------------------------------------------------------------------
PREGUNTA_INVESTIGACION = (
    "¿En qué medida un sistema de control neuro-simbólico, evaluado mediante simulación, mejora la "
    "recuperación del caudal de agua y reduce el desgaste de las membranas de un captador de agua "
    "atmosférica, en comparación con un control convencional por temporizador, a medida que aumenta "
    "la salinidad del ambiente?"
)

VERSION_DIVULGATIVA = (
    "¿Puede un control inteligente basado en reglas hacer que un captador de agua atmosférica rinda "
    "mejor y dure más en ambientes salinos que un control por temporizador?"
)

HIPOTESIS = (
    "El control neuro-simbólico mantiene una recuperación de caudal estable y una degradación "
    "acumulada menor que el temporizador, y su ventaja crece con el nivel de salinidad."
)

RESPUESTA_PRELIMINAR: list[str] = [
    "Desgaste. El control basado en reglas (modo neuro-simbólico en la API y el dashboard) reduce la "
    "degradación acumulada entre 74 % y 99 % frente al temporizador en los seis niveles de salinidad. La reducción es mayor con salinidad baja, "
    "donde el temporizador aplica pulsos que no hacen falta.",
    "Recuperación. El control basado en reglas mantiene la recuperación entre 85.9 % y 88.9 % en todos "
    "los niveles. La del temporizador cae de 95.8 % a 63.2 % a medida que aumenta la salinidad. Con "
    "salinidad baja el temporizador recupera más, porque limpia una membrana casi limpia. Desde una "
    "carga de 60 Ohm por L/m² el control basado en reglas lo supera, y la diferencia llega a 22.7 puntos con "
    "la carga más alta.",
    "La respuesta es condicional: la ventaja en recuperación aparece y crece con la salinidad, "
    "mientras que la reducción del desgaste se observa en todos los niveles. Estos resultados "
    "dependen de parámetros físicos supuestos, en particular la eficacia del pulso, que deben "
    "medirse en laboratorio.",
]


# ---------------------------------------------------------------------------
# Conjeturas (docs/01, sección 3; lectura según README, "Interpretación de los resultados")
# ---------------------------------------------------------------------------
def _conjetura(nombre: str, enunciado: str, criterio: str, lectura: str) -> dict[str, str]:
    """Agrupa los textos de una conjetura con las claves que usa la tabla del dashboard."""
    return {"nombre": nombre, "enunciado": enunciado, "criterio": criterio, "lectura": lectura}


_NO_EQUIVALE_A_REFUTADA = (
    "Que no se valide en el modelo no equivale a que quede refutada: el resultado depende de la "
    "eficacia del pulso (0.90), un parámetro supuesto que aún no se ha medido."
)

CONJETURAS: list[dict[str, str]] = [
    _conjetura(
        "Conjetura 1: Control neuro-simbólico vs. control fijo",
        "El control neuro-simbólico local extiende la vida útil de la membrana biomimética más que "
        "un temporizador estático al prevenir la saturación salina.",
        "Recuperación de caudal >= 90 % tras cada pulso y ahorro de energía en pulsos >= 35 % "
        "frente al temporizador.",
        "No validada. El ahorro de energía cumple en casi todos los casos, pero la recuperación de "
        "caudal tras el pulso queda bajo el 90 %. Validarla requiere que un pulso de 90 s a 44 °C "
        "remueva al menos el 78 % de la costra salina. " + _NO_EQUIVALE_A_REFUTADA,
    ),
    _conjetura(
        "Conjetura 2: Autorreparación por pulso resonante",
        "El pulso térmico controlado (<= 45 °C) disuelve las costras de NaCl sin degradar la matriz "
        "de acuaporinas sintéticas.",
        "Tiempo de regeneración < 120 s (impedancia de vuelta a 1100 Ω o menos) y 0 % de "
        "degradación térmica.",
        "No validada. La ausencia de degradación térmica se sostiene en el modelo: 0 % en los diez "
        "escenarios. La eficacia de disolución no es verificable por simulación; validarla requiere "
        "remover al menos el 81 % de la costra en un pulso. " + _NO_EQUIVALE_A_REFUTADA,
    ),
    _conjetura(
        "Conjetura 3: Preservación ecológica y saber territorial",
        "Limitar la captación al 33 % de la niebla circulante orientando el cubo 20° al norte "
        "preserva la humedad del suelo y la flora local.",
        "Cero violaciones ecológicas y rendimiento hídrico >= 12 L/m² por noche.",
        "Validada en cuatro escenarios con 85 % de humedad inicial. El control basado en reglas no "
        "registró violaciones ecológicas en ningún escenario. Con 45 % no se valida porque el "
        "recurso atmosférico no alcanza: el rendimiento nocturno queda entre 4 y 6 L/m² por noche, "
        "y el temporizador tampoco llega a 12.",
    ),
]

# Encabezados de la tabla de conjeturas, en el orden de las claves.
COLUMNAS_CONJETURAS = {
    "nombre": "Conjetura",
    "enunciado": "Enunciado",
    "criterio": "Criterio de verificación",
    "lectura": "Lectura del resultado",
}


# ---------------------------------------------------------------------------
# Reglas de control (orden de evaluación del motor)
# ---------------------------------------------------------------------------
def _regla(prioridad: int, regla: str, condicion: str, accion: str) -> dict[str, int | str]:
    """Agrupa los textos de una regla con las claves que usa la tabla del dashboard."""
    return {"prioridad": prioridad, "regla": regla, "condicion": condicion, "accion": accion}


_IMPEDANCIA_ALTA = f"> {config.UMBRAL_IMPEDANCIA_OHMS:g} Ω"
_TOPE = f"tope ecológico ({FRACCION_MAXIMA_EXTRACCION_PCT:g} % de la niebla disponible)"

REGLAS: list[dict[str, int | str]] = [
    _regla(
        1,
        "REGLA_01_LIMITE_TERMICO_ABSOLUTO",
        f"Temperatura de la matriz >= {config.UMBRAL_TEMPERATURA_CORTE_C:g} °C",
        "Corte de emergencia; caudal 0 %",
    ),
    _regla(
        2,
        "REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL",
        f"Humedad relativa < {config.UMBRAL_HUMEDAD_ECOLOGICA_PCT:g} %",
        "Pausa ecológica; caudal 0 %",
    ),
    _regla(
        3,
        "REGLA_06_SUPERVISION_HUMANA",
        (
            "Anulación del operador: suspender la extracción, o inhibir el pulso con impedancia "
            f"{_IMPEDANCIA_ALTA}"
        ),
        f"Suspender: caudal 0 %, sin pulso. Inhibir el pulso: caudal al 50 % del {_TOPE}, sin pulso",
    ),
    _regla(
        4,
        "REGLA_04_PROTECCION_RESERVA_CRITICA",
        f"Reserva < {config.UMBRAL_RESERVA_CRITICA_PCT:g} % e impedancia {_IMPEDANCIA_ALTA}",
        f"Reducir el caudal al 50 % del {_TOPE}, sin pulso",
    ),
    _regla(
        5,
        "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA",
        f"Impedancia {_IMPEDANCIA_ALTA} y reserva >= {config.UMBRAL_RESERVA_CRITICA_PCT:g} %",
        f"Pulso resistivo de {DURACION_PULSO_SEG} s hacia {TEMPERATURA_OBJETIVO_PULSO_C:g} °C; "
        f"caudal al 80 % del {_TOPE}",
    ),
    _regla(
        6,
        "REGLA_05_OPERACION_NOMINAL",
        "Ninguna de las anteriores",
        f"Filtración pasiva continua; caudal al 100 % del {_TOPE}",
    ),
]

COLUMNAS_REGLAS = {
    "prioridad": "Prioridad",
    "regla": "Regla",
    "condicion": "Condición",
    "accion": "Acción",
}

NOTA_REGLAS = (
    "Las reglas se evalúan en este orden y la primera que se cumple decide. El sistema nunca extrae "
    f"más del {FRACCION_MAXIMA_EXTRACCION_PCT:g} % de la niebla disponible. La REGLA_04 se evalúa "
    "antes que la REGLA_03 porque ambas comparten la condición de impedancia y la REGLA_04 protege "
    "la reserva térmica. La REGLA_06 aplica la supervisión humana en la evaluación de un nodo: el "
    "operador solo puede ser más conservador que el motor, nunca forzar extracción ni pulsos, y los "
    "límites térmico y ecológico prevalecen sobre su decisión."
)


# ---------------------------------------------------------------------------
# Supuestos clave (docs/06_Referencias_y_Trazabilidad_AxiomaH.md) y limitaciones (README)
# ---------------------------------------------------------------------------
def _supuesto(parametro: str, valor: str, origen: str) -> dict[str, str]:
    """Agrupa los textos de un supuesto con las claves que usa la tabla del dashboard."""
    return {"parametro": parametro, "valor": valor, "origen": origen}


SUPUESTOS_CLAVE: list[dict[str, str]] = [
    _supuesto(
        "Eficacia máxima del pulso",
        "0.90",
        "Supuesto del modelo, sin fuente: estimación de orden de magnitud pendiente de medición en "
        "laboratorio. Validar la Conjetura 1 requiere al menos 0.94 y la Conjetura 2 al menos 0.97. "
        "El análisis de incertidumbre la varía entre 0.80 y 1.00.",
    ),
    _supuesto(
        "Flujo máximo de niebla",
        "6.0 L/m²/h con humedad relativa del 100 %; rango calibrado de 0.49 a 1.83 L/m²/h",
        "Supuesto del modelo, sin fuente. Contrastado con Klemm et al. (2012), que reportan de 3 a "
        "10 L/m² al día en proyectos operativos de captación de niebla: es un supuesto optimista. La "
        "calibración inversa contra ese rango (Día normal, humedad inicial de 85 %, semilla 42) da un "
        "flujo de 0.49 a 1.83 L/m²/h, que el análisis de incertidumbre usa en lugar de 6.0.",
    ),
]

COLUMNAS_SUPUESTOS = {"parametro": "Parámetro", "valor": "Valor", "origen": "Origen"}

LIMITACIONES: list[str] = [
    "Los resultados provienen de un modelo simulado, no de mediciones en campo.",
    "La eficacia del pulso resistivo (0.90) y los demás parámetros físicos (flujo de niebla, tasas "
    "de incrustación, capacidad térmica, consumo y recarga de energía, degradación de la membrana) "
    "son supuestos de orden de magnitud pendientes de validación experimental.",
    "El estado de las Conjeturas 1 y 2 cambia con la eficacia del pulso, como muestran los análisis "
    "de sensibilidad. Medir esa eficacia es la prioridad experimental antes de dar por validada o "
    "refutada cualquiera de las dos.",
    "El clima de referencia usa ciclos diurnos idealizados con ruido gaussiano, y los escenarios "
    "repiten sus ventanas de sequía o tormenta cada día simulado.",
    "La configuración CORS admite por defecto solo orígenes locales. Para que una página web consuma "
    "la API desde el navegador, sus dominios deben agregarse con AXIOMA_CORS_ORIGINS.",
    "En el plan gratuito de Render, los servicios se suspenden tras 15 minutos sin tráfico y tardan "
    "cerca de un minuto en reactivarse.",
]

# ---------------------------------------------------------------------------
# Perspectivas y madurez (docs/01, secciones 2.7 y 2.8)
# ---------------------------------------------------------------------------
PERSPECTIVAS: dict[str, str] = {
    "social": (
        "El proyecto se orienta a Cabo de la Vela, en la Alta Guajira, un territorio árido con "
        "escasez hídrica. El control es descentralizado: cada uno de los 8 nodos decide con su "
        "propia telemetría. Respetar el tope ecológico tiene un costo: con humedad inicial de 85 %, "
        "el control basado en reglas capta entre 23 % y 27 % menos agua que el temporizador. Cada "
        "simulación estima además el impacto comunitario: con humedad inicial de 85 %, la red de 8 m² "
        "abastecería entre 7.5 y 12.7 personas al nivel de acceso básico de la OMS (20 L por persona "
        "al día), según el escenario. Es un indicador informativo que no interviene en la validación."
    ),
    "etica": (
        f"El sistema nunca extrae más del {FRACCION_MAXIMA_EXTRACCION_PCT:g} % de la niebla disponible "
        f"y suspende la extracción con humedad relativa menor que {config.UMBRAL_HUMEDAD_ECOLOGICA_PCT:g} %. "
        "No se ajustan parámetros para forzar resultados, y cada simulación expone sus indicadores y "
        "su bitácora; el código es abierto, con licencia MIT. Antes de cualquier piloto en territorio "
        "Wayuu se requiere consulta previa (Convenio 169 de la OIT, Ley 21 de 1991). Esta consulta no "
        "se ha realizado."
    ),
    "cultural": (
        "La Conjetura 3 se denomina \"saber territorial\" y busca preservar la humedad disponible "
        "para la vegetación de trupillo y cardón. El tope del "
        f"{FRACCION_MAXIMA_EXTRACCION_PCT:g} % proviene de la formulación de la Conjetura 3 en la "
        "Matriz del equipo (narrativa del Ciclo 1, \"El Axioma del Silencio\"): no es un saber wayuu "
        "documentado ni un criterio de la literatura ecológica, y debe validarse con las comunidades. "
        "Para el Ciclo 3 se propone un protocolo de co-creación en cuatro pasos: consulta previa; "
        "validación comunitaria del tope y de la pausa ecológica; traducción de la interfaz con "
        "traductores wayuu; y reglas de gobernanza del dispositivo y de los datos. No resuelto: la "
        "interfaz está solo en español y no tiene versión en wayuunaiki, y la orientación del colector "
        "a 20° al norte no se modela."
    ),
    "humana": (
        "Cada decisión del motor incluye un motivo legible, y la vista de evaluación manual permite "
        "explorar las reglas. En la evaluación de un nodo, un operador puede suspender la extracción o "
        "inhibir el pulso (REGLA_06): solo en sentido conservador y sin pasar por encima de los límites "
        "térmico y ecológico. Resuelto parcialmente: la simulación no admite supervisión humana y sus "
        "decisiones se aplican sin operador; incorporarla se propone para el Ciclo 3."
    ),
}

TITULOS_PERSPECTIVAS = {
    "social": "Social",
    "etica": "Ética",
    "cultural": "Cultural",
    "humana": "Humana",
}

MADUREZ = (
    "El artefacto del Ciclo 2 es una prueba de concepto analítica por simulación, equivalente de forma "
    "aproximada a un nivel de madurez tecnológica TRL 2-3. No existe un prototipo físico del captador "
    "ni de la membrana, y no hay datos de campo. Lo que sí está implementado y verificado es el "
    "software de control: la API, el simulador, el dashboard, las pruebas automatizadas y el "
    "despliegue público. El siguiente ciclo debe medir en laboratorio qué fracción de la costra "
    f"salina remueve un pulso de {DURACION_PULSO_SEG} s a {TEMPERATURA_OBJETIVO_PULSO_C:g} °C."
)

# ---------------------------------------------------------------------------
# Glosario y referencias
# ---------------------------------------------------------------------------
GLOSARIO: dict[str, str] = {
    "acceso básico al agua": (
        f"Nivel de servicio de la OMS de unos {config.CONSUMO_ACCESO_BASICO_L_PERSONA_DIA:g} L por "
        "persona al día, suficiente para bebida e higiene básica. El mínimo humanitario de Sphere es "
        f"{config.CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA:g} L. El impacto comunitario estimado divide el "
        "agua captada por día entre estos consumos."
    ),
    "rendimiento por m²": (
        "Litros captados por día y por m² de colector. Proyectos reales de captación de niebla "
        f"reportan de {config.RENDIMIENTO_LITERATURA_MIN_L_M2_DIA:g} a "
        f"{config.RENDIMIENTO_LITERATURA_MAX_L_M2_DIA:g} L/m² al día (Klemm et al., 2012); el modelo "
        "supera ese rango con humedad alta porque su flujo de niebla es un supuesto optimista."
    ),
    "impedancia": (
        "Resistencia eléctrica de la membrana, en Ω. La membrana limpia tiene 1000 Ω; la sal "
        f"cristalizada la eleva, y sobre {config.UMBRAL_IMPEDANCIA_OHMS:g} Ω el motor detecta "
        "cristalización."
    ),
    "conductancia relativa": (
        "Cociente entre la impedancia de la membrana limpia y la impedancia tras el pulso, en %. "
        "Es la medida de recuperación de caudal."
    ),
    "pulso resistivo": (
        f"Calentamiento de la matriz durante {DURACION_PULSO_SEG} s hacia "
        f"{TEMPERATURA_OBJETIVO_PULSO_C:g} °C para desprender la sal cristalizada."
    ),
    "tope ecológico": (
        f"Fracción máxima de la niebla disponible que el sistema puede extraer: "
        f"{FRACCION_MAXIMA_EXTRACCION_PCT:g} %. El caudal de cada regla se expresa como porcentaje "
        "de este tope."
    ),
    "humedad relativa": (
        f"Humedad del aire, en %. Con menos de {config.UMBRAL_HUMEDAD_ECOLOGICA_PCT:g} % el motor "
        "suspende la extracción para no competir con la vegetación local."
    ),
    "integridad de la membrana": (
        "Porcentaje de la membrana que conserva su función. Disminuye por la fatiga de cada pulso, "
        f"por la exposición a {config.UMBRAL_TEMPERATURA_CORTE_C:g} °C o más y por el tiempo con "
        "impedancia alta. Su complemento es la degradación acumulada."
    ),
    "control basado en reglas": (
        "Control que evalúa la telemetría de cada nodo con reglas explícitas en orden de prioridad. Es la "
        "implementación del Ciclo 2 y la primera etapa de una arquitectura neuro-simbólica; el componente "
        "neuronal queda como trabajo futuro."
    ),
    "control neuro-simbólico": (
        "Arquitectura objetivo del proyecto, que combina reglas explícitas con un componente neuronal. Por "
        "compatibilidad, la API y el dashboard usan este nombre (modo NEURO_SIMBOLICO) para el control "
        "basado en reglas, que es su primera etapa."
    ),
    "temporizador fijo": (
        "Control tradicional de comparación: aplica un pulso cada 120 min sin leer sensores, con una "
        "fracción de extracción fija de 0.45 y sin corte térmico ni pausa ecológica."
    ),
    "supervisión humana": (
        "Intervención de un operador sobre la decisión de un nodo (REGLA_06). Puede suspender la "
        "extracción o impedir el pulso de limpieza, pero nunca forzar extracción ni pulsos. Se evalúa "
        f"después del corte térmico ({config.UMBRAL_TEMPERATURA_CORTE_C:g} °C) y de la pausa ecológica "
        f"(humedad < {config.UMBRAL_HUMEDAD_ECOLOGICA_PCT:g} %), que siempre prevalecen."
    ),
    "semilla": (
        "Número que inicializa el generador aleatorio del entorno. La misma semilla reproduce la "
        "misma corrida; los resultados documentados usan la semilla 42."
    ),
}

REFERENCIAS: list[str] = [
    f"Repositorio del proyecto: {URL_REPOSITORIO}",
    "Software de terceros, fuente científica y trazabilidad de parámetros: "
    f"{URL_REPOSITORIO}/blob/main/docs/06_Referencias_y_Trazabilidad_AxiomaH.md",
    (
        "Howard, G., Bartram, J., Williams, A., Overbo, A., Fuente, D. y Geere, J.-A. (2020). Domestic "
        "water quantity, service level and health (2.ª ed.). Organización Mundial de la Salud. "
        "https://www.who.int/publications/i/item/9789240015241"
    ),
    (
        "Sphere Association (2018). The Sphere Handbook: Humanitarian Charter and Minimum Standards in "
        "Humanitarian Response (4.ª ed.), estándar 2.1 de abastecimiento de agua. https://spherestandards.org"
    ),
]

# ---------------------------------------------------------------------------
# Recorrido guiado
# ---------------------------------------------------------------------------
VISTAS: list[str] = [
    "Investigación y guía",
    "Evaluación manual de nodo",
    "Simulación comparativa",
    "Respuesta a la pregunta",
]

AVISO_EXPLORATORIO = (
    "Análisis exploratorio. Cada corrida usa su propia copia de los parámetros: la configuración del "
    "modelo no cambia y ningún valor se ajusta para validar una conjetura (decisión D5). Los parámetros "
    "supuestos, como la eficacia del pulso y el flujo de niebla, siguen pendientes de medición."
)


def _posicion_vista(vista: str) -> int:
    """Devuelve la posición de la vista en el recorrido, desde 0.

    Lanza ValueError si la vista no forma parte del recorrido.
    """
    if vista not in VISTAS:
        raise ValueError(f"Vista desconocida: {vista}")
    return VISTAS.index(vista)


def etiqueta_vista(vista: str) -> str:
    """Devuelve la vista con su número en el recorrido, por ejemplo "1. Investigación y guía"."""
    return f"{_posicion_vista(vista) + 1}. {vista}"


def siguiente_vista(vista: str) -> str | None:
    """Devuelve la vista que sigue en el recorrido, o None si es la última."""
    posicion = _posicion_vista(vista) + 1
    return VISTAS[posicion] if posicion < len(VISTAS) else None


def glosario_ordenado() -> list[tuple[str, str]]:
    """Devuelve los términos del glosario y sus definiciones en orden alfabético."""
    return sorted(GLOSARIO.items(), key=lambda item: item[0].casefold())


def lista_markdown(elementos: list[str]) -> str:
    """Convierte una lista de textos en una lista con viñetas de Markdown."""
    return "\n".join(f"- {elemento}" for elemento in elementos)
