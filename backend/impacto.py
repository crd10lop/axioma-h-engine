"""Estimación del impacto comunitario del agua captada por la red simulada.

Traduce los litros captados en personas abastecidas según dos estándares
citados: 15 L por persona al día (Sphere, estándar 2.1) y 20 L por persona al
día (acceso básico de la OMS). Compara además el rendimiento simulado con el
rango de 3 a 10 L/m²/día que Klemm et al. (2012) reportan para proyectos
operativos de captación de niebla. Es un indicador informativo: no interviene
en la validación de las conjeturas ni en las decisiones del motor.
"""

import math

from backend import config
from backend.schemas import ImpactoComunitario

HORAS_POR_DIA = 24
DECIMALES = 4


def dimensionar(
    personas: int, consumo_l_persona_dia: float, rendimiento_l_m2_dia: float
) -> tuple[float | None, int | None]:
    """Área de colector y nodos necesarios para abastecer a las personas indicadas.

    Área = personas * consumo / rendimiento, redondeada a 4 decimales; los
    nodos son el área redondeada hacia arriba, con AREA_COLECTOR_M2 (1 m²) por
    nodo. Devuelve (None, None) si el rendimiento no es positivo. Lanza
    ValueError si las personas o el consumo no son positivos.
    """
    if personas <= 0:
        raise ValueError(f"El número de personas debe ser positivo: {personas}")
    if consumo_l_persona_dia <= 0:
        raise ValueError(f"El consumo por persona debe ser positivo: {consumo_l_persona_dia}")
    if rendimiento_l_m2_dia <= 0:
        return None, None
    # Se redondea antes de math.ceil para que un error de coma flotante no agregue un nodo.
    area = round(personas * consumo_l_persona_dia / rendimiento_l_m2_dia, DECIMALES)
    return area, math.ceil(area / config.AREA_COLECTOR_M2)


def impacto_comunitario(litros_totales: float, duracion_horas: int, numero_nodos: int) -> ImpactoComunitario:
    """Estima el abastecimiento diario que permitirían los litros captados por la red.

    Los litros se normalizan a un día y el rendimiento se refiere al área total
    de colector (AREA_COLECTOR_M2 por nodo). Lanza ValueError si la duración o el
    número de nodos no son positivos.
    """
    if duracion_horas <= 0:
        raise ValueError(f"La duración debe ser positiva: {duracion_horas} h")
    if numero_nodos <= 0:
        raise ValueError(f"El número de nodos debe ser positivo: {numero_nodos}")
    litros_dia = litros_totales * HORAS_POR_DIA / duracion_horas
    consumo_basico = config.CONSUMO_ACCESO_BASICO_L_PERSONA_DIA
    return ImpactoComunitario(
        litros_dia_red=round(litros_dia, DECIMALES),
        rendimiento_l_m2_dia=round(litros_dia / (config.AREA_COLECTOR_M2 * numero_nodos), DECIMALES),
        personas_supervivencia=round(litros_dia / config.CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA, DECIMALES),
        personas_acceso_basico=round(litros_dia / consumo_basico, DECIMALES),
        area_m2_por_persona_basico_literatura_min=round(
            consumo_basico / config.RENDIMIENTO_LITERATURA_MAX_L_M2_DIA, DECIMALES
        ),
        area_m2_por_persona_basico_literatura_max=round(
            consumo_basico / config.RENDIMIENTO_LITERATURA_MIN_L_M2_DIA, DECIMALES
        ),
    )
