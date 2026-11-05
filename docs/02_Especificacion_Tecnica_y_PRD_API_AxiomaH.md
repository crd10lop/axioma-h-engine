# Especificación Técnica y PRD: API Neuro-Simbólica y Dashboard Simulator (Axioma-H)
**Proyecto:** Axioma-H — Captación Pasiva de Agua Atmosférica  
**Equipo:** AXIOMA — Curso Fundamentos de Investigación (UdeA)  
**Ciclo:** 2 — Operacionalización, Simulación y Verificación de Conjeturas  
**Repositorio:** https://github.com/crd10lop/axioma-h-engine  
**Aplicación desplegada:** [Dashboard](https://axioma-h-dashboard.onrender.com) | [API, documentación interactiva](https://axioma-h-api.onrender.com/docs)  

---

## 1. Visión General del Sistema

El sistema **Axioma-H** es un prototipo de captación pasiva de humedad atmosférica diseñado para el ecosistema árido de Cabo de la Vela (La Guajira). En este Ciclo 2, la API actúa como el **motor de control neuro-simbólico** que procesa la telemetría de 8 nodos de la matriz de nanomateriales (nanorredes MOFs y membranas biomiméticas de acuaporinas) y toma decisiones de operación en tiempo real.

Este documento sirve como **Documento de Requerimientos de Producto (PRD) y Especificación de Arquitectura** para ser procesado directamente en **VS Code con Claude Pro / Claude Code**.

---

## 2. Arquitectura del Sistema (Backend & Frontend)

### 2.1 Stack Recomendado para Desarrollo Rápido
* **Backend API:** Python 3.11+ con **FastAPI** (o Flask) y `pydantic` para validación de esquemas.
* **Motor de Reglas:** Lógica Neuro-Simbólica determinista combinada con estimador de impedancia/salinidad.
* **Frontend Dashboard:** **Streamlit** (para interfaz en Python puro en 1 solo archivo) O **HTML5 + TailwindCSS + Chart.js** alimentado por la API REST.

---

## 3. Especificación de la API REST (Endpoints)

### 3.1 Endpoint Principal: Evaluar Telemetría del Nodo
* **Ruta:** `POST /api/v1/nodo/evaluar`
* **Descripción:** Recibe lecturas de sensores de un nodo y retorna la acción de control calculada por las reglas neuro-simbólicas.

#### Request Payload (`TelemetryInput`):
```json
{
  "nodo_id": "NODO_01",
  "impedancia_ohms": 1650.5,
  "temperatura_celsius": 36.2,
  "reserva_calor_pct": 55.0,
  "humedad_relativa_pct": 42.0,
  "flujo_actual_ml_min": 14.5,
  "modo_operacion": "NEURO_SIMBOLICO"
}
```

#### Response Payload (`ControlDecision`):
```json
{
  "nodo_id": "NODO_01",
  "timestamp": "2026-10-28T08:30:00Z",
  "estado_nodo": "CRISTALIZACION_DETECTADA",
  "accion_recomendada": "APLICAR_PULSO_RESISTIVO",
  "pulso_termico_activo": true,
  "temperatura_objetivo_c": 44.0,
  "duracion_pulso_seg": 90,
  "ajuste_caudal_pct": 80.0,
  "regla_activada": "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA",
  "motivo": "Impedancia 1650.5 Ohm sobre el umbral de 1500.0 Ohm: cristalización salina detectada. Se aplica un pulso de 90 s hacia 44.0 °C y el caudal se ajusta al 80 %.",
  "metricas_conjeturas": {
    "eficiencia_energetica_pct": 92.4,
    "recuperacion_hidraulica_pct": 88.0,
    "preservacion_ecologica_ok": true
  }
}
```

---

### 3.2 Endpoint: Simulación de Experimentos (Verificación de Conjeturas)
* **Ruta:** `POST /api/v1/simulacion/ejecutar`
* **Descripción:** Corre un ciclo de prueba de 24 horas simuladas comparando el modo Neuro-Simbólico contra un Temporizador Fijo para validar las 3 conjeturas.

#### Request Payload (`SimulationConfig`):
```json
{
  "duracion_horas": 24,
  "escenario": "TORMENTA_DE_SAL_Y_CALOR_EXTREMO",
  "humedad_ambiente_inicial_pct": 45.0,
  "tasa_salinizacion": "ALTA"
}
```

#### Response Payload (`SimulationResult`):
```json
{
  "comparativa": {
    "modo_neuro_simbolico": {
      "litros_totales_agua": 18.4,
      "pulsos_termicos_ejecutados": 3,
      "consumo_energia_wh": 120,
      "integridad_membrana_final_pct": 94.0,
      "violaciones_ecologicas": 0
    },
    "modo_temporizador_fijo": {
      "litros_totales_agua": 11.2,
      "pulsos_termicos_ejecutados": 12,
      "consumo_energia_wh": 480,
      "integridad_membrana_final_pct": 68.0,
      "violaciones_ecologicas": 4
    }
  },
  "conjeturas_validadas": {
    "conjetura_1_eficiencia": true,
    "conjetura_2_autorreparacion": true,
    "conjetura_3_saber_territorial": true
  }
}
```

---

### 3.3 Endpoints: Análisis de Robustez

Estos endpoints se agregaron en la implementación del Ciclo 2 y no forman parte de la especificación original. Ninguno modifica la configuración global del modelo: cada solicitud construye su propia copia inmutable de los parámetros (`ParametrosModelo`), por lo que solicitudes simultáneas no comparten estado. Las corridas individuales se guardan en una caché de hasta 256 resultados.

#### Barrido de salinidad
* **Ruta:** `POST /api/v1/analisis/barrido-salinidad`
* **Descripción:** Simula `DIA_NORMAL` e `INCRUSTACION_SALINA_RAPIDA` con las tasas BAJA, MEDIA y ALTA (cargas de 20 a 240 Ohm por L/m²), una vez por semilla, y entrega la media y la desviación estándar muestral de la recuperación tras pulso y de la degradación de ambos modos, ordenadas por carga salina. Cada punto informa además el rendimiento del neuro-simbólico, la incrustación diaria (carga salina por ese rendimiento, en Ohm por día), la ventaja en recuperación (neuro-simbólico menos temporizador, en puntos) y los pulsos del neuro-simbólico. El resultado informa el flujo de niebla y la eficacia usados y el cruce de la ventaja en recuperación frente a la incrustación diaria (`docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md`, sección 8.8).

##### Request Payload (`BarridoConfig`):
Todos los campos son opcionales. `semillas` admite de 1 a 5 valores sin repetir; con una sola semilla la desviación es 0. `flujo_niebla_maximo_l_m2_h` (en (0, 20]) y `eficacia_maxima_pulso` (en (0, 1]) son nulos por defecto, y entonces se usan los valores de `backend/config.py`.
```json
{
  "humedad_ambiente_inicial_pct": 85.0,
  "duracion_horas": 24,
  "numero_nodos": 8,
  "semillas": [42]
}
```

##### Response Payload (`BarridoResultado`), primer punto de seis:
```json
{
  "puntos": [
    {
      "escenario": "DIA_NORMAL",
      "tasa_salinizacion": "BAJA",
      "carga_salina_ohm_l_m2": 20.0,
      "n_semillas": 1,
      "recuperacion_neuro_media": 88.8549,
      "recuperacion_neuro_desv": 0.0,
      "recuperacion_temporizador_media": 95.8389,
      "recuperacion_temporizador_desv": 0.0,
      "degradacion_neuro_media": 0.02,
      "degradacion_neuro_desv": 0.0,
      "degradacion_temporizador_media": 2.0707,
      "degradacion_temporizador_desv": 0.0,
      "reduccion_desgaste_pct": 99.0341,
      "rendimiento_neuro_l_m2_dia_media": 33.33,
      "incrustacion_diaria_ohm_media": 666.6,
      "ventaja_recuperacion_pts": -6.984,
      "pulsos_neuro_media": 8.0
    }
  ],
  "flujo_niebla_maximo_l_m2_h": 6.0,
  "eficacia_maxima_pulso": 0.9,
  "cruce": {
    "estado": "INTERPOLADO",
    "incrustacion_diaria_ohm": 1789.1225,
    "carga_salina_ohm_l_m2": 55.8891
  }
}
```

`cruce.estado` es `INTERPOLADO` si la ventaja pasa de <= 0 a > 0 al crecer la incrustación diaria, `CRUCE_DESCENDENTE` si solo pasa de > 0 a <= 0, `SIN_CRUCE_NEURO_SUPERIOR` o `SIN_CRUCE_NEURO_INFERIOR` si no cambia de signo, y `SIN_DATOS` con menos de dos puntos con ventaja.

#### Robustez de la respuesta
* **Ruta:** `POST /api/v1/analisis/robustez-respuesta`
* **Descripción:** Repite el barrido de salinidad con cada combinación de tres flujos de niebla (6.0, 1.83 y 0.49 L/m²/h) y tres eficacias del pulso (0.80, 0.90 y 1.00), y resume el rango de la reducción del desgaste, el número de combinaciones con cruce `INTERPOLADO` y el rango de la incrustación diaria de esos cruces.

##### Request Payload (`RobustezConfig`):
Todos los campos son opcionales: `humedad_ambiente_inicial_pct` (85), `duracion_horas` (24, de 24 a 72), `numero_nodos` (8, de 1 a 8) y `semillas` ([42], de 1 a 3 valores sin repetir).
```json
{
  "humedad_ambiente_inicial_pct": 85.0,
  "semillas": [42]
}
```

##### Response Payload (`RobustezResultado`), primera combinación de nueve y último punto de seis:
```json
{
  "combinaciones": [
    {
      "flujo_niebla_maximo_l_m2_h": 6.0,
      "eficacia_maxima_pulso": 0.8,
      "barrido": {
        "puntos": [
          {
            "escenario": "INCRUSTACION_SALINA_RAPIDA",
            "tasa_salinizacion": "ALTA",
            "carga_salina_ohm_l_m2": 240.0,
            "n_semillas": 1,
            "recuperacion_neuro_media": 82.5117,
            "recuperacion_temporizador_media": 58.7313,
            "degradacion_neuro_media": 1.136,
            "degradacion_temporizador_media": 4.2478,
            "reduccion_desgaste_pct": 73.2567,
            "rendimiento_neuro_l_m2_dia_media": 22.3664,
            "incrustacion_diaria_ohm_media": 5367.936,
            "ventaja_recuperacion_pts": 23.7804,
            "pulsos_neuro_media": 104.0,
            "...": "desviaciones con la misma estructura del barrido"
          }
        ],
        "flujo_niebla_maximo_l_m2_h": 6.0,
        "eficacia_maxima_pulso": 0.8,
        "cruce": {"estado": "INTERPOLADO", "incrustacion_diaria_ohm": 1819.8228, "carga_salina_ohm_l_m2": 57.5769}
      }
    }
  ],
  "reduccion_desgaste_min_pct": 73.2567,
  "reduccion_desgaste_max_pct": 100.0,
  "combinaciones_con_cruce": 6,
  "incrustacion_diaria_cruce_min_ohm": 1632.8705,
  "incrustacion_diaria_cruce_max_ohm": 1839.2066
}
```

#### Dimensionamiento del captador
* **Ruta:** `POST /api/v1/analisis/dimensionamiento`
* **Descripción:** Simula 24 h con 8 nodos para cada uno de los tres flujos de referencia (6.0 L/m²/h supuesto y 1.83 y 0.49 L/m²/h calibrados) y calcula el área de colector (`personas * consumo / rendimiento del neuro-simbólico`) y los nodos de 1 m² necesarios para abastecer a las personas indicadas. Informa además el área con los rendimientos de 10 y 3 L/m² al día de Klemm et al. (2012).

##### Request Payload (`DimensionamientoConfig`):
`personas` (1 a 1000), `escenario` y `humedad_ambiente_inicial_pct` son obligatorios. Son opcionales `estandar` (`OMS_20`, 20 L por persona al día, por defecto, o `SPHERE_15`, 15 L), `tasa_salinizacion` (ALTA) y `semilla` (42).
```json
{
  "personas": 50,
  "estandar": "OMS_20",
  "escenario": "DIA_NORMAL",
  "humedad_ambiente_inicial_pct": 85.0
}
```

##### Response Payload (`DimensionamientoResultado`):
```json
{
  "consumo_l_persona_dia": 20.0,
  "dimensiones": [
    {"origen_flujo": "SUPUESTO", "flujo_niebla_maximo_l_m2_h": 6.0, "rendimiento_neuro_l_m2_dia": 31.8254, "area_colector_m2": 31.4214, "nodos_requeridos": 32},
    {"origen_flujo": "CALIBRADO_MAX", "flujo_niebla_maximo_l_m2_h": 1.83, "rendimiento_neuro_l_m2_dia": 10.0169, "area_colector_m2": 99.8313, "nodos_requeridos": 100},
    {"origen_flujo": "CALIBRADO_MIN", "flujo_niebla_maximo_l_m2_h": 0.49, "rendimiento_neuro_l_m2_dia": 3.0171, "area_colector_m2": 331.4441, "nodos_requeridos": 332}
  ],
  "area_literatura_min_m2": 100.0,
  "area_literatura_max_m2": 333.3333
}
```

Si el rendimiento de un flujo es 0, por ejemplo sin humedad, `area_colector_m2` y `nodos_requeridos` son nulos.

#### Sensibilidad a un parámetro supuesto
* **Ruta:** `POST /api/v1/analisis/sensibilidad`
* **Descripción:** Repite la simulación con cada valor del parámetro elegido, manteniendo los demás en su valor base, y entrega el estado de las tres conjeturas y sus indicadores principales.

##### Request Payload (`SensibilidadConfig`):
`parametro` es `EFICACIA_MAXIMA_PULSO` (valores en (0, 1]) o `FLUJO_NIEBLA_MAXIMO` (valores en (0, 20] L/m²/h). `valores` admite de 1 a 11 elementos. `duracion_horas` (por defecto 24) y `semilla` (por defecto 42) son opcionales.
```json
{
  "escenario": "DIA_NORMAL",
  "humedad_ambiente_inicial_pct": 85.0,
  "tasa_salinizacion": "ALTA",
  "parametro": "EFICACIA_MAXIMA_PULSO",
  "valores": [0.90, 0.94, 0.97]
}
```

##### Response Payload (`SensibilidadResultado`):
```json
{
  "parametro": "EFICACIA_MAXIMA_PULSO",
  "puntos": [
    {
      "valor": 0.9,
      "conjeturas_validadas": {"conjetura_1_eficiencia": false, "conjetura_2_autorreparacion": false, "conjetura_3_saber_territorial": true},
      "recuperacion_caudal_promedio_pct": 88.7829,
      "tiempo_regeneracion_promedio_seg": 11934.7826,
      "rendimiento_nocturno_l_m2_noche": 16.9708,
      "litros_neuro": 254.603
    },
    {
      "valor": 0.94,
      "conjeturas_validadas": {"conjetura_1_eficiencia": true, "conjetura_2_autorreparacion": false, "conjetura_3_saber_territorial": true},
      "recuperacion_caudal_promedio_pct": 90.1218,
      "tiempo_regeneracion_promedio_seg": 12200.0,
      "rendimiento_nocturno_l_m2_noche": 17.0404,
      "litros_neuro": 256.139
    },
    {
      "valor": 0.97,
      "conjeturas_validadas": {"conjetura_1_eficiencia": true, "conjetura_2_autorreparacion": true, "conjetura_3_saber_territorial": true},
      "recuperacion_caudal_promedio_pct": 91.1441,
      "tiempo_regeneracion_promedio_seg": 84.4935,
      "rendimiento_nocturno_l_m2_noche": 17.0973,
      "litros_neuro": 257.131
    }
  ]
}
```

#### Propagación de la incertidumbre
* **Ruta:** `POST /api/v1/analisis/incertidumbre`
* **Descripción:** Muestrea a la vez la eficacia máxima del pulso y el flujo máximo de niebla con distribución uniforme, simula una corrida por muestra y entrega la proporción de muestras que validan cada conjetura y los percentiles 5, 50 y 95 de la recuperación tras pulso, el rendimiento del neuro-simbólico en L/m²/día y la reducción de la degradación. Los percentiles ignoran las muestras sin datos, por ejemplo las corridas sin pulsos. La regla de validación y los valores por defecto del modelo no cambian.

##### Request Payload (`IncertidumbreConfig`):
`escenario`, `humedad_ambiente_inicial_pct` y `tasa_salinizacion` son obligatorios. Son opcionales `duracion_horas` (24), `semilla` del entorno (42), `semilla_muestreo` (7), `n_muestras` (20, de 5 a 30) y los rangos `eficacia_min` y `eficacia_max` (0.80 y 1.00, en (0, 1]) y `flujo_min` y `flujo_max` (0.49 y 1.83 L/m²/h, en (0, 20]). El mínimo de cada rango debe ser menor que el máximo.
```json
{
  "escenario": "INCRUSTACION_SALINA_RAPIDA",
  "humedad_ambiente_inicial_pct": 85.0,
  "tasa_salinizacion": "ALTA",
  "n_muestras": 5
}
```

##### Response Payload (`IncertidumbreResultado`), primera muestra de cinco:
```json
{
  "probabilidad_c1": 0.0,
  "probabilidad_c2": 0.0,
  "probabilidad_c3": 0.0,
  "recuperacion": {"p5": 85.8929, "p50": 87.7029, "p95": 89.7203, "n_validos": 5},
  "rendimiento": {"p5": 3.3393, "p50": 5.2756, "p95": 6.1043, "n_validos": 5},
  "reduccion_degradacion": {"p5": 96.8126, "p50": 97.7061, "p95": 98.9134, "n_validos": 5},
  "muestras": [
    {
      "eficacia": 0.8648,
      "flujo": 0.6921,
      "conjeturas_validadas": {"conjetura_1_eficiencia": false, "conjetura_2_autorreparacion": false, "conjetura_3_saber_territorial": false},
      "recuperacion_caudal_promedio_pct": 87.7029,
      "rendimiento_l_m2_dia": 3.7478,
      "reduccion_degradacion_pct": 98.4305,
      "recuperacion_temporizador_pct": 93.7002,
      "ventaja_recuperacion_pts": -5.9973
    }
  ],
  "ventaja_recuperacion": {"p5": -5.9291, "p50": -3.2141, "p95": -2.4391, "n_validos": 5},
  "probabilidad_ventaja_recuperacion": 0.0
}
```

`probabilidad_ventaja_recuperacion` es la proporción de las muestras con ambas recuperaciones en que la ventaja del neuro-simbólico es positiva; es nula si ninguna muestra tiene ambas.

#### Perfiles de sitio
* **Ruta:** `GET /api/v1/sitios`
* **Descripción:** Devuelve los perfiles de sitio de referencia que acepta el campo `sitio` de `SimulationConfig`: Cabo de la Vela con el flujo supuesto y con los dos extremos calibrados. No se incluyen otros sitios porque el proyecto no tiene datos climáticos con fuente para ellos.

##### Response Payload (lista de `PerfilSitio`), primer perfil de tres:
```json
[
  {
    "nombre": "CABO_DE_LA_VELA",
    "flujo_niebla_maximo_l_m2_h": 6.0,
    "temperatura_media_c": 30.0,
    "amplitud_temperatura_c": 4.5,
    "amplitud_humedad_pct": 10.0
  }
]
```

Los otros dos perfiles, `CABO_DE_LA_VELA_CALIBRADO_MAX` y `CABO_DE_LA_VELA_CALIBRADO_MIN`, solo cambian el flujo a 1.83 y 0.49 L/m²/h.

Los valores de los ejemplos son los que calcula el modelo y coinciden con `docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md`, secciones 5.6, 5.7, 7.3, 7.7, 8.7 y 8.8. Una configuración inválida (semillas repetidas, más de 5 semillas en el barrido o más de 3 en la robustez, duración de la robustez fuera de 24 a 72 h, eficacia igual a 0 o mayor que 1, flujo fuera de (0, 20], rangos invertidos, un número de muestras fuera de 5 a 30, o personas fuera de 1 a 1000) devuelve `422`.

---

## 4. Matriz de Reglas Neuro-Simbólicas (Lógica del Core)

1. **REGLA 01 — Límite Térmico Absoluto (Seguridad de la Matriz):**
   * *Condición:* `temperatura_celsius >= 45.0`
   * *Acción:* `CORTE_DE_EMERGENCIA`, `pulso_termico = False`.
   * *Motivo:* Evita la degradación irreversible de las acuaporinas sintéticas.

2. **REGLA 02 — Límite Ecológico Territorial (Respeto al Ecosistema Wayuu):**
   * *Condición:* `humedad_relativa_pct < 30.0`
   * *Acción:* `PAUSA_ECOLOGICA`, `ajuste_caudal_pct = 0.0`.
   * *Motivo:* Garantiza la disponibilidad de niebla para la vegetación local (trupillo y cardón). No extrae más del 33% del flujo.

3. **REGLA 03 — Detección y Limpieza de Cristalización Salina:**
   * *Condición:* `impedancia_ohms > 1500.0` Y `reserva_calor_pct >= 30.0`
   * *Acción:* `APLICAR_PULSO_RESISTIVO`, `duracion_pulso_seg = 90`.
   * *Motivo:* Remueve la costra de sal regenerando la conductancia hidráulica de la membrana.

4. **REGLA 04 — Protección de Reserva de Calor Crítica:**
   * *Condición:* `reserva_calor_pct < 30.0` Y `impedancia_ohms > 1500.0`
   * *Acción:* `REDUCIR_CAUDAL_SIN_PULSO`, `ajuste_caudal_pct = 50.0`.
   * *Motivo:* Prioriza mantener viva la red antes que gastar la última reserva de calor en un pulso completo.

5. **REGLA 05 — Operación Nominal Silenciosa:**
   * *Condición:* Todos los parámetros en rango normal.
   * *Acción:* `FILTRACION_PASIVA_CONTINUA`, `ajuste_caudal_pct = 100.0`.

6. **REGLA 06 — Supervisión Humana (agregada en el Ciclo 2):**
   * *Condición:* `anulacion_manual = SUSPENDER_EXTRACCION`, o `anulacion_manual = INHIBIR_PULSO` Y `impedancia_ohms > 1500.0`.
   * *Acción:* con `SUSPENDER_EXTRACCION`, `SUSPENSION_MANUAL`, `ajuste_caudal_pct = 0.0`, `pulso_termico = False`; con `INHIBIR_PULSO`, `REDUCIR_CAUDAL_SIN_PULSO`, `ajuste_caudal_pct = 50.0`, `pulso_termico = False`. El estado del nodo es `SUPERVISION_HUMANA`.
   * *Motivo:* Permite que un operador intervenga solo en sentido conservador. Se evalúa después de la REGLA 01 y la REGLA 02, que prevalecen, y antes de la REGLA 04, la REGLA 03 y la REGLA 05. El operador nunca puede forzar extracción ni pulsos.

---

## 5. Especificación del Frontend Dashboard (Simulador Gráfico)

El Dashboard web debe mostrar visualmente:
1. **Panel de Telemetría en Tiempo Real:** 4 indicadores tipo "Card" (Impedancia, Temperatura, Reserva de Calor, Humedad Relativa) con barras de nivel.
2. **Selector de Escenarios:** Botones para simular eventos ("Día Normal", "Incrustación Salina Rápida", "Sequía / Humedad Bajo 30%", "Tormenta de Arena").
3. **Consola de Decisiones de la IA:** Cuadro de texto tipo log que muestra el motivo exacto y la regla activada en cada instante.
4. **Gráfico Comparativo de Conjeturas:** Gráficos de barras o líneas comparando en vivo **Axioma-H (Neuro-Simbólico)** vs **Temporizador Convencional** (Agua obtenida, Energía consumida y Salud del material).

---

## 5.1 Estado de la implementación (Ciclo 2)

La API y el dashboard están implementados en `backend/` (FastAPI) y `frontend/` (Streamlit). Las instrucciones de uso están en `README.md`. Respecto de esta especificación:

- **Nombres de campos.** Los nombres de `TelemetryInput`, `ControlDecision`, `SimulationConfig` y `SimulationResult` coinciden con los de este documento.
- **Campos adicionales en las respuestas.**
  - `ControlDecision` incluye `motivo`, la explicación de la decisión que se muestra en la consola del dashboard.
  - Cada modo de `comparativa` incluye `recuperacion_caudal_promedio_pct` (nulo si el modo no ejecutó pulsos) y `degradacion_acumulada_pct`. Son las variables dependientes de la pregunta de investigación (`01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md`, sección 2) y se muestran en el dashboard.
  - `SimulationResult` incluye `detalle_verificacion`, con los indicadores de cada conjetura, su umbral y si cumplen, y los indicadores informativos `pulsos_regenerados` y `pulsos_totales` de la Conjetura 2. También incluye `series_temporales`, para las gráficas, y `bitacora`, con los cambios de regla del modo neuro-simbólico.
  - `comparativa` incluye un tercer modo, `modo_temporizador_tope_ecologico`: el temporizador fijo con la fracción de 0.33 del modo neuro-simbólico. Es una referencia para separar el efecto del tope ecológico del de la lógica de control y no interviene en la validación ni en `series_temporales`.
  - Cada conjetura de `detalle_verificacion` incluye `causas_no_validacion`, la lista de causas de los indicadores que no cumplen (`SIN_DATOS`, `DEPENDE_DE_PARAMETRO_SUPUESTO`, `LIMITE_DEL_RECURSO_ATMOSFERICO`, `DESEMPENO_DEL_CONTROL`); está vacía si la conjetura se valida. `indicadores_informativos` incluye además `reduccion_degradacion_pct` (Conjetura 1), `tiempo_desprendimiento_t95_promedio_seg` e `impedancia_promedio_tras_pulso_ohms` (Conjetura 2) y `rendimiento_nocturno_temporizador_l_m2_noche` (Conjetura 3). Ninguno de estos campos cambia la validación. Las definiciones están en `docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md`, sección 4.
  - `SimulationResult` incluye `impacto_comunitario`, con una entrada por modo (`modo_neuro_simbolico`, `modo_temporizador_fijo` y `modo_temporizador_tope_ecologico`). Cada entrada tiene `litros_dia_red`, `rendimiento_l_m2_dia`, `personas_supervivencia` (15 L por persona al día, Sphere), `personas_acceso_basico` (20 L por persona al día, OMS) y el área de colector por persona para el acceso básico con los rendimientos de la literatura (`area_m2_por_persona_basico_literatura_min` y `area_m2_por_persona_basico_literatura_max`). Es opcional, con un diccionario vacío por defecto, y no interviene en la validación. Las definiciones y los resultados están en `docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md`, sección 7.6.
  - `SimulationResult` incluye `parametros_usados`, con el nombre del sitio, el flujo máximo de niebla, la eficacia máxima del pulso, la temperatura media y las amplitudes térmica y de humedad con que se ejecutó la corrida. El simulador siempre lo llena; para el payload de la sección 3.2 informa `CABO_DE_LA_VELA`, 6.0 L/m²/h, 0.90, 30.0 °C, 4.5 °C y 10.0 puntos.
- **Supervisión humana.** `TelemetryInput` admite el campo opcional `anulacion_manual` (`NINGUNA`, `SUSPENDER_EXTRACCION` o `INHIBIR_PULSO`; por defecto `NINGUNA`), que aplica la REGLA 06 de la sección 4. Se agregaron el estado `SUPERVISION_HUMANA` y la acción `SUSPENSION_MANUAL`. El payload de la sección 3.1 sigue siendo válido sin cambios y produce la misma decisión. La regla no aplica en modo `TEMPORIZADOR_FIJO` ni en la simulación. El detalle está en `docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md`, sección 2 y decisión D6.
- **Campos opcionales en la solicitud.** `SimulationConfig` admite `numero_nodos` (por defecto 8), `paso_minutos` (por defecto 5) y `semilla` (por defecto 42). También admite `sitio`, un perfil de sitio (`PerfilSitio`: `nombre` con el patrón `^[A-Z0-9_]{1,40}$`, `flujo_niebla_maximo_l_m2_h` en (0, 20], `temperatura_media_c` de 0 a 45, `amplitud_temperatura_c` de 0 a 15 y `amplitud_humedad_pct` de 0 a 30), y `eficacia_maxima_pulso`, en (0, 1]. Ambos son nulos por defecto, y entonces se usan los valores de Cabo de la Vela de `backend/config.py` y los resultados no cambian. El payload de la sección 3.2 sigue siendo válido sin cambios. El procedimiento para transferir el modelo a otro sitio está en `docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md`, sección 8.10.
- **Temperatura objetivo del pulso.** Es 44.0 °C. Con 45.0 °C el pulso activaría el corte térmico de la REGLA_01 (`>= 45.0`). El ejemplo de la sección 3.1 se actualizó en consecuencia.
- **Orden de evaluación.** La REGLA_04 se evalúa antes que la REGLA_03, porque ambas comparten la condición de impedancia alta. El caudal se expresa como porcentaje del tope ecológico del 33 %.
- **Escenarios y endpoints adicionales.** El simulador incluye el escenario `TORMENTA_DE_SAL_Y_CALOR_EXTREMO`, además de los cuatro de la sección 5. La API expone también `GET /` y `GET /api/v1/health`, y los endpoints de la sección 3.3 (`POST /api/v1/analisis/barrido-salinidad`, `POST /api/v1/analisis/robustez-respuesta`, `POST /api/v1/analisis/sensibilidad`, `POST /api/v1/analisis/incertidumbre`, `POST /api/v1/analisis/dimensionamiento` y `GET /api/v1/sitios`). El de incertidumbre usa por defecto un rango de flujo de niebla calibrado contra la literatura (0.49 a 1.83 L/m²/h); el valor por defecto del modelo sigue siendo 6.0 L/m²/h.
- **Dashboard.** Los cuatro elementos de la sección 5 están implementados. El panel de telemetría, con las cuatro tarjetas y sus barras de nivel, está en la vista "Evaluación manual de nodo". El selector de escenarios, la consola de decisiones y los gráficos comparativos están en la vista "Simulación comparativa", que incluye además el escenario `TORMENTA_DE_SAL_Y_CALOR_EXTREMO`. El dashboard agrega dos vistas que la especificación no pedía: "Investigación y guía", con la pregunta, las conjeturas, las reglas y las perspectivas del estudio, y "Respuesta a la pregunta", que consume los endpoints de barrido, sensibilidad e incertidumbre de la sección 3.3. La robustez de la respuesta, el dimensionamiento y los perfiles de sitio todavía no tienen controles en el dashboard; se usan desde la API. La descripción de cada vista está en `docs/03_Funcionamiento_General_AxiomaH.md`, sección 5.
- **Valores de ejemplo.** Los valores numéricos de la respuesta de ejemplo de la sección 3.2 son ilustrativos. Los resultados calculados por el modelo para ese payload están en `docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md`, sección 5.1.
- **Despliegue.** La API y el dashboard están desplegados en Render, en el plan gratuito, como los servicios web `axioma-h-api` (https://axioma-h-api.onrender.com) y `axioma-h-dashboard` (https://axioma-h-dashboard.onrender.com), definidos en `render.yaml`. Render despliega desde `main` solo cuando las pruebas y la Quality Gate de SonarQube Cloud están en verde. El dashboard obtiene la URL de la API de la variable `AXIOMA_API_URL`; los orígenes CORS adicionales se configuran con `AXIOMA_CORS_ORIGINS`. La configuración, la verificación y la operación están en `docs/05_Despliegue_y_Operacion_AxiomaH.md`.

---

## 6. Prompt Maestro de Inicio para Claude Code / VS Code

Para iniciar la codificación en Claude Code, copie y pegue la siguiente instrucción:

> *"Actúa como un Ingeniero Senior de Software y MLOps. Requiero que implementes la API y el Dashboard Simulador para el proyecto Axioma-H basándote en la especificación del documento `02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md`. Desarrolla una API en FastAPI (o Flask) con los endpoints `/api/v1/nodo/evaluar` y `/api/v1/simulacion/ejecutar`, e integra un Frontend interactivo en Streamlit (o HTML/Tailwind) que permita probar interactivamente las 3 conjeturas del proyecto."*
