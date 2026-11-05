"""Endpoint de los perfiles de sitio de referencia para transferir el modelo."""

from fastapi import APIRouter

from backend.analisis import perfiles_sitio
from backend.schemas import PerfilSitio

router = APIRouter(prefix="/api/v1", tags=["Sitios"])


@router.get("/sitios")
def listar_sitios() -> list[PerfilSitio]:
    """Devuelve los perfiles de Cabo de la Vela con el flujo supuesto y con los extremos de la calibración."""
    return perfiles_sitio()
