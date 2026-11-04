# Referencias, créditos y trazabilidad de parámetros

Este documento reúne el software de terceros que usa Axioma-H Engine, la fuente científica que respalda la comparación del modelo con la literatura y el origen de cada parámetro de `backend/config.py`. El proyecto se distribuye con licencia MIT (archivo `LICENSE`).

## 1. Software de terceros

Las licencias se obtuvieron de los metadatos de cada paquete instalado en el entorno virtual del proyecto, con `importlib.metadata` (campos `License-Expression` o `License`, y clasificadores `License ::`). Las URL corresponden a las declaradas en esos mismos metadatos. La versión indicada es la instalada al momento de la consulta; las versiones mínimas exigidas están en `requirements.txt` y `requirements-dev.txt`.

| Paquete | Versión consultada | Uso en el proyecto | URL oficial | Licencia |
|---|---|---|---|---|
| FastAPI | 0.162.0 | Framework de la API REST: aplicación, CORS y endpoints (`backend/main.py`, `backend/routers/`). | https://fastapi.tiangolo.com/ | MIT |
| Pydantic | 2.14.1 | Validación de los esquemas `TelemetryInput`, `ControlDecision`, `SimulationConfig` y `SimulationResult` (`backend/schemas.py`). | https://github.com/pydantic/pydantic | MIT |
| Uvicorn | 0.54.0 | Servidor ASGI que ejecuta la API en local y en Render. | https://uvicorn.dev/ | BSD-3-Clause |
| Streamlit | 1.66.1 | Dashboard interactivo (`frontend/app.py`). | https://streamlit.io | Apache-2.0 |
| Altair | 6.3.0 | Gráficos del dashboard (`frontend/app.py`). | https://altair-viz.github.io | BSD de tres cláusulas (texto del campo `License`; clasificador `BSD License`) |
| pandas | 3.1.0 | Conversión de las respuestas de la API en tablas para el dashboard (`frontend/transformaciones.py`). | https://pandas.pydata.org | BSD-3-Clause |
| Requests | 2.34.2 | Cliente HTTP del dashboard hacia la API (`frontend/cliente_api.py`). | https://requests.readthedocs.io | Apache-2.0 |
| pytest | 9.2.0 | Suite de pruebas automatizadas (`tests/`). | https://docs.pytest.org/en/latest/ | MIT |
| httpx | 0.28.1 | Cliente de `fastapi.testclient.TestClient` en `tests/test_api.py` y cliente HTTP de `scripts/verificar_despliegue.py`. | https://www.python-httpx.org | BSD-3-Clause |
| pytest-cov | 7.1.0 | Medición de cobertura de líneas y ramas en local y en CI, con reporte para SonarQube Cloud. | https://pytest-cov.readthedocs.io/ | MIT |

## 2. Fuentes científicas

| Referencia | Uso en el proyecto |
|---|---|
| Klemm, O., Schemenauer, R. S., Lummerich, A., et al. (2012). Fog as a fresh-water resource: overview and perspectives. *Ambio*, 41, 221-234. https://doi.org/10.1007/s13280-012-0247-8 | Los proyectos operativos de captación de niebla reportan promedios anuales típicos de 3 a 10 L por m² de malla al día. Se usa para contrastar el flujo de niebla supuesto por el modelo y el umbral de rendimiento de la Conjetura 3 (sección 4). |

## 3. Trazabilidad de parámetros

La tabla recorre todas las constantes de `backend/config.py` en el orden del archivo. La columna Origen sigue el comentario de cada constante:

- **PRD:** [02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md).
- **Matriz:** [01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 3.
- **Criterio del equipo:** decisión documentada en [modelo_simulacion.md](modelo_simulacion.md).
- **Supuesto:** estimación de orden de magnitud del modelo, pendiente de calibración con datos de campo.

| Constante | Valor | Origen | Fuente |
|---|---|---|---|
| `UMBRAL_TEMPERATURA_CORTE_C` | 45.0 °C | PRD | PRD, sección 4 (REGLA 01); decisión D1 de modelo_simulacion |
| `TEMPERATURA_OBJETIVO_PULSO_C` | 44.0 °C | Matriz | Matriz, Conjetura 2; decisión D1 de modelo_simulacion |
| `UMBRAL_HUMEDAD_ECOLOGICA_PCT` | 30.0 % | PRD | PRD, sección 4 (REGLA 02) |
| `UMBRAL_RESERVA_CRITICA_PCT` | 30.0 % | PRD | PRD, sección 4 (REGLA 03 y REGLA 04); decisión D2 de modelo_simulacion |
| `UMBRAL_IMPEDANCIA_OHMS` | 1500.0 Ohm | PRD | PRD, sección 4 (REGLA 03 y REGLA 04) |
| `IMPEDANCIA_NOMINAL_OHMS` | 1000.0 Ohm | PRD | PRD, según el comentario de config.py. El PRD no declara el valor de forma explícita |
| `DURACION_PULSO_SEG` | 90 s | PRD | PRD, sección 4 (REGLA 03) |
| `FRACCION_MAXIMA_EXTRACCION` | 0.33 | Matriz | Matriz, Conjetura 3; decisión D3 de modelo_simulacion |
| `CAUDAL_DURANTE_PULSO_PCT` | 80.0 % | PRD | PRD, sección 3.1 (respuesta de ejemplo de REGLA_03) |
| `CAUDAL_RESERVA_CRITICA_PCT` | 50.0 % | PRD | PRD, sección 4 (REGLA 04) |
| `CAUDAL_NOMINAL_PCT` | 100.0 % | PRD | PRD, sección 4 (REGLA 05) |
| `RECUPERACION_MINIMA_PCT` | 90.0 % | Matriz | Matriz, Conjetura 1 |
| `AHORRO_ENERGIA_MINIMO_PCT` | 35.0 % | Matriz | Matriz, Conjetura 1 |
| `TIEMPO_REGENERACION_MAX_SEG` | 120 s | Matriz | Matriz, Conjetura 2 |
| `FACTOR_IMPEDANCIA_REGENERADA` | 1.10 (1100 Ohm) | Criterio del equipo | modelo_simulacion, sección 6.4 |
| `PERDIDA_TERMICA_MAXIMA_PCT` | 0.0 % | Matriz | Matriz, Conjetura 2 |
| `VIOLACIONES_ECOLOGICAS_MAXIMAS` | 0 | Matriz | Matriz, Conjetura 3 |
| `RENDIMIENTO_MINIMO_L_M2_NOCHE` | 12.0 L/m²/noche | Matriz | Matriz, Conjetura 3. Contrastado con Klemm et al. (2012) en la sección 4 |
| `HORA_INICIO_SIMULACION` | 18.0 h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `HORA_INICIO_NOCHE` | 18.0 h | Matriz | Matriz, Conjetura 3 |
| `HORA_FIN_NOCHE` | 6.0 h | Matriz | Matriz, Conjetura 3 |
| `HORAS_POR_NOCHE` | 12.0 h | Matriz | Matriz, Conjetura 3 (ventana de 18:00 a 06:00) |
| `AMPLITUD_HUMEDAD_PCT` | 10.0 puntos de HR | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `HORA_MAXIMA_HUMEDAD` | 4.0 h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `TEMPERATURA_MEDIA_C` | 30.0 °C | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `AMPLITUD_TEMPERATURA_C` | 4.5 °C | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `HORA_MAXIMA_TEMPERATURA` | 14.0 h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CALENTAMIENTO_SOLAR_MATRIZ_C` | 7.0 °C | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `RUIDO_HUMEDAD_PASO_PCT` | 1.0 % | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `RUIDO_TEMPERATURA_PASO_C` | 0.3 °C | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `DISPERSION_HUMEDAD_NODO_PCT` | 2.0 % | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `DISPERSION_TEMPERATURA_NODO_C` | 0.5 °C | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `DISPERSION_SALINIZACION_NODO` | 0.10 | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `AREA_COLECTOR_M2` | 1.0 m² | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `FLUJO_NIEBLA_MAXIMO_L_M2_H` | 6.0 L/m²/h | Supuesto | Sin fuente: supuesto de orden de magnitud. Contrastado con Klemm et al. (2012) en la sección 4 |
| `HUMEDAD_MINIMA_CAPTACION_PCT` | 20.0 % | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `EXPONENTE_CAPTACION` | 1.5 | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `FRACCION_EXTRACCION_TEMPORIZADOR` | 0.45 | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `INCRUSTACION_OHM_POR_L_M2` | BAJA 20.0, MEDIA 40.0, ALTA 80.0 Ohm por L/m² | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `MULTIPLICADOR_INCRUSTACION_RAPIDA` | 3.0 | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `MULTIPLICADOR_INCRUSTACION_SAL_Y_CALOR` | 1.5 | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `EFICACIA_MAXIMA_PULSO` | 0.90 | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `TEMPERATURA_MINIMA_EFECTO_C` | 30.0 °C | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `TEMPERATURA_SATURACION_EFECTO_C` | 44.0 °C | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CARGA_SALINA_REFERENCIA_OHMS` | 2500.0 Ohm | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CONSTANTE_TIEMPO_DISOLUCION_SEG` | 25.0 s | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CAPACIDAD_RESERVA_WH` | 150.0 Wh | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `RESERVA_INICIAL_PCT` | 70.0 % | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `POTENCIA_RECARGA_SOLAR_W` | 20.0 W | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CAPACIDAD_TERMICA_MATRIZ_J_K` | 800.0 J/K | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CONDUCTANCIA_PERDIDAS_W_K` | 30.0 W/K | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CONSUMO_BASE_NEURO_W` | 0.6 W | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CONSUMO_BASE_TEMPORIZADOR_W` | 0.2 W | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `INTERVALO_PULSO_TEMPORIZADOR_MIN` | 120 min | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `INCREMENTO_TERMICO_TEMPORIZADOR_C` | 12.0 °C | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `FATIGA_POR_PULSO_PCT` | 0.02 % | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `DEGRADACION_TERMICA_PCT_POR_C_MIN` | 0.05 %/(°C·min) | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `DEGRADACION_CRISTALIZACION_PCT_H` | 0.10 %/h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `SEQUIA_REDUCCION_HUMEDAD_PCT` | 10.0 puntos de HR | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `SEQUIA_HORA_INICIO` | 9.0 h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `SEQUIA_HORA_FIN` | 17.0 h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `SEQUIA_HUMEDAD_MAXIMA_PCT` | 25.0 % | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `TORMENTA_ARENA_HORA_INICIO` | 12.0 h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `TORMENTA_ARENA_HORA_FIN` | 18.0 h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `TORMENTA_ARENA_FACTOR_CAPTACION` | 0.6 | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `TORMENTA_ARENA_FACTOR_RADIACION` | 0.5 | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `TORMENTA_ARENA_ENSUCIAMIENTO_OHM_H` | 60.0 Ohm/h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CONSTANTE_LIMPIEZA_POLVO_H` | 4.0 h | Supuesto | Sin fuente: supuesto de orden de magnitud |
| `CALOR_EXTREMO_INCREMENTO_C` | 3.0 °C | Supuesto | Sin fuente: supuesto de orden de magnitud |

`FRACCION_EXTRACCION_TEMPORIZADOR`, `INTERVALO_PULSO_TEMPORIZADOR_MIN` e `INCREMENTO_TERMICO_TEMPORIZADOR_C` se describen en config.py como "Especificación del simulador": definen el control tradicional de comparación y no provienen de una fuente externa.

## 4. Comparación del flujo de niebla supuesto con la literatura

El modelo supone un flujo máximo de niebla de 6.0 L/m²/h con humedad relativa del 100 % (`FLUJO_NIEBLA_MAXIMO_L_M2_H`). Con humedad inicial de 85 %, el modo neuro-simbólico obtiene un rendimiento nocturno de 16.97 L/m²/noche en DIA_NORMAL ([modelo_simulacion.md](modelo_simulacion.md), sección 5.4), aun con el tope de extracción del 33 %.

Klemm et al. (2012) reportan para los proyectos operativos de captación de niebla promedios anuales típicos de 3 a 10 L por m² de malla al día. El valor del modelo supera en cerca de 70 % el extremo superior de ese rango, y corresponde solo a las 12 horas nocturnas, sin contar la captación diurna.

La comparación es de orden de magnitud: la literatura se refiere a colectores de malla en sitios con niebla frecuente, mientras que el modelo describe una membrana con un flujo idealizado. Aun así, permite dos conclusiones:

- `FLUJO_NIEBLA_MAXIMO_L_M2_H = 6.0` es un supuesto optimista. Con humedad inicial de 45 %, el rendimiento nocturno del modelo (5.95 L/m²/noche en la corrida de referencia del PRD, modelo_simulacion 5.1) sí queda dentro del rango reportado.
- El umbral de 12 L/m²/noche de la Conjetura 3 (`RENDIMIENTO_MINIMO_L_M2_NOCHE`) supera el rango típico de operación de 3 a 10 L/m²/día. La validación de la Conjetura 3 con humedad inicial de 85 % depende, por tanto, de un flujo de niebla mayor que el observado en proyectos reales.

La calibración del flujo con mediciones en Cabo de la Vela queda como pregunta para el Ciclo 3 ([modelo_simulacion.md](modelo_simulacion.md), sección 8.3).
