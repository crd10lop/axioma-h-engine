# Axioma-H Engine

[![CI](https://github.com/crd10lop/axioma-h-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/crd10lop/axioma-h-engine/actions/workflows/ci.yml)
[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=crd10lop_axioma-h-engine&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine)
[![Cobertura](https://sonarcloud.io/api/project_badges/measure?project=crd10lop_axioma-h-engine&metric=coverage)](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine)
[![Fiabilidad](https://sonarcloud.io/api/project_badges/measure?project=crd10lop_axioma-h-engine&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine)

Axioma-H Engine es un motor de control neuro-simbólico para nodos de captación pasiva de agua atmosférica. A partir de la telemetría de cada nodo (impedancia de la membrana, temperatura de la matriz, reserva de calor y humedad relativa), el motor decide si filtrar de forma continua, aplicar un pulso resistivo para desprender la sal cristalizada, reducir el caudal o detener la extracción para proteger la membrana y el ecosistema.

El proyecto incluye una API REST y un dashboard simulador. El simulador compara el control neuro-simbólico con un temporizador fijo tradicional bajo cinco escenarios ambientales de referencia de Cabo de la Vela (La Guajira). Con esa comparación se verifican las tres conjeturas de investigación del Ciclo 2.

Lo desarrolla el equipo AXIOMA en el curso Fundamentos de Investigación de la Universidad de Antioquia (UdeA), Ciclo 2.

Para una explicación general de qué hace la aplicación y cómo funciona, ver [docs/03_Funcionamiento_General_AxiomaH.md](docs/03_Funcionamiento_General_AxiomaH.md). Hay un resumen en inglés en [README_EN.md](README_EN.md).

## Enlaces

| Recurso | Enlace |
|---|---|
| Código fuente | https://github.com/crd10lop/axioma-h-engine |
| Dashboard desplegado | [Abrir dashboard](https://axioma-h-dashboard.onrender.com) |
| API desplegada (documentación interactiva) | [Abrir API](https://axioma-h-api.onrender.com/docs) |
| Salud de la API | [Verificar estado](https://axioma-h-api.onrender.com/api/v1/health) |
| Calidad del código (SonarQube Cloud) | [Abrir tablero](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine) |
| Datos de referencia abiertos (CSV y JSON) | [docs/datos/](docs/datos/README.md) |
| Resumen en inglés | [README_EN.md](README_EN.md) |

## Documentación

Los documentos de `docs/` están numerados en orden de lectura:

| N.º | Documento | Contenido |
|---|---|---|
| 01 | [Plan y Matriz de Operacionalización](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md) | Pregunta de investigación, conjeturas, variables, perspectivas del estudio, alcance e hitos. |
| 02 | [Especificación técnica y PRD de la API](docs/02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md) | Datos que recibe y entrega la API, payloads de ejemplo y estado de la implementación. |
| 03 | [Funcionamiento general](docs/03_Funcionamiento_General_AxiomaH.md) | Explicación en lenguaje general de la aplicación y del dashboard. |
| 04 | [Modelo de control y simulación](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md) | Reglas, ecuaciones, parámetros, resultados, sensibilidad y lectura crítica de las conjeturas. |
| 05 | [Despliegue y operación](docs/05_Despliegue_y_Operacion_AxiomaH.md) | Despliegue en Render, integración continua, verificación y operación del plan gratuito. |
| 06 | [Referencias y trazabilidad](docs/06_Referencias_y_Trazabilidad_AxiomaH.md) | Software de terceros, fuente científica y origen de cada parámetro del modelo. |
| Anexo | [Datos de referencia](docs/datos/README.md) | Resultados en CSV y JSON con su diccionario de campos. |

## Pregunta de investigación

> ¿En qué medida un sistema de control neuro-simbólico, evaluado mediante simulación, mejora la recuperación del caudal de agua y reduce el desgaste de las membranas de un captador de agua atmosférica, en comparación con un control convencional por temporizador, a medida que aumenta la salinidad del ambiente? 

Las sub-preguntas, las variables y la hipótesis de trabajo están en [docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2. La respuesta preliminar del simulador está en la sección [Resultados](#barrido-de-salinidad).

## Cómo leer este artefacto

Se recomienda recorrer el proyecto en este orden:

1. **Pregunta.** La pregunta de investigación de la sección anterior y su desarrollo en [docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.
2. **Respuesta.** El [Barrido de salinidad](#barrido-de-salinidad), que compara ambos modos de control a medida que aumenta la salinidad.
3. **Conjeturas.** La verificación de las tres conjeturas en [Resultados](#resultados) y su detalle en [docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), secciones 5 y 6.
4. **Lectura crítica.** El conflicto entre los indicadores de la Conjetura 1, el contraste del umbral de la Conjetura 3 con la literatura y las preguntas para el Ciclo 3, en [docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.
5. **Limitaciones.** Las [Limitaciones conocidas](#limitaciones-conocidas) y el [Alcance y madurez](#alcance-y-madurez) del artefacto.
6. **Referencias.** El software de terceros, las fuentes científicas y la trazabilidad de cada parámetro en [docs/06_Referencias_y_Trazabilidad_AxiomaH.md](docs/06_Referencias_y_Trazabilidad_AxiomaH.md).

## Naturaleza del control

El motor implementado es simbólico: aplica reglas explícitas en orden de prioridad (`backend/motor_reglas.py`) y se apoya en un modelo físico explícito (`backend/modelo_fisico.py`). El "Módulo Neuronal" del diagrama de arquitectura del plan no está implementado y queda como trabajo futuro, en particular para distinguir la impedancia causada por sal de la causada por polvo. El término neuro-simbólico describe la arquitectura objetivo del sistema, no la implementación actual. El detalle está en [docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 4.

## Arquitectura

El sistema se compone de dos servicios que se ejecutan por separado:

- **Backend (FastAPI, puerto 8000):** contiene el motor de reglas, el modelo físico, el simulador comparativo, la verificación de conjeturas y el análisis de robustez (barrido de salinidad y sensibilidad).
- **Frontend (Streamlit, puerto 8501):** dashboard que consume la API por HTTP. No importa código del backend, de modo que ambos servicios pueden desplegarse en máquinas distintas.

```
axioma-h-engine/
├── backend/
│   ├── main.py             Aplicación FastAPI, CORS y endpoints generales
│   ├── config.py           Umbrales de control y parámetros físicos del modelo
│   ├── schemas.py          Modelos Pydantic v2 y enumerados
│   ├── modelo_fisico.py    Ecuaciones compartidas: pulso, energía y captación
│   ├── motor_reglas.py     Reglas neuro-simbólicas en orden de prioridad
│   ├── simulador.py        Simulación comparativa y verificación de conjeturas
│   ├── analisis.py         Barrido, sensibilidad, calibración e incertidumbre con parámetros inmutables
│   ├── impacto.py          Impacto comunitario estimado con estándares de la OMS y Sphere
│   └── routers/
│       ├── nodo.py         POST /api/v1/nodo/evaluar
│       ├── simulacion.py   POST /api/v1/simulacion/ejecutar
│       └── analisis.py     POST /api/v1/analisis/barrido-salinidad y /sensibilidad
├── frontend/
│   ├── app.py              Dashboard Streamlit
│   ├── config.py           URL de la API y tiempos de espera
│   ├── cliente_api.py      Cliente HTTP con manejo de errores
│   └── transformaciones.py Conversión de respuestas en DataFrames
├── tests/                  Pruebas con pytest
├── docs/                                            Documentación, en orden de lectura
│   ├── 01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md   Pregunta, conjeturas, variables, perspectivas e hitos
│   ├── 02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md        Especificación de la API y estado de la implementación
│   ├── 03_Funcionamiento_General_AxiomaH.md                  Explicación general de la aplicación y del dashboard
│   ├── 04_Modelo_de_Control_y_Simulacion_AxiomaH.md          Reglas, ecuaciones, resultados y lectura crítica
│   ├── 05_Despliegue_y_Operacion_AxiomaH.md                  Despliegue en Render, CI y verificación
│   ├── 06_Referencias_y_Trazabilidad_AxiomaH.md              Software de terceros, fuentes y trazabilidad de parámetros
│   └── datos/                                       Resultados de referencia en CSV y JSON, con su diccionario de campos
├── scripts/
│   ├── verificar_despliegue.py         Comprobaciones contra el despliegue publicado
│   └── generar_resultados_referencia.py Datos de referencia sin red ni API
├── README_EN.md            Resumen en inglés
├── pytest.ini
├── render.yaml             Blueprint de despliegue en Render
└── requirements.txt
```

## Requisitos

- Windows 10 u 11.
- Python 3.11 o superior.
- Las dependencias de `requirements.txt`: FastAPI, Uvicorn, Pydantic v2, Streamlit, Altair, Requests, pandas, pytest y httpx.

## Instalación en Windows

Desde la raíz del proyecto, en PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Si PowerShell bloquea la activación del entorno, ejecute una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Ejecución

Abra dos terminales en la raíz del proyecto y active el entorno virtual en cada una.

Terminal 1, backend:

```powershell
uvicorn backend.main:app --reload --port 8000
```

La documentación interactiva queda disponible en http://127.0.0.1:8000/docs.

Terminal 2, frontend:

```powershell
streamlit run frontend/app.py
```

El dashboard queda disponible en http://localhost:8501. Streamlit escucha por defecto en todas las interfaces de red; para limitarlo al equipo local, agregue `--server.address 127.0.0.1`.

### Vistas del dashboard

La barra lateral ofrece un recorrido de cuatro vistas, con un botón "Siguiente" al final de cada una, salvo la última:

1. **Investigación y guía:** pregunta, hipótesis, conjeturas, reglas, perspectivas y alcance. No requiere la API.
2. **Evaluación manual de nodo:** decisión del motor para una telemetría ajustable, con supervisión humana opcional (suspender la extracción o impedir el pulso).
3. **Simulación comparativa:** ambos modos sobre un escenario, con impacto comunitario estimado, gráficos, conjeturas y bitácora.
4. **Respuesta a la pregunta:** barrido de salinidad con 1 a 5 semillas (media y banda de +/- una desviación) sensibilidad a la eficacia del pulso o al flujo de niebla, e incertidumbre conjunta de ambos parámetros con la probabilidad de validar cada conjetura. Usa los endpoints de `/api/v1/analisis` y no modifica la configuración del modelo.

El detalle de cada vista está en [docs/03_Funcionamiento_General_AxiomaH.md](docs/03_Funcionamiento_General_AxiomaH.md), sección 5.

### Uso local sin conexión

El proyecto no depende del despliegue en Render. Con las dependencias instaladas, todo funciona en el equipo sin conexión a internet:

- **Aplicación completa:** iniciar el backend y el dashboard como se indica arriba. El dashboard se conecta por defecto a la API local (`http://127.0.0.1:8000`).
- **Resultados de referencia:** `python scripts/generar_resultados_referencia.py` importa el backend directamente, sin la API, y regenera en [docs/datos/](docs/datos/README.md) los cinco escenarios con 45 % y 85 % de humedad inicial y el barrido de salinidad con semillas 1 a 5. Los archivos ya generados están en el repositorio y se pueden abrir con cualquier hoja de cálculo.
- **Pruebas:** `pytest` no usa la red; el cliente HTTP del dashboard se prueba con `requests` simulado.

El dashboard guarda durante una hora la respuesta de cada simulación y de cada análisis: repetir la misma configuración no vuelve a llamar a la API.

### Variable AXIOMA_API_URL

El dashboard se conecta por defecto a `http://127.0.0.1:8000`. Para usar otra dirección, defina la variable antes de iniciar Streamlit:

```powershell
$env:AXIOMA_API_URL = "http://192.168.1.50:8000"
streamlit run frontend/app.py
```

Los tiempos de espera son de 75 s para la verificación de salud (para tolerar la reactivación de un servicio suspendido; configurable con `AXIOMA_TIMEOUT_SALUD_SEG`), 10 s para la evaluación de nodos y 60 s para la simulación (`frontend/config.py`).

## Despliegue

La aplicación está desplegada en **Render**, en el plan gratuito, con el Blueprint versionado en `render.yaml`. Son dos servicios web construidos desde la rama `main`:

| Servicio | URL |
|---|---|
| `axioma-h-api` (FastAPI) | https://axioma-h-api.onrender.com |
| `axioma-h-dashboard` (Streamlit) | https://axioma-h-dashboard.onrender.com |

Cada push a `main` ejecuta el workflow CI (pruebas, cobertura y análisis de SonarQube Cloud), y Render despliega ambos servicios solo cuando todos los checks del commit están en verde (`autoDeployTrigger: checksPass`). El dashboard se conecta a la API publicada mediante la variable `AXIOMA_API_URL`.

La verificación automatizada (`python scripts/verificar_despliegue.py`) ejecuta 22 comprobaciones contra los servicios publicados; la última ejecución registrada está en la sección 4.3 de docs/05. La configuración de cada plataforma, las variables de entorno, la verificación, la operación en el plan gratuito y el procedimiento para recrear el despliegue están en [docs/05_Despliegue_y_Operacion_AxiomaH.md](docs/05_Despliegue_y_Operacion_AxiomaH.md).

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Estado general del motor |
| GET | `/api/v1/health` | Salud del servicio y tiempo de actividad |
| POST | `/api/v1/nodo/evaluar` | Evalúa la telemetría de un nodo y devuelve la acción de control |
| POST | `/api/v1/simulacion/ejecutar` | Ejecuta la simulación comparativa entre ambos modos |
| POST | `/api/v1/analisis/barrido-salinidad` | Barrido de salinidad en seis niveles de carga, con media y desviación entre 1 y 5 semillas |
| POST | `/api/v1/analisis/sensibilidad` | Repite la simulación con varios valores de la eficacia del pulso o del flujo de niebla |
| POST | `/api/v1/analisis/incertidumbre` | Muestrea a la vez la eficacia del pulso y el flujo de niebla (5 a 30 muestras) y estima la probabilidad de validar cada conjetura |

Los tres endpoints de análisis no modifican la configuración global del modelo: cada solicitud usa su propia copia inmutable de los parámetros, de modo que solicitudes simultáneas no se afectan entre sí. Los payloads de ejemplo están en [docs/02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](docs/02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md), sección 3.3.

Los datos que no cumplen la validación devuelven `422` con el detalle de cada campo, por ejemplo un `nodo_id` fuera de `NODO_01` a `NODO_08` o una humedad mayor que 100.

### GET /api/v1/health

```json
{
  "estado": "SALUDABLE",
  "servicio": "Axioma-H Engine",
  "version": "0.1.0",
  "timestamp": "2026-10-28T03:01:23.035280+00:00",
  "tiempo_actividad_seg": 0.05
}
```

### POST /api/v1/nodo/evaluar

Solicitud:

```json
{
  "nodo_id": "NODO_04",
  "impedancia_ohms": 1650.5,
  "temperatura_celsius": 36.2,
  "reserva_calor_pct": 55.0,
  "humedad_relativa_pct": 42.0,
  "flujo_actual_ml_min": 14.5,
  "modo_operacion": "NEURO_SIMBOLICO"
}
```

Respuesta:

```json
{
  "nodo_id": "NODO_04",
  "timestamp": "2026-10-28T03:01:23.041067Z",
  "estado_nodo": "CRISTALIZACION_DETECTADA",
  "accion_recomendada": "APLICAR_PULSO_RESISTIVO",
  "pulso_termico_activo": true,
  "temperatura_objetivo_c": 44.0,
  "duracion_pulso_seg": 90,
  "ajuste_caudal_pct": 80.0,
  "regla_activada": "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA",
  "motivo": "Impedancia 1650.5 Ohm sobre el umbral de 1500.0 Ohm: cristalización salina detectada. Se aplica un pulso de 90 s hacia 44.0 °C y el caudal se ajusta al 80 %.",
  "metricas_conjeturas": {
    "eficiencia_energetica_pct": 82.44,
    "recuperacion_hidraulica_pct": 84.32,
    "preservacion_ecologica_ok": true
  }
}
```

La solicitud admite además el campo opcional `anulacion_manual` (`NINGUNA` por defecto, `SUSPENDER_EXTRACCION` o `INHIBIR_PULSO`), que aplica la supervisión humana de la REGLA_06 (ver [Reglas de control](#reglas-de-control)). Con el mismo payload y `"anulacion_manual": "INHIBIR_PULSO"`, la respuesta cambia a `"estado_nodo": "SUPERVISION_HUMANA"`, `"accion_recomendada": "REDUCIR_CAUDAL_SIN_PULSO"`, `"pulso_termico_activo": false`, `"ajuste_caudal_pct": 50.0` y `"regla_activada": "REGLA_06_SUPERVISION_HUMANA"`, y el motivo indica que el motor habría aplicado la REGLA_03 sin la intervención.

### POST /api/v1/simulacion/ejecutar

Solicitud: es el payload de ejemplo del PRD. Los campos `numero_nodos` (1 a 8, por defecto 8), `paso_minutos` (1 a 60, por defecto 5) y `semilla` (por defecto 42) son opcionales.

```json
{
  "duracion_horas": 24,
  "escenario": "TORMENTA_DE_SAL_Y_CALOR_EXTREMO",
  "humedad_ambiente_inicial_pct": 45.0,
  "tasa_salinizacion": "ALTA"
}
```

Respuesta calculada por el modelo (abreviada). Los valores de la respuesta de ejemplo del PRD son ilustrativos.

```json
{
  "comparativa": {
    "modo_neuro_simbolico": {
      "litros_totales_agua": 81.652,
      "pulsos_termicos_ejecutados": 19,
      "consumo_energia_wh": 323.155,
      "integridad_membrana_final_pct": 99.9525,
      "violaciones_ecologicas": 0,
      "recuperacion_caudal_promedio_pct": 88.8126,
      "degradacion_acumulada_pct": 0.0475
    },
    "modo_temporizador_fijo": {
      "litros_totales_agua": 120.408,
      "pulsos_termicos_ejecutados": 88,
      "consumo_energia_wh": 1065.067,
      "integridad_membrana_final_pct": 97.0941,
      "violaciones_ecologicas": 8,
      "recuperacion_caudal_promedio_pct": 91.882,
      "degradacion_acumulada_pct": 2.9059
    },
    "modo_temporizador_tope_ecologico": {
      "litros_totales_agua": 91.784,
      "pulsos_termicos_ejecutados": 88,
      "consumo_energia_wh": 1065.067,
      "integridad_membrana_final_pct": 97.0941,
      "violaciones_ecologicas": 0,
      "recuperacion_caudal_promedio_pct": 93.9574,
      "degradacion_acumulada_pct": 2.9059
    }
  },
  "conjeturas_validadas": {
    "conjetura_1_eficiencia": false,
    "conjetura_2_autorreparacion": false,
    "conjetura_3_saber_territorial": false
  },
  "detalle_verificacion": {
    "conjetura_2_autorreparacion": {
      "validada": false,
      "indicadores": {
        "tiempo_regeneracion_promedio_seg": { "valor": 22263.1579, "umbral": 120.0, "operador": "<", "cumple": false },
        "perdida_integridad_termica_pct": { "valor": 0.0, "umbral": 0.0, "operador": "<=", "cumple": true }
      },
      "indicadores_informativos": {
        "pulsos_regenerados": 0,
        "pulsos_totales": 19,
        "tiempo_desprendimiento_t95_promedio_seg": 64.4395,
        "impedancia_promedio_tras_pulso_ohms": 1125.9662
      },
      "causas_no_validacion": ["DEPENDE_DE_PARAMETRO_SUPUESTO"]
    },
    "...": "conjetura_1_eficiencia y conjetura_3_saber_territorial con la misma estructura"
  },
  "series_temporales": [ { "minuto": 0, "humedad_relativa_pct": 84.85, "...": "..." } ],
  "bitacora": [ { "minuto": 0, "nodo_id": "NODO_01", "regla_activada": "REGLA_05_OPERACION_NOMINAL", "motivo": "..." } ],
  "impacto_comunitario": {
    "modo_neuro_simbolico": {
      "litros_dia_red": 81.652,
      "rendimiento_l_m2_dia": 10.2065,
      "personas_supervivencia": 5.4435,
      "personas_acceso_basico": 4.0826,
      "area_m2_por_persona_basico_literatura_min": 2.0,
      "area_m2_por_persona_basico_literatura_max": 6.6667
    },
    "...": "modo_temporizador_fijo y modo_temporizador_tope_ecologico con la misma estructura"
  }
}
```

`impacto_comunitario` es informativo y no interviene en la validación: traduce el agua de cada modo en personas abastecidas (ver [Impacto comunitario estimado](#impacto-comunitario-estimado)).

Los escenarios disponibles son `DIA_NORMAL`, `INCRUSTACION_SALINA_RAPIDA`, `SEQUIA`, `TORMENTA_DE_ARENA` y `TORMENTA_DE_SAL_Y_CALOR_EXTREMO`. Las tasas de salinización son `BAJA`, `MEDIA` y `ALTA`.

## Reglas de control

Las reglas se evalúan en este orden y la primera que se cumple decide.

| Prioridad | Regla | Condición | Acción | Caudal |
|---|---|---|---|---|
| 1 | REGLA_01_LIMITE_TERMICO_ABSOLUTO | Temperatura >= 45 °C | Corte de emergencia | 0 % |
| 2 | REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL | Humedad < 30 % | Pausa ecológica | 0 % |
| 3 | REGLA_06_SUPERVISION_HUMANA | Anulación del operador: `SUSPENDER_EXTRACCION`, o `INHIBIR_PULSO` con impedancia > 1500 Ω | Suspensión manual, o reducir caudal sin pulso | 0 % o 50 % |
| 4 | REGLA_04_PROTECCION_RESERVA_CRITICA | Reserva < 30 % e impedancia > 1500 Ω | Reducir caudal sin pulso | 50 % |
| 5 | REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA | Impedancia > 1500 Ω y reserva >= 30 % | Pulso resistivo a 44 °C durante 90 s | 80 % |
| 6 | REGLA_05_OPERACION_NOMINAL | Ninguna de las anteriores | Filtración pasiva continua | 100 % |

El caudal se expresa como porcentaje del tope ecológico: el sistema nunca extrae más del 33 % de la niebla disponible. La REGLA_04 se evalúa antes que la REGLA_03 porque ambas comparten la condición de impedancia y la REGLA_04 protege la reserva térmica.

La REGLA_06 aplica la supervisión humana mediante el campo opcional `anulacion_manual` de `POST /api/v1/nodo/evaluar` (`NINGUNA` por defecto). El operador solo puede ser más conservador que el motor: nunca puede forzar extracción ni pulsos, y la REGLA_01 y la REGLA_02 prevalecen sobre su decisión. Con `INHIBIR_PULSO` e impedancia normal, la regla no actúa y decide la REGLA_05. No aplica en modo `TEMPORIZADOR_FIJO` ni en la simulación, donde las decisiones se toman sin operador.

## Pruebas

```powershell
pytest -v
```

La suite cubre el motor de reglas (cada regla, casos límite, prioridad y supervisión humana, incluido que los límites térmico y ecológico prevalecen sobre cualquier anulación), el simulador (reproducibilidad, límites térmico y ecológico, criterio de regeneración, modo de referencia, indicadores informativos y causas de no validación), el impacto comunitario, el análisis de robustez (barrido, sensibilidad, validaciones y ausencia de efectos sobre la configuración global, también con solicitudes simultáneas), la API, el cliente HTTP del dashboard (con `requests` simulado), las transformaciones de datos y el contenido de la vista de investigación. Ninguna prueba usa la red.

### Integración continua y calidad

El workflow [.github/workflows/ci.yml](.github/workflows/ci.yml) se ejecuta en GitHub Actions en cada push a `main` y en cada pull request. Instala las dependencias, ejecuta la suite de pruebas con medición de cobertura de líneas y ramas, y envía los resultados a SonarQube Cloud para el análisis de calidad.

Para medir la cobertura localmente con el mismo criterio del workflow:

```powershell
pip install -r requirements-dev.txt
pytest --cov --cov-report=xml --cov-report=term
```

Render despliega la API y el dashboard solo cuando el workflow CI termina en verde (`autoDeployTrigger: checksPass` en `render.yaml`).

`frontend/app.py` y `scripts/` están excluidos de la cobertura; la justificación está en [docs/03_Funcionamiento_General_AxiomaH.md](docs/03_Funcionamiento_General_AxiomaH.md), sección 10.

## Resultados

Todas las corridas usan las mismas condiciones:

- 24 h, inicio a las 18:00, paso de 5 min;
- 8 nodos, semilla 42, salinización ALTA;
- parámetros sin modificar: eficacia del pulso 0.90 y criterio de regeneración de 1100 Ω.

### Corrida de referencia del PRD (Tormenta de sal y calor extremo, humedad inicial 45 %)

| Métrica | Neuro-simbólico | Temporizador fijo |
|---|---|---|
| Agua captada (L) | 81.65 | 120.41 |
| Pulsos térmicos | 19 | 88 |
| Energía consumida (Wh) | 323.2 | 1065.1 |
| Integridad final (%) | 99.95 | 97.09 |
| Violaciones ecológicas | 0 | 8 |

| Conjetura | Estado | Indicador que no cumple |
|---|---|---|
| C1 Eficiencia | No validada | Recuperación de caudal 88.81 % (umbral 90 %). El ahorro de energía, 79.74 %, sí cumple. |
| C2 Autorreparación | No validada | Tiempo de regeneración 22 263 s (umbral 120 s), con 0 de 19 pulsos regenerados. La pérdida térmica, 0 %, sí cumple. |
| C3 Saber territorial | No validada | Rendimiento nocturno 5.95 L/m²/noche (umbral 12). Las violaciones ecológicas, 0, sí cumplen. |

### Estado de las conjeturas por escenario y humedad inicial

| Escenario | C1 (45 %) | C2 (45 %) | C3 (45 %) | C1 (85 %) | C2 (85 %) | C3 (85 %) |
|---|---|---|---|---|---|---|
| Día normal | No validada | No validada | No validada | No validada | No validada | Validada |
| Incrustación salina rápida | No validada | No validada | No validada | No validada | No validada | No validada |
| Sequía | No validada | No validada | No validada | No validada | No validada | Validada |
| Tormenta de arena | No validada | No validada | No validada | No validada | No validada | Validada |
| Tormenta de sal y calor extremo | No validada | No validada | No validada | No validada | No validada | Validada |

### Interpretación de los resultados

- **C3 (saber territorial):** el modo neuro-simbólico no registró violaciones ecológicas en ningún escenario. La conjetura se valida en cuatro escenarios con 85 % de humedad inicial. Con 45 % no se valida, porque el recurso atmosférico no alcanza: el rendimiento nocturno queda entre 4 y 6 L/m²/noche, y el temporizador tampoco llega a 12 L/m²/noche.
- **C1 (eficiencia):** el ahorro de energía cumple en casi todos los casos, pero la recuperación de caudal tras el pulso queda bajo el 90 %.
- **C2 (autorreparación):**
  - la ausencia de degradación térmica se sostiene en el modelo: 0 % en los diez escenarios;
  - la eficacia de disolución no es verificable por simulación, porque depende de la eficacia del pulso, un parámetro supuesto.
- **Eficacia necesaria:** según el análisis de sensibilidad, validar la C1 requiere que un pulso de 90 s a 44 °C remueva al menos el 78 % de la costra salina (`eta_max` >= 0.94). Validar la C2 requiere al menos el 81 % (`eta_max` >= 0.97). Esa es la medición experimental prioritaria para el siguiente ciclo.
- **Criterio de regeneración:** se endureció de 1500 Ω a 1100 Ω porque el anterior se cumplía trivialmente, y se mantuvo fijo después de ese cambio.

### Barrido de salinidad

Responde la pregunta de investigación. Usa `DIA_NORMAL` e `INCRUSTACION_SALINA_RAPIDA` con tasas BAJA, MEDIA y ALTA y humedad inicial de 85 %, lo que forma un gradiente de carga salina de 20 a 240 Ohm por L/m².

| Carga salina (Ohm por L/m²) | Recuperación neuro / temporizador (%) | Degradación neuro / temporizador (%) |
|---|---|---|
| 20 | 88.85 / 95.84 | 0.020 / 2.071 |
| 40 | 88.83 / 91.83 | 0.052 / 2.071 |
| 60 | 88.80 / 88.02 | 0.082 / 2.117 |
| 80 | 88.78 / 84.45 | 0.115 / 2.427 |
| 120 | 88.02 / 78.02 | 0.408 / 3.070 |
| 240 | 85.92 / 63.21 | 1.073 / 4.117 |

El control neuro-simbólico reduce la degradación acumulada entre 74 % y 99 % en todos los niveles. Su recuperación se mantiene estable, mientras que la del temporizador cae con la salinidad: el temporizador recupera más con salinidad baja, porque limpia membranas casi limpias, y el neuro-simbólico lo supera desde 60 Ohm por L/m². El método y las limitaciones están en [docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 7.

### Tope ecológico frente a lógica de control

Cada simulación ejecuta además un temporizador con tope ecológico: la misma programación del temporizador fijo, con la fracción de 0.33 del neuro-simbólico. Se reporta en `comparativa.modo_temporizador_tope_ecologico` y no interviene en la validación. Permite separar la diferencia de agua entre los dos modos en la parte debida al tope y la parte debida a la lógica de control.

| Corrida | Neuro-simbólico (L) | Temporizador 0.45 (L) | Temporizador 0.33 (L) | Brecha debida al tope |
|---|---|---|---|---|
| Tormenta de sal y calor extremo, humedad 45 % | 81.7 | 120.4 | 91.8 | 73.9 % |
| Día normal, humedad 85 % | 254.6 | 340.4 | 266.1 | 86.6 % |

En los cinco escenarios, el tope explica entre 69.8 % y 89.8 % de la brecha con humedad inicial de 45 %, y entre 76.2 % y 90.8 % con 85 %. El menor rendimiento del neuro-simbólico es, sobre todo, el costo del límite ecológico, no de la lógica de control. El tope por sí solo tampoco evita las violaciones: en Sequía, el temporizador con tope registra 8, porque no tiene pausa ecológica.

### Impacto comunitario estimado

Cada simulación traduce el agua captada en personas abastecidas (`impacto_comunitario`), con el acceso básico de la OMS (20 L por persona al día, Howard et al., 2020) y el mínimo humanitario de Sphere (15 L por persona al día, estándar 2.1). Es un indicador informativo y no interviene en la validación.

| Corrida | L por día (neuro / temporizador) | L/m² al día del neuro | Personas con 20 L (neuro / temporizador / temporizador 0.33) |
|---|---|---|---|
| Tormenta de sal y calor extremo, humedad 45 % | 81.7 / 120.4 | 10.21 | 4.1 / 6.0 / 4.6 |
| Día normal, humedad 85 % | 254.6 / 340.4 | 31.83 | 12.7 / 17.0 / 13.3 |

- Con el flujo de niebla supuesto y humedad inicial de 85 %, la red de 8 m² abastecería a unas 12 personas en Día normal, y entre 7.5 y 12.7 según el escenario. Con 45 %, entre 2.0 y 4.1.
- El rendimiento simulado con 85 % (18.7 a 31.8 L/m² al día) supera el rango de 3 a 10 L/m² al día de proyectos reales (Klemm et al., 2012). Con esos rendimientos harían falta de 2 a 6.7 m² de colector por persona.
- El tope ecológico reduce las personas abastecidas frente al temporizador: entre 2.8 y 4.3 personas menos con 85 % y entre 1.1 y 2.2 con 45 %.

La tabla de los diez casos y su interpretación están en [docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 7.6. El origen del tope del 33 % y el protocolo de co-creación propuesto para el Ciclo 3 están en [docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.7.

### Calibración del flujo de niebla e incertidumbre

El flujo de niebla supuesto, 6.0 L/m²/h, da 31.8 L/m²/día en Día normal con 85 %, frente a 3 a 10 L/m²/día en proyectos reales (Klemm et al., 2012). Una calibración inversa por bisección (`calibrar_flujo_niebla`) encuentra los flujos que reproducen ese rango: 0.49 a 1.83 L/m²/h. El valor por defecto del modelo no cambia (decisión D5); el rango calibrado solo se usa en el análisis de incertidumbre. Con el flujo calibrado, la C3 no se valida en Día normal con 85 %: el rendimiento nocturno baja a entre 1.67 y 5.47 L/m²/noche.

`POST /api/v1/analisis/incertidumbre` muestrea a la vez la eficacia del pulso (0.80 a 1.00) y el flujo calibrado. Con 20 muestras, humedad inicial de 85 % y tasa ALTA:

| Escenario | P(C1) | P(C2) | P(C3) | Muestras con pulsos | Reducción de la degradación (p5 a p95) |
|---|---|---|---|---|---|
| Día normal | 0.05 | 0.00 | 0.00 | 8 de 20 | 99.0 % a 100 % |
| Incrustación salina rápida | 0.15 | 0.10 | 0.00 | 20 de 20 | 95.7 % a 99.0 % |
| Sequía | 0.00 | 0.00 | 0.00 | 0 de 20 | 100 % |
| Tormenta de arena | 0.00 | 0.00 | 0.00 | 20 de 20 | 97.2 % a 98.6 % |
| Tormenta de sal y calor extremo | 0.10 | 0.05 | 0.00 | 14 de 20 | 98.6 % a 100 % |

Las probabilidades son proporciones del espacio de parámetros supuesto, no predicciones de campo. Con menos niebla hay menos sal y muchas corridas no aplican pulsos, de modo que C1 y C2 quedan sin datos en lugar de refutarse. La menor degradación del control neuro-simbólico se mantiene en todas las muestras. El método y la interpretación están en [docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), secciones 8.6 y 8.7.

### Indicadores informativos y causas de no validación

Cada conjetura informa indicadores adicionales que no intervienen en la validación, y la causa de cada indicador que no cumple (`causas_no_validacion`):

- **C1:** reducción de la degradación frente al temporizador, que corresponde al enunciado de vida útil. Va de 73.9 % a 100 % en las diez corridas.
- **C2:** el pulso logra el 95 % de su remoción en 64.4 s (cinética, bajo el umbral de 120 s), pero deja la impedancia en unos 1126 Ohm (extensión, sobre el criterio de 1100 Ohm). La conjetura falla por la extensión de la limpieza, no por la cinética.
- **C3:** rendimiento nocturno del temporizador. Con 45 % tampoco alcanza 12 L/m²/noche, por lo que la causa es el límite del recurso atmosférico.

Las causas de no validación son, en las diez corridas: dependencia de un parámetro supuesto en C1 y C2 (o falta de datos cuando no hay pulsos, en Sequía con 45 %), límite del recurso atmosférico en C3 con 45 % y desempeño del control en dos casos de Incrustación salina rápida con 85 % (ahorro de energía de C1 y rendimiento nocturno de C3). El detalle está en [docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md), secciones 4, 8.4 y 8.5.

El análisis completo, las ecuaciones, los parámetros y las tablas de sensibilidad están en [docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md](docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md).

## Limitaciones conocidas

- Los resultados provienen de un modelo simulado, no de mediciones en campo.
- La eficacia del pulso resistivo (0.90) y los demás parámetros físicos (flujo de niebla, tasas de incrustación, capacidad térmica, consumo y recarga de energía, degradación de la membrana) son supuestos de orden de magnitud pendientes de validación experimental.
- El estado de las Conjeturas 1 y 2 cambia con la eficacia del pulso, como muestran los análisis de sensibilidad. Medir esa eficacia es la prioridad experimental antes de dar por validada o refutada cualquiera de las dos.
- El flujo de niebla supuesto es optimista. Calibrado contra la literatura, la Conjetura 3 no se valida en ningún escenario con 85 % de humedad inicial.
- El clima de referencia usa ciclos diurnos idealizados con ruido gaussiano, y los escenarios repiten sus ventanas de sequía o tormenta cada día simulado.
- La configuración CORS admite por defecto solo orígenes locales. Para que una página web consuma la API desde el navegador, sus dominios deben agregarse con `AXIOMA_CORS_ORIGINS`.
- En el plan gratuito de Render, los servicios se suspenden tras 15 minutos sin tráfico y tardan cerca de un minuto en reactivarse.

## Alcance y madurez

El artefacto es una prueba de concepto analítica por simulación, equivalente de forma aproximada a un nivel de madurez tecnológica TRL 2-3. No hay prototipo físico ni datos de campo. El horizonte del siguiente ciclo es medir en laboratorio la fracción de costra salina que remueve un pulso de 90 s a 44 °C.

- Alcance y madurez: [docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.8.
- Perspectivas social, ética, cultural y humana, incluida la consulta previa pendiente antes de cualquier piloto en territorio Wayuu: [docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.7.

## Referencias y créditos

El software de terceros con su uso, URL y licencia, las fuentes científicas usadas para contrastar el flujo de niebla (Klemm et al., 2012) y para estimar el impacto comunitario (OMS, Howard et al., 2020; Sphere, 2018), y la trazabilidad de cada parámetro de `backend/config.py` están en [docs/06_Referencias_y_Trazabilidad_AxiomaH.md](docs/06_Referencias_y_Trazabilidad_AxiomaH.md). El proyecto se distribuye con licencia MIT (archivo `LICENSE`).
