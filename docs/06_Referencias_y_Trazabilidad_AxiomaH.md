# Referencias, créditos y trazabilidad de parámetros

**Proyecto:** Axioma-H — Captación Pasiva de Agua Atmosférica  
**Equipo:** AXIOMA — Curso Fundamentos de Investigación (UdeA), Ciclo 2  
**Repositorio:** https://github.com/crd10lop/axioma-h-engine  
**Aplicación desplegada:** [Dashboard](https://axioma-h-dashboard.onrender.com) | [API](https://axioma-h-api.onrender.com/docs)

Este documento reúne el software de terceros que usa Axioma-H Engine, las fuentes científicas que respaldan la comparación del modelo con la literatura y la estimación del impacto comunitario, y el origen de cada parámetro de `backend/config.py`. El proyecto se distribuye con licencia MIT (archivo `LICENSE`).

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
| Klemm, O., Schemenauer, R. S., Lummerich, A., et al. (2012). Fog as a fresh-water resource: overview and perspectives. *Ambio*, 41, 221-234. https://doi.org/10.1007/s13280-012-0247-8 | Los proyectos operativos de captación de niebla reportan promedios anuales típicos de 3 a 10 L por m² de malla al día. Se usa para contrastar el flujo de niebla supuesto por el modelo y el umbral de rendimiento de la Conjetura 3 (sección 4), como rango de rendimiento real en el impacto comunitario (`RENDIMIENTO_LITERATURA_MIN_L_M2_DIA` y `RENDIMIENTO_LITERATURA_MAX_L_M2_DIA`) y como objetivo de la calibración inversa del flujo de niebla (`FLUJO_NIEBLA_CALIBRADO_MIN_L_M2_H` y `FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H`). |
| Howard, G., Bartram, J., Williams, A., Overbo, A., Fuente, D. y Geere, J.-A. (2020). *Domestic water quantity, service level and health* (2.ª ed.). Organización Mundial de la Salud. https://www.who.int/publications/i/item/9789240015241 | Acceso básico de unos 20 L por persona al día. Se usa para estimar las personas abastecidas en el impacto comunitario (`CONSUMO_ACCESO_BASICO_L_PERSONA_DIA`; documento 04, sección 7.6). |
| Sphere Association (2018). *The Sphere Handbook: Humanitarian Charter and Minimum Standards in Humanitarian Response* (4.ª ed.), estándar 2.1 de abastecimiento de agua. https://spherestandards.org | Mínimo de 15 L por persona al día. Se usa para estimar las personas abastecidas con el mínimo humanitario en el impacto comunitario (`CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA`; documento 04, sección 7.6). |
| Instituto Colombiano de Bienestar Familiar (2025). *Más agua, más vida digna: Bienestar Familiar avanza en el acceso al agua en territorios étnicos*. https://www.icbf.gov.co/node/309446 | En el departamento de La Guajira, el ICBF informa un abastecimiento mediante carrotanques con una entrega mensual de 1000 L por comunidad, acompañada de hasta 30 L adicionales por ración alimentaria para preparar en el hogar, como parte de las acciones implementadas en los municipios priorizados por la Sentencia T-302 de 2017 (Riohacha, Maicao, Manaure y Uribia). Se usa como entrega mensual de referencia (`ENTREGA_CARROTANQUE_L_COMUNIDAD_MES`) para calcular cuántos nodos de 1 m² igualan una entrega por carrotanque en `POST /api/v1/analisis/impacto-entornos` (documento 04, sección 7.8). |
| Schemenauer, R. S. y Cereceda, P. (1994). A proposed standard fog collector for use in high-elevation regions. *Journal of Applied Meteorology*, 33, 1313-1322. https://doi.org/10.1175/1520-0450(1994)033<1313:APSFCF>2.0.CO;2 | Colector de niebla estándar de 1 m². Se cita en el informe final (documento 00) como instrumento de referencia para comparar rendimientos entre sitios y para la medición de campo propuesta en Cabo de la Vela. |
| Molina, J. M. y Escobar, C. M. (2008). Fog collection variability in the Andean Mountain Range of southern Colombia. *Die Erde*, 139(1-2), 127-140. | Media anual de 3.3 L/m² al día atribuible solo a la niebla en los Andes del sur de Colombia. Se usa en el informe final como dato colombiano para contrastar el rango de Klemm et al. (2012) y los flujos calibrados del modelo; no modifica ningún parámetro. |
| Araujo-Carrillo, G. A., Martínez-Maldonado, F. E., Deantonio-Florido, L. Y. y Gómez-Latorre, D. A. (2019). Agroclimatic zoning: a planning strategy for agricultural and livestock systems in Alta Guajira, Colombia. *Revista Colombiana de Ciencias Hortícolas*, 13(3), 435-447. https://doi.org/10.17584/rcch.2019v13i3.9648 | Precipitación media anual de 300 a 600 mm en la Alta Guajira, inferior a 500 mm en Uribia, y evapotranspiración cercana a 2000 mm. Contexto climático de la introducción del informe final. |
| Ospina-Noreña, J. E., Domínguez-Ramírez, C. A., Vega-Rodríguez, E. E., Darghan-Contreras, A. E. y Rodríguez-Molano, L. E. (2017). Analysis of the water balance under regional scenarios of climate change for arid zones of Colombia. *Atmósfera*, 30(1), 63-76. https://doi.org/10.20937/ATM.2017.30.01.06 | Condición desértica de La Guajira según el índice de Lang. Contexto climático de la introducción del informe final. |
| Corte Constitucional de Colombia (2017). *Sentencia T-302 de 2017*. https://www.corteconstitucional.gov.co/T-302-17/ | Sentencia que prioriza los municipios de Riohacha, Maicao, Manaure y Uribia. Se cita en el informe final en el contexto social, la justificación y las perspectivas éticas. |
| Jardine, A. K. S., Lin, D. y Banjevic, D. (2006). A review on machinery diagnostics and prognostics implementing condition-based maintenance. *Mechanical Systems and Signal Processing*, 20(7), 1483-1510. https://doi.org/10.1016/j.ymssp.2005.09.012 | Contraste entre mantenimiento basado en tiempo y mantenimiento basado en condición. Marco general del informe final para comparar el temporizador con el control por reglas. |
| Comas, J., Meabe, E., Sancho, L., Ferrero, G., Sipma, J., Monclús, H. y Rodriguez-Roda, I. (2010). Knowledge-based system for automatic MBR control. *Water Science and Technology*, 62(12). https://doi.org/10.2166/wst.2010.693 | Sistema basado en conocimiento para el control automático de biorreactores de membrana. Antecedente del control de limpieza en lazo cerrado en el informe final. |
| Ferrero, G., Monclús, H., Sancho, L., Garrido, J. M., Comas, J. y Rodríguez-Roda, I. (2011). A knowledge-based control system for air-scour optimisation in membrane bioreactors. *Water Science and Technology*, 63(9), 2025-2031. https://doi.org/10.2166/wst.2011.455 | Control basado en conocimiento de la aireación de limpieza de membranas frente a ciclos fijos. Antecedente del control de limpieza en lazo cerrado en el informe final. |
| Sim, L. N., Wang, Z. J., Gu, J., Coster, H. G. L. y Fane, A. G. (2013). Detection of reverse osmosis membrane fouling with silica, bovine serum albumin and their mixture using in-situ electrical impedance spectroscopy. *Journal of Membrane Science*, 443, 45-53. https://doi.org/10.1016/j.memsci.2013.04.047 | Espectroscopía de impedancia para detectar de forma temprana el ensuciamiento de membranas de ósmosis inversa. Antecedente del uso de la impedancia como sensor; su transferencia a captadores de niebla es un supuesto del proyecto que el informe final discute. |
| Antony, A., Low, J. H., Gray, S., Childress, A. E., Le-Clech, P. y Leslie, G. (2011). Scale formation and control in high pressure membrane water treatment systems: A review. *Journal of Membrane Science*, 383(1-2), 1-16. https://doi.org/10.1016/j.memsci.2011.08.054 | Revisión de la formación y el control de incrustaciones minerales en membranas. Respalda en el informe final que la incrustación es un problema documentado en membranas de tratamiento de agua. |
| d'Avila Garcez, A. y Lamb, L. C. (2023). Neurosymbolic AI: the 3rd wave. *Artificial Intelligence Review*, 56(11), 12387-12406. https://doi.org/10.1007/s10462-023-10448-w | Definición de la arquitectura neuro-simbólica y del papel del componente simbólico como explicable y verificable. Marco del motor de reglas como primera etapa en el informe final. |
| Fessehaye, M., Abdul-Wahab, S. A., Savage, M. J., Kohler, T., Gherezghiher, T. y Hurni, H. (2014). Fog-water collection for community use. *Renewable and Sustainable Energy Reviews*, 29, 52-62. https://doi.org/10.1016/j.rser.2013.08.063 | La captación de niebla para uso comunitario es estacional y localizada, y sus equipos requieren mantenimiento continuo. Se usa en el informe final (documento 00) para conectar la reducción del desgaste con la carga de mantenimiento de una comunidad. |
| Cereceda, P., Larrain, H., Osses, P., Farías, M. y Egaña, I. (2008). The spatial and temporal variability of fog and its relation to fog oases in the Atacama Desert, Chile. *Atmospheric Research*, 87(3-4), 312-323. https://doi.org/10.1016/j.atmosres.2007.11.012 | Unos 7.0 L/m² al día con colector estándar en los acantilados costeros de Atacama y menos de 1 L/m² al día 12 km tierra adentro. Se usa como contexto comparable en el análisis exploratorio E4 (documento 04, sección 8.13); no modifica ningún parámetro. |
| Alshiekh, M., Bloem, R., Ehlers, R., Könighofer, B., Niekum, S. y Topcu, U. (2018). Safe Reinforcement Learning via Shielding. *Proceedings of the AAAI Conference on Artificial Intelligence*, 32(1), 2669-2678. https://doi.org/10.1609/aaai.v32i1.11797 | Escudo de seguridad que filtra las acciones de un agente que aprende. Marco del informe final para discutir el papel de las reglas como guardarraíl de una futura etapa neuronal. |
| Asamblea General de las Naciones Unidas (2010). *El derecho humano al agua y el saneamiento* (A/RES/64/292). https://digitallibrary.un.org/record/687002 | Reconocimiento del derecho humano al agua. Se cita en la justificación social del informe final. |
| Congreso de Colombia (1991). *Ley 21 de 1991, por medio de la cual se aprueba el Convenio número 169 sobre pueblos indígenas y tribales en países independientes*. https://www.cancilleria.gov.co/sites/default/files/Normograma/docs/pdf/ley_0021_1991.pdf | Aprobación en Colombia del Convenio 169 de la OIT, base de la consulta previa, libre e informada. Se cita en las perspectivas éticas del informe final. |
| Park, J., Lee, C., Lee, S., Cho, H., Moon, M.-W. y Kim, S. J. (2021). Clogged water bridges for fog harvesting. *Soft Matter*, 17(1), 136-144. https://doi.org/10.1039/d0sm01133a | Obstrucción de los poros de mallas de niebla por puentes de agua, un mecanismo distinto de la incrustación salina. Única fuente revisada por pares que cumplió los criterios de la búsqueda documentada en el apéndice E del informe final. |
| Schemenauer, R. S. y Cereceda, P. (1992). The quality of fog water collected for domestic and agricultural use in Chile. *Journal of Applied Meteorology*, 31(3), 275-290. https://doi.org/10.1175/1520-0450(1992)031<0275:TQOFWC>2.0.CO;2 | En el agua de niebla costera de Chile, los cálculos con Cl⁻ como trazador de agua de mar mostraron que las sales marinas eran la fuente principal de Na⁺, Mg²⁺ y Cl⁻, y que la deposición seca tenía abundancias iónicas muy similares a las del agua de niebla. Se cita en el informe final (documento 00, secciones 1.3 y 3.2) como evidencia externa de que la niebla advectiva transporta sal marina hacia la malla colectora; no mide incrustación sobre la malla ni modifica ningún parámetro. |

## 3. Trazabilidad de parámetros

La tabla recorre todas las constantes de `backend/config.py` en el orden del archivo. La columna Origen sigue el comentario de cada constante:

- **PRD:** [02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md).
- **Matriz:** [01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 3.
- **Criterio del equipo:** decisión documentada en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md).
- **Supuesto:** estimación de orden de magnitud del modelo, pendiente de calibración con datos de campo.
- **Referencia:** valor tomado de una de las fuentes de la sección 2.
- **Calibración:** valor obtenido con el modelo para reproducir una cifra de una fuente de la sección 2.

| Constante | Valor | Origen | Fuente |
|---|---|---|---|
| `UMBRAL_TEMPERATURA_CORTE_C` | 45.0 °C | PRD | PRD, sección 4 (REGLA 01); decisión D1 del documento 04 |
| `TEMPERATURA_OBJETIVO_PULSO_C` | 44.0 °C | Matriz | Matriz, Conjetura 2; decisión D1 del documento 04 |
| `UMBRAL_HUMEDAD_ECOLOGICA_PCT` | 30.0 % | PRD | PRD, sección 4 (REGLA 02) |
| `UMBRAL_RESERVA_CRITICA_PCT` | 30.0 % | PRD | PRD, sección 4 (REGLA 03 y REGLA 04); decisión D2 del documento 04 |
| `UMBRAL_IMPEDANCIA_OHMS` | 1500.0 Ohm | PRD | PRD, sección 4 (REGLA 03 y REGLA 04) |
| `IMPEDANCIA_NOMINAL_OHMS` | 1000.0 Ohm | PRD | PRD, según el comentario de config.py. El PRD no declara el valor de forma explícita |
| `DURACION_PULSO_SEG` | 90 s | PRD | PRD, sección 4 (REGLA 03) |
| `FRACCION_MAXIMA_EXTRACCION` | 0.33 | Matriz | Matriz, Conjetura 3; decisión D3 del documento 04 |
| `CAUDAL_DURANTE_PULSO_PCT` | 80.0 % | PRD | PRD, sección 3.1 (respuesta de ejemplo de REGLA_03) |
| `CAUDAL_RESERVA_CRITICA_PCT` | 50.0 % | PRD | PRD, sección 4 (REGLA 04) |
| `CAUDAL_NOMINAL_PCT` | 100.0 % | PRD | PRD, sección 4 (REGLA 05) |
| `RECUPERACION_MINIMA_PCT` | 90.0 % | Matriz | Matriz, Conjetura 1 |
| `AHORRO_ENERGIA_MINIMO_PCT` | 35.0 % | Matriz | Matriz, Conjetura 1 |
| `TIEMPO_REGENERACION_MAX_SEG` | 120 s | Matriz | Matriz, Conjetura 2 |
| `FACTOR_IMPEDANCIA_REGENERADA` | 1.10 (1100 Ohm) | Criterio del equipo | Documento 04, sección 6.4 |
| `FRACCION_TIEMPO_DESPRENDIMIENTO` | 0.95 | Criterio del equipo | Documento 04, secciones 4 y 8.5. Indicador informativo `t95` de la Conjetura 2 |
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
| `CONSUMO_SUPERVIVENCIA_L_PERSONA_DIA` | 15.0 L/persona/día | Referencia | Sphere (2018), estándar 2.1 de abastecimiento de agua. Indicador informativo de impacto comunitario |
| `CONSUMO_ACCESO_BASICO_L_PERSONA_DIA` | 20.0 L/persona/día | Referencia | OMS, Howard et al. (2020), acceso básico. Indicador informativo de impacto comunitario |
| `RENDIMIENTO_LITERATURA_MIN_L_M2_DIA` | 3.0 L/m²/día | Referencia | Klemm et al. (2012). Indicador informativo de impacto comunitario |
| `RENDIMIENTO_LITERATURA_MAX_L_M2_DIA` | 10.0 L/m²/día | Referencia | Klemm et al. (2012). Indicador informativo de impacto comunitario |
| `FLUJO_NIEBLA_CALIBRADO_MIN_L_M2_H` | 0.49 L/m²/h | Calibración | Calibración inversa: rendimiento de 3 L/m²/día de Klemm et al. (2012), DIA_NORMAL, 85 %, semilla 42 (documento 04, sección 8.6). Solo se usa en la incertidumbre, la robustez de la respuesta, el dimensionamiento y los perfiles de `GET /api/v1/sitios` (documento 04, secciones 7.7, 8.7 y 8.8) |
| `FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H` | 1.83 L/m²/h | Calibración | Calibración inversa: rendimiento de 10 L/m²/día de Klemm et al. (2012), DIA_NORMAL, 85 %, semilla 42 (documento 04, sección 8.6). Solo se usa en la incertidumbre, la robustez de la respuesta y del desgaste, el dimensionamiento y los perfiles de `GET /api/v1/sitios` (documento 04, secciones 7.7, 8.7, 8.8 y 8.11) |
| `EFICACIA_PULSO_RANGO_MIN` | 0.80 | Supuesto | Rango plausible alrededor de 0.90, pendiente de medición. Solo se usa en la incertidumbre y en la robustez de la respuesta (documento 04, secciones 8.7 y 8.8) |
| `EFICACIA_PULSO_RANGO_MAX` | 1.00 | Supuesto | Rango plausible alrededor de 0.90, pendiente de medición. Solo se usa en la incertidumbre y en la robustez de la respuesta (documento 04, secciones 8.7 y 8.8) |
| `FATIGAS_ROBUSTEZ_PCT` | 0.01, 0.02 y 0.04 % | Supuesto | Mitad, valor supuesto y doble de `FATIGA_POR_PULSO_PCT`. Solo se usa en la robustez del desgaste (documento 04, sección 8.11) |
| `DEGRADACIONES_TERMICAS_ROBUSTEZ` | 0.025, 0.05 y 0.10 %/(°C·min) | Supuesto | Mitad, valor supuesto y doble de `DEGRADACION_TERMICA_PCT_POR_C_MIN`. Solo se usa en la robustez del desgaste (documento 04, sección 8.11) |
| `ENTREGA_CARROTANQUE_L_COMUNIDAD_MES` | 1000.0 L/comunidad/mes | Referencia | ICBF (2025), entrega mensual por comunidad mediante carrotanque en La Guajira (acompañada de hasta 30 L adicionales por ración alimentaria; iniciativa que hace parte de las acciones en Riohacha, Maicao, Manaure y Uribia, Sentencia T-302 de 2017). Solo se usa en el análisis de impacto en distintos entornos (documento 04, sección 7.8) |
| `DIAS_POR_MES` | 30 días | Criterio del equipo | Mes de 30 días para convertir el rendimiento diario de un nodo en producción mensual y compararla con `ENTREGA_CARROTANQUE_L_COMUNIDAD_MES` (documento 04, sección 7.8) |
| `INCRUSTACION_TRANSICION_MIN_OHM_DIA` | 1171.06 Ohm/día | Resultado del modelo | Menor `cruce_incrustacion_inferior_ohm` entre las seis combinaciones con cruce interpolado de la robustez de la respuesta con la semilla 42 (documento 04, secciones 7.8 y 8.8) |
| `INCRUSTACION_TRANSICION_MAX_OHM_DIA` | 2365.34 Ohm/día | Resultado del modelo | Mayor `cruce_incrustacion_superior_ohm` entre las seis combinaciones con cruce interpolado de la robustez de la respuesta con la semilla 42 (documento 04, secciones 7.8 y 8.8) |

`FRACCION_EXTRACCION_TEMPORIZADOR`, `INTERVALO_PULSO_TEMPORIZADOR_MIN` e `INCREMENTO_TERMICO_TEMPORIZADOR_C` se describen en config.py como "Especificación del simulador": definen el control tradicional de comparación y no provienen de una fuente externa.

## 4. Comparación del flujo de niebla supuesto con la literatura

El modelo supone un flujo máximo de niebla de 6.0 L/m²/h con humedad relativa del 100 % (`FLUJO_NIEBLA_MAXIMO_L_M2_H`). Con humedad inicial de 85 %, el modo neuro-simbólico obtiene un rendimiento nocturno de 16.97 L/m²/noche en DIA_NORMAL ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 5.4), aun con el tope de extracción del 33 %.

Klemm et al. (2012) reportan para los proyectos operativos de captación de niebla promedios anuales típicos de 3 a 10 L por m² de malla al día. El valor del modelo supera en cerca de 70 % el extremo superior de ese rango, y corresponde solo a las 12 horas nocturnas, sin contar la captación diurna.

La comparación es de orden de magnitud: la literatura se refiere a colectores de malla en sitios con niebla frecuente, mientras que el modelo describe una membrana con un flujo idealizado. Aun así, permite dos conclusiones:

- `FLUJO_NIEBLA_MAXIMO_L_M2_H = 6.0` es un supuesto optimista. Con humedad inicial de 45 %, el rendimiento nocturno del modelo (5.95 L/m²/noche en la corrida de referencia del PRD, documento 04, sección 5.1) sí queda dentro del rango reportado.
- El umbral de 12 L/m²/noche de la Conjetura 3 (`RENDIMIENTO_MINIMO_L_M2_NOCHE`) supera el rango típico de operación de 3 a 10 L/m²/día. La validación de la Conjetura 3 con humedad inicial de 85 % depende, por tanto, de un flujo de niebla mayor que el observado en proyectos reales.

Una calibración inversa contra el rango de Klemm et al. (2012) da un flujo de 0.49 a 1.83 L/m²/h, entre 3.3 y 12 veces menor que el supuesto; con él, la Conjetura 3 no se valida en DIA_NORMAL con humedad inicial de 85 % ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.6). El valor por defecto del modelo no cambia (decisión D5). La calibración del flujo con mediciones en Cabo de la Vela queda como pregunta para el Ciclo 3 ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.3).
