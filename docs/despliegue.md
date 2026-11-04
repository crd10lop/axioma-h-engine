# Despliegue de Axioma-H Engine

Este documento describe cómo publicar la API y el dashboard en servicios gratuitos para la demostración del Ciclo 2. El repositorio ya incluye la configuración necesaria (`render.yaml`).

## 1. Opciones

| Opción | API | Dashboard | Cuándo usarla |
|---|---|---|---|
| A (recomendada) | Render | Render | Despliegue más rápido: un solo Blueprint crea los dos servicios. |
| B | Render | Streamlit Community Cloud | Si se prefiere que el dashboard tenga una URL `*.streamlit.app`. |

Ambas opciones son gratuitas y se despliegan desde el repositorio de GitHub. Cada `git push` a `main` vuelve a desplegar los servicios.

## 2. Antes de desplegar

1. Ejecutar las pruebas localmente: `pytest -q`.
2. Subir los cambios a GitHub: `git push origin main`.

## 3. Opción A: Render con Blueprint

1. Crear una cuenta en https://render.com con la cuenta de GitHub.
2. En el panel, elegir **New > Blueprint** y seleccionar el repositorio `axioma-h-engine`.
3. Render lee `render.yaml` y propone dos servicios web gratuitos:
   - `axioma-h-api`: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`, con verificación de salud en `/api/v1/health`.
   - `axioma-h-dashboard`: `streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`.
4. Render solicita el valor de `AXIOMA_API_URL` para el dashboard. Ingresar la URL pública de la API, por ejemplo `https://axioma-h-api.onrender.com`. Si Render asigna otro nombre a la API (porque el nombre ya está en uso), corregir el valor en **axioma-h-dashboard > Environment** y volver a desplegar.
5. Confirmar con **Apply**. La primera construcción tarda entre 3 y 6 minutos.

## 4. Opción B: dashboard en Streamlit Community Cloud

1. Desplegar solo la API en Render: **New > Web Service**, seleccionar el repositorio y configurar:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/api/v1/health`
   - Variable `PYTHON_VERSION`: `3.12.10`
2. Entrar a https://share.streamlit.io con la cuenta de GitHub y elegir **Create app**.
3. Seleccionar el repositorio, la rama `main` y el archivo principal `frontend/app.py`. En **Advanced settings**, elegir Python 3.12.
4. En **Secrets**, definir la URL de la API como clave de nivel raíz:

   ```toml
   AXIOMA_API_URL = "https://axioma-h-api.onrender.com"
   ```

   Streamlit Community Cloud expone las claves de nivel raíz como variables de entorno, que es como las lee `frontend/config.py`.
5. Desplegar con **Deploy**.

## 5. Variables de entorno

| Variable | Servicio | Valor por defecto | Uso |
|---|---|---|---|
| `AXIOMA_API_URL` | Dashboard | `http://127.0.0.1:8000` | URL pública de la API, sin barra final. |
| `AXIOMA_TIMEOUT_SALUD_SEG` | Dashboard | `75` | Espera máxima de la verificación de salud, en segundos. |
| `AXIOMA_CORS_ORIGINS` | API | Vacío | Orígenes adicionales permitidos, separados por comas. Solo es necesario si una página web en el navegador consume la API directamente. El dashboard Streamlit llama a la API desde el servidor y no lo requiere. |
| `PYTHON_VERSION` | Ambos (Render) | `3.12.10` en `render.yaml` | Versión de Python de la construcción. |

## 6. Verificación

1. Abrir `https://<api>.onrender.com/api/v1/health`. Debe responder `"estado": "SALUDABLE"`.
2. Abrir `https://<api>.onrender.com/docs` y ejecutar `POST /api/v1/simulacion/ejecutar` con el payload de ejemplo.
3. Abrir el dashboard. La barra lateral debe mostrar **Estado: SALUDABLE** y la URL de la API.
4. En **Simulación comparativa**, ejecutar un escenario y confirmar que aparecen las tarjetas de la comparativa, incluidas **Recuperación tras pulso** y **Degradación acumulada**.

## 7. Limitaciones del plan gratuito

- Render suspende los servicios gratuitos tras 15 minutos sin tráfico. La primera solicitud posterior tarda cerca de un minuto mientras el servicio se reactiva. Por eso la verificación de salud del dashboard espera hasta 75 s y muestra un aviso mientras tanto.
- Antes de una presentación, abrir la URL de salud de la API y el dashboard uno o dos minutos antes para reactivarlos.
- Render ofrece 750 horas mensuales de instancia gratuita por cuenta. Con la suspensión por inactividad, dos servicios de uso académico quedan dentro de ese límite.
- El sistema no guarda estado entre solicitudes, por lo que la suspensión no implica pérdida de datos.
