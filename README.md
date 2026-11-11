# Axioma-H Engine

[![CI](https://github.com/crd10lop/axioma-h-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/crd10lop/axioma-h-engine/actions/workflows/ci.yml)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=crd10lop_axioma-h-engine&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine)
[![Cobertura](https://sonarcloud.io/api/project_badges/measure?project=crd10lop_axioma-h-engine&metric=coverage)](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine)
[![Fiabilidad](https://sonarcloud.io/api/project_badges/measure?project=crd10lop_axioma-h-engine&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine)

Axioma-H Engine es un motor de control basado en reglas, primera etapa de una arquitectura neuro-simbólica, para nodos de captación pasiva de agua atmosférica. Con la telemetría de cada nodo (impedancia de la membrana, temperatura, reserva de calor y humedad), decide si filtrar, aplicar un pulso resistivo para desprender la sal, reducir el caudal o detener la extracción para proteger la membrana y el ecosistema.

Incluye una API REST, un dashboard de cinco vistas y un simulador que compara el control basado en reglas con un temporizador fijo en cinco escenarios de Cabo de la Vela (La Guajira). Lo desarrolla el equipo AXIOMA en el curso Fundamentos de Investigación de la Universidad de Antioquia, Ciclo 2. Hay un resumen en inglés en [README_EN.md](README_EN.md).

## Enlaces

| Recurso | Enlace |
|---|---|
| Código fuente | https://github.com/crd10lop/axioma-h-engine |
| Informe final (PDF y fuente LaTeX) | [docs/00_Informe_Final_AxiomaH.pdf](docs/00_Informe_Final_AxiomaH.pdf) ([fuente LaTeX](docs/00_Informe_Final_AxiomaH/README.md)) |
| Dashboard desplegado | [Abrir dashboard](https://axioma-h-dashboard.onrender.com) |
| API desplegada (documentación interactiva) | [Abrir API](https://axioma-h-api.onrender.com/docs) |
| Contrato OpenAPI versionado | [docs/api/openapi.json](docs/api/openapi.json) |
| Datos abiertos (CSV, JSON y Data Package) | [docs/datos/](docs/datos/README.md) |
| Calidad del código (SonarQube Cloud) | [Abrir tablero](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine) |

## Pregunta de investigación

> ¿En qué medida un sistema de control neuro-simbólico, evaluado mediante simulación, mejora la recuperación del caudal de agua y reduce el desgaste de las membranas de un captador de agua atmosférica, en comparación con un control convencional por temporizador, a medida que aumenta la salinidad del ambiente? 

Las sub-preguntas, las variables y la hipótesis de trabajo están en [docs/01](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.

## Respuesta

Todas las cifras salen de ejecuciones del modelo y su fuente única es [docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), secciones 6 a 8. En el modelo, con 24 h, humedad inicial de 85 % y los rangos evaluados de flujo de niebla y eficacia del pulso:

- **Desgaste.** El control basado en reglas (modo neuro-simbólico en la API) reduce la degradación de la membrana entre 73.3 % y 100 % frente al temporizador en los 54 puntos de las nueve combinaciones de flujo y eficacia (§8.8). Con la mitad y el doble de la fatiga por pulso y de la degradación térmica supuestas, se degrada menos en los 108 puntos de 18 combinaciones, con una reducción de 61.5 % a 100 % (§8.11).
- **Recuperación.** Su ventaja no depende de la carga salina por litro sino de la incrustación diaria: el cruce está entre 1632.9 y 1839.2 Ohm por día con la semilla 42 (1682.1 a 1866.6 con las semillas 1 a 3), mientras que la carga por litro del cruce va de 50.3 a 190.9 Ohm por L/m². Los dos niveles entre los que se interpola cada cruce están separados de 617 a 1165 Ohm por día, más que ese rango: el barrido no distingue el cruce entre combinaciones, que en cada una está en algún punto entre 1171 y 2365 Ohm por día (§8.8).
- **Con niebla como la de la literatura.** Con el flujo calibrado mínimo, 0.49 L/m²/h, la incrustación diaria no pasa de 659 Ohm por día y el temporizador recupera más en todos los niveles con pulsos; con el flujo calibrado, el control basado en reglas recupera más en solo 3 de 62 muestras de la incertidumbre (§8.7 y §8.8).
- **Conjeturas.** Las Conjeturas 1 y 2 dependen de la eficacia del pulso, que habría que medir (0.94 y 0.97 para validarlas, §6.2); la Conjetura 3 no se valida con el flujo calibrado (§8.6).
- **Personas.** Para 50 personas con 20 L al día harían falta 32 nodos de 1 m² con el flujo supuesto, y entre 100 y 332 con el flujo calibrado, en línea con los 100 a 333 m² de la literatura (§7.7). Igualar la entrega mensual de 1000 L por comunidad con carrotanque reportada por el ICBF (2025) toma 2 nodos de 1 m² con el flujo supuesto, de 3 a 4 con el flujo calibrado máximo y de 11 a 13 con el mínimo (§7.8).

La respuesta es condicional: la reducción del desgaste es robusta, y la ventaja en recuperación aparece solo por encima de una incrustación diaria de unos 1633 a 1867 Ohm por día (un rango estimado por interpolación: el cruce de cada combinación está en algún punto entre 1171 y 2365 Ohm por día). De ahí sale la hipótesis H1-Ciclo 3 ([docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), §8.9).

## Cómo leer este artefacto

Para una lectura integrada y autocontenida del proyecto, empieza por el [Informe final en PDF (documento 00)](docs/00_Informe_Final_AxiomaH.pdf) (fuente en LaTeX en [docs/00_Informe_Final_AxiomaH/](docs/00_Informe_Final_AxiomaH/README.md)). En la barra lateral del dashboard, el selector **Nivel de lectura** adapta las vistas 1 y 4 a tres públicos: **Comunidad** (lectura breve; vistas 1 y 4, parte d, impacto en distintos entornos), **Evaluador no técnico** (lectura breve; vistas 1 y 4, y la sección [Respuesta](#respuesta) de este documento) e **Investigador** (lectura completa, seleccionada por defecto; vistas 4 y 5, y [docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), secciones 7 y 8).

1. **Pregunta y tesis.** La vista 1 del dashboard, "Investigación y guía", y [docs/01](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2. La vista incluye los supuestos clave con la medición que reemplazaría a cada uno y una guía de lectura por disciplina.
2. **Funcionamiento.** Las vistas 2 y 3 muestran cómo decide un nodo y cómo se comparan ambos controles; [docs/03](docs/03_Funcionamiento_General_AxiomaH.md) lo explica en lenguaje general.
3. **Respuesta por partes.** La vista 4 responde la pregunta en cuatro partes: ¿reduce el desgaste?, ¿mejora la recuperación y desde qué salinidad?, ¿qué tan seguro es? y ¿para cuántas personas alcanza? Las tablas completas están en [docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), secciones 5 a 8.
4. **Hipótesis propias.** La vista 5, "Explorador de hipótesis", simula con una eficacia del pulso y un perfil de sitio propios, calibra el flujo de niebla con un rendimiento medido, dice qué cambiaría cada resultado y propone preguntas para el Ciclo 3.
5. **Lectura crítica.** Conflictos entre indicadores, contraste con la literatura, robustez y transferencia a otro sitio en [docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.
6. **Límites y fuentes.** Las [limitaciones](#limitaciones) de este documento y la trazabilidad de cada parámetro en [docs/06](docs/06_Referencias_y_Trazabilidad_AxiomaH.md).

**Mapa de evidencias por criterio de evaluación del curso.** Relaciona cada criterio con el capítulo del informe final (documento 00) y la evidencia del repositorio que lo respalda.

| Criterio | Informe final | Evidencia en el repositorio |
|---|---|---|
| Cobertura | Planteamiento, Metodología, Artefacto y Resultados | [docs/01](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), [docs/02](docs/02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md), `backend/main.py`, `docs/api/openapi.json` |
| Coherencia | Metodología, Resultados (contraste de conjeturas) y Discusión | [docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md) (§7 y §8), `frontend/contenido.py`, `tests/test_contenido.py` |
| Profundidad | Resultados (comparación por modo, banda de transición y robustez) | `backend/analisis.py`, [docs/datos/](docs/datos/README.md), [docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md) (§8.6 a §8.11) |
| Síntesis | Resumen, Lectura breve y tablero de veredictos | Sección [Respuesta](#respuesta), `frontend/contenido.py` (`VEREDICTOS`, `LECTURA_BREVE`) |
| Originalidad | Marco teórico (antecedentes del control basado en condición) y Artefacto | `backend/motor_reglas.py`, decisión D5 de [docs/04](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md) |
| Fluidez | Estructura global del informe | Fuente LaTeX en [docs/00_Informe_Final_AxiomaH/](docs/00_Informe_Final_AxiomaH/README.md) |
| Relevancia | Introducción, Planteamiento y Conclusiones | Contexto de La Guajira, Sentencia T-302 y estándares OMS y Sphere en [docs/06](docs/06_Referencias_y_Trazabilidad_AxiomaH.md) |
| Claridad | Lectura breve, Glosario y Artefacto | Selector de nivel de lectura del dashboard (`frontend/app.py`) |
| Confiabilidad | Discusión (validez de la comparación) y Anexo de trazabilidad | Pruebas en `tests/`, cobertura y SonarQube Cloud (sección [Pruebas y calidad](#pruebas-y-calidad)) |
| Universalidad | Conclusiones, trabajo futuro y guías de lectura | API REST desacoplada, datos abiertos Frictionless en [docs/datos/](docs/datos/README.md) |

## Documentación

| N.º | Documento | Contenido |
|---|---|---|
| 00 | [Informe final del proyecto (PDF)](docs/00_Informe_Final_AxiomaH.pdf) ([fuente LaTeX](docs/00_Informe_Final_AxiomaH/README.md)) | Síntesis académica completa, figuras de los datos abiertos, discusión y anexos. |
| 01 | [Plan y Matriz de Operacionalización](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md) | Pregunta, conjeturas, variables, perspectivas, alcance e hitos. |
| 02 | [Especificación técnica y PRD de la API](docs/02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md) | Endpoints, payloads y respuestas de ejemplo calculadas por el modelo. |
| 03 | [Funcionamiento general](docs/03_Funcionamiento_General_AxiomaH.md) | Explicación general, uso de las cinco vistas y guía por disciplina. |
| 04 | [Modelo de control y simulación](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md) | Reglas, ecuaciones, parámetros y fuente única de los resultados. |
| 05 | [Despliegue y operación](docs/05_Despliegue_y_Operacion_AxiomaH.md) | Render, CI, verificación e integración con otros sistemas. |
| 06 | [Referencias y trazabilidad](docs/06_Referencias_y_Trazabilidad_AxiomaH.md) | Software de terceros, fuentes científicas y origen de cada parámetro. |
| Anexo | [Datos de referencia](docs/datos/README.md) | CSV, JSON y Data Package con su diccionario de campos. |

## Arquitectura

La API (FastAPI, puerto 8000) hace todos los cálculos; el dashboard (Streamlit, puerto 8501) la consume por HTTP y no importa código del backend.

```
axioma-h-engine/
├── backend/
│   ├── main.py             Aplicación FastAPI, CORS y endpoints generales
│   ├── config.py           Umbrales de control y parámetros físicos con su origen
│   ├── schemas.py          Modelos Pydantic v2 y enumerados
│   ├── modelo_fisico.py    Ecuaciones compartidas y parámetros inmutables
│   ├── motor_reglas.py     Motor de control basado en reglas
│   ├── simulador.py        Simulación comparativa y verificación de conjeturas
│   ├── analisis.py         Barrido, robustez de la respuesta y del desgaste, sensibilidad, calibración, incertidumbre, dimensionamiento e impacto por entorno
│   ├── impacto.py          Impacto comunitario y dimensionamiento (OMS y Sphere)
│   └── routers/            nodo.py, simulacion.py, analisis.py y sitios.py
├── frontend/
│   ├── app.py              Dashboard Streamlit de cinco vistas (solo presentación)
│   ├── config.py           URL de la API, tiempos de espera y valores replicados del backend
│   ├── cliente_api.py      Cliente HTTP con manejo de errores
│   ├── contenido.py        Tesis, supuestos, etiquetas llanas, guía por disciplina y recorrido
│   └── transformaciones.py Conversión de respuestas en tablas, gráficos y frases calculadas
├── tests/                  Pruebas con pytest, sin red
├── docs/
│   ├── 00_Informe_Final_AxiomaH/   Código fuente en LaTeX del informe final (informe.tex, secciones, figuras y referencias)
│   ├── 00_Informe_Final_AxiomaH.pdf Informe académico compilado
│   ├── 01_ a 06_*.md       Documentación en orden de lectura
│   ├── api/openapi.json    Contrato OpenAPI generado desde la aplicación
│   └── datos/              CSV, JSON, datapackage.json y diccionario de campos
├── scripts/
│   ├── verificar_despliegue.py          Comprobaciones contra un despliegue
│   └── generar_resultados_referencia.py Datos abiertos, Data Package y OpenAPI sin red
├── .github/workflows/ci.yml  Pruebas, cobertura y SonarQube Cloud
├── render.yaml               Blueprint de despliegue en Render
└── requirements.txt, requirements-dev.txt
```

## Instalación y ejecución

Requiere Python 3.11 o superior. Desde la raíz del proyecto:

```bash
python -m venv venv
# Windows (PowerShell):  .\venv\Scripts\activate
# Linux y macOS:         source venv/bin/activate
pip install -r requirements.txt
```

En Linux y macOS puede ser necesario usar `python3` en lugar de `python`. Si PowerShell bloquea la activación, ejecute una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Con el entorno activo, en dos terminales:

```bash
uvicorn backend.main:app --reload --port 8000   # API: http://127.0.0.1:8000/docs
streamlit run frontend/app.py                   # Dashboard: http://localhost:8501
```

Todo funciona sin conexión a internet. Para usar otra API, defina `AXIOMA_API_URL` antes de iniciar Streamlit. Los datos de [docs/datos/](docs/datos/README.md) se regeneran sin la API con `python scripts/generar_resultados_referencia.py`, y `--comprobar` verifica que coinciden con el modelo. El despliegue en Render, con 31 comprobaciones automatizadas, está en [docs/05](docs/05_Despliegue_y_Operacion_AxiomaH.md).

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/health` | Salud del servicio |
| POST | `/api/v1/nodo/evaluar` | Decisión de control para la telemetría de un nodo |
| POST | `/api/v1/simulacion/ejecutar` | Simulación comparativa, con perfil de sitio y eficacia opcionales |
| POST | `/api/v1/analisis/barrido-salinidad` | Seis niveles de carga salina, de 1 a 5 semillas |
| POST | `/api/v1/analisis/robustez-respuesta` | Barrido con 3 flujos por 3 eficacias y cruce de la ventaja |
| POST | `/api/v1/analisis/robustez-desgaste` | Barrido con 2 flujos por 3 fatigas por pulso por 3 degradaciones térmicas |
| POST | `/api/v1/analisis/calibracion` | Flujo de niebla calibrado con un rendimiento medido y el perfil del sitio |
| POST | `/api/v1/analisis/sensibilidad` | Varios valores de la eficacia o del flujo de niebla |
| POST | `/api/v1/analisis/incertidumbre` | Muestreo conjunto de eficacia y flujo calibrado |
| POST | `/api/v1/analisis/dimensionamiento` | Área y nodos para un número de personas |
| POST | `/api/v1/analisis/impacto-entornos` | Impacto en 18 entornos de niebla y salinidad frente a la entrega por carrotanque |
| GET | `/api/v1/sitios` | Perfiles de sitio de referencia |

El esquema OpenAPI ([docs/api/openapi.json](docs/api/openapi.json)) publica 13 rutas en total: las 12 de la tabla y `GET /` (estado general del motor). Ningún análisis modifica la configuración del modelo (decisión D5). Los payloads y las respuestas de ejemplo están en [docs/02](docs/02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md), sección 3, y el uso desde otros sistemas (curl, pandas, Data Package y sensores reales) en [docs/05](docs/05_Despliegue_y_Operacion_AxiomaH.md), sección 7.

## Reglas de control

La primera regla que se cumple decide. El caudal es un porcentaje del tope ecológico: nunca se extrae más del 33 % de la niebla disponible.

| Prioridad | Regla | Condición | Acción |
|---|---|---|---|
| 1 | REGLA_01 | Temperatura >= 45 °C | Corte de emergencia, caudal 0 % |
| 2 | REGLA_02 | Humedad < 30 % | Pausa ecológica, caudal 0 % |
| 3 | REGLA_06 | Anulación del operador (solo más conservadora) | Suspender, o caudal 50 % sin pulso |
| 4 | REGLA_04 | Reserva < 30 % e impedancia > 1500 Ω | Caudal 50 % sin pulso |
| 5 | REGLA_03 | Impedancia > 1500 Ω y reserva >= 30 % | Pulso de 90 s a 44 °C, caudal 80 % |
| 6 | REGLA_05 | Ninguna de las anteriores | Filtración continua, caudal 100 % |

## Pruebas y calidad

`pytest --cov --cov-report=term-missing` ejecuta la suite sin red, con cobertura de 100 % en `backend/` y en la lógica del frontend. El CI de GitHub Actions envía los resultados a SonarQube Cloud, y Render despliega solo cuando las pruebas y la Quality Gate están en verde. `frontend/app.py` y `scripts/` están excluidos de la cobertura ([docs/03](docs/03_Funcionamiento_General_AxiomaH.md), sección 10).

## Limitaciones

- Los resultados provienen de un modelo simulado, no de mediciones en campo.
- La eficacia del pulso, el flujo de niebla, la carga salina por litro y la degradación por fatiga son supuestos pendientes de medición; la vista 1 indica qué medición reemplazaría a cada uno.
- El flujo de niebla supuesto es optimista frente a la literatura; con el flujo calibrado, la Conjetura 3 no se valida y la ventaja en recuperación casi no aparece.
- El tope del 33 % proviene de la Matriz del equipo, no de un saber wayuu documentado, y debe validarse con las comunidades. La consulta previa no se ha realizado.
- Los perfiles de sitio disponibles son solo de Cabo de la Vela, y el clima usa ciclos diurnos idealizados.
- Para consumir la API desde un navegador, el dominio debe agregarse en `AXIOMA_CORS_ORIGINS`. En el plan gratuito de Render, los servicios tardan cerca de un minuto en reactivarse.

Es una prueba de concepto analítica, aproximadamente TRL 2-3, sin prototipo físico ([docs/01](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.8).

## Historial de versiones

La versión de la API se publica en `GET /api/v1/health` (`VERSION_SERVICIO` en `backend/main.py`).

| Versión | Contenido |
|---|---|
| 0.1.0 | Motor de reglas, simulación comparativa, verificación de las tres conjeturas, dashboard y despliegue en Render. |
| 0.2.0 | Barrido con varias semillas, sensibilidad, causas de no validación, temporizador con tope ecológico, impacto comunitario, supervisión humana (REGLA_06) e incertidumbre con el flujo calibrado. |
| 0.3.0 | Robustez de la respuesta, incrustación diaria y cruce, dimensionamiento, perfil de sitio, `parametros_usados` y `GET /api/v1/sitios`. |
| 0.4.0 | Robustez del desgaste frente a la fatiga por pulso y la degradación térmica, niveles interpolados y separación del cruce, y calibración del flujo por API con el perfil del sitio. Los resultados por defecto del modelo no cambian. |
| 0.5.0 | Impacto en 18 entornos de niebla y salinidad, clasificación frente al intervalo de transición del cruce y comparación con la entrega de 1000 L/mes por comunidad con carrotanque (ICBF, 2025). Los resultados por defecto del modelo no cambian. |

El dashboard de cinco vistas, con la respuesta por partes y el explorador de hipótesis, y los datos interoperables (Data Package y OpenAPI versionado) se agregaron sobre la API 0.3.0, sin cambios en la API.

## Referencias y créditos

El software de terceros, las fuentes científicas (Klemm et al., 2012; OMS, Howard et al., 2020; Sphere, 2018; ICBF, 2025) y la trazabilidad de cada parámetro están en [docs/06](docs/06_Referencias_y_Trazabilidad_AxiomaH.md). El proyecto se distribuye con licencia MIT (archivo `LICENSE`).
