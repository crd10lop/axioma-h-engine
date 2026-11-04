"""Simulador comparativo de la red de nodos de captación.

Ejecuta el mismo entorno, generado con una semilla fija, para dos estrategias
de control: el motor neuro-simbólico y un temporizador fijo sin sensores.
Los resultados y la verificación de las conjeturas se calculan a partir del
modelo; ningún indicador se fija de antemano (decisión D5).

La simulación arranca a las 18:00 hora local y avanza en pasos discretos de
`paso_minutos`. Las ecuaciones se documentan en `docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md`.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from backend import config, modelo_fisico
from backend.modelo_fisico import PARAMETROS_BASE, ParametrosModelo
from backend.motor_reglas import evaluar_telemetria, temperatura_alcanzada_pulso
from backend.schemas import (
    CausaNoValidacion,
    ComparativaModos,
    ConjeturasValidadas,
    DetalleVerificacion,
    Escenario,
    EventoBitacora,
    IndicadorVerificacion,
    ModoOperacion,
    PuntoSerieTemporal,
    ResultadoModo,
    SimulationConfig,
    SimulationResult,
    TasaSalinizacion,
    TelemetryInput,
    VerificacionConjetura,
)

# Instante de referencia para las decisiones internas; no se expone en la respuesta.
_INSTANTE_REFERENCIA = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)
_TOLERANCIA = 1e-9


# ---------------------------------------------------------------------------
# Entorno
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Entorno:
    """Condiciones ambientales precalculadas, idénticas para ambos modos."""

    paso_minutos: int
    minutos: List[int]
    horas_locales: List[float]
    humedad: List[List[float]]
    temperatura_ambiente: List[float]
    temperatura_matriz: List[List[float]]
    radiacion: List[float]
    factor_captacion: List[float]
    ensuciamiento_ohm_h: List[float]
    incrustacion_ohm_por_l_m2: List[float]

    @property
    def numero_nodos(self) -> int:
        """Cantidad de nodos del entorno."""
        return len(self.incrustacion_ohm_por_l_m2)

    @property
    def numero_pasos(self) -> int:
        """Cantidad de pasos simulados."""
        return len(self.minutos)


def _en_ventana(hora: float, inicio: float, fin: float) -> bool:
    """Indica si la hora local cae en la ventana [inicio, fin), con cruce de medianoche."""
    if inicio <= fin:
        return inicio <= hora < fin
    return hora >= inicio or hora < fin


def _radiacion_solar(hora: float) -> float:
    """Radiación relativa entre 0 y 1: semiseno de 06:00 a 18:00."""
    if 6.0 <= hora <= 18.0:
        return max(0.0, math.sin(math.pi * (hora - 6.0) / 12.0))
    return 0.0


def _ciclo_humedad(hora: float) -> float:
    """Forma del ciclo diurno de humedad, con máximo a las 04:00."""
    return math.cos(2.0 * math.pi * (hora - config.HORA_MAXIMA_HUMEDAD) / 24.0)


def tasa_incrustacion_base(escenario: Escenario, tasa: TasaSalinizacion) -> float:
    """Ohm por litro captado por m² según el escenario y la tasa elegida."""
    if escenario == Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO:
        return config.INCRUSTACION_OHM_POR_L_M2["ALTA"] * config.MULTIPLICADOR_INCRUSTACION_SAL_Y_CALOR
    base = config.INCRUSTACION_OHM_POR_L_M2[tasa.value]
    if escenario == Escenario.INCRUSTACION_SALINA_RAPIDA:
        return base * config.MULTIPLICADOR_INCRUSTACION_RAPIDA
    return base


def _tasa_incrustacion_base(escenario: Escenario, tasa: TasaSalinizacion) -> float:
    """Alias interno de `tasa_incrustacion_base`, que también usa el análisis de robustez."""
    return tasa_incrustacion_base(escenario, tasa)


def _humedad_base(cfg: SimulationConfig, hora: float, referencia_humedad: float) -> float:
    """Humedad del ciclo diurno a la hora dada, con la reducción del escenario de sequía."""
    humedad_base = cfg.humedad_ambiente_inicial_pct + config.AMPLITUD_HUMEDAD_PCT * (
        _ciclo_humedad(hora) - referencia_humedad
    )
    if cfg.escenario == Escenario.SEQUIA:
        humedad_base -= config.SEQUIA_REDUCCION_HUMEDAD_PCT
    return humedad_base


def _temperatura_ambiente(escenario: Escenario, hora: float, sol: float) -> float:
    """Temperatura ambiente a la hora dada, con el calor adicional del escenario extremo."""
    temperatura = config.TEMPERATURA_MEDIA_C + config.AMPLITUD_TEMPERATURA_C * math.cos(
        2.0 * math.pi * (hora - config.HORA_MAXIMA_TEMPERATURA) / 24.0
    )
    if escenario == Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO:
        temperatura += config.CALOR_EXTREMO_INCREMENTO_C * sol
    return temperatura


def _condiciones_nodos(
    rng: random.Random,
    humedad_base: float,
    temperatura: float,
    sol_efectivo: float,
    sequia_severa: bool,
    desfase_humedad: List[float],
    desfase_temperatura: List[float],
) -> Tuple[List[float], List[float]]:
    """Humedad y temperatura de la matriz de cada nodo en un paso, con su desfase y ruido gaussiano."""
    humedad_paso, matriz_paso = [], []
    for n in range(len(desfase_humedad)):
        hr = humedad_base + desfase_humedad[n] + rng.gauss(0.0, config.RUIDO_HUMEDAD_PASO_PCT)
        if sequia_severa:
            hr = min(hr, config.SEQUIA_HUMEDAD_MAXIMA_PCT + rng.gauss(0.0, config.RUIDO_HUMEDAD_PASO_PCT))
        humedad_paso.append(max(0.0, min(100.0, hr)))
        matriz_paso.append(
            temperatura
            + config.CALENTAMIENTO_SOLAR_MATRIZ_C * sol_efectivo
            + desfase_temperatura[n]
            + rng.gauss(0.0, config.RUIDO_TEMPERATURA_PASO_C)
        )
    return humedad_paso, matriz_paso


def generar_entorno(cfg: SimulationConfig) -> Entorno:
    """Genera las condiciones ambientales de la simulación.

    La humedad sigue un ciclo cosenoidal anclado al valor inicial a las 18:00;
    la temperatura ambiente oscila entre 25.5 y 34.5 °C con máximo a las 14:00
    y la matriz se calienta con la radiación solar. Cada nodo recibe un
    desfase fijo y ruido gaussiano por paso.
    """
    rng = random.Random(cfg.semilla)
    paso = cfg.paso_minutos
    numero_pasos = (cfg.duracion_horas * 60) // paso
    escenario = cfg.escenario

    desfase_humedad = [rng.uniform(-1, 1) * config.DISPERSION_HUMEDAD_NODO_PCT for _ in range(cfg.numero_nodos)]
    desfase_temperatura = [
        rng.uniform(-1, 1) * config.DISPERSION_TEMPERATURA_NODO_C for _ in range(cfg.numero_nodos)
    ]
    tasa_base = _tasa_incrustacion_base(escenario, cfg.tasa_salinizacion)
    incrustacion = [
        tasa_base * (1.0 + rng.uniform(-1, 1) * config.DISPERSION_SALINIZACION_NODO)
        for _ in range(cfg.numero_nodos)
    ]

    referencia_humedad = _ciclo_humedad(config.HORA_INICIO_SIMULACION)
    minutos, horas, humedad, t_amb, t_mat, radiacion, captacion, ensuciamiento = [], [], [], [], [], [], [], []

    for i in range(numero_pasos):
        minuto = i * paso
        hora = (config.HORA_INICIO_SIMULACION + minuto / 60.0) % 24.0
        sol = _radiacion_solar(hora)

        tormenta_arena = escenario == Escenario.TORMENTA_DE_ARENA and _en_ventana(
            hora, config.TORMENTA_ARENA_HORA_INICIO, config.TORMENTA_ARENA_HORA_FIN
        )
        sequia_severa = escenario == Escenario.SEQUIA and _en_ventana(
            hora, config.SEQUIA_HORA_INICIO, config.SEQUIA_HORA_FIN
        )

        humedad_base = _humedad_base(cfg, hora, referencia_humedad)
        temperatura = _temperatura_ambiente(escenario, hora, sol)

        sol_efectivo = sol * (config.TORMENTA_ARENA_FACTOR_RADIACION if tormenta_arena else 1.0)

        humedad_paso, matriz_paso = _condiciones_nodos(
            rng, humedad_base, temperatura, sol_efectivo, sequia_severa, desfase_humedad, desfase_temperatura
        )

        minutos.append(minuto)
        horas.append(hora)
        humedad.append(humedad_paso)
        t_amb.append(temperatura)
        t_mat.append(matriz_paso)
        radiacion.append(sol_efectivo)
        captacion.append(config.TORMENTA_ARENA_FACTOR_CAPTACION if tormenta_arena else 1.0)
        ensuciamiento.append(config.TORMENTA_ARENA_ENSUCIAMIENTO_OHM_H if tormenta_arena else 0.0)

    return Entorno(
        paso_minutos=paso,
        minutos=minutos,
        horas_locales=horas,
        humedad=humedad,
        temperatura_ambiente=t_amb,
        temperatura_matriz=t_mat,
        radiacion=radiacion,
        factor_captacion=captacion,
        ensuciamiento_ohm_h=ensuciamiento,
        incrustacion_ohm_por_l_m2=incrustacion,
    )


# ---------------------------------------------------------------------------
# Simulación de un modo
# ---------------------------------------------------------------------------
@dataclass
class _EstadoNodo:
    """Estado dinámico de un nodo durante la simulación."""

    impedancia_sal: float = 0.0
    impedancia_polvo: float = 0.0
    reserva_wh: float = config.CAPACIDAD_RESERVA_WH * config.RESERVA_INICIAL_PCT / 100.0
    integridad: float = 100.0
    flujo_ml_min: float = 0.0
    ultimo_pulso_min: int = 0
    regla_previa: Optional[str] = None
    en_violacion: bool = False
    pulso_no_regenerado_min: Optional[int] = None

    @property
    def impedancia(self) -> float:
        """Impedancia total: nominal más componentes salina y de polvo."""
        return config.IMPEDANCIA_NOMINAL_OHMS + self.impedancia_sal + self.impedancia_polvo


@dataclass
class DiagnosticoModo:
    """Resultados detallados de un modo, usados para la verificación y las pruebas."""

    modo: ModoOperacion
    litros_totales: float = 0.0
    pulsos: int = 0
    energia_total_wh: float = 0.0
    energia_pulsos_wh: float = 0.0
    violaciones_ecologicas: int = 0
    integridad_final_promedio: float = 100.0
    perdida_termica_pulso_pct: float = 0.0
    perdida_termica_ambiental_pct: float = 0.0
    litros_nocturnos: float = 0.0
    horas_nocturnas: float = 0.0
    pasos_extraccion_humedad_baja: int = 0
    fraccion_maxima_extraida: float = 0.0
    integridad_minima: float = 100.0
    recuperaciones_pct: List[float] = field(default_factory=list)
    tiempos_regeneracion_seg: List[float] = field(default_factory=list)
    pulsos_regenerados: int = 0
    pulsos_no_regenerados: int = 0
    temperaturas_pulso_c: List[float] = field(default_factory=list)
    tiempos_desprendimiento_seg: List[float] = field(default_factory=list)
    impedancias_tras_pulso_ohms: List[float] = field(default_factory=list)
    pulsos_omitidos_por_energia: int = 0
    impedancia_promedio: List[float] = field(default_factory=list)
    litros_acumulados: List[float] = field(default_factory=list)
    energia_acumulada: List[float] = field(default_factory=list)
    integridad_promedio: List[float] = field(default_factory=list)
    bitacora: List[EventoBitacora] = field(default_factory=list)

    @property
    def perdida_termica_pct(self) -> float:
        """Pérdida promedio de integridad por degradación térmica (pulso y ambiente)."""
        return self.perdida_termica_pulso_pct + self.perdida_termica_ambiental_pct


def _descontar_integridad(estado: _EstadoNodo, perdida: float) -> float:
    """Aplica una pérdida de integridad acotada en cero y devuelve la pérdida efectiva."""
    efectiva = min(estado.integridad, max(0.0, perdida))
    estado.integridad -= efectiva
    return efectiva


def _decidir_accion(
    neuro: bool,
    estado: _EstadoNodo,
    diag: DiagnosticoModo,
    nodo_id: str,
    minuto: int,
    humedad: float,
    t_matriz: float,
    impedancia_inicial: float,
    fraccion_temporizador: float,
    *,
    parametros: ParametrosModelo = PARAMETROS_BASE,
) -> Tuple[float, bool, float]:
    """Decide la fracción de extracción, si se ordena un pulso y su temperatura objetivo.

    En modo neuro-simbólico consulta el motor de reglas y registra en la
    bitácora cada cambio de regla; en modo temporizador aplica la
    programación fija con la fracción de extracción indicada.
    """
    if neuro:
        telemetria = TelemetryInput(
            nodo_id=nodo_id,
            impedancia_ohms=impedancia_inicial,
            temperatura_celsius=t_matriz,
            reserva_calor_pct=estado.reserva_wh / config.CAPACIDAD_RESERVA_WH * 100.0,
            humedad_relativa_pct=humedad,
            flujo_actual_ml_min=estado.flujo_ml_min,
            modo_operacion=ModoOperacion.NEURO_SIMBOLICO,
        )
        decision = evaluar_telemetria(
            telemetria, _INSTANTE_REFERENCIA + timedelta(minutes=minuto), parametros=parametros
        )
        if decision.regla_activada != estado.regla_previa:
            diag.bitacora.append(
                EventoBitacora(
                    minuto=minuto,
                    nodo_id=nodo_id,
                    regla_activada=decision.regla_activada,
                    motivo=decision.motivo,
                )
            )
            estado.regla_previa = decision.regla_activada
        fraccion = config.FRACCION_MAXIMA_EXTRACCION * decision.ajuste_caudal_pct / 100.0
        ordena_pulso = decision.pulso_termico_activo
        t_pulso = temperatura_alcanzada_pulso(t_matriz) if ordena_pulso else t_matriz
    else:
        fraccion = fraccion_temporizador
        ordena_pulso = minuto - estado.ultimo_pulso_min >= config.INTERVALO_PULSO_TEMPORIZADOR_MIN
        if ordena_pulso:
            estado.ultimo_pulso_min = minuto
        t_pulso = t_matriz + config.INCREMENTO_TERMICO_TEMPORIZADOR_C
    return fraccion, ordena_pulso, t_pulso


def _registrar_regeneracion(
    estado: _EstadoNodo,
    diag: DiagnosticoModo,
    t_pulso: float,
    sal_antes: float,
    impedancia_inicial: float,
    minuto: int,
    *,
    parametros: ParametrosModelo = PARAMETROS_BASE,
) -> None:
    """Registra el tiempo de regeneración de un pulso aplicado (ver `simular_modo`)."""
    # Un pulso previo no regenerado se cierra al iniciar el siguiente.
    if estado.pulso_no_regenerado_min is not None:
        diag.tiempos_regeneracion_seg.append((minuto - estado.pulso_no_regenerado_min) * 60.0)
        estado.pulso_no_regenerado_min = None
    if impedancia_inicial > config.UMBRAL_IMPEDANCIA_OHMS:
        objetivo_sal = (
            config.FACTOR_IMPEDANCIA_REGENERADA * config.IMPEDANCIA_NOMINAL_OHMS
            - config.IMPEDANCIA_NOMINAL_OHMS
            - estado.impedancia_polvo
        )
        segundos = modelo_fisico.tiempo_hasta_impedancia(t_pulso, sal_antes, objetivo_sal, parametros=parametros)
        if segundos is not None:
            diag.tiempos_regeneracion_seg.append(segundos)
            diag.pulsos_regenerados += 1
        else:
            estado.pulso_no_regenerado_min = minuto
            diag.pulsos_no_regenerados += 1


def _ejecutar_pulso(
    estado: _EstadoNodo,
    diag: DiagnosticoModo,
    t_pulso: float,
    t_matriz: float,
    impedancia_inicial: float,
    minuto: int,
    duracion_pulso_min: float,
    *,
    parametros: ParametrosModelo = PARAMETROS_BASE,
) -> Tuple[float, float]:
    """Aplica el pulso resistivo si la reserva alcanza.

    Devuelve la energía consumida por el pulso y la pérdida de integridad por
    sobretemperatura; ambas son cero si el pulso se omite por falta de energía.
    """
    energia = modelo_fisico.energia_pulso_wh(t_pulso - t_matriz)
    if energia <= estado.reserva_wh:
        sal_antes = estado.impedancia_sal
        estado.impedancia_sal = modelo_fisico.impedancia_sal_tras_pulso(t_pulso, sal_antes, parametros=parametros)
        estado.reserva_wh -= energia
        diag.energia_pulsos_wh += energia
        diag.pulsos += 1
        diag.temperaturas_pulso_c.append(t_pulso)
        _descontar_integridad(estado, config.FATIGA_POR_PULSO_PCT)
        perdida_pulso = 0.0
        if t_pulso > config.UMBRAL_TEMPERATURA_CORTE_C:
            perdida_pulso = _descontar_integridad(
                estado,
                (t_pulso - config.UMBRAL_TEMPERATURA_CORTE_C)
                * duracion_pulso_min
                * config.DEGRADACION_TERMICA_PCT_POR_C_MIN,
            )
        diag.recuperaciones_pct.append(
            min(100.0, modelo_fisico.conductancia_relativa(estado.impedancia) * 100.0)
        )
        diag.impedancias_tras_pulso_ohms.append(estado.impedancia)
        desprendimiento = modelo_fisico.tiempo_fraccion_remocion(t_pulso)
        if desprendimiento is not None:
            diag.tiempos_desprendimiento_seg.append(desprendimiento)
        _registrar_regeneracion(estado, diag, t_pulso, sal_antes, impedancia_inicial, minuto, parametros=parametros)
        return energia, perdida_pulso
    diag.pulsos_omitidos_por_energia += 1
    return 0.0, 0.0


def _registrar_violacion(
    estado: _EstadoNodo, diag: DiagnosticoModo, litros: float, humedad: float, fraccion: float
) -> None:
    """Cuenta un nuevo episodio de violación ecológica cuando comienza."""
    extrae = litros > 0
    if extrae:
        diag.fraccion_maxima_extraida = max(diag.fraccion_maxima_extraida, fraccion)
    humedad_baja = humedad < config.UMBRAL_HUMEDAD_ECOLOGICA_PCT
    if extrae and humedad_baja:
        diag.pasos_extraccion_humedad_baja += 1
    violacion = extrae and (
        humedad_baja or fraccion > config.FRACCION_MAXIMA_EXTRACCION + _TOLERANCIA
    )
    if violacion and not estado.en_violacion:
        diag.violaciones_ecologicas += 1
    estado.en_violacion = violacion


def _actualizar_impedancia(
    estado: _EstadoNodo, entorno: Entorno, i: int, n: int, litros: float, dt_h: float
) -> None:
    """Suma la incrustación salina del agua captada y acumula o limpia el polvo."""
    estado.impedancia_sal += entorno.incrustacion_ohm_por_l_m2[n] * litros / config.AREA_COLECTOR_M2
    if entorno.ensuciamiento_ohm_h[i] > 0:
        estado.impedancia_polvo += entorno.ensuciamiento_ohm_h[i] * dt_h
    else:
        estado.impedancia_polvo *= math.exp(-dt_h / config.CONSTANTE_LIMPIEZA_POLVO_H)


def _degradar_membrana(
    estado: _EstadoNodo, t_matriz: float, impedancia_operacion: float, paso_min: int, dt_h: float
) -> float:
    """Descuenta la degradación por calor ambiental y por cristalización.

    Devuelve la pérdida de integridad atribuible al calor ambiental.
    """
    perdida_ambiental = 0.0
    if t_matriz > config.UMBRAL_TEMPERATURA_CORTE_C:
        perdida_ambiental = _descontar_integridad(
            estado,
            (t_matriz - config.UMBRAL_TEMPERATURA_CORTE_C)
            * paso_min
            * config.DEGRADACION_TERMICA_PCT_POR_C_MIN,
        )
    if impedancia_operacion > config.UMBRAL_IMPEDANCIA_OHMS:
        _descontar_integridad(estado, config.DEGRADACION_CRISTALIZACION_PCT_H * dt_h)
    return perdida_ambiental


def _cerrar_regeneraciones_pendientes(nodos: List[_EstadoNodo], diag: DiagnosticoModo, fin_min: int) -> None:
    """Mide hasta el fin de la simulación los pulsos no regenerados sin pulso posterior."""
    for estado in nodos:
        if estado.pulso_no_regenerado_min is not None:
            diag.tiempos_regeneracion_seg.append(
                max(float(config.DURACION_PULSO_SEG), (fin_min - estado.pulso_no_regenerado_min) * 60.0)
            )


def simular_modo(
    entorno: Entorno,
    modo: ModoOperacion,
    fraccion_temporizador: float | None = None,
    *,
    parametros: ParametrosModelo = PARAMETROS_BASE,
) -> DiagnosticoModo:
    """Simula la red completa bajo una estrategia de control.

    En modo temporizador, `fraccion_temporizador` fija la fracción de
    extracción; si se omite, se usa FRACCION_EXTRACCION_TEMPORIZADOR. El
    temporizador conserva su programación (pulso cada intervalo fijo, sin corte
    térmico ni pausa ecológica) con cualquier fracción. `parametros` define la
    eficacia del pulso y el flujo de niebla sin modificar `backend.config`.

    En cada paso y para cada nodo: se decide la acción (motor de reglas o
    programación fija), se ejecuta el pulso si corresponde, se calcula el
    agua captada, se actualizan impedancia, integridad y reserva, y se
    registran las violaciones ecológicas por episodios.

    Tiempo de regeneración: por cada pulso aplicado con impedancia sobre el
    umbral, se mide el tiempo que tarda la impedancia en volver a
    <= FACTOR_IMPEDANCIA_REGENERADA * Z_nominal. Si el pulso no lo logra, el
    evento cuenta como no regenerado y su tiempo es la duración del pulso más
    el intervalo hasta el siguiente pulso del nodo, es decir, la diferencia
    entre ambos inicios; si no hay otro pulso, se mide hasta el fin de la
    simulación, con un mínimo de la duración del pulso.
    """
    neuro = modo == ModoOperacion.NEURO_SIMBOLICO
    fraccion_fija = config.FRACCION_EXTRACCION_TEMPORIZADOR if fraccion_temporizador is None else fraccion_temporizador
    nodos = [_EstadoNodo() for _ in range(entorno.numero_nodos)]
    diag = DiagnosticoModo(modo=modo)
    paso_min = entorno.paso_minutos
    dt_h = paso_min / 60.0
    consumo_base_w = config.CONSUMO_BASE_NEURO_W if neuro else config.CONSUMO_BASE_TEMPORIZADOR_W
    duracion_pulso_min = config.DURACION_PULSO_SEG / 60.0
    perdida_pulso_total = 0.0
    perdida_ambiental_total = 0.0

    for i in range(entorno.numero_pasos):
        minuto = entorno.minutos[i]
        hora = entorno.horas_locales[i]
        nocturno = _en_ventana(hora, config.HORA_INICIO_NOCHE, config.HORA_FIN_NOCHE)
        if nocturno:
            diag.horas_nocturnas += dt_h

        for n, estado in enumerate(nodos):
            nodo_id = f"NODO_{n + 1:02d}"
            humedad = entorno.humedad[i][n]
            t_matriz = entorno.temperatura_matriz[i][n]
            impedancia_inicial = estado.impedancia

            # Decisión de control.
            fraccion, ordena_pulso, t_pulso = _decidir_accion(
                neuro,
                estado,
                diag,
                nodo_id,
                minuto,
                humedad,
                t_matriz,
                impedancia_inicial,
                fraccion_fija,
                parametros=parametros,
            )

            # Ejecución del pulso resistivo.
            energia_paso = consumo_base_w * dt_h
            if ordena_pulso:
                energia_pulso, perdida_pulso = _ejecutar_pulso(
                    estado,
                    diag,
                    t_pulso,
                    t_matriz,
                    impedancia_inicial,
                    minuto,
                    duracion_pulso_min,
                    parametros=parametros,
                )
                energia_paso += energia_pulso
                perdida_pulso_total += perdida_pulso

            # Captación de agua con la impedancia posterior al pulso.
            impedancia_operacion = estado.impedancia
            litros = (
                modelo_fisico.flujo_niebla_disponible_l_m2_h(humedad, parametros=parametros)
                * entorno.factor_captacion[i]
                * fraccion
                * modelo_fisico.conductancia_relativa(impedancia_operacion)
                * estado.integridad
                / 100.0
                * config.AREA_COLECTOR_M2
                * dt_h
            )
            estado.flujo_ml_min = litros * 1000.0 / paso_min
            diag.litros_totales += litros
            if nocturno:
                diag.litros_nocturnos += litros

            # Violaciones ecológicas por episodios.
            _registrar_violacion(estado, diag, litros, humedad, fraccion)

            # Incrustación salina y ensuciamiento por polvo.
            _actualizar_impedancia(estado, entorno, i, n, litros, dt_h)

            # Degradación de la membrana.
            perdida_ambiental_total += _degradar_membrana(estado, t_matriz, impedancia_operacion, paso_min, dt_h)
            diag.integridad_minima = min(diag.integridad_minima, estado.integridad)

            # Balance de la reserva térmica.
            recarga = config.POTENCIA_RECARGA_SOLAR_W * entorno.radiacion[i] * dt_h
            estado.reserva_wh = max(
                0.0, min(config.CAPACIDAD_RESERVA_WH, estado.reserva_wh + recarga - consumo_base_w * dt_h)
            )
            diag.energia_total_wh += energia_paso

        diag.impedancia_promedio.append(sum(e.impedancia for e in nodos) / len(nodos))
        diag.litros_acumulados.append(diag.litros_totales)
        diag.energia_acumulada.append(diag.energia_total_wh)
        diag.integridad_promedio.append(sum(e.integridad for e in nodos) / len(nodos))

    # Los pulsos no regenerados sin pulso posterior se miden hasta el fin de la simulación.
    _cerrar_regeneraciones_pendientes(nodos, diag, entorno.numero_pasos * paso_min)

    diag.integridad_final_promedio = sum(e.integridad for e in nodos) / len(nodos)
    diag.perdida_termica_pulso_pct = perdida_pulso_total / len(nodos)
    diag.perdida_termica_ambiental_pct = perdida_ambiental_total / len(nodos)
    return diag


# ---------------------------------------------------------------------------
# Verificación de conjeturas
# ---------------------------------------------------------------------------
def _promedio(valores: List[float]) -> Optional[float]:
    """Promedio aritmético, o None si la lista está vacía."""
    return sum(valores) / len(valores) if valores else None


def _indicador(valor: Optional[float], umbral: float, operador: str) -> IndicadorVerificacion:
    """Construye un indicador comparando el valor con su umbral.

    Un valor nulo indica que la simulación no produjo datos para medirlo y
    se reporta como no cumplido.
    """
    if valor is None:
        cumple = False
    elif operador == ">=":
        cumple = valor >= umbral
    elif operador == "<":
        cumple = valor < umbral
    elif operador == "<=":
        cumple = valor <= umbral + _TOLERANCIA
    else:
        raise ValueError(f"Operador no soportado: {operador}")
    return IndicadorVerificacion(
        valor=None if valor is None else round(valor, 4),
        umbral=umbral,
        operador=operador,
        cumple=cumple,
    )


# Causa de no validación de los indicadores que dependen de la eficacia del pulso,
# un parámetro supuesto sin medición experimental. Los demás indicadores se
# atribuyen al desempeño del control, salvo el rendimiento nocturno.
_CAUSA_POR_INDICADOR = {
    "recuperacion_caudal_promedio_pct": CausaNoValidacion.DEPENDE_DE_PARAMETRO_SUPUESTO,
    "tiempo_regeneracion_promedio_seg": CausaNoValidacion.DEPENDE_DE_PARAMETRO_SUPUESTO,
}
_INDICADOR_RENDIMIENTO_NOCTURNO = "rendimiento_nocturno_l_m2_noche"


def _causa_indicador(
    nombre: str, indicador: IndicadorVerificacion, rendimiento_temporizador: float | None
) -> CausaNoValidacion:
    """Causa por la que un indicador no cumple su umbral.

    El rendimiento nocturno se atribuye al recurso atmosférico cuando el
    temporizador, sin restricciones de control, tampoco alcanza el umbral.
    """
    if indicador.valor is None:
        return CausaNoValidacion.SIN_DATOS
    if nombre == _INDICADOR_RENDIMIENTO_NOCTURNO:
        recurso_insuficiente = rendimiento_temporizador is not None and rendimiento_temporizador < indicador.umbral
        if recurso_insuficiente:
            return CausaNoValidacion.LIMITE_DEL_RECURSO_ATMOSFERICO
        return CausaNoValidacion.DESEMPENO_DEL_CONTROL
    return _CAUSA_POR_INDICADOR.get(nombre, CausaNoValidacion.DESEMPENO_DEL_CONTROL)


def _causas_no_validacion(
    indicadores: dict[str, IndicadorVerificacion], rendimiento_temporizador: float | None
) -> list[CausaNoValidacion]:
    """Causas de los indicadores que no cumplen, en su orden y sin repetir.

    Una conjetura validada no tiene indicadores incumplidos y devuelve una
    lista vacía.
    """
    causas: list[CausaNoValidacion] = []
    for nombre, indicador in indicadores.items():
        if indicador.cumple:
            continue
        causa = _causa_indicador(nombre, indicador, rendimiento_temporizador)
        if causa not in causas:
            causas.append(causa)
    return causas


def _informativos(valores: dict[str, float | None]) -> dict[str, float]:
    """Redondea a 4 decimales los indicadores informativos y omite los que no tienen datos."""
    return {clave: round(valor, 4) for clave, valor in valores.items() if valor is not None}


def _verificacion(
    indicadores: dict,
    informativos: Optional[dict] = None,
    rendimiento_temporizador: float | None = None,
) -> VerificacionConjetura:
    """Una conjetura se valida solo si todos sus indicadores cumplen.

    Los indicadores informativos y las causas de no validación se adjuntan
    como contexto y no intervienen en la validación.
    """
    return VerificacionConjetura(
        validada=all(i.cumple for i in indicadores.values()),
        indicadores=indicadores,
        indicadores_informativos=informativos or {},
        causas_no_validacion=_causas_no_validacion(indicadores, rendimiento_temporizador),
    )


def _reduccion_degradacion_pct(neuro: DiagnosticoModo, temporizador: DiagnosticoModo) -> float | None:
    """Reducción relativa de la degradación del neuro-simbólico frente al temporizador.

    (D_temp - D_neuro) / D_temp * 100, con D = 100 - integridad final. Devuelve
    None si el temporizador no acumuló degradación.
    """
    degradacion_temporizador = 100.0 - temporizador.integridad_final_promedio
    if degradacion_temporizador <= 0:
        return None
    degradacion_neuro = 100.0 - neuro.integridad_final_promedio
    return (degradacion_temporizador - degradacion_neuro) / degradacion_temporizador * 100.0


def rendimiento_nocturno_l_m2(diag: DiagnosticoModo, numero_nodos: int) -> Optional[float]:
    """Rendimiento nocturno en L/m² por noche.

    R = L_noche / (A * N) / (H_noche / 12), donde L_noche es el agua captada
    entre 18:00 y 06:00, A el área por nodo, N el número de nodos y H_noche las
    horas nocturnas simuladas. Si la duración no cubre una noche completa, el
    rendimiento se normaliza proporcionalmente a 12 horas; si cubre varias
    noches, el resultado es el promedio por noche. Devuelve None si no se
    simuló ninguna hora nocturna.
    """
    if diag.horas_nocturnas <= 0:
        return None
    area_total = config.AREA_COLECTOR_M2 * numero_nodos
    return diag.litros_nocturnos / area_total / (diag.horas_nocturnas / config.HORAS_POR_NOCHE)


def verificar_conjeturas(
    neuro: DiagnosticoModo, temporizador: DiagnosticoModo, numero_nodos: int
) -> DetalleVerificacion:
    """Evalúa los indicadores de la Matriz de Operacionalización.

    - Conjetura 1: recuperación promedio tras pulso >= 90 % y ahorro de
      energía en pulsos frente al temporizador >= 35 %, con
      ahorro = (E_temporizador - E_neuro) / E_temporizador * 100.
    - Conjetura 2: tiempo promedio de regeneración < 120 s, medido hasta
      Z <= 1.10 * Z_nominal (ver `simular_modo`), y pérdida de integridad por
      degradación térmica (pulso y ambiente) igual a 0 %. Se informan además,
      sin efecto en la validación, los pulsos regenerados y los pulsos totales
      del modo neuro-simbólico.
    - Conjetura 3: cero episodios de violación ecológica y rendimiento
      nocturno >= 12 L/m²/noche (ver `rendimiento_nocturno_l_m2`).

    Indicadores informativos, sin efecto en la validación: reducción de la
    degradación frente al temporizador (Conjetura 1, enunciado de vida útil);
    tiempo promedio hasta el 95 % de la remoción de cada pulso e impedancia
    promedio tras el pulso (Conjetura 2); y rendimiento nocturno del
    temporizador (Conjetura 3). Cada conjetura informa además las causas de
    los indicadores que no cumplen.
    """
    if temporizador.energia_pulsos_wh > 0:
        ahorro = (temporizador.energia_pulsos_wh - neuro.energia_pulsos_wh) / temporizador.energia_pulsos_wh * 100.0
    else:
        ahorro = None

    rendimiento = rendimiento_nocturno_l_m2(neuro, numero_nodos)
    rendimiento_temporizador = rendimiento_nocturno_l_m2(temporizador, numero_nodos)

    conjetura_1 = _verificacion(
        {
            "recuperacion_caudal_promedio_pct": _indicador(
                _promedio(neuro.recuperaciones_pct), config.RECUPERACION_MINIMA_PCT, ">="
            ),
            "ahorro_energia_pulsos_pct": _indicador(ahorro, config.AHORRO_ENERGIA_MINIMO_PCT, ">="),
        },
        informativos=_informativos({"reduccion_degradacion_pct": _reduccion_degradacion_pct(neuro, temporizador)}),
    )
    conjetura_2 = _verificacion(
        {
            "tiempo_regeneracion_promedio_seg": _indicador(
                _promedio(neuro.tiempos_regeneracion_seg), float(config.TIEMPO_REGENERACION_MAX_SEG), "<"
            ),
            "perdida_integridad_termica_pct": _indicador(
                neuro.perdida_termica_pct, config.PERDIDA_TERMICA_MAXIMA_PCT, "<="
            ),
        },
        informativos={
            "pulsos_regenerados": neuro.pulsos_regenerados,
            "pulsos_totales": neuro.pulsos,
            **_informativos(
                {
                    "tiempo_desprendimiento_t95_promedio_seg": _promedio(neuro.tiempos_desprendimiento_seg),
                    "impedancia_promedio_tras_pulso_ohms": _promedio(neuro.impedancias_tras_pulso_ohms),
                }
            ),
        },
    )
    conjetura_3 = _verificacion(
        {
            "violaciones_ecologicas": _indicador(
                float(neuro.violaciones_ecologicas), float(config.VIOLACIONES_ECOLOGICAS_MAXIMAS), "<="
            ),
            _INDICADOR_RENDIMIENTO_NOCTURNO: _indicador(
                rendimiento, config.RENDIMIENTO_MINIMO_L_M2_NOCHE, ">="
            ),
        },
        informativos=_informativos({"rendimiento_nocturno_temporizador_l_m2_noche": rendimiento_temporizador}),
        rendimiento_temporizador=rendimiento_temporizador,
    )
    return DetalleVerificacion(
        conjetura_1_eficiencia=conjetura_1,
        conjetura_2_autorreparacion=conjetura_2,
        conjetura_3_saber_territorial=conjetura_3,
    )


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def _resultado_modo(diag: DiagnosticoModo) -> ResultadoModo:
    """Resume el diagnóstico de un modo en el formato del PRD, más los indicadores de la pregunta de investigación."""
    recuperacion = _promedio(diag.recuperaciones_pct)
    return ResultadoModo(
        litros_totales_agua=round(diag.litros_totales, 3),
        pulsos_termicos_ejecutados=diag.pulsos,
        consumo_energia_wh=round(diag.energia_total_wh, 3),
        integridad_membrana_final_pct=round(diag.integridad_final_promedio, 4),
        violaciones_ecologicas=diag.violaciones_ecologicas,
        recuperacion_caudal_promedio_pct=None if recuperacion is None else round(recuperacion, 4),
        degradacion_acumulada_pct=round(100.0 - diag.integridad_final_promedio, 4),
    )


def ejecutar_simulacion_detallada(
    cfg: SimulationConfig, *, parametros: ParametrosModelo = PARAMETROS_BASE
) -> Tuple[Entorno, DiagnosticoModo, DiagnosticoModo]:
    """Ejecuta ambos modos sobre el mismo entorno y devuelve los diagnósticos completos."""
    entorno = generar_entorno(cfg)
    neuro = simular_modo(entorno, ModoOperacion.NEURO_SIMBOLICO, parametros=parametros)
    temporizador = simular_modo(entorno, ModoOperacion.TEMPORIZADOR_FIJO, parametros=parametros)
    return entorno, neuro, temporizador


def ejecutar_simulacion(cfg: SimulationConfig, *, parametros: ParametrosModelo = PARAMETROS_BASE) -> SimulationResult:
    """Ejecuta la simulación comparativa y arma la respuesta de la API."""
    entorno, neuro, temporizador = ejecutar_simulacion_detallada(cfg, parametros=parametros)
    detalle = verificar_conjeturas(neuro, temporizador, entorno.numero_nodos)
    # Referencia: el temporizador con el tope ecológico del modo neuro-simbólico separa el
    # efecto del tope del de la lógica de control. No se agrega a las series temporales.
    referencia = simular_modo(
        entorno,
        ModoOperacion.TEMPORIZADOR_FIJO,
        fraccion_temporizador=config.FRACCION_MAXIMA_EXTRACCION,
        parametros=parametros,
    )

    series = [
        PuntoSerieTemporal(
            minuto=entorno.minutos[i],
            humedad_relativa_pct=round(sum(entorno.humedad[i]) / entorno.numero_nodos, 2),
            temperatura_c=round(entorno.temperatura_ambiente[i], 2),
            impedancia_promedio_neuro_ohms=round(neuro.impedancia_promedio[i], 2),
            impedancia_promedio_temporizador_ohms=round(temporizador.impedancia_promedio[i], 2),
            litros_acumulados_neuro=round(neuro.litros_acumulados[i], 3),
            litros_acumulados_temporizador=round(temporizador.litros_acumulados[i], 3),
            energia_acumulada_neuro_wh=round(neuro.energia_acumulada[i], 3),
            energia_acumulada_temporizador_wh=round(temporizador.energia_acumulada[i], 3),
            integridad_promedio_neuro_pct=round(neuro.integridad_promedio[i], 4),
            integridad_promedio_temporizador_pct=round(temporizador.integridad_promedio[i], 4),
        )
        for i in range(entorno.numero_pasos)
    ]

    return SimulationResult(
        comparativa=ComparativaModos(
            modo_neuro_simbolico=_resultado_modo(neuro),
            modo_temporizador_fijo=_resultado_modo(temporizador),
            modo_temporizador_tope_ecologico=_resultado_modo(referencia),
        ),
        conjeturas_validadas=ConjeturasValidadas(
            conjetura_1_eficiencia=detalle.conjetura_1_eficiencia.validada,
            conjetura_2_autorreparacion=detalle.conjetura_2_autorreparacion.validada,
            conjetura_3_saber_territorial=detalle.conjetura_3_saber_territorial.validada,
        ),
        detalle_verificacion=detalle,
        series_temporales=series,
        bitacora=neuro.bitacora,
    )
