# Especificación Técnica y PRD: API Neuro-Simbólica y Dashboard Simulator (Axioma-H)
**Proyecto:** Axioma-H — Captación Pasiva de Agua Atmosférica  
**Equipo:** AXIOMA — Curso Fundamentos de Investigación (UdeA)  
**Ciclo:** 2 — Operacionalización, Simulación y Verificación de Conjeturas  

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
  - `SimulationResult` incluye `detalle_verificacion`, con los indicadores de cada conjetura, su umbral y si cumplen, y los indicadores informativos `pulsos_regenerados` y `pulsos_totales` de la Conjetura 2. También incluye `series_temporales`, para las gráficas, y `bitacora`, con los cambios de regla del modo neuro-simbólico.
- **Campos opcionales en la solicitud.** `SimulationConfig` admite `numero_nodos` (por defecto 8), `paso_minutos` (por defecto 5) y `semilla` (por defecto 42). El payload de la sección 3.2 sigue siendo válido sin cambios.
- **Temperatura objetivo del pulso.** Es 44.0 °C. Con 45.0 °C el pulso activaría el corte térmico de la REGLA_01 (`>= 45.0`). El ejemplo de la sección 3.1 se actualizó en consecuencia.
- **Orden de evaluación.** La REGLA_04 se evalúa antes que la REGLA_03, porque ambas comparten la condición de impedancia alta. El caudal se expresa como porcentaje del tope ecológico del 33 %.
- **Escenarios y endpoints adicionales.** El simulador incluye el escenario `TORMENTA_DE_SAL_Y_CALOR_EXTREMO`, además de los cuatro de la sección 5. La API expone también `GET /` y `GET /api/v1/health`.
- **Valores de ejemplo.** Los valores numéricos de la respuesta de ejemplo de la sección 3.2 son ilustrativos. Los resultados calculados por el modelo para ese payload están en `docs/modelo_simulacion.md`, sección 5.1.

---

## 6. Prompt Maestro de Inicio para Claude Code / VS Code

Para iniciar la codificación en Claude Code, copie y pegue la siguiente instrucción:

> *"Actúa como un Ingeniero Senior de Software y MLOps. Requiero que implementes la API y el Dashboard Simulador para el proyecto Axioma-H basándote en la especificación del documento `02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md`. Desarrolla una API en FastAPI (o Flask) con los endpoints `/api/v1/nodo/evaluar` y `/api/v1/simulacion/ejecutar`, e integra un Frontend interactivo en Streamlit (o HTML/Tailwind) que permita probar interactivamente las 3 conjeturas del proyecto."*
