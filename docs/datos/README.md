# Datos de referencia del modelo Axioma-H

Esta carpeta contiene los resultados de referencia del simulador como datos abiertos. Se generan ejecutando el backend localmente, sin red y sin la API desplegada, con el script `scripts/generar_resultados_referencia.py`. Los archivos están en UTF-8, con fin de línea LF y punto decimal.

## 1. Cómo regenerarlos

Desde la raíz del proyecto, con el entorno virtual activo:

```powershell
python scripts/generar_resultados_referencia.py
```

La salida es determinista: dos ejecuciones con el mismo código producen archivos idénticos. Para escribir en otra carpeta, agregar `--salida <carpeta>`. Si cambia el modelo, se deben regenerar los archivos y revisar que las cifras de `README.md` y `docs/modelo_simulacion.md` sigan coincidiendo.

## 2. Condiciones

| Conjunto | Condiciones |
|---|---|
| Escenarios | Los cinco escenarios con humedad inicial de 45 % y 85 %; 24 h, inicio a las 18:00, paso de 5 min, 8 nodos, tasa de salinización ALTA, semilla 42. |
| Barrido de salinidad | `DIA_NORMAL` e `INCRUSTACION_SALINA_RAPIDA` con tasas BAJA, MEDIA y ALTA; humedad inicial de 85 %, 24 h, 8 nodos, semillas 1 a 5. |

Todos los parámetros son los de `backend/config.py`, sin modificar. Varios son supuestos de orden de magnitud; su origen está en [../referencias.md](../referencias.md), sección 3.

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

`<modo>` es `neuro` (control neuro-simbólico), `temporizador` (temporizador fijo, fracción 0.45) o `temporizador_tope` (temporizador con tope ecológico, fracción 0.33). Las definiciones de los indicadores y de las causas están en [../modelo_simulacion.md](../modelo_simulacion.md), sección 4.

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
| `humedad_inicial_pct` | Humedad relativa a las 18:00 (%). |

## 5. resultados_completos.json

| Clave | Contenido |
|---|---|
| `condiciones` | Versión del servicio y condiciones de ejecución de ambos conjuntos. |
| `escenarios` | Lista de 10 corridas con `escenario`, `humedad_inicial_pct`, `comparativa` (los tres modos), `conjeturas_validadas` y `detalle_verificacion` (indicadores, informativos y causas), con el mismo formato que la respuesta de `POST /api/v1/simulacion/ejecutar`. |
| `barrido_salinidad` | Respuesta completa del barrido, con el formato de `POST /api/v1/analisis/barrido-salinidad`. |

El JSON omite `series_temporales` y `bitacora` para mantener un tamaño manejable (288 puntos y entre 24 y 210 eventos por corrida). Se reproducen con `POST /api/v1/simulacion/ejecutar` y la misma configuración, o importando `backend.simulador.ejecutar_simulacion`.
