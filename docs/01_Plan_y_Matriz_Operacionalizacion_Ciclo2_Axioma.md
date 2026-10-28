# Plan de Investigación y Matriz de Operacionalización - Ciclo 2
**Proyecto:** *Axioma-H: Sistema de Captación Pasiva de Agua Atmosférica con Control Neuro-Simbólico*  
**Curso:** Fundamentos de Investigación en Ingeniería — Universidad de Antioquia (2026-2)  
**Equipo AXIOMA:**
- Juan Esteban Gil Quintero (Líder de Metodología y Calidad)
- Cristian David Diez López (Analista de Vigilancia Tecnológica)
- Cristian Andrés Monterrosa Durango (Especialista en Prospectiva y Co-creación)
- Felipe Meneses Rodríguez (Coordinador de Logística y Colaboración)

---

## 1. Declaración de Elección del Entregable del Ciclo 2

El equipo **AXIOMA** declara formalmente que para el **Ciclo 2 (Fase de Operacionalización y Profundización)** desarrollará la **Especificación Técnica y Arquitectura de la Aplicación Neuro-Simbólica de Control**, acompañada de un **Simulador con Interfaz Gráfica (Frontend Interactivo)** para el dispositivo *Axioma-H*.

### Justificación del Alcance:
A partir de las hipótesis y conjeturas planteadas en la narrativa prospectiva del Ciclo 1 (*"El Axioma del Silencio"*), el equipo busca traducir el comportamiento de los 8 nodos neuro-simbólicos del prototipo a un modelo computacional funcional y medible.

La solución constará de dos componentes integrados:
1. **Backend / API Neuro-Simbólica:** Microservicio encargado de procesar la telemetría de la matriz de captura (impedancia eléctrica, temperatura de la matriz de polímero MOF, reserva térmica y humedad ambiental) y aplicar reglas de inferencia para la toma de decisiones pasivas y autorreparadoras.
2. **Frontend Interactivo (Simulador de Telemetría):** Dashboard web interactivo que permitirá a los investigadores y miembros de la comunidad simular variables extremas del entorno de Cabo de la Vela (cambios bruscos de salinidad, sequías y variaciones de viento nocturno) para observar la respuesta en tiempo real del dispositivo *Axioma-H*.

---

## 2. Matriz de Operacionalización de Conjeturas

Para el Ciclo 2, la investigación pasa de la conceptualización narrativa a la verificación empírica/simulada de tres conjeturas clave formuladas al cierre del Ciclo 1:

| Conjetura de Investigación | Variable Independiente (Causa / Control) | Variable Dependiente (Efecto / Respuesta) | Indicador y Métrica de Verificación |
| :--- | :--- | :--- | :--- |
| **Conjetura 1: Control Neuro-Simbólico vs. Control Fijo**<br>*"El control neuro-simbólico local extiende la vida útil de la membrana biomimética más que un temporizador estático al prevenir la saturación salina."* | **Tipo de Algoritmo de Control:**<br>- Lógica Neuro-Simbólica (Adaptativa)<br>- Temporizador estático (Control tradicional) | **Conductancia Hidráulica Restante y Frecuencia de Fallas:**<br>- Caudal de agua filtrada ($L/m^2/h$)<br>- Tasa de cristalización e incrustación salina en poros. | - **% de recuperación de caudal:** $\ge 90\%$ tras pulso.<br>- **Ahorro de energía en reserva:** Reducción del $35\%$ en pulsos innecesarios. |
| **Conjetura 2: Autorreparación por Pulso Resonante**<br>*"El pulso térmico controlado ($\le 45^\circ\text{C}$) disuelve las costras de NaCl sin degradar la matriz de acuaporinas sintéticas."* | **Parámetros del Pulso Térmico:**<br>- Frecuencia del pulso (Hz)<br>- Temperatura máxima aplicada ($\Delta T \le 45^\circ\text{C}$)<br>- Duración del micro-pulso (s) | **Integridad Molecular y Tiempo de Regeneración:**<br>- Resistencia mecánica del material.<br>- Tiempo de desprendimiento de la sal. | - **Tiempo de regeneración:** $< 120$ segundos.<br>- **Integridad estructural:** $0\%$ de degradación térmica a $45^\circ\text{C}$. |
| **Conjetura 3: Preservación Ecológica y Saber Territorial**<br>*"Limitar la captación al $33\%$ de la niebla circulante orientando el cubo $20^\circ$ al norte preserva la humedad del suelo y la flora local."* | **Tasa de Extracción Pasiva:**<br>- Porcentaje de niebla captada ($10\%$ a $50\%$).<br>- Orientación angular del colector ($20^\circ$ Norte). | **Humedad del Ecosistema Local:**<br>- Humedad relativa del microclima del sotobosque (trupillo y cardón). | - **Humedad relativa del sotobosque:** $\ge 30\%$ garantizada.<br>- **Rendimiento hídrico:** $\ge 12\text{ L/m}^2/\text{noche}$. |

### Nota de operacionalización en el simulador

Los indicadores de la matriz se calculan en el simulador del Ciclo 2. La definición de cada uno está en [modelo_simulacion.md](modelo_simulacion.md), sección 4.

- **Conjetura 1.** La recuperación de caudal se mide como la conductancia relativa a la membrana limpia después de cada pulso. El ahorro de energía se mide como la reducción de la energía gastada en pulsos frente al temporizador fijo.
- **Conjetura 2.** Una membrana se considera regenerada cuando la impedancia vuelve a 1100 Ohm o menos. La degradación térmica se registra cuando la matriz supera 45 °C. La frecuencia del pulso (Hz) no se modela: el pulso se representa como un calentamiento resistivo de 90 s hacia 44 °C.
- **Conjetura 3.** La humedad del sotobosque no se simula de forma directa. Se usa como aproximación la regla de no extraer agua con humedad ambiente menor que 30 %, junto con el tope de extracción del 33 %. La orientación del colector (20° al norte) no se modela.

---

## 3. Arquitectura del Sistema (API + Frontend)

```
[ SENSORES SIMULADOS ] 
   - Impedancia (Ω)
   - Temp. Polímero (°C)
   - Humedad Relativa (%)
   - Reserva Térmica (%)
          │
          ▼
┌────────────────────────────────────────────────────────┐
│             BACKEND / API NEURO-SIMBÓLICA             │
│  - Módulo Simbólico: Reglas de seguridad y ecología   │
│  - Módulo Neuronal: Detección de umbral salino        │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│             FRONTEND / DASHBOARD INTERACTIVO           │
│  - Visualización de estado (Operación / Limpieza)     │
│  - Controles de prueba de entorno (Simulador)          │
│  - Registro de alertas y volumen de agua captada       │
└────────────────────────────────────────────────────────┘
```

### Reglas Lógicas de la API (Motor de Inferencia):
1. **Regla de Integridad Térmica:** Si $T_{polímero} \ge 45^\circ\text{C} \implies \text{Acción: CORTE_DE_EMERGENCIA}$.
2. **Regla de Preservación Ecológica:** Si $\text{Humedad}_{ambiental} < 30\% \implies \text{Acción: DETENER_CAPTACIÓN}$.
3. **Regla de Reserva Energética:** Si $\text{Reserva}_{térmica} < 30\% \implies \text{Acción: REDUCIR_CAUDAL}$.
4. **Regla de Regeneración Salina:** Si $\text{Impedancia} > 1500\ \Omega \implies \text{Acción: APLICAR_PULSO_RESONANTE}$.

**Nota sobre la implementación.** La API sigue la versión de las reglas del PRD (`02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md`, sección 4), con cinco reglas evaluadas en orden de prioridad:

1. REGLA_01, corte térmico;
2. REGLA_02, pausa ecológica;
3. REGLA_04, reserva crítica;
4. REGLA_03, pulso resistivo;
5. REGLA_05, operación nominal.

Frente a esta lista:

- las acciones `DETENER_CAPTACIÓN` y `APLICAR_PULSO_RESONANTE` se implementan como `PAUSA_ECOLOGICA` y `APLICAR_PULSO_RESISTIVO`;
- la regla de reserva energética solo actúa cuando, además, la impedancia supera 1500 Ohm;
- el pulso apunta a 44 °C.

Las decisiones que justifican estas diferencias están en [modelo_simulacion.md](modelo_simulacion.md), sección 1.

---

## 4. Plan de Trabajo e Hitos para la Entrega Final del Ciclo 2

- **Hito 1 (Completado):** Definición del alcance, conjeturas y matriz de operacionalización de variables.
- **Hito 2 (Completado):** Implementación de la API de control neuro-simbólico en FastAPI (`backend/`), con motor de reglas, simulador comparativo y pruebas automatizadas.
- **Hito 3 (Completado):** Desarrollo del Frontend Interactivo en Streamlit (`frontend/app.py`): panel de telemetría, simulación comparativa, consola de decisiones y gráficos.
- **Hito 4 (En desarrollo):** Las pruebas de simulación de los cinco escenarios están ejecutadas y documentadas en [modelo_simulacion.md](modelo_simulacion.md). Queda pendiente la redacción del Informe de Avance del Ciclo 2.

---
*Documento preparado por el Equipo AXIOMA para el seguimiento del Ciclo 2 — Universidad de Antioquia.*
