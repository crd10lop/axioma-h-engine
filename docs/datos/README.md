# Datos de referencia del modelo Axioma-H

Esta carpeta contiene los resultados de referencia del simulador como datos abiertos. Se generan ejecutando el backend localmente, sin red y sin la API desplegada, con el script `scripts/generar_resultados_referencia.py`. Los archivos están en UTF-8, con fin de línea LF y punto decimal.

## 1. Cómo regenerarlos

Desde la raíz del proyecto, con el entorno virtual activo:

```powershell
python scripts/generar_resultados_referencia.py
```

La salida es determinista: dos ejecuciones con el mismo código producen archivos idénticos. El script escribe en esta carpeta los cuatro CSV, `resultados_completos.json` y `datapackage.json`, y en `docs/api/` el contrato `openapi.json`. Para comprobar que todos coinciden con el modelo actual sin modificarlos, agregar `--comprobar`: el script genera los archivos en un directorio temporal, los compara byte a byte y termina con código 1 si alguno difiere o falta. La carpeta de destino no se puede cambiar por línea de comandos. Si cambia el modelo, se deben regenerar los archivos y revisar que las cifras de `README.md` y `docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md` sigan coincidiendo.

## 2. Condiciones

| Conjunto | Condiciones |
|---|---|
| Escenarios | Los cinco escenarios con humedad inicial de 45 % y 85 %; 24 h, inicio a las 18:00, paso de 5 min, 8 nodos, tasa de salinización ALTA, semilla 42. |
| Barrido de salinidad | `DIA_NORMAL` e `INCRUSTACION_SALINA_RAPIDA` con tasas BAJA, MEDIA y ALTA; humedad inicial de 85 %, 24 h, 8 nodos, semillas 1 a 5. |
| Robustez de la respuesta | El mismo barrido con cada combinación de flujo de niebla (6.0, 1.83 y 0.49 L/m²/h) y eficacia del pulso (0.80, 0.90 y 1.00); humedad inicial de 85 %, 24 h, 8 nodos, semilla 42. |
| Robustez del desgaste | El mismo barrido con cada combinación de flujo de niebla (6.0 y 1.83 L/m²/h), fatiga por pulso (0.01, 0.02 y 0.04 %) y degradación térmica (0.025, 0.05 y 0.10 % por °C y minuto), con la eficacia del pulso de 0.90; humedad inicial de 85 %, 24 h, 8 nodos, semilla 42. |

Salvo el flujo, la eficacia, la fatiga y la degradación térmica de las robusteces, que se aplican sobre copias de los parámetros, todos los parámetros son los de `backend/config.py`, sin modificar. Varios son supuestos de orden de magnitud; su origen está en [../06_Referencias_y_Trazabilidad_AxiomaH.md](../06_Referencias_y_Trazabilidad_AxiomaH.md), sección 3.

## 3. resultados_escenarios.csv

Una fila por escenario y humedad inicial (10 filas). Una celda vacía indica que la corrida no produjo datos para ese valor, por ejemplo la recuperación de un modo que no ejecutó pulsos.

Las descripciones y los tipos de esta sección, de las dos siguientes y de la sección 8 son los del diccionario único `DICCIONARIO_CAMPOS` de `scripts/generar_resultados_referencia.py`, que también genera el esquema de `datapackage.json` (sección 7). Una prueba automatizada verifica que cada descripción del diccionario aparezca en este documento.

| Campo | Tipo | Descripción |
|---|---|---|
| `escenario` | string | Escenario ambiental. |
| `humedad_inicial_pct` | number | Humedad relativa a las 18:00 (%). |
| `<modo>_litros` | number | Agua captada por los 8 nodos (L). |
| `<modo>_pulsos` | integer | Pulsos resistivos ejecutados. |
| `<modo>_energia_wh` | number | Energía consumida, pulsos y electrónica (Wh). |
| `<modo>_integridad_final_pct` | number | Integridad promedio de las membranas al final (%). |
| `<modo>_degradacion_pct` | number | Degradación acumulada, 100 - integridad final (%). |
| `<modo>_violaciones` | integer | Episodios de extracción fuera del límite ecológico. |
| `<modo>_recuperacion_pct` | number | Conductancia relativa promedio tras cada pulso (%). |
| `c1_validada` | boolean | Estado de la Conjetura 1 (True o False). |
| `c2_validada` | boolean | Estado de la Conjetura 2 (True o False). |
| `c3_validada` | boolean | Estado de la Conjetura 3 (True o False). |
| `c1_recuperacion_pct` | number | Indicador de la Conjetura 1: recuperación de caudal (umbral >= 90 %). |
| `c1_ahorro_energia_pct` | number | Indicador de la Conjetura 1: ahorro de energía en pulsos (umbral >= 35 %). |
| `c2_tiempo_regeneracion_s` | number | Indicador de la Conjetura 2: tiempo de regeneración (umbral < 120 s). |
| `c2_perdida_termica_pct` | number | Indicador de la Conjetura 2: pérdida de integridad térmica (umbral 0 %). |
| `c3_violaciones` | number | Indicador de la Conjetura 3: violaciones ecológicas (umbral 0). |
| `c3_rendimiento_nocturno_l_m2_noche` | number | Indicador de la Conjetura 3: rendimiento nocturno (umbral >= 12 L/m²/noche). |
| `c1_reduccion_degradacion_pct` | number | Informativo: reducción de la degradación frente al temporizador (%). |
| `c2_pulsos_regenerados` | integer | Informativo: pulsos que alcanzaron 1100 Ohm. |
| `c2_pulsos_totales` | integer | Informativo: pulsos totales del control basado en reglas. |
| `c2_t95_promedio_s` | number | Informativo: tiempo hasta el 95 % de la remoción de cada pulso (s). |
| `c2_impedancia_tras_pulso_ohm` | number | Informativo: impedancia promedio al terminar cada pulso (Ohm). |
| `c3_rendimiento_temporizador_l_m2_noche` | number | Informativo: rendimiento nocturno del temporizador fijo. |
| `c1_causas` | string | Causas de no validación de la Conjetura 1, separadas por punto y coma. |
| `c2_causas` | string | Causas de no validación de la Conjetura 2, separadas por punto y coma. |
| `c3_causas` | string | Causas de no validación de la Conjetura 3, separadas por punto y coma. |
| `<modo>_personas_acceso_basico` | number | Informativo: personas abastecidas con 20 L por persona al día (acceso básico de la OMS). |
| `<modo>_rendimiento_l_m2_dia` | number | Informativo: litros por día y por m² de colector de la red (8 m²). |

`<modo>` es `neuro` (control basado en reglas, modo neuro-simbólico), `temporizador` (temporizador fijo, fracción 0.45) o `temporizador_tope` (temporizador con tope ecológico, fracción 0.33). En `datapackage.json`, la descripción de cada columna antepone el nombre del modo. Las definiciones de los indicadores y de las causas están en [../04_Modelo_de_Control_y_Simulacion_AxiomaH.md](../04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 4, y las del impacto comunitario en la sección 7.6.

## 4. barrido_salinidad.csv

Una fila por combinación de escenario y tasa (6 filas), ordenadas por carga salina creciente.

| Campo | Tipo | Descripción |
|---|---|---|
| `escenario` | string | Escenario ambiental. |
| `tasa_salinizacion` | string | Tasa de salinización de la combinación simulada. |
| `carga_salina_ohm_l_m2` | number | Aumento de impedancia por litro captado por m². |
| `n_semillas` | integer | Corridas promediadas, una por semilla. |
| `recuperacion_neuro_media` | number | Media de la recuperación tras pulso del control basado en reglas (%). |
| `recuperacion_neuro_desv` | number | Desviación estándar muestral de la recuperación del control basado en reglas. |
| `recuperacion_temporizador_media` | number | Media de la recuperación tras pulso del temporizador fijo (%). |
| `recuperacion_temporizador_desv` | number | Desviación estándar muestral de la recuperación del temporizador fijo. |
| `degradacion_neuro_media` | number | Media de la degradación acumulada del control basado en reglas (%). |
| `degradacion_neuro_desv` | number | Desviación estándar muestral de la degradación del control basado en reglas. |
| `degradacion_temporizador_media` | number | Media de la degradación acumulada del temporizador fijo (%). |
| `degradacion_temporizador_desv` | number | Desviación estándar muestral de la degradación del temporizador fijo. |
| `reduccion_desgaste_pct` | number | Reducción del desgaste, (D_temp - D_neuro) / D_temp * 100, con las medias. |
| `rendimiento_neuro_l_m2_dia_media` | number | Media del rendimiento del control basado en reglas (L/m² al día). |
| `incrustacion_diaria_ohm_media` | number | Media de la carga salina por el rendimiento del control basado en reglas (Ohm/día). |
| `ventaja_recuperacion_pts` | number | Recuperación media del control basado en reglas menos la del temporizador (puntos). |
| `pulsos_neuro_media` | number | Media de los pulsos del control basado en reglas en toda la red. |
| `humedad_inicial_pct` | number | Humedad relativa a las 18:00 (%). |

## 5. robustez_respuesta.csv

Una fila por combinación de flujo y eficacia y por punto del barrido (9 combinaciones por 6 puntos, 54 filas), en orden de flujo, eficacia y carga salina creciente. Los campos del punto se calculan con el flujo y la eficacia de la fila, y los del cruce se repiten en las seis filas de cada combinación. `cruce_estado` vale `INTERPOLADO`, `CRUCE_DESCENDENTE`, `SIN_CRUCE_NEURO_SUPERIOR`, `SIN_CRUCE_NEURO_INFERIOR` o `SIN_DATOS`. Los tres últimos campos del cruce, agregados en la versión 0.4.0, informan entre qué dos niveles de incrustación diaria se interpola y su separación: el cruce real puede estar en cualquier punto de ese intervalo. Quedan vacíos si no hay cruce.

| Campo | Tipo | Descripción |
|---|---|---|
| `flujo_niebla_maximo_l_m2_h` | number | Flujo máximo de niebla de la combinación (L/m²/h). |
| `eficacia_maxima_pulso` | number | Eficacia máxima del pulso de la combinación. |
| `cruce_estado` | string | Estado del cruce de la ventaja en recuperación frente a la incrustación diaria. |
| `cruce_incrustacion_diaria_ohm` | number | Incrustación diaria interpolada donde la ventaja vale 0 (Ohm/día). |
| `cruce_carga_salina_ohm_l_m2` | number | Carga salina interpolada donde la ventaja vale 0 (Ohm por L/m²). |
| `cruce_incrustacion_inferior_ohm` | number | Menor incrustación diaria de los dos puntos entre los que se interpola el cruce (Ohm/día). |
| `cruce_incrustacion_superior_ohm` | number | Mayor incrustación diaria de los dos puntos entre los que se interpola el cruce (Ohm/día). |
| `cruce_separacion_ohm` | number | Distancia entre los dos puntos interpolados del cruce (Ohm/día). |
| `escenario` | string | Escenario ambiental. |
| `tasa_salinizacion` | string | Tasa de salinización de la combinación simulada. |
| `carga_salina_ohm_l_m2` | number | Aumento de impedancia por litro captado por m². |
| `n_semillas` | integer | Corridas promediadas, una por semilla. |
| `recuperacion_neuro_media` | number | Media de la recuperación tras pulso del control basado en reglas (%). |
| `recuperacion_neuro_desv` | number | Desviación estándar muestral de la recuperación del control basado en reglas. |
| `recuperacion_temporizador_media` | number | Media de la recuperación tras pulso del temporizador fijo (%). |
| `recuperacion_temporizador_desv` | number | Desviación estándar muestral de la recuperación del temporizador fijo. |
| `degradacion_neuro_media` | number | Media de la degradación acumulada del control basado en reglas (%). |
| `degradacion_neuro_desv` | number | Desviación estándar muestral de la degradación del control basado en reglas. |
| `degradacion_temporizador_media` | number | Media de la degradación acumulada del temporizador fijo (%). |
| `degradacion_temporizador_desv` | number | Desviación estándar muestral de la degradación del temporizador fijo. |
| `reduccion_desgaste_pct` | number | Reducción del desgaste, (D_temp - D_neuro) / D_temp * 100, con las medias. |
| `rendimiento_neuro_l_m2_dia_media` | number | Media del rendimiento del control basado en reglas (L/m² al día). |
| `incrustacion_diaria_ohm_media` | number | Media de la carga salina por el rendimiento del control basado en reglas (Ohm/día). |
| `ventaja_recuperacion_pts` | number | Recuperación media del control basado en reglas menos la del temporizador (puntos). |
| `pulsos_neuro_media` | number | Media de los pulsos del control basado en reglas en toda la red. |
| `humedad_inicial_pct` | number | Humedad relativa a las 18:00 (%). |

El método y la lectura de estos datos están en [../04_Modelo_de_Control_y_Simulacion_AxiomaH.md](../04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.8.

## 6. resultados_completos.json

| Clave | Contenido |
|---|---|
| `condiciones` | Versión del servicio y condiciones de ejecución de los escenarios, el barrido y las dos robusteces. |
| `escenarios` | Lista de 10 corridas con `escenario`, `humedad_inicial_pct`, `comparativa` (los tres modos), `conjeturas_validadas`, `detalle_verificacion` (indicadores, informativos y causas) e `impacto_comunitario` (los tres modos: litros por día, rendimiento por m², personas con 15 y 20 L y área de colector por persona con los rendimientos de la literatura), con el mismo formato que la respuesta de `POST /api/v1/simulacion/ejecutar`. |
| `barrido_salinidad` | Respuesta completa del barrido, con el formato de `POST /api/v1/analisis/barrido-salinidad`, incluidos el flujo y la eficacia usados y el cruce. |
| `robustez_respuesta` | Resumen de `POST /api/v1/analisis/robustez-respuesta`: rango de la reducción del desgaste, combinaciones con cruce y rango de la incrustación diaria del cruce. Las combinaciones completas están en `robustez_respuesta.csv`. |
| `robustez_desgaste` | Resumen de `POST /api/v1/analisis/robustez-desgaste`: rango de la reducción del desgaste y combinaciones en que el control basado en reglas se degrada menos en todos los puntos. Las combinaciones completas están en `robustez_desgaste.csv`. |

El JSON omite `series_temporales` y `bitacora` para mantener un tamaño manejable (288 puntos y entre 24 y 210 eventos por corrida). Se reproducen con `POST /api/v1/simulacion/ejecutar` y la misma configuración, o importando `backend.simulador.ejecutar_simulacion`.

## 7. datapackage.json y contrato de la API

`datapackage.json` es un descriptor [Frictionless Data Package](https://specs.frictionlessdata.io/data-package/) de los cuatro CSV: nombre del paquete, licencia MIT, versión del servicio y, por cada CSV, ruta, formato, codificación UTF-8 y esquema de campos con nombre, tipo (`string`, `number`, `integer` o `boolean`) y descripción. Las celdas vacías se declaran como valores ausentes. Permite que otra herramienta lea los datos con sus tipos sin consultar este documento.

El contrato de la API está en [../api/openapi.json](../api/openapi.json), generado desde `backend.main.app.openapi()`. Describe todos los endpoints, sus esquemas de entrada y salida y sus límites de validación, de modo que otros sistemas pueden generar clientes a partir de él.

`--comprobar` también verifica que ambos archivos coincidan con el código actual. El uso desde otros sistemas, con ejemplos de `curl`, pandas y validación del paquete, está en [../05_Despliegue_y_Operacion_AxiomaH.md](../05_Despliegue_y_Operacion_AxiomaH.md), sección 7.

## 8. robustez_desgaste.csv

Una fila por combinación de flujo, fatiga por pulso y degradación térmica (2 por 3 por 3, 18 filas), en ese orden. Cada fila resume los seis puntos del barrido de la combinación; los puntos completos se reproducen con `POST /api/v1/analisis/robustez-desgaste` y la misma configuración. Una reducción del desgaste vacía indica que ningún punto la tiene, porque el temporizador no se degradó.

| Campo | Tipo | Descripción |
|---|---|---|
| `flujo_niebla_maximo_l_m2_h` | number | Flujo máximo de niebla de la combinación (L/m²/h). |
| `fatiga_por_pulso_pct` | number | Pérdida de integridad por ciclo térmico de la combinación (%). |
| `degradacion_termica_pct_por_c_min` | number | Pérdida de integridad por cada °C sobre 45 y minuto de exposición de la combinación (%). |
| `reduccion_desgaste_min_pct` | number | Menor reducción del desgaste entre los puntos del barrido (%). |
| `reduccion_desgaste_max_pct` | number | Mayor reducción del desgaste entre los puntos del barrido (%). |
| `puntos_con_menor_desgaste` | integer | Puntos del barrido en que el control basado en reglas se degrada menos que el temporizador. |
| `puntos_totales` | integer | Puntos del barrido de la combinación. |
| `humedad_inicial_pct` | number | Humedad relativa a las 18:00 (%). |

El método y la lectura de estos datos están en [../04_Modelo_de_Control_y_Simulacion_AxiomaH.md](../04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.11.
