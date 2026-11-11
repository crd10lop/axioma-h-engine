"""Pruebas del contenido de la vista de investigación y del recorrido guiado."""

import ast
from pathlib import Path

import pytest

from backend.schemas import AccionControl, EstadoCruce, EstadoNodo, ZonaIncrustacion
from frontend import config
from frontend import contenido

RUTA_APP = Path(__file__).resolve().parent.parent / "frontend" / "app.py"
VISTA_INVESTIGACION = "Investigación y guía"
VISTA_EVALUACION = "Evaluación manual de nodo"
VISTA_SIMULACION = "Simulación comparativa"
VISTA_RESPUESTA = "Respuesta a la pregunta"
VISTA_EXPLORADOR = "Explorador de hipótesis"
REGLA_03 = "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA"
REGLA_04 = "REGLA_04_PROTECCION_RESERVA_CRITICA"
REGLA_06 = "REGLA_06_SUPERVISION_HUMANA"
ACCESO_BASICO = "acceso básico al agua"
RUTA_DOCS = RUTA_APP.parent.parent / "docs"


def _constantes_app() -> dict[str, str]:
    """Lee las asignaciones de texto de nivel de módulo de app.py sin ejecutar Streamlit."""
    arbol = ast.parse(RUTA_APP.read_text(encoding="utf-8"))
    constantes = {}
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and isinstance(nodo.value, ast.Constant):
            for destino in nodo.targets:
                if isinstance(destino, ast.Name):
                    constantes[destino.id] = nodo.value.value
    return constantes


def _campo_regla(nombre: str, campo: str) -> str:
    """Devuelve un campo de la regla con el nombre indicado."""
    reglas = {regla["regla"]: regla for regla in contenido.REGLAS}
    return reglas[nombre][campo]


def _condicion(nombre: str) -> str:
    """Condición de la regla con el nombre indicado."""
    return _campo_regla(nombre, "condicion")


def _accion(nombre: str) -> str:
    """Acción de la regla con el nombre indicado."""
    return _campo_regla(nombre, "accion")


def _texto_reglas() -> str:
    """Une condiciones y acciones de todas las reglas en un solo texto."""
    nombres = [regla["regla"] for regla in contenido.REGLAS]
    return " ".join(f"{_condicion(nombre)} {_accion(nombre)}" for nombre in nombres)


# ---------------------------------------------------------------------------
# Textos
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "texto",
    [
        contenido.PREGUNTA_INVESTIGACION,
        contenido.VERSION_DIVULGATIVA,
        contenido.HIPOTESIS,
        contenido.MADUREZ,
        contenido.AVISO_EXPLORATORIO,
    ],
)
def test_textos_principales_no_vacios(texto):
    assert texto.strip()


def test_pregunta_y_version_divulgativa_son_preguntas():
    assert contenido.PREGUNTA_INVESTIGACION.endswith("?")
    assert contenido.VERSION_DIVULGATIVA.endswith("?")


@pytest.mark.parametrize(
    "lista",
    [contenido.RESPUESTA_PRELIMINAR, contenido.LIMITACIONES, contenido.REFERENCIAS],
)
def test_listas_de_texto_no_vacias(lista):
    assert lista
    for elemento in lista:
        assert elemento.strip()


def test_respuesta_preliminar_conserva_las_cifras():
    texto = " ".join(contenido.RESPUESTA_PRELIMINAR)
    for cifra in ("74 %", "99 %", "85.9 %", "88.9 %", "95.8 %", "63.2 %", "22.7 puntos"):
        assert cifra in texto


def test_respuesta_preliminar_incluye_la_robustez():
    texto = " ".join(contenido.RESPUESTA_PRELIMINAR)
    for cifra in ("73.3 %", "54 puntos", "1633 y 1839 Ohm", "61.5 % y 100 % en 108 puntos"):
        assert cifra in texto


def test_robustez_del_desgaste_coincide_con_docs_01():
    documento = (RUTA_DOCS / "01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md").read_text(encoding="utf-8")
    assert "lo reduce entre 61.5 % y 100 % en 108 puntos" in documento


def test_supuesto_de_fatiga_informa_el_efecto_observado():
    fatiga = contenido.SUPUESTOS_CLAVE[3]
    assert "108 puntos" in fatiga["efecto"]
    assert "de 73.9 % a 69.7 %" in fatiga["efecto"]
    assert "docs/04, sección 8.11" in fatiga["efecto"]
    assert "2.0 % por pulso, 100 veces la supuesta" in fatiga["medicion"]


def test_respuesta_preliminar_no_repite_la_tesis():
    assert len(contenido.RESPUESTA_PRELIMINAR) == 3
    assert "La respuesta es condicional" not in " ".join(contenido.RESPUESTA_PRELIMINAR)


FRASE_CRUCE_FLUJO_SUPUESTO = (
    "Con el flujo de niebla supuesto (6.0 L/m²/h), el control basado en reglas supera al temporizador "
    "desde una carga de 60 Ohm por L/m²."
)


@pytest.mark.parametrize(
    "fragmento",
    [
        FRASE_CRUCE_FLUJO_SUPUESTO,
        "Con otros flujos el cruce cambia de carga, pero ocurre con una incrustación diaria parecida (ver la tesis).",
    ],
)
def test_recuperacion_no_contradice_la_tesis(fragmento):
    assert fragmento in contenido.RESPUESTA_PRELIMINAR[1]


def test_recuperacion_coincide_con_docs_01():
    documento = (RUTA_DOCS / "01_Plan_y_Matriz_Operacionalizacion_Ciclo2_Axioma.md").read_text(encoding="utf-8")
    assert FRASE_CRUCE_FLUJO_SUPUESTO in documento


@pytest.mark.parametrize(
    "fragmento", ["H1-Ciclo 3", "incrustación diaria", "1633 y 1867 Ohm por día", "interpolación"]
)
def test_hipotesis_derivada(fragmento):
    assert fragmento in contenido.HIPOTESIS_DERIVADA


def test_conjeturas_completas():
    assert len(contenido.CONJETURAS) == 3
    for conjetura in contenido.CONJETURAS:
        assert set(conjetura) == set(contenido.COLUMNAS_CONJETURAS)
        for valor in conjetura.values():
            assert valor.strip()


@pytest.mark.parametrize(
    ("indice", "titulo"),
    [
        (0, "Conjetura 1: Control basado en reglas frente a control fijo"),
        (1, "Conjetura 2: Autorreparación por pulso resistivo (en la Matriz, pulso resonante)"),
    ],
)
def test_titulos_de_las_conjeturas(indice, titulo):
    assert contenido.CONJETURAS[indice]["nombre"] == titulo


def test_enunciado_de_la_conjetura_1_conserva_la_matriz():
    assert contenido.CONJETURAS[0]["enunciado"].startswith("El control neuro-simbólico local extiende")


@pytest.mark.parametrize("indice", [0, 1])
def test_conjeturas_1_y_2_aclaran_que_no_validada_no_es_refutada(indice):
    assert "no equivale a que quede refutada" in contenido.CONJETURAS[indice]["lectura"]


def test_supuestos_clave():
    valores = [supuesto["valor"] for supuesto in contenido.SUPUESTOS_CLAVE]
    assert "0.90" in valores
    assert any(valor.startswith("6.0 L/m²/h") for valor in valores)
    for supuesto in contenido.SUPUESTOS_CLAVE:
        assert set(supuesto) == set(contenido.COLUMNAS_SUPUESTOS)
        for texto in supuesto.values():
            assert texto.strip()


def test_supuesto_de_flujo_incluye_el_rango_calibrado():
    flujo = contenido.SUPUESTOS_CLAVE[1]
    assert "0.49 a 1.83 L/m²/h" in flujo["valor"]
    assert "Klemm et al. (2012)" in flujo["origen"]
    assert "calibración inversa" in flujo["medicion"]


def test_perspectivas_y_titulos():
    assert set(contenido.PERSPECTIVAS) == {"social", "etica", "cultural", "humana"}
    assert set(contenido.TITULOS_PERSPECTIVAS) == set(contenido.PERSPECTIVAS)
    for texto in contenido.PERSPECTIVAS.values():
        assert texto.strip()


def test_perspectiva_etica_declara_consulta_previa_no_realizada():
    assert "no se ha realizado" in contenido.PERSPECTIVAS["etica"]


def test_referencias_incluyen_repositorio_y_documento():
    texto = " ".join(contenido.REFERENCIAS)
    assert contenido.URL_REPOSITORIO in texto
    assert "docs/06_Referencias_y_Trazabilidad_AxiomaH.md" in texto


@pytest.mark.parametrize(
    "cita",
    [
        "Howard, G., Bartram, J.",
        "https://www.who.int/publications/i/item/9789240015241",
        "Sphere Association (2018)",
        "estándar 2.1 de abastecimiento de agua",
        "Klemm, O., Schemenauer, R. S., Lummerich, A., et al. (2012)",
        "https://doi.org/10.1007/s13280-012-0247-8",
    ],
)
def test_referencias_incluyen_oms_sphere_y_klemm(cita):
    assert cita in " ".join(contenido.REFERENCIAS)


@pytest.mark.parametrize("texto", ["impacto comunitario", "entre 7.5 y 12.7 personas", "20 L por persona"])
def test_perspectiva_social_describe_el_impacto_comunitario(texto):
    assert texto in contenido.PERSPECTIVAS["social"]


@pytest.mark.parametrize(
    "fragmento",
    [
        "El tope del 33 %",
        "El Axioma del Silencio",
        "no es un saber wayuu documentado",
        "debe validarse con las comunidades",
        "protocolo de co-creación en cuatro pasos",
        "traductores wayuu",
        "gobernanza del dispositivo y de los datos",
    ],
)
def test_perspectiva_cultural_documenta_origen_del_tope_y_protocolo(fragmento):
    assert fragmento in contenido.PERSPECTIVAS["cultural"]


@pytest.mark.parametrize(
    ("termino", "valor"),
    [(ACCESO_BASICO, "20 L"), (ACCESO_BASICO, "15 L"), ("rendimiento por m²", "de 3 a 10 L/m²")],
)
def test_glosario_usa_los_estandares_de_config(termino, valor):
    assert valor in contenido.GLOSARIO[termino]


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------
def test_reglas_en_orden_de_prioridad():
    prioridades = [regla["prioridad"] for regla in contenido.REGLAS]
    assert prioridades == [1, 2, 3, 4, 5, 6]
    for regla in contenido.REGLAS:
        assert set(regla) == set(contenido.COLUMNAS_REGLAS)


def test_reglas_usan_los_umbrales_de_config():
    assert config.UMBRAL_TEMPERATURA_CORTE_C == pytest.approx(45.0)
    assert config.UMBRAL_HUMEDAD_ECOLOGICA_PCT == pytest.approx(30.0)
    assert config.UMBRAL_RESERVA_CRITICA_PCT == pytest.approx(30.0)
    assert config.UMBRAL_IMPEDANCIA_OHMS == pytest.approx(1500.0)
    assert _condicion("REGLA_01_LIMITE_TERMICO_ABSOLUTO").endswith(">= 45 °C")
    assert _condicion("REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL").endswith("< 30 %")
    assert "Reserva < 30 %" in _condicion(REGLA_04)
    assert "impedancia > 1500 Ω" in _condicion(REGLA_04)
    assert "Impedancia > 1500 Ω" in _condicion(REGLA_03)
    assert "reserva >= 30 %" in _condicion(REGLA_03)


def test_reglas_describen_pulso_reserva_critica_y_tope():
    tope = "33 %"
    assert "90 s hacia 44 °C" in _accion(REGLA_03)
    assert "sin pulso" in _accion(REGLA_04)
    assert tope in _texto_reglas()
    assert tope in contenido.NOTA_REGLAS


def test_regla_06_en_tercera_posicion_tras_los_limites_de_seguridad():
    orden = [regla["regla"] for regla in contenido.REGLAS]
    assert orden == [
        "REGLA_01_LIMITE_TERMICO_ABSOLUTO",
        "REGLA_02_LIMITE_ECOLOGICO_TERRITORIAL",
        REGLA_06,
        REGLA_04,
        REGLA_03,
        "REGLA_05_OPERACION_NOMINAL",
    ]


@pytest.mark.parametrize("texto", ["Suspender: caudal 0 %", "Inhibir el pulso: caudal al 50 %", "sin pulso"])
def test_regla_06_describe_acciones_conservadoras(texto):
    assert texto in _accion(REGLA_06)


def test_regla_06_condicion_usa_el_umbral_de_impedancia():
    assert "impedancia > 1500 Ω" in _condicion(REGLA_06)


@pytest.mark.parametrize("texto", ["REGLA_06", "más conservador que el motor", "prevalecen"])
def test_nota_reglas_explica_la_supervision_humana(texto):
    assert texto in contenido.NOTA_REGLAS


@pytest.mark.parametrize("texto", ["REGLA_06", "Resuelto parcialmente", "la simulación no admite supervisión humana"])
def test_perspectiva_humana_describe_la_supervision(texto):
    assert texto in contenido.PERSPECTIVAS["humana"]


def test_glosario_supervision_humana_cita_los_limites():
    definicion = contenido.GLOSARIO["supervisión humana"]
    assert "45 °C" in definicion
    assert "nunca forzar extracción ni pulsos" in definicion


def test_constantes_de_pulso_y_tope():
    assert contenido.TEMPERATURA_OBJETIVO_PULSO_C == pytest.approx(44.0)
    assert contenido.DURACION_PULSO_SEG == 90
    assert contenido.FRACCION_MAXIMA_EXTRACCION_PCT == pytest.approx(33.0)


# ---------------------------------------------------------------------------
# Recorrido guiado
# ---------------------------------------------------------------------------
def test_vistas_en_orden():
    assert contenido.VISTAS == [
        VISTA_INVESTIGACION, VISTA_EVALUACION, VISTA_SIMULACION, VISTA_RESPUESTA, VISTA_EXPLORADOR
    ]


def test_vistas_coinciden_con_app():
    constantes = _constantes_app()
    assert constantes["VISTA_EVALUACION"] == contenido.VISTAS[1]
    assert constantes["VISTA_SIMULACION"] == contenido.VISTAS[2]


@pytest.mark.parametrize(
    ("vista", "esperada"),
    [
        (VISTA_INVESTIGACION, "1. Investigación y guía"),
        (VISTA_EVALUACION, "2. Evaluación manual de nodo"),
        (VISTA_SIMULACION, "3. Simulación comparativa"),
        (VISTA_RESPUESTA, "4. Respuesta a la pregunta"),
        (VISTA_EXPLORADOR, "5. Explorador de hipótesis"),
    ],
)
def test_etiqueta_vista(vista, esperada):
    assert contenido.etiqueta_vista(vista) == esperada


@pytest.mark.parametrize(
    ("vista", "esperada"),
    [
        (VISTA_INVESTIGACION, VISTA_EVALUACION),
        (VISTA_EVALUACION, VISTA_SIMULACION),
        (VISTA_SIMULACION, VISTA_RESPUESTA),
        (VISTA_RESPUESTA, VISTA_EXPLORADOR),
    ],
)
def test_siguiente_vista(vista, esperada):
    assert contenido.siguiente_vista(vista) == esperada


def test_siguiente_vista_de_la_ultima_es_none():
    assert contenido.siguiente_vista(VISTA_EXPLORADOR) is None


def test_aviso_exploratorio_cita_la_decision_d5():
    assert "decisión D5" in contenido.AVISO_EXPLORATORIO


@pytest.mark.parametrize("funcion", [contenido.etiqueta_vista, contenido.siguiente_vista])
def test_vista_desconocida_lanza_error(funcion):
    with pytest.raises(ValueError, match="Vista desconocida"):
        funcion("Vista inexistente")


# ---------------------------------------------------------------------------
# Glosario y utilidades
# ---------------------------------------------------------------------------
def test_glosario_ordenado_alfabeticamente():
    terminos = [termino for termino, _ in contenido.glosario_ordenado()]
    assert terminos == sorted(contenido.GLOSARIO, key=str.casefold)
    assert terminos[0] == ACCESO_BASICO
    assert terminos[-1] == "tope ecológico"


def test_glosario_contiene_los_terminos_requeridos():
    requeridos = {
        ACCESO_BASICO,
        "rendimiento por m²",
        "impedancia",
        "conductancia relativa",
        "pulso resistivo",
        "tope ecológico",
        "humedad relativa",
        "integridad de la membrana",
        "control basado en reglas",
        "control neuro-simbólico",
        "temporizador fijo",
        "supervisión humana",
        "semilla",
    }
    assert set(contenido.GLOSARIO) == requeridos
    for definicion in contenido.GLOSARIO.values():
        assert definicion.strip()


def test_lista_markdown():
    resultado = contenido.lista_markdown(["uno", "dos"])
    assert resultado == "- uno\n- dos"


def test_lista_markdown_vacia():
    resultado = contenido.lista_markdown([])
    assert resultado == ""


@pytest.mark.parametrize(
    "texto",
    [
        " ".join(contenido.RESPUESTA_PRELIMINAR),
        contenido.CONJETURAS[2]["lectura"],
        contenido.PERSPECTIVAS["social"],
    ],
)
def test_resultados_se_atribuyen_al_control_basado_en_reglas(texto):
    assert "control basado en reglas" in texto


def test_glosario_aclara_la_equivalencia_con_el_modo_neuro_simbolico():
    assert "NEURO_SIMBOLICO" in contenido.GLOSARIO["control neuro-simbólico"]
    assert "primera etapa de una arquitectura neuro-simbólica" in contenido.GLOSARIO["control basado en reglas"]


def test_pregunta_de_investigacion_conserva_la_formulacion_del_equipo():
    assert contenido.PREGUNTA_INVESTIGACION.startswith(
        "¿En qué medida un sistema de control neuro-simbólico, evaluado mediante simulación"
    )


# ---------------------------------------------------------------------------
# Tesis, etiquetas llanas, supuestos y guía por disciplina
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fragmento",
    ["73.3 % y 100 %", "61.5 % y 100 %", "incrustación diaria", "1633 a 1867 Ohm por día", "1171 y 2365"],
)
def test_tesis_usa_las_cifras_de_docs_04(fragmento):
    assert fragmento in contenido.TESIS


@pytest.mark.parametrize("enumerado", [EstadoNodo, AccionControl, EstadoCruce, ZonaIncrustacion])
def test_etiquetas_llanas_cubren_los_enumerados_de_la_api(enumerado):
    for valor in enumerado:
        assert contenido.ETIQUETAS_LLANAS[valor.value].strip()


def test_etiquetas_llanas_cubren_las_reglas():
    for regla in contenido.REGLAS:
        assert regla["regla"] in contenido.ETIQUETAS_LLANAS


@pytest.mark.parametrize("origen", ["SUPUESTO", "CALIBRADO_MAX", "CALIBRADO_MIN"])
def test_etiquetas_llanas_cubren_los_origenes_del_flujo(origen):
    assert origen in contenido.ETIQUETAS_LLANAS


def test_supuestos_clave_cubren_los_cinco_parametros():
    parametros = [supuesto["parametro"] for supuesto in contenido.SUPUESTOS_CLAVE]
    assert parametros == [
        "Eficacia máxima del pulso",
        "Flujo máximo de niebla",
        "Carga salina por litro",
        "Degradación por fatiga del pulso",
        "Tope ecológico de extracción",
    ]


def test_supuestos_clave_citan_su_origen_y_su_efecto():
    for supuesto in contenido.SUPUESTOS_CLAVE:
        assert "docs/0" in supuesto["origen"]
        assert "docs/04" in supuesto["efecto"]


def test_guia_por_disciplina():
    assert list(contenido.GUIA_DISCIPLINAS) == [
        "Hidrología e ingeniería", "Salud pública", "Ecología", "Ciencias sociales"
    ]
    for guia in contenido.GUIA_DISCIPLINAS.values():
        assert set(guia) == set(contenido.COLUMNAS_GUIA)
        assert guia["pregunta"].startswith("¿")


def test_partes_de_la_respuesta():
    titulos = [parte["titulo"] for parte in contenido.PARTES_RESPUESTA.values()]
    assert [titulo[:2] for titulo in titulos] == ["a)", "b)", "c)", "d)"]
    for parte in contenido.PARTES_RESPUESTA.values():
        assert parte["frase"].startswith("Esta parte responde") or parte["frase"].startswith("Esta parte traduce")


def test_intro_del_explorador_cita_la_decision_d5():
    assert "decisión D5" in contenido.INTRO_EXPLORADOR


def test_guia_por_disciplina_coincide_con_docs_03():
    documento = (RUTA_DOCS / "03_Funcionamiento_General_AxiomaH.md").read_text(encoding="utf-8")
    for guia in contenido.GUIA_DISCIPLINAS.values():
        assert guia["donde"] in documento
        assert guia["pregunta"] in documento


# ---------------------------------------------------------------------------
# Nombre visible único del modo de control
# ---------------------------------------------------------------------------
def test_nota_del_codigo_del_modo():
    assert contenido.NOTA_CODIGO_MODO == "En la API este modo se identifica como NEURO_SIMBOLICO."


def test_app_muestra_la_nota_del_codigo_una_sola_vez():
    assert RUTA_APP.read_text(encoding="utf-8").count("contenido.NOTA_CODIGO_MODO") == 1


def test_app_no_muestra_el_nombre_neuro_simbolico_del_modo():
    assert "neuro-simbólico" not in RUTA_APP.read_text(encoding="utf-8").casefold()


def test_klemm_coincide_con_docs_06():
    documento = (RUTA_DOCS / "06_Referencias_y_Trazabilidad_AxiomaH.md").read_text(encoding="utf-8")
    assert "https://doi.org/10.1007/s13280-012-0247-8" in documento
    assert "Fog as a fresh-water resource: overview and perspectives" in documento


# ---------------------------------------------------------------------------
# Públicos, lectura breve y tablero de veredictos
# ---------------------------------------------------------------------------
def test_publicos_tiene_tres_filas_con_las_tres_claves():
    assert len(contenido.PUBLICOS) == 3
    claves_esperadas = {"publico", "que_leer", "donde"}
    assert set(contenido.COLUMNAS_PUBLICOS) == claves_esperadas
    for fila in contenido.PUBLICOS:
        assert set(fila) == claves_esperadas
        for valor in fila.values():
            assert valor.strip()
    assert [fila["publico"] for fila in contenido.PUBLICOS] == [
        "Comunidad",
        "Evaluador no técnico",
        "Investigador",
    ]


def test_lectura_breve_y_partes_tienen_las_claves_esperadas():
    assert set(contenido.LECTURA_BREVE) == {"pregunta", "hallazgo", "certeza", "comunidad", "falta"}
    assert set(contenido.TITULOS_LECTURA_BREVE) == set(contenido.LECTURA_BREVE)
    assert set(contenido.LECTURA_BREVE_PARTES) == set(contenido.PARTES_RESPUESTA)
    for texto in list(contenido.LECTURA_BREVE.values()) + list(contenido.LECTURA_BREVE_PARTES.values()):
        assert texto.strip()


@pytest.mark.parametrize("termino_prohibido", ["Ohm", "NEURO_SIMBOLICO", "incrustación"])
def test_lectura_breve_no_usa_unidades_tecnicas_ni_codigos(termino_prohibido):
    textos = list(contenido.LECTURA_BREVE.values()) + list(contenido.LECTURA_BREVE_PARTES.values())
    for texto in textos:
        assert termino_prohibido.casefold() not in texto.casefold()


@pytest.mark.parametrize(
    "cifra", ["61 %", "100 y 333", "1000 L", "3 a 4", "11 a 13", "no es toda el agua de la comunidad", "complemento"]
)
def test_lectura_breve_conserva_las_cifras_clave(cifra):
    unido = " ".join(list(contenido.LECTURA_BREVE.values()) + list(contenido.LECTURA_BREVE_PARTES.values()))
    assert cifra in unido


def test_lectura_breve_incluye_temporizador_con_salvaguardas():
    hallazgo = contenido.LECTURA_BREVE["hallazgo"]
    assert "mismos límites de temperatura y de humedad" in hallazgo
    assert "40.6 % a 90.9 %" in hallazgo
    assert "en la sequía desaparece" in hallazgo


def test_veredictos_cubren_las_cuatro_partes_de_la_respuesta():
    assert [item["parte"] for item in contenido.VEREDICTOS] == list(contenido.PARTES_RESPUESTA)
    for item in contenido.VEREDICTOS:
        assert set(item) == {"parte", "veredicto", "cifra", "falta_medir"}
        for valor in item.values():
            assert valor.strip()


def test_cifras_de_veredictos_aparecen_en_docs_04():
    ruta_04 = Path(__file__).resolve().parent.parent / "docs" / "04_Modelo_de_Control_y_Simulacion_AxiomaH.md"
    documento = ruta_04.read_text(encoding="utf-8").casefold()
    for item in contenido.VEREDICTOS:
        assert item["cifra"].casefold() in documento
    assert contenido.VEREDICTOS[3]["veredicto"].casefold() in documento
