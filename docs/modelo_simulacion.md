# Modelo de control y simulación del motor Axioma-H

Este documento describe el motor de reglas neuro-simbólico, el simulador comparativo y la forma en que se verifican las conjeturas del Ciclo 2. Los valores de todos los parámetros están en `backend/config.py`. Las ecuaciones compartidas por el motor y el simulador están en `backend/modelo_fisico.py`.

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

### 3.4 Parámetros

| Parámetro | Valor | Origen |
|---|---|---|
| Umbral de corte térmico | 45.0 °C | PRD |
| Temperatura objetivo del pulso | 44.0 °C | Matriz |
| Umbral de humedad ecológica | 30.0 % | PRD |
| Umbral de reserva crítica | 30.0 % | PRD |
| Umbral de impedancia | 1500 Ohm | PRD |
| Impedancia nominal | 1000 Ohm | PRD |
| Duración del pulso | 90 s | PRD |
| Fracción máxima de extracción | 0.33 | Matriz |
| Caudal durante pulso / reserva crítica | 80 % / 50 % | PRD |
| Factor de impedancia regenerada | 1.10 (1100 Ohm) | Criterio del equipo |
| Área de colector por nodo | 1.0 m² | Supuesto |
| Flujo máximo de niebla | 6.0 L/m²/h (0.35 g/m³ a 5 m/s) | Supuesto |
| HR mínima de captación, exponente | 20 %, 1.5 | Supuesto |
| Amplitud del ciclo de HR | 10 puntos, máximo a las 04:00 | Supuesto |
| Temperatura ambiente | 30 +/- 4.5 °C, máximo a las 14:00 | Supuesto |
| Calentamiento solar de la matriz | +7 °C con radiación máxima | Supuesto |
| Incrustación BAJA / MEDIA / ALTA | 20 / 40 / 80 Ohm por L/m² | Supuesto |
| Eficacia máxima del pulso | 0.90 | Supuesto |
| Temperaturas de efecto mínimo y de saturación | 30 °C / 44 °C | Supuesto |
| Carga salina de referencia | 2500 Ohm | Supuesto |
| Constante de disolución | 25 s | Supuesto |
| Capacidad de reserva, reserva inicial | 150 Wh, 70 % | Supuesto |
| Recarga solar máxima | 20 W | Supuesto |
| Capacidad térmica de la matriz | 800 J/K | Supuesto |
| Conductancia de pérdidas | 30 W/K | Supuesto |
| Consumo base neuro-simbólico / temporizador | 0.6 W / 0.2 W | Supuesto |
| Fatiga por pulso | 0.02 % | Supuesto |
| Degradación térmica | 0.05 %/(°C·min) | Supuesto |
| Degradación por cristalización | 0.10 %/h | Supuesto |
| Ruido HR / T por paso | 1.0 % / 0.3 °C | Supuesto |
| Dispersión entre nodos HR / T / salinización | +/-2 % / +/-0.5 °C / +/-10 % | Supuesto |

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

## 5. Resultados con semilla 42 y 8 nodos

Configuración común: 24 h, paso de 5 min, HR inicial de 85 % y tasa de salinización ALTA. Esta es la configuración de ejemplo de la API.

### 5.1 Comparativa de modos

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

### 5.2 Verificación de conjeturas

| Escenario | Recuperación (%) | Ahorro (%) | C1 | Regeneración (s) | Pérdida térmica (%) | C2 | Violaciones | Rendimiento nocturno (L/m²) | C3 |
|---|---|---|---|---|---|---|---|---|---|
| DIA_NORMAL | 88.78 | 46.50 | false | 11934.78 | 0.00 | false | 0 | 16.97 | true |
| INCRUSTACION_SALINA_RAPIDA | 85.92 | 12.49 | false | 6593.81 | 0.00 | false | 0 | 11.45 | false |
| SEQUIA | 88.78 | 63.31 | false | 21575.00 | 0.00 | false | 0 | 14.19 | true |
| TORMENTA_DE_ARENA | 85.78 | 37.97 | false | 10358.49 | 0.00 | false | 0 | 16.97 | true |
| TORMENTA_DE_SAL_Y_CALOR_EXTREMO | 88.02 | 35.17 | false | 9257.81 | 0.00 | false | 0 | 16.62 | true |

El tiempo de regeneración se calcula con el criterio de 1100 Ohm descrito en 3.2. Con el criterio anterior (volver bajo 1500 Ohm), los valores eran 0.23, 278.28, 0.24, 0.30 y 1.81 s, y la Conjetura 2 se validaba en cuatro escenarios.

### 5.3 Análisis

**Conjetura 1 (false en los cinco escenarios).** El indicador que falla es la recuperación de caudal, que queda entre 85.8 % y 88.8 %. El pulso se dispara apenas Z supera 1500 Ohm, es decir, con unos 500 Ohm de carga salina. Con `eta_max = 0.90` y la atenuación por carga, cada pulso remueve cerca del 75 % de esa carga y la impedancia queda alrededor de 1125 Ohm, lo que equivale a un 89 % de conductancia. Para superar el 90 % haría falta `eta_max` de 0.94 o más (ver 5.4), un valor que hoy no tiene respaldo experimental.

El ahorro de energía sí cumple en cuatro escenarios. En INCRUSTACION_SALINA_RAPIDA no cumple (12.5 %): la red pulsa más veces que el temporizador (97 frente a 88) y, de noche, cada pulso neuro-simbólico eleva la matriz unos 18 °C, contra 12 °C del temporizador. En TORMENTA_DE_SAL_Y_CALOR_EXTREMO el ahorro (35.17 %) apenas supera el umbral, por lo que el resultado es frágil.

**Conjetura 2 (false en los cinco escenarios).** El componente térmico de la conjetura sí se cumple. En ningún escenario hay pérdida térmica en el modo neuro-simbólico. El pulso más caliente fue de 44.30 °C, cuando la matriz ya estaba sobre el objetivo por radiación. En TORMENTA_DE_SAL_Y_CALOR_EXTREMO la matriz llegó a 44.79 °C sin cruzar 45 °C, así que la REGLA_01 no se activó en la simulación. El temporizador, en cambio, alcanzó 55.9 °C y perdió 2.69 % de integridad por degradación térmica.

Lo que falla es el tiempo de regeneración. El criterio anterior (volver bajo 1500 Ohm) se satisfacía de forma trivial. Como el pulso se dispara apenas la impedancia cruza el umbral, bastaba remover unos pocos ohmios, y el indicador quedaba entre 0.2 y 1.8 s sin decir nada sobre la limpieza real de la membrana. El nuevo criterio exige volver a 1100 Ohm, es decir, recuperar al menos el 91 % de la conductancia nominal.

Con `eta_max = 0.90`, un pulso típico deja la impedancia cerca de 1125 Ohm. Por eso ninguno de los pulsos de los cinco escenarios alcanza el criterio. Cada evento se mide entonces hasta el pulso siguiente, y el promedio queda entre 1.8 y 6.0 horas.

El resultado es coherente con el de la Conjetura 1: ambos indicadores dependen de la fracción de sal que remueve un pulso. La sensibilidad se muestra en 5.5.

**Conjetura 3 (false solo en INCRUSTACION_SALINA_RAPIDA).** El modo neuro-simbólico no registró violaciones ecológicas en ningún escenario. Esto se cumple por diseño: el tope del 33 % es estructural (D3) y la REGLA_02 detiene la extracción con HR < 30 %. El temporizador acumula un episodio continuo por nodo debido a su fracción de 0.45.

En la incrustación rápida, el rendimiento nocturno cae a 11.45 L/m² porque la impedancia se mantiene alta y la REGLA_04 reduce el caudal. En la corrida de 24 h, la sequía y la tormenta de arena ocurren de día, después de la única noche simulada. Por eso afectan poco el rendimiento nocturno.

**Observación adicional.** El modo neuro-simbólico capta entre 23 % y 27 % menos agua que el temporizador. Esto es consecuencia directa del tope ecológico (0.33 frente a 0.45) y es el costo esperado de la Conjetura 3: el temporizador obtiene más agua a costa de violar el límite territorial.

### 5.4 Sensibilidad de la recuperación a la eficacia máxima del pulso

Recuperación promedio en el modo neuro-simbólico (%). Un asterisco indica que la Conjetura 1 queda validada con ese valor. Esta tabla es solo un análisis de sensibilidad: el valor configurado sigue siendo 0.90.

| eta_max | DIA_NORMAL | INCRUSTACION_SALINA_RAPIDA | SEQUIA | TORMENTA_DE_ARENA | TORMENTA_DE_SAL_Y_CALOR_EXTREMO |
|---|---|---|---|---|---|
| 0.85 | 87.16 | 84.16 | 87.17 | 84.06 | 86.29 |
| 0.90 | 88.78 | 85.92 | 88.78 | 85.78 | 88.02 |
| 0.94 | 90.12* | 87.34 | 90.12* | 86.95 | 89.47 |
| 0.95 | 90.46* | 87.69 | 90.46* | 87.15 | 89.85 |
| 1.00 | 92.20* | 89.60 | 92.22* | 88.89 | 91.73* |

La Conjetura 1 depende de un parámetro que todavía no se ha medido. Antes de dar por refutada o validada la conjetura, la prioridad experimental es medir la fracción de sal que remueve un pulso de 90 s a 44 °C.

### 5.5 Sensibilidad del tiempo de regeneración a la eficacia máxima del pulso

Tiempo promedio de regeneración en el modo neuro-simbólico (s), con el criterio de 1100 Ohm. Entre paréntesis se indican los pulsos regenerados sobre los pulsos totales. Un asterisco indica que la Conjetura 2 queda validada. Igual que en 5.4, el valor configurado sigue siendo 0.90.

| eta_max | DIA_NORMAL | INCRUSTACION_SALINA_RAPIDA | SEQUIA | TORMENTA_DE_ARENA | TORMENTA_DE_SAL_Y_CALOR_EXTREMO |
|---|---|---|---|---|---|
| 0.90 | 11934.8 (0/46) | 6593.8 (0/97) | 21575.0 (0/24) | 10358.5 (0/53) | 9257.8 (0/64) |
| 0.95 | 12200.0 (0/45) | 6877.4 (0/93) | 21575.0 (0/24) | 10764.7 (0/51) | 9257.8 (0/64) |
| 0.96 | 12200.0 (0/45) | 6952.2 (0/92) | 21575.0 (0/24) | 10764.7 (0/51) | 9404.8 (0/63) |
| 0.97 | 84.5 (44/44)* | 3231.5 (49/92) | 84.1 (24/24)* | 2111.0 (35/51) | 1678.0 (52/62) |
| 1.00 | 69.1 (43/43)* | 711.0 (76/92) | 68.9 (23/23)* | 2001.1 (35/48) | 851.8 (56/62) |

El indicador tiene un comportamiento de umbral. Por debajo de `eta_max` cercano a 0.97, ningún pulso llega a 1100 Ohm. Por encima, la mayoría lo logra en menos de 90 s. Esto refuerza la recomendación de 5.4: medir la eficacia real del pulso define el resultado de las Conjeturas 1 y 2.
