# Axioma-H Engine

Axioma-H Engine es un motor de control neuro-simbólico para nodos de captación pasiva de agua atmosférica. A partir de la telemetría de cada nodo (impedancia de la membrana, temperatura de la matriz, reserva de calor y humedad relativa), el motor decide si filtrar de forma continua, aplicar un pulso resistivo para desprender la sal cristalizada, reducir el caudal o detener la extracción para proteger la membrana y el ecosistema.

El proyecto incluye una API REST y un dashboard simulador. El simulador compara el control neuro-simbólico con un temporizador fijo tradicional bajo cinco escenarios ambientales de referencia de Cabo de la Vela (La Guajira). Con esa comparación se verifican las tres conjeturas de investigación del Ciclo 2.

Lo desarrolla el equipo AXIOMA en el curso Fundamentos de Investigación de la Universidad de Antioquia (UdeA), Ciclo 2.

## Arquitectura

El sistema se compone de dos servicios que se ejecutan por separado:

- **Backend (FastAPI, puerto 8000):** contiene el motor de reglas, el modelo físico, el simulador comparativo y la verificación de conjeturas.
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
│   └── routers/
│       ├── nodo.py         POST /api/v1/nodo/evaluar
│       └── simulacion.py   POST /api/v1/simulacion/ejecutar
├── frontend/
│   ├── app.py              Dashboard Streamlit
│   ├── config.py           URL de la API y tiempos de espera
│   ├── cliente_api.py      Cliente HTTP con manejo de errores
│   └── transformaciones.py Conversión de respuestas en DataFrames
├── tests/                  Pruebas con pytest
├── docs/
│   ├── 01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md
│   ├── 02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md
│   └── modelo_simulacion.md
├── pytest.ini
└── requirements.txt
```

## Requisitos

- Windows 10 u 11.
- Python 3.11 o superior.
- Las dependencias de `requirements.txt`: FastAPI, Uvicorn, Pydantic v2, Streamlit, Requests, pandas, pytest y httpx.

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

### Variable AXIOMA_API_URL

El dashboard se conecta por defecto a `http://127.0.0.1:8000`. Para usar otra dirección, defina la variable antes de iniciar Streamlit:

```powershell
$env:AXIOMA_API_URL = "http://192.168.1.50:8000"
streamlit run frontend/app.py
```

Los tiempos de espera son de 10 s para la evaluación de nodos y de 60 s para la simulación (`frontend/config.py`).

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Estado general del motor |
| GET | `/api/v1/health` | Salud del servicio y tiempo de actividad |
| POST | `/api/v1/nodo/evaluar` | Evalúa la telemetría de un nodo y devuelve la acción de control |
| POST | `/api/v1/simulacion/ejecutar` | Ejecuta la simulación comparativa entre ambos modos |

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
      "violaciones_ecologicas": 0
    },
    "modo_temporizador_fijo": {
      "litros_totales_agua": 120.408,
      "pulsos_termicos_ejecutados": 88,
      "consumo_energia_wh": 1065.067,
      "integridad_membrana_final_pct": 97.0941,
      "violaciones_ecologicas": 8
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
      "indicadores_informativos": { "pulsos_regenerados": 0, "pulsos_totales": 19 }
    },
    "...": "conjetura_1_eficiencia y conjetura_3_saber_territorial con la misma estructura"
  },
  "series_temporales": [ { "minuto": 0, "humedad_relativa_pct": 84.85, "...": "..." } ],
  "bitacora": [ { "minuto": 0, "nodo_id": "NODO_01", "regla_activada": "REGLA_05_OPERACION_NOMINAL", "motivo": "..." } ]
}
```

Los escenarios disponibles son `DIA_NORMAL`, `INCRUSTACION_SALINA_RAPIDA`, `SEQUIA`, `TORMENTA_DE_ARENA` y `TORMENTA_DE_SAL_Y_CALOR_EXTREMO`. Las tasas de salinización son `BAJA`, `MEDIA` y `ALTA`.

## Reglas de control

Las reglas se evalúan en este orden y la primera que se cumple decide.

| Prioridad | Regla | Condición | Acción | Caudal |
|---|---|---|---|---|
| 1 | REGLA_01_LIMITE_TERMICO_ABSOLUTO | Temperatura >= 45 °C | Corte de emergencia | 0 % |
| 2 | REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL | Humedad < 30 % | Pausa ecológica | 0 % |
| 3 | REGLA_04_PROTECCION_RESERVA_CRITICA | Reserva < 30 % e impedancia > 1500 Ω | Reducir caudal sin pulso | 50 % |
| 4 | REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA | Impedancia > 1500 Ω y reserva >= 30 % | Pulso resistivo a 44 °C durante 90 s | 80 % |
| 5 | REGLA_05_OPERACION_NOMINAL | Ninguna de las anteriores | Filtración pasiva continua | 100 % |

El caudal se expresa como porcentaje del tope ecológico: el sistema nunca extrae más del 33 % de la niebla disponible. La REGLA_04 se evalúa antes que la REGLA_03 porque ambas comparten la condición de impedancia y la REGLA_04 protege la reserva térmica.

## Pruebas

```powershell
pytest -v
```

La suite cubre el motor de reglas (cada regla, casos límite y prioridad), el simulador (reproducibilidad, límites térmico y ecológico, criterio de regeneración), la API, el cliente HTTP del dashboard (con `requests` simulado) y las transformaciones de datos.

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

El análisis completo, las ecuaciones, los parámetros y las tablas de sensibilidad están en [docs/modelo_simulacion.md](docs/modelo_simulacion.md).

## Limitaciones conocidas

- Los resultados provienen de un modelo simulado, no de mediciones en campo.
- La eficacia del pulso resistivo (0.90) y los demás parámetros físicos (flujo de niebla, tasas de incrustación, capacidad térmica, consumo y recarga de energía, degradación de la membrana) son supuestos de orden de magnitud pendientes de validación experimental.
- El estado de las Conjeturas 1 y 2 cambia con la eficacia del pulso, como muestran los análisis de sensibilidad. Medir esa eficacia es la prioridad experimental antes de dar por validada o refutada cualquiera de las dos.
- El clima de referencia usa ciclos diurnos idealizados con ruido gaussiano, y los escenarios repiten sus ventanas de sequía o tormenta cada día simulado.
- La configuración CORS admite solo orígenes locales y debe restringirse antes de cualquier despliegue en producción.
