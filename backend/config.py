"""Configuración centralizada del motor Axioma-H.

Reúne los umbrales de control, los criterios de verificación de conjeturas y
los parámetros físicos del simulador. Los valores marcados como "Supuesto del
modelo" no provienen del PRD ni de la Matriz: son estimaciones de orden de
magnitud que deben calibrarse con datos de campo.
"""

# ---------------------------------------------------------------------------
# Umbrales de control (reglas neuro-simbólicas)
# ---------------------------------------------------------------------------
UMBRAL_TEMPERATURA_CORTE_C = 45.0  # °C. PRD, REGLA_01 (decisión D1).
TEMPERATURA_OBJETIVO_PULSO_C = 44.0  # °C. Matriz, Conjetura 2 (decisión D1).
UMBRAL_HUMEDAD_ECOLOGICA_PCT = 30.0  # % HR. PRD, REGLA_02.
UMBRAL_RESERVA_CRITICA_PCT = 30.0  # %. PRD, REGLA_04 (decisión D2).
UMBRAL_IMPEDANCIA_OHMS = 1500.0  # Ohm. PRD, REGLA_03 y REGLA_04.
IMPEDANCIA_NOMINAL_OHMS = 1000.0  # Ohm. Membrana limpia. PRD.
DURACION_PULSO_SEG = 90  # s. PRD, REGLA_03.
FRACCION_MAXIMA_EXTRACCION = 0.33  # Fracción de la niebla disponible. Matriz (decisión D3).
CAUDAL_DURANTE_PULSO_PCT = 80.0  # % del tope ecológico. PRD, REGLA_03.
CAUDAL_RESERVA_CRITICA_PCT = 50.0  # % del tope ecológico. PRD, REGLA_04.
CAUDAL_NOMINAL_PCT = 100.0  # % del tope ecológico. PRD, REGLA_05.

# ---------------------------------------------------------------------------
# Umbrales de verificación de conjeturas (Matriz de Operacionalización)
# ---------------------------------------------------------------------------
RECUPERACION_MINIMA_PCT = 90.0  # %. Conjetura 1.
AHORRO_ENERGIA_MINIMO_PCT = 35.0  # %. Conjetura 1.
TIEMPO_REGENERACION_MAX_SEG = 120  # s. Conjetura 2.
PERDIDA_TERMICA_MAXIMA_PCT = 0.0  # % de integridad. Conjetura 2.
VIOLACIONES_ECOLOGICAS_MAXIMAS = 0  # Episodios. Conjetura 3.
RENDIMIENTO_MINIMO_L_M2_NOCHE = 12.0  # L/m²/noche. Conjetura 3.

# ---------------------------------------------------------------------------
# Calendario de la simulación
# ---------------------------------------------------------------------------
HORA_INICIO_SIMULACION = 18.0  # Hora local de arranque. Supuesto del modelo.
HORA_INICIO_NOCHE = 18.0  # Hora local. Matriz, Conjetura 3.
HORA_FIN_NOCHE = 6.0  # Hora local. Matriz, Conjetura 3.
HORAS_POR_NOCHE = 12.0  # h. Ventana 18:00 a 06:00.

# ---------------------------------------------------------------------------
# Clima de referencia (Cabo de la Vela, La Guajira). Supuestos del modelo.
# ---------------------------------------------------------------------------
AMPLITUD_HUMEDAD_PCT = 10.0  # Puntos de HR; máximo a las 04:00.
HORA_MAXIMA_HUMEDAD = 4.0  # Hora local.
TEMPERATURA_MEDIA_C = 30.0  # °C ambiente.
AMPLITUD_TEMPERATURA_C = 4.5  # °C; ciclo 25.5 a 34.5 °C.
HORA_MAXIMA_TEMPERATURA = 14.0  # Hora local.
CALENTAMIENTO_SOLAR_MATRIZ_C = 7.0  # °C sobre el ambiente con radiación máxima.
RUIDO_HUMEDAD_PASO_PCT = 1.0  # Desviación estándar por paso y nodo.
RUIDO_TEMPERATURA_PASO_C = 0.3  # Desviación estándar por paso y nodo.
DISPERSION_HUMEDAD_NODO_PCT = 2.0  # Desfase fijo por nodo, uniforme +/-.
DISPERSION_TEMPERATURA_NODO_C = 0.5  # Desfase fijo por nodo, uniforme +/-.
DISPERSION_SALINIZACION_NODO = 0.10  # Variación relativa fija por nodo, uniforme +/-.

# ---------------------------------------------------------------------------
# Recurso hídrico y captación. Supuestos del modelo.
# ---------------------------------------------------------------------------
AREA_COLECTOR_M2 = 1.0  # m² de matriz por nodo.
FLUJO_NIEBLA_MAXIMO_L_M2_H = 6.0  # L/m²/h con HR = 100 % (0.35 g/m³ a 5 m/s).
HUMEDAD_MINIMA_CAPTACION_PCT = 20.0  # % HR por debajo de la cual no hay recurso.
EXPONENTE_CAPTACION = 1.5  # Curvatura de la disponibilidad frente a la HR.
FRACCION_EXTRACCION_TEMPORIZADOR = 0.45  # Control tradicional. Especificación del simulador.

# ---------------------------------------------------------------------------
# Salinización e impedancia. Supuestos del modelo.
# ---------------------------------------------------------------------------
# Aumento de impedancia por cada litro captado por m² (sal arrastrada por la niebla).
INCRUSTACION_OHM_POR_L_M2 = {
    "BAJA": 20.0,
    "MEDIA": 40.0,
    "ALTA": 80.0,
}
MULTIPLICADOR_INCRUSTACION_RAPIDA = 3.0  # Escenario INCRUSTACION_SALINA_RAPIDA.
MULTIPLICADOR_INCRUSTACION_SAL_Y_CALOR = 1.5  # Escenario TORMENTA_DE_SAL_Y_CALOR_EXTREMO (tasa ALTA).

# ---------------------------------------------------------------------------
# Efecto del pulso resistivo. Supuestos del modelo.
# ---------------------------------------------------------------------------
EFICACIA_MAXIMA_PULSO = 0.90  # Fracción máxima de sal removida en un pulso.
TEMPERATURA_MINIMA_EFECTO_C = 30.0  # °C sin efecto de disolución.
TEMPERATURA_SATURACION_EFECTO_C = 44.0  # °C con efecto térmico completo.
CARGA_SALINA_REFERENCIA_OHMS = 2500.0  # Ohm; a esta carga la eficacia cae a la mitad.
CONSTANTE_TIEMPO_DISOLUCION_SEG = 25.0  # s a temperatura de saturación.

# ---------------------------------------------------------------------------
# Energía. Supuestos del modelo.
# ---------------------------------------------------------------------------
CAPACIDAD_RESERVA_WH = 150.0  # Wh de reserva por nodo.
RESERVA_INICIAL_PCT = 70.0  # % al iniciar la simulación (18:00).
POTENCIA_RECARGA_SOLAR_W = 20.0  # W con radiación máxima.
CAPACIDAD_TERMICA_MATRIZ_J_K = 800.0  # J/K de la matriz de 1 m².
CONDUCTANCIA_PERDIDAS_W_K = 30.0  # W/K por convección en ambas caras.
CONSUMO_BASE_NEURO_W = 0.6  # W de sensores y microcontrolador.
CONSUMO_BASE_TEMPORIZADOR_W = 0.2  # W del temporizador.
INTERVALO_PULSO_TEMPORIZADOR_MIN = 120  # min. Especificación del simulador.
INCREMENTO_TERMICO_TEMPORIZADOR_C = 12.0  # °C sobre la matriz. Especificación del simulador.

# ---------------------------------------------------------------------------
# Integridad de la membrana. Supuestos del modelo.
# ---------------------------------------------------------------------------
FATIGA_POR_PULSO_PCT = 0.02  # % por ciclo térmico.
DEGRADACION_TERMICA_PCT_POR_C_MIN = 0.05  # % por cada °C sobre 45 y minuto de exposición.
DEGRADACION_CRISTALIZACION_PCT_H = 0.10  # % por hora con impedancia sobre el umbral.

# ---------------------------------------------------------------------------
# Escenarios. Supuestos del modelo.
# ---------------------------------------------------------------------------
SEQUIA_REDUCCION_HUMEDAD_PCT = 10.0  # Puntos de HR restados durante toda la simulación.
SEQUIA_HORA_INICIO = 9.0  # Hora local de inicio del déficit severo (cada día).
SEQUIA_HORA_FIN = 17.0  # Hora local de fin del déficit severo.
SEQUIA_HUMEDAD_MAXIMA_PCT = 25.0  # Techo de HR durante el déficit severo.
TORMENTA_ARENA_HORA_INICIO = 12.0  # Hora local; alisios intensos de la tarde.
TORMENTA_ARENA_HORA_FIN = 18.0  # Hora local.
TORMENTA_ARENA_FACTOR_CAPTACION = 0.6  # Fracción de captación durante la tormenta.
TORMENTA_ARENA_FACTOR_RADIACION = 0.5  # Fracción de recarga solar durante la tormenta.
TORMENTA_ARENA_ENSUCIAMIENTO_OHM_H = 60.0  # Ohm/h de impedancia por polvo.
CONSTANTE_LIMPIEZA_POLVO_H = 4.0  # h; el viento retira el polvo tras la tormenta.
CALOR_EXTREMO_INCREMENTO_C = 3.0  # °C extra con radiación máxima.
