# Cómo funciona Axioma-H Engine

**Proyecto:** Axioma-H — Captación Pasiva de Agua Atmosférica  
**Equipo:** AXIOMA — Curso Fundamentos de Investigación (UdeA), Ciclo 2  
**Repositorio:** https://github.com/crd10lop/axioma-h-engine  
**Aplicación desplegada:** [Dashboard](https://axioma-h-dashboard.onrender.com) | [API](https://axioma-h-api.onrender.com/docs)

Este documento explica en lenguaje general qué hace la aplicación y cómo funciona. El detalle técnico está en los documentos listados en la sección 9.

---

## 1. Propósito

Axioma-H Engine simula el sistema de control de un dispositivo que captura agua del aire (niebla y humedad) en Cabo de la Vela, La Guajira. El dispositivo tiene 8 nodos y cada uno tiene una membrana que filtra el agua captada.

El problema central es la sal. La niebla costera trae sal que se adhiere a la membrana, la obstruye y reduce el agua que pasa. Para limpiarla, el dispositivo puede calentar la membrana durante unos segundos (el pulso térmico). Si la calienta demasiado (45 °C o más) la daña, y si la calienta con demasiada frecuencia gasta energía y la desgasta.

La aplicación compara dos formas de decidir cuándo limpiar:

- **Control basado en reglas:** cada nodo lee sus propios sensores y aplica reglas explícitas para decidir qué hacer. Es la primera etapa de una arquitectura neuro-simbólica: el componente neuronal todavía no está implementado. Por compatibilidad, la API y el dashboard llaman a este control "modo neuro-simbólico" (`NEURO_SIMBOLICO`).
- **Control por temporizador:** limpia cada 2 horas sin consultar los sensores. Es la forma tradicional.

Con esa comparación, el equipo responde su pregunta de investigación: si el control basado en reglas recupera mejor el caudal de agua y desgasta menos las membranas a medida que aumenta la salinidad.

## 2. Componentes

La aplicación tiene dos partes que se ejecutan por separado.

**Backend o API (FastAPI).** Realiza todos los cálculos:

- el motor de reglas, que decide qué debe hacer un nodo;
- el modelo físico, que describe cómo se acumula la sal, cómo se calienta la membrana, cuánta energía se gasta y cuánta agua se capta;
- el simulador, que ejecuta uno a tres días con ambos tipos de control;
- la verificación de las tres conjeturas del proyecto;
- la estimación del impacto comunitario, que traduce el agua captada en personas abastecidas;
- el análisis de robustez, que repite las simulaciones con varias semillas o con distintos valores de un parámetro supuesto.

**Frontend o dashboard (Streamlit).** Es la página web que usa la persona. No calcula nada: solicita los resultados a la API y los presenta en tarjetas, tablas y gráficos. Guarda durante una hora la respuesta de cada simulación y de cada análisis, de modo que repetir una misma configuración no vuelve a llamar a la API.

**Acceso.** Ambas partes están publicadas en Render (enlaces del encabezado) y se actualizan automáticamente con cada cambio aprobado en el repositorio. También se pueden ejecutar en un equipo local sin conexión a internet, como se explica en el `README.md` (secciones Ejecución y Uso local sin conexión). El despliegue se describe en [05_Despliegue_y_Operacion_AxiomaH.md](05_Despliegue_y_Operacion_AxiomaH.md).

## 3. Cómo decide un nodo

Cada nodo envía cuatro lecturas:

- impedancia de la membrana, que indica cuánto la obstruye la sal;
- temperatura de la membrana;
- reserva de energía;
- humedad relativa del aire.

El motor revisa seis reglas en orden y la primera que se cumple decide:

1. **Temperatura de 45 °C o más:** corte de emergencia. Se detiene todo para no dañar la membrana.
2. **Humedad menor que 30 %:** pausa ecológica. No se extrae agua, para no restársela a la vegetación local (trupillo y cardón).
3. **Intervención de un operador (supervisión humana):** una persona puede pedir que se suspenda la extracción, o que no se aplique el pulso de limpieza. En el segundo caso, si la membrana está obstruida, el caudal baja a la mitad sin pulso. El operador solo puede ser más prudente que el motor: no puede forzar la extracción ni un pulso, y las dos reglas anteriores siempre se imponen a su decisión.
4. **Membrana obstruida (impedancia mayor que 1500 Ohm) y reserva menor que 30 %:** se reduce el caudal a la mitad y no se limpia, para no agotar la energía.
5. **Membrana obstruida y energía suficiente:** pulso de limpieza de 90 segundos que lleva la membrana a 44 °C, con un grado de margen frente al límite de 45 °C.
6. **Condiciones normales:** filtración continua.

La intervención del operador está disponible al evaluar un nodo, no en la simulación, donde las decisiones se toman sin operador.

Además, el sistema nunca extrae más del 33 % de la niebla disponible. Es un límite ecológico incorporado en el diseño que no puede superarse.

Cada decisión incluye una explicación en texto (el motivo), que el dashboard muestra en una consola.

## 4. Cómo funciona la simulación

La persona elige un escenario, la humedad inicial y el nivel de salinidad (BAJA, MEDIA o ALTA). Los escenarios son:

- día normal;
- incrustación salina rápida;
- sequía;
- tormenta de arena;
- tormenta de sal y calor extremo.

El simulador genera un clima de referencia con ciclos de día y noche, humedad más alta en la madrugada, calor al mediodía y pequeñas variaciones aleatorias. Luego hace funcionar los 8 nodos en pasos de 5 minutos.

Ambos tipos de control se ejecutan sobre el mismo clima, de modo que la comparación es justa. Gracias a una semilla fija, los resultados se repiten de forma idéntica en cada ejecución.

Al final, la simulación entrega para cada tipo de control:

- litros de agua captados;
- número de pulsos de limpieza;
- energía consumida;
- integridad final de la membrana;
- violaciones ecológicas;
- recuperación del caudal después de cada limpieza;
- desgaste acumulado de la membrana.

También entrega las series de tiempo para los gráficos y una bitácora de las decisiones.

**Temporizador de referencia.** Cada simulación ejecuta además un tercer control, solo como referencia: el mismo temporizador, pero limitado al 33 % de la niebla, igual que el control basado en reglas. Comparar los tres permite saber qué parte de la diferencia de agua se debe al límite ecológico y qué parte a las reglas. No interviene en la verificación de las conjeturas.

**Explicación de los resultados.** Para cada conjetura, la simulación indica si se valida, los valores medidos frente a sus umbrales, algunos indicadores adicionales que ayudan a interpretarlos (por ejemplo, cuánto tarda el pulso en actuar y cómo queda la membrana después) y, cuando una conjetura no se valida, la causa: falta de datos, dependencia de un parámetro todavía no medido, falta de niebla disponible o desempeño del control.

**Análisis de robustez.** La API ofrece tres análisis adicionales, pensados para comprobar qué tan firmes son los resultados:

- **Barrido de salinidad** (`/api/v1/analisis/barrido-salinidad`): compara ambos tipos de control en seis niveles de sal, repitiendo cada caso con hasta cinco climas distintos (semillas). Entrega el promedio y la variación entre climas. Con cinco semillas, la variación resulta pequeña y las conclusiones del barrido se mantienen.
- **Sensibilidad** (`/api/v1/analisis/sensibilidad`): repite una simulación con varios valores de un parámetro que todavía no se ha medido, la eficacia del pulso o la cantidad de niebla disponible, y muestra cómo cambia el estado de cada conjetura.
- **Incertidumbre** (`/api/v1/analisis/incertidumbre`): varía a la vez la eficacia del pulso y la cantidad de niebla, tomando valores al azar (pero reproducibles) dentro de un rango, y cuenta en qué proporción de los casos se valida cada conjetura. El rango de la niebla se ajustó para que el captador rinda lo mismo que los proyectos reales descritos en la literatura, de 3 a 10 litros por m² al día.

Ninguno de los tres análisis cambia la configuración del modelo, de modo que varias personas pueden usarlos al mismo tiempo sin afectarse entre sí.

## 5. Uso del dashboard

La barra lateral presenta un recorrido de cuatro vistas numeradas, en el orden recomendado de lectura. Al final de las tres primeras, un botón "Siguiente" lleva a la vista siguiente; también se puede saltar directamente a cualquiera desde la barra lateral.

- **Investigación y guía:** es la vista inicial y no requiere la API. Presenta la pregunta de investigación, su versión divulgativa, la hipótesis de trabajo y la respuesta preliminar del simulador; la tabla de conjeturas con su criterio y la lectura de su resultado; las reglas de control; las perspectivas social, ética, cultural y humana; y el alcance y la madurez del artefacto. En secciones desplegables muestra los supuestos clave y las limitaciones, un glosario y las referencias. Los textos resumen el README y el plan del Ciclo 2 y están en `frontend/contenido.py`.
- **Evaluación manual de nodo:** se ajustan la impedancia, la temperatura, la energía y la humedad, y se observa al instante qué regla se activa y por qué. El selector "Supervisión humana" permite suspender la extracción o impedir el pulso, y el caso de demostración "Operador inhibe el pulso" muestra el efecto sobre una membrana obstruida.
- **Simulación comparativa:** se ejecuta un escenario y se comparan lado a lado el control basado en reglas y el temporizador. Empieza con un resumen ejecutivo de cinco frases (agua, desgaste, energía, límite ecológico y conjeturas validadas). Luego muestra las tarjetas de la comparativa, con la descomposición de la diferencia de agua según el temporizador de referencia; el bloque "Impacto comunitario estimado", con las personas que abastecería el agua captada y el rendimiento frente a la literatura; el estado de cada conjetura con sus indicadores y, si no se valida, sus causas; los gráficos en el tiempo y los totales. Las condiciones del entorno, la consola de decisiones y la reproducción paso a paso están en secciones desplegables, para no recargar la página.
- **Respuesta a la pregunta:** usa los tres análisis de robustez de la API (sección 4). Muestra la pregunta y la hipótesis, y un aviso de que se trata de un análisis exploratorio que no cambia la configuración del modelo (decisión D5). Tiene tres bloques:
  - **Barrido de salinidad.** Se elige la humedad inicial y de 1 a 5 semillas (consecutivas desde 1) y se presiona "Ejecutar barrido". Dos gráficos muestran, en función de la carga salina, la recuperación tras el pulso (con la referencia de 90 %) y la degradación de la membrana de ambos modos, con su media y una banda de más o menos una desviación estándar. Debajo aparecen frases calculadas con los datos: la carga desde la cual el control basado en reglas recupera más que el temporizador y el rango de reducción del desgaste.
  - **Sensibilidad.** Se elige el parámetro (eficacia del pulso, con 0.85, 0.90, 0.94, 0.97 y 1.00; o flujo de niebla, con 3, 4.5, 6 y 7.5 L/m²/h) y el escenario. Un gráfico muestra el indicador correspondiente frente al valor, con su umbral: la recuperación (90 %) para la eficacia y el rendimiento nocturno (12 L/m²/noche) para el flujo. Una tabla indica qué conjeturas se validan con cada valor.
  - **Incertidumbre de los parámetros supuestos.** Se eligen el escenario, la humedad inicial y el número de muestras (5 a 30). Un gráfico de puntos muestra cada muestra según su eficacia del pulso y su flujo de niebla, coloreada según si valida la Conjetura 1. Una tabla da la probabilidad de validar cada conjetura, y unas frases resumen el rango entre los percentiles 5 y 95 de la recuperación, el rendimiento y la reducción del desgaste, y cuántas muestras no aplicaron pulsos.

  Con 5 semillas el barrido ejecuta 60 simulaciones y puede tardar más que una simulación individual; el dashboard espera hasta 120 s (`TIMEOUT_ANALISIS_SEG`).

## 6. Conjeturas que se verifican

| Conjetura | Qué afirma | Criterio en el simulador |
|---|---|---|
| 1. Eficiencia | El control basado en reglas recupera mejor el caudal y ahorra energía. | Recuperación de al menos 90 % tras cada pulso y ahorro de al menos 35 % de energía en pulsos. |
| 2. Autorreparación | El pulso a 44 °C limpia la sal sin dañar la membrana. | Regeneración en menos de 120 s y 0 % de pérdida por calor. |
| 3. Saber territorial | Respetar el límite ecológico sigue permitiendo una captación útil. | Cero violaciones ecológicas y al menos 12 L/m² por noche. |

## 7. Resultados obtenidos

- El control basado en reglas desgasta la membrana entre 74 % y 99 % menos que el temporizador, en todos los niveles de salinidad.
- Mantiene una recuperación de caudal estable, entre 86 % y 89 %. La del temporizador cae de 96 % a 63 % a medida que aumenta la sal. Con poca sal el temporizador recupera más, porque limpia membranas casi limpias.
- Nunca supera 45 °C ni viola el límite ecológico. El temporizador alcanzó 55.9 °C.
- Capta entre 23 % y 27 % menos agua que el temporizador. Es el costo de respetar el límite del 33 %.
- Un temporizador de referencia con el mismo límite del 33 % confirma que la mayor parte de esa diferencia se debe al límite y no a las reglas: entre 70 % y 91 %, según el escenario y la humedad. El dashboard muestra esa descomposición debajo de la comparativa.
- Con la niebla supuesta y humedad inicial de 85 %, el agua del control basado en reglas en la red de 8 m² alcanzaría para unas 12 personas en un día normal, y para entre 7.5 y 12.7 según el escenario, al nivel de acceso básico de la OMS (20 L por persona al día). Con 45 % de humedad alcanzaría para entre 2 y 4 personas. El temporizador abastecería a más personas porque no respeta el límite ecológico. Con los rendimientos de proyectos reales, de 3 a 10 L por m² al día, harían falta de 2 a 6.7 m² de colector por persona. Este cálculo es informativo y no cambia la verificación de las conjeturas.
- Cada pulso logra el 95 % de su limpieza en unos 64 s, por debajo del límite de 120 s, pero deja la membrana en unos 1126 Ω, por encima del criterio de 1100 Ω. La Conjetura 2 falla porque el pulso no limpia lo suficiente, no porque sea lento.
- Cada conjetura no validada indica su causa. Los valores insuficientes de recuperación y regeneración dependen de un parámetro supuesto, y no equivalen a una refutación. Con humedad baja, el rendimiento nocturno no alcanza porque la niebla disponible es insuficiente, incluso para el temporizador.
- Las Conjeturas 1 y 2 todavía no se validan. Ambas dependen de cuánta sal remueve realmente un pulso: el modelo supone una eficacia de 0.90 y harían falta valores de 0.94 a 0.97 para validarlas. Medir esa eficacia en laboratorio es la prioridad del siguiente ciclo.
- Si la cantidad de niebla se ajusta a lo que rinden los proyectos reales, la Conjetura 3 deja de validarse: el rendimiento nocturno queda muy por debajo de 12 litros por m², incluso para el temporizador. Variando a la vez la eficacia del pulso y la niebla, ninguna conjetura se valida en más del 15 % de los casos, y en muchos no hay pulsos que evaluar. En cambio, el menor desgaste de la membrana con el control basado en reglas se mantiene en todos los casos (detalle en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), secciones 8.6 y 8.7).

## 8. Limitaciones

Todos los resultados provienen de una simulación, no de mediciones de campo. Varios parámetros físicos son estimaciones de orden de magnitud, como la eficacia del pulso, el flujo de niebla y el desgaste por calor, y deben calibrarse con datos reales.

## 9. Documentación relacionada

| Documento | Contenido |
|---|---|
| [README.md](../README.md) | Visión general, instalación, uso, endpoints y resultados resumidos. |
| [01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md) | Pregunta de investigación, conjeturas, variables, perspectivas del estudio, alcance e hitos. |
| [02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md) | Datos que recibe y entrega la API y estado de la implementación. |
| 03_Funcionamiento_General_AxiomaH.md | Este documento: explicación general de la aplicación. |
| [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md) | Reglas, ecuaciones, parámetros, resultados detallados, análisis y lectura crítica de las conjeturas. |
| [05_Despliegue_y_Operacion_AxiomaH.md](05_Despliegue_y_Operacion_AxiomaH.md) | Despliegue en Render, integración continua, verificación y operación. |
| [06_Referencias_y_Trazabilidad_AxiomaH.md](06_Referencias_y_Trazabilidad_AxiomaH.md) | Software de terceros con su licencia, fuente científica y origen de cada parámetro del modelo. |
| [datos/README.md](datos/README.md) | Resultados de referencia en CSV y JSON y su diccionario de campos. |
| [README_EN.md](../README_EN.md) | Resumen del proyecto en inglés. |

## 10. Calidad del código y cobertura

El código se analiza en SonarQube Cloud: [tablero del proyecto](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine) `crd10lop_axioma-h-engine`, organización `cristian-diez`. El análisis se ejecuta en GitHub Actions en cada push a `main` y en cada pull request, y usa la Quality Gate Sonar way:

- calificación A en fiabilidad, seguridad y mantenibilidad;
- cobertura de al menos 80 % en el código nuevo;
- duplicación de 3 % como máximo en el código nuevo.

**Alcance de la cobertura.** Las pruebas de `tests/` cubren todo `backend/` y la lógica del frontend: `frontend/cliente_api.py`, `frontend/transformaciones.py`, `frontend/contenido.py` y `frontend/config.py`. La cobertura medida localmente con el criterio de Sonar (líneas y ramas, sin `frontend/app.py`) es del 100 %.

**Rutas del reporte.** El archivo `.coveragerc` activa `relative_files`, de modo que `coverage.xml` registra cada archivo con su ruta desde la raíz del repositorio (por ejemplo, `backend/config.py` y `frontend/config.py`) y SonarQube Cloud lo asocia sin ambigüedad con el código fuente.

**Exclusión de `frontend/app.py`.** Es la capa de presentación de Streamlit y no tiene lógica de negocio propia. Toda la lógica que usa, la transformación de datos y las llamadas a la API, está separada en `transformaciones.py` y `cliente_api.py`, que sí tienen pruebas. Su comportamiento se valida al ejecutar el dashboard y con `scripts/verificar_despliegue.py`. Probarla en CI exigiría simular la interfaz completa sin aportar verificación adicional de las reglas del motor.

**Exclusión de `scripts/`.** Contiene dos herramientas operativas, no código de la aplicación: `verificar_despliegue.py`, que se ejecuta contra el despliegue real, y `generar_resultados_referencia.py`, que regenera los datos de `docs/datos/` importando el backend.

**Trabajo futuro.** Si se quiere cubrir la interfaz, se puede usar `streamlit.testing.v1.AppTest` con `cliente_api` simulado mediante `monkeypatch`.
