"""Análisis de robustez del modelo: barrido de salinidad, sensibilidad, calibración e incertidumbre.

Ningún análisis modifica `backend.config`. El barrido usa los parámetros base;
la sensibilidad, la calibración del flujo de niebla y la propagación de la
incertidumbre construyen una instancia inmutable de `ParametrosModelo` por
cada valor, de modo que solicitudes simultáneas en el servidor no comparten
estado. Las corridas individuales se guardan en una caché LRU cuyas claves son
valores inmutables (enumerados, números y `ParametrosModelo`).
"""

import statistics
from dataclasses import replace
from functools import lru_cache

from backend.impacto import impacto_comunitario
from backend.modelo_fisico import PARAMETROS_BASE, ParametrosModelo
from backend.schemas import (
    BarridoConfig,
    BarridoResultado,
    ConjeturasValidadas,
    DetalleVerificacion,
    Escenario,
    IncertidumbreConfig,
    IncertidumbreResultado,
    MuestraIncertidumbre,
    ParametroSensible,
    PuntoBarrido,
    PuntoSensibilidad,
    ResumenDistribucion,
    SensibilidadConfig,
    SensibilidadResultado,
    SimulationConfig,
    TasaSalinizacion,
)
from backend.simulador import (
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

_TAMANO_CACHE = 64
_DECIMALES = 4


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
) -> tuple[float | None, float | None, float, float]:
    """Recuperación y degradación de ambos modos en una corrida con los parámetros base.

    Devuelve una tupla inmutable (recuperación neuro, recuperación temporizador,
    degradación neuro, degradación temporizador). La recuperación es nula si el
    modo no ejecutó pulsos.
    """
    cfg = SimulationConfig(
        duracion_horas=duracion_horas,
        escenario=escenario,
        humedad_ambiente_inicial_pct=humedad,
        tasa_salinizacion=tasa,
        numero_nodos=numero_nodos,
        semilla=semilla,
    )
    _, neuro, temporizador = ejecutar_simulacion_detallada(cfg)
    return (
        _media(neuro.recuperaciones_pct),
        _media(temporizador.recuperaciones_pct),
        100.0 - neuro.integridad_final_promedio,
        100.0 - temporizador.integridad_final_promedio,
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


def _punto_barrido(cfg: BarridoConfig, escenario: Escenario, tasa: TasaSalinizacion) -> PuntoBarrido:
    """Agrega las corridas de todas las semillas para una combinación de escenario y tasa."""
    corridas = [
        _metricas_corrida(
            escenario, tasa, cfg.humedad_ambiente_inicial_pct, cfg.duracion_horas, cfg.numero_nodos, semilla
        )
        for semilla in cfg.semillas
    ]
    rec_neuro, rec_temp, deg_neuro, deg_temp = (list(columna) for columna in zip(*corridas))
    recuperacion_neuro = _estadisticos(rec_neuro)
    recuperacion_temporizador = _estadisticos(rec_temp)
    degradacion_neuro = _estadisticos(deg_neuro)
    degradacion_temporizador = _estadisticos(deg_temp)
    return PuntoBarrido(
        escenario=escenario,
        tasa_salinizacion=tasa,
        carga_salina_ohm_l_m2=tasa_incrustacion_base(escenario, tasa),
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
    )


def ejecutar_barrido(cfg: BarridoConfig) -> BarridoResultado:
    """Barrido de salinidad: DIA_NORMAL e INCRUSTACION_SALINA_RAPIDA con tasas BAJA, MEDIA y ALTA.

    Cada combinación se simula una vez por semilla con los parámetros base, y
    se reportan la media y la desviación estándar muestral de la recuperación
    tras pulso y de la degradación acumulada de ambos modos. Los puntos se
    ordenan por carga salina creciente.
    """
    puntos = [_punto_barrido(cfg, escenario, tasa) for escenario in ESCENARIOS_BARRIDO for tasa in TASAS_BARRIDO]
    return BarridoResultado(puntos=sorted(puntos, key=lambda punto: punto.carga_salina_ohm_l_m2))


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
    detalle, litros_neuro, _ = _simular_con_parametros(escenario, humedad, tasa, duracion_horas, semilla, parametros)
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
        round(litros_neuro, 3),
    )


def _simular_con_parametros(
    escenario: Escenario,
    humedad: float,
    tasa: TasaSalinizacion,
    duracion_horas: int,
    semilla: int,
    parametros: ParametrosModelo,
) -> tuple[DetalleVerificacion, float, int]:
    """Simula una corrida con 8 nodos y los parámetros dados, y verifica las conjeturas.

    Devuelve el detalle de verificación, los litros captados por el modo
    neuro-simbólico y el número de nodos.
    """
    cfg = SimulationConfig(
        duracion_horas=duracion_horas,
        escenario=escenario,
        humedad_ambiente_inicial_pct=humedad,
        tasa_salinizacion=tasa,
        semilla=semilla,
    )
    entorno, neuro, temporizador = ejecutar_simulacion_detallada(cfg, parametros=parametros)
    return verificar_conjeturas(neuro, temporizador, entorno.numero_nodos), neuro.litros_totales, entorno.numero_nodos


def _punto_sensibilidad(cfg: SensibilidadConfig, valor: float) -> PuntoSensibilidad:
    """Simula un valor del parámetro sensible sin modificar la configuración global."""
    parametros = replace(PARAMETROS_BASE, **{CAMPO_PARAMETRO[cfg.parametro]: valor})
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
def _rendimiento_neuro(escenario: Escenario, humedad: float, semilla: int, flujo: float) -> float:
    """Rendimiento del modo neuro-simbólico en L/m²/día con el flujo de niebla dado y los demás parámetros base."""
    parametros = replace(PARAMETROS_BASE, flujo_niebla_maximo_l_m2_h=flujo)
    _, litros, nodos = _simular_con_parametros(
        escenario, humedad, TASA_CALIBRACION, DURACION_CALIBRACION_H, semilla, parametros
    )
    return impacto_comunitario(litros, DURACION_CALIBRACION_H, nodos).rendimiento_l_m2_dia


def calibrar_flujo_niebla(
    rendimiento_objetivo_l_m2_dia: float,
    *,
    escenario: Escenario = Escenario.DIA_NORMAL,
    humedad_pct: float = 85.0,
    semilla: int = 42,
    tolerancia: float = 0.01,
) -> float:
    """Flujo máximo de niebla con el que el neuro-simbólico alcanza el rendimiento objetivo.

    Bisección sobre [0.1, 6.0] L/m²/h con una corrida de 24 h y tasa ALTA por
    cada flujo evaluado; el rendimiento crece con el flujo. Se detiene cuando
    el intervalo mide menos que la tolerancia y devuelve su punto medio,
    redondeado a 4 decimales. No modifica `backend.config`: cada corrida usa una
    copia de `ParametrosModelo`. Lanza ValueError si la tolerancia no es
    positiva o si el objetivo no está entre los rendimientos de los extremos.
    """
    if tolerancia <= 0:
        raise ValueError(f"La tolerancia debe ser positiva: {tolerancia}")
    inferior, superior = FLUJO_BUSQUEDA_MIN_L_M2_H, FLUJO_BUSQUEDA_MAX_L_M2_H
    alcanzable_min = _rendimiento_neuro(escenario, humedad_pct, semilla, inferior)
    alcanzable_max = _rendimiento_neuro(escenario, humedad_pct, semilla, superior)
    if not alcanzable_min <= rendimiento_objetivo_l_m2_dia <= alcanzable_max:
        raise ValueError(
            f"El rendimiento objetivo {rendimiento_objetivo_l_m2_dia} L/m²/día no está en el intervalo "
            f"alcanzable [{alcanzable_min}, {alcanzable_max}] con flujos de {inferior} a {superior} L/m²/h."
        )
    iteraciones = 0
    while superior - inferior >= tolerancia and iteraciones < _MAXIMO_ITERACIONES:
        medio = (inferior + superior) / 2.0
        if _rendimiento_neuro(escenario, humedad_pct, semilla, medio) < rendimiento_objetivo_l_m2_dia:
            inferior = medio
        else:
            superior = medio
        iteraciones += 1
    return round((inferior + superior) / 2.0, _DECIMALES)


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
) -> tuple[bool, bool, bool, float | None, float, float | None]:
    """Conjeturas e indicadores de una corrida con una muestra de los parámetros.

    Devuelve una tupla inmutable (C1, C2, C3, recuperación, rendimiento en
    L/m²/día, reducción de la degradación).
    """
    detalle, litros, nodos = _simular_con_parametros(escenario, humedad, tasa, duracion_horas, semilla, parametros)
    c1 = detalle.conjetura_1_eficiencia
    return (
        c1.validada,
        detalle.conjetura_2_autorreparacion.validada,
        detalle.conjetura_3_saber_territorial.validada,
        c1.indicadores["recuperacion_caudal_promedio_pct"].valor,
        impacto_comunitario(litros, duracion_horas, nodos).rendimiento_l_m2_dia,
        c1.indicadores_informativos.get("reduccion_degradacion_pct"),
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
    parametros = replace(PARAMETROS_BASE, eficacia_maxima_pulso=eficacia, flujo_niebla_maximo_l_m2_h=flujo)
    c1, c2, c3, recuperacion, rendimiento, reduccion = _corrida_incertidumbre(
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


def ejecutar_incertidumbre(cfg: IncertidumbreConfig) -> IncertidumbreResultado:
    """Propaga la incertidumbre de la eficacia del pulso y del flujo de niebla.

    Muestrea ambos parámetros con distribución uniforme, simula una corrida por
    muestra con una copia de `ParametrosModelo` y reporta la proporción de
    muestras que validan cada conjetura y los percentiles 5, 50 y 95 de la
    recuperación, el rendimiento y la reducción de la degradación. La regla de
    validación y los valores por defecto del modelo no cambian (decisión D5).
    """
    muestras = [_muestra(cfg, eficacia, flujo) for eficacia, flujo in _muestrear_parametros(cfg)]
    validadas = [muestra.conjeturas_validadas for muestra in muestras]
    return IncertidumbreResultado(
        probabilidad_c1=_proporcion([estado.conjetura_1_eficiencia for estado in validadas]),
        probabilidad_c2=_proporcion([estado.conjetura_2_autorreparacion for estado in validadas]),
        probabilidad_c3=_proporcion([estado.conjetura_3_saber_territorial for estado in validadas]),
        recuperacion=_resumen([muestra.recuperacion_caudal_promedio_pct for muestra in muestras]),
        rendimiento=_resumen([muestra.rendimiento_l_m2_dia for muestra in muestras]),
        reduccion_degradacion=_resumen([muestra.reduccion_degradacion_pct for muestra in muestras]),
        muestras=muestras,
    )
