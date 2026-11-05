"""Configuración del dashboard: conexión con la API y valores de referencia."""

import os

# URL base de la API. Se puede sobrescribir con la variable de entorno AXIOMA_API_URL.
API_URL = os.environ.get("AXIOMA_API_URL", "http://127.0.0.1:8000").rstrip("/")

# Los planes gratuitos de hosting suspenden la API por inactividad y tardan cerca de un
# minuto en reactivarla; por eso la verificación de salud admite una espera mayor.
TIMEOUT_SALUD_SEG = int(os.environ.get("AXIOMA_TIMEOUT_SALUD_SEG", "75"))  # s. Verificación de salud.
TIMEOUT_EVALUACION_SEG = 10  # s. Evaluación de nodos.
TIMEOUT_SIMULACION_SEG = 60  # s. Simulación comparativa.
TIMEOUT_ANALISIS_SEG = 120  # s. Barrido, robustez, sensibilidad, incertidumbre, dimensionamiento y calibración.

# Limita la robustez del desgaste del dashboard a una semilla para respetar TIMEOUT_ANALISIS_SEG
# en el plan gratuito; la API acepta hasta 3 (backend/schemas.py, RobustezDesgasteConfig).
MAXIMO_SEMILLAS_ROBUSTEZ_DESGASTE = 1

COMANDO_BACKEND = "uvicorn backend.main:app --reload --port 8000"

# Indica si el dashboard apunta a una API en el equipo local.
API_LOCAL = any(host in API_URL for host in ("127.0.0.1", "localhost"))

# Umbrales mostrados en las tarjetas y gráficos; deben coincidir con backend/config.py.
UMBRAL_IMPEDANCIA_OHMS = 1500.0
UMBRAL_TEMPERATURA_CORTE_C = 45.0
UMBRAL_RESERVA_CRITICA_PCT = 30.0
UMBRAL_HUMEDAD_ECOLOGICA_PCT = 30.0

# Umbrales de verificación de las conjeturas mostrados en los gráficos de análisis;
# deben coincidir con backend/config.py.
RECUPERACION_MINIMA_PCT = 90.0  # %. Conjetura 1.
TIEMPO_REGENERACION_MAX_SEG = 120.0  # s. Conjetura 2.
RENDIMIENTO_MINIMO_L_M2_NOCHE = 12.0  # L/m²/noche. Conjetura 3.

# Estándares del resumen de impacto comunitario; deben coincidir con backend/config.py.
CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA = 15.0  # Sphere (2018), estándar 2.1.
CONSUMO_ACCESO_BASICO_L_PERSONA_DIA = 20.0  # OMS, Howard et al. (2020).
RENDIMIENTO_LITERATURA_MIN_L_M2_DIA = 3.0  # Klemm et al. (2012).
RENDIMIENTO_LITERATURA_MAX_L_M2_DIA = 10.0  # Klemm et al. (2012).

# Hora local en que arranca la simulación del backend.
HORA_INICIO_SIMULACION = 18

# Consulta de los perfiles de sitio (GET /api/v1/sitios): una lectura breve, sin simulación.
TIMEOUT_SITIOS_SEG = 10  # s.

# Eficacia máxima del pulso supuesta y mínima para validar cada conjetura con el flujo supuesto.
# Origen: backend/config.py (EFICACIA_MAXIMA_PULSO) y docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md,
# sección 6.2 (0.94 equivale a remover el 78 % de la costra en un pulso y 0.97, el 81 %).
EFICACIA_SUPUESTA = 0.90
EFICACIA_MINIMA_C1 = 0.94
EFICACIA_MINIMA_C2 = 0.97

# Umbral de incrustación diaria de la hipótesis H1-Ciclo 3 (Ohm/día).
# Origen: docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md, sección 8.9.
INCRUSTACION_CRUCE_MIN_OHM_DIA = 1633.0
INCRUSTACION_CRUCE_MAX_OHM_DIA = 1867.0

# Límites de los campos editables del explorador de hipótesis; deben coincidir con
# PerfilSitio y SimulationConfig en backend/schemas.py. La eficacia se acota al rango
# supuesto de backend/config.py (EFICACIA_PULSO_RANGO_MIN y EFICACIA_PULSO_RANGO_MAX).
EFICACIA_EXPLORADOR_MIN = 0.80
EFICACIA_EXPLORADOR_MAX = 1.00
FLUJO_NIEBLA_MIN_L_M2_H = 0.01
FLUJO_NIEBLA_MAX_L_M2_H = 20.0
TEMPERATURA_MEDIA_MIN_C = 0.0
TEMPERATURA_MEDIA_MAX_C = 45.0
AMPLITUD_TEMPERATURA_MAX_C = 15.0
AMPLITUD_HUMEDAD_MAX_PCT = 30.0

# Límites del rendimiento medido de la calibración del flujo; el máximo coincide con
# CalibracionConfig en backend/schemas.py, que exige un valor positivo de hasta 40 L/m²/día.
RENDIMIENTO_MEDIDO_MIN_L_M2_DIA = 0.1
RENDIMIENTO_MEDIDO_MAX_L_M2_DIA = 40.0

# Perfil de Cabo de la Vela con que arranca el explorador de hipótesis antes de consultar
# GET /api/v1/sitios; debe coincidir con los valores por defecto de PerfilSitio (backend/schemas.py).
PERFIL_SITIO_POR_DEFECTO = {
    "nombre": "CABO_DE_LA_VELA",
    "flujo_niebla_maximo_l_m2_h": 6.0,
    "temperatura_media_c": 30.0,
    "amplitud_temperatura_c": 4.5,
    "amplitud_humedad_pct": 10.0,
}
