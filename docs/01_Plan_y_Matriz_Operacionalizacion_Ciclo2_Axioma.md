# Plan de Investigación y Matriz de Operacionalización - Ciclo 2
**Proyecto:** *Axioma-H: Sistema de Captación Pasiva de Agua Atmosférica con Control Neuro-Simbólico*  
**Curso:** Fundamentos de Investigación en Ingeniería — Universidad de Antioquia (2026-2)  
**Repositorio:** https://github.com/crd10lop/axioma-h-engine  
**Aplicación desplegada:** [Dashboard](https://axioma-h-dashboard.onrender.com) | [API](https://axioma-h-api.onrender.com/docs)  
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

## 2. Pregunta de Investigación

### 2.1 Formulación

**Pregunta principal:**

> ¿En qué medida un sistema de control neuro-simbólico, evaluado mediante simulación, mejora la recuperación del caudal de agua y reduce el desgaste de las membranas de un captador de agua atmosférica, en comparación con un control convencional por temporizador, a medida que aumenta la salinidad del ambiente?

**Versión divulgativa** (para presentaciones y público no especializado):

> ¿Puede un control inteligente basado en reglas hacer que un captador de agua atmosférica rinda mejor y dure más en ambientes salinos que un control por temporizador?

**Formulación técnica de partida:**

> ¿En qué medida un sistema simulado de control neuro-simbólico descentralizado mejora la tasa de recuperación del caudal hídrico y reduce la degradación acumulada de membranas biomiméticas de captación de agua atmosférica, frente a un control convencional por temporizador, bajo distintos niveles de salinidad extrema?

### 2.2 Ajustes respecto de la formulación técnica

La pregunta principal conserva las dos variables de respuesta y el contraste entre tipos de control, y simplifica los términos que dificultaban su lectura:

| Formulación técnica | Pregunta principal | Motivo |
| :--- | :--- | :--- |
| "sistema simulado ... descentralizado" | "evaluado mediante simulación" | La descentralización (cada uno de los 8 nodos decide con su propia telemetría) se mantiene como característica del sistema, descrita en el alcance, sin cargar la pregunta. |
| "tasa de recuperación del caudal hídrico" | "recuperación del caudal de agua" | Mismo indicador: conductancia relativa de la membrana tras cada pulso de limpieza. |
| "degradación acumulada de membranas biomiméticas" | "desgaste de las membranas" | Mismo indicador: pérdida de integridad de la membrana al final de la corrida. El tipo de membrana se describe en el alcance. |
| "distintos niveles de salinidad extrema" | "a medida que aumenta la salinidad del ambiente" | El simulador evalúa un gradiente de salinidad (tasas BAJA, MEDIA y ALTA, y el escenario de incrustación rápida), no solo condiciones extremas. Así la pregunta admite una respuesta en función del nivel de salinidad. |

### 2.3 Sub-preguntas

1. **Recuperación (Conjetura 1).** ¿Cómo cambia la recuperación del caudal tras cada pulso de limpieza en cada tipo de control a medida que aumenta la carga salina?
2. **Desgaste (Conjetura 2).** ¿Cuánta degradación acumulan las membranas con cada tipo de control, y qué parte de ella se debe a sobrecalentamiento?
3. **Costo ecológico (Conjetura 3).** ¿Cuánta agua y energía se dejan de obtener al respetar los límites ecológicos (tope de extracción del 33 % y pausa con humedad menor que 30 %)?

### 2.4 Variables

| Tipo | Variable | Valores o unidad | Campo en la API |
| :--- | :--- | :--- | :--- |
| Independiente | Tipo de control | Neuro-simbólico / temporizador fijo | `comparativa.modo_*` |
| Moderadora | Nivel de salinidad | Tasa BAJA, MEDIA, ALTA; escenario `INCRUSTACION_SALINA_RAPIDA` (x3) | `tasa_salinizacion`, `escenario` |
| Dependiente | Recuperación de caudal tras pulso | % de la conductancia de la membrana limpia | `recuperacion_caudal_promedio_pct` |
| Dependiente | Degradación acumulada de la membrana | % de integridad perdida en la corrida | `degradacion_acumulada_pct` |
| Controlada | Humedad inicial, duración, número de nodos, semilla | 85 %, 24 h, 8 nodos, semilla 42 | `SimulationConfig` |

### 2.5 Hipótesis de trabajo

El control neuro-simbólico mantiene una recuperación de caudal estable y una degradación acumulada menor que el temporizador, y su ventaja crece con el nivel de salinidad.

**Hipótesis derivada H1-Ciclo 3.** La recuperación tras pulso del control basado en reglas supera a la del temporizador cuando la incrustación diaria de la membrana, el aumento de impedancia por sal en un día, supera un umbral situado en el modelo entre 1633 y 1867 Ohm por día, cualquiera sea la combinación de flujo de niebla y carga salina por litro que la produzca. Surge de la robustez de la respuesta (sección 2.6) y se propone para ponerla a prueba en el Ciclo 3. Su enunciado completo, cómo refutarla y su relación con la medición prioritaria de la eficacia del pulso están en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.9.

### 2.6 Respuesta preliminar del simulador

El barrido de salinidad, con su método y su análisis, está en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 7. En síntesis, con humedad inicial de 85 %:

- **Desgaste.** El control basado en reglas (modo neuro-simbólico en la API y el dashboard; ver la sección 4) reduce la degradación acumulada entre 74 % y 99 % frente al temporizador en los seis niveles de salinidad. La reducción es mayor con salinidad baja, donde el temporizador aplica pulsos que no hacen falta.
- **Recuperación.** El control basado en reglas mantiene la recuperación entre 85.9 % y 88.9 % en todos los niveles. La del temporizador cae de 95.8 % a 63.2 % a medida que aumenta la salinidad. Con salinidad baja el temporizador recupera más, porque limpia una membrana casi limpia. Desde una carga de 60 Ohm por L/m² el control basado en reglas lo supera, y la diferencia llega a 22.7 puntos con la carga más alta.
- **Robustez frente a los parámetros supuestos.** Repetido con tres flujos de niebla (el supuesto y los dos extremos calibrados contra la literatura) y tres eficacias del pulso (0.80, 0.90 y 1.00), el control basado en reglas reduce el desgaste entre 73.3 % y 100 % en los 54 puntos. La ventaja en recuperación no depende de la carga salina por litro sino de la incrustación diaria (la carga salina por el agua captada en un día): en las seis combinaciones en que aparece, el cruce está entre 1633 y 1839 Ohm por día, mientras que la carga por litro del cruce va de 50 a 191. Con el flujo calibrado mínimo esa incrustación no se alcanza y el temporizador recupera más en todos los niveles en que hay pulsos.

La respuesta a la pregunta es, por tanto, condicional. La reducción del desgaste es robusta: se observa en todos los niveles de salinidad y con todos los parámetros evaluados. La ventaja en recuperación aparece solo por encima de una incrustación diaria de unos 1633 a 1867 Ohm por día, que con rendimientos como los de la literatura solo se alcanza con la carga salina más alta. Estos resultados dependen de parámetros físicos supuestos, en particular la eficacia del pulso, que deben medirse en laboratorio. La robustez completa, con la tabla de las nueve combinaciones, está en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.8.

Las cifras anteriores corresponden a la semilla 42. Repetido con las semillas 1 a 5, el barrido muestra una dispersión pequeña y las mismas conclusiones; el punto de cruce de las curvas de recuperación (entre 40 y 60 Ohm por L/m²) es el resultado menos robusto ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 7.5). El barrido y el análisis de sensibilidad se pueden ejecutar desde la API y desde la vista "Respuesta a la pregunta" del dashboard.

### 2.7 Perspectivas social, ética, cultural y humana

Esta sección se limita a lo que el repositorio implementa o documenta. Lo que no se ha realizado se declara de forma explícita.

**Perspectiva social.**

- El proyecto se orienta a Cabo de la Vela, en la Alta Guajira, un territorio árido con escasez hídrica.
- El control es descentralizado por nodo: cada uno de los 8 nodos decide con su propia telemetría (sección 2.2), de modo que una condición local, como la cristalización de una membrana, se atiende sin detener los demás nodos.
- Respetar el tope ecológico tiene un costo hídrico medible. Con humedad inicial de 85 %, el control basado en reglas capta entre 23 % y 27 % menos agua que el temporizador ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 5.5). El estudio hace visible ese costo en lugar de ocultarlo.
- Cada simulación estima el impacto comunitario del agua captada con estándares citados: el acceso básico de la OMS (20 L por persona al día) y el mínimo humanitario de Sphere (15 L por persona al día). Con humedad inicial de 85 %, la red de 8 m² con el control basado en reglas abastecería entre 7.5 y 12.7 personas al nivel de acceso básico, según el escenario. Con los rendimientos de proyectos reales (3 a 10 L/m² al día) harían falta de 2 a 6.7 m² de colector por persona ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 7.6). Es un indicador informativo: no interviene en la validación de las conjeturas.

**Perspectiva ética.**

- El sistema nunca extrae más del 33 % de la niebla disponible (decisión D3) y suspende la extracción con humedad relativa menor que 30 % (REGLA_02).
- Los resultados se calculan con el modelo y no se ajustan parámetros para forzar la validación de una conjetura (decisión D5). Las conjeturas que no se validan se reportan como tales.
- El funcionamiento es transparente: cada simulación devuelve `detalle_verificacion`, con el valor, el umbral y el cumplimiento de cada indicador, y una `bitacora` con los cambios de regla. La API es pública, con documentación interactiva, y el código se distribuye con licencia MIT.
- Antes de cualquier piloto en territorio Wayuu se requiere consulta previa con las comunidades, conforme al Convenio 169 de la OIT, ratificado por Colombia mediante la Ley 21 de 1991. **Esta consulta no se ha realizado.** El Ciclo 2 se limita a la simulación y no involucra a las comunidades ni su territorio.

**Perspectiva cultural.**

- La Conjetura 3 se denomina "saber territorial" y su motivación es preservar la humedad disponible para la vegetación local de trupillo y cardón.
- **Origen del tope del 33 %.** El tope de extracción proviene de la formulación de la Conjetura 3 en la Matriz del equipo (sección 3), construida a partir de la narrativa prospectiva del Ciclo 1, *"El Axioma del Silencio"*. No es un saber wayuu documentado ni un criterio tomado de la literatura ecológica. Su pertinencia debe validarse con las comunidades.
- **Protocolo propuesto de co-creación para el Ciclo 3.** Antes de cualquier piloto, se propone trabajar con las comunidades en cuatro pasos:
  1. Consulta previa, conforme al Convenio 169 de la OIT y la Ley 21 de 1991.
  2. Validación comunitaria del tope de extracción y de la pausa ecológica: si los valores de 33 % y de 30 % de humedad relativa corresponden a su conocimiento del territorio, o deben cambiar.
  3. Traducción de la interfaz al wayuunaiki con traductores wayuu.
  4. Reglas de gobernanza del dispositivo y de los datos: quién lo opera, quién decide sobre el agua captada y quién accede a la telemetría.

  Este protocolo es una propuesta del equipo y no se ha ejecutado.
- **Limitaciones no resueltas:** la interfaz está solo en español y no tiene versión en wayuunaiki; la orientación del colector a 20° al norte, que forma parte de la formulación de la Conjetura 3, no se modela en el simulador (sección 3).

**Perspectiva humana.**

- Cada decisión del motor incluye un campo `motivo` con una explicación legible de la regla activada y de la acción tomada.
- La vista "Evaluación manual de nodo" del dashboard permite explorar las reglas: se ajustan los valores de telemetría y se observa qué regla se activa y por qué.
- **Supervisión humana en la evaluación de un nodo.** `POST /api/v1/nodo/evaluar` admite el campo `anulacion_manual`, y la vista "Evaluación manual de nodo" lo ofrece con el selector "Supervisión humana". Un operador puede suspender la extracción o inhibir el pulso (REGLA_06), solo en sentido conservador: nunca puede forzar extracción ni pulsos, y el corte térmico (REGLA_01) y la pausa ecológica (REGLA_02) prevalecen sobre su decisión ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 2 y decisión D6).
- **Limitación resuelta parcialmente:** la supervisión existe en la evaluación individual, pero no en la simulación, cuyas decisiones se aplican sin intervención de un operador. Incorporarla al simulador, con reglas sobre cuándo y cómo interviene el operador, se propone para el Ciclo 3.

### 2.8 Alcance y madurez

El artefacto del Ciclo 2 es una prueba de concepto analítica por simulación, equivalente de forma aproximada a un nivel de madurez tecnológica TRL 2-3: el concepto y sus reglas de control están formulados e implementados, y su comportamiento se evalúa con un modelo físico simplificado.

- No existe un prototipo físico del captador ni de la membrana.
- No hay datos de campo. Los parámetros marcados como supuestos en `backend/config.py` son estimaciones de orden de magnitud; su trazabilidad está en [06_Referencias_y_Trazabilidad_AxiomaH.md](06_Referencias_y_Trazabilidad_AxiomaH.md), sección 3.
- Lo que sí está implementado y verificado es el software de control: la API, el simulador, el dashboard, las pruebas automatizadas y el despliegue público.

El horizonte del siguiente ciclo es la medición experimental prioritaria descrita en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 6.3: medir en laboratorio qué fracción de la costra salina remueve un pulso de 90 s a 44 °C. Las preguntas emergentes que surgen de la lectura crítica de las conjeturas están en la sección 8 del mismo documento.

---

## 3. Matriz de Operacionalización de Conjeturas

Para el Ciclo 2, la investigación pasa de la conceptualización narrativa a la verificación empírica/simulada de tres conjeturas clave formuladas al cierre del Ciclo 1:

| Conjetura de Investigación | Variable Independiente (Causa / Control) | Variable Dependiente (Efecto / Respuesta) | Indicador y Métrica de Verificación |
| :--- | :--- | :--- | :--- |
| **Conjetura 1: Control Neuro-Simbólico vs. Control Fijo**<br>*"El control neuro-simbólico local extiende la vida útil de la membrana biomimética más que un temporizador estático al prevenir la saturación salina."* | **Tipo de Algoritmo de Control:**<br>- Lógica Neuro-Simbólica (Adaptativa)<br>- Temporizador estático (Control tradicional) | **Conductancia Hidráulica Restante y Frecuencia de Fallas:**<br>- Caudal de agua filtrada ($L/m^2/h$)<br>- Tasa de cristalización e incrustación salina en poros. | - **% de recuperación de caudal:** $\ge 90\%$ tras pulso.<br>- **Ahorro de energía en reserva:** Reducción del $35\%$ en pulsos innecesarios. |
| **Conjetura 2: Autorreparación por Pulso Resonante**<br>*"El pulso térmico controlado ($\le 45^\circ\text{C}$) disuelve las costras de NaCl sin degradar la matriz de acuaporinas sintéticas."* | **Parámetros del Pulso Térmico:**<br>- Frecuencia del pulso (Hz)<br>- Temperatura máxima aplicada ($\Delta T \le 45^\circ\text{C}$)<br>- Duración del micro-pulso (s) | **Integridad Molecular y Tiempo de Regeneración:**<br>- Resistencia mecánica del material.<br>- Tiempo de desprendimiento de la sal. | - **Tiempo de regeneración:** $< 120$ segundos.<br>- **Integridad estructural:** $0\%$ de degradación térmica a $45^\circ\text{C}$. |
| **Conjetura 3: Preservación Ecológica y Saber Territorial**<br>*"Limitar la captación al $33\%$ de la niebla circulante orientando el cubo $20^\circ$ al norte preserva la humedad del suelo y la flora local."* | **Tasa de Extracción Pasiva:**<br>- Porcentaje de niebla captada ($10\%$ a $50\%$).<br>- Orientación angular del colector ($20^\circ$ Norte). | **Humedad del Ecosistema Local:**<br>- Humedad relativa del microclima del sotobosque (trupillo y cardón). | - **Humedad relativa del sotobosque:** $\ge 30\%$ garantizada.<br>- **Rendimiento hídrico:** $\ge 12\text{ L/m}^2/\text{noche}$. |

### Nota de operacionalización en el simulador

Los indicadores de la matriz se calculan en el simulador del Ciclo 2. La definición de cada uno está en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 4.

- **Conjetura 1.** La recuperación de caudal se mide como la conductancia relativa a la membrana limpia después de cada pulso. El ahorro de energía se mide como la reducción de la energía gastada en pulsos frente al temporizador fijo.
- **Conjetura 2.** Una membrana se considera regenerada cuando la impedancia vuelve a 1100 Ohm o menos. La degradación térmica se registra cuando la matriz supera 45 °C. El "pulso resonante" de la Matriz se implementa como un pulso resistivo: un calentamiento de la matriz de 90 s hacia 44 °C (acción `APLICAR_PULSO_RESISTIVO`). La frecuencia del pulso (Hz) no se modela.
- **Conjetura 3.** La humedad del sotobosque no se simula de forma directa. Se usa como aproximación la regla de no extraer agua con humedad ambiente menor que 30 %, junto con el tope de extracción del 33 %. La orientación del colector (20° al norte) no se modela.

---

## 4. Arquitectura del Sistema (API + Frontend)

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

**Sobre el componente neuronal.** El motor implementado en el Ciclo 2 es simbólico: aplica reglas explícitas en orden de prioridad (`backend/motor_reglas.py`) y se apoya en un modelo físico explícito (`backend/modelo_fisico.py`). El "Módulo Neuronal" del diagrama no está implementado; la detección del umbral salino se hace con una comparación directa de la impedancia contra 1500 Ohm. El componente sub-simbólico queda como trabajo futuro, en particular para distinguir la impedancia causada por sal de la causada por polvo ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), pregunta 8.3 c). El término neuro-simbólico describe la arquitectura objetivo del sistema, no la implementación actual.

### Reglas Lógicas de la API (Motor de Inferencia):
1. **Regla de Integridad Térmica:** Si $T_{polímero} \ge 45^\circ\text{C} \implies \text{Acción: CORTE_DE_EMERGENCIA}$.
2. **Regla de Preservación Ecológica:** Si $\text{Humedad}_{ambiental} < 30\% \implies \text{Acción: DETENER_CAPTACIÓN}$.
3. **Regla de Reserva Energética:** Si $\text{Reserva}_{térmica} < 30\% \implies \text{Acción: REDUCIR_CAUDAL}$.
4. **Regla de Regeneración Salina:** Si $\text{Impedancia} > 1500\ \Omega \implies \text{Acción: APLICAR_PULSO_RESONANTE}$.

**Nota sobre la implementación.** La API sigue la versión de las reglas del PRD (`02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md`, sección 4), con seis reglas evaluadas en orden de prioridad:

1. REGLA_01, corte térmico;
2. REGLA_02, pausa ecológica;
3. REGLA_06, supervisión humana, que solo actúa si un operador indica una anulación manual (sección 2.7);
4. REGLA_04, reserva crítica;
5. REGLA_03, pulso resistivo;
6. REGLA_05, operación nominal.

Frente a esta lista:

- las acciones `DETENER_CAPTACIÓN` y `APLICAR_PULSO_RESONANTE` se implementan como `PAUSA_ECOLOGICA` y `APLICAR_PULSO_RESISTIVO`;
- la regla de reserva energética solo actúa cuando, además, la impedancia supera 1500 Ohm;
- el pulso apunta a 44 °C.

Las decisiones que justifican estas diferencias están en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 1.

---

## 5. Plan de Trabajo e Hitos para la Entrega Final del Ciclo 2

- **Hito 1 (Completado):** Definición del alcance, conjeturas y matriz de operacionalización de variables.
- **Hito 2 (Completado):** Implementación de la API de control neuro-simbólico en FastAPI (`backend/`), con motor de reglas, simulador comparativo y pruebas automatizadas. Incluye el temporizador de referencia con tope ecológico, los indicadores informativos y las causas de no validación de cada conjetura, y los endpoints de análisis de robustez (barrido de salinidad con varias semillas y sensibilidad a parámetros supuestos). La versión 0.3.0 agrega la robustez de la respuesta frente a los parámetros supuestos, el dimensionamiento del captador para un número de personas, el perfil de sitio para transferir el modelo y los perfiles de referencia de `GET /api/v1/sitios`.
- **Hito 3 (Completado):** Desarrollo del Frontend Interactivo en Streamlit (`frontend/app.py`), organizado como un recorrido de cinco vistas: investigación y guía (pregunta, tesis actual, hipótesis derivada H1-Ciclo 3, supuestos clave con la medición que reemplazaría a cada uno y guía de lectura por disciplina), evaluación manual de nodo (panel de telemetría con las decisiones en lenguaje llano), simulación comparativa (resumen ejecutivo, conjeturas con lo que cambiaría cada resultado, gráficos, consola de decisiones y reproducción paso a paso), respuesta a la pregunta por partes (desgaste con la robustez, recuperación frente a la incrustación diaria, seguridad con la incertidumbre y la sensibilidad, y personas abastecidas con el dimensionamiento) y explorador de hipótesis (simulación con una eficacia del pulso y un perfil de sitio propios, y preguntas para el Ciclo 3 calculadas con los datos de la sesión).
- **Hito 4 (En desarrollo):** Las pruebas de simulación de los cinco escenarios y el barrido de salinidad que responde la pregunta de investigación están ejecutados y documentados en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md). Queda pendiente la redacción del Informe de Avance del Ciclo 2.
- **Hito 5 (Completado):** Despliegue público de la API y del dashboard para la demostración del Ciclo 2, en Render: [Dashboard](https://axioma-h-dashboard.onrender.com) y [API](https://axioma-h-api.onrender.com/docs). Cada push a `main` se despliega solo si las pruebas y la Quality Gate de SonarQube Cloud están en verde. La verificación automatizada (`scripts/verificar_despliegue.py`) pasó 17 de 17 comprobaciones en su primera versión y, tras agregar los endpoints de análisis, 19 de 19 en la verificación del 2026-11-04. La versión 0.3.0 amplía la verificación a 26 comprobaciones, con la simulación con perfil de sitio, la robustez de la respuesta, el dimensionamiento y los perfiles de sitio. La configuración, la verificación y la operación están en [05_Despliegue_y_Operacion_AxiomaH.md](05_Despliegue_y_Operacion_AxiomaH.md).

---
*Documento preparado por el Equipo AXIOMA para el seguimiento del Ciclo 2 — Universidad de Antioquia.*
