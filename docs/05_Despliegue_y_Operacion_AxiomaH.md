# Despliegue y operación de Axioma-H Engine

**Proyecto:** Axioma-H — Captación Pasiva de Agua Atmosférica  
**Equipo:** AXIOMA — Curso Fundamentos de Investigación (UdeA), Ciclo 2  
**Repositorio:** https://github.com/crd10lop/axioma-h-engine  
**Aplicación desplegada:** [Dashboard](https://axioma-h-dashboard.onrender.com) | [API](https://axioma-h-api.onrender.com/docs)

Este documento describe el despliegue que está en uso para la demostración del Ciclo 2: la plataforma, los servicios publicados, el flujo de despliegue automático, la configuración, la verificación y la operación del plan gratuito. La configuración está versionada en `render.yaml`.

---

## 1. Plataforma y servicios publicados

La API y el dashboard están desplegados en **Render**, en el plan gratuito, como dos servicios web definidos por el Blueprint `render.yaml`. Ambos se construyen desde la rama `main` de este repositorio.

| Servicio en Render | Componente | URL pública | Comando de inicio |
|---|---|---|---|
| `axioma-h-api` | API FastAPI (`backend/`) | https://axioma-h-api.onrender.com | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| `axioma-h-dashboard` | Dashboard Streamlit (`frontend/`) | https://axioma-h-dashboard.onrender.com | `streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` |

Características comunes de ambos servicios, según `render.yaml`:

- entorno Python 3.12.10 (`PYTHON_VERSION`);
- construcción con `pip install -r requirements.txt`;
- rama `main` y despliegue automático con `autoDeployTrigger: checksPass` (sección 2);
- la API declara `healthCheckPath: /api/v1/health`, que Render consulta para saber si el servicio está activo.

### 1.1 Direcciones de acceso

| Recurso | URL | Qué se espera |
|---|---|---|
| Dashboard | https://axioma-h-dashboard.onrender.com | La barra lateral muestra **Estado: SALUDABLE** y el recorrido de cinco vistas. |
| API, documentación interactiva | https://axioma-h-api.onrender.com/docs | Interfaz Swagger con los endpoints de evaluación, simulación y análisis de robustez. |
| API, salud | https://axioma-h-api.onrender.com/api/v1/health | Código 200 con `"estado": "SALUDABLE"`. |
| API, esquema OpenAPI | https://axioma-h-api.onrender.com/openapi.json | Publica todas las rutas de la API; la copia versionada está en `docs/api/openapi.json` (sección 7). |

Los endpoints disponibles se describen en `README.md` (sección Endpoints) y en [02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md), secciones 3.1 a 3.3.

## 2. Flujo de despliegue automático

Cada push a `main` sigue este flujo:

1. GitHub Actions ejecuta el workflow `.github/workflows/ci.yml`: instala `requirements-dev.txt`, ejecuta la suite de `pytest` con cobertura de líneas y ramas (`coverage.xml`) y envía el resultado a SonarQube Cloud.
2. SonarQube Cloud evalúa la Quality Gate Sonar way (calificación A en fiabilidad, seguridad y mantenibilidad; cobertura del código nuevo de al menos 80 %; duplicación de 3 % como máximo).
3. Render despliega la API y el dashboard solo cuando todos los checks del commit están en verde (`autoDeployTrigger: checksPass`). Un push con pruebas fallidas o con la Quality Gate fallida no se despliega, y los servicios siguen con la versión anterior.

El workflow también se ejecuta en cada pull request, pero Render solo despliega desde `main`.

### 2.1 Configuración de las plataformas

Esta es la configuración aplicada en cada plataforma para que el flujo funcione:

1. **SonarQube Cloud.** El proyecto `crd10lop_axioma-h-engine` (organización `cristian-diez`) tiene desactivado el análisis automático (**Administration > Analysis Method**). El análisis se hace desde CI, que es la única forma de incluir la cobertura. La configuración está en `sonar-project.properties`.
2. **GitHub.** El secreto `SONAR_TOKEN` (**Settings > Secrets and variables > Actions**) contiene el token generado en SonarQube Cloud. Si el secreto no existe, el workflow ejecuta las pruebas y omite el análisis.
3. **Render.** Cada servicio tiene **Auto-Deploy** en **After CI Checks Pass** (**Settings > Build & Deploy**).

## 3. Variables de entorno

| Variable | Servicio | Valor en el despliegue | Valor por defecto en local | Uso |
|---|---|---|---|---|
| `AXIOMA_API_URL` | Dashboard | `https://axioma-h-api.onrender.com` | `http://127.0.0.1:8000` | URL de la API, sin barra final. En Render se define en **Environment** del servicio `axioma-h-dashboard`, porque `render.yaml` la declara con `sync: false`. |
| `AXIOMA_TIMEOUT_SALUD_SEG` | Dashboard | No definida (75 s) | `75` | Espera máxima de la verificación de salud, en segundos. |
| `AXIOMA_CORS_ORIGINS` | API | No definida | Vacío | Orígenes adicionales permitidos, separados por comas. Solo hace falta si una página web consume la API desde el navegador; el dashboard llama a la API desde el servidor y no la requiere. |
| `PYTHON_VERSION` | Ambos | `3.12.10` | No aplica | Versión de Python de la construcción en Render, fijada en `render.yaml`. |

## 4. Verificación del despliegue

### 4.1 Verificación manual

1. Abrir https://axioma-h-api.onrender.com/api/v1/health. Debe responder `"estado": "SALUDABLE"`.
2. Abrir https://axioma-h-api.onrender.com/docs y ejecutar `POST /api/v1/simulacion/ejecutar` con el payload de ejemplo.
3. Abrir https://axioma-h-dashboard.onrender.com. La barra lateral debe mostrar **Estado: SALUDABLE** y la URL de la API.
4. En la vista **3. Simulación comparativa**, ejecutar un escenario y confirmar que aparecen el resumen ejecutivo y las tarjetas de la comparativa, incluidas **Recuperación tras pulso** y **Degradación acumulada**.
5. En la vista **4. Respuesta a la pregunta**, ejecutar el barrido con una semilla y confirmar que aparecen los dos gráficos y las frases de lectura.

### 4.2 Verificación automatizada

El script `scripts/verificar_despliegue.py` ejecuta contra los servicios publicados las comprobaciones de la sección 4.1 y otras adicionales. Solo requiere las dependencias de `requirements.txt` y no forma parte de la suite de `pytest`, porque depende de la red.

```bash
python scripts/verificar_despliegue.py
```

Argumentos opcionales:

| Argumento | Valor por defecto | Uso |
|---|---|---|
| `--api` | Variable `AXIOMA_API_URL` o `https://axioma-h-api.onrender.com` | URL base de la API. |
| `--dashboard` | `https://axioma-h-dashboard.onrender.com` | URL base del dashboard. |
| `--timeout` | `90` | Espera máxima por solicitud, en segundos. Cubre la reactivación de los servicios suspendidos del plan gratuito. |

Comprobaciones realizadas (26 en total):

1. `GET /api/v1/health` responde 200 con `"estado": "SALUDABLE"`.
2. `GET /docs` y `GET /openapi.json` responden 200 y el esquema publica `/api/v1/nodo/evaluar`, `/api/v1/simulacion/ejecutar`, `/api/v1/analisis/barrido-salinidad`, `/api/v1/analisis/sensibilidad`, `/api/v1/analisis/incertidumbre`, `/api/v1/analisis/robustez-respuesta`, `/api/v1/analisis/dimensionamiento` y `/api/v1/sitios`.
3. `POST /api/v1/nodo/evaluar` aplica cada regla del motor (REGLA_01 a REGLA_05) con la acción y el estado esperados, respetando el orden de prioridad. Dos casos más verifican la supervisión humana: `anulacion_manual = SUSPENDER_EXTRACCION` con telemetría nominal activa la REGLA_06 con caudal 0 %, y con la matriz a 46 °C activa la REGLA_01, porque el corte térmico prevalece sobre el operador.
4. `POST /api/v1/nodo/evaluar` rechaza una telemetría inválida con código 422.
5. `POST /api/v1/simulacion/ejecutar` responde para el ejemplo del esquema y para cada escenario, con comparativa entre modos (incluido `modo_temporizador_tope_ecologico`), conjeturas validadas, `causas_no_validacion` como lista en cada conjetura, `impacto_comunitario` con los tres modos y serie temporal no vacía.
6. `POST /api/v1/analisis/barrido-salinidad` responde, con una sola semilla para no exceder el tiempo de espera, seis puntos ordenados por carga salina; y `POST /api/v1/analisis/sensibilidad` responde un punto por cada valor de eficacia solicitado, con el estado de la Conjetura 1; y `POST /api/v1/analisis/incertidumbre` responde, con 5 muestras, probabilidades entre 0 y 1 y percentiles del rendimiento ordenados.
7. `POST /api/v1/simulacion/ejecutar` con un perfil de sitio y una eficacia del pulso propios devuelve esos valores en `parametros_usados`; `POST /api/v1/analisis/robustez-respuesta` responde, con una semilla, nueve combinaciones de seis puntos; `POST /api/v1/analisis/dimensionamiento` responde una dimensión por cada flujo de referencia (SUPUESTO, CALIBRADO_MAX y CALIBRADO_MIN); y `GET /api/v1/sitios` devuelve los tres perfiles de Cabo de la Vela.
8. `GET /_stcore/health` del dashboard responde 200 con el cuerpo `ok`.
9. `GET /` del dashboard responde 200.
10. Las funciones de `frontend/cliente_api.py` funcionan contra la URL pública de la API.

El script imprime una tabla con el resultado, la duración y el detalle de cada comprobación, y termina con código 0 si todas pasan o 1 si alguna falla.

### 4.3 Última verificación registrada

| Fecha | Estado del repositorio | Resultado |
|---|---|---|
| 2026-11-04 | `main` en el commit `f89a294`; la API reporta la versión 0.1.0 | 19 de 19 comprobaciones exitosas, incluidos los endpoints de análisis. El barrido de salinidad con una semilla respondió en 2.3 s. |
| 2026-11-04 | Commit "docs: alinear terminología, versión 0.2.0 y cifras con la verificación integral", sobre `902a4d6`; la API reporta la versión 0.2.0 | Verificación local, con la API y el dashboard en el equipo: 22 de 22 comprobaciones exitosas, y recorrido de las cuatro vistas del dashboard con `streamlit.testing.v1.AppTest` (simulación, barrido, sensibilidad e incertidumbre) sin excepciones. La verificación contra los servicios publicados se completa después del despliegue de este commit. |
| 2026-11-04 | Cambios de la versión 0.3.0 (robustez de la respuesta, dimensionamiento y perfil de sitio), antes del commit; la API reporta la versión 0.3.0 | Verificación local, con la API y el dashboard en el equipo: 26 de 26 comprobaciones exitosas. La robustez de la respuesta con una semilla respondió en 1.9 s. La vista "Investigación y guía" se recorrió con `streamlit.testing.v1.AppTest` sin excepciones. La verificación contra los servicios publicados se completa después del despliegue. |
| 2026-11-05 | Dashboard de cinco vistas, Data Package y OpenAPI versionado sobre la API 0.3.0, antes del commit | Verificación local, con la API y el dashboard en el equipo: 26 de 26 comprobaciones exitosas. Recorrido de las cinco vistas con `streamlit.testing.v1.AppTest`, ejecutando la robustez, el barrido con el flujo calibrado máximo, la incertidumbre, la sensibilidad, el dimensionamiento y una simulación del explorador con perfil editado, sin excepciones. La verificación contra los servicios publicados se completa después del despliegue. |

Después de cada despliegue relevante se recomienda repetir el script y actualizar esta tabla.

## 5. Operación en el plan gratuito

- Render suspende los servicios gratuitos tras 15 minutos sin tráfico. La primera solicitud posterior tarda cerca de un minuto mientras el servicio se reactiva. Por eso la verificación de salud del dashboard espera hasta 75 s y muestra un aviso mientras tanto.
- Antes de una presentación, abrir la URL de salud de la API y el dashboard uno o dos minutos antes para reactivarlos.
- Render ofrece 750 horas mensuales de instancia gratuita por cuenta. Con la suspensión por inactividad, dos servicios de uso académico quedan dentro de ese límite.
- El sistema no guarda estado entre solicitudes, por lo que la suspensión no implica pérdida de datos.
- El dashboard guarda durante una hora la respuesta de cada simulación y de cada análisis, de modo que repetir una configuración no vuelve a llamar a la API.
- El barrido de salinidad con 5 semillas ejecuta 60 simulaciones; el dashboard espera hasta 120 s (`TIMEOUT_ANALISIS_SEG`).

## 6. Mantenimiento

### 6.1 Cambio de las URL públicas

Si Render cambia alguna de las URL (por ejemplo, al recrear un servicio), se deben actualizar:

- `README.md` (sección Enlaces) y `README_EN.md` (sección Links);
- el encabezado de [01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), [02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md), [03_Funcionamiento_General_AxiomaH.md](03_Funcionamiento_General_AxiomaH.md) y de este documento;
- los valores por defecto de `scripts/verificar_despliegue.py`;
- la variable `AXIOMA_API_URL` del servicio `axioma-h-dashboard` (**Environment** en el panel de Render), sin barra final.

### 6.2 Recreación del despliegue

El despliegue actual se creó desde el Blueprint del repositorio. Para recrearlo en otra cuenta de Render:

1. En https://render.com, elegir **New > Blueprint** y seleccionar el repositorio.
2. Confirmar los dos servicios de `render.yaml`.
3. Cuando Render lo solicite, definir `AXIOMA_API_URL` del dashboard con la URL pública de la nueva API.
4. Configurar **Auto-Deploy** en **After CI Checks Pass** en ambos servicios (sección 2.1).
5. Ejecutar el script de la sección 4.2 con `--api` y `--dashboard` apuntando a las nuevas URL:

```bash
python scripts/verificar_despliegue.py --api https://otra-api.onrender.com --dashboard https://otro-dashboard.onrender.com --timeout 120
```

### 6.3 Uso sin el despliegue

La aplicación no depende de Render. El backend y el dashboard se ejecutan en local sin conexión a internet, y los resultados de referencia se regeneran sin la API con `python scripts/generar_resultados_referencia.py`. Con `python scripts/generar_resultados_referencia.py --comprobar` se verifica, sin modificar `docs/datos/`, que los archivos publicados coinciden con el modelo actual; el script termina con código 0 si coinciden y con código 1 si alguno difiere o falta (ver `README.md`, sección Instalación y ejecución, y [datos/README.md](datos/README.md)). El mismo comando verifica también `docs/api/openapi.json`.

## 7. Integración con otros sistemas

El artefacto se puede reutilizar sin el dashboard: la API publica un contrato estable y los resultados de referencia se distribuyen como datos abiertos tipados. Nada de lo que sigue requiere dependencias adicionales a las de `requirements.txt`, salvo la validación opcional de la sección 7.3.

### 7.1 Consumo de la API

El contrato completo está en [api/openapi.json](api/openapi.json), generado desde `backend.main.app` por `scripts/generar_resultados_referencia.py` y verificado con `--comprobar`. La misma información se sirve en `GET /openapi.json` de la API desplegada. A partir de ese archivo, cualquier generador de clientes OpenAPI puede producir un cliente en otro lenguaje.

Ejemplos con `curl`, contra la API local (`http://127.0.0.1:8000`) o la desplegada (`https://axioma-h-api.onrender.com`):

```bash
# Salud del servicio
curl https://axioma-h-api.onrender.com/api/v1/health

# Perfiles de sitio de referencia
curl https://axioma-h-api.onrender.com/api/v1/sitios

# Simulación con un perfil de sitio y una eficacia del pulso propios
curl -X POST https://axioma-h-api.onrender.com/api/v1/simulacion/ejecutar \
  -H "Content-Type: application/json" \
  -d '{"escenario": "DIA_NORMAL", "humedad_ambiente_inicial_pct": 85, "tasa_salinizacion": "ALTA",
       "eficacia_maxima_pulso": 0.95,
       "sitio": {"nombre": "SITIO_EJEMPLO", "flujo_niebla_maximo_l_m2_h": 1.2, "temperatura_media_c": 24,
                 "amplitud_temperatura_c": 6, "amplitud_humedad_pct": 15}}'

# Dimensionamiento para 50 personas con el estándar de la OMS
curl -X POST https://axioma-h-api.onrender.com/api/v1/analisis/dimensionamiento \
  -H "Content-Type: application/json" \
  -d '{"personas": 50, "estandar": "OMS_20", "escenario": "DIA_NORMAL", "humedad_ambiente_inicial_pct": 85}'
```

Los valores del perfil del ejemplo son ilustrativos, no de un sitio real. Una solicitud que no supera la validación devuelve `422` con el detalle de cada campo. Una página web que consuma la API desde el navegador necesita que su dominio se agregue en `AXIOMA_CORS_ORIGINS` (sección 3); un programa de servidor, como un script de Python o un flujo de datos, no lo necesita.

### 7.2 Lectura de los datos abiertos con pandas

Los CSV de [datos/](datos/README.md) están en UTF-8, con punto decimal y celdas vacías para los valores sin datos. Se leen directamente desde el repositorio:

```python
import pandas as pd

base = "https://raw.githubusercontent.com/crd10lop/axioma-h-engine/main/docs/datos/"
robustez = pd.read_csv(base + "robustez_respuesta.csv")
cruces = robustez.drop_duplicates(["flujo_niebla_maximo_l_m2_h", "eficacia_maxima_pulso"])
print(cruces[["flujo_niebla_maximo_l_m2_h", "eficacia_maxima_pulso", "cruce_estado", "cruce_incrustacion_diaria_ohm"]])
```

El tipo y la descripción de cada columna están en `datapackage.json` y en [datos/README.md](datos/README.md), secciones 3 a 5.

### 7.3 Validación con el Data Package

[datos/datapackage.json](datos/datapackage.json) es un descriptor Frictionless Data Package con licencia MIT, la versión del servicio y, por cada CSV, el esquema de sus campos. Herramientas compatibles con esa especificación pueden validar los datos sin conocer el proyecto. Por ejemplo, con la herramienta de línea de comandos de Frictionless, que no forma parte de las dependencias del proyecto y se instala aparte:

```bash
frictionless validate docs/datos/datapackage.json
```

Dentro del proyecto, `tests/test_scripts.py` comprueba sin dependencias adicionales que el encabezado de cada CSV coincide con su esquema y que cada celda cumple el tipo declarado.

### 7.4 Envío de telemetría desde un sensor real

`POST /api/v1/nodo/evaluar` recibe un `TelemetryInput` y devuelve un `ControlDecision` ([02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md](02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md), sección 3.1). El simulador y el dashboard usan el mismo contrato que usaría un nodo físico, de modo que un sensor real no requiere cambios en la API: basta con que el microcontrolador o una pasarela envíe periódicamente la lectura en JSON y aplique la decisión.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/nodo/evaluar \
  -H "Content-Type: application/json" \
  -d '{"nodo_id": "NODO_04", "impedancia_ohms": 1650.5, "temperatura_celsius": 36.2, "reserva_calor_pct": 55.0,
       "humedad_relativa_pct": 42.0, "flujo_actual_ml_min": 14.5, "modo_operacion": "NEURO_SIMBOLICO"}'
```

La respuesta indica la acción (`accion_recomendada`), si se ordena un pulso (`pulso_termico_activo`, `temperatura_objetivo_c`, `duracion_pulso_seg`), el caudal como porcentaje del tope ecológico (`ajuste_caudal_pct`) y el motivo legible. El identificador del nodo debe estar entre `NODO_01` y `NODO_08`, y los valores fuera de rango se rechazan con `422`.

### 7.5 Rutas de integración propuestas para el Ciclo 3

Las siguientes rutas son una **propuesta** del equipo y no están implementadas:

- **Pasarela de campo.** Un servicio en el sitio que reciba la telemetría de los nodos por un protocolo de bajo consumo, la convierta en `TelemetryInput` y consulte la API, de modo que el control siga funcionando si se pierde la conexión con un servidor remoto.
- **Registro de mediciones.** Guardar cada lectura y cada decisión con su marca de tiempo, para estimar en campo la incrustación diaria (pendiente de la impedancia entre pulsos) y contrastar la hipótesis H1-Ciclo 3 ([04_Modelo_de_Control_y_Simulacion_AxiomaH.md](04_Modelo_de_Control_y_Simulacion_AxiomaH.md), sección 8.9).
- **Perfiles de sitio con fuente.** Publicar en `GET /api/v1/sitios` perfiles medidos en otros lugares, con la referencia de cada medición, cuando existan.
- **Gobernanza de los datos.** Definir con las comunidades quién accede a la telemetría y a los resultados antes de cualquier piloto ([01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md](01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md), sección 2.7).
