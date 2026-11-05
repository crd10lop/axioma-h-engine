"""Análisis de robustez del modelo: barrido de salinidad, robustez de la respuesta y del desgaste,
sensibilidad, calibración, incertidumbre y dimensionamiento del captador.

Ningún análisis modifica `backend.config`. Cada análisis construye con
`parametros_desde` una instancia inmutable de `ParametrosModelo` por cada
valor, de modo que solicitudes simultáneas en el servidor no comparten estado.
Las corridas individuales se guardan en una caché LRU cuyas claves son valores
inmutables (enumerados, números y `ParametrosModelo`).
"""

import math
import statistics
from functools import lru_cache

from backend import config
from backend.impacto import dimensionar, impacto_comunitario
from backend.modelo_fisico import ParametrosModelo, parametros_desde
from backend.schemas import (
    BarridoConfig,
    BarridoResultado,
    CalibracionConfig,
    CalibracionResultado,
    CombinacionDesgaste,
    CombinacionRobustez,
    ConjeturasValidadas,
    CruceRecuperacion,
    DetalleVerificacion,
    DimensionamientoConfig,
    DimensionamientoResultado,
    DimensionPorFlujo,
    EntornoImpacto,
    Escenario,
    EstadoCruce,
    EstandarConsumo,
    ImpactoEntornosConfig,
    ImpactoEntornosResultado,
    IncertidumbreConfig,
    IncertidumbreResultado,
    MuestraIncertidumbre,
    ParametroSensible,
    PerfilSitio,
    PuntoBarrido,
    PuntoSensibilidad,
    ResumenDistribucion,
    RobustezConfig,
    RobustezDesgasteConfig,
    RobustezDesgasteResultado,
    RobustezResultado,
    SensibilidadConfig,
    SensibilidadResultado,
    SimulationConfig,
    TasaSalinizacion,
    ZonaIncrustacion,
)
from backend.simulador import (
    DiagnosticoModo,
    crear_generador,
    ejecutar_simulacion_detallada,
    tasa_incrustacion_base,
    verificar_conjeturas,
)

# Combinaciones del barrido: forman un gradiente de carga salina de 20 a 240 Ohm por L/m².
ESCENARIOS_BARRIDO = (Escenario.DIA_NORMAL, Escenario.INCRUSTACION_SALINA_RAPIDA)
TASAS_BARRIDO = (TasaSalinizacion.BAJA, TasaSalinizacion.MEDIA, TasaSalinizacion.ALTA)

# Campo de ParametrosModelo que corresponde a cada parámetro sensible.
CAMPO_PARAMETRO = {
    ParametroSensible.EFICACIA_MAXIMA_PULSO: "eficacia_maxima_pulso",
    ParametroSensible.FLUJO_NIEBLA_MAXIMO: "flujo_niebla_maximo_l_m2_h",
}

# Flujos de niebla de referencia (L/m²/h): el supuesto del modelo y los dos extremos de la calibración.
FLUJOS_REFERENCIA = (
    ("SUPUESTO", config.FLUJO_NIEBLA_MAXIMO_L_M2_H),
    ("CALIBRADO_MAX", config.FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H),
    ("CALIBRADO_MIN", config.FLUJO_NIEBLA_CALIBRADO_MIN_L_M2_H),
)
# Eficacias del pulso de la grilla de robustez: el rango supuesto y el valor por defecto.
EFICACIAS_ROBUSTEZ = (config.EFICACIA_PULSO_RANGO_MIN, config.EFICACIA_MAXIMA_PULSO, config.EFICACIA_PULSO_RANGO_MAX)
# Flujos de la robustez del desgaste: el supuesto del modelo y el extremo superior de la calibración.
FLUJOS_DESGASTE = (config.FLUJO_NIEBLA_MAXIMO_L_M2_H, config.FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H)

_TAMANO_CACHE = 256
_DECIMALES = 4
_TOLERANCIA = 1e-9


# ---------------------------------------------------------------------------
# Barrido de salinidad
# ---------------------------------------------------------------------------
@lru_cache(maxsize=_TAMANO_CACHE)
def _metricas_corrida(
    escenario: Escenario,
    tasa: TasaSalinizacion,
    humedad: float,
    duracion_horas: int,
    numero_nodos: int,
    semilla: int,
    parametros: ParametrosModelo,
) -> tuple[float | None, float | None, float, float, float, int]:
    """Recuperación, degradación, rendimiento y pulsos de una corrida con los parámetros dados.

    Devuelve una tupla inmutable (recuperación neuro, recuperación temporizador,
    degradación neuro, degradación temporizador, rendimiento neuro en
    L/m²/día, pulsos neuro). La recuperación es nula si el modo no ejecutó
    pulsos.
    """
    cfg = SimulationConfig(
        duracion_horas=duracion_horas,
        escenario=escenario,
        humedad_ambiente_inicial_pct=humedad,
        tasa_salinizacion=tasa,
        numero_nodos=numero_nodos,
        semilla=semilla,
    )
    _, neuro, temporizador = ejecutar_simulacion_detallada(cfg, parametros=parametros)
    return (
        _media(neuro.recuperaciones_pct),
        _media(temporizador.recuperaciones_pct),
        100.0 - neuro.integridad_final_promedio,
        100.0 - temporizador.integridad_final_promedio,
        impacto_comunitario(neuro.litros_totales, duracion_horas, numero_nodos).rendimiento_l_m2_dia,
        neuro.pulsos,
    )


def _media(valores: list[float]) -> float | None:
    """Media aritmética, o None si no hay valores."""
    return statistics.fmean(valores) if valores else None


def _estadisticos(valores: list[float | None]) -> tuple[float | None, float | None]:
    """Media y desviación estándar muestral de los valores con datos.

    Con un solo dato la desviación es 0.0; sin datos, ambas son None.
    """
    datos = [valor for valor in valores if valor is not None]
    if not datos:
        return None, None
    desviacion = statistics.stdev(datos) if len(datos) >= 2 else 0.0
    return round(statistics.fmean(datos), _DECIMALES), round(desviacion, _DECIMALES)


def _reduccion_desgaste(degradacion_neuro: float | None, degradacion_temporizador: float | None) -> float | None:
    """(D_temp - D_neuro) / D_temp * 100, o None si el temporizador no se degrada."""
    if degradacion_neuro is None or degradacion_temporizador is None or degradacion_temporizador <= 0:
        return None
    return round((degradacion_temporizador - degradacion_neuro) / degradacion_temporizador * 100.0, _DECIMALES)


def _diferencia(minuendo: float | None, sustraendo: float | None) -> float | None:
    """minuendo - sustraendo redondeado a 4 decimales, o None si falta alguno."""
    if minuendo is None or sustraendo is None:
        return None
    return round(minuendo - sustraendo, _DECIMALES)


def _punto_barrido(
    cfg: BarridoConfig, escenario: Escenario, tasa: TasaSalinizacion, parametros: ParametrosModelo
) -> PuntoBarrido:
    """Agrega las corridas de todas las semillas para una combinación de escenario y tasa.

    La incrustación diaria de cada corrida es la carga salina por el
    rendimiento del neuro-simbólico (Ohm/día); la ventaja en recuperación es
    la media del neuro-simbólico menos la del temporizador.
    """
    carga = tasa_incrustacion_base(escenario, tasa)
    corridas = [
        _metricas_corrida(
            escenario,
            tasa,
            cfg.humedad_ambiente_inicial_pct,
            cfg.duracion_horas,
            cfg.numero_nodos,
            semilla,
            parametros,
        )
        for semilla in cfg.semillas
    ]
    rec_neuro, rec_temp, deg_neuro, deg_temp, rendimientos, pulsos = (list(columna) for columna in zip(*corridas))
    recuperacion_neuro = _estadisticos(rec_neuro)
    recuperacion_temporizador = _estadisticos(rec_temp)
    degradacion_neuro = _estadisticos(deg_neuro)
    degradacion_temporizador = _estadisticos(deg_temp)
    return PuntoBarrido(
        escenario=escenario,
        tasa_salinizacion=tasa,
        carga_salina_ohm_l_m2=carga,
        n_semillas=len(cfg.semillas),
        recuperacion_neuro_media=recuperacion_neuro[0],
        recuperacion_neuro_desv=recuperacion_neuro[1],
        recuperacion_temporizador_media=recuperacion_temporizador[0],
        recuperacion_temporizador_desv=recuperacion_temporizador[1],
        degradacion_neuro_media=degradacion_neuro[0],
        degradacion_neuro_desv=degradacion_neuro[1],
        degradacion_temporizador_media=degradacion_temporizador[0],
        degradacion_temporizador_desv=degradacion_temporizador[1],
        reduccion_desgaste_pct=_reduccion_desgaste(degradacion_neuro[0], degradacion_temporizador[0]),
        rendimiento_neuro_l_m2_dia_media=_estadisticos(rendimientos)[0],
        incrustacion_diaria_ohm_media=_estadisticos([carga * rendimiento for rendimiento in rendimientos])[0],
        ventaja_recuperacion_pts=_diferencia(recuperacion_neuro[0], recuperacion_temporizador[0]),
        pulsos_neuro_media=_estadisticos([float(cantidad) for cantidad in pulsos])[0],
    )


def _neuro_supera(ventaja: float) -> bool:
    """Indica si la ventaja en recuperación es positiva; una ventaja nula no cuenta como superioridad."""
    return ventaja > 0 and not math.isclose(ventaja, 0.0, abs_tol=_TOLERANCIA)


def _interpolar_cruce(
    estado: EstadoCruce, anterior: tuple[float, float, float], siguiente: tuple[float, float, float]
) -> CruceRecuperacion:
    """Interpola linealmente la incrustación diaria y la carga salina donde la ventaja vale 0.

    Cada punto es (incrustación diaria, ventaja, carga salina), y el anterior
    tiene la menor incrustación. Las ventajas de los dos puntos tienen signos
    distintos, por lo que su diferencia no es nula. Se informan además los dos
    puntos y su separación, que acota dónde puede estar el cruce real.
    """
    incrustacion_0, ventaja_0, carga_0 = anterior
    incrustacion_1, ventaja_1, carga_1 = siguiente
    fraccion = ventaja_0 / (ventaja_0 - ventaja_1)
    return CruceRecuperacion(
        estado=estado,
        incrustacion_diaria_ohm=round(incrustacion_0 + fraccion * (incrustacion_1 - incrustacion_0), _DECIMALES),
        carga_salina_ohm_l_m2=round(carga_0 + fraccion * (carga_1 - carga_0), _DECIMALES),
        incrustacion_inferior_ohm=round(incrustacion_0, _DECIMALES),
        incrustacion_superior_ohm=round(incrustacion_1, _DECIMALES),
        separacion_ohm=round(incrustacion_1 - incrustacion_0, _DECIMALES),
    )


def _cruce(puntos: list[PuntoBarrido]) -> CruceRecuperacion:
    """Incrustación diaria a partir de la cual el neuro-simbólico supera al temporizador en recuperación.

    Toma los puntos con ventaja e incrustación diaria no nulas, ordenados por
    incrustación diaria. Con menos de dos, SIN_DATOS. Si la ventaja es positiva
    en todos, SIN_CRUCE_NEURO_SUPERIOR; si no lo es en ninguno,
    SIN_CRUCE_NEURO_INFERIOR. En otro caso interpola el primer par consecutivo
    que pasa de ventaja <= 0 a > 0 (INTERPOLADO) o, si no hay ninguno, el
    primero que pasa de > 0 a <= 0 (CRUCE_DESCENDENTE).
    """
    datos = sorted(
        (punto.incrustacion_diaria_ohm_media, punto.ventaja_recuperacion_pts, punto.carga_salina_ohm_l_m2)
        for punto in puntos
        if punto.incrustacion_diaria_ohm_media is not None and punto.ventaja_recuperacion_pts is not None
    )
    if len(datos) < 2:
        return CruceRecuperacion(estado=EstadoCruce.SIN_DATOS)
    supera = [_neuro_supera(ventaja) for _, ventaja, _ in datos]
    if all(supera):
        return CruceRecuperacion(estado=EstadoCruce.SIN_CRUCE_NEURO_SUPERIOR)
    if not any(supera):
        return CruceRecuperacion(estado=EstadoCruce.SIN_CRUCE_NEURO_INFERIOR)
    pares = list(zip(range(len(datos) - 1), supera, supera[1:]))
    ascendente = next((indice for indice, previo, actual in pares if actual and not previo), None)
    if ascendente is not None:
        return _interpolar_cruce(EstadoCruce.INTERPOLADO, datos[ascendente], datos[ascendente + 1])
    # La ventaja cambia de signo y nunca pasa de <= 0 a > 0: hay al menos un paso de > 0 a <= 0.
    descendente = next(indice for indice, previo, actual in pares if previo and not actual)
    return _interpolar_cruce(EstadoCruce.CRUCE_DESCENDENTE, datos[descendente], datos[descendente + 1])


def ejecutar_barrido(cfg: BarridoConfig, *, parametros: ParametrosModelo | None = None) -> BarridoResultado:
    """Barrido de salinidad: DIA_NORMAL e INCRUSTACION_SALINA_RAPIDA con tasas BAJA, MEDIA y ALTA.

    Cada combinación se simula una vez por semilla con el flujo de niebla y la
    eficacia del pulso de la configuración (los de `backend/config.py` si son
    nulos), y se reportan la media y la desviación estándar muestral de la
    recuperación tras pulso y de la degradación acumulada de ambos modos, junto
    con la incrustación diaria y la ventaja en recuperación. Los puntos se
    ordenan por carga salina creciente y se informa el cruce de la ventaja.
    Con `parametros` explícitos se usan esos en lugar de los de la
    configuración; así la robustez del desgaste varía la fatiga y la
    degradación térmica, que no son campos de la API del barrido.
    """
    if parametros is None:
        parametros = parametros_desde(cfg.flujo_niebla_maximo_l_m2_h, cfg.eficacia_maxima_pulso)
    puntos = [
        _punto_barrido(cfg, escenario, tasa, parametros)
        for escenario in ESCENARIOS_BARRIDO
        for tasa in TASAS_BARRIDO
    ]
    return BarridoResultado(
        puntos=sorted(puntos, key=lambda punto: punto.carga_salina_ohm_l_m2),
        flujo_niebla_maximo_l_m2_h=parametros.flujo_niebla_maximo_l_m2_h,
        eficacia_maxima_pulso=parametros.eficacia_maxima_pulso,
        cruce=_cruce(puntos),
    )


# ---------------------------------------------------------------------------
# Robustez de la respuesta frente a los parámetros supuestos
# ---------------------------------------------------------------------------
def _config_barrido(cfg: RobustezConfig, flujo: float, eficacia: float | None = None) -> BarridoConfig:
    """Barrido con las condiciones de corrida de la robustez y el flujo y la eficacia dados."""
    return BarridoConfig(
        humedad_ambiente_inicial_pct=cfg.humedad_ambiente_inicial_pct,
        duracion_horas=cfg.duracion_horas,
        numero_nodos=cfg.numero_nodos,
        semillas=cfg.semillas,
        flujo_niebla_maximo_l_m2_h=flujo,
        eficacia_maxima_pulso=eficacia,
    )


def _combinacion_robustez(cfg: RobustezConfig, flujo: float, eficacia: float) -> CombinacionRobustez:
    """Barrido de salinidad con un flujo de niebla y una eficacia del pulso de la grilla."""
    barrido = ejecutar_barrido(_config_barrido(cfg, flujo, eficacia))
    return CombinacionRobustez(flujo_niebla_maximo_l_m2_h=flujo, eficacia_maxima_pulso=eficacia, barrido=barrido)


def _extremos(valores: list[float]) -> tuple[float | None, float | None]:
    """Mínimo y máximo de los valores, o (None, None) si no hay ninguno."""
    if not valores:
        return None, None
    return min(valores), max(valores)


def ejecutar_robustez(cfg: RobustezConfig) -> RobustezResultado:
    """Repite el barrido de salinidad en la grilla de 3 flujos de niebla por 3 eficacias del pulso.

    Los flujos son el supuesto del modelo y los extremos de la calibración
    contra la literatura; las eficacias, el rango supuesto y el valor por
    defecto. Resume el rango de la reducción del desgaste entre todos los
    puntos, el número de combinaciones con cruce INTERPOLADO y el rango de la
    incrustación diaria de esos cruces. No modifica `backend.config`.
    """
    combinaciones = [
        _combinacion_robustez(cfg, flujo, eficacia)
        for _, flujo in FLUJOS_REFERENCIA
        for eficacia in EFICACIAS_ROBUSTEZ
    ]
    reducciones = [
        punto.reduccion_desgaste_pct
        for combinacion in combinaciones
        for punto in combinacion.barrido.puntos
        if punto.reduccion_desgaste_pct is not None
    ]
    cruces = [
        combinacion.barrido.cruce.incrustacion_diaria_ohm
        for combinacion in combinaciones
        if combinacion.barrido.cruce.estado == EstadoCruce.INTERPOLADO
    ]
    reduccion_min, reduccion_max = _extremos(reducciones)
    cruce_min, cruce_max = _extremos(cruces)
    return RobustezResultado(
        combinaciones=combinaciones,
        reduccion_desgaste_min_pct=reduccion_min,
        reduccion_desgaste_max_pct=reduccion_max,
        combinaciones_con_cruce=len(cruces),
        incrustacion_diaria_cruce_min_ohm=cruce_min,
        incrustacion_diaria_cruce_max_ohm=cruce_max,
    )


# ---------------------------------------------------------------------------
# Robustez del desgaste frente a la fatiga y la degradación térmica
# ---------------------------------------------------------------------------
def _combinacion_desgaste(
    cfg: RobustezDesgasteConfig, flujo: float, fatiga: float, degradacion: float
) -> CombinacionDesgaste:
    """Barrido con un flujo, una fatiga por pulso y una degradación térmica, resumido en su reducción del desgaste.

    La eficacia del pulso es la de `backend/config.py`. Un punto cuenta como de
    menor desgaste si su reducción es positiva; un punto sin reducción (el
    temporizador no se degrada) no cuenta.
    """
    parametros = parametros_desde(flujo, fatiga_por_pulso_pct=fatiga, degradacion_termica_pct_por_c_min=degradacion)
    barrido = ejecutar_barrido(_config_barrido(cfg, flujo), parametros=parametros)
    reducciones = [punto.reduccion_desgaste_pct for punto in barrido.puntos if punto.reduccion_desgaste_pct is not None]
    reduccion_min, reduccion_max = _extremos(reducciones)
    return CombinacionDesgaste(
        flujo_niebla_maximo_l_m2_h=flujo,
        fatiga_por_pulso_pct=fatiga,
        degradacion_termica_pct_por_c_min=degradacion,
        reduccion_desgaste_min_pct=reduccion_min,
        reduccion_desgaste_max_pct=reduccion_max,
        puntos_con_menor_desgaste=sum(1 for reduccion in reducciones if _neuro_supera(reduccion)),
        puntos_totales=len(barrido.puntos),
    )


def ejecutar_robustez_desgaste(cfg: RobustezDesgasteConfig) -> RobustezDesgasteResultado:
    """Repite el barrido de salinidad con 2 flujos por 3 fatigas por pulso por 3 degradaciones térmicas.

    Los flujos son el supuesto del modelo y el extremo superior de la
    calibración; la fatiga y la degradación térmica toman la mitad, el valor
    supuesto y el doble. Resume el rango de la reducción del desgaste entre
    todos los puntos y cuenta las combinaciones en que el control basado en
    reglas se degrada menos en los seis puntos. No modifica `backend.config`.
    """
    combinaciones = [
        _combinacion_desgaste(cfg, flujo, fatiga, degradacion)
        for flujo in FLUJOS_DESGASTE
        for fatiga in config.FATIGAS_ROBUSTEZ_PCT
        for degradacion in config.DEGRADACIONES_TERMICAS_ROBUSTEZ
    ]
    extremos = [
        valor
        for combinacion in combinaciones
        for valor in (combinacion.reduccion_desgaste_min_pct, combinacion.reduccion_desgaste_max_pct)
        if valor is not None
    ]
    reduccion_min, reduccion_max = _extremos(extremos)
    return RobustezDesgasteResultado(
        combinaciones=combinaciones,
        reduccion_desgaste_min_pct=reduccion_min,
        reduccion_desgaste_max_pct=reduccion_max,
        combinaciones_con_menor_desgaste_en_todos_los_puntos=sum(
            1 for combinacion in combinaciones if combinacion.puntos_con_menor_desgaste == combinacion.puntos_totales
        ),
    )


# ---------------------------------------------------------------------------
# Perfiles de sitio de referencia
# ---------------------------------------------------------------------------
def perfiles_sitio() -> list[PerfilSitio]:
    """Perfiles de Cabo de la Vela con el flujo supuesto y con los dos extremos de la calibración.

    Solo cambia el flujo de niebla; la temperatura y las amplitudes son las de
    `backend/config.py`. No se incluyen otros sitios porque el proyecto no
    tiene datos climáticos con fuente para ellos.
    """
    nombre_base = PerfilSitio().nombre
    return [
        PerfilSitio(
            nombre=nombre_base if origen == "SUPUESTO" else f"{nombre_base}_{origen}",
            flujo_niebla_maximo_l_m2_h=flujo,
        )
        for origen, flujo in FLUJOS_REFERENCIA
    ]


# ---------------------------------------------------------------------------
# Sensibilidad a parámetros supuestos
# ---------------------------------------------------------------------------
@lru_cache(maxsize=_TAMANO_CACHE)
def _corrida_sensibilidad(
    escenario: Escenario,
    humedad: float,
    tasa: TasaSalinizacion,
    duracion_horas: int,
    semilla: int,
    parametros: ParametrosModelo,
) -> tuple[bool, bool, bool, float | None, float | None, float | None, float]:
    """Estado de las conjeturas e indicadores principales de una corrida con los parámetros dados.

    Devuelve una tupla inmutable (C1, C2, C3, recuperación, tiempo de
    regeneración, rendimiento nocturno, litros neuro-simbólicos).
    """
    detalle, neuro, _, _ = _simular_con_parametros(escenario, humedad, tasa, duracion_horas, semilla, parametros)
    c1 = detalle.conjetura_1_eficiencia
    c2 = detalle.conjetura_2_autorreparacion
    c3 = detalle.conjetura_3_saber_territorial
    return (
        c1.validada,
        c2.validada,
        c3.validada,
        c1.indicadores["recuperacion_caudal_promedio_pct"].valor,
        c2.indicadores["tiempo_regeneracion_promedio_seg"].valor,
        c3.indicadores["rendimiento_nocturno_l_m2_noche"].valor,
        round(neuro.litros_totales, 3),
    )


def _simular_con_parametros(
    escenario: Escenario,
    humedad: float,
    tasa: TasaSalinizacion,
    duracion_horas: int,
    semilla: int,
    parametros: ParametrosModelo,
    sitio: PerfilSitio | None = None,
) -> tuple[DetalleVerificacion, DiagnosticoModo, DiagnosticoModo, int]:
    """Simula una corrida con 8 nodos y los parámetros dados, y verifica las conjeturas.

    Con `sitio`, el entorno usa su temperatura y sus amplitudes; sin él, las
    de Cabo de la Vela. Devuelve el detalle de verificación, los diagnósticos
    del modo neuro-simbólico y del temporizador, y el número de nodos.
    """
    cfg = SimulationConfig(
        duracion_horas=duracion_horas,
        escenario=escenario,
        humedad_ambiente_inicial_pct=humedad,
        tasa_salinizacion=tasa,
        semilla=semilla,
        sitio=sitio,
    )
    entorno, neuro, temporizador = ejecutar_simulacion_detallada(cfg, parametros=parametros)
    return verificar_conjeturas(neuro, temporizador, entorno.numero_nodos), neuro, temporizador, entorno.numero_nodos


def _punto_sensibilidad(cfg: SensibilidadConfig, valor: float) -> PuntoSensibilidad:
    """Simula un valor del parámetro sensible sin modificar la configuración global."""
    parametros = parametros_desde(**{CAMPO_PARAMETRO[cfg.parametro]: valor})
    c1, c2, c3, recuperacion, regeneracion, rendimiento, litros = _corrida_sensibilidad(
        cfg.escenario,
        cfg.humedad_ambiente_inicial_pct,
        cfg.tasa_salinizacion,
        cfg.duracion_horas,
        cfg.semilla,
        parametros,
    )
    return PuntoSensibilidad(
        valor=valor,
        conjeturas_validadas=ConjeturasValidadas(
            conjetura_1_eficiencia=c1,
            conjetura_2_autorreparacion=c2,
            conjetura_3_saber_territorial=c3,
        ),
        recuperacion_caudal_promedio_pct=recuperacion,
        tiempo_regeneracion_promedio_seg=regeneracion,
        rendimiento_nocturno_l_m2_noche=rendimiento,
        litros_neuro=litros,
    )


def ejecutar_sensibilidad(cfg: SensibilidadConfig) -> SensibilidadResultado:
    """Repite la simulación con cada valor del parámetro elegido y los demás parámetros base."""
    return SensibilidadResultado(
        parametro=cfg.parametro,
        puntos=[_punto_sensibilidad(cfg, valor) for valor in cfg.valores],
    )


# ---------------------------------------------------------------------------
# Calibración inversa del flujo de niebla
# ---------------------------------------------------------------------------
# Intervalo de búsqueda del flujo (L/m²/h): el extremo superior es el valor por defecto del modelo.
FLUJO_BUSQUEDA_MIN_L_M2_H = 0.1
FLUJO_BUSQUEDA_MAX_L_M2_H = 6.0
# Condiciones fijas de la calibración: tasa ALTA y 24 h, como las corridas de referencia.
TASA_CALIBRACION = TasaSalinizacion.ALTA
DURACION_CALIBRACION_H = 24
_MAXIMO_ITERACIONES = 60


@lru_cache(maxsize=_TAMANO_CACHE)
def _rendimiento_neuro(
    escenario: Escenario, humedad: float, semilla: int, flujo: float, clima: tuple[float, float, float] | None = None
) -> float:
    """Rendimiento del modo neuro-simbólico en L/m²/día con el flujo de niebla dado y los demás parámetros base.

    `clima` es la temperatura media y las amplitudes térmica y de humedad del
    sitio, en una tupla inmutable que sirve de clave de la caché; con None se
    usa el clima de Cabo de la Vela.
    """
    parametros = parametros_desde(flujo_niebla_maximo_l_m2_h=flujo)
    sitio = None
    if clima is not None:
        temperatura, amplitud_temperatura, amplitud_humedad = clima
        sitio = PerfilSitio(
            flujo_niebla_maximo_l_m2_h=flujo,
            temperatura_media_c=temperatura,
            amplitud_temperatura_c=amplitud_temperatura,
            amplitud_humedad_pct=amplitud_humedad,
        )
    _, neuro, _, nodos = _simular_con_parametros(
        escenario, humedad, TASA_CALIBRACION, DURACION_CALIBRACION_H, semilla, parametros, sitio
    )
    return impacto_comunitario(neuro.litros_totales, DURACION_CALIBRACION_H, nodos).rendimiento_l_m2_dia


def _clima(sitio: PerfilSitio | None) -> tuple[float, float, float] | None:
    """Temperatura media y amplitudes del sitio como tupla inmutable, o None si no hay sitio."""
    if sitio is None:
        return None
    return sitio.temperatura_media_c, sitio.amplitud_temperatura_c, sitio.amplitud_humedad_pct


def calibrar_flujo_niebla(
    rendimiento_objetivo_l_m2_dia: float,
    *,
    escenario: Escenario = Escenario.DIA_NORMAL,
    humedad_pct: float = 85.0,
    semilla: int = 42,
    tolerancia: float = 0.01,
    sitio: PerfilSitio | None = None,
) -> float:
    """Flujo máximo de niebla con el que el neuro-simbólico alcanza el rendimiento objetivo.

    Bisección sobre [0.1, 6.0] L/m²/h con una corrida de 24 h y tasa ALTA por
    cada flujo evaluado; el rendimiento crece con el flujo. Se detiene cuando
    el intervalo mide menos que la tolerancia y devuelve su punto medio,
    redondeado a 4 decimales. Con `sitio`, cada corrida usa su temperatura
    media y sus amplitudes con el flujo evaluado; sin él, el clima de Cabo de
    la Vela. No modifica `backend.config`: cada corrida usa una copia de
    `ParametrosModelo`. Lanza ValueError si la tolerancia no es positiva o si
    el objetivo no está entre los rendimientos de los extremos.
    """
    if tolerancia <= 0:
        raise ValueError(f"La tolerancia debe ser positiva: {tolerancia}")
    clima = _clima(sitio)
    inferior, superior = FLUJO_BUSQUEDA_MIN_L_M2_H, FLUJO_BUSQUEDA_MAX_L_M2_H
    alcanzable_min = _rendimiento_neuro(escenario, humedad_pct, semilla, inferior, clima)
    alcanzable_max = _rendimiento_neuro(escenario, humedad_pct, semilla, superior, clima)
    if not alcanzable_min <= rendimiento_objetivo_l_m2_dia <= alcanzable_max:
        raise ValueError(
            f"El rendimiento objetivo {rendimiento_objetivo_l_m2_dia} L/m²/día no está en el intervalo "
            f"alcanzable [{alcanzable_min}, {alcanzable_max}] con flujos de {inferior} a {superior} L/m²/h."
        )
    iteraciones = 0
    while superior - inferior >= tolerancia and iteraciones < _MAXIMO_ITERACIONES:
        medio = (inferior + superior) / 2.0
        if _rendimiento_neuro(escenario, humedad_pct, semilla, medio, clima) < rendimiento_objetivo_l_m2_dia:
            inferior = medio
        else:
            superior = medio
        iteraciones += 1
    return round((inferior + superior) / 2.0, _DECIMALES)


def ejecutar_calibracion(cfg: CalibracionConfig) -> CalibracionResultado:
    """Calibra el flujo de niebla con el rendimiento medido y devuelve el perfil del sitio con ese flujo.

    Informa el rendimiento que produce el flujo calibrado, que difiere del
    objetivo en lo que cambia el rendimiento dentro de la tolerancia de la
    bisección. Sin sitio, el perfil es el de Cabo de la Vela con el flujo
    calibrado. Lanza ValueError si el objetivo no es alcanzable.
    """
    clima = _clima(cfg.sitio)
    flujo = calibrar_flujo_niebla(
        cfg.rendimiento_objetivo_l_m2_dia,
        escenario=cfg.escenario,
        humedad_pct=cfg.humedad_ambiente_inicial_pct,
        semilla=cfg.semilla,
        sitio=cfg.sitio,
    )
    rendimiento = _rendimiento_neuro(cfg.escenario, cfg.humedad_ambiente_inicial_pct, cfg.semilla, flujo, clima)
    sitio = cfg.sitio if cfg.sitio is not None else PerfilSitio()
    return CalibracionResultado(
        flujo_calibrado_l_m2_h=flujo,
        rendimiento_obtenido_l_m2_dia=rendimiento,
        perfil=sitio.model_copy(update={"flujo_niebla_maximo_l_m2_h": flujo}),
    )


# ---------------------------------------------------------------------------
# Propagación de la incertidumbre de los parámetros supuestos
# ---------------------------------------------------------------------------
@lru_cache(maxsize=_TAMANO_CACHE)
def _corrida_incertidumbre(
    escenario: Escenario,
    humedad: float,
    tasa: TasaSalinizacion,
    duracion_horas: int,
    semilla: int,
    parametros: ParametrosModelo,
) -> tuple[bool, bool, bool, float | None, float, float | None, float | None]:
    """Conjeturas e indicadores de una corrida con una muestra de los parámetros.

    Devuelve una tupla inmutable (C1, C2, C3, recuperación neuro, rendimiento
    en L/m²/día, reducción de la degradación, recuperación del temporizador).
    """
    detalle, neuro, temporizador, nodos = _simular_con_parametros(
        escenario, humedad, tasa, duracion_horas, semilla, parametros
    )
    c1 = detalle.conjetura_1_eficiencia
    recuperacion_temporizador = _media(temporizador.recuperaciones_pct)
    return (
        c1.validada,
        detalle.conjetura_2_autorreparacion.validada,
        detalle.conjetura_3_saber_territorial.validada,
        c1.indicadores["recuperacion_caudal_promedio_pct"].valor,
        impacto_comunitario(neuro.litros_totales, duracion_horas, nodos).rendimiento_l_m2_dia,
        c1.indicadores_informativos.get("reduccion_degradacion_pct"),
        None if recuperacion_temporizador is None else round(recuperacion_temporizador, _DECIMALES),
    )


def _muestrear_parametros(cfg: IncertidumbreConfig) -> list[tuple[float, float]]:
    """Pares (eficacia, flujo) con distribución uniforme en los rangos de la configuración.

    El generador se crea con la semilla de muestreo, de modo que la misma
    configuración produce siempre las mismas muestras.
    """
    generador = crear_generador(cfg.semilla_muestreo)
    return [
        (
            round(generador.uniform(cfg.eficacia_min, cfg.eficacia_max), _DECIMALES),
            round(generador.uniform(cfg.flujo_min, cfg.flujo_max), _DECIMALES),
        )
        for _ in range(cfg.n_muestras)
    ]


def _muestra(cfg: IncertidumbreConfig, eficacia: float, flujo: float) -> MuestraIncertidumbre:
    """Simula una muestra sin modificar la configuración global."""
    parametros = parametros_desde(flujo, eficacia)
    c1, c2, c3, recuperacion, rendimiento, reduccion, recuperacion_temporizador = _corrida_incertidumbre(
        cfg.escenario,
        cfg.humedad_ambiente_inicial_pct,
        cfg.tasa_salinizacion,
        cfg.duracion_horas,
        cfg.semilla,
        parametros,
    )
    return MuestraIncertidumbre(
        eficacia=eficacia,
        flujo=flujo,
        conjeturas_validadas=ConjeturasValidadas(
            conjetura_1_eficiencia=c1,
            conjetura_2_autorreparacion=c2,
            conjetura_3_saber_territorial=c3,
        ),
        recuperacion_caudal_promedio_pct=recuperacion,
        rendimiento_l_m2_dia=rendimiento,
        reduccion_degradacion_pct=reduccion,
        recuperacion_temporizador_pct=recuperacion_temporizador,
        ventaja_recuperacion_pts=_diferencia(recuperacion, recuperacion_temporizador),
    )


def _resumen(valores: list[float | None]) -> ResumenDistribucion:
    """Percentiles 5, 50 y 95 de los valores con datos (método inclusivo); los nulos se ignoran."""
    datos = [valor for valor in valores if valor is not None]
    if not datos:
        return ResumenDistribucion(n_validos=0)
    if len(datos) == 1:
        unico = round(datos[0], _DECIMALES)
        return ResumenDistribucion(p5=unico, p50=unico, p95=unico, n_validos=1)
    cortes = statistics.quantiles(datos, n=20, method="inclusive")
    return ResumenDistribucion(
        p5=round(cortes[0], _DECIMALES),
        p50=round(cortes[9], _DECIMALES),
        p95=round(cortes[18], _DECIMALES),
        n_validos=len(datos),
    )


def _proporcion(estados: list[bool]) -> float:
    """Proporción de valores verdaderos, redondeada a 4 decimales."""
    return round(sum(estados) / len(estados), _DECIMALES)


def _probabilidad_ventaja(ventajas: list[float | None]) -> float | None:
    """Proporción de las ventajas no nulas que son positivas, o None si no hay ninguna."""
    datos = [ventaja for ventaja in ventajas if ventaja is not None]
    if not datos:
        return None
    return _proporcion([_neuro_supera(ventaja) for ventaja in datos])


def ejecutar_incertidumbre(cfg: IncertidumbreConfig) -> IncertidumbreResultado:
    """Propaga la incertidumbre de la eficacia del pulso y del flujo de niebla.

    Muestrea ambos parámetros con distribución uniforme, simula una corrida por
    muestra con una copia de `ParametrosModelo` y reporta la proporción de
    muestras que validan cada conjetura, los percentiles 5, 50 y 95 de la
    recuperación, el rendimiento, la reducción de la degradación y la ventaja
    en recuperación frente al temporizador, y la proporción de muestras con
    ventaja positiva. La regla de validación y los valores por defecto del
    modelo no cambian (decisión D5).
    """
    muestras = [_muestra(cfg, eficacia, flujo) for eficacia, flujo in _muestrear_parametros(cfg)]
    validadas = [muestra.conjeturas_validadas for muestra in muestras]
    ventajas = [muestra.ventaja_recuperacion_pts for muestra in muestras]
    return IncertidumbreResultado(
        probabilidad_c1=_proporcion([estado.conjetura_1_eficiencia for estado in validadas]),
        probabilidad_c2=_proporcion([estado.conjetura_2_autorreparacion for estado in validadas]),
        probabilidad_c3=_proporcion([estado.conjetura_3_saber_territorial for estado in validadas]),
        recuperacion=_resumen([muestra.recuperacion_caudal_promedio_pct for muestra in muestras]),
        rendimiento=_resumen([muestra.rendimiento_l_m2_dia for muestra in muestras]),
        reduccion_degradacion=_resumen([muestra.reduccion_degradacion_pct for muestra in muestras]),
        muestras=muestras,
        ventaja_recuperacion=_resumen(ventajas),
        probabilidad_ventaja_recuperacion=_probabilidad_ventaja(ventajas),
    )


# ---------------------------------------------------------------------------
# Dimensionamiento del captador
# ---------------------------------------------------------------------------
# Corrida del dimensionamiento: 24 h con la red completa de 8 nodos.
DURACION_DIMENSIONAMIENTO_H = 24
NODOS_DIMENSIONAMIENTO = 8
CONSUMO_POR_ESTANDAR = {
    EstandarConsumo.SPHERE_15: config.CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA,
    EstandarConsumo.OMS_20: config.CONSUMO_ACCESO_BASICO_L_PERSONA_DIA,
}
# Posición del rendimiento del neuro-simbólico en la tupla de _metricas_corrida.
_INDICE_RENDIMIENTO = 4


def _dimension_por_flujo(cfg: DimensionamientoConfig, consumo: float, origen: str, flujo: float) -> DimensionPorFlujo:
    """Simula 24 h con el flujo dado y dimensiona el captador con el rendimiento del neuro-simbólico."""
    rendimiento = _metricas_corrida(
        cfg.escenario,
        cfg.tasa_salinizacion,
        cfg.humedad_ambiente_inicial_pct,
        DURACION_DIMENSIONAMIENTO_H,
        NODOS_DIMENSIONAMIENTO,
        cfg.semilla,
        parametros_desde(flujo_niebla_maximo_l_m2_h=flujo),
    )[_INDICE_RENDIMIENTO]
    area, nodos = dimensionar(cfg.personas, consumo, rendimiento)
    return DimensionPorFlujo(
        origen_flujo=origen,
        flujo_niebla_maximo_l_m2_h=flujo,
        rendimiento_neuro_l_m2_dia=rendimiento,
        area_colector_m2=area,
        nodos_requeridos=nodos,
    )


def ejecutar_dimensionamiento(cfg: DimensionamientoConfig) -> DimensionamientoResultado:
    """Área de colector y nodos para abastecer a las personas indicadas con los tres flujos de referencia.

    Cada flujo se simula 24 h con 8 nodos; el área es personas por consumo
    dividido entre el rendimiento del neuro-simbólico. Se informa además el
    rango de área con los rendimientos de 3 y 10 L/m²/día de Klemm et al.
    (2012). No modifica `backend.config`.
    """
    consumo = CONSUMO_POR_ESTANDAR[cfg.estandar]
    area_min, _ = dimensionar(cfg.personas, consumo, config.RENDIMIENTO_LITERATURA_MAX_L_M2_DIA)
    area_max, _ = dimensionar(cfg.personas, consumo, config.RENDIMIENTO_LITERATURA_MIN_L_M2_DIA)
    return DimensionamientoResultado(
        consumo_l_persona_dia=consumo,
        dimensiones=[_dimension_por_flujo(cfg, consumo, origen, flujo) for origen, flujo in FLUJOS_REFERENCIA],
        area_literatura_min_m2=area_min,
        area_literatura_max_m2=area_max,
    )


# ---------------------------------------------------------------------------
# Impacto en distintos entornos y comparación con abastecimiento por carrotanque
# ---------------------------------------------------------------------------
_ZONAS_CLASIFICABLES = (ZonaIncrustacion.BAJO_TRANSICION, ZonaIncrustacion.SOBRE_TRANSICION)


def clasificar_incrustacion(incrustacion: float | None) -> ZonaIncrustacion:
    """Clasifica la incrustación diaria frente al intervalo de transición del cruce (docs/04, sección 8.8)."""
    if incrustacion is None:
        return ZonaIncrustacion.SIN_DATOS
    if incrustacion < config.INCRUSTACION_TRANSICION_MIN_OHM_DIA:
        return ZonaIncrustacion.BAJO_TRANSICION
    if incrustacion >= config.INCRUSTACION_TRANSICION_MAX_OHM_DIA:
        return ZonaIncrustacion.SOBRE_TRANSICION
    return ZonaIncrustacion.TRANSICION


def _produccion_mensual_nodo(rendimiento: float | None) -> tuple[float | None, int | None]:
    """Litros al mes de un nodo de 1 m² y nodos necesarios para igualar la entrega mensual por carrotanque."""
    if rendimiento is None or rendimiento <= 0:
        return None, None
    litros_mes = round(rendimiento * config.AREA_COLECTOR_M2 * config.DIAS_POR_MES, _DECIMALES)
    nodos_entrega = math.ceil(round(config.ENTREGA_CARROTANQUE_L_COMUNIDAD_MES / litros_mes, _DECIMALES))
    return litros_mes, nodos_entrega


def _entorno_impacto(
    origen: str, flujo: float, punto: PuntoBarrido, personas: int, consumo: float
) -> EntornoImpacto:
    """Construye el resumen de impacto de un entorno a partir de un punto del barrido."""
    rendimiento = punto.rendimiento_neuro_l_m2_dia_media
    incrustacion = punto.incrustacion_diaria_ohm_media
    area, nodos = dimensionar(personas, consumo, rendimiento or 0.0)
    litros_mes, nodos_entrega = _produccion_mensual_nodo(rendimiento)
    return EntornoImpacto(
        origen_flujo=origen,
        flujo_niebla_maximo_l_m2_h=flujo,
        escenario=punto.escenario,
        tasa_salinizacion=punto.tasa_salinizacion,
        carga_salina_ohm_l_m2=punto.carga_salina_ohm_l_m2,
        rendimiento_neuro_l_m2_dia=rendimiento,
        incrustacion_diaria_ohm=incrustacion,
        zona_incrustacion=clasificar_incrustacion(incrustacion),
        ventaja_recuperacion_pts=punto.ventaja_recuperacion_pts,
        reduccion_desgaste_pct=punto.reduccion_desgaste_pct,
        area_colector_m2=area,
        nodos_requeridos=nodos,
        litros_mes_por_nodo=litros_mes,
        nodos_equivalentes_entrega=nodos_entrega,
    )


def _es_clasificable(entorno: EntornoImpacto) -> bool:
    """Indica si el entorno cae fuera de la transición y tiene ventaja de recuperación calculada."""
    return entorno.zona_incrustacion in _ZONAS_CLASIFICABLES and entorno.ventaja_recuperacion_pts is not None


def _es_coherente_con_simulacion(entorno: EntornoImpacto) -> bool:
    """Indica si la ventaja simulada coincide con lo esperado en la zona del entorno."""
    if not _es_clasificable(entorno):
        return False
    supera = _neuro_supera(entorno.ventaja_recuperacion_pts)  # type: ignore[arg-type]
    return supera if entorno.zona_incrustacion == ZonaIncrustacion.SOBRE_TRANSICION else not supera


def ejecutar_impacto_entornos(cfg: ImpactoEntornosConfig) -> ImpactoEntornosResultado:
    """Evalúa el impacto del control basado en reglas en los 18 entornos de flujo de niebla y salinidad.

    Para cada flujo de `FLUJOS_REFERENCIA` ejecuta el barrido de seis niveles de
    salinidad y traduce cada punto en área de colector, nodos requeridos para la
    comunidad y el estándar elegidos, producción mensual por nodo, nodos que
    igualan la entrega mensual por carrotanque del ICBF (2025) y zona de la
    incrustación diaria frente al intervalo de transición del cruce. No modifica
    `backend.config`.
    """
    consumo = CONSUMO_POR_ESTANDAR[cfg.estandar]
    entornos: list[EntornoImpacto] = []
    for origen, flujo in FLUJOS_REFERENCIA:
        barrido = ejecutar_barrido(
            BarridoConfig(
                humedad_ambiente_inicial_pct=cfg.humedad_ambiente_inicial_pct,
                semillas=[cfg.semilla],
                flujo_niebla_maximo_l_m2_h=flujo,
            )
        )
        entornos.extend(_entorno_impacto(origen, flujo, punto, cfg.personas, consumo) for punto in barrido.puntos)
    return ImpactoEntornosResultado(
        personas=cfg.personas,
        consumo_l_persona_dia=consumo,
        entrega_referencia_l_comunidad_mes=config.ENTREGA_CARROTANQUE_L_COMUNIDAD_MES,
        entornos=entornos,
        entornos_con_ventaja_esperada=sum(
            1 for entorno in entornos if entorno.zona_incrustacion == ZonaIncrustacion.SOBRE_TRANSICION
        ),
        entornos_coherentes_con_simulacion=sum(1 for entorno in entornos if _es_coherente_con_simulacion(entorno)),
        entornos_clasificables=sum(1 for entorno in entornos if _es_clasificable(entorno)),
    )
