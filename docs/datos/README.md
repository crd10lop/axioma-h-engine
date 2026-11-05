# Datos de referencia del modelo Axioma-H

Esta carpeta contiene los resultados de referencia del simulador como datos abiertos. Se generan ejecutando el backend localmente, sin red y sin la API desplegada, con el script `scripts/generar_resultados_referencia.py`. Los archivos están en UTF-8, con fin de línea LF y punto decimal.

## 1. Cómo regenerarlos

Desde la raíz del proyecto, con el entorno virtual activo:

```powershell
python scripts/generar_resultados_referencia.py
```

La salida es determinista: dos ejecuciones con el mismo código producen archivos idénticos. Para comprobar que los archivos de esta carpeta coinciden con el modelo actual sin modificarlos, agregar `--comprobar`: el script genera los datos en un directorio temporal, los compara byte a byte con los de esta carpeta y termina con código 1 si alguno difiere o falta. La carpeta de destino no se puede cambiar por línea de comandos. Si cambia el modelo, se deben regenerar los archivos y revisar que las cifras de `README.md` y `docs/04_Modelo_de_Control_y_Simulacion_AxiomaH.md` sigan coincidiendo.

## 2. Condiciones

| Conjunto | Condiciones |
|---|---|
| Escenarios | Los cinco escenarios con humedad inicial de 45 % y 85 %; 24 h, inicio a las 18:00, paso de 5 min, 8 nodos, tasa de salinización ALTA, semilla 42. |
| Barrido de salinidad | `DIA_NORMAL` e `INCRUSTACION_SALINA_RAPIDA` con tasas BAJA, MEDIA y ALTA; humedad inicial de 85 %, 24 h, 8 nodos, semillas 1 a 5. |
| Robustez de la respuesta | El mismo barrido con cada combinación de flujo de niebla (6.0, 1.83 y 0.49 L/m²/h) y eficacia del pulso (0.80, 0.90 y 1.00); humedad inicial de 85 %, 24 h, 8 nodos, semilla 42. |

Salvo el flujo y la eficacia de la robustez, que se aplican sobre copias de los parámetros, todos los parámetros son los de `backend/config.py`, sin modificar. Varios son supuestos de orden de magnitud; su origen está en [../06_Referencias_y_Trazabilidad_AxiomaH.md](../06_Referencias_y_Trazabilidad_AxiomaH.md), sección 3.

## 3. resultados_escenarios.csv

Una fila por escenario y humedad inicial (10 filas). Una celda vacía indica que la corrida no produjo datos para ese valor, por ejemplo la recuperación de un modo que no ejecutó pulsos.

| Campo | Descripción |
|---|---|
| `escenario` | Escenario ambiental. |
| `humedad_inicial_pct` | Humedad relativa a las 18:00 (%). |
| `<modo>_litros` | Agua captada por los 8 nodos (L). |
| `<modo>_pulsos` | Pulsos resistivos ejecutados. |
| `<modo>_energia_wh` | Energía consumida, pulsos y electrónica (Wh). |
| `<modo>_integridad_final_pct` | Integridad promedio de las membranas al final (%). |
| `<modo>_degradacion_pct` | Degradación acumulada, `100 - integridad final` (%). |
| `<modo>_violaciones` | Episodios de extracción fuera del límite ecológico. |
| `<modo>_recuperacion_pct` | Conductancia relativa promedio tras cada pulso (%). |
| `c1_validada`, `c2_validada`, `c3_validada` | Estado de cada conjetura (`True` o `False`). |
| `c1_recuperacion_pct`, `c1_ahorro_energia_pct` | Indicadores de la Conjetura 1 (umbrales: >= 90 % y >= 35 %). |
| `c2_tiempo_regeneracion_s`, `c2_perdida_termica_pct` | Indicadores de la Conjetura 2 (umbrales: < 120 s y 0 %). |
| `c3_violaciones`, `c3_rendimiento_nocturno_l_m2_noche` | Indicadores de la Conjetura 3 (umbrales: 0 y >= 12 L/m²/noche). |
| `c1_reduccion_degradacion_pct` | Informativo: reducción de la degradación frente al temporizador (%). |
| `c2_pulsos_regenerados`, `c2_pulsos_totales` | Informativo: pulsos que alcanzaron 1100 Ohm y pulsos totales del neuro-simbólico. |
| `c2_t95_promedio_s` | Informativo: tiempo hasta el 95 % de la remoción de cada pulso (s). |
| `c2_impedancia_tras_pulso_ohm` | Informativo: impedancia promedio al terminar cada pulso (Ohm). |
| `c3_rendimiento_temporizador_l_m2_noche` | Informativo: rendimiento nocturno del temporizador fijo. |
| `c1_causas`, `c2_causas`, `c3_causas` | Causas de no validación separadas por `;`; vacío si la conjetura se valida. |
| `<modo>_personas_acceso_basico` | Informativo: personas abastecidas con 20 L por persona al día (acceso básico de la OMS), con el agua del modo normalizada a un día. |
| `<modo>_rendimiento_l_m2_dia` | Informativo: litros por día y por m² de colector de la red (8 m²). La literatura reporta de 3 a 10 L/m² al día. |

`<modo>` es `neuro` (control neuro-simbólico), `temporizador` (temporizador fijo, fracción 0.45) o `temporizador_tope` (temporizador con tope ecológico, fracción 0.33). Las definiciones de los indicadores y de las causas están en [../04_Modelo_de_Control_y_Simulacion_AxiomaH.md](../04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 4, y las del impacto comunitario en la sección 7.6.

## 4. barrido_salinidad.csv

Una fila por combinación de escenario y tasa (6 filas), ordenadas por carga salina creciente.

| Campo | Descripción |
|---|---|
| `escenario`, `tasa_salinizacion` | Combinación simulada. |
| `carga_salina_ohm_l_m2` | Aumento de impedancia por litro captado por m². |
| `n_semillas` | Corridas promediadas, una por semilla. |
| `recuperacion_neuro_media`, `recuperacion_neuro_desv` | Media y desviación estándar muestral de la recuperación tras pulso del neuro-simbólico (%). |
| `recuperacion_temporizador_media`, `recuperacion_temporizador_desv` | Lo mismo para el temporizador fijo. |
| `degradacion_neuro_media`, `degradacion_neuro_desv` | Media y desviación de la degradación acumulada del neuro-simbólico (%). |
| `degradacion_temporizador_media`, `degradacion_temporizador_desv` | Lo mismo para el temporizador fijo. |
| `reduccion_desgaste_pct` | `(D_temp - D_neuro) / D_temp * 100`, calculada con las medias. |
| `rendimiento_neuro_l_m2_dia_media` | Media del rendimiento del neuro-simbólico (L/m² al día). |
| `incrustacion_diaria_ohm_media` | Media de la carga salina por el rendimiento del neuro-simbólico: aumento de impedancia por sal en un día (Ohm/día). |
| `ventaja_recuperacion_pts` | Recuperación media del neuro-simbólico menos la del temporizador (puntos); vacía si falta alguna. |
| `pulsos_neuro_media` | Media de los pulsos del neuro-simbólico en toda la red. |
| `humedad_inicial_pct` | Humedad relativa a las 18:00 (%). |

## 5. robustez_respuesta.csv

Una fila por combinación de flujo y eficacia y por punto del barrido (9 combinaciones por 6 puntos, 54 filas), en orden de flujo, eficacia y carga salina creciente. Los campos desde `escenario` hasta `pulsos_neuro_media` son los de `barrido_salinidad.csv` (sección 4), calculados con el flujo y la eficacia de la fila.

| Campo | Descripción |
|---|---|
| `flujo_niebla_maximo_l_m2_h` | Flujo máximo de niebla de la combinación (L/m²/h). |
| `eficacia_maxima_pulso` | Eficacia máxima del pulso de la combinación. |
| `cruce_estado` | Cruce de la ventaja en recuperación frente a la incrustación diaria en la combinación: `INTERPOLADO`, `CRUCE_DESCENDENTE`, `SIN_CRUCE_NEURO_SUPERIOR`, `SIN_CRUCE_NEURO_INFERIOR` o `SIN_DATOS`. Se repite en las seis filas de la combinación. |
| `cruce_incrustacion_diaria_ohm` | Incrustación diaria interpolada donde la ventaja vale 0 (Ohm/día); vacía sin cruce. |
| `cruce_carga_salina_ohm_l_m2` | Carga salina interpolada en el mismo punto (Ohm por L/m²); vacía sin cruce. |
| `escenario` a `pulsos_neuro_media` | Campos del punto, como en `barrido_salinidad.csv`. |
| `humedad_inicial_pct` | Humedad relativa a las 18:00 (%). |

El método y la lectura de estos datos están en [../04_Modelo_de_Control_y_Simulacion_AxiomaH.md](../04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.8.

## 6. resultados_completos.json

| Clave | Contenido |
|---|---|
| `condiciones` | Versión del servicio y condiciones de ejecución de los escenarios, el barrido y la robustez. |
| `escenarios` | Lista de 10 corridas con `escenario`, `humedad_inicial_pct`, `comparativa` (los tres modos), `conjeturas_validadas`, `detalle_verificacion` (indicadores, informativos y causas) e `impacto_comunitario` (los tres modos: litros por día, rendimiento por m², personas con 15 y 20 L y área de colector por persona con los rendimientos de la literatura), con el mismo formato que la respuesta de `POST /api/v1/simulacion/ejecutar`. |
| `barrido_salinidad` | Respuesta completa del barrido, con el formato de `POST /api/v1/analisis/barrido-salinidad`, incluidos el flujo y la eficacia usados y el cruce. |
| `robustez_respuesta` | Resumen de `POST /api/v1/analisis/robustez-respuesta`: rango de la reducción del desgaste, combinaciones con cruce y rango de la incrustación diaria del cruce. Las combinaciones completas están en `robustez_respuesta.csv`. |

El JSON omite `series_temporales` y `bitacora` para mantener un tamaño manejable (288 puntos y entre 24 y 210 eventos por corrida). Se reproducen con `POST /api/v1/simulacion/ejecutar` y la misma configuración, o importando `backend.simulador.ejecutar_simulacion`.
