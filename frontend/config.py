"""Configuración del dashboard: conexión con la API y valores de referencia."""

import os

# URL base de la API. Se puede sobrescribir con la variable de entorno AXIOMA_API_URL.
API_URL = os.environ.get("AXIOMA_API_URL", "http://127.0.0.1:8000").rstrip("/")

# Los planes gratuitos de hosting suspenden la API por inactividad y tardan cerca de un
# minuto en reactivarla; por eso la verificación de salud admite una espera mayor.
TIMEOUT_SALUD_SEG = int(os.environ.get("AXIOMA_TIMEOUT_SALUD_SEG", "75"))  # s. Verificación de salud.
TIMEOUT_EVALUACION_SEG = 10  # s. Evaluación de nodos.
TIMEOUT_SIMULACION_SEG = 60  # s. Simulación comparativa.
TIMEOUT_ANALISIS_SEG = 120  # s. Barrido y sensibilidad.

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

# Hora local en que arranca la simulación del backend.
HORA_INICIO_SIMULACION = 18
