# Modelo de control y simulación del motor Axioma-H

**Proyecto:** Axioma-H — Captación Pasiva de Agua Atmosférica  
**Equipo:** AXIOMA — Curso Fundamentos de Investigación (UdeA), Ciclo 2  
**Repositorio:** https://github.com/crd10lop/axioma-h-engine  
**Aplicación desplegada:** [Dashboard](https://axioma-h-dashboard.onrender.com) | [API](https://axioma-h-api.onrender.com/docs)

Este documento describe el motor de reglas neuro-simbólico, el simulador comparativo y la forma en que se verifican las conjeturas del Ciclo 2. Los valores de todos los parámetros están en `backend/config.py`. Las ecuaciones compartidas por el motor y el simulador están en `backend/modelo_fisico.py`. Los parámetros supuestos que se varían en los análisis, la eficacia máxima del pulso, el flujo máximo de niebla y, desde la versión 0.4.0, la fatiga por pulso y la degradación térmica, se agrupan además en `ParametrosModelo` (`backend/modelo_fisico.py`), que toma por defecto los valores de `backend/config.py`. El barrido de salinidad con varias semillas y la sensibilidad están en `backend/analisis.py` (secciones 6.4 y 7.5), junto con la robustez de la respuesta frente a los parámetros supuestos (sección 8.8), la robustez del desgaste (sección 8.11), la calibración del flujo para otro sitio (sección 8.12) y el dimensionamiento del captador (sección 7.7). El impacto comunitario estimado está en `backend/impacto.py` (sección 7.6). La transferencia del modelo a otro sitio se describe en la sección 8.10.

Los documentos de referencia son el PRD de la API ([02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md)) y la Matriz de Operacionalización ([01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md)). Las decisiones de la sección 1 resuelven las diferencias entre ambos.

## 1. Decisiones de diseño

| Id | Decisión | Justificación |
|----|----------|---------------|
| D1 | El corte térmico de emergencia se activa con T >= 45.0 °C. El pulso resistivo apunta a 44.0 °C. | La Conjetura 2 exige pulsos de hasta 45 °C sin activar el corte. Un objetivo de 44 °C deja 1 °C de margen frente al límite absoluto. |
| D2 | La regla de reserva crítica aplica solo si la reserva es menor que 30 % y la impedancia es mayor que 1500 Ohm. | Se adopta la versión del PRD. Una reserva baja sin cristalización no requiere intervención, porque no hay pulso que proteger. |
| D3 | El sistema nunca extrae más del 33 % de la niebla disponible. `ajuste_caudal_pct` es relativo a ese tope. | Es el límite ecológico de la Matriz. Expresar el caudal relativo al tope impide superarlo por construcción. |
| D4 | El enum de escenarios es único: DIA_NORMAL, INCRUSTACION_SALINA_RAPIDA, SEQUIA, TORMENTA_DE_ARENA y TORMENTA_DE_SAL_Y_CALOR_EXTREMO. | Unifica los nombres del PRD y de la Matriz. |
| D5 | Los resultados y la validación de conjeturas se calculan con el modelo. No se fijan valores ni se ajustan parámetros para forzar resultados. | Garantiza que el simulador sirva como instrumento de verificación y no como confirmación circular. |
| D6 | Un operador puede intervenir en la decisión de un nodo (REGLA_06), pero solo puede ser más conservador que el motor: suspender la extracción o inhibir el pulso, nunca forzar extracción ni pulsos. La REGLA_01 y la REGLA_02 prevalecen sobre su decisión. | Incorpora supervisión humana sin abrir una vía para saltarse los límites térmico y ecológico. Que la intervención solo pueda reducir el caudal o retirar el pulso la hace segura por construcción. |

## 2. Reglas de control

Las reglas se evalúan en el orden de la tabla y la primera que se cumple decide. La REGLA_04 se evalúa antes que la REGLA_03 porque ambas comparten la condición de impedancia alta y la REGLA_04 protege la reserva. La REGLA_06 conserva la numeración del PRD, por eso es la 06 aunque se evalúe en tercer lugar.

| Prioridad | Regla | Condición | Estado | Acción | Pulso | Caudal (% del tope) |
|---|---|---|---|---|---|---|
| 1 | REGLA_01_LIMITE_TERMICO_ABSOLUTO | T >= 45.0 °C | EMERGENCIA_TERMICA | CORTE_DE_EMERGENCIA | No | 0 |
| 2 | REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL | HR < 30.0 % | PAUSA_ECOLOGICA | PAUSA_ECOLOGICA | No | 0 |
| 3 | REGLA_06_SUPERVISION_HUMANA | `anulacion_manual = SUSPENDER_EXTRACCION` | SUPERVISION_HUMANA | SUSPENSION_MANUAL | No | 0 |
| 3 | REGLA_06_SUPERVISION_HUMANA | `anulacion_manual = INHIBIR_PULSO` y Z > 1500 Ohm | SUPERVISION_HUMANA | REDUCIR_CAUDAL_SIN_PULSO | No | 50 |
| 4 | REGLA_04_PROTECCION_RESERVA_CRITICA | Reserva < 30.0 % y Z > 1500 Ohm | RESERVA_CRITICA | REDUCIR_CAUDAL_SIN_PULSO | No | 50 |
| 5 | REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA | Z > 1500 Ohm y reserva >= 30.0 % | CRISTALIZACION_DETECTADA | APLICAR_PULSO_RESISTIVO | 44 °C, 90 s | 80 |
| 6 | REGLA_05_OPERACION_NOMINAL | Ningún caso anterior | NOMINAL | FILTRACION_PASIVA_CONTINUA | No | 100 |

**Supervisión humana (decisión D6).** `anulacion_manual` es un campo opcional de la telemetría, con valor `NINGUNA` por defecto, que no cambia ninguna decisión del motor. Con `INHIBIR_PULSO` e impedancia de 1500 Ohm o menos, la REGLA_06 no actúa y decide la REGLA_05, porque no hay pulso que inhibir. En cada caso el caudal resultante es menor o igual que el de la regla automática y nunca hay pulso. El `motivo` indica que la decisión es del operador y qué regla automática habría aplicado. La anulación solo existe en la evaluación individual: el simulador construye la telemetría con `NINGUNA`, de modo que sus resultados no cambian.

En modo `TEMPORIZADOR_FIJO`, el endpoint de evaluación no aplica reglas ni la anulación manual. Devuelve `FILTRACION_PASIVA_CONTINUA` con caudal del 100 % y regla `SIN_REGLAS_TEMPORIZADOR_FIJO`.

### Métricas de una evaluación individual

- **Recuperación hidráulica:** `min(100, Z_nom / Z_tras * 100)`. Con pulso, `Z_tras = Z_nom + Z_sal * (1 - eta)`, donde `Z_sal = Z - Z_nom`. Sin pulso, `Z_tras = Z`.
- **Eficiencia energética:** `100 * R / (R + C)`. R son los puntos porcentuales de conductancia recuperados y C los puntos porcentuales de reserva que consume el pulso. Vale 100 si la acción no consume reserva.
- **Preservación ecológica:** es verdadera si no se extrae agua con HR < 30 % y la fracción efectiva no supera 0.33. Se interpreta como ausencia de violación. Por eso una pausa ecológica, con HR baja y caudal nulo, se considera conforme. El modo temporizador, con fracción fija de 0.45, nunca lo es.

## 3. Ecuaciones del simulador

La simulación arranca a las 18:00 hora local y avanza en pasos de `paso_minutos` durante `duracion_horas`. Ambos modos se ejecutan sobre el mismo entorno, que se genera una sola vez con `random.Random(semilla)`.

### 3.1 Entorno

- **Radiación relativa:** `S(h) = sen(pi * (h - 6) / 12)` entre 06:00 y 18:00, y 0 fuera de ese intervalo.
- **Humedad relativa:** `HR(h) = HR_0 + A_HR * [cos(2 pi (h - 4) / 24) - cos(2 pi (18 - 4) / 24)] + d_n + e`, acotada entre 0 y 100. HR_0 es la humedad a las 18:00, d_n el desfase fijo del nodo y e el ruido gaussiano por paso.
- **Temperatura ambiente:** `T_a(h) = T_med + A_T * cos(2 pi (h - 14) / 24)`, con `T_med = 30` y `A_T = 4.5` en el perfil por defecto.
- **Temperatura de la matriz:** `T_m = T_a + 7 * S(h) * f_rad + d_n + e`.

`A_HR`, `T_med` y `A_T` provienen del perfil del sitio (campo opcional `sitio` de `SimulationConfig`, modelo `PerfilSitio`), junto con el flujo máximo de niebla. Sin `sitio`, se usan los valores de Cabo de la Vela de `backend/config.py` (`A_HR = 10`) y los resultados son idénticos a los de una solicitud sin ese campo. La sección 8.10 describe cómo usar el perfil para otro sitio.

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
- **Temporizador con salvaguardas (análisis exploratorio):** el parámetro interno `salvaguardas_temporizador` de `simular_modo`, falso por defecto, agrega al temporizador el corte a 45 °C, la pausa con HR < 30 % y un pulso limitado a 44 °C. No se expone en la API ni cambia los resultados de las secciones 5 a 8.12; se usa en la sección 8.13 para contrastar si la ventaja en desgaste se debe a la lógica de control o a las salvaguardas.
- **Intervalo del temporizador (análisis exploratorio):** el parámetro interno `intervalo_temporizador_min` de `simular_modo`, nulo por defecto, fija los minutos entre pulsos programados; con el valor nulo se usan los 120 min de `INTERVALO_PULSO_TEMPORIZADOR_MIN` y los resultados no cambian. Debe ser positivo. Tampoco se expone en la API; se usa en la sección 8.14 para variar el intervalo del temporizador con salvaguardas.

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
| Flujo máximo de niebla | 6.0 L/m²/h (0.35 g/m³ a 5 m/s) | Supuesto | Sin fuente; contrastado con Klemm et al. (2012) en [Documento 06, sección 4](06_Referencias_y_Trazabilidad_AxiomaH.md#4-comparación-del-flujo-de-niebla-supuesto-con-la-literatura). La calibración inversa contra la literatura da 0.49 a 1.83 L/m²/h (sección 8.6) |
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

Los resultados de las secciones 5.1 a 5.4, junto con el modo de referencia de la sección 8.4, el barrido con semillas 1 a 5 de la sección 7.5 y la robustez de la sección 8.8, están también como datos abiertos en [datos/](datos/README.md) (CSV, JSON y descriptor Data Package). Se regeneran sin la API con `python scripts/generar_resultados_referencia.py`.

### 5.1 Corrida de referencia del PRD (TORMENTA_DE_SAL_Y_CALOR_EXTREMO, humedad inicial 45 %)

Es el payload de ejemplo del PRD (sección 3.2): `duracion_horas` 24, `escenario` TORMENTA_DE_SAL_Y_CALOR_EXTREMO, `humedad_ambiente_inicial_pct` 45.0 y `tasa_salinizacion` ALTA. Los valores numéricos de la respuesta de ejemplo del PRD son ilustrativos. Los de esta tabla son los que calcula el modelo.

| Métrica | Control basado en reglas (modo neuro-simbólico) | Temporizador fijo | Diferencia |
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
| DIA_NORMAL | Control basado en reglas (modo neuro-simbólico) | 254.60 | 46 | 664.5 | 99.89 | 0 |
| DIA_NORMAL | Temporizador fijo | 340.40 | 88 | 1065.1 | 97.57 | 8 |
| INCRUSTACION_SALINA_RAPIDA | Control basado en reglas (modo neuro-simbólico) | 185.37 | 97 | 1013.7 | 98.93 | 0 |
| INCRUSTACION_SALINA_RAPIDA | Temporizador fijo | 240.94 | 88 | 1065.1 | 95.88 | 8 |
| SEQUIA | Control basado en reglas (modo neuro-simbólico) | 149.35 | 24 | 491.9 | 99.84 | 0 |
| SEQUIA | Temporizador fijo | 204.40 | 88 | 1065.1 | 97.78 | 8 |
| TORMENTA_DE_ARENA | Control basado en reglas (modo neuro-simbólico) | 232.43 | 53 | 752.1 | 99.87 | 0 |
| TORMENTA_DE_ARENA | Temporizador fijo | 306.41 | 88 | 1065.1 | 98.18 | 8 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | Control basado en reglas (modo neuro-simbólico) | 234.98 | 64 | 780.8 | 99.59 | 0 |
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

| Carga salina (Ohm por L/m²) | Escenario y tasa | Recuperación, control basado en reglas (modo neuro-simbólico) (%) | Recuperación temporizador (%) | Diferencia (puntos) | Degradación, control basado en reglas (modo neuro-simbólico) (%) | Degradación temporizador (%) | Reducción del desgaste | Pulsos: control basado en reglas (modo neuro-simbólico) / temporizador |
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
- Los valores absolutos dependen de parámetros supuestos, en especial la eficacia máxima del pulso (0.90), la fatiga por pulso y la degradación térmica (sección 3.4). La dirección de los resultados se explica por la lógica de control (pulsar por demanda frente a pulsar por horario, y el límite de 45 °C), pero su magnitud debe calibrarse con mediciones. La sección 8.11 varía la fatiga por pulso y la degradación térmica entre la mitad y el doble de su valor: la reducción del desgaste sigue siendo positiva en todos los puntos, y su mínimo va de 61.5 % a 83.7 % con el flujo supuesto.
- Las cifras de 7.3 corresponden a una semilla. El barrido con varias semillas ya está disponible en la API (`POST /api/v1/analisis/barrido-salinidad`, de 1 a 5 semillas), que reporta la media y la desviación estándar muestral de cada variable. La tabla siguiente es el resultado con las semillas 1 a 5, con las demás condiciones de 7.2 (media +/- desviación).

| Carga salina (Ohm por L/m²) | Escenario y tasa | Recuperación, control basado en reglas (modo neuro-simbólico) (%) | Recuperación temporizador (%) | Degradación, control basado en reglas (modo neuro-simbólico) (%) | Degradación temporizador (%) | Reducción del desgaste |
|---|---|---|---|---|---|---|
| 20 | DIA_NORMAL, BAJA | 88.86 +/- 0.01 | 95.92 +/- 0.14 | 0.020 +/- 0.000 | 2.151 +/- 0.021 | 99.1 % |
| 40 | DIA_NORMAL, MEDIA | 88.83 +/- 0.01 | 91.95 +/- 0.24 | 0.052 +/- 0.004 | 2.151 +/- 0.021 | 97.6 % |
| 60 | INCRUSTACION_SALINA_RAPIDA, BAJA | 88.80 +/- 0.01 | 88.15 +/- 0.32 | 0.086 +/- 0.002 | 2.183 +/- 0.016 | 96.1 % |
| 80 | DIA_NORMAL, ALTA | 88.77 +/- 0.01 | 84.59 +/- 0.39 | 0.117 +/- 0.002 | 2.495 +/- 0.022 | 95.3 % |
| 120 | INCRUSTACION_SALINA_RAPIDA, MEDIA | 88.01 +/- 0.08 | 78.13 +/- 0.48 | 0.419 +/- 0.021 | 3.159 +/- 0.024 | 86.7 % |
| 240 | INCRUSTACION_SALINA_RAPIDA, ALTA | 85.89 +/- 0.07 | 63.24 +/- 0.58 | 1.082 +/- 0.013 | 4.210 +/- 0.014 | 74.3 % |

  La reducción del desgaste se calcula con las medias. La dispersión entre semillas es pequeña frente a las diferencias entre modos, y las conclusiones de 7.4 se mantienen: el neuro-simbólico degrada menos la membrana en los seis niveles (reducción de 74.3 % a 99.1 %), y las curvas de recuperación se cruzan entre 40 y 60 Ohm por L/m². En 60 Ohm por L/m² la ventaja del neuro-simbólico (0.65 puntos) equivale a unas dos desviaciones del temporizador, por lo que el punto de cruce es el resultado menos robusto del barrido. Las semillas solo varían el clima de referencia; la incertidumbre de los parámetros supuestos no está incluida en esta dispersión.

### 7.6 Impacto comunitario estimado

La respuesta de `POST /api/v1/simulacion/ejecutar` incluye el campo `impacto_comunitario`, con una entrada por modo (`modo_neuro_simbolico`, `modo_temporizador_fijo` y `modo_temporizador_tope_ecologico`). Traduce el agua captada en personas abastecidas. Es un indicador informativo: no interviene en la validación de las conjeturas ni en las decisiones del motor. Se calcula en `backend/impacto.py` a partir de `litros_totales_agua` de cada modo:

- `litros_dia_red = litros_totales * 24 / duracion_horas`.
- `rendimiento_l_m2_dia = litros_dia_red / (AREA_COLECTOR_M2 * numero_nodos)`, con 1 m² por nodo.
- `personas_supervivencia = litros_dia_red / 15`, el mínimo de 15 L por persona al día del estándar 2.1 de Sphere (2018).
- `personas_acceso_basico = litros_dia_red / 20`, el acceso básico de unos 20 L por persona al día de la OMS (Howard et al., 2020).
- `area_m2_por_persona_basico_literatura_min = 20 / 10 = 2.0` y `area_m2_por_persona_basico_literatura_max = 20 / 3 = 6.67`: m² de colector por persona para el acceso básico con el rendimiento máximo y mínimo de proyectos reales, de 3 a 10 L/m² al día según Klemm et al. (2012). No dependen de la simulación.

Resultados con 24 h, tasa ALTA, 8 nodos (8 m² de colector) y semilla 42. Cada celda muestra control basado en reglas (modo neuro-simbólico) / temporizador fijo / temporizador con tope ecológico.

| Escenario | Humedad inicial | Litros por día | L/m² al día | Personas con 15 L | Personas con 20 L |
|---|---|---|---|---|---|
| DIA_NORMAL | 45 % | 82.7 / 126.6 / 95.5 | 10.34 / 15.83 / 11.94 | 5.5 / 8.4 / 6.4 | 4.1 / 6.3 / 4.8 |
| INCRUSTACION_SALINA_RAPIDA | 45 % | 80.5 / 106.2 / 83.1 | 10.06 / 13.27 / 10.39 | 5.4 / 7.1 / 5.5 | 4.0 / 5.3 / 4.2 |
| SEQUIA | 45 % | 40.8 / 63.6 / 47.7 | 5.10 / 7.95 / 5.96 | 2.7 / 4.2 / 3.2 | 2.0 / 3.2 / 2.4 |
| TORMENTA_DE_ARENA | 45 % | 77.9 / 116.8 / 88.1 | 9.74 / 14.60 / 11.02 | 5.2 / 7.8 / 5.9 | 3.9 / 5.8 / 4.4 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 45 % | 81.7 / 120.4 / 91.8 | 10.21 / 15.05 / 11.47 | 5.4 / 8.0 / 6.1 | 4.1 / 6.0 / 4.6 |
| DIA_NORMAL | 85 % | 254.6 / 340.4 / 266.1 | 31.83 / 42.55 / 33.26 | 17.0 / 22.7 / 17.7 | 12.7 / 17.0 / 13.3 |
| INCRUSTACION_SALINA_RAPIDA | 85 % | 185.4 / 240.9 / 198.6 | 23.17 / 30.12 / 24.83 | 12.4 / 16.1 / 13.2 | 9.3 / 12.0 / 9.9 |
| SEQUIA | 85 % | 149.4 / 204.4 / 158.7 | 18.67 / 25.55 / 19.83 | 10.0 / 13.6 / 10.6 | 7.5 / 10.2 / 7.9 |
| TORMENTA_DE_ARENA | 85 % | 232.4 / 306.4 / 239.3 | 29.05 / 38.30 / 29.91 | 15.5 / 20.4 / 16.0 | 11.6 / 15.3 / 12.0 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 85 % | 235.0 / 305.8 / 243.7 | 29.37 / 38.23 / 30.46 | 15.7 / 20.4 / 16.2 | 11.7 / 15.3 / 12.2 |

**Interpretación.**

- **Escala.** Con el flujo de niebla supuesto y humedad inicial de 85 %, la red de 8 m² con control neuro-simbólico abastecería a unas 12 personas al nivel de acceso básico en DIA_NORMAL (12.7), y entre 7.5 y 12.7 según el escenario. Con 45 % la cifra baja a entre 2.0 y 4.1 personas. Es la escala de una vivienda o de un grupo familiar, no de una comunidad.
- **Rendimiento frente a la literatura.** Con 85 % el rendimiento simulado del neuro-simbólico, de 18.67 a 31.83 L/m² al día, supera el rango de 3 a 10 L/m² al día de proyectos reales; en DIA_NORMAL es 3.2 veces el extremo superior. Con 45 % queda entre 5.10 y 10.34, cerca o dentro de ese rango. Las cifras de 85 % heredan el carácter optimista del flujo de niebla supuesto (sección 8.2). Con los rendimientos reales de la literatura harían falta de 2 a 6.7 m² de colector por persona para el acceso básico, frente a los 0.63 m² por persona que implica el modelo en DIA_NORMAL con 85 % (8 m² para 12.7 personas).
- **Costo social del tope ecológico.** El tope reduce las personas abastecidas frente al temporizador. El neuro-simbólico abastece entre 2.8 y 4.3 personas menos que el temporizador fijo con 85 %, y entre 1.1 y 2.2 menos con 45 %. Comparando los dos temporizadores, que solo difieren en la fracción de extracción (0.45 frente a 0.33), el tope por sí solo resta entre 2.1 y 3.7 personas con 85 % y entre 0.8 y 1.6 con 45 %. Es la otra cara del costo hídrico de la sección 5.5: preservar la humedad para la vegetación tiene un costo en personas abastecidas que debe discutirse con las comunidades ([01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.7).
- **Alcance.** El cálculo supone que toda el agua captada se destina al consumo, sin pérdidas de almacenamiento ni de distribución, y no considera la variación estacional de la niebla. Los estándares de 15 y 20 L por persona al día son mínimos para bebida e higiene doméstica básica; no incluyen usos productivos.

### 7.7 Dimensionamiento

La sección 7.6 responde cuántas personas abastece una red de 8 m². El dimensionamiento responde la pregunta inversa: cuánta área de colector, y cuántos nodos, hacen falta para un número de personas. Lo calcula `POST /api/v1/analisis/dimensionamiento` (`ejecutar_dimensionamiento` en `backend/analisis.py` y `dimensionar` en `backend/impacto.py`).

**Método.**

- La solicitud indica las personas (1 a 1000), el estándar de consumo (`SPHERE_15`, 15 L por persona al día, o `OMS_20`, 20 L, por defecto), el escenario, la humedad inicial, la tasa de salinización (ALTA por defecto) y la semilla (42 por defecto).
- Para cada uno de los tres flujos de niebla de referencia (6.0 L/m²/h supuesto, 1.83 y 0.49 L/m²/h calibrados, sección 8.6) se simulan 24 h con 8 nodos, con una copia de `ParametrosModelo` en la que solo cambia el flujo.
- `area_colector_m2 = personas * consumo / rendimiento_neuro_l_m2_dia`, con el rendimiento del control basado en reglas, que respeta el tope ecológico. `nodos_requeridos` es el área redondeada hacia arriba, con 1 m² por nodo. Si el rendimiento es 0, ambos valores son nulos.
- `area_literatura_min_m2` y `area_literatura_max_m2` son el área con los rendimientos de 10 y 3 L/m² al día de Klemm et al. (2012). No dependen de la simulación.

**Resultados** para 50 personas en DIA_NORMAL, tasa ALTA y semilla 42. Cada celda muestra el rendimiento del control basado en reglas (L/m² al día), el área (m²) y los nodos.

| Humedad inicial | Estándar | Flujo 6.0 (supuesto) | Flujo 1.83 (calibrado, máximo) | Flujo 0.49 (calibrado, mínimo) | Literatura (m²) |
|---|---|---|---|---|---|
| 85 % | OMS, 20 L | 31.83; 31.42 m²; 32 nodos | 10.02; 99.83 m²; 100 nodos | 3.02; 331.44 m²; 332 nodos | 100.0 a 333.3 |
| 85 % | Sphere, 15 L | 31.83; 23.57 m²; 24 nodos | 10.02; 74.87 m²; 75 nodos | 3.02; 248.58 m²; 249 nodos | 75.0 a 250.0 |
| 45 % | OMS, 20 L | 10.34; 96.75 m²; 97 nodos | 3.50; 285.87 m²; 286 nodos | 1.02; 975.90 m²; 976 nodos | 100.0 a 333.3 |
| 45 % | Sphere, 15 L | 10.34; 72.56 m²; 73 nodos | 3.50; 214.40 m²; 215 nodos | 1.02; 731.92 m²; 732 nodos | 75.0 a 250.0 |

**Interpretación.**

- **Con el flujo supuesto el área queda subestimada.** Con 85 %, 32 nodos bastarían para 50 personas con 20 L al día (nivel de acceso básico): entre 3.2 y 10.6 veces menos área que con los rendimientos de la literatura.
- **Con el flujo calibrado el área coincide con la literatura por construcción.** La calibración de la sección 8.6 se hizo en DIA_NORMAL con 85 %, de modo que los extremos calibrados reproducen 10 y 3 L/m² al día y el área cae en el rango de 100 a 333 m². No es una validación independiente: confirma que el dimensionamiento usa el mismo rendimiento que la calibración.
- **Con 45 % el área crece de forma marcada.** Con el flujo calibrado mínimo harían falta 976 m² para 50 personas, unas 122 redes de 8 nodos. Una red de 8 m² con los flujos calibrados abastecería entre 1.2 y 4.0 personas con 85 %.
- **Alcance.** Hereda las limitaciones de la sección 7.6. Además, los flujos de referencia son los de Cabo de la Vela: para otro sitio, el rendimiento se obtiene con una simulación con su perfil (sección 8.10) y se aplica la misma fórmula.

### 7.8 Impacto en distintos entornos

El dimensionamiento de la sección 7.7 evalúa un solo nivel de salinidad (`DIA_NORMAL`, tasa `ALTA`) y no compara el agua producida con las fuentes actuales del territorio. El análisis de impacto por entorno (`POST /api/v1/analisis/impacto-entornos`, `ejecutar_impacto_entornos` en `backend/analisis.py` y [datos/impacto_entornos.csv](datos/impacto_entornos.csv)) extiende ese cálculo a los 18 entornos que resultan de cruzar los tres flujos de niebla de referencia con los seis niveles de carga salina del barrido (sección 8.7), y compara la producción mensual por nodo con la entrega de agua por carrotanque reportada por el Instituto Colombiano de Bienestar Familiar (ICBF, 2025) en La Guajira (iniciativa que hace parte de las acciones en los municipios priorizados por la Sentencia T-302 de 2017: Riohacha, Maicao, Manaure y Uribia): **1000 L al mes por comunidad** (`ENTREGA_CARROTANQUE_L_COMUNIDAD_MES = 1000.0`), acompañada de hasta 30 L adicionales por ración alimentaria. No crea perfiles de sitios ficticios: usa únicamente los rendimientos y las cifras con fuente documentada en [06_Referencias_y_Trazabilidad_AxiomaH.md](06_Referencias_y_Trazabilidad_AxiomaH.md).

**Método.**

- Para cada flujo de `FLUJOS_REFERENCIA` (`SUPUESTO` 6.0, `CALIBRADO_MAX` 1.83 y `CALIBRADO_MIN` 0.49 L/m²/h) se ejecuta `ejecutar_barrido` con 24 h, 8 nodos, humedad inicial de 85 % y semilla 42 (eficacia del pulso de 0.90).
- Con el rendimiento del control basado en reglas (`rendimiento_neuro_l_m2_dia`) se calculan:
  - `area_colector_m2` y `nodos_requeridos` para las personas y el estándar elegidos (`dimensionar`, sección 7.7);
  - `litros_mes_por_nodo = rendimiento_neuro_l_m2_dia * AREA_COLECTOR_M2 * DIAS_POR_MES`, con `AREA_COLECTOR_M2 = 1.0` m² y `DIAS_POR_MES = 30`, redondeado a 4 decimales;
  - `nodos_equivalentes_entrega = ceil(round(ENTREGA_CARROTANQUE_L_COMUNIDAD_MES / litros_mes_por_nodo, 4))`, el número de nodos de 1 m² cuya producción mensual iguala o supera los 1000 L mensuales por comunidad del ICBF.
- Cada entorno se clasifica con `clasificar_incrustacion` según la posición de su `incrustacion_diaria_ohm` frente al intervalo de transición `[1171.06, 2365.34)` Ohm/día de la sección 8.8 (`INCRUSTACION_TRANSICION_MIN_OHM_DIA` y `INCRUSTACION_TRANSICION_MAX_OHM_DIA`, que son el menor `incrustacion_inferior_ohm` y el mayor `incrustacion_superior_ohm` entre las seis combinaciones con cruce interpolado de la robustez de la respuesta):
  - `BAJO_TRANSICION` (`< 1171.06` Ohm/día): no se espera ventaja en recuperación frente al temporizador;
  - `TRANSICION` (`1171.06` a `< 2365.34` Ohm/día): dentro de la banda de resolución del barrido, donde el signo depende de la eficacia del pulso y de la discretización;
  - `SOBRE_TRANSICION` (`>= 2365.34` Ohm/día): se espera ventaja positiva en recuperación;
  - `SIN_DATOS`: incrustación nula.

**Resultados** con la configuración por defecto (50 personas, estándar `OMS_20` de 20 L por persona al día, humedad inicial de 85 %, semilla 42):

| Origen del flujo | Flujo (L/m²/h) | Escenario y tasa | Carga (Ohm·m²/L) | Rendimiento (L/m²/día) | Incrustación (Ohm/día) | Zona | Ventaja recuperación (pts) | Reducción desgaste (%) | Área 50 p. (m²) | Nodos 50 p. | Litros/mes por nodo (L) | Nodos = 1000 L/mes (ICBF) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `SUPUESTO` | 6.00 | `DIA_NORMAL` / `BAJA` | 20 | 33.33 | 666.6 | `BAJO_TRANSICION` | -6.98 | 99.03 | 30.00 | 31 | 999.90 | 2 |
| `SUPUESTO` | 6.00 | `DIA_NORMAL` / `MEDIA` | 40 | 32.26 | 1290.5 | `TRANSICION` | -3.00 | 97.46 | 31.00 | 31 | 967.86 | 2 |
| `SUPUESTO` | 6.00 | `INCRUSTACION_SALINA_RAPIDA` / `BAJA` | 60 | 31.97 | 1918.1 | `TRANSICION` | +0.78 | 96.10 | 31.28 | 32 | 959.07 | 2 |
| `SUPUESTO` | 6.00 | `DIA_NORMAL` / `ALTA` | 80 | 31.83 | 2546.0 | `SOBRE_TRANSICION` | +4.33 | 95.26 | 31.42 | 32 | 954.76 | 2 |
| `SUPUESTO` | 6.00 | `INCRUSTACION_SALINA_RAPIDA` / `MEDIA` | 120 | 29.37 | 3524.7 | `SOBRE_TRANSICION` | +10.01 | 86.71 | 34.05 | 35 | 881.16 | 2 |
| `SUPUESTO` | 6.00 | `INCRUSTACION_SALINA_RAPIDA` / `ALTA` | 240 | 23.17 | 5561.1 | `SOBRE_TRANSICION` | +22.70 | 73.94 | 43.16 | 44 | 695.13 | 2 |
| `CALIBRADO_MAX` | 1.83 | `DIA_NORMAL` / `BAJA` | 20 | 11.34 | 226.8 | `BAJO_TRANSICION` | sin pulsos | 100.00 | 88.18 | 89 | 340.22 | 3 |
| `CALIBRADO_MAX` | 1.83 | `DIA_NORMAL` / `MEDIA` | 40 | 10.45 | 418.1 | `BAJO_TRANSICION` | sin pulsos | 100.00 | 95.66 | 96 | 313.61 | 4 |
| `CALIBRADO_MAX` | 1.83 | `INCRUSTACION_SALINA_RAPIDA` / `BAJA` | 60 | 10.18 | 610.7 | `BAJO_TRANSICION` | -7.32 | 99.03 | 98.24 | 99 | 305.37 | 4 |
| `CALIBRADO_MAX` | 1.83 | `DIA_NORMAL` / `ALTA` | 80 | 10.02 | 801.4 | `BAJO_TRANSICION` | -6.09 | 99.03 | 99.83 | 100 | 300.51 | 4 |
| `CALIBRADO_MAX` | 1.83 | `INCRUSTACION_SALINA_RAPIDA` / `MEDIA` | 120 | 9.87 | 1184.1 | `TRANSICION` | -3.67 | 97.95 | 101.34 | 102 | 296.03 | 4 |
| `CALIBRADO_MAX` | 1.83 | `INCRUSTACION_SALINA_RAPIDA` / `ALTA` | 240 | 9.72 | 2332.0 | `TRANSICION` | +3.12 | 95.34 | 102.91 | 103 | 291.50 | 4 |
| `CALIBRADO_MIN` | 0.49 | `DIA_NORMAL` / `BAJA` | 20 | 3.27 | 65.4 | `BAJO_TRANSICION` | sin pulsos | 100.00 | 305.74 | 306 | 98.12 | 11 |
| `CALIBRADO_MIN` | 0.49 | `DIA_NORMAL` / `MEDIA` | 40 | 3.18 | 127.1 | `BAJO_TRANSICION` | sin pulsos | 100.00 | 314.75 | 315 | 95.31 | 11 |
| `CALIBRADO_MIN` | 0.49 | `INCRUSTACION_SALINA_RAPIDA` / `BAJA` | 60 | 3.09 | 185.6 | `BAJO_TRANSICION` | sin pulsos | 100.00 | 323.30 | 324 | 92.79 | 11 |
| `CALIBRADO_MIN` | 0.49 | `DIA_NORMAL` / `ALTA` | 80 | 3.02 | 241.4 | `BAJO_TRANSICION` | sin pulsos | 100.00 | 331.44 | 332 | 90.51 | 12 |
| `CALIBRADO_MIN` | 0.49 | `INCRUSTACION_SALINA_RAPIDA` / `MEDIA` | 120 | 2.88 | 346.1 | `BAJO_TRANSICION` | sin pulsos | 100.00 | 346.74 | 347 | 86.52 | 12 |
| `CALIBRADO_MIN` | 0.49 | `INCRUSTACION_SALINA_RAPIDA` / `ALTA` | 240 | 2.72 | 653.8 | `BAJO_TRANSICION` | -7.05 | 99.03 | 367.11 | 368 | 81.72 | 13 |

**Lectura y alcance.**

- **Coherencia de la regla de zonas con la simulación.** De los 18 entornos, 3 caen en `SOBRE_TRANSICION` (`SUPUESTO` con 80, 120 y 240 Ohm·m²/L), 4 en `TRANSICION` y 11 en `BAJO_TRANSICION`. Siete entornos son clasificables (están fuera de `TRANSICION` y tienen pulsos en ambos modos), y en los **7 de 7** el signo simulado de la ventaja coincide con la zona: positiva en los 3 de `SOBRE_TRANSICION` (+4.33 a +22.70 puntos) y negativa en los 4 de `BAJO_TRANSICION` con pulsos (-7.32 a -6.09 puntos). Igual que ocurre en la sección 7.7 con el dimensionamiento calibrado, esta coincidencia de 7 de 7 se cumple en buena parte por construcción: los bordes del intervalo de transición `[1171.06, 2365.34)` Ohm/día se obtuvieron de esos mismos barridos con la semilla 42 en la sección 8.8; una comprobación independiente requiere otra semilla o una eficacia del pulso fuera de la grilla (como el muestreo continuo de la incertidumbre en la sección 8.8). Con `CALIBRADO_MAX` y 240 Ohm·m²/L la incrustación diaria es de 2332.0 Ohm/día (ventaja de +3.12 puntos), justo por debajo del corte superior de 2365.34 Ohm/día que proviene de la combinación con eficacia de 1.00 en la sección 8.8. Con `CALIBRADO_MIN` ningún entorno supera 653.8 Ohm/día y todos quedan en `BAJO_TRANSICION`. En los 18 entornos la reducción del desgaste es de 73.94 % a 100 %.
- **Comparación con la entrega por carrotanque del ICBF.** Para igualar la entrega mensual de referencia de 1000 L por comunidad del ICBF (2025) bastan **2 nodos de 1 m²** con el flujo supuesto (695.1 a 999.9 L/mes por nodo), **3 a 4 nodos** con el flujo calibrado máximo (291.5 a 340.2 L/mes por nodo; 4 nodos con la carga salina más alta) y **11 a 13 nodos** con el flujo calibrado mínimo (81.7 a 98.1 L/mes por nodo; 13 nodos con la carga salina más alta). En cambio, abastecer a 50 personas al nivel de acceso básico de la OMS (20 L por persona al día, es decir, 30 000 L al mes) exige de 31 a 44 nodos con el flujo supuesto, de 89 a 103 con el calibrado máximo y de 306 a 368 con el calibrado mínimo. La diferencia de escala refleja que los 1000 L mensuales por comunidad equivalen a 33.3 L por día para toda la comunidad, mientras que el estándar de la OMS para 50 personas exige 1000 L por día. El entorno con ventaja esperada en recuperación que requiere menos nodos para 50 personas es el de flujo supuesto con carga salina de 80 Ohm·m²/L (32 nodos).
- **Límites del cálculo.** En los 18 entornos el ciclo térmico y de humedad es el de Cabo de la Vela; lo que varía es el flujo máximo de niebla y la carga salina. La cifra del ICBF (2025) es una entrega institucional por comunidad y por mes mediante carrotanque, no una dotación por persona ni el único abastecimiento posible en cada ranchería. Todos los valores de producción y desgaste provienen de la simulación del Ciclo 2 y están sujetos a las limitaciones de las secciones 7.6 y 7.7.

**Preguntas abiertas para el Ciclo 3.**

1. ¿Qué rendimiento de niebla (L/m²/día) y qué carga salina (Ohm·m²/L) tiene un sitio candidato medido en campo, y en cuál de las tres zonas de incrustación diaria (`BAJO_TRANSICION`, `TRANSICION` o `SOBRE_TRANSICION`) cae?
2. En una comunidad concreta, ¿con qué frecuencia efectiva llega el carrotanque, cuántas personas comparten cada entrega de 1000 L y qué fracción de esa demanda podría cubrir de forma complementaria una batería de 4 a 13 nodos de 1 m² durante la temporada de niebla?

## 8. Lectura crítica de las conjeturas

### 8.1 Conflicto entre los indicadores de la Conjetura 1

La sección 5.5 muestra que la Conjetura 1 falla por la recuperación de caudal, mientras que el ahorro de energía cumple en la mayoría de los escenarios. Una pregunta natural es si disparar el pulso antes, con menos carga salina, resolvería el problema. Para responderla se ejecutó un análisis exploratorio con un script temporal, fuera del repositorio, que asigna en memoria `UMBRAL_IMPEDANCIA_OHMS` a 1500, 1400, 1300 y 1200 Ohm y ejecuta `ejecutar_simulacion` con estas condiciones:

- escenarios DIA_NORMAL, INCRUSTACION_SALINA_RAPIDA y TORMENTA_DE_SAL_Y_CALOR_EXTREMO;
- 24 h, inicio a las 18:00, paso de 5 min, 8 nodos, semilla 42, tasa ALTA, humedad inicial 85 %;
- los demás parámetros de `backend/config.py` sin modificar.

| Umbral (Ohm) | Escenario | Recuperación (%) | Ahorro (%) | C1 | Pulsos: control basado en reglas (modo neuro-simbólico) / temporizador | Litros: control basado en reglas (modo neuro-simbólico) / temporizador | Degradación: control basado en reglas (modo neuro-simbólico) / temporizador (%) |
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

La validación de la Conjetura 3 en cuatro escenarios con humedad inicial de 85 % depende de ese flujo optimista. Con humedad inicial de 45 %, el rendimiento del modelo (4.0 a 6.0 L/m²/noche, sección 5.5) queda dentro del rango de la literatura y la conjetura no se valida. La sección 8.6 calibra el flujo contra ese rango y confirma que, con un flujo como el de la literatura, la Conjetura 3 tampoco se valida con 85 %.

### 8.3 Preguntas emergentes para el Ciclo 3

a) ¿Un umbral de disparo adaptativo, que dependa por ejemplo de la reserva o de la tasa de incrustación, puede cumplir a la vez la recuperación y el ahorro de la Conjetura 1? La sección 8.1 muestra que un umbral fijo no lo logra.

b) ¿Qué fracción de la costra remueve un pulso de 90 s a 44 °C? Es la medición experimental prioritaria descrita en 6.3, de la que depende el estado de las Conjeturas 1 y 2.

c) ¿Un estimador sub-simbólico puede distinguir la impedancia causada por sal de la causada por polvo? Esa distinción explica el resultado de TORMENTA_DE_ARENA (sección 6.2), donde el ensuciamiento por polvo eleva la impedancia y no se remueve con el pulso.

d) ¿Cuál es el rendimiento real de niebla en Cabo de la Vela? De él dependen el flujo supuesto y la pertinencia del umbral de la Conjetura 3 (sección 8.2).

e) Reoperacionalizar la Conjetura 2 en dos indicadores declarados antes de ejecutar las simulaciones: la cinética de desprendimiento (< 120 s) y la extensión de la limpieza (Z <= 1100 Ohm). Hoy ambos aspectos se miden en un solo indicador, el tiempo hasta 1100 Ohm, y el criterio se endureció después de observar los primeros resultados (sección 6.4).

f) ¿La ventaja en recuperación del control basado en reglas depende de la incrustación diaria y no de la carga salina por litro? Es la hipótesis H1-Ciclo 3 de la sección 8.9, que surge de la robustez de la sección 8.8.

### 8.4 Control de confusión: tope ecológico frente a lógica de control

El modo neuro-simbólico capta menos agua que el temporizador fijo (sección 5.5), pero los dos modos difieren en dos aspectos a la vez: la lógica de control (reglas frente a programación fija) y la fracción de extracción (0.33 frente a 0.45). Para separar ambos efectos, cada simulación ejecuta además un temporizador con tope ecológico (sección 3.3): la misma programación del temporizador fijo con la fracción de 0.33.

Con L_neuro, L_temp y L_temp33 como el agua captada por el neuro-simbólico, el temporizador fijo y el temporizador con tope:

- brecha total = `L_temp - L_neuro`;
- parte debida al tope ecológico = `L_temp - L_temp33`;
- parte debida a la lógica de control = `L_temp33 - L_neuro`.

Condiciones: 24 h, inicio a las 18:00, paso de 5 min, 8 nodos, semilla 42, tasa ALTA y parámetros de `backend/config.py` sin modificar. Las columnas de neuro-simbólico y temporizador 0.45 coinciden con las secciones 5.2 a 5.4.

| Escenario | Humedad inicial | Control basado en reglas (modo neuro-simbólico) (L) | Temporizador 0.45 (L) | Temporizador 0.33 (L) | Brecha total (L) | Por tope (L) | Por lógica de control (L) | Brecha debida al tope (%) | Violaciones del temporizador 0.33 |
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

### 8.6 Calibración del flujo de niebla contra la literatura

La sección 8.2 muestra que el flujo máximo de niebla supuesto, 6.0 L/m²/h, es optimista: con humedad inicial de 85 % el modelo base obtiene 31.8 L/m²/día en DIA_NORMAL (sección 7.6), frente a los 3 a 10 L/m²/día que Klemm et al. (2012) reportan para proyectos operativos. Para anclar el rango del flujo a la literatura se hizo una calibración inversa.

**Método.** `calibrar_flujo_niebla` (`backend/analisis.py`) busca por bisección, en el intervalo de 0.1 a 6.0 L/m²/h, el flujo con el que el modo neuro-simbólico alcanza un rendimiento objetivo en L/m²/día. Cada evaluación es una corrida de 24 h en DIA_NORMAL con humedad inicial de 85 %, tasa ALTA, 8 nodos y semilla 42, con una copia de `ParametrosModelo` en la que solo cambia el flujo. En los flujos evaluados el rendimiento crece con el flujo, de 0.67 L/m²/día con 0.1 L/m²/h a 31.8 con 6.0, lo que permite la bisección. La búsqueda se detiene cuando el intervalo mide menos de 0.01 L/m²/h.

**Resultado.**

| Rendimiento objetivo (L/m²/día) | Flujo calibrado (L/m²/h) | Constante de `backend/config.py` |
|---|---|---|
| 3.0 (mínimo de Klemm et al.) | 0.4889 | `FLUJO_NIEBLA_CALIBRADO_MIN_L_M2_H = 0.49` |
| 10.0 (máximo de Klemm et al.) | 1.8256 | `FLUJO_NIEBLA_CALIBRADO_MAX_L_M2_H = 1.83` |

El rango calibrado, de 0.49 a 1.83 L/m²/h, está entre 3.3 y 12 veces por debajo del valor supuesto de 6.0. El valor por defecto del modelo no cambia (decisión D5): las secciones 5 a 7 se siguen calculando con 6.0, y el rango calibrado solo se usa en el análisis de incertidumbre de la sección 8.7. Una prueba automatizada verifica que las dos constantes coinciden con la calibración dentro de 0.01.

**Efecto sobre la Conjetura 3.** Con el flujo calibrado, la Conjetura 3 no se valida en DIA_NORMAL con humedad inicial de 85 %, el caso en que sí se valida con el flujo de 6.0:

| Flujo (L/m²/h) | Rendimiento (L/m²/día) | Rendimiento nocturno, control basado en reglas (modo neuro-simbólico) (L/m²/noche) | Rendimiento nocturno temporizador (L/m²/noche) | C3 | Causa |
|---|---|---|---|---|---|
| 6.0 (supuesto) | 31.83 | 16.97 | 21.96 | Validada | |
| 1.83 (calibrado, máximo) | 10.02 | 5.47 | 8.09 | No validada | `LIMITE_DEL_RECURSO_ATMOSFERICO` |
| 0.49 (calibrado, mínimo) | 3.02 | 1.67 | 2.35 | No validada | `LIMITE_DEL_RECURSO_ATMOSFERICO` |

Con rendimientos como los de la literatura, ni el temporizador alcanza el umbral de 12 L/m²/noche. Esto confirma la lectura de la sección 8.2: la validación de la Conjetura 3 con 85 % depende del flujo optimista, y el umbral de rendimiento de la Matriz está por encima de lo que reportan los proyectos operativos. El indicador de violaciones ecológicas no cambia: el modo neuro-simbólico sigue sin violaciones.

La calibración usa un solo escenario, una semilla y un rango de rendimientos medido en colectores de malla. Calibrar el flujo con mediciones en Cabo de la Vela sigue pendiente (sección 8.3). Desde la versión 0.4.0 la calibración tiene endpoint y puede usar el clima de otro sitio (sección 8.12); sin perfil de sitio da los mismos flujos de esta tabla.

### 8.7 Propagación de la incertidumbre

Las secciones 5.6 y 5.7 varían un parámetro a la vez. Para ver el efecto conjunto de los dos parámetros supuestos que más influyen en las conjeturas, `POST /api/v1/analisis/incertidumbre` (`ejecutar_incertidumbre` en `backend/analisis.py`) los muestrea a la vez.

**Método.**

- Cada muestra toma una eficacia máxima del pulso y un flujo máximo de niebla con distribución uniforme e independiente. Los rangos por defecto son 0.80 a 1.00 para la eficacia (`EFICACIA_PULSO_RANGO_MIN` y `EFICACIA_PULSO_RANGO_MAX`, supuesto alrededor de 0.90) y 0.49 a 1.83 L/m²/h para el flujo (sección 8.6).
- El muestreo usa un generador con semilla (`semilla_muestreo`, 7 por defecto), creado con la misma función que genera el entorno de la simulación. La misma configuración produce siempre las mismas muestras.
- Cada muestra se simula una vez, con el mismo entorno (semilla 42), y se verifican las conjeturas con la regla de validación sin cambios.
- La probabilidad de una conjetura es la proporción de muestras que la validan. Para la recuperación tras pulso, el rendimiento en L/m²/día y la reducción de la degradación se reportan los percentiles 5, 50 y 95 de las muestras con datos.
- Cada muestra informa también la recuperación del temporizador y la ventaja en recuperación (`ventaja_recuperacion_pts`, recuperación del control basado en reglas menos la del temporizador). El resultado agrega sus percentiles (`ventaja_recuperacion`) y la proporción de las muestras con ambas recuperaciones en que la ventaja es positiva (`probabilidad_ventaja_recuperacion`). Sus valores se discuten en la sección 8.8.

**Resultados.** 24 h, humedad inicial de 85 %, tasa ALTA, 8 nodos, semilla 42, 20 muestras y rangos por defecto. Los percentiles se indican como p5 / p50 / p95.

| Escenario | P(C1) | P(C2) | P(C3) | Recuperación (%) | Muestras con pulsos | Rendimiento (L/m²/día) | Reducción de la degradación (%) |
|---|---|---|---|---|---|---|---|
| DIA_NORMAL | 0.05 | 0.00 | 0.00 | 85.98 / 87.64 / 89.94 | 8 de 20 | 3.47 / 5.56 / 8.88 | 99.03 / 100.00 / 100.00 |
| INCRUSTACION_SALINA_RAPIDA | 0.15 | 0.10 | 0.00 | 85.99 / 88.00 / 91.31 | 20 de 20 | 3.16 / 5.31 / 8.54 | 95.74 / 97.71 / 99.03 |
| SEQUIA | 0.00 | 0.00 | 0.00 | Sin datos | 0 de 20 | 2.12 / 3.47 / 5.31 | 100.00 / 100.00 / 100.00 |
| TORMENTA_DE_ARENA | 0.00 | 0.00 | 0.00 | 76.86 / 78.93 / 84.32 | 20 de 20 | 3.18 / 5.17 / 8.08 | 97.24 / 98.62 / 98.62 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 0.10 | 0.05 | 0.00 | 85.99 / 88.00 / 90.49 | 14 de 20 | 3.30 / 5.48 / 8.71 | 98.62 / 99.31 / 100.00 |

**Interpretación.**

- **Conjetura 3.** No se valida en ninguna muestra de ningún escenario. Con el flujo calibrado, el rendimiento nocturno queda por debajo de 12 L/m²/noche (sección 8.6). El resultado depende sobre todo del umbral de la Matriz frente a la literatura, no de la eficacia del pulso.
- **Conjeturas 1 y 2.** Su probabilidad es baja, entre 0.00 y 0.15 para C1 y entre 0.00 y 0.10 para C2, por dos causas distintas:
  - la eficacia necesaria con el flujo de 6.0 (alrededor de 0.94 para C1 y 0.97 para C2, sección 6.2) solo ocupa el 30 % y el 15 % del rango muestreado. Con el flujo calibrado el umbral puede variar: en DIA_NORMAL la única muestra que valida C1 tiene una eficacia de 0.936;
  - con el flujo calibrado se capta menos agua, se acumula menos sal y en muchas corridas el motor no llega a aplicar pulsos. En DIA_NORMAL, 12 de 20 muestras no aplican pulsos, y en SEQUIA ninguna. Sin pulsos no hay recuperación ni tiempo de regeneración que medir, y la causa de no validación es `SIN_DATOS`. En esas muestras las conjeturas no se refutan: no se ponen a prueba.

  En TORMENTA_DE_ARENA la recuperación no supera 84.32 % en el percentil 95, porque el pulso no remueve el polvo (sección 8.5), y ninguna muestra valida C1.
- **Desgaste.** Entre los percentiles 5 y 95, la reducción de la degradación frente al temporizador se mantiene entre 95.7 % y 100 % en los cinco escenarios. Vale 100 % cuando el neuro-simbólico no aplica pulsos y su membrana no se degrada. Es el resultado más robusto del análisis, y es coherente con el barrido de la sección 7.
- **Alcance.** Las probabilidades son proporciones del espacio de parámetros supuesto, no probabilidades de lo que ocurrirá en campo: cambian si cambian los rangos o la distribución. Con 20 muestras, la resolución es de 0.05, de modo que valores como 0.05 o 0.10 corresponden a una o dos muestras. La incertidumbre del clima (semillas) y la de los demás parámetros supuestos no está incluida.

### 8.8 Robustez de la respuesta

El barrido de la sección 7 usa el flujo de niebla supuesto (6.0 L/m²/h) y la eficacia del pulso supuesta (0.90). Para saber si la respuesta a la pregunta de investigación depende de esos dos valores, `POST /api/v1/analisis/robustez-respuesta` (`ejecutar_robustez` en `backend/analisis.py`) repite el barrido con cada combinación de tres flujos y tres eficacias.

**Método.**

- Flujos: 6.0 L/m²/h (supuesto) y 1.83 y 0.49 L/m²/h (extremos de la calibración contra la literatura, sección 8.6). Eficacias: 0.80, 0.90 y 1.00 (`EFICACIA_PULSO_RANGO_MIN`, `EFICACIA_MAXIMA_PULSO` y `EFICACIA_PULSO_RANGO_MAX`).
- Cada combinación es un barrido completo, con las condiciones de la sección 7.2 (24 h, 8 nodos, humedad inicial de 85 %, semilla 42) y una copia de `ParametrosModelo`. `backend/config.py` no cambia.
- Además de los campos de la sección 7, cada punto informa el rendimiento del control basado en reglas, la **incrustación diaria** (`incrustacion_diaria_ohm_media`, carga salina por ese rendimiento: el aumento de impedancia por sal que la membrana recibiría en un día), la ventaja en recuperación y los pulsos del control basado en reglas.
- **Cruce.** Cada barrido informa dónde la ventaja en recuperación pasa de <= 0 a > 0 (`cruce`). Se ordenan los puntos con ventaja por incrustación diaria y se interpola linealmente la incrustación diaria y la carga salina en que la ventaja vale 0 (estado `INTERPOLADO`). Si la ventaja es positiva en todos los puntos, el estado es `SIN_CRUCE_NEURO_SUPERIOR`; si no lo es en ninguno, `SIN_CRUCE_NEURO_INFERIOR`; con menos de dos puntos con ventaja, `SIN_DATOS`. Si la ventaja solo pasa de > 0 a <= 0, el estado es `CRUCE_DESCENDENTE`, que contradiría la dirección de la hipótesis; no se presentó en ninguna combinación. Desde la versión 0.4.0, el cruce informa además los dos niveles de incrustación diaria entre los que se interpola (`incrustacion_inferior_ohm` e `incrustacion_superior_ohm`) y su distancia (`separacion_ohm`).

**Resultados.** Los datos completos, con una fila por combinación y punto, están en `docs/datos/robustez_respuesta.csv`.

| Flujo (L/m²/h) | Eficacia | Cruce | Incrustación diaria del cruce (Ohm/día) | Carga salina del cruce (Ohm por L/m²) | Incrustación diaria máxima del barrido (Ohm/día) | Reducción del desgaste |
|---|---|---|---|---|---|---|
| 6.0 | 0.80 | `INTERPOLADO` | 1819.82 | 57.58 | 5367.9 | 73.3 % a 99.0 % |
| 6.0 | 0.90 | `INTERPOLADO` | 1789.12 | 55.89 | 5561.1 | 73.9 % a 99.0 % |
| 6.0 | 1.00 | `INTERPOLADO` | 1632.87 | 50.25 | 5748.2 | 74.4 % a 99.0 % |
| 1.83 | 0.80 | `INTERPOLADO` | 1839.21 | 190.94 | 2301.4 | 95.3 % a 100 % |
| 1.83 | 0.90 | `INTERPOLADO` | 1804.68 | 184.87 | 2332.0 | 95.3 % a 100 % |
| 1.83 | 1.00 | `INTERPOLADO` | 1639.61 | 165.22 | 2365.3 | 95.7 % a 100 % |
| 0.49 | 0.80 | `SIN_DATOS` | | | 649.1 | 99.0 % a 100 % |
| 0.49 | 0.90 | `SIN_DATOS` | | | 653.8 | 99.0 % a 100 % |
| 0.49 | 1.00 | `SIN_DATOS` | | | 658.7 | 99.0 % a 100 % |

La fila de 6.0 y 0.90 es el barrido de la sección 7.3. La reducción del desgaste vale 100 % en los puntos en que el control basado en reglas no aplica pulsos y su membrana no se degrada.

**Lectura.**

- **Desgaste.** El control basado en reglas degrada menos la membrana en los 54 puntos, con una reducción de 73.3 % a 100 %. Es la parte de la respuesta que no depende de los parámetros supuestos en los rangos evaluados.
- **Recuperación con el flujo calibrado máximo.** Con 1.83 L/m²/h el control basado en reglas supera al temporizador solo con la carga más alta, 240 Ohm por L/m², por 3.1 a 3.5 puntos según la eficacia. Con 20 y 40 Ohm por L/m² no llega a aplicar pulsos, y entre 60 y 120 el temporizador recupera más.
- **Recuperación con el flujo calibrado mínimo.** Con 0.49 L/m²/h solo la carga de 240 Ohm por L/m² produce pulsos, y en ese punto el temporizador recupera más (ventaja de -8.9, -7.1 y -4.7 puntos con eficacias de 0.80, 0.90 y 1.00). Con un solo punto con ventaja no hay cruce que interpolar (`SIN_DATOS`), pero el control basado en reglas no supera al temporizador en ningún nivel.
- **El cruce depende de la incrustación diaria, no de la carga por litro.** En las seis combinaciones con cruce, la carga salina del cruce va de 50.3 a 190.9 Ohm por L/m², un factor de 3.8, mientras que la incrustación diaria del cruce va de 1632.9 a 1839.2 Ohm/día, una variación de 13 %. Con una eficacia fija, cambiar el flujo de 6.0 a 1.83 L/m²/h mueve el cruce como mucho 19.4 Ohm/día. La eficacia lo mueve más: alrededor de 1633 a 1640 Ohm/día con 1.00 y de 1820 a 1839 con 0.80. Con 0.49 L/m²/h la incrustación diaria no pasa de 659 Ohm/día en ningún punto, por debajo de todos los cruces, lo que explica que el control basado en reglas no supere al temporizador. Es coherente con el mecanismo de la sección 7.4: la recuperación del temporizador depende de la sal acumulada entre dos pulsos programados, que crece con la incrustación por unidad de tiempo, mientras que el control basado en reglas pulsa siempre con una carga parecida.
- **Otras semillas.** Repetida con las semillas 1, 2 y 3 (media de las tres), la robustez da los mismos estados de cruce y una incrustación diaria del cruce de 1682.1 a 1866.6 Ohm/día; la reducción del desgaste va de 73.6 % a 100 %. El barrido base con las semillas 1 a 5 de `docs/datos/` cruza en 1818.4 Ohm/día.

**Resolución del cruce.** El barrido tiene seis niveles de carga salina, y el cruce se interpola linealmente entre los dos niveles vecinos en que cambia el signo de la ventaja. Esos niveles están lejos entre sí:

| Flujo (L/m²/h) | Eficacia | Nivel inferior (Ohm/día) | Nivel superior (Ohm/día) | Separación (Ohm/día) |
|---|---|---|---|---|
| 6.0 | 0.80 | 1277.90 | 1894.53 | 616.63 |
| 6.0 | 0.90 | 1290.48 | 1918.13 | 627.65 |
| 6.0 | 1.00 | 1305.24 | 1944.40 | 639.16 |
| 1.83 | 0.80 | 1171.06 | 2301.36 | 1130.30 |
| 1.83 | 0.90 | 1184.11 | 2332.03 | 1147.92 |
| 1.83 | 1.00 | 1200.71 | 2365.34 | 1164.64 |

Con el flujo de 6.0 L/m²/h los niveles vecinos son las cargas de 40 y 60 Ohm por L/m², y con 1.83, las de 120 y 240. La separación, de 616.6 a 1164.6 Ohm/día, es de 3.0 a 5.6 veces el rango del cruce entre combinaciones (206.3 Ohm/día, de 1632.9 a 1839.2). Dos consecuencias:

- **El rango del cruce es una estimación por interpolación, no un umbral resuelto.** La interpolación supone que la ventaja cambia en línea recta entre los dos niveles. El barrido no puede distinguir los cruces de las seis combinaciones: lo que sí muestra es que el cruce real de cada una está en algún punto de su intervalo, es decir, entre 1171.1 y 2365.3 Ohm/día en el conjunto. Los seis intervalos comparten el tramo de 1305.2 a 1894.5 Ohm/día.
- **La comparación entre flujos depende de la interpolación.** Con el flujo calibrado los niveles están casi el doble de separados que con el supuesto, de modo que la diferencia de 19.4 Ohm/día entre flujos con la misma eficacia es mucho menor que la resolución del barrido. La conclusión de que el cruce depende de la incrustación diaria y no de la carga por litro sí se sostiene: en carga por litro los intervalos de los dos flujos no se solapan (de 40 a 60 Ohm por L/m² con el supuesto y de 120 a 240 con el calibrado), mientras que en incrustación diaria los seis se solapan. El valor exacto del umbral, en cambio, no está resuelto.

Estrechar el rango exige agregar niveles de carga salina entre 40 y 60 Ohm por L/m² con el flujo supuesto y entre 120 y 240 con el calibrado, o medirlo directamente, como propone H1-Ciclo 3 (sección 8.9).

**Contraste con la propagación de la incertidumbre.** La sección 8.7 muestrea la eficacia y el flujo calibrado de forma continua. La ventaja en recuperación de esas muestras (20 muestras, humedad inicial de 85 %, tasa ALTA, semilla 42) es:

| Escenario | Muestras con ambas recuperaciones | Ventaja en recuperación, p5 / p50 / p95 (puntos) | P(ventaja > 0) |
|---|---|---|---|
| DIA_NORMAL | 8 de 20 | -10.03 / -7.94 / -6.21 | 0.00 |
| INCRUSTACION_SALINA_RAPIDA | 20 de 20 | -6.98 / -2.95 / 1.51 | 0.15 |
| SEQUIA | 0 de 20 | Sin datos | Sin datos |
| TORMENTA_DE_ARENA | 20 de 20 | -18.86 / -14.67 / -9.88 | 0.00 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 14 de 20 | -9.60 / -6.54 / -4.37 | 0.00 |

Con los flujos calibrados, solo hay 3 de 62 muestras con ventaja en recuperación para el control basado en reglas, todas en INCRUSTACION_SALINA_RAPIDA (sobre las 62 muestras que registraron ambas recuperaciones). Multiplicando la carga salina de cada escenario (240, 120 y 80 Ohm por L/m²) por el rendimiento de cada muestra, en DIA_NORMAL, INCRUSTACION_SALINA_RAPIDA y TORMENTA_DE_SAL_Y_CALOR_EXTREMO las 42 muestras con ambas recuperaciones se separan por la incrustación diaria: la ventaja es negativa en todas las que tienen 1628.9 Ohm/día o menos y positiva en las tres que tienen 2014.9 Ohm/día o más. Es una comprobación independiente de la grilla, porque usa valores de eficacia y flujo distintos, y es coherente con el rango de cruce. En TORMENTA_DE_ARENA la ventaja es negativa en todas las muestras, porque el pulso no remueve el polvo (sección 8.5).

**Respuesta robusta a la pregunta.** En el modelo, y en los rangos evaluados de flujo de niebla y eficacia del pulso:

1. el control basado en reglas reduce el desgaste de la membrana frente al temporizador en todos los niveles de salinidad, con una reducción de 73.3 % a 100 %, y la reducción se mantiene con la mitad y el doble de la fatiga por pulso y de la degradación térmica, de 61.5 % a 100 % (sección 8.11);
2. su ventaja en recuperación no depende de la carga salina por litro, sino de la incrustación diaria, y aparece solo por encima de unos 1633 a 1867 Ohm/día, un rango obtenido por interpolación entre niveles separados de 617 a 1165 Ohm/día (cruce entre 1171 y 2365 Ohm por día, resolución del cruce);
3. con rendimientos como los de la literatura (flujo calibrado), esa incrustación diaria solo se alcanza con la carga salina más alta, por lo que en la mayoría de las condiciones el temporizador recupera igual o más. Esa recuperación mayor no indica una membrana mejor mantenida (sección 7.5): el temporizador pulsa con la membrana casi limpia, a costa de más desgaste.

### 8.9 Hipótesis derivada H1-Ciclo 3

La sección 8.8 sugiere una hipótesis más precisa que la hipótesis de trabajo ([01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.5), que se propone para ponerla a prueba en el Ciclo 3.

**Enunciado.** Con el control basado en reglas (pulso cuando la impedancia supera 1500 Ohm) y un temporizador con pulsos cada 2 h, la recuperación tras pulso del control basado en reglas supera a la del temporizador cuando la incrustación diaria de la membrana, el aumento de impedancia por sal en un día de operación, supera un umbral situado en el modelo entre 1633 y 1867 Ohm/día, y no lo supera por debajo de ese umbral, cualquiera sea la combinación de flujo de niebla y carga salina por litro que produzca esa incrustación.

El rango sale de las 6 combinaciones con cruce de la semilla 42 (1632.9 a 1839.2 Ohm/día) y de las mismas combinaciones con las semillas 1 a 3 (1682.1 a 1866.6 Ohm/día). Dentro del rango, el umbral depende sobre todo de la eficacia del pulso. Como el rango es más estrecho que la separación de los niveles interpolados (sección 8.8, resolución del cruce), es una estimación del modelo que la medición debe precisar, no un valor resuelto por el barrido.

**Cómo refutarla.**

- **Medición.** Dos grupos de membranas, uno con cada modo de control, expuestos a niebla salina con al menos dos combinaciones que den la misma incrustación diaria con cargas por litro distintas (más agua con menos sal por litro, y menos agua con más sal por litro), y a incrustaciones diarias por debajo y por encima del rango. La incrustación diaria se mide como la pendiente de la impedancia entre pulsos, con el mismo sensor de impedancia que usa el nodo, y la recuperación como `Z_nominal / Z_tras_pulso`, el cálculo del indicador de la Conjetura 1.
- **Resultado que la contradiría.** (a) Que, con la misma incrustación diaria, el signo de la ventaja cambie entre las combinaciones de distinta carga por litro, lo que indicaría que el cruce depende de la carga por litro. (b) Que el control basado en reglas supere al temporizador con incrustaciones claramente menores que 1633 Ohm/día, o no lo supere con incrustaciones claramente mayores que 1867 Ohm/día, una vez descontada la incertidumbre de la medición. (c) Que la ventaja pase de positiva a negativa al aumentar la incrustación diaria, lo que la API informaría como `CRUCE_DESCENDENTE`.

**Relación con el experimento de la sección 6.3.** El experimento de 6.3 mide qué fracción de la costra remueve un pulso de 90 s a 44 °C, es decir, la eficacia del pulso. Ese valor es el que más mueve el umbral: con la semilla 42, el cruce está cerca de 1633 a 1640 Ohm/día con una eficacia de 1.00 y de 1820 a 1839 Ohm/día con 0.80. Por eso conviene hacer primero el experimento de 6.3, repetir la robustez con la eficacia medida para estrechar el rango y, después, contrastar H1-Ciclo 3 con ese rango más estrecho. Ambas mediciones comparten la muestra de membrana y el sensor de impedancia.

### 8.10 Transferencia a otro sitio

El modelo se calibró para Cabo de la Vela, pero el clima de referencia ya no está fijo en el código: `POST /api/v1/simulacion/ejecutar` acepta un perfil de sitio y una eficacia del pulso, y la respuesta informa en `parametros_usados` los valores con que se ejecutó la corrida. `GET /api/v1/sitios` devuelve los tres perfiles disponibles, todos de Cabo de la Vela: `CABO_DE_LA_VELA` (flujo supuesto de 6.0 L/m²/h), `CABO_DE_LA_VELA_CALIBRADO_MAX` (1.83) y `CABO_DE_LA_VELA_CALIBRADO_MIN` (0.49). No se incluyen otros sitios porque el proyecto no tiene datos climáticos con fuente para ellos.

**Procedimiento.**

1. **Medir cinco parámetros en el sitio.**
   - el rendimiento de niebla en L/m² al día, con un colector de niebla, para calibrar el flujo máximo (paso 2);
   - la temperatura ambiente media, en °C;
   - la amplitud del ciclo térmico diurno, en °C (la mitad de la diferencia entre la máxima y la mínima diarias);
   - la amplitud del ciclo diurno de humedad relativa, en puntos de HR;
   - la humedad relativa a las 18:00, que es `humedad_ambiente_inicial_pct`.
2. **Calibrar el flujo de niebla.** `POST /api/v1/analisis/calibracion` busca por bisección el flujo con el que el control basado en reglas alcanza el rendimiento medido, con la temperatura y las amplitudes del perfil del sitio, y devuelve el perfil con el flujo calibrado (sección 8.12). En la vista 5 del dashboard lo hace el botón "Calibrar flujo". No modifica `backend/config.py`.
3. **Pasar el perfil en la simulación.** El campo `sitio` lleva el nombre (mayúsculas, dígitos y guion bajo, hasta 40 caracteres), el flujo calibrado, la temperatura media, la amplitud térmica y la amplitud de humedad. Los valores fuera de rango (flujo en (0, 20] L/m²/h, temperatura media de 0 a 45 °C, amplitud térmica de 0 a 15 °C y amplitud de humedad de 0 a 30 puntos) devuelven `422`. Por ejemplo:

   ```json
   {
     "duracion_horas": 24,
     "escenario": "DIA_NORMAL",
     "humedad_ambiente_inicial_pct": 80.0,
     "tasa_salinizacion": "ALTA",
     "sitio": {
       "nombre": "SITIO_EJEMPLO",
       "flujo_niebla_maximo_l_m2_h": 1.2,
       "temperatura_media_c": 24.0,
       "amplitud_temperatura_c": 6.0,
       "amplitud_humedad_pct": 15.0
     },
     "eficacia_maxima_pulso": 0.9
   }
   ```

   Los valores del ejemplo son ilustrativos, no de un sitio real.
4. **Leer el resultado.** `parametros_usados` confirma el perfil aplicado. `impacto_comunitario.modo_neuro_simbolico.rendimiento_l_m2_dia` da el rendimiento del sitio, con el que se dimensiona el captador con la fórmula de la sección 7.7. Multiplicando la carga salina por ese rendimiento se obtiene la incrustación diaria, que, comparada con el umbral de H1-Ciclo 3, anticipa si cabe esperar una ventaja en recuperación del control basado en reglas.

**Preguntas que abre.**

a) Hasta la versión 0.3.0, `calibrar_flujo_niebla` simulaba con el ciclo de temperatura y humedad de Cabo de la Vela. Como la amplitud de humedad cambia la disponibilidad de niebla, la calibración para otro sitio era aproximada. ¿Cuánto cambia el flujo calibrado si la calibración usa el perfil del sitio? La sección 8.12 lo responde: la temperatura y la amplitud térmica no lo cambian en los perfiles evaluados, y la amplitud de humedad lo mueve de -4.7 % a +19.6 %.

b) ¿Cómo se mide la carga salina por litro en un sitio nuevo? El modelo la expresa en Ohm por L/m², y para transferirla hace falta relacionar la sal depositada en la membrana con el aumento de impedancia.

c) El perfil conserva las horas de máximo de Cabo de la Vela (04:00 para la humedad y 14:00 para la temperatura) y no representa la estacionalidad de la niebla. ¿Son adecuadas para otros climas costeros?

d) El dimensionamiento (sección 7.7), la robustez (sección 8.8) y el barrido aceptan el flujo de niebla, pero no la temperatura ni las amplitudes del sitio. ¿Cambia la respuesta de la sección 8.8 con otro ciclo térmico, que modifica el calentamiento de la matriz y la energía de cada pulso?

e) La consulta previa y el protocolo de co-creación ([01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.7) se aplican a cualquier sitio con comunidades, no solo a Cabo de la Vela.

### 8.11 Robustez del desgaste frente a la fatiga y la degradación térmica

La sección 8.8 muestra que la reducción del desgaste no depende del flujo de niebla ni de la eficacia del pulso en los rangos evaluados. Pero la degradación de ambos modos la determinan otros dos parámetros supuestos, sin fuente ([06_Referencias_y_Trazabilidad_AxiomaH.md](06_Referencias_y_Trazabilidad_AxiomaH.md), sección 3): la fatiga por pulso (`FATIGA_POR_PULSO_PCT`, 0.02 % de integridad por ciclo térmico) y la degradación térmica (`DEGRADACION_TERMICA_PCT_POR_C_MIN`, 0.05 % por cada °C sobre 45 y minuto de exposición). Hasta la versión 0.3.0 la reducción del desgaste se declaraba robusta sin variarlos. `POST /api/v1/analisis/robustez-desgaste` (`ejecutar_robustez_desgaste` en `backend/analisis.py`) repite el barrido variando ambos.

**Método.**

- Flujos: 6.0 L/m²/h (supuesto) y 1.83 L/m²/h (extremo superior de la calibración, sección 8.6). Se omite el extremo inferior, 0.49 L/m²/h, con el que el control basado en reglas casi no aplica pulsos y la reducción ya es de 99.0 % a 100 % (sección 8.8).
- Fatiga por pulso: 0.01, 0.02 y 0.04 % (`FATIGAS_ROBUSTEZ_PCT`). Degradación térmica: 0.025, 0.05 y 0.10 % por °C y minuto (`DEGRADACIONES_TERMICAS_ROBUSTEZ`). En ambos casos, la mitad, el valor supuesto y el doble; el rango también es un supuesto.
- Eficacia del pulso de 0.90. Cada una de las 18 combinaciones es un barrido completo de seis puntos, con las condiciones de la sección 7.2 (24 h, 8 nodos, humedad inicial de 85 %, semilla 42): 108 puntos.
- La fatiga y la degradación térmica son campos de `ParametrosModelo` y el simulador las lee de allí, como la eficacia y el flujo. Cada combinación usa una copia con `dataclasses.replace`; `backend/config.py` no cambia. Con los valores por defecto, la respuesta de `ejecutar_simulacion` para los cinco escenarios con humedad inicial de 45 % y 85 % es idéntica a la de la versión 0.3.0, y la combinación de 6.0, 0.02 y 0.05 reproduce el barrido de la sección 7.3.
- Un punto cuenta como de menor desgaste si su reducción es positiva. Un punto sin reducción calculable (el temporizador no se degrada) no cuenta.

**Resultados.** Los datos están en `docs/datos/robustez_desgaste.csv`.

| Flujo (L/m²/h) | Fatiga por pulso (%) | Degradación térmica (% por °C y min) | Reducción del desgaste | Puntos con menor desgaste |
|---|---|---|---|---|
| 6.0 | 0.01 | 0.025 | 69.2 % a 99.0 % | 6 de 6 |
| 6.0 | 0.01 | 0.05 | 76.3 % a 99.5 % | 6 de 6 |
| 6.0 | 0.01 | 0.10 | 83.7 % a 99.7 % | 6 de 6 |
| 6.0 | 0.02 | 0.025 | 66.4 % a 98.3 % | 6 de 6 |
| 6.0 | 0.02 | 0.05 | 73.9 % a 99.0 % | 6 de 6 |
| 6.0 | 0.02 | 0.10 | 82.0 % a 99.5 % | 6 de 6 |
| 6.0 | 0.04 | 0.025 | 61.5 % a 97.1 % | 6 de 6 |
| 6.0 | 0.04 | 0.05 | 69.7 % a 98.3 % | 6 de 6 |
| 6.0 | 0.04 | 0.10 | 78.7 % a 99.0 % | 6 de 6 |
| 1.83 | 0.01 | 0.025 | 95.8 % a 100 % | 6 de 6 |
| 1.83 | 0.01 | 0.05 | 97.6 % a 100 % | 6 de 6 |
| 1.83 | 0.01 | 0.10 | 98.7 % a 100 % | 6 de 6 |
| 1.83 | 0.02 | 0.025 | 92.2 % a 100 % | 6 de 6 |
| 1.83 | 0.02 | 0.05 | 95.3 % a 100 % | 6 de 6 |
| 1.83 | 0.02 | 0.10 | 97.4 % a 100 % | 6 de 6 |
| 1.83 | 0.04 | 0.025 | 86.6 % a 100 % | 6 de 6 |
| 1.83 | 0.04 | 0.05 | 91.5 % a 100 % | 6 de 6 |
| 1.83 | 0.04 | 0.10 | 95.1 % a 100 % | 6 de 6 |

**Lectura.**

- **Dirección.** En las 18 combinaciones el control basado en reglas se degrada menos que el temporizador en los seis puntos: 108 de 108, con una reducción de 61.5 % a 100 %. En los rangos evaluados, ninguna combinación de fatiga y degradación térmica invierte la respuesta sobre el desgaste.
- **Magnitud.** Con el flujo supuesto, la reducción mínima va de 61.5 % a 83.7 % según los dos parámetros. Más fatiga reduce la ventaja (con 0.05 % por °C y min, 76.3 %, 73.9 % y 69.7 % con fatigas de 0.01, 0.02 y 0.04 %), porque el control basado en reglas también pulsa, y más en los niveles de salinidad altos. Más degradación térmica la aumenta (con fatiga de 0.02 %, 66.4 %, 73.9 % y 82.0 % con 0.025, 0.05 y 0.10), porque solo el temporizador lleva la matriz por encima de 45 °C (sección 7.4). La combinación menos favorable, fatiga doble con degradación térmica a la mitad, da el mínimo de 61.5 %.
- **Flujo calibrado.** Con 1.83 L/m²/h la reducción es de 86.6 % a 100 %: el control basado en reglas aplica pocos pulsos, y en los niveles sin pulsos su membrana no se degrada.
- **Alcance.** El análisis usa una semilla y un rango de mitad a doble que también es supuesto. No mide cuál es la fatiga real de un pulso: esa medición sigue pendiente (ciclos repetidos de pulso a 44 °C sobre una muestra de membrana). Lo que muestra es que la conclusión sobre el desgaste no depende de que esos dos valores sean exactos dentro de un factor de 2.
- **Otras semillas.** Repetida con las semillas 1, 2 y 3 (media de las tres, `RobustezDesgasteConfig(semillas=[1, 2, 3])`), la robustez del desgaste da una reducción de 61.7 % a 100 % (61.74 % a 100 %), con menor desgaste del control basado en reglas en los seis puntos de las 18 combinaciones (108 de 108). La menor reducción aparece en la misma combinación que con la semilla 42: flujo de 6.0 L/m²/h, fatiga de 0.04 % por pulso y degradación térmica de 0.025 % por °C y minuto (61.7 % a 97.1 %). En el dashboard la robustez del desgaste se ejecuta con una semilla para no superar el tiempo de espera del plan gratuito; las semillas 1 a 3 se ejecutan desde la API o con `ejecutar_robustez_desgaste`.
- **Fatiga de quiebre.** En la combinación menos favorable de la grilla (flujo de 6.0 L/m²/h y degradación térmica de 0.025 % por °C y minuto, con eficacia de 0.90, humedad inicial de 85 % y semilla 42), se buscó con `_combinacion_desgaste` y copias de `ParametrosModelo`, sin modificar `backend/config.py`, la menor fatiga por pulso con la que el control basado en reglas deja de degradarse menos que el temporizador en al menos uno de los seis puntos: empezando en `[0.04, 0.08]` %, duplicando el extremo superior hasta encontrar el quiebre o llegar a 2.0 % y refinando por bisección (tolerancia de 0.0005 puntos de fatiga, máximo 40 iteraciones). La conclusión no se invierte hasta 2.0 % por pulso, que es 100 veces el valor supuesto (0.02 %): incluso con 2.0 % de fatiga por pulso, el control basado en reglas se degrada menos en los seis niveles de salinidad, con una reducción de 10.2 % a 91.3 %, porque la pérdida de integridad reduce el caudal filtrado y la sal acumulada por paso (de 97 a 86 pulsos en el nivel de 240 Ohm por L/m², frente a los 88 del temporizador). Si la fatiga medida en el ensayo de ciclos a 44 °C superara el punto en que la reducción deja de ser positiva, la conclusión sobre el desgaste se invertiría; ese umbral es el criterio de refutación del ensayo de fatiga, y en el modelo está por encima de 2.0 % por pulso. Es un análisis exploratorio reproducible con las funciones del backend:

  ```python
  from backend.analisis import _combinacion_desgaste, ejecutar_robustez_desgaste
  from backend.schemas import RobustezDesgasteConfig

  semillas_1_a_3 = ejecutar_robustez_desgaste(RobustezDesgasteConfig(semillas=[1, 2, 3]))
  cfg = RobustezDesgasteConfig()
  inferior, superior = 0.04, 0.08
  while superior < 2.0 and _combinacion_desgaste(cfg, 6.0, superior, 0.025).puntos_con_menor_desgaste == 6:
      inferior, superior = superior, min(2.0, superior * 2.0)
  if _combinacion_desgaste(cfg, 6.0, superior, 0.025).puntos_con_menor_desgaste < 6:
      for _ in range(40):
          if superior - inferior <= 0.0005:
              break
          medio = (inferior + superior) / 2.0
          inferior, superior = (medio, superior) if _combinacion_desgaste(cfg, 6.0, medio, 0.025).puntos_con_menor_desgaste == 6 else (inferior, medio)
  print(semillas_1_a_3.reduccion_desgaste_min_pct, _combinacion_desgaste(cfg, 6.0, superior, 0.025))
  ```

### 8.12 Calibración del flujo para otro sitio

La pregunta (a) de la sección 8.10 queda abierta mientras la calibración use el ciclo de Cabo de la Vela. Desde la versión 0.4.0, `calibrar_flujo_niebla` acepta un perfil de sitio y `POST /api/v1/analisis/calibracion` (`ejecutar_calibracion` en `backend/analisis.py`) la expone en la API.

**Método.**

- Entrada (`CalibracionConfig`): el rendimiento medido, en (0, 40] L/m²/día; el escenario (DIA_NORMAL por defecto), la humedad inicial (85 % por defecto), la semilla (42 por defecto) y un perfil de sitio opcional.
- Cada corrida de la bisección de la sección 8.6 usa la temperatura media y las amplitudes térmica y de humedad del perfil, con el flujo reemplazado por el valor evaluado. Sin perfil, el resultado es el de la sección 8.6: 0.4889 L/m²/h para 3 L/m²/día y 1.8256 para 10.
- Salida (`CalibracionResultado`): el flujo calibrado, el rendimiento que produce y el perfil con ese flujo, listo para el campo `sitio` de la simulación. Sin perfil, se devuelve el de Cabo de la Vela con el flujo calibrado.
- Un rendimiento fuera del intervalo alcanzable con flujos de 0.1 a 6.0 L/m²/h devuelve `422` con el intervalo en el mensaje. Con el clima de Cabo de la Vela el intervalo es de 0.6713 a 31.8254 L/m²/día, de modo que 40 L/m²/día es inalcanzable.
- En la vista 5 del dashboard, el campo "Rendimiento medido (L/m²/día)" y el botón "Calibrar flujo" llaman al endpoint con el escenario, la humedad inicial y el perfil editado, y copian el flujo calibrado en el campo de flujo del perfil.

**Resultados.** DIA_NORMAL, humedad inicial de 85 %, tasa ALTA, 8 nodos, semilla 42. Los perfiles distintos de Cabo de la Vela son ilustrativos, no sitios reales; cada uno cambia solo los valores indicados.

| Perfil | Temperatura media (°C) | Amplitud térmica (°C) | Amplitud de humedad (puntos) | Flujo para 3 L/m²/día (L/m²/h) | Flujo para 10 L/m²/día (L/m²/h) |
|---|---|---|---|---|---|
| Cabo de la Vela (sin perfil) | 30.0 | 4.5 | 10 | 0.4889 | 1.8256 |
| Sin ciclo de humedad | 30.0 | 4.5 | 0 | 0.5811 | 2.1829 |
| Amplitud de humedad de 20 | 30.0 | 4.5 | 20 | 0.4716 | 1.7565 |
| Amplitud de humedad de 30 | 30.0 | 4.5 | 30 | 0.4659 | 1.7392 |
| Sitio más fresco | 24.0 | 6.0 | 10 | 0.4889 | 1.8256 |
| `SITIO_VERIFICACION` | 28.0 | 5.0 | 12 | 0.4832 | 1.8026 |

En todos los casos el rendimiento obtenido con el flujo calibrado difiere del objetivo en menos de 0.02 L/m²/día.

**Lectura.**

- **La amplitud de humedad es la que cuenta.** El ciclo diurno se ancla en la humedad de las 18:00 y la sube hasta su máximo a las 04:00, de modo que con más amplitud hay más niebla disponible y basta un flujo menor. Sin ciclo de humedad el flujo calibrado es 19.6 % mayor para 10 L/m²/día (18.9 % para 3), y con 30 puntos de amplitud es 4.7 % menor. Calibrar con el ciclo de Cabo de la Vela un sitio sin ciclo de humedad subestimaría su flujo en 16.4 %.
- **La temperatura no cambia el flujo calibrado** en los perfiles evaluados: con 24 °C y 6 °C de amplitud, los flujos coinciden con los de Cabo de la Vela. Sí cambia el rendimiento alcanzable con el flujo máximo de 6.0 L/m²/h (31.26 frente a 31.83 L/m²/día), lejos de los rendimientos de la literatura.
- **Alcance.** La calibración usa un escenario, una semilla y una humedad inicial, y conserva las horas de máximo de Cabo de la Vela (pregunta c de la sección 8.10). El rendimiento medido debe corresponder a las mismas condiciones: un promedio anual no equivale a un día de niebla con 85 % de humedad a las 18:00.

### 8.13 Temporizador con salvaguardas, validación fuera de muestra y robustez temporal

Las secciones 8.8 y 8.11 dejan abiertas tres amenazas a la validez de la comparación. El temporizador fijo no tiene corte térmico ni pausa ecológica, de modo que una parte de su desgaste se debe a la falta de salvaguardas y no a la programación fija (hipótesis H2 del informe final). La banda de transición `[1171.06, 2365.34)` Ohm/día se derivó y se verificó con la misma semilla (hipótesis H3). Y todas las corridas cubren 24 h con una semilla. Esta sección reúne cuatro análisis exploratorios, E1 a E4, ejecutados con un script temporal fuera del repositorio y con las funciones del backend. No modifican `backend/config.py`, los datos abiertos ni la API.

**Temporizador con salvaguardas.** `simular_modo` acepta el parámetro interno `salvaguardas_temporizador` (falso por defecto). Con valor verdadero, en modo temporizador y en cada paso: si la humedad es menor que 30 %, el nodo no extrae ni pulsa (equivale a la REGLA_02); si la matriz está a 45 °C o más, tampoco (equivale a la REGLA_01); en otro caso, el pulso programado apunta a `max(T_m, min(T_m + 12, 44))` °C, un termostato a la temperatura objetivo de las reglas que no enfría una matriz que ya la supera. El reloj del temporizador avanza aunque el pulso se cancele: el ciclo perdido no se reprograma. En E1 se usa con la fracción de extracción de 0.33, de modo que el temporizador con salvaguardas solo difiere de las reglas en la lógica de disparo. Con el valor por defecto, la respuesta de `ejecutar_simulacion` para los cinco escenarios con humedad inicial de 45 % y 85 % es idéntica a la de la versión 0.5.0, y los datos abiertos no cambian.

**E1. Contraste de H2.** Cinco escenarios, humedad inicial de 85 %, 24 h, 8 nodos, tasa ALTA y semilla 42. Degradación en puntos porcentuales de integridad; la fatiga es pulsos por nodo por 0.02 %, la pérdida térmica la registra el simulador y la cristalización es el resto.

| Escenario | Pulsos R / T / TS | Energía (Wh) R / T / TS | Agua (L) R / T / TS | Violaciones R / T / TS | Degradación (%) R / T / TS | Reducción frente a T | Reducción frente a TS |
|---|---|---|---|---|---|---|---|
| DIA_NORMAL | 46 / 88 / 88 | 664.5 / 1065.1 / 834.7 | 254.6 / 340.4 / 266.9 | 0 / 8 / 0 | 0.115 / 2.427 / 0.253 | 95.3 % | 54.6 % |
| INCRUSTACION_SALINA_RAPIDA | 97 / 88 / 88 | 1013.7 / 1065.1 / 834.7 | 185.4 / 240.9 / 199.2 | 0 / 8 / 0 | 1.073 / 4.117 / 1.887 | 73.9 % | 43.1 % |
| SEQUIA | 24 / 88 / 56 | 491.9 / 1065.1 / 682.1 | 149.4 / 204.4 / 155.6 | 0 / 8 / 0 | 0.160 / 2.224 / 0.140 | 92.8 % | -14.3 % |
| TORMENTA_DE_ARENA | 53 / 88 / 88 | 752.1 / 1065.1 / 899.1 | 232.4 / 306.4 / 239.7 | 0 / 8 / 0 | 0.132 / 1.817 / 0.253 | 92.7 % | 47.7 % |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 64 / 88 / 88 | 780.8 / 1065.1 / 747.6 | 235.0 / 305.8 / 244.9 | 0 / 8 / 0 | 0.408 / 3.903 / 0.714 | 89.5 % | 42.8 % |

R: control basado en reglas (modo neuro-simbólico); T: temporizador fijo; TS: temporizador con salvaguardas y fracción de 0.33.

| Escenario | Modo | Fatiga | Térmica | Cristalización |
|---|---|---|---|---|
| DIA_NORMAL | R | 0.115 | 0.000 | 0.000 |
| DIA_NORMAL | TS | 0.220 | 0.000 | 0.033 |
| INCRUSTACION_SALINA_RAPIDA | R | 0.242 | 0.000 | 0.830 |
| INCRUSTACION_SALINA_RAPIDA | TS | 0.220 | 0.000 | 1.667 |
| SEQUIA | R | 0.060 | 0.000 | 0.100 |
| SEQUIA | TS | 0.140 | 0.000 | 0.000 |

Repetido en el barrido de salinidad de la sección 7.2 con las semillas 1 a 5 (media +/- desviación):

| Carga salina (Ohm por L/m²) | Degradación R (%) | Degradación T (%) | Degradación TS (%) | Reducción frente a T | Reducción frente a TS | Pulsos R / TS |
|---|---|---|---|---|---|---|
| 20 | 0.020 +/- 0.000 | 2.151 +/- 0.021 | 0.220 +/- 0.000 | 99.1 % | 90.9 % | 8.0 / 88.0 |
| 40 | 0.052 +/- 0.004 | 2.151 +/- 0.021 | 0.220 +/- 0.000 | 97.6 % | 76.4 % | 20.8 / 88.0 |
| 60 | 0.085 +/- 0.002 | 2.183 +/- 0.016 | 0.220 +/- 0.000 | 96.1 % | 61.1 % | 34.2 / 88.0 |
| 80 | 0.117 +/- 0.002 | 2.495 +/- 0.022 | 0.242 +/- 0.013 | 95.3 % | 51.6 % | 46.8 / 88.0 |
| 120 | 0.419 +/- 0.021 | 3.159 +/- 0.024 | 0.705 +/- 0.043 | 86.7 % | 40.6 % | 65.4 / 88.0 |
| 240 | 1.082 +/- 0.012 | 4.210 +/- 0.014 | 1.901 +/- 0.032 | 74.3 % | 43.1 % | 98.4 / 88.0 |

Lectura de E1:

- **H2 se sostiene con una excepción.** Frente a un temporizador con las mismas salvaguardas y el mismo tope, las reglas se degradan menos en los seis niveles de salinidad y en cuatro de los cinco escenarios, con una reducción de 40.6 % a 90.9 % en el barrido y de 42.8 % a 54.6 % en esos escenarios. La excepción es SEQUIA, donde el temporizador con salvaguardas se degrada 14.3 % menos: la pausa ecológica de las reglas (REGLA_02) tiene prioridad sobre el pulso y deja la membrana con impedancia sobre 1500 Ohm mientras la humedad está bajo 30 % (0.100 puntos de cristalización; la REGLA_04 no se activa y no hay pulsos omitidos por energía), mientras que el temporizador limpia por calendario antes de que la impedancia llegue al umbral.
- **La estimación contable sobrestimaba la ventaja.** La resta de la pérdida térmica del temporizador fijo daba 80.0 % en DIA_NORMAL y 52.7 % en INCRUSTACION_SALINA_RAPIDA; la simulación da 54.6 % y 43.1 %, porque las salvaguardas y el tope también reducen la cristalización del temporizador.
- **El origen de la ventaja residual cambia con la salinidad.** Con salinidad baja se debe a la fatiga: las reglas aplican de 8 a 47 pulsos frente a 88. Con salinidad alta, las reglas pulsan igual o más, y la ventaja se debe a la menor cristalización (0.830 frente a 1.667 puntos en INCRUSTACION_SALINA_RAPIDA). La reducción frente al temporizador con salvaguardas cae de 90.9 % a 40.6 % entre 20 y 120 Ohm por L/m² y queda en 43.1 % con 240.
- **Energía y seguridad.** El temporizador con salvaguardas no tiene pérdida térmica, no supera 44.0 °C en ningún pulso y no registra violaciones. Consume menos energía que las reglas en INCRUSTACION_SALINA_RAPIDA y en TORMENTA_DE_SAL_Y_CALOR_EXTREMO, de modo que la ventaja energética de las reglas frente al temporizador fijo se debe en parte a la falta de salvaguardas de este.

**E2. Validación fuera de muestra de H3.** Robustez de la respuesta (`_combinacion_robustez`, con las condiciones de la sección 8.8) con las semillas 101, 202 y 303, ninguna usada para derivar la banda, una por corrida, y con las eficacias de la cuadrícula (0.80, 0.90 y 1.00) más dos fuera de ella (0.85 y 0.95): 45 barridos.

| Semilla | Flujo (L/m²/h) | Cruces interpolados | Rango del cruce (Ohm/día) | Dentro de la banda |
|---|---|---|---|---|
| 101 | 6.0 | 5 de 5 | 1710.8 a 1877.9 | 5 de 5 |
| 101 | 1.83 | 5 de 5 | 1717.2 a 1895.5 | 5 de 5 |
| 202 | 6.0 | 5 de 5 | 1742.7 a 1905.0 | 5 de 5 |
| 202 | 1.83 | 5 de 5 | 1747.2 a 1921.6 | 5 de 5 |
| 303 | 6.0 | 5 de 5 | 1651.1 a 1814.3 | 5 de 5 |
| 303 | 1.83 | 5 de 5 | 1652.5 a 1830.4 | 5 de 5 |

Con 0.49 L/m²/h los 15 barridos dan `SIN_DATOS`, como con la semilla 42. Los 30 cruces interpolados caen dentro de la banda, y de los 165 puntos con ventaja ninguno contradice su zona: no hay ventaja positiva por debajo de 1171.06 Ohm/día ni ventaja nula o negativa desde 2365.34. H3 no se refuta. El rango de los cruces interpolados, en cambio, se amplía de 1633 a 1867 Ohm/día (sección 8.9) a 1651.1 a 1921.6 Ohm/día: la banda se conserva, pero el rango interpolado de H1-Ciclo 3 debe leerse como una estimación central y no como un intervalo cerrado. Con las eficacias fuera de la cuadrícula (0.85 y 0.95), los 12 cruces van de 1740.8 a 1921.6 Ohm/día.

**E3. Robustez temporal y climática.** Cinco escenarios con humedad inicial de 85 %, tasa ALTA y 8 nodos: a 72 h (tres noches) con la semilla 42, y a 24 h con las semillas 1 a 5.

| Escenario | Reducción del desgaste, 72 h | Pulsos R / T, 72 h | Violaciones R / T, 72 h | Ventaja en recuperación, 72 h (puntos) | Energía R / T, 72 h (Wh) | Reducción del desgaste, 24 h, semillas 1 a 5 | Ventaja en recuperación, 24 h, semillas 1 a 5 (puntos) |
|---|---|---|---|---|---|---|---|
| DIA_NORMAL | 94.8 % | 151 / 280 | 0 / 8 | +3.55 | 2162.1 / 3381.9 | 95.3 +/- 0.1 % | +4.18 +/- 0.39 |
| INCRUSTACION_SALINA_RAPIDA | 75.6 % | 316 / 280 | 0 / 8 | +21.77 | 3465.2 / 3381.9 | 74.3 +/- 0.3 % | +22.65 +/- 0.52 |
| SEQUIA | 93.8 % | 86 / 280 | 0 / 8 | -0.57 | 1667.9 / 3381.9 | 97.2 +/- 0.1 % | +0.04 +/- 0.29 |
| TORMENTA_DE_ARENA | 92.9 % | 170 / 256 | 0 / 8 | +4.77 | 2403.7 / 3101.9 | 92.9 +/- 0.1 % | +3.18 +/- 0.48 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 93.1 % | 222 / 280 | 0 / 8 | +9.30 | 2787.1 / 3381.9 | 89.4 +/- 0.4 % | +9.86 +/- 0.42 |

Lectura de E3:

- **Desgaste y seguridad no cambian de signo.** A 72 h la reducción del desgaste va de 75.6 % a 94.8 %, las reglas no tienen pérdida térmica ni violaciones y el temporizador registra 8 violaciones, un episodio continuo por nodo. Con las semillas 1 a 5 la desviación de la reducción es de 0.1 a 0.4 puntos y las violaciones son 0 frente a 8 en todas las corridas.
- **Dos resultados sí cambian.** En INCRUSTACION_SALINA_RAPIDA a 72 h las reglas consumen más energía que el temporizador (3465.2 frente a 3381.9 Wh), porque acumulan 316 pulsos frente a 280: la afirmación de menor consumo en todos los escenarios solo vale a 24 h. En SEQUIA la ventaja en recuperación es prácticamente nula y cambia de signo con la semilla (positiva en dos de las cinco) y con la duración; en los demás escenarios conserva el signo.
- **Alcance.** El clima sigue siendo sintético y repetido día a día; tres noches no representan la estacionalidad ni episodios extremos de varios días.

**E4. Contexto comparable.** Cereceda et al. (2008) midieron 7.0 L/m² al día con un colector estándar en los acantilados costeros de Atacama. Con `calibrar_flujo_niebla(7.0)` (DIA_NORMAL, humedad inicial de 85 %, semilla 42) el flujo calibrado es 1.261 L/m²/h, y el barrido con ese flujo y la semilla 42 da:

| Carga salina (Ohm por L/m²) | Rendimiento (L/m²/día) | Incrustación diaria (Ohm/día) | Zona | Ventaja en recuperación (puntos) | Reducción del desgaste |
|---|---|---|---|---|---|
| 20 | 8.05 | 161.0 | `BAJO_TRANSICION` | sin pulsos | 100.0 % |
| 40 | 7.56 | 302.4 | `BAJO_TRANSICION` | sin pulsos | 100.0 % |
| 60 | 7.17 | 430.1 | `BAJO_TRANSICION` | sin pulsos | 100.0 % |
| 80 | 7.00 | 559.9 | `BAJO_TRANSICION` | -7.62 | 99.2 % |
| 120 | 6.88 | 825.1 | `BAJO_TRANSICION` | -5.94 | 98.9 % |
| 240 | 6.75 | 1619.6 | `TRANSICION` | -0.99 | 96.7 % |

Con el rendimiento de un sitio costero real, cinco de los seis niveles de carga salina quedan por debajo de la banda y el de 240 Ohm por L/m² queda dentro, con ventaja todavía negativa (estado de cruce `SIN_CRUCE_NEURO_INFERIOR`). Es coherente con H1-Ciclo 3: en un sitio con niebla costera abundante, la ventaja esperada del control por reglas es la reducción del desgaste y no la recuperación, salvo con cargas salinas por litro muy altas. El cálculo usa el ciclo térmico y de humedad de Cabo de la Vela con un flujo equivalente al de Atacama, y la carga salina de ese sitio no se conoce: indica en qué zona caería el sitio para cada carga, no cuál es su carga.

Reproducción (desde la raíz del repositorio):

```python
from backend import config
from backend.analisis import _combinacion_robustez, calibrar_flujo_niebla, ejecutar_barrido
from backend.schemas import BarridoConfig, Escenario, ModoOperacion, RobustezConfig, SimulationConfig, TasaSalinizacion
from backend.simulador import generar_entorno, simular_modo

def corrida(escenario, semilla=42, horas=24):
    entorno = generar_entorno(SimulationConfig(duracion_horas=horas, escenario=escenario, humedad_ambiente_inicial_pct=85.0,
                                               tasa_salinizacion=TasaSalinizacion.ALTA, semilla=semilla))
    return (simular_modo(entorno, ModoOperacion.NEURO_SIMBOLICO),
            simular_modo(entorno, ModoOperacion.TEMPORIZADOR_FIJO),
            simular_modo(entorno, ModoOperacion.TEMPORIZADOR_FIJO, config.FRACCION_MAXIMA_EXTRACCION,
                         salvaguardas_temporizador=True))

e1 = {escenario: corrida(escenario) for escenario in Escenario}  # E1
e2 = [_combinacion_robustez(RobustezConfig(semillas=[semilla]), flujo, eficacia).barrido.cruce
      for semilla in (101, 202, 303) for flujo in (6.0, 1.83, 0.49) for eficacia in (0.80, 0.85, 0.90, 0.95, 1.00)]  # E2
e3 = {escenario: corrida(escenario, horas=72) for escenario in Escenario}  # E3 a 72 h; a 24 h, semilla=1 a 5
flujo_atacama = calibrar_flujo_niebla(7.0)  # E4
e4 = ejecutar_barrido(BarridoConfig(semillas=[42], flujo_niebla_maximo_l_m2_h=flujo_atacama))
```

### 8.14 Métrica homogénea de recuperación y sensibilidad al intervalo del temporizador

La sección 8.13 deja dos amenazas acotadas, pero no resueltas. La recuperación tras pulso se mide en momentos distintos en cada modo (sección 7.5), de modo que la ventaja en recuperación compara políticas de limpieza y no el estado de la membrana. Y el temporizador con salvaguardas usa un único intervalo, 120 min, elegido por el equipo. Esta sección reúne dos análisis exploratorios, E5 y E6, ejecutados con un script temporal fuera del repositorio y con las funciones del backend. No modifican `backend/config.py`, los datos abiertos ni la API. El intervalo se varía con el parámetro interno `intervalo_temporizador_min` de `simular_modo` (sección 3.3); con 120 min, el temporizador con salvaguardas reproduce exactamente las cifras de E1 en los cinco escenarios y en el barrido.

**Métrica homogénea.** Para cada modo, la conductancia relativa media en el tiempo es `G = media_t min(1, Z_nom / Z_t)`, donde `Z_t` es `impedancia_promedio[t]`, la impedancia media de la red al final de cada paso. La métrica se mide igual en todos los modos y en todos los pasos, haya o no pulso, y se expresa en porcentaje. La ventaja en `G` es `G_R - G_alternativa`, en puntos; las diferencias se calculan con los valores sin redondear.

**E5. Métrica homogénea de recuperación.** Cinco escenarios, humedad inicial de 85 %, 24 h, 8 nodos, tasa ALTA y semilla 42. La última columna es la ventaja en recuperación tras pulso de la sección 5.3.

| Escenario | G R / T / TS (%) | Ventaja en G frente a T (puntos) | Ventaja en G frente a TS (puntos) | Ventaja en recuperación tras pulso frente a T (puntos) |
|---|---|---|---|---|
| DIA_NORMAL | 76.65 / 76.14 / 80.93 | +0.51 | -4.28 | +4.33 |
| INCRUSTACION_SALINA_RAPIDA | 67.12 / 54.39 / 60.96 | +12.73 | +6.16 | +22.70 |
| SEQUIA | 76.99 / 83.71 / 81.98 | -6.71 | -4.99 | +0.17 |
| TORMENTA_DE_ARENA | 76.00 / 74.61 / 78.98 | +1.39 | -2.98 | +3.35 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 74.56 / 68.83 / 74.46 | +5.73 | +0.10 | +9.99 |

R: control basado en reglas (modo neuro-simbólico); T: temporizador fijo; TS: temporizador con salvaguardas, fracción de 0.33 e intervalo de 120 min.

Barrido de salinidad de la sección 7.2 con las semillas 1 a 5 (media +/- desviación). La incrustación diaria, la zona y la ventaja en recuperación tras pulso son las de `ejecutar_barrido` con las mismas semillas.

| Carga salina (Ohm por L/m²) | Incrustación diaria (Ohm/día) | Zona | G R (%) | G T (%) | G TS (%) | Ventaja en G frente a T (puntos) | Ventaja en G frente a TS (puntos) | Ventaja en recuperación tras pulso frente a T (puntos) |
|---|---|---|---|---|---|---|---|---|
| 20 | 669.0 | `BAJO_TRANSICION` | 80.77 +/- 0.07 | 92.26 +/- 0.17 | 94.15 +/- 0.13 | -11.50 +/- 0.13 | -13.39 +/- 0.10 | -7.06 |
| 40 | 1296.0 | `TRANSICION` | 77.94 +/- 0.07 | 85.94 +/- 0.27 | 89.14 +/- 0.22 | -8.00 +/- 0.33 | -11.20 +/- 0.28 | -3.12 |
| 60 | 1926.9 | `TRANSICION` | 77.14 +/- 0.13 | 80.63 +/- 0.33 | 84.77 +/- 0.28 | -3.49 +/- 0.22 | -7.64 +/- 0.18 | +0.65 |
| 80 | 2554.6 | `SOBRE_TRANSICION` | 76.62 +/- 0.08 | 76.11 +/- 0.37 | 80.92 +/- 0.33 | +0.51 +/- 0.38 | -4.30 +/- 0.34 | +4.18 |
| 120 | 3530.2 | `SOBRE_TRANSICION` | 74.50 +/- 0.21 | 68.74 +/- 0.42 | 74.42 +/- 0.39 | +5.76 +/- 0.22 | +0.08 +/- 0.18 | +9.88 |
| 240 | 5574.6 | `SOBRE_TRANSICION` | 67.02 +/- 0.22 | 54.30 +/- 0.46 | 60.88 +/- 0.45 | +12.72 +/- 0.24 | +6.13 +/- 0.23 | +22.65 |

Cruces interpolados linealmente sobre las medias, con el mismo criterio de `_interpolar_cruce`:

| Métrica y alternativa | Niveles vecinos (Ohm/día) | Cruce interpolado (Ohm/día) | Carga salina del cruce (Ohm por L/m²) | Posición frente a la banda `[1171.06, 2365.34)` |
|---|---|---|---|---|
| Recuperación tras pulso, frente a T | 1296.0 a 1926.9 | 1818.4 | 56.6 | Dentro |
| G, frente a T | 1926.9 a 2554.6 | 2474.5 | 77.4 | Por encima (los niveles vecinos abarcan el límite superior) |
| G, frente a TS | 2554.6 a 3530.2 | 3513.0 | 119.3 | Por encima |

Lectura de E5:

- **La estructura del veredicto b) se conserva.** Con la métrica homogénea, la ventaja de las reglas es negativa con incrustación baja y positiva con incrustación alta, cambia de signo una sola vez y crece con la incrustación diaria, frente a T y frente a TS. La dispersión entre semillas es pequeña: la desviación de la ventaja no supera 0.38 puntos.
- **El cruce se desplaza hacia arriba y sale de la banda.** Frente a T, el cruce de `G` queda entre 1926.9 y 2554.6 Ohm/día, con estimación interpolada de 2474.5 Ohm/día, por encima del límite superior de la banda; la recuperación tras pulso lo sitúa en 1818.4 Ohm/día, dentro de ella. Con 2554.6 Ohm/día la ventaja en `G` es +0.51 +/- 0.38 puntos: positiva en las cinco semillas, pero pequeña. Frente a TS, el cruce sube a 3513.0 Ohm/día; con 3530.2 Ohm/día la ventaja (+0.08 +/- 0.18) es indistinguible de cero, positiva en tres de las cinco semillas, y solo con 5574.6 Ohm/día es clara (+6.13 puntos).
- **La recuperación tras pulso sobrestima la ventaja y adelanta el cruce.** Las reglas esperan a que la impedancia supere 1500 Ohm antes de limpiar, y su `G` baja de 80.77 % a 67.02 % a lo largo del barrido, mientras que su recuperación tras pulso se mantiene entre 85.9 % y 88.9 % (sección 7.5). La métrica tras pulso solo ve el instante posterior a la limpieza; `G` incluye el tiempo que la membrana pasa incrustada entre pulsos. Con incrustación alta, las ventajas en `G` son cerca de la mitad de las ventajas tras pulso (+12.72 frente a +22.65 puntos con 240 Ohm por L/m²).
- **Coincidencia con el veredicto b).** Coinciden en que la ventaja en recuperación es condicional a la incrustación diaria y solo aparece con incrustación alta. No coinciden en la ubicación del cruce: la banda `[1171.06, 2365.34)` describe el cruce de la recuperación tras pulso, no el de la conductancia media. Con la métrica homogénea, las reglas mantienen la membrana más conductora que el temporizador fijo por encima de unos 2500 Ohm/día y que el temporizador con salvaguardas por encima de unos 3500 Ohm/día.
- **Escenarios.** El signo de la ventaja en `G` frente a T coincide con el de la ventaja tras pulso en cuatro de los cinco escenarios. En SEQUIA la ventaja tras pulso es +0.17 puntos (indistinguible de cero según E3) y la ventaja en `G` es -6.71 puntos: la pausa ecológica deja la membrana incrustada mientras la humedad está bajo 30 %, el mismo mecanismo que explica la excepción de desgaste de E1.
- **Limitación.** `G` usa la impedancia media de la red, no la de cada nodo. Como `1/Z` es convexa, `Z_nom / media(Z_i)` no supera la media de `Z_nom / Z_i`: `G` subestima la conductancia media de los nodos, y la subestima más cuanto más dispersas estén sus impedancias. La dispersión entre nodos no se registra por modo, de modo que no se puede descartar que el sesgo sea distinto en cada uno; las reglas limpian cada nodo cuando cruza el umbral y el temporizador limpia todos a la vez. `G` pondera además cada paso por igual, no por el agua captada en él.

**E6. Sensibilidad al intervalo del temporizador con salvaguardas.** Temporizador con salvaguardas, fracción de 0.33 e intervalos de 60, 120, 180 y 240 min. Cinco escenarios con humedad inicial de 85 %, 24 h, 8 nodos, tasa ALTA y semilla 42. Los valores de cada temporizador se dan en el orden 60 / 120 / 180 / 240 min.

| Escenario | Pulsos R | Pulsos TS | Energía R (Wh) | Energía TS (Wh) | Degradación R (%) | Degradación TS (%) | Reducción frente a TS | Ventaja en G frente a TS (puntos) |
|---|---|---|---|---|---|---|---|---|
| DIA_NORMAL | 46 | 144 / 88 / 56 / 40 | 664.5 | 1248.1 / 834.7 / 539.5 / 392.3 | 0.115 | 0.662 / 0.253 / 0.550 / 0.967 | 82.6 / 54.6 / 79.1 / 88.1 % | -7.35 / -4.28 / +1.58 / +6.08 |
| INCRUSTACION_SALINA_RAPIDA | 97 | 144 / 88 / 56 / 40 | 1013.7 | 1248.1 / 834.7 / 539.5 / 392.3 | 1.073 | 1.267 / 1.887 / 2.264 / 2.320 | 15.4 / 43.1 / 52.6 / 53.8 % | -0.48 / +6.16 / +13.84 / +18.66 |
| SEQUIA | 24 | 80 / 56 / 32 / 24 | 491.9 | 940.3 / 682.1 / 411.7 / 318.4 | 0.160 | 0.439 / 0.140 / 1.156 / 1.331 | 63.5 / -14.3 / 86.2 / 88.0 % | -3.34 / -4.99 / +5.28 / +7.56 |
| TORMENTA_DE_ARENA | 53 | 144 / 88 / 56 / 40 | 752.1 | 1365.1 / 899.1 / 585.9 / 415.9 | 0.132 | 0.662 / 0.253 / 0.601 / 1.146 | 80.0 / 47.7 / 78.0 / 88.4 % | -5.32 / -2.98 / +2.37 / +6.66 |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 64 | 144 / 88 / 56 / 40 | 780.8 | 1077.9 / 747.6 / 483.1 / 351.9 | 0.408 | 0.829 / 0.714 / 1.304 / 1.761 | 50.8 / 42.8 / 68.7 / 76.8 % | -4.26 / +0.10 / +6.95 / +11.88 |

Con cualquier intervalo, el temporizador con salvaguardas no tiene pérdida térmica ni violaciones ecológicas.

Repetido en el barrido de salinidad con las semillas 1 a 5 (media +/- desviación; la reducción se calcula con las medias). En todos los niveles y semillas el temporizador con salvaguardas aplica 144, 88, 56 y 40 pulsos y consume, en promedio, 1236.8, 826.1, 534.5 y 389.2 Wh con 60, 120, 180 y 240 min (desviación de 1.0 a 4.4 Wh).

| Carga salina (Ohm por L/m²) | Degradación R (%) | Degradación TS (%) | Reducción frente a TS | G R (%) | G TS (%) | Pulsos R | Energía R (Wh) |
|---|---|---|---|---|---|---|---|
| 20 | 0.020 +/- 0.000 | 0.360 +/- 0.000 / 0.220 +/- 0.000 / 0.140 +/- 0.000 / 0.100 +/- 0.000 | 94.4 / 90.9 / 85.7 / 80.0 % | 80.77 | 94.73 / 94.15 / 91.81 / 89.73 | 8.0 | 149.7 |
| 40 | 0.052 +/- 0.004 | 0.360 +/- 0.000 / 0.220 +/- 0.000 / 0.140 +/- 0.000 / 0.100 +/- 0.000 | 85.6 / 76.4 / 62.9 / 48.0 % | 77.94 | 90.54 / 89.14 / 85.18 / 81.86 | 20.8 | 347.9 |
| 60 | 0.085 +/- 0.002 | 0.527 +/- 0.016 / 0.220 +/- 0.000 / 0.196 +/- 0.017 / 0.430 +/- 0.036 | 83.8 / 61.1 / 56.3 / 80.1 % | 77.14 | 87.01 / 84.77 / 79.66 / 75.60 | 34.2 | 513.2 |
| 80 | 0.117 +/- 0.002 | 0.660 +/- 0.013 / 0.242 +/- 0.013 / 0.547 +/- 0.031 / 0.972 +/- 0.056 | 82.3 / 51.6 / 78.6 / 88.0 % | 76.62 | 83.93 / 80.92 / 75.01 / 70.49 | 46.8 | 666.8 |
| 120 | 0.419 +/- 0.021 | 0.835 +/- 0.017 / 0.705 +/- 0.043 / 1.317 +/- 0.042 / 1.774 +/- 0.029 | 49.8 / 40.6 / 68.2 / 76.4 % | 74.50 | 78.72 / 74.42 / 67.53 / 62.58 | 65.4 | 856.1 |
| 240 | 1.082 +/- 0.012 | 1.269 +/- 0.024 / 1.901 +/- 0.032 / 2.274 +/- 0.012 / 2.323 +/- 0.003 | 14.8 / 43.1 / 52.4 / 53.4 % | 67.02 | 67.46 / 60.88 / 53.16 / 48.34 | 98.4 | 1011.0 |

Lectura de E6:

- **Ningún intervalo iguala a las reglas en desgaste en el barrido.** Con intervalos de 60 a 240 min, la reducción del desgaste de las reglas frente al temporizador con salvaguardas va de 14.8 % a 94.4 % en los seis niveles. En los escenarios, el único caso en que el temporizador se degrada menos es SEQUIA con 120 min (-14.3 %, la excepción de E1); con 60, 180 y 240 min la excepción desaparece (63.5 %, 86.2 % y 88.0 %). La excepción de la sequía depende, por tanto, del intervalo de 120 min.
- **El mejor intervalo para el temporizador cambia con la salinidad.** La menor reducción de cada nivel se obtiene con 240 min en 20 y 40 Ohm por L/m² (80.0 % y 48.0 %), con 180 min en 60 (56.3 %), con 120 min en 80 y 120 (51.6 % y 40.6 %) y con 60 min en 240 (14.8 %). Con poca sal conviene pulsar poco, para evitar fatiga; con mucha sal, pulsar seguido, para evitar cristalización. Un calendario fijo puede ajustarse a una carga salina, pero no a todas; las reglas ajustan la frecuencia de limpieza a la incrustación sin conocerla de antemano.
- **Costo de acercarse a las reglas.** El temporizador que más se acerca, con 60 min y 240 Ohm por L/m², reduce la ventaja de las reglas a 14.8 % y mantiene una `G` algo mayor (67.46 % frente a 67.02 %), a costa de 144 pulsos frente a 98.4 y de 1236.8 frente a 1011.0 Wh. En INCRUSTACION_SALINA_RAPIDA ocurre lo mismo: 15.4 %, `G` de 67.60 % frente a 67.12 % y 1248.1 frente a 1013.7 Wh. Con 60 min, el temporizador con salvaguardas tiene mayor `G` que las reglas en todos los niveles del barrido y en los cinco escenarios.
- **Intervalos largos.** Con 180 y 240 min el temporizador consume menos energía que las reglas en los cinco escenarios, pero se degrada más y, desde 60 Ohm por L/m² (240 min) o desde 80 Ohm por L/m² (180 min), mantiene una `G` menor. Ningún intervalo ofrece a la vez menor desgaste y mayor `G` que las reglas con menos energía.
- **Relación con E5.** El cruce de la ventaja en `G` frente al temporizador con salvaguardas depende del intervalo: no hay cruce con 60 min (la ventaja va de -13.96 a -0.44 puntos), está en 3513.0 Ohm/día con 120 min, en 2310.9 Ohm/día con 180 min y en 1748.8 Ohm/día con 240 min. La posición del cruce en recuperación depende, por tanto, de la frecuencia de limpieza de la alternativa, además de la incrustación diaria del sitio.
- **Alcance.** Los intervalos explorados son múltiplos del paso de 5 min entre 60 y 240 min; el temporizador conserva el reloj que avanza aunque el pulso se cancele, la temperatura de pulso limitada a 44 °C y la fracción de 0.33. Otro diseño de temporizador (por ejemplo, con reprogramación del ciclo perdido) no está representado.

Reproducción (desde la raíz del repositorio):

```python
import statistics
from backend import config
from backend.analisis import ESCENARIOS_BARRIDO, TASAS_BARRIDO, ejecutar_barrido
from backend.schemas import BarridoConfig, Escenario, ModoOperacion, SimulationConfig, TasaSalinizacion
from backend.simulador import generar_entorno, simular_modo

def conductancia_media(diag):  # G en %, con la impedancia media de la red en cada paso
    return 100 * statistics.fmean(min(1.0, config.IMPEDANCIA_NOMINAL_OHMS / z) for z in diag.impedancia_promedio)

def corrida(escenario, semilla=42, tasa=TasaSalinizacion.ALTA, intervalos=(60, 120, 180, 240)):
    entorno = generar_entorno(SimulationConfig(duracion_horas=24, escenario=escenario, humedad_ambiente_inicial_pct=85.0,
                                               tasa_salinizacion=tasa, semilla=semilla))
    modos = {"R": simular_modo(entorno, ModoOperacion.NEURO_SIMBOLICO),
             "T": simular_modo(entorno, ModoOperacion.TEMPORIZADOR_FIJO)}
    for intervalo in intervalos:
        modos[f"TS{intervalo}"] = simular_modo(entorno, ModoOperacion.TEMPORIZADOR_FIJO, config.FRACCION_MAXIMA_EXTRACCION,
                                               salvaguardas_temporizador=True, intervalo_temporizador_min=intervalo)
    return modos

e5_e6_escenarios = {escenario: corrida(escenario) for escenario in Escenario}  # E5 (a) y E6 (a)
e5_e6_barrido = {(escenario, tasa): [corrida(escenario, semilla, tasa) for semilla in (1, 2, 3, 4, 5)]
                 for escenario in ESCENARIOS_BARRIDO for tasa in TASAS_BARRIDO}  # E5 (b) y E6 (b)
referencia = ejecutar_barrido(BarridoConfig(semillas=[1, 2, 3, 4, 5]))  # incrustación diaria, zona y cruce tras pulso
```

La degradación de cada modo es `100 - integridad_final_promedio`; la energía, `energia_total_wh`; los pulsos, `pulsos`. Los cruces de `G` se interpolan linealmente entre los dos niveles consecutivos del barrido en que la ventaja media pasa de `<= 0` a `> 0`.
