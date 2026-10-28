"""Simulador comparativo de la red de nodos de captación.

Ejecuta el mismo entorno, generado con una semilla fija, para dos estrategias
de control: el motor neuro-simbólico y un temporizador fijo sin sensores.
Los resultados y la verificación de las conjeturas se calculan a partir del
modelo; ningún indicador se fija de antemano (decisión D5).

La simulación arranca a las 18:00 hora local y avanza en pasos discretos de
`paso_minutos`. Las ecuaciones se documentan en `docs/modelo_simulacion.md`.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from backend import config, modelo_fisico
from backend.motor_reglas import evaluar_telemetria, temperatura_alcanzada_pulso
from backend.schemas import (
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


def _tasa_incrustacion_base(escenario: Escenario, tasa: TasaSalinizacion) -> float:
    """Ohm por litro captado por m² según el escenario y la tasa elegida."""
    if escenario == Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO:
        return config.INCRUSTACION_OHM_POR_L_M2["ALTA"] * config.MULTIPLICADOR_INCRUSTACION_SAL_Y_CALOR
    base = config.INCRUSTACION_OHM_POR_L_M2[tasa.value]
    if escenario == Escenario.INCRUSTACION_SALINA_RAPIDA:
        return base * config.MULTIPLICADOR_INCRUSTACION_RAPIDA
    return base


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

        humedad_base = cfg.humedad_ambiente_inicial_pct + config.AMPLITUD_HUMEDAD_PCT * (
            _ciclo_humedad(hora) - referencia_humedad
        )
        if escenario == Escenario.SEQUIA:
            humedad_base -= config.SEQUIA_REDUCCION_HUMEDAD_PCT

        temperatura = config.TEMPERATURA_MEDIA_C + config.AMPLITUD_TEMPERATURA_C * math.cos(
            2.0 * math.pi * (hora - config.HORA_MAXIMA_TEMPERATURA) / 24.0
        )
        if escenario == Escenario.TORMENTA_DE_SAL_Y_CALOR_EXTREMO:
            temperatura += config.CALOR_EXTREMO_INCREMENTO_C * sol

        sol_efectivo = sol * (config.TORMENTA_ARENA_FACTOR_RADIACION if tormenta_arena else 1.0)

        humedad_paso, matriz_paso = [], []
        for n in range(cfg.numero_nodos):
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
    inicio_regeneracion_min: Optional[int] = None

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
    temperaturas_pulso_c: List[float] = field(default_factory=list)
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


def simular_modo(entorno: Entorno, modo: ModoOperacion) -> DiagnosticoModo:
    """Simula la red completa bajo una estrategia de control.

    En cada paso y para cada nodo: se decide la acción (motor de reglas o
    programación fija), se ejecuta el pulso si corresponde, se calcula el
    agua captada, se actualizan impedancia, integridad y reserva, y se
    registran las violaciones ecológicas por episodios.
    """
    neuro = modo == ModoOperacion.NEURO_SIMBOLICO
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
                decision = evaluar_telemetria(telemetria, _INSTANTE_REFERENCIA + timedelta(minutes=minuto))
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
                fraccion = config.FRACCION_EXTRACCION_TEMPORIZADOR
                ordena_pulso = minuto - estado.ultimo_pulso_min >= config.INTERVALO_PULSO_TEMPORIZADOR_MIN
                if ordena_pulso:
                    estado.ultimo_pulso_min = minuto
                t_pulso = t_matriz + config.INCREMENTO_TERMICO_TEMPORIZADOR_C

            # Ejecución del pulso resistivo.
            energia_paso = consumo_base_w * dt_h
            if ordena_pulso:
                energia = modelo_fisico.energia_pulso_wh(t_pulso - t_matriz)
                if energia <= estado.reserva_wh:
                    sal_antes = estado.impedancia_sal
                    estado.impedancia_sal = modelo_fisico.impedancia_sal_tras_pulso(t_pulso, sal_antes)
                    estado.reserva_wh -= energia
                    energia_paso += energia
                    diag.energia_pulsos_wh += energia
                    diag.pulsos += 1
                    diag.temperaturas_pulso_c.append(t_pulso)
                    _descontar_integridad(estado, config.FATIGA_POR_PULSO_PCT)
                    if t_pulso > config.UMBRAL_TEMPERATURA_CORTE_C:
                        perdida_pulso_total += _descontar_integridad(
                            estado,
                            (t_pulso - config.UMBRAL_TEMPERATURA_CORTE_C)
                            * duracion_pulso_min
                            * config.DEGRADACION_TERMICA_PCT_POR_C_MIN,
                        )
                    diag.recuperaciones_pct.append(
                        min(100.0, modelo_fisico.conductancia_relativa(estado.impedancia) * 100.0)
                    )
                    if impedancia_inicial > config.UMBRAL_IMPEDANCIA_OHMS:
                        if estado.inicio_regeneracion_min is None:
                            estado.inicio_regeneracion_min = minuto
                        objetivo_sal = (
                            config.UMBRAL_IMPEDANCIA_OHMS - config.IMPEDANCIA_NOMINAL_OHMS - estado.impedancia_polvo
                        )
                        segundos = modelo_fisico.tiempo_hasta_impedancia(t_pulso, sal_antes, objetivo_sal)
                        if segundos is not None:
                            diag.tiempos_regeneracion_seg.append(
                                (minuto - estado.inicio_regeneracion_min) * 60.0 + segundos
                            )
                            estado.inicio_regeneracion_min = None
                else:
                    diag.pulsos_omitidos_por_energia += 1

            # Captación de agua con la impedancia posterior al pulso.
            impedancia_operacion = estado.impedancia
            litros = (
                modelo_fisico.flujo_niebla_disponible_l_m2_h(humedad)
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

            # Incrustación salina y ensuciamiento por polvo.
            estado.impedancia_sal += entorno.incrustacion_ohm_por_l_m2[n] * litros / config.AREA_COLECTOR_M2
            if entorno.ensuciamiento_ohm_h[i] > 0:
                estado.impedancia_polvo += entorno.ensuciamiento_ohm_h[i] * dt_h
            else:
                estado.impedancia_polvo *= math.exp(-dt_h / config.CONSTANTE_LIMPIEZA_POLVO_H)

            # Degradación de la membrana.
            if t_matriz > config.UMBRAL_TEMPERATURA_CORTE_C:
                perdida_ambiental_total += _descontar_integridad(
                    estado,
                    (t_matriz - config.UMBRAL_TEMPERATURA_CORTE_C)
                    * paso_min
                    * config.DEGRADACION_TERMICA_PCT_POR_C_MIN,
                )
            if impedancia_operacion > config.UMBRAL_IMPEDANCIA_OHMS:
                _descontar_integridad(estado, config.DEGRADACION_CRISTALIZACION_PCT_H * dt_h)
            diag.integridad_minima = min(diag.integridad_minima, estado.integridad)

            # Cierre de un episodio de regeneración sin pulso (limpieza del polvo).
            if estado.inicio_regeneracion_min is not None and estado.impedancia <= config.UMBRAL_IMPEDANCIA_OHMS:
                diag.tiempos_regeneracion_seg.append((minuto + paso_min - estado.inicio_regeneracion_min) * 60.0)
                estado.inicio_regeneracion_min = None

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

    # Los episodios abiertos al final se cuentan hasta el cierre de la simulación.
    fin_min = entorno.numero_pasos * paso_min
    for estado in nodos:
        if estado.inicio_regeneracion_min is not None:
            diag.tiempos_regeneracion_seg.append((fin_min - estado.inicio_regeneracion_min) * 60.0)

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


def _verificacion(indicadores: dict) -> VerificacionConjetura:
    """Una conjetura se valida solo si todos sus indicadores cumplen."""
    return VerificacionConjetura(validada=all(i.cumple for i in indicadores.values()), indicadores=indicadores)


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
    - Conjetura 2: tiempo promedio de regeneración < 120 s y pérdida de
      integridad por degradación térmica (pulso y ambiente) igual a 0 %.
    - Conjetura 3: cero episodios de violación ecológica y rendimiento
      nocturno >= 12 L/m²/noche (ver `rendimiento_nocturno_l_m2`).
    """
    if temporizador.energia_pulsos_wh > 0:
        ahorro = (temporizador.energia_pulsos_wh - neuro.energia_pulsos_wh) / temporizador.energia_pulsos_wh * 100.0
    else:
        ahorro = None

    rendimiento = rendimiento_nocturno_l_m2(neuro, numero_nodos)

    conjetura_1 = _verificacion(
        {
            "recuperacion_caudal_promedio_pct": _indicador(
                _promedio(neuro.recuperaciones_pct), config.RECUPERACION_MINIMA_PCT, ">="
            ),
            "ahorro_energia_pulsos_pct": _indicador(ahorro, config.AHORRO_ENERGIA_MINIMO_PCT, ">="),
        }
    )
    conjetura_2 = _verificacion(
        {
            "tiempo_regeneracion_promedio_seg": _indicador(
                _promedio(neuro.tiempos_regeneracion_seg), float(config.TIEMPO_REGENERACION_MAX_SEG), "<"
            ),
            "perdida_integridad_termica_pct": _indicador(
                neuro.perdida_termica_pct, config.PERDIDA_TERMICA_MAXIMA_PCT, "<="
            ),
        }
    )
    conjetura_3 = _verificacion(
        {
            "violaciones_ecologicas": _indicador(
                float(neuro.violaciones_ecologicas), float(config.VIOLACIONES_ECOLOGICAS_MAXIMAS), "<="
            ),
            "rendimiento_nocturno_l_m2_noche": _indicador(
                rendimiento, config.RENDIMIENTO_MINIMO_L_M2_NOCHE, ">="
            ),
        }
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
    """Resume el diagnóstico de un modo en el formato del PRD."""
    return ResultadoModo(
        litros_totales_agua=round(diag.litros_totales, 3),
        pulsos_termicos_ejecutados=diag.pulsos,
        consumo_energia_wh=round(diag.energia_total_wh, 3),
        integridad_membrana_final_pct=round(diag.integridad_final_promedio, 4),
        violaciones_ecologicas=diag.violaciones_ecologicas,
    )


def ejecutar_simulacion_detallada(cfg: SimulationConfig) -> Tuple[Entorno, DiagnosticoModo, DiagnosticoModo]:
    """Ejecuta ambos modos sobre el mismo entorno y devuelve los diagnósticos completos."""
    entorno = generar_entorno(cfg)
    neuro = simular_modo(entorno, ModoOperacion.NEURO_SIMBOLICO)
    temporizador = simular_modo(entorno, ModoOperacion.TEMPORIZADOR_FIJO)
    return entorno, neuro, temporizador


def ejecutar_simulacion(cfg: SimulationConfig) -> SimulationResult:
    """Ejecuta la simulación comparativa y arma la respuesta de la API."""
    entorno, neuro, temporizador = ejecutar_simulacion_detallada(cfg)
    detalle = verificar_conjeturas(neuro, temporizador, entorno.numero_nodos)

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
