"""Pruebas de las funciones con lógica propia de los scripts de scripts/.

scripts/ no es un paquete, por lo que cada script se carga desde su ruta con
importlib.util.spec_from_file_location.
"""

import argparse
import csv
import importlib.util
import json
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
    carpeta_api = tmp_path / "api"
    generador.generar(tmp_path, carpeta_api)
    assert generador.comparar_con_referencia(tmp_path) == []
    assert generador.comparar_con_referencia(carpeta_api, generador.CARPETA_API, generador.ARCHIVOS_API) == []


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
    assert filas[0]["cruce_separacion_ohm"] == ""
    assert filas[0][generador.CAMPO_HUMEDAD] == pytest.approx(generador.HUMEDAD_BARRIDO_PCT)


def test_filas_robustez_incluye_la_separacion_del_cruce():
    cruce = {
        "estado": "INTERPOLADO",
        "incrustacion_diaria_ohm": 1789.1,
        "carga_salina_ohm_l_m2": 55.9,
        "incrustacion_inferior_ohm": 1290.5,
        "incrustacion_superior_ohm": 1918.1,
        "separacion_ohm": 627.6,
    }
    robustez = {
        "combinaciones": [
            {"flujo_niebla_maximo_l_m2_h": 6.0, "eficacia_maxima_pulso": 0.9, "barrido": {"cruce": cruce, "puntos": [{}]}}
        ]
    }
    fila = generador.filas_robustez(robustez)[0]
    assert fila["cruce_incrustacion_inferior_ohm"] == pytest.approx(1290.5)
    assert fila["cruce_incrustacion_superior_ohm"] == pytest.approx(1918.1)
    assert fila["cruce_separacion_ohm"] == pytest.approx(627.6)


def test_filas_robustez_desgaste_una_fila_por_combinacion():
    robustez_desgaste = {
        "combinaciones": [
            {
                "flujo_niebla_maximo_l_m2_h": 6.0,
                "fatiga_por_pulso_pct": fatiga,
                "degradacion_termica_pct_por_c_min": 0.05,
                "reduccion_desgaste_min_pct": None,
                "reduccion_desgaste_max_pct": 99.0,
                "puntos_con_menor_desgaste": 6,
                "puntos_totales": 6,
            }
            for fatiga in (0.01, 0.02)
        ],
        "combinaciones_con_menor_desgaste_en_todos_los_puntos": 2,
    }
    filas = generador.filas_robustez_desgaste(robustez_desgaste)
    assert len(filas) == 2
    assert filas[1]["fatiga_por_pulso_pct"] == pytest.approx(0.02)
    assert filas[0]["reduccion_desgaste_min_pct"] == ""
    assert list(filas[0])[-1] == generador.CAMPO_HUMEDAD


def test_filas_impacto_entornos_una_fila_por_entorno():
    impacto = {
        "personas": 50,
        "entornos": [
            {
                "origen_flujo": origen,
                "flujo_niebla_maximo_l_m2_h": 6.0,
                "escenario": "DIA_NORMAL",
                "tasa_salinizacion": "BAJA",
                "carga_salina_ohm_l_m2": 20.0,
                "rendimiento_neuro_l_m2_dia": 31.83,
                "incrustacion_diaria_ohm": 636.6,
                "zona_incrustacion": "BAJO_TRANSICION",
                "ventaja_recuperacion_pts": None,
                "reduccion_desgaste_pct": 89.2,
                "area_colector_m2": 31.42,
                "nodos_requeridos": 32,
                "litros_mes_por_nodo": 954.9,
                "nodos_equivalentes_entrega": 2,
            }
            for origen in ("SUPUESTO", "CALIBRADO_MAX")
        ],
    }
    filas = generador.filas_impacto_entornos(impacto)
    assert len(filas) == 2
    assert filas[1]["origen_flujo"] == "CALIBRADO_MAX"
    assert filas[0]["ventaja_recuperacion_pts"] == ""
    assert filas[0]["personas"] == 50
    assert filas[0]["estandar"] == "OMS_20"


# ---------------------------------------------------------------------------
# Interoperabilidad: diccionario de campos, Data Package y OpenAPI
# ---------------------------------------------------------------------------
CARPETA_DATOS = CARPETA_SCRIPTS.parent / "docs" / "datos"
VALORES_LOGICOS = {"True", "False"}
CODIFICACION = "utf-8"


def _es_valido(valor: str, tipo: str) -> bool:
    """Indica si una celda de CSV es válida para el tipo Frictionless; la celda vacía es un valor ausente."""
    if valor == "":
        return True
    if tipo == generador.TIPO_LOGICO:
        return valor in VALORES_LOGICOS
    if tipo == generador.TIPO_ENTERO:
        return valor.lstrip("-").isdigit()
    if tipo == generador.TIPO_NUMERO:
        try:
            float(valor)
        except ValueError:
            return False
        return True
    return True


def test_campo_csv_con_clave_exacta():
    campo = generador.campo_csv("carga_salina_ohm_l_m2")
    assert campo == {
        "name": "carga_salina_ohm_l_m2",
        "type": generador.TIPO_NUMERO,
        "description": "Aumento de impedancia por litro captado por m².",
    }


@pytest.mark.parametrize(
    ("columna", "modo"),
    [("neuro_pulsos", "neuro"), ("temporizador_pulsos", "temporizador"), ("temporizador_tope_pulsos", "temporizador_tope")],
)
def test_campo_csv_con_prefijo_de_modo(columna, modo):
    campo = generador.campo_csv(columna)
    assert campo["type"] == generador.TIPO_ENTERO
    assert campo["description"].startswith(generador.NOMBRES_MODO[modo])


@pytest.mark.parametrize("columna", ["columna_nueva", "neuro_desconocido"])
def test_campo_csv_desconocido_lanza_error(columna):
    with pytest.raises(ValueError, match="DICCIONARIO_CAMPOS"):
        generador.campo_csv(columna)


def test_descriptor_datapackage():
    descriptor = generador.descriptor_datapackage({"barrido_salinidad.csv": ["escenario", "n_semillas"]})
    assert descriptor["licenses"][0]["name"] == "MIT"
    assert descriptor["version"] == generador.VERSION_SERVICIO
    recurso = descriptor["resources"][0]
    assert recurso["name"] == "barrido_salinidad"
    assert recurso["encoding"] == CODIFICACION
    assert [campo["name"] for campo in recurso["schema"]["fields"]] == ["escenario", "n_semillas"]


def test_escribir_json_usa_utf8_y_fin_de_linea_lf(tmp_path):
    ruta = tmp_path / "prueba.json"
    generador.escribir_json(ruta, {"texto": "año"})
    contenido = ruta.read_bytes()
    assert contenido.endswith(b"}\n")
    assert b"\r\n" not in contenido
    assert "año".encode(CODIFICACION) in contenido


def test_datapackage_describe_las_columnas_de_cada_csv():
    descriptor = json.loads((CARPETA_DATOS / generador.ARCHIVO_DATAPACKAGE).read_text(encoding=CODIFICACION))
    for recurso in descriptor["resources"]:
        with (CARPETA_DATOS / recurso["path"]).open(encoding=CODIFICACION) as archivo:
            encabezado = next(csv.reader(archivo))
        assert [campo["name"] for campo in recurso["schema"]["fields"]] == encabezado


def test_celdas_de_los_csv_cumplen_los_tipos_del_datapackage():
    descriptor = json.loads((CARPETA_DATOS / generador.ARCHIVO_DATAPACKAGE).read_text(encoding=CODIFICACION))
    for recurso in descriptor["resources"]:
        tipos = {campo["name"]: campo["type"] for campo in recurso["schema"]["fields"]}
        with (CARPETA_DATOS / recurso["path"]).open(encoding=CODIFICACION) as archivo:
            invalidas = [
                (columna, valor)
                for fila in csv.DictReader(archivo)
                for columna, valor in fila.items()
                if not _es_valido(valor, tipos[columna])
            ]
        assert invalidas == []


@pytest.mark.parametrize(("valor", "tipo"), [("x", "number"), ("1.5", "integer"), ("si", "boolean")])
def test_validacion_de_tipos_rechaza_valores_invalidos(valor, tipo):
    assert _es_valido(valor, tipo) is False


def test_readme_de_datos_reproduce_el_diccionario():
    readme = (CARPETA_DATOS / "README.md").read_text(encoding=CODIFICACION)
    faltantes = [clave for clave, (_, descripcion) in generador.DICCIONARIO_CAMPOS.items() if descripcion not in readme]
    assert faltantes == []


def test_openapi_publicado_coincide_con_la_aplicacion():
    publicado = json.loads((generador.CARPETA_API / generador.ARCHIVO_OPENAPI).read_text(encoding=CODIFICACION))
    assert publicado == generador.app.openapi()
    assert "/api/v1/sitios" in publicado["paths"]
