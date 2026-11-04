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
| Dashboard | https://axioma-h-dashboard.onrender.com | La barra lateral muestra **Estado: SALUDABLE** y el recorrido de cuatro vistas. |
| API, documentación interactiva | https://axioma-h-api.onrender.com/docs | Interfaz Swagger con los endpoints de evaluación, simulación y análisis de robustez. |
| API, salud | https://axioma-h-api.onrender.com/api/v1/health | Código 200 con `"estado": "SALUDABLE"`. |
| API, esquema OpenAPI | https://axioma-h-api.onrender.com/openapi.json | Publica las seis rutas de la API. |

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

Comprobaciones realizadas (19 en total):

1. `GET /api/v1/health` responde 200 con `"estado": "SALUDABLE"`.
2. `GET /docs` y `GET /openapi.json` responden 200 y el esquema publica `/api/v1/nodo/evaluar`, `/api/v1/simulacion/ejecutar`, `/api/v1/analisis/barrido-salinidad` y `/api/v1/analisis/sensibilidad`.
3. `POST /api/v1/nodo/evaluar` aplica cada regla del motor (REGLA_01 a REGLA_05) con la acción y el estado esperados, respetando el orden de prioridad.
4. `POST /api/v1/nodo/evaluar` rechaza una telemetría inválida con código 422.
5. `POST /api/v1/simulacion/ejecutar` responde para el ejemplo del esquema y para cada escenario, con comparativa entre modos (incluido `modo_temporizador_tope_ecologico`), conjeturas validadas, `causas_no_validacion` como lista en cada conjetura y serie temporal no vacía.
6. `POST /api/v1/analisis/barrido-salinidad` responde, con una sola semilla para no exceder el tiempo de espera, seis puntos ordenados por carga salina; y `POST /api/v1/analisis/sensibilidad` responde un punto por cada valor de eficacia solicitado, con el estado de la Conjetura 1.
7. `GET /_stcore/health` del dashboard responde 200 con el cuerpo `ok`.
8. `GET /` del dashboard responde 200.
9. Las funciones de `frontend/cliente_api.py` funcionan contra la URL pública de la API.

El script imprime una tabla con el resultado, la duración y el detalle de cada comprobación, y termina con código 0 si todas pasan o 1 si alguna falla.

### 4.3 Última verificación registrada

| Fecha | Estado del repositorio | Resultado |
|---|---|---|
| 2026-11-04 | `main` en el commit `f89a294`; la API reporta la versión 0.1.0 | 19 de 19 comprobaciones exitosas, incluidos los endpoints de análisis. El barrido de salinidad con una semilla respondió en 2.3 s. |

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

La aplicación no depende de Render. El backend y el dashboard se ejecutan en local sin conexión a internet, y los resultados de referencia se regeneran sin la API con `python scripts/generar_resultados_referencia.py` (ver `README.md`, sección Uso local sin conexión, y [datos/README.md](datos/README.md)).
