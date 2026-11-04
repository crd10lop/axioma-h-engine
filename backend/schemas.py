"""Esquemas de entrada y salida de la API del motor Axioma-H.

Los nombres de modelos y campos siguen el PRD de la API. Los enumerados
unifican los valores usados en el PRD y en la Matriz de Operacionalización
(decisión D4).
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    escenario: Escenario = Field(..., description="Escenario ambiental.")
    humedad_ambiente_inicial_pct: float = Field(
        ..., ge=0, le=100, description="Humedad relativa al inicio de la simulación (18:00 hora local)."
    )
    tasa_salinizacion: TasaSalinizacion = Field(..., description="Velocidad de incrustación salina.")
    numero_nodos: int = Field(default=8, ge=1, le=8, description="Cantidad de nodos simulados.")
    paso_minutos: int = Field(default=5, ge=1, le=60, description="Resolución temporal en minutos.")
    semilla: int = Field(default=42, description="Semilla del generador aleatorio del entorno.")


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


# ---------------------------------------------------------------------------
# Análisis de robustez: barrido de salinidad y sensibilidad
# ---------------------------------------------------------------------------
MAXIMO_SEMILLAS = 5
MAXIMO_VALORES_SENSIBILIDAD = 11


class BarridoConfig(BaseModel):
    """Parámetros del barrido de salinidad con una o varias semillas."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"humedad_ambiente_inicial_pct": 85.0, "semillas": [42]}]}
    )

    humedad_ambiente_inicial_pct: float = Field(
        default=85.0, ge=0, le=100, description="Humedad relativa al inicio de cada corrida (18:00 hora local)."
    )
    duracion_horas: int = Field(default=24, ge=1, le=72, description="Horas simuladas en cada corrida.")
    numero_nodos: int = Field(default=8, ge=1, le=8, description="Cantidad de nodos simulados.")
    semillas: List[int] = Field(
        default_factory=lambda: [42],
        min_length=1,
        max_length=MAXIMO_SEMILLAS,
        description="Semillas del entorno, sin repetir; cada combinación se simula una vez por semilla.",
    )

    @field_validator("semillas")
    @classmethod
    def _semillas_sin_duplicados(cls, semillas: List[int]) -> List[int]:
        """Rechaza semillas repetidas, que duplicarían corridas idénticas en la estadística."""
        if len(set(semillas)) != len(semillas):
            raise ValueError("Las semillas no deben repetirse.")
        return semillas


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


class BarridoResultado(BaseModel):
    """Barrido de salinidad ordenado por carga salina creciente."""

    puntos: List[PuntoBarrido]


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

    escenario: Escenario = Field(..., description="Escenario ambiental.")
    humedad_ambiente_inicial_pct: float = Field(
        ..., ge=0, le=100, description="Humedad relativa al inicio de la simulación (18:00 hora local)."
    )
    tasa_salinizacion: TasaSalinizacion = Field(..., description="Velocidad de incrustación salina.")
    duracion_horas: int = Field(default=24, ge=1, le=72, description="Horas simuladas.")
    semilla: int = Field(default=42, description="Semilla del generador aleatorio del entorno.")
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
