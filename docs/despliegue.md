# Despliegue de Axioma-H Engine

Este documento describe cómo esta publicada la API y el dashboard en servicios gratuitos para la demostración del Ciclo 2. El repositorio ya incluye la configuración necesaria (`render.yaml`).


## 1. Variables de entorno

| Variable | Servicio | Valor por defecto | Uso |
|---|---|---|---|
| `AXIOMA_API_URL` | Dashboard | `http://127.0.0.1:8000` | URL pública de la API, sin barra final. |
| `AXIOMA_TIMEOUT_SALUD_SEG` | Dashboard | `75` | Espera máxima de la verificación de salud, en segundos. |
| `AXIOMA_CORS_ORIGINS` | API | Vacío | Orígenes adicionales permitidos, separados por comas. Solo es necesario si una página web en el navegador consume la API directamente. El dashboard Streamlit llama a la API desde el servidor y no lo requiere. |
| `PYTHON_VERSION` | Ambos (Render) | `3.12.10` en `render.yaml` | Versión de Python de la construcción. |

## 2. Verificación

1. Abrir `https://<api>.onrender.com/api/v1/health`. Debe responder `"estado": "SALUDABLE"`.
2. Abrir `https://<api>.onrender.com/docs` y ejecutar `POST /api/v1/simulacion/ejecutar` con el payload de ejemplo.
3. Abrir el dashboard. La barra lateral debe mostrar **Estado: SALUDABLE** y la URL de la API.
4. En **Simulación comparativa**, ejecutar un escenario y confirmar que aparecen las tarjetas de la comparativa, incluidas **Recuperación tras pulso** y **Degradación acumulada**.

## 3. Limitaciones del plan gratuito

- Render suspende los servicios gratuitos tras 15 minutos sin tráfico. La primera solicitud posterior tarda cerca de un minuto mientras el servicio se reactiva. Por eso la verificación de salud del dashboard espera hasta 75 s y muestra un aviso mientras tanto.
- Antes de una presentación, abrir la URL de salud de la API y el dashboard uno o dos minutos antes para reactivarlos.
- Render ofrece 750 horas mensuales de instancia gratuita por cuenta. Con la suspensión por inactividad, dos servicios de uso académico quedan dentro de ese límite.
- El sistema no guarda estado entre solicitudes, por lo que la suspensión no implica pérdida de datos.

## 4. URL públicas del despliegue

La aplicación está desplegada en Render con el Blueprint de `render.yaml` (opción A):

| Servicio | URL | Verificación |
|---|---|---|
| Dashboard | https://axioma-h-dashboard.onrender.com | La barra lateral muestra **Estado: SALUDABLE**. |
| API, documentación interactiva | https://axioma-h-api.onrender.com/docs | Carga la interfaz Swagger con los endpoints `/api/v1/nodo/evaluar` y `/api/v1/simulacion/ejecutar`. |
| API, salud | https://axioma-h-api.onrender.com/api/v1/health | Responde código 200 con `"estado": "SALUDABLE"`. |

Si Render cambia alguna de estas URL (por ejemplo, al recrear un servicio), se debe actualizar en `README.md` (sección Enlaces), en el encabezado de `docs/01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md`, `docs/02_Especificacion_Tecnica_y_PRD_API_AxiomaH.md` y `docs/funcionamiento.md`, y en la variable `AXIOMA_API_URL` del servicio `axioma-h-dashboard` (**Environment** en el panel de Render), sin barra final.

## 5. Integración continua

El workflow `.github/workflows/ci.yml` se ejecuta en GitHub Actions en cada push a `main` y en cada pull request. Instala `requirements-dev.txt`, ejecuta la suite de `pytest` con cobertura de líneas y ramas (`coverage.xml`) y envía el resultado a SonarQube Cloud.

1. En SonarQube Cloud, el proyecto `crd10lop_axioma-h-engine` (organización `cristian-diez`) tiene desactivado el análisis automático (**Administration > Analysis Method**). El análisis se hace desde CI, que es la única forma de incluir la cobertura. La configuración está en `sonar-project.properties`.
2. En GitHub, el secreto `SONAR_TOKEN` (**Settings > Secrets and variables > Actions**) contiene el token generado en SonarQube Cloud. Si el secreto no existe, el workflow ejecuta las pruebas y omite el análisis.
3. En el panel de Render, cada servicio debe mostrar **Auto-Deploy** en **After CI Checks Pass** (**Settings > Build & Deploy**). Así, un push a `main` solo se despliega cuando el workflow CI termina en verde.

## 6. Verificación automatizada del despliegue

El script `scripts/verificar_despliegue.py` ejecuta contra los servicios publicados las comprobaciones de la sección 6 y algunas adicionales. Solo requiere las dependencias de `requirements.txt` y no forma parte de la suite de `pytest`, porque depende de la red.

```bash
python scripts/verificar_despliegue.py
```

Argumentos opcionales:

| Argumento | Valor por defecto | Uso |
|---|---|---|
| `--api` | Variable `AXIOMA_API_URL` o `https://axioma-h-api.onrender.com` | URL base de la API. |
| `--dashboard` | `https://axioma-h-dashboard.onrender.com` | URL base del dashboard. |
| `--timeout` | `90` | Espera máxima por solicitud, en segundos. Cubre la reactivación de los servicios suspendidos del plan gratuito. |

Comprobaciones realizadas:

1. `GET /api/v1/health` responde 200 con `"estado": "SALUDABLE"`.
2. `GET /docs` y `GET /openapi.json` responden 200 y el esquema publica `/api/v1/nodo/evaluar` y `/api/v1/simulacion/ejecutar`.
3. `POST /api/v1/nodo/evaluar` aplica cada regla del motor (REGLA_01 a REGLA_05) con la acción y el estado esperados, respetando el orden de prioridad.
4. `POST /api/v1/nodo/evaluar` rechaza una telemetría inválida con código 422.
5. `POST /api/v1/simulacion/ejecutar` responde para el ejemplo del esquema y para cada escenario, con comparativa entre modos, conjeturas validadas y serie temporal no vacía.
6. `GET /_stcore/health` del dashboard responde 200 con el cuerpo `ok`.
7. `GET /` del dashboard responde 200.
8. Las funciones de `frontend/cliente_api.py` funcionan contra la URL pública de la API.

El script imprime una tabla con el resultado, la duración y el detalle de cada comprobación, y termina con código 0 si todas pasan o 1 si alguna falla. Ejemplo contra un despliegue alternativo:

```bash
python scripts/verificar_despliegue.py --api https://otra-api.onrender.com --dashboard https://otro-dashboard.onrender.com --timeout 120
```
