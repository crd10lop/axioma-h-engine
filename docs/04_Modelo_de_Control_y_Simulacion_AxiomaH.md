# Modelo de control y simulación del motor Axioma-H

Este documento describe el motor de reglas neuro-simbólico, el simulador comparativo y la forma en que se verifican las conjeturas del Ciclo 2. Los valores de todos los parámetros están en `backend/config.py`. Las ecuaciones compartidas por el motor y el simulador están en `backend/modelo_fisico.py`. Los dos parámetros que admiten análisis de sensibilidad, la eficacia máxima del pulso y el flujo máximo de niebla, se agrupan además en `ParametrosModelo` (`backend/modelo_fisico.py`), que toma por defecto los valores de `backend/config.py`. El barrido de salinidad con varias semillas y la sensibilidad están en `backend/analisis.py` (secciones 6.4 y 7.5).

Los documentos de referencia son el PRD de la API ([02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md)) y la Matriz de Operacionalización ([01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md)). Las decisiones de la sección 1 resuelven las diferencias entre ambos.

## 1. Decisiones de diseño

| Id | Decisión | Justificación |
|----|----------|---------------|
| D1 | El corte térmico de emergencia se activa con T >= 45.0 °C. El pulso resistivo apunta a 44.0 °C. | La Conjetura 2 exige pulsos de hasta 45 °C sin activar el corte. Un objetivo de 44 °C deja 1 °C de margen frente al límite absoluto. |
| D2 | La regla de reserva crítica aplica solo si la reserva es menor que 30 % y la impedancia es mayor que 1500 Ohm. | Se adopta la versión del PRD. Una reserva baja sin cristalización no requiere intervención, porque no hay pulso que proteger. |
| D3 | El sistema nunca extrae más del 33 % de la niebla disponible. `ajuste_caudal_pct` es relativo a ese tope. | Es el límite ecológico de la Matriz. Expresar el caudal relativo al tope impide superarlo por construcción. |
| D4 | El enum de escenarios es único: DIA_NORMAL, INCRUSTACION_SALINA_RAPIDA, SEQUIA, TORMENTA_DE_ARENA y TORMENTA_DE_SAL_Y_CALOR_EXTREMO. | Unifica los nombres del PRD y de la Matriz. |
| D5 | Los resultados y la validación de conjeturas se calculan con el modelo. No se fijan valores ni se ajustan parámetros para forzar resultados. | Garantiza que el simulador sirva como instrumento de verificación y no como confirmación circular. |

## 2. Reglas de control

Las reglas se evalúan en el orden de la tabla y la primera que se cumple decide. La REGLA_04 se evalúa antes que la REGLA_03 porque ambas comparten la condición de impedancia alta y la REGLA_04 protege la reserva.

| Prioridad | Regla | Condición | Estado | Acción | Pulso | Caudal (% del tope) |
|---|---|---|---|---|---|---|
| 1 | REGLA_01_LIMITE_TERMICO_ABSOLUTO | T >= 45.0 °C | EMERGENCIA_TERMICA | CORTE_DE_EMERGENCIA | No | 0 |
| 2 | REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL | HR < 30.0 % | PAUSA_ECOLOGICA | PAUSA_ECOLOGICA | No | 0 |
| 3 | REGLA_04_PROTECCION_RESERVA_CRITICA | Reserva < 30.0 % y Z > 1500 Ohm | RESERVA_CRITICA | REDUCIR_CAUDAL_SIN_PULSO | No | 50 |
| 4 | REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA | Z > 1500 Ohm y reserva >= 30.0 % | CRISTALIZACION_DETECTADA | APLICAR_PULSO_RESISTIVO | 44 °C, 90 s | 80 |
| 5 | REGLA_05_OPERACION_NOMINAL | Ningún caso anterior | NOMINAL | FILTRACION_PASIVA_CONTINUA | No | 100 |

En modo `TEMPORIZADOR_FIJO`, el endpoint de evaluación no aplica reglas. Devuelve `FILTRACION_PASIVA_CONTINUA` con caudal del 100 % y regla `SIN_REGLAS_TEMPORIZADOR_FIJO`.

### Métricas de una evaluación individual

- **Recuperación hidráulica:** `min(100, Z_nom / Z_tras * 100)`. Con pulso, `Z_tras = Z_nom + Z_sal * (1 - eta)`, donde `Z_sal = Z - Z_nom`. Sin pulso, `Z_tras = Z`.
- **Eficiencia energética:** `100 * R / (R + C)`. R son los puntos porcentuales de conductancia recuperados y C los puntos porcentuales de reserva que consume el pulso. Vale 100 si la acción no consume reserva.
- **Preservación ecológica:** es verdadera si no se extrae agua con HR < 30 % y la fracción efectiva no supera 0.33. Se interpreta como ausencia de violación. Por eso una pausa ecológica, con HR baja y caudal nulo, se considera conforme. El modo temporizador, con fracción fija de 0.45, nunca lo es.

## 3. Ecuaciones del simulador

La simulación arranca a las 18:00 hora local y avanza en pasos de `paso_minutos` durante `duracion_horas`. Ambos modos se ejecutan sobre el mismo entorno, que se genera una sola vez con `random.Random(semilla)`.

### 3.1 Entorno

- **Radiación relativa:** `S(h) = sen(pi * (h - 6) / 12)` entre 06:00 y 18:00, y 0 fuera de ese intervalo.
- **Humedad relativa:** `HR(h) = HR_0 + A_HR * [cos(2 pi (h - 4) / 24) - cos(2 pi (18 - 4) / 24)] + d_n + e`, acotada entre 0 y 100. HR_0 es la humedad a las 18:00, d_n el desfase fijo del nodo y e el ruido gaussiano por paso.
- **Temperatura ambiente:** `T_a(h) = 30 + 4.5 * cos(2 pi (h - 14) / 24)`.
- **Temperatura de la matriz:** `T_m = T_a + 7 * S(h) * f_rad + d_n + e`.

| Escenario | Modificación |
|---|---|
| DIA_NORMAL | Salinización según la tasa elegida. |
| INCRUSTACION_SALINA_RAPIDA | Incrustación multiplicada por 3. |
| SEQUIA | HR reducida 10 puntos en toda la corrida. Entre 09:00 y 17:00 la HR se limita a 25 % (más ruido). |
| TORMENTA_DE_ARENA | Entre 12:00 y 18:00: captación al 60 %, recarga solar al 50 % y ensuciamiento de 60 Ohm/h por polvo. Fuera de esa ventana, el polvo decae con constante de 4 h. |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | Tasa ALTA multiplicada por 1.5 y +3 °C ambiente proporcional a S(h). La matriz alcanza picos cercanos a 45 °C (máximo simulado de 44.79 °C con semilla 42). |

### 3.2 Estado por nodo y dinámica

La impedancia total es `Z = Z_nom + Z_sal + Z_polvo`.

- **Recurso hídrico:** `Q(HR) = Q_max * ((HR - 20) / 80)^1.5` si HR > 20 %, y 0 en otro caso (L/m²/h).
- **Agua captada por paso:** `L = Q(HR) * f_capt * fraccion * (Z_nom / Z) * (I / 100) * A * dt`. La fracción es `0.33 * ajuste / 100` en el modo neuro-simbólico y `0.45` en el temporizador. I es la integridad de la membrana.
- **Incrustación salina:** `Z_sal += k_sal * L / A`. La sal crece en proporción al agua procesada.
- **Eficacia del pulso:** `eta = eta_max * g(T) * Z_ref / (Z_ref + Z_sal)`, con `g(T) = clamp((T - 30) / (44 - 30), 0, 1)`. Tras el pulso, `Z_sal' = Z_sal * (1 - eta)`. La eficacia crece con la temperatura alcanzada y disminuye con la carga salina.
- **Cinética durante el pulso:** `Z_sal(t) = Z_sal0 * [1 - eta * (1 - e^(-t/tau)) / (1 - e^(-90/tau))]`, con `tau = 25 / g(T)` segundos.
- **Tiempo de regeneración:** se mide en cada pulso aplicado con Z > 1500 Ohm, como el tiempo hasta que la impedancia vuelve a `Z <= 1.10 * Z_nom` (1100 Ohm, constante `FACTOR_IMPEDANCIA_REGENERADA`). Se obtiene resolviendo la cinética del pulso con `Z_sal` objetivo igual a `1100 - Z_nom - Z_polvo`. Si el pulso no alcanza ese valor, el evento cuenta como no regenerado. Su tiempo es entonces la duración del pulso más el intervalo hasta el siguiente pulso del nodo, es decir, la diferencia entre ambos inicios. Si no hay otro pulso, se mide hasta el fin de la simulación, con un mínimo de 90 s.
- **Energía del pulso:** `E = (C * dT + G * dT * 90) / 3600` Wh. En el modo neuro-simbólico, `dT = max(T_m, 44) - T_m`. En el temporizador, `dT = 12 °C`. Un pulso sin reserva suficiente no se ejecuta.
- **Reserva:** `R += P_solar * S * f_rad * dt - P_base * dt - E_pulso`, acotada entre 0 y la capacidad.
- **Integridad de la membrana:**
  - fatiga de 0.02 % por pulso;
  - degradación térmica de 0.05 % por cada °C sobre 45 y minuto de exposición, aplicada tanto al pulso como a la matriz expuesta al sol;
  - pérdida de 0.10 %/h mientras Z > 1500.

  La pérdida térmica se registra aparte y se desglosa en dos componentes: la inducida por pulso y la ambiental.

### 3.3 Modos de control

- **Neuro-simbólico:** en cada paso y nodo se construye un `TelemetryInput` y se llama a `evaluar_telemetria`. El simulador reutiliza el mismo motor de reglas del endpoint.
- **Temporizador fijo:** aplica un pulso cada 120 min sin leer sensores, a `T_m + 12 °C` y sin corte térmico. La fracción de extracción es fija en 0.45 y no hay pausa ecológica.
- **Temporizador con tope ecológico (referencia):** es el mismo temporizador fijo, con la misma programación de pulsos y sin corte térmico ni pausa ecológica, pero con la fracción de 0.33 del modo neuro-simbólico. Se ejecuta sobre el mismo entorno y se reporta en `comparativa.modo_temporizador_tope_ecologico`. No interviene en la validación de las conjeturas ni en las series temporales. Su función es separar el efecto del tope ecológico del de la lógica de control (sección 8.4).

### 3.4 Parámetros

| Parámetro | Valor | Origen | Fuente |
|---|---|---|---|
| Umbral de corte térmico | 45.0 °C | PRD | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Temperatura objetivo del pulso | 44.0 °C | Matriz | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Umbral de humedad ecológica | 30.0 % | PRD | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Umbral de reserva crítica | 30.0 % | PRD | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Umbral de impedancia | 1500 Ohm | PRD | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Impedancia nominal | 1000 Ohm | PRD | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Duración del pulso | 90 s | PRD | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Fracción máxima de extracción | 0.33 | Matriz | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Caudal durante pulso / reserva crítica | 80 % / 50 % | PRD | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Factor de impedancia regenerada | 1.10 (1100 Ohm) | Criterio del equipo | [Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros) |
| Área de colector por nodo | 1.0 m² | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Flujo máximo de niebla | 6.0 L/m²/h (0.35 g/m³ a 5 m/s) | Supuesto | Sin fuente; contrastado con Klemm et al. (2012) en [Documento 06, sección 4](06_Referencias_y_Trazabilidad_AxiomaH.md#4-comparación-del-flujo-de-niebla-supuesto-con-la-literatura) |
| HR mínima de captación, exponente | 20 %, 1.5 | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Amplitud del ciclo de HR | 10 puntos, máximo a las 04:00 | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Temperatura ambiente | 30 +/- 4.5 °C, máximo a las 14:00 | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Calentamiento solar de la matriz | +7 °C con radiación máxima | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Incrustación BAJA / MEDIA / ALTA | 20 / 40 / 80 Ohm por L/m² | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Eficacia máxima del pulso | 0.90 | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Temperaturas de efecto mínimo y de saturación | 30 °C / 44 °C | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Carga salina de referencia | 2500 Ohm | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Constante de disolución | 25 s | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Capacidad de reserva, reserva inicial | 150 Wh, 70 % | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Recarga solar máxima | 20 W | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Capacidad térmica de la matriz | 800 J/K | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Conductancia de pérdidas | 30 W/K | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Consumo base neuro-simbólico / temporizador | 0.6 W / 0.2 W | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Fatiga por pulso | 0.02 % | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Degradación térmica | 0.05 %/(°C·min) | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Degradación por cristalización | 0.10 %/h | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Ruido HR / T por paso | 1.0 % / 0.3 °C | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |
| Dispersión entre nodos HR / T / salinización | +/-2 % / +/-0.5 °C / +/-10 % | Supuesto | Sin fuente: supuesto de orden de magnitud ([Documento 06, sección 3](06_Referencias_y_Trazabilidad_AxiomaH.md#3-trazabilidad-de-parámetros)) |

Los parámetros marcados como supuestos son estimaciones de orden de magnitud y deben calibrarse con mediciones de campo.

## 4. Indicadores de verificación

| Conjetura | Indicador | Cálculo | Umbral |
|---|---|---|---|
| C1 Eficiencia | Recuperación de caudal tras pulso | Promedio de `min(100, Z_nom / Z_tras_pulso * 100)` sobre todos los pulsos del modo neuro-simbólico | >= 90 % |
| C1 Eficiencia | Ahorro de energía en pulsos | `(E_pulsos_temp - E_pulsos_neuro) / E_pulsos_temp * 100` | >= 35 % |
| C2 Autorreparación | Tiempo de regeneración | Promedio, sobre todos los pulsos, del tiempo hasta Z <= 1100 Ohm (definición en 3.2) | < 120 s |
| C2 Autorreparación | Pérdida térmica | Pérdida promedio por nodo debida a T > 45 °C, por pulso o por exposición ambiental | = 0 % |
| C3 Saber territorial | Violaciones ecológicas | Episodios (pasos consecutivos por nodo) con extracción y HR < 30 % o fracción > 0.33 | = 0 |
| C3 Saber territorial | Rendimiento nocturno | `L_noche / (A * N) / (H_noche / 12)` | >= 12 L/m²/noche |

El rendimiento nocturno se normaliza a 12 horas. Si la corrida no cubre una noche completa, el valor se escala proporcionalmente. Si cubre varias noches, el valor es el promedio por noche.

Una conjetura se valida solo si todos sus indicadores cumplen. Si la corrida no produce datos para un indicador, este se reporta con valor nulo y como no cumplido. Esto ocurre, por ejemplo, en una corrida de 1 h sin pulsos del temporizador.

La Conjetura 2 incluye además dos indicadores informativos, `pulsos_regenerados` y `pulsos_totales`, en el campo `indicadores_informativos` de la respuesta. Muestran cuántos pulsos del modo neuro-simbólico alcanzaron el criterio de 1100 Ohm y no intervienen en la validación.

Cada conjetura informa también otros indicadores informativos, redondeados a 4 decimales. Una clave se omite si la corrida no produce datos para calcularla. Ninguno interviene en la validación.

| Conjetura | Indicador informativo | Cálculo |
|---|---|---|
| C1 | `reduccion_degradacion_pct` | `(D_temp - D_neuro) / D_temp * 100`, con `D = 100 - integridad final`. Corresponde al enunciado de vida útil de la conjetura. |
| C2 | `tiempo_desprendimiento_t95_promedio_seg` | Promedio, sobre los pulsos neuro-simbólicos, de `t_95 = -tau * ln(1 - 0.95 * (1 - e^(-90/tau)))`, el tiempo en que el pulso logra el 95 % de su remoción total (`FRACCION_TIEMPO_DESPRENDIMIENTO`, criterio del equipo). |
| C2 | `impedancia_promedio_tras_pulso_ohms` | Promedio de la impedancia al terminar cada pulso neuro-simbólico. |
| C3 | `rendimiento_nocturno_temporizador_l_m2_noche` | Rendimiento nocturno del temporizador fijo, con la misma fórmula del indicador. |

El campo `causas_no_validacion` de cada conjetura lista, en el orden de los indicadores y sin repetir, la causa de cada indicador que no cumple. Una conjetura validada tiene la lista vacía.

| Causa | Cuándo se asigna |
|---|---|
| `SIN_DATOS` | El indicador no tiene valor, porque la corrida no generó datos para medirlo. |
| `DEPENDE_DE_PARAMETRO_SUPUESTO` | No cumple la recuperación de caudal o el tiempo de regeneración, que dependen de la eficacia del pulso (`eta_max`), un parámetro supuesto (secciones 5.6 y 5.7). |
| `LIMITE_DEL_RECURSO_ATMOSFERICO` | No cumple el rendimiento nocturno y el temporizador fijo, que extrae al 45 %, tampoco alcanza el umbral. |
| `DESEMPENO_DEL_CONTROL` | No cumple el rendimiento nocturno, pero el temporizador sí alcanza el umbral, o no cumple cualquier otro indicador. |

La clasificación se asigna por indicador y no es un diagnóstico completo. Por ejemplo, en TORMENTA_DE_ARENA la recuperación se atribuye a la eficacia del pulso, aunque el polvo, que el pulso no remueve, también contribuye (sección 6.2).

## 5. Resultados

Todas las corridas comparten estas condiciones:

- 24 h, inicio a las 18:00, paso de 5 min;
- 8 nodos, semilla 42, tasa de salinización ALTA;
- parámetros de `backend/config.py` sin modificar (eficacia máxima del pulso 0.90 y criterio de regeneración de 1100 Ohm).

Solo cambia la humedad inicial, que se indica en el título de cada tabla.

Los resultados de las secciones 5.1 a 5.4, junto con el modo de referencia de la sección 8.4 y el barrido con semillas 1 a 5 de la sección 7.5, están también como datos abiertos en [datos/](datos/README.md) (CSV y JSON). Se regeneran sin la API con `python scripts/generar_resultados_referencia.py`.

### 5.1 Corrida de referencia del PRD (TORMENTA_DE_SAL_Y_CALOR_EXTREMO, humedad inicial 45 %)

Es el payload de ejemplo del PRD (sección 3.2): `duracion_horas` 24, `escenario` TORMENTA_DE_SAL_Y_CALOR_EXTREMO, `humedad_ambiente_inicial_pct` 45.0 y `tasa_salinizacion` ALTA. Los valores numéricos de la respuesta de ejemplo del PRD son ilustrativos. Los de esta tabla son los que calcula el modelo.

| Métrica | Neuro-simbólico | Temporizador fijo | Diferencia |
|---|---|---|---|
| Agua captada (L) | 81.652 | 120.408 | -32.2 % |
| Pulsos térmicos | 19 | 88 | -78.4 % |
| Energía consumida (Wh) | 323.155 | 1065.067 | -69.7 % |
| Integridad final (%) | 99.9525 | 97.0941 | +2.9 % |
| Violaciones ecológicas | 0 | 8 | -100.0 % |

| Conjetura | Indicador | Valor | Umbral | Cumple | Estado |
|---|---|---|---|---|---|
| C1 Eficiencia | Recuperación de caudal tras pulso (%) | 88.81 | >= 90 | No | false |
| C1 Eficiencia | Ahorro de energía en pulsos (%) | 79.74 | >= 35 | Sí | |
| C2 Autorreparación | Tiempo promedio de regeneración (s) | 22263.16 | < 120 | No | false |
| C2 Autorreparación | Pulsos regenerados / totales (informativo) | 0 / 19 | No aplica | Informativo | |
| C2 Autorreparación | Pérdida de integridad térmica (%) | 0.00 | <= 0 | Sí | |
| C3 Saber territorial | Violaciones ecológicas | 0 | <= 0 | Sí | false |
| C3 Saber territorial | Rendimiento nocturno (L/m²/noche) | 5.95 | >= 12 | No | |

### 5.2 Cinco escenarios con humedad inicial 45 %

| Escenario | Recuperación (%) | Ahorro (%) | C1 | Regeneración (s) | Pulsos regenerados | Pérdida térmica (%) | C2 | Violaciones | Rendimiento nocturno (L/m²) | C3 |
|---|---|---|---|---|---|---|---|---|---|---|
| DIA_NORMAL | 88.85 | 87.38 | false | 32400.00 | 0/10 | 0.00 | false | 0 | 6.01 | false |
| INCRUSTACION_SALINA_RAPIDA | 88.76 | 45.57 | false | 12013.64 | 0/44 | 0.00 | false | 0 | 5.78 | false |
| SEQUIA | Sin datos | 100.00 | false | Sin datos | 0/0 | 0.00 | false | 0 | 4.01 | false |
| TORMENTA_DE_ARENA | 83.92 | 81.52 | false | 18000.00 | 0/18 | 0.00 | false | 0 | 6.01 | false |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 88.81 | 79.74 | false | 22263.16 | 0/19 | 0.00 | false | 0 | 5.95 | false |

En SEQUIA con humedad inicial de 45 %, el modo neuro-simbólico no ejecutó ningún pulso. La humedad baja reduce la captación y, con ella, la incrustación salina, de modo que la impedancia nunca superó 1500 Ohm. Sin pulsos, la recuperación y el tiempo de regeneración no tienen datos y se reportan como no cumplidos (sección 4).

### 5.3 Cinco escenarios con humedad inicial 85 %: comparativa de modos

| Escenario | Modo | Litros | Pulsos | Energía (Wh) | Integridad final (%) | Violaciones |
|---|---|---|---|---|---|---|
| DIA_NORMAL | Neuro-simbólico | 254.60 | 46 | 664.5 | 99.89 | 0 |
| DIA_NORMAL | Temporizador fijo | 340.40 | 88 | 1065.1 | 97.57 | 8 |
| INCRUSTACION_SALINA_RAPIDA | Neuro-simbólico | 185.37 | 97 | 1013.7 | 98.93 | 0 |
| INCRUSTACION_SALINA_RAPIDA | Temporizador fijo | 240.94 | 88 | 1065.1 | 95.88 | 8 |
| SEQUIA | Neuro-simbólico | 149.35 | 24 | 491.9 | 99.84 | 0 |
| SEQUIA | Temporizador fijo | 204.40 | 88 | 1065.1 | 97.78 | 8 |
| TORMENTA_DE_ARENA | Neuro-simbólico | 232.43 | 53 | 752.1 | 99.87 | 0 |
| TORMENTA_DE_ARENA | Temporizador fijo | 306.41 | 88 | 1065.1 | 98.18 | 8 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | Neuro-simbólico | 234.98 | 64 | 780.8 | 99.59 | 0 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | Temporizador fijo | 305.83 | 88 | 1065.1 | 96.10 | 8 |

### 5.4 Cinco escenarios con humedad inicial 85 %: verificación de conjeturas

| Escenario | Recuperación (%) | Ahorro (%) | C1 | Regeneración (s) | Pulsos regenerados | Pérdida térmica (%) | C2 | Violaciones | Rendimiento nocturno (L/m²) | C3 |
|---|---|---|---|---|---|---|---|---|---|---|
| DIA_NORMAL | 88.78 | 46.50 | false | 11934.78 | 0/46 | 0.00 | false | 0 | 16.97 | true |
| INCRUSTACION_SALINA_RAPIDA | 85.92 | 12.49 | false | 6593.81 | 0/97 | 0.00 | false | 0 | 11.45 | false |
| SEQUIA | 88.78 | 63.31 | false | 21575.00 | 0/24 | 0.00 | false | 0 | 14.19 | true |
| TORMENTA_DE_ARENA | 85.78 | 37.97 | false | 10358.49 | 0/53 | 0.00 | false | 0 | 16.97 | true |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 88.02 | 35.17 | false | 9257.81 | 0/64 | 0.00 | false | 0 | 16.62 | true |

El tiempo de regeneración se calcula con el criterio de 1100 Ohm descrito en 3.2. Con el criterio anterior (volver bajo 1500 Ohm), los valores eran 0.23, 278.28, 0.24, 0.30 y 1.81 s, y la Conjetura 2 se validaba en cuatro escenarios.

### 5.5 Análisis

Salvo que se indique otra cosa, el análisis se refiere a las corridas con humedad inicial de 85 % (secciones 5.3 y 5.4). Las diferencias de la corrida del PRD con 45 % se tratan al final de esta sección.

**Conjetura 1 (false en los cinco escenarios).** El indicador que falla es la recuperación de caudal, que queda entre 85.8 % y 88.8 %. El pulso se dispara apenas Z supera 1500 Ohm, es decir, con unos 500 Ohm de carga salina. Con `eta_max = 0.90` y la atenuación por carga, cada pulso remueve cerca del 75 % de esa carga y la impedancia queda alrededor de 1125 Ohm, lo que equivale a un 89 % de conductancia. Para superar el 90 % haría falta `eta_max` de 0.94 o más (ver 5.6), un valor que hoy no tiene respaldo experimental.

El ahorro de energía sí cumple en cuatro escenarios. En INCRUSTACION_SALINA_RAPIDA no cumple (12.5 %): la red pulsa más veces que el temporizador (97 frente a 88) y, de noche, cada pulso neuro-simbólico eleva la matriz unos 18 °C, contra 12 °C del temporizador. En TORMENTA_DE_SAL_Y_CALOR_EXTREMO el ahorro (35.17 %) apenas supera el umbral, por lo que el resultado es frágil.

**Conjetura 2 (false en los cinco escenarios).** El componente térmico de la conjetura sí se cumple. En ningún escenario hay pérdida térmica en el modo neuro-simbólico. El pulso más caliente fue de 44.30 °C, cuando la matriz ya estaba sobre el objetivo por radiación. En TORMENTA_DE_SAL_Y_CALOR_EXTREMO la matriz llegó a 44.79 °C sin cruzar 45 °C, así que la REGLA_01 no se activó en la simulación. El temporizador, en cambio, alcanzó 55.9 °C y perdió 2.69 % de integridad por degradación térmica.

Lo que falla es el tiempo de regeneración. El criterio anterior (volver bajo 1500 Ohm) se satisfacía de forma trivial. Como el pulso se dispara apenas la impedancia cruza el umbral, bastaba remover unos pocos ohmios, y el indicador quedaba entre 0.2 y 1.8 s sin decir nada sobre la limpieza real de la membrana. El nuevo criterio exige volver a 1100 Ohm, es decir, recuperar al menos el 91 % de la conductancia nominal.

Con `eta_max = 0.90`, un pulso típico deja la impedancia cerca de 1125 Ohm. Por eso ninguno de los pulsos de los cinco escenarios alcanza el criterio. Cada evento se mide entonces hasta el pulso siguiente, y el promedio queda entre 1.8 y 6.0 horas.

El resultado es coherente con el de la Conjetura 1: ambos indicadores dependen de la fracción de sal que remueve un pulso. La sensibilidad se muestra en 5.7.

**Conjetura 3 (false solo en INCRUSTACION_SALINA_RAPIDA).** El modo neuro-simbólico no registró violaciones ecológicas en ningún escenario. Esto se cumple por diseño: el tope del 33 % es estructural (D3) y la REGLA_02 detiene la extracción con HR < 30 %. El temporizador acumula un episodio continuo por nodo debido a su fracción de 0.45.

En la incrustación rápida, el rendimiento nocturno cae a 11.45 L/m² porque la impedancia se mantiene alta y la REGLA_04 reduce el caudal. En la corrida de 24 h, la sequía y la tormenta de arena ocurren de día, después de la única noche simulada. Por eso afectan poco el rendimiento nocturno.

**Observación adicional.** El modo neuro-simbólico capta entre 23 % y 27 % menos agua que el temporizador. Esto es consecuencia directa del tope ecológico (0.33 frente a 0.45) y es el costo esperado de la Conjetura 3: el temporizador obtiene más agua a costa de violar el límite territorial.

**Corrida del PRD con humedad inicial de 45 % (secciones 5.1 y 5.2).** Con 45 % a las 18:00, la humedad nocturna alcanza como máximo entre 64 % y 68 %, según el nodo. El recurso hídrico disponible es mucho menor que con 85 % y aparecen tres diferencias:

- **Conjetura 3:** pasa a false en los cinco escenarios. El modo neuro-simbólico mantiene cero violaciones, pero el rendimiento nocturno cae a 4.0–6.0 L/m²/noche, menos de la mitad del umbral. Esto refleja un límite del recurso atmosférico, no una falla del control: el temporizador, que extrae al 45 % sin restricciones, también queda por debajo del umbral, con 5.8–8.9 L/m²/noche.
- **Conjetura 1:** el ahorro de energía es mayor (46 % a 100 %), porque con menos captación hay menos sal y menos pulsos (10 a 44 frente a 88 del temporizador). La recuperación tras pulso sigue entre 83.9 % y 88.9 %, bajo el umbral.
- **Conjetura 2:** el resultado no cambia. La pérdida térmica es 0 % y ningún pulso se regenera.

### 5.6 Sensibilidad de la recuperación a la eficacia máxima del pulso

Recuperación promedio en el modo neuro-simbólico (%), con humedad inicial de 85 %. Un asterisco indica que la Conjetura 1 queda validada con ese valor. Esta tabla es solo un análisis de sensibilidad: el valor configurado sigue siendo 0.90.

| eta_max | DIA_NORMAL | INCRUSTACION_SALINA_RAPIDA | SEQUIA | TORMENTA_DE_ARENA | TORMENTA_DE_SAL_Y_CALOR_EXTREMO |
|---|---|---|---|---|---|
| 0.85 | 87.16 | 84.16 | 87.17 | 84.06 | 86.29 |
| 0.90 | 88.78 | 85.92 | 88.78 | 85.78 | 88.02 |
| 0.94 | 90.12* | 87.34 | 90.12* | 86.95 | 89.47 |
| 0.95 | 90.46* | 87.69 | 90.46* | 87.15 | 89.85 |
| 1.00 | 92.20* | 89.60 | 92.22* | 88.89 | 91.73* |

La Conjetura 1 depende de un parámetro que todavía no se ha medido. Antes de dar por refutada o validada la conjetura, la prioridad experimental es medir la fracción de sal que remueve un pulso de 90 s a 44 °C.

### 5.7 Sensibilidad del tiempo de regeneración a la eficacia máxima del pulso

Tiempo promedio de regeneración en el modo neuro-simbólico (s), con el criterio de 1100 Ohm y humedad inicial de 85 %. Entre paréntesis se indican los pulsos regenerados sobre los pulsos totales. Un asterisco indica que la Conjetura 2 queda validada. Igual que en 5.6, el valor configurado sigue siendo 0.90.

| eta_max | DIA_NORMAL | INCRUSTACION_SALINA_RAPIDA | SEQUIA | TORMENTA_DE_ARENA | TORMENTA_DE_SAL_Y_CALOR_EXTREMO |
|---|---|---|---|---|---|
| 0.90 | 11934.8 (0/46) | 6593.8 (0/97) | 21575.0 (0/24) | 10358.5 (0/53) | 9257.8 (0/64) |
| 0.95 | 12200.0 (0/45) | 6877.4 (0/93) | 21575.0 (0/24) | 10764.7 (0/51) | 9257.8 (0/64) |
| 0.96 | 12200.0 (0/45) | 6952.2 (0/92) | 21575.0 (0/24) | 10764.7 (0/51) | 9404.8 (0/63) |
| 0.97 | 84.5 (44/44)* | 3231.5 (49/92) | 84.1 (24/24)* | 2111.0 (35/51) | 1678.0 (52/62) |
| 1.00 | 69.1 (43/43)* | 711.0 (76/92) | 68.9 (23/23)* | 2001.1 (35/48) | 851.8 (56/62) |

El indicador tiene un comportamiento de umbral. Por debajo de `eta_max` cercano a 0.97, ningún pulso llega a 1100 Ohm. Por encima, la mayoría lo logra en menos de 90 s. Esto refuerza la recomendación de 5.6: medir la eficacia real del pulso define el resultado de las Conjeturas 1 y 2.

## 6. Interpretación de resultados

### 6.1 La Conjetura 2 contiene dos afirmaciones distintas

La Conjetura 2 sostiene que el pulso térmico controlado (<= 45 °C) disuelve las costras de NaCl sin degradar la matriz. Contiene dos afirmaciones que el simulador puede evaluar de forma muy distinta:

- **Ausencia de degradación térmica.** Se sostiene en el modelo. La pérdida de integridad térmica del modo neuro-simbólico es 0 % en los diez escenarios simulados (cinco con 45 % y cinco con 85 % de humedad inicial). Este resultado se deriva de la lógica de control y no de un parámetro supuesto: la REGLA_01 corta antes de 45 °C, el pulso apunta a 44 °C y en ningún caso el pulso superó 44.30 °C. El temporizador fijo, sin esas reglas, llegó a 55.9 °C y perdió hasta 2.69 % de integridad.
- **Eficacia de disolución.** No es verificable por simulación. Que un pulso de 90 s devuelva la membrana a 1100 Ohm depende de la eficacia del pulso (`eta_max`), un parámetro supuesto sin respaldo experimental. El modelo solo permite establecer qué eficacia haría falta, como se muestra en 6.2.

Por eso, el valor false de la Conjetura 2 no refuta la autorreparación. Indica que, con la eficacia supuesta de 0.90, el modelo no alcanza el criterio de regeneración.

### 6.2 Eficacia mínima del pulso para validar las Conjeturas 1 y 2

La tabla resume una búsqueda de `eta_max` entre 0.90 y 1.00 con paso de 0.01, manteniendo fijos los demás parámetros y el criterio de 1100 Ohm. Cada celda indica el menor valor con el que la conjetura completa queda validada, con todos sus indicadores cumpliendo. "No alcanza" significa que la conjetura no se valida ni con 1.00.

| Escenario | C1 (HR 45 %) | C2 (HR 45 %) | C1 (HR 85 %) | C2 (HR 85 %) |
|---|---|---|---|---|
| DIA_NORMAL | 0.94 | 0.97 | 0.94 | 0.97 |
| INCRUSTACION_SALINA_RAPIDA | 0.94 | 0.97 | No alcanza | No alcanza |
| SEQUIA | No alcanza (sin pulsos) | No alcanza (sin pulsos) | 0.94 | 0.97 |
| TORMENTA_DE_ARENA | No alcanza | No alcanza | No alcanza | No alcanza |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 0.94 | 0.97 | 0.97 | No alcanza |

`eta_max` es un parámetro del modelo y no se mide directamente. Para el pulso típico de las simulaciones (44 °C y unos 500 Ohm de carga salina), la fracción de costra que remueve un pulso es `eta = eta_max * 2500 / (2500 + 505)`. Por eso:

- `eta_max = 0.94` equivale a remover al menos el **78 %** de la costra en un pulso, que es lo que exige la Conjetura 1;
- `eta_max = 0.97` equivale a remover al menos el **81 %**, que es lo que exige la Conjetura 2.

Los casos que no alcanzan tienen causas identificables:

- **TORMENTA_DE_ARENA:** el ensuciamiento por polvo no se remueve con el pulso.
- **INCRUSTACION_SALINA_RAPIDA con 85 %:** la reserva se agota y el ahorro de energía no llega al 35 %.
- **TORMENTA_DE_SAL_Y_CALOR_EXTREMO con 85 %:** la REGLA_04 posterga pulsos cuando la reserva es baja. Algunos pulsos se aplican entonces con cargas de hasta unos 770 Ohm, y un solo pulso no alcanza a llevarlas a 1100 Ohm.
- **SEQUIA con 45 %:** no hay pulsos que medir.

### 6.3 Medición experimental prioritaria para el siguiente ciclo

Los valores de 6.2 definen el experimento prioritario del siguiente ciclo. Hay que medir, en una muestra de membrana con costra de NaCl equivalente a unos 500 Ohm sobre la impedancia nominal, qué fracción de la costra remueve un pulso de 90 s a 44 °C. El resultado decide el estado de dos conjeturas:

- si la fracción removida es menor que 78 %, el modelo predice que ni la Conjetura 1 ni la 2 se validan;
- entre 78 % y 81 %, se validaría la Conjetura 1 en los escenarios favorables;
- desde 81 %, se validarían ambas en esos escenarios.

Como mediciones secundarias, conviene registrar:

- el tiempo de disolución, que calibra la constante de 25 s;
- la diferencia entre la impedancia causada por sal y la causada por polvo, que explica el resultado de TORMENTA_DE_ARENA;
- el flujo de niebla disponible en Cabo de la Vela, del que depende el rendimiento nocturno de la Conjetura 3, como muestra la corrida con 45 %.

### 6.4 Endurecimiento del criterio de regeneración

El tiempo de regeneración se medía al principio hasta que la impedancia volvía bajo el umbral de 1500 Ohm. Ese criterio se cumplía de forma trivial. Como el pulso se dispara apenas la impedancia cruza 1500 Ohm, bastaba remover unos pocos ohmios, y el indicador daba entre 0.2 y 1.8 s sin informar sobre la limpieza real de la membrana.

Por esa razón, el criterio se endureció a 1100 Ohm (`FACTOR_IMPEDANCIA_REGENERADA = 1.10`, al menos 91 % de la conductancia nominal). Después de ese cambio, el criterio, la eficacia del pulso (0.90) y los demás parámetros se mantuvieron fijos. Ningún valor se ajustó para cambiar el resultado de una conjetura (decisión D5). Los análisis de sensibilidad de 5.6, 5.7 y 6.2 varían `eta_max` solo en memoria, con fines exploratorios, y no modifican la configuración del modelo.

La API expone ese análisis en `POST /api/v1/analisis/sensibilidad`, para la eficacia máxima del pulso y el flujo máximo de niebla. Cada valor se simula con una copia inmutable de los parámetros (`ParametrosModelo` en `backend/modelo_fisico.py`) en lugar de modificar `backend/config.py`, de modo que solicitudes simultáneas no se afectan entre sí. Con DIA_NORMAL, humedad inicial de 85 % y tasa ALTA, el endpoint reproduce los valores de 5.6 y 5.7: con 0.94 la recuperación es 90.12 % y la Conjetura 1 se valida; con 0.97 el tiempo de regeneración es 84.5 s y la Conjetura 2 se valida.

## 7. Barrido de salinidad: respuesta a la pregunta de investigación

La pregunta de investigación está en [01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2. Compara los dos modos de control en dos variables de respuesta a medida que aumenta la salinidad.

### 7.1 Indicadores

La respuesta de `POST /api/v1/simulacion/ejecutar` incluye dos campos en cada modo de `comparativa`:

- **`recuperacion_caudal_promedio_pct`:** promedio de `min(100, Z_nom / Z_tras_pulso * 100)` sobre todos los pulsos del modo. Es el mismo cálculo del indicador de la Conjetura 1 (sección 4), pero se reporta también para el temporizador. Vale `null` si el modo no ejecutó pulsos.
- **`degradacion_acumulada_pct`:** `100 - integridad_membrana_final_pct`. Suma la fatiga por pulso, la degradación térmica y la degradación por cristalización (sección 3.2), promediada entre nodos.

### 7.2 Método

- Escenarios `DIA_NORMAL` e `INCRUSTACION_SALINA_RAPIDA`, cada uno con tasas BAJA, MEDIA y ALTA.
- 24 h, inicio a las 18:00, paso de 5 min, 8 nodos, semilla 42, humedad inicial 85 %.
- Parámetros de `backend/config.py` sin modificar.

La carga salina efectiva es la tasa de incrustación por litro captado: 20, 40 y 80 Ohm por L/m² para BAJA, MEDIA y ALTA, multiplicada por 3 en `INCRUSTACION_SALINA_RAPIDA`. Las seis combinaciones forman un gradiente de 20 a 240 Ohm por L/m².

### 7.3 Resultados (humedad inicial 85 %)

| Carga salina (Ohm por L/m²) | Escenario y tasa | Recuperación neuro (%) | Recuperación temporizador (%) | Diferencia (puntos) | Degradación neuro (%) | Degradación temporizador (%) | Reducción del desgaste | Pulsos neuro / temporizador |
|---|---|---|---|---|---|---|---|---|
| 20 | DIA_NORMAL, BAJA | 88.85 | 95.84 | -7.0 | 0.020 | 2.071 | 99.0 % | 8 / 88 |
| 40 | DIA_NORMAL, MEDIA | 88.83 | 91.83 | -3.0 | 0.052 | 2.071 | 97.5 % | 21 / 88 |
| 60 | INCRUSTACION_SALINA_RAPIDA, BAJA | 88.80 | 88.02 | +0.8 | 0.082 | 2.117 | 96.1 % | 33 / 88 |
| 80 | DIA_NORMAL, ALTA | 88.78 | 84.45 | +4.3 | 0.115 | 2.427 | 95.3 % | 46 / 88 |
| 120 | INCRUSTACION_SALINA_RAPIDA, MEDIA | 88.02 | 78.02 | +10.0 | 0.408 | 3.070 | 86.7 % | 64 / 88 |
| 240 | INCRUSTACION_SALINA_RAPIDA, ALTA | 85.92 | 63.21 | +22.7 | 1.073 | 4.117 | 73.9 % | 97 / 88 |

La reducción del desgaste es `(D_temp - D_neuro) / D_temp * 100`.

Con humedad inicial de 45 % hay menos agua captada y, por tanto, menos sal. El modo neuro-simbólico no ejecuta pulsos en `DIA_NORMAL` con tasas BAJA y MEDIA, de modo que su recuperación no tiene datos, y su degradación es 0.000 %. En las combinaciones restantes, el patrón coincide con el de la tabla: la degradación neuro-simbólica queda entre 0.020 % y 0.110 %, frente a 2.071 % a 2.518 % del temporizador.

### 7.4 Interpretación

- **Desgaste.** El control neuro-simbólico degrada menos la membrana en los seis niveles de salinidad. El temporizador aplica 88 pulsos en 24 h sin importar el estado de la membrana. Cada pulso causa fatiga y, de día, eleva la matriz por encima de 45 °C (hasta 55.9 °C), lo que añade degradación térmica. El neuro-simbólico pulsa solo cuando la impedancia supera 1500 Ohm y nunca cruza 45 °C. La reducción del desgaste disminuye con la salinidad, de 99 % a 74 %, porque el neuro-simbólico necesita cada vez más pulsos y la membrana pasa más tiempo con impedancia alta.
- **Recuperación.** El neuro-simbólico mantiene una recuperación casi constante (85.9 % a 88.9 %), porque siempre pulsa con una carga salina parecida, unos 500 Ohm sobre la impedancia nominal. La recuperación del temporizador depende de cuánta sal se acumuló en las 2 h entre pulsos: con salinidad baja limpia una membrana casi limpia y recupera más, y con salinidad alta la sal se acumula más rápido de lo que un pulso cada 2 h puede retirar. Las curvas se cruzan entre 40 y 60 Ohm por L/m².
- **Respuesta a la pregunta.** En el modelo, el control neuro-simbólico reduce el desgaste de las membranas frente al temporizador en todo el rango de salinidad estudiado, y mejora la recuperación del caudal a partir de una carga salina moderada. Esta ventaja crece con la salinidad, lo que es coherente con la hipótesis de trabajo.

### 7.5 Limitaciones

- La recuperación tras pulso compara momentos distintos en cada modo: el neuro-simbólico mide justo después de un pulso disparado por impedancia alta, y el temporizador mide después de pulsos a intervalos fijos. Por eso, con salinidad baja, un valor alto del temporizador no indica una membrana mejor mantenida, sino una membrana que no necesitaba limpieza.
- Los valores absolutos dependen de parámetros supuestos, en especial la eficacia máxima del pulso (0.90), la fatiga por pulso y la degradación térmica (sección 3.4). La dirección de los resultados se explica por la lógica de control (pulsar por demanda frente a pulsar por horario, y el límite de 45 °C), pero su magnitud debe calibrarse con mediciones.
- Las cifras de 7.3 corresponden a una semilla. El barrido con varias semillas ya está disponible en la API (`POST /api/v1/analisis/barrido-salinidad`, de 1 a 5 semillas), que reporta la media y la desviación estándar muestral de cada variable. La tabla siguiente es el resultado con las semillas 1 a 5, con las demás condiciones de 7.2 (media +/- desviación).

| Carga salina (Ohm por L/m²) | Escenario y tasa | Recuperación neuro (%) | Recuperación temporizador (%) | Degradación neuro (%) | Degradación temporizador (%) | Reducción del desgaste |
|---|---|---|---|---|---|---|
| 20 | DIA_NORMAL, BAJA | 88.86 +/- 0.01 | 95.92 +/- 0.14 | 0.020 +/- 0.000 | 2.151 +/- 0.021 | 99.1 % |
| 40 | DIA_NORMAL, MEDIA | 88.83 +/- 0.01 | 91.95 +/- 0.24 | 0.052 +/- 0.004 | 2.151 +/- 0.021 | 97.6 % |
| 60 | INCRUSTACION_SALINA_RAPIDA, BAJA | 88.80 +/- 0.01 | 88.15 +/- 0.32 | 0.086 +/- 0.002 | 2.183 +/- 0.016 | 96.1 % |
| 80 | DIA_NORMAL, ALTA | 88.77 +/- 0.01 | 84.59 +/- 0.39 | 0.117 +/- 0.002 | 2.495 +/- 0.022 | 95.3 % |
| 120 | INCRUSTACION_SALINA_RAPIDA, MEDIA | 88.01 +/- 0.08 | 78.13 +/- 0.48 | 0.419 +/- 0.021 | 3.159 +/- 0.024 | 86.7 % |
| 240 | INCRUSTACION_SALINA_RAPIDA, ALTA | 85.89 +/- 0.07 | 63.24 +/- 0.58 | 1.082 +/- 0.013 | 4.210 +/- 0.014 | 74.3 % |

  La reducción del desgaste se calcula con las medias. La dispersión entre semillas es pequeña frente a las diferencias entre modos, y las conclusiones de 7.4 se mantienen: el neuro-simbólico degrada menos la membrana en los seis niveles (reducción de 74.3 % a 99.1 %), y las curvas de recuperación se cruzan entre 40 y 60 Ohm por L/m². En 60 Ohm por L/m² la ventaja del neuro-simbólico (0.65 puntos) equivale a unas dos desviaciones del temporizador, por lo que el punto de cruce es el resultado menos robusto del barrido. Las semillas solo varían el clima de referencia; la incertidumbre de los parámetros supuestos no está incluida en esta dispersión.

## 8. Lectura crítica de las conjeturas

### 8.1 Conflicto entre los indicadores de la Conjetura 1

La sección 5.5 muestra que la Conjetura 1 falla por la recuperación de caudal, mientras que el ahorro de energía cumple en la mayoría de los escenarios. Una pregunta natural es si disparar el pulso antes, con menos carga salina, resolvería el problema. Para responderla se ejecutó un análisis exploratorio con un script temporal, fuera del repositorio, que asigna en memoria `UMBRAL_IMPEDANCIA_OHMS` a 1500, 1400, 1300 y 1200 Ohm y ejecuta `ejecutar_simulacion` con estas condiciones:

- escenarios DIA_NORMAL, INCRUSTACION_SALINA_RAPIDA y TORMENTA_DE_SAL_Y_CALOR_EXTREMO;
- 24 h, inicio a las 18:00, paso de 5 min, 8 nodos, semilla 42, tasa ALTA, humedad inicial 85 %;
- los demás parámetros de `backend/config.py` sin modificar.

| Umbral (Ohm) | Escenario | Recuperación (%) | Ahorro (%) | C1 | Pulsos neuro / temporizador | Litros neuro / temporizador | Degradación neuro / temporizador (%) |
|---|---|---|---|---|---|---|---|
| 1500 | DIA_NORMAL | 88.78 | 46.50 | false | 46 / 88 | 254.60 / 340.40 | 0.115 / 2.427 |
| 1500 | INCRUSTACION_SALINA_RAPIDA | 85.92 | 12.49 | false | 97 / 88 | 185.37 / 240.94 | 1.073 / 4.117 |
| 1500 | TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 88.02 | 35.17 | false | 64 / 88 | 234.98 / 305.83 | 0.408 / 3.903 |
| 1400 | DIA_NORMAL | 91.50 | 30.47 | false | 60 / 88 | 261.71 / 339.81 | 0.216 / 2.798 |
| 1400 | INCRUSTACION_SALINA_RAPIDA | 88.65 | 4.35 | false | 113 / 88 | 183.48 / 240.83 | 1.231 / 4.275 |
| 1400 | TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 90.47 | 30.11 | false | 75 / 88 | 227.77 / 305.43 | 0.668 / 4.298 |
| 1300 | DIA_NORMAL | 93.63 | 25.09 | false | 70 / 88 | 248.94 / 339.14 | 0.566 / 3.275 |
| 1300 | INCRUSTACION_SALINA_RAPIDA | 91.31 | -8.64 | false | 136 / 88 | 178.99 / 240.74 | 1.423 / 4.381 |
| 1300 | TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 92.82 | 28.15 | false | 88 / 88 | 218.71 / 305.01 | 0.942 / 4.715 |
| 1200 | DIA_NORMAL | 95.68 | 16.16 | false | 89 / 88 | 231.90 / 338.45 | 0.954 / 3.858 |
| 1200 | INCRUSTACION_SALINA_RAPIDA | 93.90 | -26.58 | false | 176 / 88 | 173.20 / 240.70 | 1.680 / 4.419 |
| 1200 | TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 95.06 | 20.22 | false | 115 / 88 | 209.42 / 304.68 | 1.236 / 5.052 |

Las filas de 1500 Ohm coinciden con las secciones 5.3, 5.4 y 7.3. Un ahorro negativo indica que el modo neuro-simbólico gastó más energía en pulsos que el temporizador.

El umbral no solo dispara el pulso: también define el criterio de degradación por cristalización (pérdida de 0.10 %/h mientras Z supera el umbral, sección 3.2), que se aplica a ambos modos. Por eso, al bajar el umbral, la degradación y los litros del temporizador también cambian, aunque su programación de pulsos no dependa de la impedancia.

Los dos indicadores de la Conjetura 1 se mueven en direcciones opuestas:

- **Recuperación.** Con un umbral más bajo, el pulso actúa sobre menos carga salina, remueve una fracción mayor y deja la membrana más cerca de la impedancia nominal. La recuperación supera el 90 % desde 1400 Ohm en DIA_NORMAL y TORMENTA_DE_SAL_Y_CALOR_EXTREMO, y desde 1300 Ohm en INCRUSTACION_SALINA_RAPIDA.
- **Ahorro.** Con un umbral más bajo, el pulso se dispara más veces y el ahorro de energía cae. Solo con 1500 Ohm alcanza el 35 % (DIA_NORMAL y TORMENTA_DE_SAL_Y_CALOR_EXTREMO). Con 1200 Ohm, el modo neuro-simbólico pulsa más veces que el temporizador en los tres escenarios.

Ningún umbral entre 1200 y 1500 Ohm satisface a la vez la recuperación >= 90 % y el ahorro >= 35 % en los escenarios evaluados. Con la eficacia del pulso supuesta (0.90), el conflicto es estructural: un umbral fijo único no puede optimizar los dos indicadores al mismo tiempo. Bajar el umbral también aumenta la degradación neuro-simbólica en los tres escenarios, por la fatiga de los pulsos adicionales y por el criterio de cristalización más estricto. Con 1300 y 1200 Ohm, el agua captada por el modo neuro-simbólico es menor que con 1500 Ohm en los tres escenarios.

Este es un análisis exploratorio. No modifica `backend/config.py` y el umbral de 1500 Ohm del PRD se mantiene. Ningún valor se ajustó para cambiar el resultado de una conjetura (decisión D5).

### 8.2 Umbral de la Conjetura 3 frente a la literatura

La comparación completa está en [06_Referencias_y_Trazabilidad_AxiomaH.md](06_Referencias_y_Trazabilidad_AxiomaH.md), sección 4. En síntesis, con humedad inicial de 85 % el modelo obtiene 16.97 L/m²/noche en DIA_NORMAL (sección 5.4), por encima del rango de 3 a 10 L/m²/día que Klemm et al. (2012) reportan para proyectos operativos de captación de niebla. Por eso:

- el flujo máximo de niebla supuesto (`FLUJO_NIEBLA_MAXIMO_L_M2_H = 6.0`) es optimista;
- el umbral de 12 L/m²/noche de la Conjetura 3 supera el rango típico de operación.

La validación de la Conjetura 3 en cuatro escenarios con humedad inicial de 85 % depende de ese flujo optimista. Con humedad inicial de 45 %, el rendimiento del modelo (4.0 a 6.0 L/m²/noche, sección 5.5) queda dentro del rango de la literatura y la conjetura no se valida.

### 8.3 Preguntas emergentes para el Ciclo 3

a) ¿Un umbral de disparo adaptativo, que dependa por ejemplo de la reserva o de la tasa de incrustación, puede cumplir a la vez la recuperación y el ahorro de la Conjetura 1? La sección 8.1 muestra que un umbral fijo no lo logra.

b) ¿Qué fracción de la costra remueve un pulso de 90 s a 44 °C? Es la medición experimental prioritaria descrita en 6.3, de la que depende el estado de las Conjeturas 1 y 2.

c) ¿Un estimador sub-simbólico puede distinguir la impedancia causada por sal de la causada por polvo? Esa distinción explica el resultado de TORMENTA_DE_ARENA (sección 6.2), donde el ensuciamiento por polvo eleva la impedancia y no se remueve con el pulso.

d) ¿Cuál es el rendimiento real de niebla en Cabo de la Vela? De él dependen el flujo supuesto y la pertinencia del umbral de la Conjetura 3 (sección 8.2).

e) Reoperacionalizar la Conjetura 2 en dos indicadores declarados antes de ejecutar las simulaciones: la cinética de desprendimiento (< 120 s) y la extensión de la limpieza (Z <= 1100 Ohm). Hoy ambos aspectos se miden en un solo indicador, el tiempo hasta 1100 Ohm, y el criterio se endureció después de observar los primeros resultados (sección 6.4).

### 8.4 Control de confusión: tope ecológico frente a lógica de control

El modo neuro-simbólico capta menos agua que el temporizador fijo (sección 5.5), pero los dos modos difieren en dos aspectos a la vez: la lógica de control (reglas frente a programación fija) y la fracción de extracción (0.33 frente a 0.45). Para separar ambos efectos, cada simulación ejecuta además un temporizador con tope ecológico (sección 3.3): la misma programación del temporizador fijo con la fracción de 0.33.

Con L_neuro, L_temp y L_temp33 como el agua captada por el neuro-simbólico, el temporizador fijo y el temporizador con tope:

- brecha total = `L_temp - L_neuro`;
- parte debida al tope ecológico = `L_temp - L_temp33`;
- parte debida a la lógica de control = `L_temp33 - L_neuro`.

Condiciones: 24 h, inicio a las 18:00, paso de 5 min, 8 nodos, semilla 42, tasa ALTA y parámetros de `backend/config.py` sin modificar. Las columnas de neuro-simbólico y temporizador 0.45 coinciden con las secciones 5.2 a 5.4.

| Escenario | Humedad inicial | Neuro-simbólico (L) | Temporizador 0.45 (L) | Temporizador 0.33 (L) | Brecha total (L) | Por tope (L) | Por lógica de control (L) | Brecha debida al tope (%) | Violaciones del temporizador 0.33 |
|---|---|---|---|---|---|---|---|---|---|
| DIA_NORMAL | 45 % | 82.7 | 126.6 | 95.5 | 43.9 | 31.1 | 12.8 | 70.9 | 0 |
| INCRUSTACION_SALINA_RAPIDA | 45 % | 80.5 | 106.2 | 83.1 | 25.7 | 23.1 | 2.6 | 89.8 | 0 |
| SEQUIA | 45 % | 40.8 | 63.6 | 47.7 | 22.9 | 16.0 | 6.9 | 69.8 | 8 |
| TORMENTA_DE_ARENA | 45 % | 77.9 | 116.8 | 88.1 | 38.9 | 28.6 | 10.2 | 73.7 | 0 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 45 % | 81.7 | 120.4 | 91.8 | 38.8 | 28.6 | 10.1 | 73.9 | 0 |
| DIA_NORMAL | 85 % | 254.6 | 340.4 | 266.1 | 85.8 | 74.3 | 11.5 | 86.6 | 0 |
| INCRUSTACION_SALINA_RAPIDA | 85 % | 185.4 | 240.9 | 198.6 | 55.6 | 42.3 | 13.2 | 76.2 | 0 |
| SEQUIA | 85 % | 149.4 | 204.4 | 158.7 | 55.0 | 45.7 | 9.3 | 83.1 | 8 |
| TORMENTA_DE_ARENA | 85 % | 232.4 | 306.4 | 239.3 | 74.0 | 67.1 | 6.8 | 90.8 | 0 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 85 % | 235.0 | 305.8 | 243.7 | 70.9 | 62.2 | 8.7 | 87.7 | 0 |

Las partes se calculan con los litros de la respuesta (3 decimales) y se redondean después, por lo que su suma puede diferir de la brecha total en 0.1 L.

- **La mayor parte de la brecha se debe al tope ecológico.** Entre 69.8 % y 89.8 % con humedad inicial de 45 %, y entre 76.2 % y 90.8 % con 85 %. El menor rendimiento del modo neuro-simbólico es, sobre todo, el costo de la decisión D3, no de la lógica de control.
- **La lógica de control explica entre 2.6 y 13.2 L** en 24 h y 8 nodos. Es el efecto neto de las demás diferencias entre los dos modos: la pausa ecológica, la reducción del caudal durante el pulso y en reserva crítica (80 % y 50 % del tope), la impedancia con que opera cada modo y la integridad de la membrana.
- **El tope por sí solo no evita las violaciones ecológicas.** En SEQUIA, el temporizador con tope registra 8 violaciones, un episodio por nodo, porque extrae con humedad relativa menor que 30 %. El neuro-simbólico no tiene violaciones porque, además del tope, aplica la REGLA_02.

El modo de referencia es informativo: no cambia la validación de las conjeturas ni los resultados de los otros dos modos.

### 8.5 Cinética frente a extensión en la Conjetura 2

La sección 8.3 e) propone separar la Conjetura 2 en dos aspectos: qué tan rápido actúa el pulso (cinética) y cuánto limpia (extensión). Los indicadores informativos de la sección 4 permiten observarlos por separado, sin cambiar el indicador que decide la validación.

| Escenario | Humedad inicial | t95 promedio (s) | Impedancia promedio tras pulso (Ohm) | Pulsos regenerados | Tiempo de regeneración (s) |
|---|---|---|---|---|---|
| DIA_NORMAL | 45 % | 64.4 | 1125.6 | 0/10 | 32400.00 |
| INCRUSTACION_SALINA_RAPIDA | 45 % | 64.4 | 1126.6 | 0/44 | 12013.64 |
| SEQUIA | 45 % | Sin datos | Sin datos | 0/0 | Sin datos |
| TORMENTA_DE_ARENA | 45 % | 64.4 | 1196.8 | 0/18 | 18000.00 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 45 % | 64.4 | 1126.0 | 0/19 | 22263.16 |
| DIA_NORMAL | 85 % | 64.4 | 1126.3 | 0/46 | 11934.78 |
| INCRUSTACION_SALINA_RAPIDA | 85 % | 64.4 | 1174.7 | 0/97 | 6593.81 |
| SEQUIA | 85 % | 64.4 | 1126.4 | 0/24 | 21575.00 |
| TORMENTA_DE_ARENA | 85 % | 64.4 | 1170.1 | 0/53 | 10358.49 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 85 % | 64.4 | 1136.7 | 0/64 | 9257.81 |

- **Cinética.** El pulso logra el 95 % de su remoción en 64.4 s, por debajo del umbral de 120 s. El valor es el mismo en todos los escenarios porque cada pulso neuro-simbólico alcanza al menos 44 °C, de modo que `g(T) = 1` y `t95` depende solo de la constante de disolución supuesta (25 s). Es una propiedad del modelo y no una medición.
- **Extensión.** Al terminar el pulso, la impedancia promedio queda entre 1125.6 y 1126.6 Ohm cuando el pulso se aplica apenas Z supera 1500 Ohm, por encima del criterio de 1100 Ohm. Por eso ningún pulso se regenera. El promedio sube en dos casos:
  - en TORMENTA_DE_ARENA (1170.1 y 1196.8 Ohm), porque el pulso no remueve el polvo;
  - con 85 % en INCRUSTACION_SALINA_RAPIDA (1174.7 Ohm) y TORMENTA_DE_SAL_Y_CALOR_EXTREMO (1136.7 Ohm), porque la REGLA_04 se activa con la reserva baja (16 y 8 veces en la bitácora) y posterga pulsos, que luego se aplican con más carga salina (sección 6.2). En DIA_NORMAL con 85 % la REGLA_04 no se activa.

En el modelo, el pulso actúa rápido pero no limpia lo suficiente. La Conjetura 2 no falla por la cinética, sino por la extensión de la limpieza, que depende de la eficacia del pulso (`eta_max`), un parámetro supuesto. Si los dos indicadores de la pregunta 8.3 e) se declaran antes de ejecutar, la cinética cumpliría en el modelo y la extensión no, y el experimento de la sección 6.3 es el que decide la extensión.
