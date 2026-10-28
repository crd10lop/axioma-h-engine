"""Motor de reglas neuro-simbólico del nodo de captación.

Las reglas se evalúan en orden de prioridad estricto y la primera que se
cumple determina la decisión:

    1. REGLA_01_LIMITE_TERMICO_ABSOLUTO
    2. REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL
    3. REGLA_04_PROTECCION_RESERVA_CRITICA
    4. REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA
    5. REGLA_05_OPERACION_NOMINAL

La REGLA_04 se evalúa antes que la REGLA_03 porque ambas comparten la
condición de impedancia alta y la REGLA_04 protege la reserva térmica. Los
nombres conservan la numeración del PRD.

Todas las funciones son puras: no dependen de estado global y, con el mismo
instante de referencia, devuelven siempre la misma decisión.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend import config, modelo_fisico
from backend.schemas import (
    AccionControl,
    ControlDecision,
    EstadoNodo,
    MetricasConjeturas,
    ModoOperacion,
    TelemetryInput,
)

REGLA_01 = "REGLA_01_LIMITE_TERMICO_ABSOLUTO"
REGLA_02 = "REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL"
REGLA_03 = "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA"
REGLA_04 = "REGLA_04_PROTECCION_RESERVA_CRITICA"
REGLA_05 = "REGLA_05_OPERACION_NOMINAL"
SIN_REGLAS_TEMPORIZADOR = "SIN_REGLAS_TEMPORIZADOR_FIJO"


@dataclass(frozen=True)
class _Accion:
    """Resultado intermedio de la evaluación de reglas."""

    regla: str
    estado: EstadoNodo
    accion: AccionControl
    pulso: bool
    temperatura_objetivo_c: Optional[float]
    caudal_pct: float
    motivo: str


def _seleccionar_regla(t: TelemetryInput) -> _Accion:
    """Aplica las reglas en orden de prioridad y devuelve la primera que se cumple."""
    if t.temperatura_celsius >= config.UMBRAL_TEMPERATURA_CORTE_C:
        return _Accion(
            regla=REGLA_01,
            estado=EstadoNodo.EMERGENCIA_TERMICA,
            accion=AccionControl.CORTE_DE_EMERGENCIA,
            pulso=False,
            temperatura_objetivo_c=None,
            caudal_pct=0.0,
            motivo=(
                f"Temperatura de la matriz {t.temperatura_celsius:.1f} °C igual o superior al límite "
                f"absoluto de {config.UMBRAL_TEMPERATURA_CORTE_C:.1f} °C. Se cortan la resistencia "
                "y la extracción para proteger la membrana."
            ),
        )
    if t.humedad_relativa_pct < config.UMBRAL_HUMEDAD_ECOLOGICA_PCT:
        return _Accion(
            regla=REGLA_02,
            estado=EstadoNodo.PAUSA_ECOLOGICA,
            accion=AccionControl.PAUSA_ECOLOGICA,
            pulso=False,
            temperatura_objetivo_c=None,
            caudal_pct=0.0,
            motivo=(
                f"Humedad relativa {t.humedad_relativa_pct:.1f} % inferior al umbral ecológico de "
                f"{config.UMBRAL_HUMEDAD_ECOLOGICA_PCT:.1f} %. Se suspende la extracción para no "
                "competir con la vegetación y la fauna locales."
            ),
        )
    impedancia_alta = t.impedancia_ohms > config.UMBRAL_IMPEDANCIA_OHMS
    if impedancia_alta and t.reserva_calor_pct < config.UMBRAL_RESERVA_CRITICA_PCT:
        return _Accion(
            regla=REGLA_04,
            estado=EstadoNodo.RESERVA_CRITICA,
            accion=AccionControl.REDUCIR_CAUDAL_SIN_PULSO,
            pulso=False,
            temperatura_objetivo_c=None,
            caudal_pct=config.CAUDAL_RESERVA_CRITICA_PCT,
            motivo=(
                f"Impedancia {t.impedancia_ohms:.1f} Ohm sobre el umbral de "
                f"{config.UMBRAL_IMPEDANCIA_OHMS:.1f} Ohm, pero la reserva térmica "
                f"({t.reserva_calor_pct:.1f} %) es inferior al {config.UMBRAL_RESERVA_CRITICA_PCT:.1f} %. "
                f"Se reduce el caudal al {config.CAUDAL_RESERVA_CRITICA_PCT:.0f} % sin aplicar pulso."
            ),
        )
    if impedancia_alta:
        return _Accion(
            regla=REGLA_03,
            estado=EstadoNodo.CRISTALIZACION_DETECTADA,
            accion=AccionControl.APLICAR_PULSO_RESISTIVO,
            pulso=True,
            temperatura_objetivo_c=config.TEMPERATURA_OBJETIVO_PULSO_C,
            caudal_pct=config.CAUDAL_DURANTE_PULSO_PCT,
            motivo=(
                f"Impedancia {t.impedancia_ohms:.1f} Ohm sobre el umbral de "
                f"{config.UMBRAL_IMPEDANCIA_OHMS:.1f} Ohm: cristalización salina detectada. Se aplica "
                f"un pulso de {config.DURACION_PULSO_SEG} s hacia {config.TEMPERATURA_OBJETIVO_PULSO_C:.1f} °C "
                f"y el caudal se ajusta al {config.CAUDAL_DURANTE_PULSO_PCT:.0f} %."
            ),
        )
    return _Accion(
        regla=REGLA_05,
        estado=EstadoNodo.NOMINAL,
        accion=AccionControl.FILTRACION_PASIVA_CONTINUA,
        pulso=False,
        temperatura_objetivo_c=None,
        caudal_pct=config.CAUDAL_NOMINAL_PCT,
        motivo=(
            f"Condiciones dentro de rango (impedancia {t.impedancia_ohms:.1f} Ohm, humedad "
            f"{t.humedad_relativa_pct:.1f} %, temperatura {t.temperatura_celsius:.1f} °C). "
            "Filtración pasiva continua al tope ecológico."
        ),
    )


def temperatura_alcanzada_pulso(temperatura_matriz_c: float) -> float:
    """Temperatura de la matriz durante un pulso del modo neuro-simbólico.

    El pulso eleva la matriz hasta la temperatura objetivo; si ya está más
    caliente (sin llegar al corte), conserva su temperatura actual.
    """
    return max(temperatura_matriz_c, config.TEMPERATURA_OBJETIVO_PULSO_C)


def calcular_metricas(
    telemetria: TelemetryInput,
    pulso: bool,
    caudal_pct: float,
    fraccion_base: float,
) -> MetricasConjeturas:
    """Calcula los indicadores de conjeturas para una decisión individual.

    - recuperacion_hidraulica_pct = min(100, Z_nominal / Z_tras_accion * 100).
      Con pulso, Z_tras_accion = Z_nominal + Z_sal * (1 - eta), donde Z_sal es
      el exceso sobre la nominal y eta la eficacia del modelo físico. Sin pulso,
      Z_tras_accion es la impedancia medida.
    - eficiencia_energetica_pct = 100 * R / (R + C), donde R son los puntos
      porcentuales de conductancia recuperados y C los puntos porcentuales de
      reserva consumidos por el pulso. Vale 100 si la acción no consume reserva.
    - preservacion_ecologica_ok es verdadero si no hay extracción con humedad
      inferior al umbral ecológico y la fracción efectiva no supera el 33 %.
    """
    z_actual = telemetria.impedancia_ohms
    recuperacion_previa = modelo_fisico.conductancia_relativa(z_actual) * 100.0

    if pulso:
        temperatura = temperatura_alcanzada_pulso(telemetria.temperatura_celsius)
        z_sal = max(0.0, z_actual - config.IMPEDANCIA_NOMINAL_OHMS)
        z_tras = config.IMPEDANCIA_NOMINAL_OHMS + modelo_fisico.impedancia_sal_tras_pulso(temperatura, z_sal)
        energia = modelo_fisico.energia_pulso_wh(temperatura - telemetria.temperatura_celsius)
        consumo_pct = energia / config.CAPACIDAD_RESERVA_WH * 100.0
    else:
        z_tras = z_actual
        consumo_pct = 0.0

    recuperacion = min(100.0, modelo_fisico.conductancia_relativa(z_tras) * 100.0)
    ganancia = max(0.0, recuperacion - recuperacion_previa)
    if consumo_pct > 0:
        eficiencia = 100.0 * ganancia / (ganancia + consumo_pct)
    else:
        eficiencia = 100.0

    fraccion_efectiva = fraccion_base * caudal_pct / 100.0
    extrae = fraccion_efectiva > 0
    humedad_baja = telemetria.humedad_relativa_pct < config.UMBRAL_HUMEDAD_ECOLOGICA_PCT
    preservacion = not (extrae and humedad_baja) and fraccion_efectiva <= config.FRACCION_MAXIMA_EXTRACCION

    return MetricasConjeturas(
        eficiencia_energetica_pct=round(eficiencia, 2),
        recuperacion_hidraulica_pct=round(recuperacion, 2),
        preservacion_ecologica_ok=preservacion,
    )


def evaluar_telemetria(telemetria: TelemetryInput, instante: Optional[datetime] = None) -> ControlDecision:
    """Evalúa una lectura de telemetría y devuelve la decisión de control.

    En modo TEMPORIZADOR_FIJO no se evalúan reglas: el control tradicional
    filtra de forma continua con su fracción fija de extracción. El parámetro
    `instante` permite fijar la marca de tiempo; si se omite se usa la hora UTC
    actual.
    """
    marca = instante or datetime.now(timezone.utc)

    if telemetria.modo_operacion == ModoOperacion.TEMPORIZADOR_FIJO:
        accion = _Accion(
            regla=SIN_REGLAS_TEMPORIZADOR,
            estado=EstadoNodo.NOMINAL,
            accion=AccionControl.FILTRACION_PASIVA_CONTINUA,
            pulso=False,
            temperatura_objetivo_c=None,
            caudal_pct=config.CAUDAL_NOMINAL_PCT,
            motivo=(
                "Modo temporizador fijo: el control no evalúa sensores. Mantiene la filtración continua "
                f"con una fracción fija del {config.FRACCION_EXTRACCION_TEMPORIZADOR * 100:.0f} % y "
                f"aplica pulsos cada {config.INTERVALO_PULSO_TEMPORIZADOR_MIN} min según su programación."
            ),
        )
        fraccion_base = config.FRACCION_EXTRACCION_TEMPORIZADOR
    else:
        accion = _seleccionar_regla(telemetria)
        fraccion_base = config.FRACCION_MAXIMA_EXTRACCION

    metricas = calcular_metricas(telemetria, accion.pulso, accion.caudal_pct, fraccion_base)

    return ControlDecision(
        nodo_id=telemetria.nodo_id,
        timestamp=marca,
        estado_nodo=accion.estado,
        accion_recomendada=accion.accion,
        pulso_termico_activo=accion.pulso,
        temperatura_objetivo_c=accion.temperatura_objetivo_c,
        duracion_pulso_seg=config.DURACION_PULSO_SEG if accion.pulso else 0,
        ajuste_caudal_pct=accion.caudal_pct,
        regla_activada=accion.regla,
        motivo=accion.motivo,
        metricas_conjeturas=metricas,
    )
