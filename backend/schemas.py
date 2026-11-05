"""Esquemas de entrada y salida de la API del motor Axioma-H.

Los nombres de modelos y campos siguen el PRD de la API. Los enumerados
unifican los valores usados en el PRD y en la Matriz de Operacionalización
(decisión D4).
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Dict, List, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from backend import config

_EFICACIA_ADMITIDA = "Eficacia máxima del pulso, en (0, 1]."
_FLUJO_ADMITIDO = "Flujo máximo de niebla en L/m²/h, en (0, 20]."
_VALOR_POR_DEFECTO = " Nulo para usar el valor de backend/config.py."
_DESCRIPCION_ESCENARIO = "Escenario ambiental."
_DESCRIPCION_HUMEDAD_INICIAL = "Humedad relativa al inicio de la simulación (18:00 hora local)."
_DESCRIPCION_TASA = "Velocidad de incrustación salina."
_DESCRIPCION_NODOS = "Cantidad de nodos simulados."
_DESCRIPCION_SEMILLA = "Semilla del generador aleatorio del entorno."
_DESCRIPCION_FLUJO = "Flujo máximo de niebla en L/m²/h."


class ModoOperacion(str, Enum):
    """Estrategia de control aplicada al nodo."""

    NEURO_SIMBOLICO = "NEURO_SIMBOLICO"
    TEMPORIZADOR_FIJO = "TEMPORIZADOR_FIJO"


class Escenario(str, Enum):
    """Escenarios ambientales disponibles en el simulador."""

    DIA_NORMAL = "DIA_NORMAL"
    INCRUSTACION_SALINA_RAPIDA = "INCRUSTACION_SALINA_RAPIDA"
    SEQUIA = "SEQUIA"
    TORMENTA_DE_ARENA = "TORMENTA_DE_ARENA"
    TORMENTA_DE_SAL_Y_CALOR_EXTREMO = "TORMENTA_DE_SAL_Y_CALOR_EXTREMO"


class TasaSalinizacion(str, Enum):
    """Velocidad de incrustación salina sobre la membrana."""

    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class EstadoNodo(str, Enum):
    """Diagnóstico del nodo emitido por el motor de reglas."""

    EMERGENCIA_TERMICA = "EMERGENCIA_TERMICA"
    PAUSA_ECOLOGICA = "PAUSA_ECOLOGICA"
    RESERVA_CRITICA = "RESERVA_CRITICA"
    CRISTALIZACION_DETECTADA = "CRISTALIZACION_DETECTADA"
    NOMINAL = "NOMINAL"
    SUPERVISION_HUMANA = "SUPERVISION_HUMANA"


class AccionControl(str, Enum):
    """Acción recomendada por el motor de reglas."""

    CORTE_DE_EMERGENCIA = "CORTE_DE_EMERGENCIA"
    PAUSA_ECOLOGICA = "PAUSA_ECOLOGICA"
    REDUCIR_CAUDAL_SIN_PULSO = "REDUCIR_CAUDAL_SIN_PULSO"
    APLICAR_PULSO_RESISTIVO = "APLICAR_PULSO_RESISTIVO"
    FILTRACION_PASIVA_CONTINUA = "FILTRACION_PASIVA_CONTINUA"
    SUSPENSION_MANUAL = "SUSPENSION_MANUAL"


class AnulacionManual(str, Enum):
    """Intervención de un operador sobre la decisión del motor; solo puede ser más conservadora."""

    NINGUNA = "NINGUNA"
    SUSPENDER_EXTRACCION = "SUSPENDER_EXTRACCION"
    INHIBIR_PULSO = "INHIBIR_PULSO"


class TelemetryInput(BaseModel):
    """Lectura de sensores de un nodo de captación."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nodo_id": "NODO_04",
                    "impedancia_ohms": 1650.5,
                    "temperatura_celsius": 36.2,
                    "reserva_calor_pct": 55.0,
                    "humedad_relativa_pct": 42.0,
                    "flujo_actual_ml_min": 14.5,
                    "modo_operacion": "NEURO_SIMBOLICO",
                }
            ]
        }
    )

    nodo_id: str = Field(
        ..., pattern=r"^NODO_0[1-8]$", description="Identificador del nodo (NODO_01 a NODO_08)."
    )
    impedancia_ohms: float = Field(..., gt=0, description="Impedancia eléctrica de la membrana en ohmios.")
    temperatura_celsius: float = Field(
        ..., ge=-10, le=120, description="Temperatura de la matriz en grados Celsius."
    )
    reserva_calor_pct: float = Field(
        ..., ge=0, le=100, description="Estado de la reserva de energía térmica del nodo en porcentaje."
    )
    humedad_relativa_pct: float = Field(..., ge=0, le=100, description="Humedad relativa ambiente en porcentaje.")
    flujo_actual_ml_min: float = Field(..., ge=0, description="Caudal de agua captada en mililitros por minuto.")
    modo_operacion: ModoOperacion = Field(
        default=ModoOperacion.NEURO_SIMBOLICO, description="Estrategia de control a aplicar."
    )
    anulacion_manual: AnulacionManual = Field(
        default=AnulacionManual.NINGUNA,
        description=(
            "Intervención del operador (REGLA_06). Solo puede ser más conservadora que el motor: "
            "SUSPENDER_EXTRACCION detiene la extracción e INHIBIR_PULSO impide el pulso resistivo. "
            "Los límites térmico (REGLA_01) y ecológico (REGLA_02) prevalecen. No aplica en modo "
            "TEMPORIZADOR_FIJO."
        ),
    )


class MetricasConjeturas(BaseModel):
    """Indicadores de la decisión asociados a las conjeturas de investigación."""

    eficiencia_energetica_pct: float = Field(
        ..., ge=0, le=100, description="Relación entre la recuperación obtenida y la reserva consumida."
    )
    recuperacion_hidraulica_pct: float = Field(
        ..., ge=0, le=100, description="Conductancia relativa estimada después de la acción."
    )
    preservacion_ecologica_ok: bool = Field(
        ..., description="Indica si la acción respeta el límite de humedad y el tope de extracción del 33 %."
    )


class ControlDecision(BaseModel):
    """Decisión de control emitida para un nodo."""

    nodo_id: str = Field(..., description="Identificador del nodo evaluado.")
    timestamp: datetime = Field(..., description="Instante de la decisión en UTC.")
    estado_nodo: EstadoNodo = Field(..., description="Diagnóstico del nodo.")
    accion_recomendada: AccionControl = Field(..., description="Acción que debe ejecutar el nodo.")
    pulso_termico_activo: bool = Field(..., description="Indica si se ordena un pulso resistivo.")
    temperatura_objetivo_c: Optional[float] = Field(
        default=None, description="Temperatura objetivo del pulso en °C, o nulo si no hay pulso."
    )
    duracion_pulso_seg: int = Field(..., ge=0, description="Duración del pulso en segundos; 0 si no hay pulso.")
    ajuste_caudal_pct: float = Field(
        ..., ge=0, le=100, description="Caudal ordenado como porcentaje del tope ecológico del 33 %."
    )
    regla_activada: str = Field(..., description="Identificador de la regla que determinó la decisión.")
    motivo: str = Field(..., description="Explicación legible de la decisión para la consola del tablero.")
    metricas_conjeturas: MetricasConjeturas = Field(..., description="Indicadores asociados a las conjeturas.")


class PerfilSitio(BaseModel):
    """Perfil climático de un sitio de captación, para transferir el modelo a otro lugar.

    Los valores por defecto son los supuestos de Cabo de la Vela en
    `backend/config.py`. El ciclo diurno conserva sus horas de máximo (04:00
    para la humedad y 14:00 para la temperatura). El procedimiento está en
    docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md, sección 8.10.
    """

    nombre: str = Field(
        default="CABO_DE_LA_VELA",
        pattern=r"^[A-Z0-9_]{1,40}$",
        description="Identificador del sitio: mayúsculas, dígitos y guion bajo, hasta 40 caracteres.",
    )
    flujo_niebla_maximo_l_m2_h: float = Field(
        default=config.FLUJO_NIEBLA_MAXIMO_L_M2_H, gt=0, le=20, description=_FLUJO_ADMITIDO
    )
    temperatura_media_c: float = Field(
        default=config.TEMPERATURA_MEDIA_C, ge=0, le=45, description="Temperatura ambiente media en °C."
    )
    amplitud_temperatura_c: float = Field(
        default=config.AMPLITUD_TEMPERATURA_C, ge=0, le=15, description="Amplitud del ciclo térmico diurno en °C."
    )
    amplitud_humedad_pct: float = Field(
        default=config.AMPLITUD_HUMEDAD_PCT,
        ge=0,
        le=30,
        description="Amplitud del ciclo diurno de humedad en puntos de HR.",
    )


class SimulationConfig(BaseModel):
    """Parámetros de una simulación comparativa."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "duracion_horas": 24,
                    "escenario": "TORMENTA_DE_SAL_Y_CALOR_EXTREMO",
                    "humedad_ambiente_inicial_pct": 45.0,
                    "tasa_salinizacion": "ALTA",
                }
            ]
        }
    )

    duracion_horas: int = Field(default=24, ge=1, le=72, description="Horas simuladas.")
    escenario: Escenario = Field(..., description=_DESCRIPCION_ESCENARIO)
    humedad_ambiente_inicial_pct: float = Field(
        ..., ge=0, le=100, description=_DESCRIPCION_HUMEDAD_INICIAL
    )
    tasa_salinizacion: TasaSalinizacion = Field(..., description=_DESCRIPCION_TASA)
    numero_nodos: int = Field(default=8, ge=1, le=8, description=_DESCRIPCION_NODOS)
    paso_minutos: int = Field(default=5, ge=1, le=60, description="Resolución temporal en minutos.")
    semilla: int = Field(default=42, description=_DESCRIPCION_SEMILLA)
    sitio: PerfilSitio | None = Field(
        default=None, description="Perfil del sitio; nulo para usar el de Cabo de la Vela de backend/config.py."
    )
    eficacia_maxima_pulso: float | None = Field(
        default=None, gt=0, le=1, description=_EFICACIA_ADMITIDA + _VALOR_POR_DEFECTO
    )


class ResultadoModo(BaseModel):
    """Resultados agregados de un modo de control."""

    litros_totales_agua: float = Field(..., ge=0, description="Agua captada por todos los nodos en litros.")
    pulsos_termicos_ejecutados: int = Field(..., ge=0, description="Pulsos resistivos ejecutados en total.")
    consumo_energia_wh: float = Field(..., ge=0, description="Energía consumida (pulsos y electrónica) en Wh.")
    integridad_membrana_final_pct: float = Field(
        ..., ge=0, le=100, description="Integridad promedio de las membranas al final."
    )
    violaciones_ecologicas: int = Field(..., ge=0, description="Episodios de extracción fuera del límite ecológico.")
    recuperacion_caudal_promedio_pct: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Conductancia relativa promedio tras cada pulso; nulo si el modo no ejecutó pulsos.",
    )
    degradacion_acumulada_pct: float = Field(
        0.0, ge=0, le=100, description="Pérdida promedio de integridad de las membranas durante la corrida."
    )


class ComparativaModos(BaseModel):
    """Resultados de ambos modos sobre el mismo entorno."""

    modo_neuro_simbolico: ResultadoModo
    modo_temporizador_fijo: ResultadoModo
    modo_temporizador_tope_ecologico: ResultadoModo | None = Field(
        default=None,
        description=(
            "Temporizador fijo con la misma fracción de 0.33 del modo neuro-simbólico; referencia para "
            "separar el efecto del tope ecológico del de la lógica de control."
        ),
    )


class CausaNoValidacion(str, Enum):
    """Motivo por el que un indicador de una conjetura no cumple su umbral."""

    SIN_DATOS = "SIN_DATOS"
    DEPENDE_DE_PARAMETRO_SUPUESTO = "DEPENDE_DE_PARAMETRO_SUPUESTO"
    LIMITE_DEL_RECURSO_ATMOSFERICO = "LIMITE_DEL_RECURSO_ATMOSFERICO"
    DESEMPENO_DEL_CONTROL = "DESEMPENO_DEL_CONTROL"


class ConjeturasValidadas(BaseModel):
    """Estado de validación de cada conjetura."""

    conjetura_1_eficiencia: bool
    conjetura_2_autorreparacion: bool
    conjetura_3_saber_territorial: bool


class IndicadorVerificacion(BaseModel):
    """Valor obtenido de un indicador frente a su umbral."""

    valor: Optional[float] = Field(
        default=None, description="Valor calculado; nulo si la simulación no generó datos para medirlo."
    )
    umbral: float = Field(..., description="Umbral de la Matriz de Operacionalización.")
    operador: str = Field(..., description="Comparación aplicada entre valor y umbral.")
    cumple: bool = Field(..., description="Indica si el valor satisface el umbral.")


class VerificacionConjetura(BaseModel):
    """Detalle de la verificación de una conjetura."""

    validada: bool = Field(..., description="Verdadero solo si todos los indicadores cumplen.")
    indicadores: Dict[str, IndicadorVerificacion] = Field(..., description="Indicadores evaluados por nombre.")
    indicadores_informativos: Dict[str, int | float] = Field(
        default_factory=dict,
        description="Valores de contexto que se reportan junto a los indicadores y no intervienen en la validación.",
    )
    causas_no_validacion: List[CausaNoValidacion] = Field(
        default_factory=list,
        description=(
            "Causas de los indicadores que no cumplen, en el orden de los indicadores y sin repetir; "
            "vacía si la conjetura se valida. No intervienen en la validación."
        ),
    )


class DetalleVerificacion(BaseModel):
    """Detalle de verificación de las tres conjeturas."""

    conjetura_1_eficiencia: VerificacionConjetura
    conjetura_2_autorreparacion: VerificacionConjetura
    conjetura_3_saber_territorial: VerificacionConjetura


class PuntoSerieTemporal(BaseModel):
    """Estado agregado de la red en un paso de simulación."""

    minuto: int = Field(..., ge=0, description="Minuto transcurrido desde el inicio.")
    humedad_relativa_pct: float = Field(..., description="Humedad relativa ambiente promedio.")
    temperatura_c: float = Field(..., description="Temperatura ambiente en °C.")
    impedancia_promedio_neuro_ohms: float
    impedancia_promedio_temporizador_ohms: float
    litros_acumulados_neuro: float
    litros_acumulados_temporizador: float
    energia_acumulada_neuro_wh: float
    energia_acumulada_temporizador_wh: float
    integridad_promedio_neuro_pct: float
    integridad_promedio_temporizador_pct: float


class EventoBitacora(BaseModel):
    """Cambio de regla activa en un nodo del modo neuro-simbólico."""

    minuto: int = Field(..., ge=0, description="Minuto en que se activó la regla.")
    nodo_id: str = Field(..., description="Nodo afectado.")
    regla_activada: str = Field(..., description="Regla que pasó a gobernar el nodo.")
    motivo: str = Field(..., description="Explicación emitida por el motor de reglas.")


class ImpactoComunitario(BaseModel):
    """Estimación del abastecimiento que permitiría el agua captada por un modo de control.

    Es un indicador informativo: no interviene en la validación de las conjeturas.
    """

    litros_dia_red: float = Field(..., ge=0, description="Agua captada por la red, normalizada a litros por día.")
    rendimiento_l_m2_dia: float = Field(
        ..., ge=0, description="Litros por día y por m² de colector de la red simulada."
    )
    personas_supervivencia: float = Field(
        ..., ge=0, description="Personas abastecidas con 15 L/persona/día (Sphere, estándar 2.1)."
    )
    personas_acceso_basico: float = Field(
        ..., ge=0, description="Personas abastecidas con 20 L/persona/día (acceso básico, OMS)."
    )
    area_m2_por_persona_basico_literatura_min: float = Field(
        ...,
        gt=0,
        description=(
            "m² de colector por persona para el acceso básico con el rendimiento máximo de la literatura "
            "(10 L/m²/día, Klemm et al., 2012)."
        ),
    )
    area_m2_por_persona_basico_literatura_max: float = Field(
        ...,
        gt=0,
        description=(
            "m² de colector por persona para el acceso básico con el rendimiento mínimo de la literatura "
            "(3 L/m²/día, Klemm et al., 2012)."
        ),
    )


class ParametrosUsados(BaseModel):
    """Sitio y parámetros supuestos con los que se ejecutó una simulación."""

    nombre_sitio: str = Field(..., description="Identificador del perfil de sitio usado.")
    flujo_niebla_maximo_l_m2_h: float = Field(..., description=_DESCRIPCION_FLUJO)
    eficacia_maxima_pulso: float = Field(..., description="Eficacia máxima del pulso resistivo.")
    temperatura_media_c: float = Field(..., description="Temperatura ambiente media en °C.")
    amplitud_temperatura_c: float = Field(..., description="Amplitud del ciclo térmico diurno en °C.")
    amplitud_humedad_pct: float = Field(..., description="Amplitud del ciclo diurno de humedad en puntos de HR.")


class SimulationResult(BaseModel):
    """Resultado completo de una simulación comparativa."""

    comparativa: ComparativaModos
    conjeturas_validadas: ConjeturasValidadas
    detalle_verificacion: DetalleVerificacion
    series_temporales: List[PuntoSerieTemporal]
    bitacora: List[EventoBitacora]
    impacto_comunitario: dict[str, ImpactoComunitario] = Field(
        default_factory=dict,
        description=(
            "Impacto comunitario estimado por modo, con las claves modo_neuro_simbolico, "
            "modo_temporizador_fijo y modo_temporizador_tope_ecologico. Informativo; no interviene "
            "en la validación."
        ),
    )
    parametros_usados: ParametrosUsados | None = Field(
        default=None, description="Sitio y parámetros supuestos usados en la corrida; el simulador siempre lo llena."
    )


# ---------------------------------------------------------------------------
# Análisis de robustez: barrido de salinidad y sensibilidad
# ---------------------------------------------------------------------------
MAXIMO_SEMILLAS = 5
MAXIMO_SEMILLAS_ROBUSTEZ = 3
MAXIMO_VALORES_SENSIBILIDAD = 11
_DESCRIPCION_SEMILLAS = "Semillas del entorno, sin repetir; cada combinación se simula una vez por semilla."
_DESCRIPCION_HUMEDAD_CORRIDAS = "Humedad relativa al inicio de cada corrida (18:00 hora local)."


def _semillas_sin_duplicados(semillas: list[int]) -> list[int]:
    """Rechaza semillas repetidas, que duplicarían corridas idénticas en la estadística."""
    if len(set(semillas)) != len(semillas):
        raise ValueError("Las semillas no deben repetirse.")
    return semillas


# Lista de semillas validada sin repetidos; la comparten el barrido y la robustez.
SemillasUnicas = Annotated[list[int], AfterValidator(_semillas_sin_duplicados)]


class BarridoConfig(BaseModel):
    """Parámetros del barrido de salinidad con una o varias semillas."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"humedad_ambiente_inicial_pct": 85.0, "semillas": [42]}]}
    )

    humedad_ambiente_inicial_pct: float = Field(
        default=85.0, ge=0, le=100, description=_DESCRIPCION_HUMEDAD_CORRIDAS
    )
    duracion_horas: int = Field(default=24, ge=1, le=72, description="Horas simuladas en cada corrida.")
    numero_nodos: int = Field(default=8, ge=1, le=8, description=_DESCRIPCION_NODOS)
    semillas: SemillasUnicas = Field(
        default_factory=lambda: [42],
        min_length=1,
        max_length=MAXIMO_SEMILLAS,
        description=_DESCRIPCION_SEMILLAS,
    )
    flujo_niebla_maximo_l_m2_h: float | None = Field(
        default=None, gt=0, le=20, description=_FLUJO_ADMITIDO + _VALOR_POR_DEFECTO
    )
    eficacia_maxima_pulso: float | None = Field(
        default=None, gt=0, le=1, description=_EFICACIA_ADMITIDA + _VALOR_POR_DEFECTO
    )


class PuntoBarrido(BaseModel):
    """Resultado agregado de una combinación de escenario y tasa de salinización."""

    escenario: Escenario
    tasa_salinizacion: TasaSalinizacion
    carga_salina_ohm_l_m2: float = Field(..., description="Aumento de impedancia por litro captado por m².")
    n_semillas: int = Field(..., ge=1, description="Corridas promediadas, una por semilla.")
    recuperacion_neuro_media: float | None = Field(
        default=None, description="Media de la recuperación tras pulso del neuro-simbólico (%); nula sin pulsos."
    )
    recuperacion_neuro_desv: float | None = Field(
        default=None, description="Desviación estándar muestral de la recuperación del neuro-simbólico."
    )
    recuperacion_temporizador_media: float | None = Field(
        default=None, description="Media de la recuperación tras pulso del temporizador (%); nula sin pulsos."
    )
    recuperacion_temporizador_desv: float | None = Field(
        default=None, description="Desviación estándar muestral de la recuperación del temporizador."
    )
    degradacion_neuro_media: float | None = Field(
        default=None, description="Media de la degradación acumulada del neuro-simbólico (%)."
    )
    degradacion_neuro_desv: float | None = Field(
        default=None, description="Desviación estándar muestral de la degradación del neuro-simbólico."
    )
    degradacion_temporizador_media: float | None = Field(
        default=None, description="Media de la degradación acumulada del temporizador (%)."
    )
    degradacion_temporizador_desv: float | None = Field(
        default=None, description="Desviación estándar muestral de la degradación del temporizador."
    )
    reduccion_desgaste_pct: float | None = Field(
        default=None,
        description="(D_temp - D_neuro) / D_temp * 100 con las medias; nula si el temporizador no se degrada.",
    )
    rendimiento_neuro_l_m2_dia_media: float | None = Field(
        default=None, description="Media del rendimiento del neuro-simbólico en L/m²/día."
    )
    incrustacion_diaria_ohm_media: float | None = Field(
        default=None,
        description="Media de la carga salina por el rendimiento del neuro-simbólico, en Ohm de impedancia por día.",
    )
    ventaja_recuperacion_pts: float | None = Field(
        default=None,
        description=(
            "Recuperación media del neuro-simbólico menos la del temporizador, en puntos porcentuales; "
            "nula si falta alguna."
        ),
    )
    pulsos_neuro_media: float | None = Field(
        default=None, description="Media de los pulsos ejecutados por el neuro-simbólico en toda la red."
    )


class EstadoCruce(str, Enum):
    """Resultado de la búsqueda del punto donde la ventaja en recuperación cambia de signo."""

    INTERPOLADO = "INTERPOLADO"
    CRUCE_DESCENDENTE = "CRUCE_DESCENDENTE"
    SIN_CRUCE_NEURO_SUPERIOR = "SIN_CRUCE_NEURO_SUPERIOR"
    SIN_CRUCE_NEURO_INFERIOR = "SIN_CRUCE_NEURO_INFERIOR"
    SIN_DATOS = "SIN_DATOS"


class CruceRecuperacion(BaseModel):
    """Incrustación diaria y carga salina donde la ventaja en recuperación vale 0, por interpolación lineal."""

    estado: EstadoCruce = Field(
        ...,
        description=(
            "INTERPOLADO: la ventaja pasa de <= 0 a > 0 al crecer la incrustación diaria. CRUCE_DESCENDENTE: "
            "solo pasa de > 0 a <= 0. SIN_CRUCE_NEURO_SUPERIOR o SIN_CRUCE_NEURO_INFERIOR: no cambia de "
            "signo. SIN_DATOS: menos de dos puntos con ventaja."
        ),
    )
    incrustacion_diaria_ohm: float | None = Field(
        default=None, description="Incrustación diaria interpolada en el cruce (Ohm/día); nula sin cruce."
    )
    carga_salina_ohm_l_m2: float | None = Field(
        default=None, description="Carga salina interpolada en el cruce (Ohm por L/m²); nula sin cruce."
    )


class BarridoResultado(BaseModel):
    """Barrido de salinidad ordenado por carga salina creciente."""

    puntos: List[PuntoBarrido]
    flujo_niebla_maximo_l_m2_h: float | None = Field(
        default=None, description="Flujo máximo de niebla usado en las corridas (L/m²/h)."
    )
    eficacia_maxima_pulso: float | None = Field(
        default=None, description="Eficacia máxima del pulso usada en las corridas."
    )
    cruce: CruceRecuperacion | None = Field(
        default=None, description="Cruce de la ventaja en recuperación frente a la incrustación diaria."
    )


class RobustezConfig(BaseModel):
    """Parámetros del barrido de salinidad repetido en la grilla de flujos de niebla y eficacias del pulso."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"humedad_ambiente_inicial_pct": 85.0, "semillas": [42]}]}
    )

    humedad_ambiente_inicial_pct: float = Field(
        default=85.0, ge=0, le=100, description=_DESCRIPCION_HUMEDAD_CORRIDAS
    )
    duracion_horas: int = Field(default=24, ge=24, le=72, description="Horas simuladas en cada corrida, de 24 a 72.")
    numero_nodos: int = Field(default=8, ge=1, le=8, description=_DESCRIPCION_NODOS)
    semillas: SemillasUnicas = Field(
        default_factory=lambda: [42],
        min_length=1,
        max_length=MAXIMO_SEMILLAS_ROBUSTEZ,
        description=_DESCRIPCION_SEMILLAS,
    )


class CombinacionRobustez(BaseModel):
    """Barrido de salinidad con un par de flujo de niebla y eficacia del pulso."""

    flujo_niebla_maximo_l_m2_h: float = Field(..., description=_DESCRIPCION_FLUJO)
    eficacia_maxima_pulso: float = Field(..., description="Eficacia máxima del pulso.")
    barrido: BarridoResultado


class RobustezResultado(BaseModel):
    """Barridos de la grilla de parámetros supuestos y resumen de la respuesta a la pregunta de investigación."""

    combinaciones: list[CombinacionRobustez] = Field(..., description="Combinaciones en orden de flujo y eficacia.")
    reduccion_desgaste_min_pct: float | None = Field(
        default=None, description="Menor reducción del desgaste entre los puntos de todas las combinaciones."
    )
    reduccion_desgaste_max_pct: float | None = Field(
        default=None, description="Mayor reducción del desgaste entre los puntos de todas las combinaciones."
    )
    combinaciones_con_cruce: int = Field(..., ge=0, description="Combinaciones con cruce INTERPOLADO.")
    incrustacion_diaria_cruce_min_ohm: float | None = Field(
        default=None, description="Menor incrustación diaria de cruce entre las combinaciones con cruce INTERPOLADO."
    )
    incrustacion_diaria_cruce_max_ohm: float | None = Field(
        default=None, description="Mayor incrustación diaria de cruce entre las combinaciones con cruce INTERPOLADO."
    )


# ---------------------------------------------------------------------------
# Dimensionamiento del captador
# ---------------------------------------------------------------------------
class EstandarConsumo(str, Enum):
    """Consumo diario por persona: Sphere (15 L, supervivencia) u OMS (20 L, acceso básico)."""

    SPHERE_15 = "SPHERE_15"
    OMS_20 = "OMS_20"


class DimensionamientoConfig(BaseModel):
    """Parámetros del dimensionamiento del captador para un número de personas."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "personas": 50,
                    "estandar": "OMS_20",
                    "escenario": "DIA_NORMAL",
                    "humedad_ambiente_inicial_pct": 85.0,
                }
            ]
        }
    )

    personas: int = Field(..., ge=1, le=1000, description="Personas que se quiere abastecer.")
    estandar: EstandarConsumo = Field(default=EstandarConsumo.OMS_20, description="Estándar de consumo diario.")
    escenario: Escenario = Field(..., description=_DESCRIPCION_ESCENARIO)
    humedad_ambiente_inicial_pct: float = Field(
        ..., ge=0, le=100, description=_DESCRIPCION_HUMEDAD_INICIAL
    )
    tasa_salinizacion: TasaSalinizacion = Field(
        default=TasaSalinizacion.ALTA, description=_DESCRIPCION_TASA
    )
    semilla: int = Field(default=42, description=_DESCRIPCION_SEMILLA)


class DimensionPorFlujo(BaseModel):
    """Área de colector y nodos necesarios con un flujo de niebla."""

    origen_flujo: str = Field(..., description="SUPUESTO, CALIBRADO_MAX o CALIBRADO_MIN.")
    flujo_niebla_maximo_l_m2_h: float = Field(..., description=_DESCRIPCION_FLUJO)
    rendimiento_neuro_l_m2_dia: float = Field(..., ge=0, description="Rendimiento del neuro-simbólico en L/m²/día.")
    area_colector_m2: float | None = Field(
        default=None, description="Área de colector requerida en m²; nula si el rendimiento es 0."
    )
    nodos_requeridos: int | None = Field(
        default=None,
        description="Nodos de 1 m² requeridos (área redondeada hacia arriba); nulo si el rendimiento es 0.",
    )


class DimensionamientoResultado(BaseModel):
    """Dimensionamiento con los tres flujos de referencia y el rango de área de la literatura."""

    consumo_l_persona_dia: float = Field(..., gt=0, description="Consumo diario por persona del estándar elegido.")
    dimensiones: list[DimensionPorFlujo] = Field(..., description="Una dimensión por flujo de referencia.")
    area_literatura_min_m2: float = Field(
        ..., gt=0, description="Área con el rendimiento máximo de la literatura (10 L/m²/día, Klemm et al., 2012)."
    )
    area_literatura_max_m2: float = Field(
        ..., gt=0, description="Área con el rendimiento mínimo de la literatura (3 L/m²/día, Klemm et al., 2012)."
    )


class ParametroSensible(str, Enum):
    """Parámetros supuestos del modelo que admite el análisis de sensibilidad."""

    EFICACIA_MAXIMA_PULSO = "EFICACIA_MAXIMA_PULSO"
    FLUJO_NIEBLA_MAXIMO = "FLUJO_NIEBLA_MAXIMO"


# Intervalo admitido (mínimo excluido, máximo incluido) para cada parámetro sensible.
LIMITES_PARAMETRO_SENSIBLE = {
    ParametroSensible.EFICACIA_MAXIMA_PULSO: (0.0, 1.0),
    ParametroSensible.FLUJO_NIEBLA_MAXIMO: (0.0, 20.0),
}


class SensibilidadConfig(BaseModel):
    """Parámetros de un análisis de sensibilidad sobre un parámetro supuesto."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "escenario": "DIA_NORMAL",
                    "humedad_ambiente_inicial_pct": 85.0,
                    "tasa_salinizacion": "ALTA",
                    "parametro": "EFICACIA_MAXIMA_PULSO",
                    "valores": [0.90, 0.94, 0.97],
                }
            ]
        }
    )

    escenario: Escenario = Field(..., description=_DESCRIPCION_ESCENARIO)
    humedad_ambiente_inicial_pct: float = Field(
        ..., ge=0, le=100, description=_DESCRIPCION_HUMEDAD_INICIAL
    )
    tasa_salinizacion: TasaSalinizacion = Field(..., description=_DESCRIPCION_TASA)
    duracion_horas: int = Field(default=24, ge=1, le=72, description="Horas simuladas.")
    semilla: int = Field(default=42, description=_DESCRIPCION_SEMILLA)
    parametro: ParametroSensible = Field(..., description="Parámetro supuesto que se varía.")
    valores: List[float] = Field(
        ...,
        min_length=1,
        max_length=MAXIMO_VALORES_SENSIBILIDAD,
        description="Valores del parámetro: eficacia en (0, 1]; flujo de niebla en (0, 20] L/m²/h.",
    )

    @model_validator(mode="after")
    def _valores_en_rango(self) -> "SensibilidadConfig":
        """Rechaza valores fuera del intervalo físico admitido para el parámetro elegido."""
        minimo, maximo = LIMITES_PARAMETRO_SENSIBLE[self.parametro]
        fuera = [valor for valor in self.valores if not minimo < valor <= maximo]
        if fuera:
            raise ValueError(
                f"Valores fuera de ({minimo:g}, {maximo:g}] para {self.parametro.value}: {fuera}"
            )
        return self


class PuntoSensibilidad(BaseModel):
    """Resultado de una simulación con un valor del parámetro sensible."""

    valor: float = Field(..., description="Valor del parámetro en esta corrida.")
    conjeturas_validadas: ConjeturasValidadas
    recuperacion_caudal_promedio_pct: float | None = Field(
        default=None, description="Indicador de la Conjetura 1; nulo sin pulsos."
    )
    tiempo_regeneracion_promedio_seg: float | None = Field(
        default=None, description="Indicador de la Conjetura 2; nulo sin pulsos."
    )
    rendimiento_nocturno_l_m2_noche: float | None = Field(
        default=None, description="Indicador de la Conjetura 3; nulo sin horas nocturnas."
    )
    litros_neuro: float = Field(..., ge=0, description="Agua captada por el modo neuro-simbólico en litros.")


class SensibilidadResultado(BaseModel):
    """Resultados del análisis de sensibilidad en el orden de los valores solicitados."""

    parametro: ParametroSensible
    puntos: List[PuntoSensibilidad]


# ---------------------------------------------------------------------------
# Propagación de la incertidumbre de los parámetros supuestos
# ---------------------------------------------------------------------------
MINIMO_MUESTRAS = 5
MAXIMO_MUESTRAS = 30


class IncertidumbreConfig(BaseModel):
    """Parámetros de la propagación de la incertidumbre de la eficacia del pulso y del flujo de niebla.

    Cada muestra toma una eficacia y un flujo con distribución uniforme en los
    rangos indicados y simula una corrida con esos valores. Los rangos por
    defecto son los de `backend/config.py`: eficacia de 0.80 a 1.00 (supuesto)
    y flujo de 0.49 a 1.83 L/m²/h (calibración inversa contra la literatura).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "escenario": "DIA_NORMAL",
                    "humedad_ambiente_inicial_pct": 85.0,
                    "tasa_salinizacion": "ALTA",
                    "n_muestras": 20,
                }
            ]
        }
    )

    escenario: Escenario = Field(..., description=_DESCRIPCION_ESCENARIO)
    humedad_ambiente_inicial_pct: float = Field(
        ..., ge=0, le=100, description=_DESCRIPCION_HUMEDAD_INICIAL
    )
    tasa_salinizacion: TasaSalinizacion = Field(..., description=_DESCRIPCION_TASA)
    duracion_horas: int = Field(default=24, ge=1, le=72, description="Horas simuladas en cada corrida.")
    semilla: int = Field(default=42, description="Semilla del entorno; es la misma en todas las muestras.")
    semilla_muestreo: int = Field(default=7, description="Semilla del muestreo de los parámetros.")
    n_muestras: int = Field(
        default=20, ge=MINIMO_MUESTRAS, le=MAXIMO_MUESTRAS, description="Número de muestras simuladas."
    )
    eficacia_min: float = Field(default=config.EFICACIA_PULSO_RANGO_MIN, gt=0, le=1, description=_EFICACIA_ADMITIDA)
    eficacia_max: float = Field(default=config.EFICACIA_PULSO_RANGO_MAX, gt=0, le=1, description=_EFICACIA_ADMITIDA)
    flujo_min: float = Field(default=config.FLUJO_NIEBLA_CALIBRADO_MIN_L_M2_H, gt=0, le=20, description=_FLUJO_ADMITIDO)
    flujo_max: float = Field(default=config.FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H, gt=0, le=20, description=_FLUJO_ADMITIDO)

    @model_validator(mode="after")
    def _rangos_ordenados(self) -> "IncertidumbreConfig":
        """Rechaza rangos vacíos o invertidos: el mínimo debe ser menor que el máximo."""
        if self.eficacia_min >= self.eficacia_max:
            raise ValueError("eficacia_min debe ser menor que eficacia_max.")
        if self.flujo_min >= self.flujo_max:
            raise ValueError("flujo_min debe ser menor que flujo_max.")
        return self


class MuestraIncertidumbre(BaseModel):
    """Resultado de una corrida con una muestra de los parámetros supuestos."""

    eficacia: float = Field(..., description="Eficacia máxima del pulso de la muestra.")
    flujo: float = Field(..., description="Flujo máximo de niebla de la muestra en L/m²/h.")
    conjeturas_validadas: ConjeturasValidadas
    recuperacion_caudal_promedio_pct: float | None = Field(
        default=None, description="Indicador de la Conjetura 1; nulo sin pulsos."
    )
    rendimiento_l_m2_dia: float | None = Field(
        default=None, description="Agua del modo neuro-simbólico por día y por m² de colector."
    )
    reduccion_degradacion_pct: float | None = Field(
        default=None, description="Reducción de la degradación frente al temporizador (%); informativo."
    )
    recuperacion_temporizador_pct: float | None = Field(
        default=None, description="Recuperación media tras pulso del temporizador (%); nula sin pulsos."
    )
    ventaja_recuperacion_pts: float | None = Field(
        default=None,
        description="Recuperación del neuro-simbólico menos la del temporizador, en puntos; nula si falta alguna.",
    )


class ResumenDistribucion(BaseModel):
    """Percentiles 5, 50 y 95 de un indicador entre las muestras con datos."""

    p5: float | None = Field(default=None, description="Percentil 5; nulo si ninguna muestra tiene datos.")
    p50: float | None = Field(default=None, description="Mediana; nula si ninguna muestra tiene datos.")
    p95: float | None = Field(default=None, description="Percentil 95; nulo si ninguna muestra tiene datos.")
    n_validos: int = Field(..., ge=0, description="Muestras con datos para el indicador.")


class IncertidumbreResultado(BaseModel):
    """Probabilidad de validar cada conjetura y dispersión de los indicadores entre las muestras."""

    probabilidad_c1: float = Field(..., ge=0, le=1, description="Proporción de muestras que validan la Conjetura 1.")
    probabilidad_c2: float = Field(..., ge=0, le=1, description="Proporción de muestras que validan la Conjetura 2.")
    probabilidad_c3: float = Field(..., ge=0, le=1, description="Proporción de muestras que validan la Conjetura 3.")
    recuperacion: ResumenDistribucion = Field(..., description="Recuperación de caudal tras pulso (%).")
    rendimiento: ResumenDistribucion = Field(..., description="Rendimiento del neuro-simbólico (L/m²/día).")
    reduccion_degradacion: ResumenDistribucion = Field(
        ..., description="Reducción de la degradación frente al temporizador (%)."
    )
    muestras: list[MuestraIncertidumbre] = Field(..., description="Muestras en el orden en que se generaron.")
    ventaja_recuperacion: ResumenDistribucion | None = Field(
        default=None, description="Ventaja en recuperación del neuro-simbólico frente al temporizador (puntos)."
    )
    probabilidad_ventaja_recuperacion: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Proporción de las muestras con ambas recuperaciones en que la ventaja es positiva; "
            "nula si ninguna muestra tiene ambas."
        ),
    )
