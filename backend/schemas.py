"""Esquemas de entrada y salida de la API del motor Axioma-H.

Los nombres de modelos y campos siguen el PRD de la API. Los enumerados
unifican los valores usados en el PRD y en la Matriz de Operacionalización
(decisión D4).
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class AccionControl(str, Enum):
    """Acción recomendada por el motor de reglas."""

    CORTE_DE_EMERGENCIA = "CORTE_DE_EMERGENCIA"
    PAUSA_ECOLOGICA = "PAUSA_ECOLOGICA"
    REDUCIR_CAUDAL_SIN_PULSO = "REDUCIR_CAUDAL_SIN_PULSO"
    APLICAR_PULSO_RESISTIVO = "APLICAR_PULSO_RESISTIVO"
    FILTRACION_PASIVA_CONTINUA = "FILTRACION_PASIVA_CONTINUA"


class TelemetryInput(BaseModel):
    """Lectura de sensores de un nodo de captación."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nodo_id": "NODO_04",
                    "impedancia_ohms": 1850.5,
                    "temperatura_celsius": 38.2,
                    "reserva_calor_pct": 65.0,
                    "humedad_relativa_pct": 82.0,
                    "flujo_actual_ml_min": 12.5,
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
                    "humedad_ambiente_inicial_pct": 85.0,
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


class ComparativaModos(BaseModel):
    """Resultados de ambos modos sobre el mismo entorno."""

    modo_neuro_simbolico: ResultadoModo
    modo_temporizador_fijo: ResultadoModo


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


class SimulationResult(BaseModel):
    """Resultado completo de una simulación comparativa."""

    comparativa: ComparativaModos
    conjeturas_validadas: ConjeturasValidadas
    detalle_verificacion: DetalleVerificacion
    series_temporales: List[PuntoSerieTemporal]
    bitacora: List[EventoBitacora]
