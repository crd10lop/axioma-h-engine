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

- **Control neuro-simbólico:** cada nodo lee sus propios sensores y aplica reglas para decidir qué hacer.
- **Control por temporizador:** limpia cada 2 horas sin consultar los sensores. Es la forma tradicional.

Con esa comparación, el equipo responde su pregunta de investigación: si el control neuro-simbólico recupera mejor el caudal de agua y desgasta menos las membranas a medida que aumenta la salinidad.

## 2. Componentes

La aplicación tiene dos partes que se ejecutan por separado.

**Backend o API (FastAPI).** Realiza todos los cálculos:

- el motor de reglas, que decide qué debe hacer un nodo;
- el modelo físico, que describe cómo se acumula la sal, cómo se calienta la membrana, cuánta energía se gasta y cuánta agua se capta;
- el simulador, que ejecuta uno a tres días con ambos tipos de control;
- la verificación de las tres conjeturas del proyecto;
- el análisis de robustez, que repite las simulaciones con varias semillas o con distintos valores de un parámetro supuesto.

**Frontend o dashboard (Streamlit).** Es la página web que usa la persona. No calcula nada: solicita los resultados a la API y los presenta en tarjetas, tablas y gráficos.

## 3. Cómo decide un nodo

Cada nodo envía cuatro lecturas:

- impedancia de la membrana, que indica cuánto la obstruye la sal;
- temperatura de la membrana;
- reserva de energía;
- humedad relativa del aire.

El motor revisa cinco reglas en orden y la primera que se cumple decide:

1. **Temperatura de 45 °C o más:** corte de emergencia. Se detiene todo para no dañar la membrana.
2. **Humedad menor que 30 %:** pausa ecológica. No se extrae agua, para no restársela a la vegetación local (trupillo y cardón).
3. **Membrana obstruida (impedancia mayor que 1500 Ohm) y reserva menor que 30 %:** se reduce el caudal a la mitad y no se limpia, para no agotar la energía.
4. **Membrana obstruida y energía suficiente:** pulso de limpieza de 90 segundos que lleva la membrana a 44 °C, con un grado de margen frente al límite de 45 °C.
5. **Condiciones normales:** filtración continua.

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

**Análisis de robustez.** La API ofrece dos análisis adicionales, pensados para comprobar qué tan firmes son los resultados:

- **Barrido de salinidad** (`/api/v1/analisis/barrido-salinidad`): compara ambos tipos de control en seis niveles de sal, repitiendo cada caso con hasta cinco climas distintos (semillas). Entrega el promedio y la variación entre climas. Con cinco semillas, la variación resulta pequeña y las conclusiones del barrido se mantienen.
- **Sensibilidad** (`/api/v1/analisis/sensibilidad`): repite una simulación con varios valores de un parámetro que todavía no se ha medido, la eficacia del pulso o la cantidad de niebla disponible, y muestra cómo cambia el estado de cada conjetura.

Ninguno de los dos análisis cambia la configuración del modelo, de modo que varias personas pueden usarlos al mismo tiempo sin afectarse entre sí.

## 5. Uso del dashboard

La barra lateral presenta un recorrido de cuatro vistas numeradas, en el orden recomendado de lectura. Al final de las tres primeras, un botón "Siguiente" lleva a la vista siguiente; también se puede saltar directamente a cualquiera desde la barra lateral.

- **Investigación y guía:** es la vista inicial y no requiere la API. Presenta la pregunta de investigación, su versión divulgativa, la hipótesis de trabajo y la respuesta preliminar del simulador; la tabla de conjeturas con su criterio y la lectura de su resultado; las reglas de control; las perspectivas social, ética, cultural y humana; y el alcance y la madurez del artefacto. En secciones desplegables muestra los supuestos clave y las limitaciones, un glosario y las referencias. Los textos resumen el README y el plan del Ciclo 2 y están en `frontend/contenido.py`.
- **Evaluación manual de nodo:** se ajustan la impedancia, la temperatura, la energía y la humedad, y se observa al instante qué regla se activa y por qué.
- **Simulación comparativa:** se ejecuta un escenario y se comparan lado a lado el control neuro-simbólico y el temporizador. Incluye gráficos en el tiempo, el estado de cada conjetura y una reproducción paso a paso de la corrida.
- **Respuesta a la pregunta:** usa los dos análisis de robustez de la API (sección 4). Muestra la pregunta y la hipótesis, y un aviso de que se trata de un análisis exploratorio que no cambia la configuración del modelo (decisión D5). Tiene dos bloques:
  - **Barrido de salinidad.** Se elige la humedad inicial y de 1 a 5 semillas (consecutivas desde 1) y se presiona "Ejecutar barrido". Dos gráficos muestran, en función de la carga salina, la recuperación tras el pulso (con la referencia de 90 %) y la degradación de la membrana de ambos modos, con su media y una banda de más o menos una desviación estándar. Debajo aparecen frases calculadas con los datos: la carga desde la cual el neuro-simbólico recupera más que el temporizador y el rango de reducción del desgaste.
  - **Sensibilidad.** Se elige el parámetro (eficacia del pulso, con 0.85, 0.90, 0.94, 0.97 y 1.00; o flujo de niebla, con 3, 4.5, 6 y 7.5 L/m²/h) y el escenario. Un gráfico muestra el indicador correspondiente frente al valor, con su umbral: la recuperación (90 %) para la eficacia y el rendimiento nocturno (12 L/m²/noche) para el flujo. Una tabla indica qué conjeturas se validan con cada valor.

  Con 5 semillas el barrido ejecuta 60 simulaciones y puede tardar más que una simulación individual; el dashboard espera hasta 120 s (`TIMEOUT_ANALISIS_SEG`).

## 6. Conjeturas que se verifican

| Conjetura | Qué afirma | Criterio en el simulador |
|---|---|---|
| 1. Eficiencia | El control neuro-simbólico recupera mejor el caudal y ahorra energía. | Recuperación de al menos 90 % tras cada pulso y ahorro de al menos 35 % de energía en pulsos. |
| 2. Autorreparación | El pulso a 44 °C limpia la sal sin dañar la membrana. | Regeneración en menos de 120 s y 0 % de pérdida por calor. |
| 3. Saber territorial | Respetar el límite ecológico sigue permitiendo una captación útil. | Cero violaciones ecológicas y al menos 12 L/m² por noche. |

## 7. Resultados obtenidos

- El control neuro-simbólico desgasta la membrana entre 74 % y 99 % menos que el temporizador, en todos los niveles de salinidad.
- Mantiene una recuperación de caudal estable, entre 86 % y 89 %. La del temporizador cae de 96 % a 63 % a medida que aumenta la sal. Con poca sal el temporizador recupera más, porque limpia membranas casi limpias.
- Nunca supera 45 °C ni viola el límite ecológico. El temporizador alcanzó 55.9 °C.
- Capta entre 23 % y 27 % menos agua que el temporizador. Es el costo de respetar el límite del 33 %.
- Un temporizador de referencia con el mismo límite del 33 % confirma que la mayor parte de esa diferencia se debe al límite y no a las reglas: entre 70 % y 91 %, según el escenario y la humedad. El dashboard muestra esa descomposición debajo de la comparativa.
- Cada pulso logra el 95 % de su limpieza en unos 64 s, por debajo del límite de 120 s, pero deja la membrana en unos 1126 Ω, por encima del criterio de 1100 Ω. La Conjetura 2 falla porque el pulso no limpia lo suficiente, no porque sea lento.
- Cada conjetura no validada indica su causa. Los valores insuficientes de recuperación y regeneración dependen de un parámetro supuesto, y no equivalen a una refutación. Con humedad baja, el rendimiento nocturno no alcanza porque la niebla disponible es insuficiente, incluso para el temporizador.
- Las Conjeturas 1 y 2 todavía no se validan. Ambas dependen de cuánta sal remueve realmente un pulso: el modelo supone una eficacia de 0.90 y harían falta valores de 0.94 a 0.97 para validarlas. Medir esa eficacia en laboratorio es la prioridad del siguiente ciclo.

## 8. Limitaciones

Todos los resultados provienen de una simulación, no de mediciones de campo. Varios parámetros físicos son estimaciones de orden de magnitud, como la eficacia del pulso, el flujo de niebla y el desgaste por calor, y deben calibrarse con datos reales.

## 9. Documentación relacionada

| Documento | Contenido |
|---|---|
| [README.md](../README.md) | Visión general, instalación, uso, endpoints y resultados resumidos. |
| [01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md) | Pregunta de investigación, conjeturas, variables e hitos. |
| [02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md) | Datos que recibe y entrega la API. |
| [modelo_simulacion.md](modelo_simulacion.md) | Ecuaciones, parámetros, resultados detallados y análisis. |
| [despliegue.md](despliegue.md) | Publicación de la aplicación en internet. |
| [referencias.md](referencias.md) | Software de terceros con su licencia, fuente científica y origen de cada parámetro del modelo. |

## 10. Calidad del código y cobertura

El código se analiza en SonarQube Cloud: [tablero del proyecto](https://sonarcloud.io/summary/new_code?id=crd10lop_axioma-h-engine) `crd10lop_axioma-h-engine`, organización `cristian-diez`. El análisis se ejecuta en GitHub Actions en cada push a `main` y en cada pull request, y usa la Quality Gate Sonar way:

- calificación A en fiabilidad, seguridad y mantenibilidad;
- cobertura de al menos 80 % en el código nuevo;
- duplicación de 3 % como máximo en el código nuevo.

**Alcance de la cobertura.** Las pruebas de `tests/` cubren todo `backend/` y la lógica del frontend: `frontend/cliente_api.py`, `frontend/transformaciones.py` y `frontend/config.py`. La cobertura medida localmente con el criterio de Sonar (líneas y ramas, sin `frontend/app.py`) es del 100 %.

**Rutas del reporte.** El archivo `.coveragerc` activa `relative_files`, de modo que `coverage.xml` registra cada archivo con su ruta desde la raíz del repositorio (por ejemplo, `backend/config.py` y `frontend/config.py`) y SonarQube Cloud lo asocia sin ambigüedad con el código fuente.

**Exclusión de `frontend/app.py`.** Es la capa de presentación de Streamlit y no tiene lógica de negocio propia. Toda la lógica que usa, la transformación de datos y las llamadas a la API, está separada en `transformaciones.py` y `cliente_api.py`, que sí tienen pruebas. Su comportamiento se valida al ejecutar el dashboard y con `scripts/verificar_despliegue.py`. Probarla en CI exigiría simular la interfaz completa sin aportar verificación adicional de las reglas del motor.

**Exclusión de `scripts/`.** Contiene una herramienta operativa que se ejecuta contra el despliegue real, no código de la aplicación.

**Trabajo futuro.** Si se quiere cubrir la interfaz, se puede usar `streamlit.testing.v1.AppTest` con `cliente_api` simulado mediante `monkeypatch`.
