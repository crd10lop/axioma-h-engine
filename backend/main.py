"""Punto de entrada de la API del motor Axioma-H.

Expone el servidor FastAPI base con los endpoints de estado general y de
monitoreo de salud del servicio. Las reglas neuro-simbólicas y los endpoints
de evaluación y simulación se incorporarán en iteraciones posteriores.
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

NOMBRE_SERVICIO = "Axioma-H Engine"
VERSION_SERVICIO = "0.1.0"
DESCRIPCION_SERVICIO = (
    "Motor de control neuro-simbólico para la captación pasiva de agua "
    "atmosférica."
)

# Orígenes permitidos para desarrollo local (Streamlit y la propia API).
# En producción esta lista debe restringirse a los dominios autorizados.
ORIGENES_PERMITIDOS = [
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

HORA_ARRANQUE = datetime.now(timezone.utc)

app = FastAPI(
    title=NOMBRE_SERVICIO,
    description=DESCRIPCION_SERVICIO,
    version=VERSION_SERVICIO,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EstadoMotor(BaseModel):
    """Estado general del motor expuesto en la raíz de la API."""

    servicio: str = Field(..., description="Nombre del servicio.")
    version: str = Field(..., description="Versión desplegada del servicio.")
    estado: str = Field(..., description="Estado operativo del motor.")
    descripcion: str = Field(..., description="Descripción breve del motor.")
    documentacion: str = Field(..., description="Ruta de la documentación interactiva.")


class EstadoSalud(BaseModel):
    """Resultado de la verificación de salud del servicio."""

    estado: str = Field(..., description="Resultado de la verificación de salud.")
    servicio: str = Field(..., description="Nombre del servicio.")
    version: str = Field(..., description="Versión desplegada del servicio.")
    timestamp: str = Field(..., description="Fecha y hora de la consulta en ISO 8601 (UTC).")
    tiempo_actividad_seg: float = Field(
        ..., description="Segundos transcurridos desde el arranque del servicio."
    )


@app.get("/", response_model=EstadoMotor, tags=["General"])
def obtener_estado_motor() -> EstadoMotor:
    """Devuelve el estado general del motor y la ruta de su documentación."""
    return EstadoMotor(
        servicio=NOMBRE_SERVICIO,
        version=VERSION_SERVICIO,
        estado="OPERATIVO",
        descripcion=DESCRIPCION_SERVICIO,
        documentacion="/docs",
    )


@app.get("/api/v1/health", response_model=EstadoSalud, tags=["Monitoreo"])
def verificar_salud() -> EstadoSalud:
    """Informa la salud del servicio junto con su tiempo de actividad."""
    ahora = datetime.now(timezone.utc)
    return EstadoSalud(
        estado="SALUDABLE",
        servicio=NOMBRE_SERVICIO,
        version=VERSION_SERVICIO,
        timestamp=ahora.isoformat(),
        tiempo_actividad_seg=round((ahora - HORA_ARRANQUE).total_seconds(), 2),
    )
