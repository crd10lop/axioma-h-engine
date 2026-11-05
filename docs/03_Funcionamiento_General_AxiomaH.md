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
- el análisis de robustez, que repite las simulaciones con varias semillas o con distintos valores de un parámetro supuesto;
- el dimensionamiento, que calcula cuánta área de captador hace falta para un número de personas;
- el perfil de sitio, que permite simular otro lugar con su propia niebla, temperatura y humedad.

**Frontend o dashboard (Streamlit).** Es la página web que usa la persona. No calcula nada: solicita los resultados a la API y los presenta en tarjetas, tablas y gráficos. Guarda durante una hora la respuesta de cada simulación y de cada análisis, de modo que repetir una misma configuración no vuelve a llamar a la API.

**Acceso.** Ambas partes están publicadas en Render (enlaces del encabezado) y se actualizan automáticamente con cada cambio aprobado en el repositorio. También se pueden ejecutar en un equipo local sin conexión a internet, como se explica en el `README.md` (sección Instalación y ejecución). El despliegue se describe en [05_Despliegue_y_Operacion_AxiomaH.md](05_Despliegue_y_Operacion_AxiomaH.md).

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

**Análisis de robustez.** La API ofrece cuatro análisis adicionales, pensados para comprobar qué tan firmes son los resultados:

- **Barrido de salinidad** (`/api/v1/analisis/barrido-salinidad`): compara ambos tipos de control en seis niveles de sal, repitiendo cada caso con hasta cinco climas distintos (semillas). Entrega el promedio y la variación entre climas. Con cinco semillas, la variación resulta pequeña y las conclusiones del barrido se mantienen.
- **Sensibilidad** (`/api/v1/analisis/sensibilidad`): repite una simulación con varios valores de un parámetro que todavía no se ha medido, la eficacia del pulso o la cantidad de niebla disponible, y muestra cómo cambia el estado de cada conjetura.
- **Incertidumbre** (`/api/v1/analisis/incertidumbre`): varía a la vez la eficacia del pulso y la cantidad de niebla, tomando valores al azar (pero reproducibles) dentro de un rango, y cuenta en qué proporción de los casos se valida cada conjetura y en qué proporción el control basado en reglas recupera más caudal que el temporizador. El rango de la niebla se ajustó para que el captador rinda lo mismo que los proyectos reales descritos en la literatura, de 3 a 10 litros por m² al día.
- **Robustez de la respuesta** (`/api/v1/analisis/robustez-respuesta`): repite el barrido de salinidad con tres cantidades de niebla y tres eficacias del pulso, nueve combinaciones en total, para ver si la respuesta a la pregunta cambia cuando cambian los valores que todavía no se han medido.

Ninguno de estos análisis cambia la configuración del modelo, de modo que varias personas pueden usarlos al mismo tiempo sin afectarse entre sí.

**Dimensionamiento.** `/api/v1/analisis/dimensionamiento` responde la pregunta inversa al impacto comunitario: para un número de personas y un consumo diario (15 o 20 litros por persona), cuántos m² de captador y cuántos nodos hacen falta. Lo calcula con tres cantidades de niebla: la supuesta y las dos que reproducen los rendimientos de la literatura.

**Otro sitio.** La simulación acepta un perfil de sitio con la niebla disponible, la temperatura media y la variación diaria de temperatura y de humedad, además de la eficacia del pulso. Sin perfil, usa los valores de Cabo de la Vela. `/api/v1/sitios` lista los perfiles disponibles, que por ahora son solo de Cabo de la Vela, porque el proyecto no tiene datos climáticos de otros lugares. El procedimiento para medir esos valores y usarlos está en [04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.10.

## 5. Uso del dashboard

La barra lateral presenta un recorrido de cinco vistas numeradas, en el orden recomendado de lectura. Al final de las cuatro primeras, un botón "Siguiente" lleva a la vista siguiente; también se puede saltar directamente a cualquiera desde la barra lateral. Los códigos de la API (reglas, estados y acciones) se muestran en lenguaje llano como texto principal, con el código debajo en letra pequeña.

- **Investigación y guía:** es la vista inicial y no requiere la API. Presenta la pregunta de investigación, su versión divulgativa, la hipótesis de trabajo, la tesis actual y la hipótesis derivada para el Ciclo 3, destacadas, y la respuesta preliminar del simulador; la tabla de conjeturas con su criterio y la lectura de su resultado; las reglas de control; la tabla "Supuestos clave y qué los reemplazaría", con el valor, el origen, el efecto observado y la medición que reemplazaría a cada supuesto; las perspectivas social, ética, cultural y humana; y el alcance y la madurez del artefacto. En secciones desplegables muestra la guía de lectura por disciplina (sección 11), las limitaciones, un glosario y las referencias. Los textos están en `frontend/contenido.py`, con su documento de origen.
- **Evaluación manual de nodo:** se ajustan la impedancia, la temperatura, la energía y la humedad, y se observa al instante qué regla se activa y por qué. El estado, la acción y la regla aparecen en lenguaje llano, con su código debajo. El selector "Supervisión humana" permite suspender la extracción o impedir el pulso, y el caso de demostración "Operador inhibe el pulso" muestra el efecto sobre una membrana obstruida.
- **Simulación comparativa:** se ejecuta un escenario y se comparan lado a lado el control basado en reglas y el temporizador. Empieza con un resumen ejecutivo de cinco frases (agua, desgaste, energía, límite ecológico y conjeturas validadas). Luego muestra las tarjetas de la comparativa, con la descomposición de la diferencia de agua según el temporizador de referencia; el bloque "Impacto comunitario estimado"; el estado de cada conjetura con sus indicadores, sus causas si no se valida y un desplegable "Qué cambiaría este resultado", que calcula la distancia de cada indicador a su umbral y nombra la medición o el parámetro que lo cambiaría, o, si la conjetura se valida, qué la haría fallar; los gráficos en el tiempo y los totales. Las condiciones del entorno, la consola de decisiones (con el filtro de reglas en lenguaje llano) y la reproducción paso a paso están en secciones desplegables.
- **Respuesta a la pregunta:** responde la pregunta por partes. Cada parte empieza con una frase que dice qué parte de la pregunta responde, y todas muestran un aviso de que se trata de un análisis exploratorio que no cambia la configuración del modelo (decisión D5).
  - **a) ¿Reduce el desgaste?** Se eligen la humedad inicial y de 1 a 3 semillas y se presiona "Ejecutar robustez". Una tabla muestra las nueve combinaciones de flujo de niebla y eficacia del pulso, con su cruce, la incrustación diaria del cruce y el rango de la reducción del desgaste, y unas frases calculadas resumen el resultado y si es coherente con la hipótesis H1-Ciclo 3.
  - **b) ¿Mejora la recuperación y desde qué salinidad?** Se eligen la humedad inicial, de 1 a 5 semillas y el flujo de niebla entre los perfiles de `GET /api/v1/sitios` (supuesto, calibrado máximo o calibrado mínimo), y se presiona "Ejecutar barrido". Un gráfico muestra la recuperación de ambos modos frente a la incrustación diaria, con la referencia de 90 % y una línea vertical en el cruce; otro muestra la degradación frente a la carga salina. Debajo aparecen el estado del cruce y las frases de lectura del barrido.
  - **c) ¿Qué tan seguro es?** Agrupa la incertidumbre de los parámetros supuestos y la sensibilidad. La incertidumbre se ejecuta con el escenario, la humedad inicial y de 5 a 30 muestras; muestra la probabilidad de validar cada conjetura, el rango entre los percentiles 5 y 95 de los indicadores, cuántas muestras no aplicaron pulsos y en cuántas el control basado en reglas recupera más que el temporizador. La sensibilidad varía la eficacia del pulso (0.85 a 1.00) o el flujo de niebla (3 a 7.5 L/m²/h) y muestra qué conjeturas se validan con cada valor.
  - **d) ¿Para cuántas personas alcanza?** Se indican las personas (1 a 1000), el consumo (OMS, 20 L, o Sphere, 15 L por persona al día), el escenario y la humedad inicial, y se presiona "Dimensionar". Las frases dan el área de colector y los nodos de 1 m² con cada flujo de referencia y el rango de área de la literatura.

  Con 5 semillas el barrido ejecuta 60 simulaciones, y la robustez con 3 semillas, 324; ambos pueden tardar más que una simulación individual. El dashboard espera hasta 120 s (`TIMEOUT_ANALISIS_SEG`).
- **Explorador de hipótesis:** permite poner a prueba una hipótesis propia. Se eligen el escenario, la tasa de salinización, la humedad inicial, la eficacia del pulso (0.80 a 1.00) y un perfil de sitio de `GET /api/v1/sitios`, cuyos cinco campos (nombre, flujo de niebla, temperatura media, amplitud térmica y amplitud de humedad) se pueden editar dentro de los límites de la API. Al presionar "Ejecutar simulación" se ven las conjeturas, qué cambiaría cada resultado y la tabla de parámetros usados. La vista termina con "Preguntas para el Ciclo 3", calculadas con la robustez, la incertidumbre y la simulación de la sesión; si falta un análisis, la pregunta indica cuál ejecutar y en qué vista.

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
- Repitiendo el barrido con tres cantidades de niebla y tres eficacias del pulso, el control basado en reglas desgasta la membrana entre 73 % y 100 % menos que el temporizador en todos los casos. La ventaja en recuperación, en cambio, depende de cuánta sal se acumula por día en la membrana, no de cuánta sal trae cada litro: aparece por encima de unos 1630 a 1870 Ohm por día. Con la niebla de los proyectos reales esa cantidad solo se alcanza con la salinidad más alta. Esta observación se propone como hipótesis para el Ciclo 3 ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), secciones 8.8 y 8.9).
- Para abastecer a 50 personas con 20 litros al día en un día normal con 85 % de humedad, el modelo pide 32 nodos con la niebla supuesta, y entre 100 y 332 con la niebla de los proyectos reales, en línea con los 100 a 333 m² que resultan de la literatura (sección 7.7 del mismo documento).

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

## 11. Guía de lectura por disciplina

El artefacto puede leerse desde varias disciplinas. La tabla indica qué vista o campo usar y qué pregunta podría poner a prueba cada una. Es la misma guía del desplegable de la vista "Investigación y guía" (`GUIA_DISCIPLINAS` en `frontend/contenido.py`). Los datos y la API también se pueden usar desde otros sistemas, como se explica en [05_Despliegue_y_Operacion_AxiomaH.md](05_Despliegue_y_Operacion_AxiomaH.md), sección 7.

| Disciplina | Vista o campo que usar | Pregunta que podría poner a prueba |
|---|---|---|
| Hidrología e ingeniería | Vista 4, partes b y d, y vista 5 con el perfil de sitio. Campos rendimiento_neuro_l_m2_dia_media, incrustacion_diaria_ohm_media y area_colector_m2; datos en docs/datos/robustez_respuesta.csv. | ¿El rendimiento de niebla medido en un sitio, convertido en flujo con la calibración, produce con la sal local una incrustación diaria por encima del umbral de H1-Ciclo 3? |
| Salud pública | Vista 3, impacto comunitario, y vista 4, parte d, dimensionamiento. Campos personas_acceso_basico y nodos_requeridos. | ¿Cuántos nodos habría que instalar para cubrir el acceso básico de la OMS de una comunidad concreta, y cuánto cambia esa cifra con el rendimiento de niebla que se mida en campo? |
| Ecología | Vista 2, pausa ecológica (REGLA_02), y vista 3, violaciones ecológicas y temporizador con tope ecológico. Campos violaciones_ecologicas y modo_temporizador_tope_ecologico. | ¿Extraer como máximo el 33 % de la niebla y pausar con humedad menor que 30 % preserva la humedad que necesitan el trupillo y el cardón? |
| Ciencias sociales | Vista 1, perspectivas y supuestos, y vista 4, parte d. Costo del tope ecológico en personas abastecidas (docs/04, sección 7.6). | ¿Aceptarían las comunidades abastecer a menos personas a cambio de respetar el tope ecológico, y quién decide sobre el agua captada y sobre los datos del dispositivo? |
