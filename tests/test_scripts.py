"""Pruebas de las funciones con lógica propia de los scripts de scripts/.

scripts/ no es un paquete, por lo que cada script se carga desde su ruta con
importlib.util.spec_from_file_location.
"""

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

CARPETA_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
URL_API = "https://axioma-h-api.onrender.com"


def _cargar_script(nombre: str):
    """Carga un script de scripts/ como módulo y lo registra en sys.modules."""
    spec = importlib.util.spec_from_file_location(f"scripts_{nombre}", CARPETA_SCRIPTS / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


generador = _cargar_script("generar_resultados_referencia")
verificador = _cargar_script("verificar_despliegue")


@pytest.fixture
def carpetas_iguales(tmp_path):
    """Dos carpetas con los mismos archivos de referencia y contenido idéntico."""
    generada = tmp_path / "generada"
    referencia = tmp_path / "referencia"
    for carpeta in (generada, referencia):
        carpeta.mkdir()
        for nombre in generador.ARCHIVOS:
            (carpeta / nombre).write_bytes(f"contenido de {nombre}\n".encode())
    return generada, referencia


def test_generador_rechaza_argumento_salida():
    with pytest.raises(SystemExit) as excepcion:
        generador.main(["--salida", "x"])
    assert excepcion.value.code == 2


def test_comparar_carpetas_iguales_no_reporta_diferencias(carpetas_iguales):
    generada, referencia = carpetas_iguales
    assert generador.comparar_con_referencia(generada, referencia) == []


def test_comparar_reporta_archivo_distinto(carpetas_iguales):
    generada, referencia = carpetas_iguales
    (generada / generador.ARCHIVO_BARRIDO).write_bytes(b"otro contenido\n")
    assert generador.comparar_con_referencia(generada, referencia) == [generador.ARCHIVO_BARRIDO]


def test_comparar_reporta_archivo_faltante(carpetas_iguales):
    generada, referencia = carpetas_iguales
    (referencia / generador.ARCHIVO_JSON).unlink()
    assert generador.comparar_con_referencia(generada, referencia) == [generador.ARCHIVO_JSON]


def test_generar_coincide_con_docs_datos(tmp_path):
    generador.generar(tmp_path)
    assert generador.comparar_con_referencia(tmp_path) == []


def test_url_base_acepta_https_y_quita_barra_final():
    assert verificador._url_base(f"{URL_API}/") == URL_API


@pytest.mark.parametrize("valor", ["ftp://x", "file:///etc/passwd", "axioma-h-api"])
def test_url_base_rechaza_esquema_o_host_invalido(valor):
    with pytest.raises(argparse.ArgumentTypeError):
        verificador._url_base(valor)


def test_filas_robustez_una_fila_por_combinacion_y_punto():
    cruce = {"estado": "SIN_DATOS", "incrustacion_diaria_ohm": None, "carga_salina_ohm_l_m2": None}
    robustez = {
        "combinaciones": [
            {
                "flujo_niebla_maximo_l_m2_h": flujo,
                "eficacia_maxima_pulso": 0.9,
                "barrido": {"cruce": cruce, "puntos": [{"carga_salina_ohm_l_m2": 20.0}, {"carga_salina_ohm_l_m2": 40.0}]},
            }
            for flujo in (6.0, 1.83)
        ]
    }
    filas = generador.filas_robustez(robustez)
    assert len(filas) == 4
    assert filas[2]["flujo_niebla_maximo_l_m2_h"] == pytest.approx(1.83)
    assert filas[1]["carga_salina_ohm_l_m2"] == pytest.approx(40.0)
    assert filas[0]["cruce_incrustacion_diaria_ohm"] == ""
    assert filas[0][generador.CAMPO_HUMEDAD] == pytest.approx(generador.HUMEDAD_BARRIDO_PCT)
