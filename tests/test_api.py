"""Pruebas de los endpoints de la API."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

cliente = TestClient(app)

RUTA_EVALUAR = "/api/v1/nodo/evaluar"
RUTA_SIMULACION = "/api/v1/simulacion/ejecutar"

PAYLOAD_TELEMETRIA_PRD = {
    "nodo_id": "NODO_04",
    "impedancia_ohms": 1650.5,
    "temperatura_celsius": 36.2,
    "reserva_calor_pct": 55.0,
    "humedad_relativa_pct": 42.0,
    "flujo_actual_ml_min": 14.5,
    "modo_operacion": "NEURO_SIMBOLICO",
}

PAYLOAD_SIMULACION_PRD = {
    "duracion_horas": 24,
    "escenario": "TORMENTA_DE_SAL_Y_CALOR_EXTREMO",
    "humedad_ambiente_inicial_pct": 45.0,
    "tasa_salinizacion": "ALTA",
}

CAMPOS_RESULTADO_MODO = {
    "litros_totales_agua",
    "pulsos_termicos_ejecutados",
    "consumo_energia_wh",
    "integridad_membrana_final_pct",
    "violaciones_ecologicas",
    "recuperacion_caudal_promedio_pct",
    "degradacion_acumulada_pct",
}
CONJETURAS = {"conjetura_1_eficiencia", "conjetura_2_autorreparacion", "conjetura_3_saber_territorial"}
MODOS_COMPARATIVA = {"modo_neuro_simbolico", "modo_temporizador_fijo", "modo_temporizador_tope_ecologico"}


def test_raiz():
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "OPERATIVO"
    assert datos["documentacion"] == "/docs"


def test_salud():
    respuesta = cliente.get("/api/v1/health")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "SALUDABLE"
    assert datos["tiempo_actividad_seg"] >= 0


def test_evaluar_nodo_valido():
    respuesta = cliente.post(RUTA_EVALUAR, json=PAYLOAD_TELEMETRIA_PRD)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["regla_activada"] == "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA"
    assert datos["temperatura_objetivo_c"] == pytest.approx(44.0)
    assert datos["pulso_termico_activo"] is True
    assert set(datos["metricas_conjeturas"]) == {
        "eficiencia_energetica_pct",
        "recuperacion_hidraulica_pct",
        "preservacion_ecologica_ok",
    }


def test_evaluar_nodo_invalido_devuelve_422():
    invalidos = [
        {**PAYLOAD_TELEMETRIA_PRD, "nodo_id": "NODO_09"},
        {**PAYLOAD_TELEMETRIA_PRD, "impedancia_ohms": 0},
        {**PAYLOAD_TELEMETRIA_PRD, "humedad_relativa_pct": 120},
        {**PAYLOAD_TELEMETRIA_PRD, "modo_operacion": "MANUAL"},
        {key: value for key, value in PAYLOAD_TELEMETRIA_PRD.items() if key != "temperatura_celsius"},
    ]
    for payload in invalidos:
        assert cliente.post(RUTA_EVALUAR, json=payload).status_code == 422


def _evaluar_con_anulacion(anulacion: str, **cambios) -> dict:
    """Evalúa el payload del PRD con la anulación manual y los campos indicados."""
    respuesta = cliente.post(RUTA_EVALUAR, json={**PAYLOAD_TELEMETRIA_PRD, **cambios, "anulacion_manual": anulacion})
    assert respuesta.status_code == 200
    return respuesta.json()


@pytest.mark.parametrize(
    ("anulacion", "regla", "accion", "caudal"),
    [
        ("NINGUNA", "REGLA_03_DESPRENDIMIENTO_SAL_POR_IMPEDANCIA", "APLICAR_PULSO_RESISTIVO", 80.0),
        ("SUSPENDER_EXTRACCION", "REGLA_06_SUPERVISION_HUMANA", "SUSPENSION_MANUAL", 0.0),
        ("INHIBIR_PULSO", "REGLA_06_SUPERVISION_HUMANA", "REDUCIR_CAUDAL_SIN_PULSO", 50.0),
    ],
)
def test_evaluar_nodo_con_anulacion_manual(anulacion, regla, accion, caudal):
    datos = _evaluar_con_anulacion(anulacion)
    assert datos["regla_activada"] == regla
    assert datos["accion_recomendada"] == accion
    assert datos["ajuste_caudal_pct"] == pytest.approx(caudal)


def test_supervision_humana_se_reporta_como_estado():
    datos = _evaluar_con_anulacion("INHIBIR_PULSO")
    assert datos["estado_nodo"] == "SUPERVISION_HUMANA"
    assert datos["pulso_termico_activo"] is False


def test_corte_termico_prevalece_sobre_la_suspension_manual():
    datos = _evaluar_con_anulacion("SUSPENDER_EXTRACCION", temperatura_celsius=46.0)
    assert datos["regla_activada"] == "REGLA_01_LIMITE_TERMICO_ABSOLUTO"


def test_anulacion_manual_invalida_devuelve_422():
    payload = {**PAYLOAD_TELEMETRIA_PRD, "anulacion_manual": "FORZAR_PULSO"}
    assert cliente.post(RUTA_EVALUAR, json=payload).status_code == 422


def test_ejecutar_simulacion_payload_prd():
    respuesta = cliente.post(RUTA_SIMULACION, json=PAYLOAD_SIMULACION_PRD)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert set(datos["comparativa"]) == MODOS_COMPARATIVA
    assert set(datos["conjeturas_validadas"]) == {
        "conjetura_1_eficiencia",
        "conjetura_2_autorreparacion",
        "conjetura_3_saber_territorial",
    }
    assert all(isinstance(v, bool) for v in datos["conjeturas_validadas"].values())
    assert len(datos["series_temporales"]) == 24 * 60 // 5
    assert datos["bitacora"]


def test_simulacion_incluye_impacto_comunitario():
    respuesta = cliente.post(RUTA_SIMULACION, json=PAYLOAD_SIMULACION_PRD)
    impacto = respuesta.json()["impacto_comunitario"]
    neuro = impacto["modo_neuro_simbolico"]
    assert set(impacto) == MODOS_COMPARATIVA
    assert set(neuro) == {
        "litros_dia_red",
        "rendimiento_l_m2_dia",
        "personas_supervivencia",
        "personas_acceso_basico",
        "area_m2_por_persona_basico_literatura_min",
        "area_m2_por_persona_basico_literatura_max",
    }
    assert neuro["litros_dia_red"] == pytest.approx(81.65, abs=0.01)


def test_simulacion_payload_prd_estructura_completa():
    """Ejecuta el payload exacto del PRD y valida la estructura, no los valores ilustrativos."""
    respuesta = cliente.post(RUTA_SIMULACION, json=PAYLOAD_SIMULACION_PRD)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert set(datos) == {
        "comparativa",
        "conjeturas_validadas",
        "detalle_verificacion",
        "series_temporales",
        "bitacora",
        "impacto_comunitario",
        "parametros_usados",
    }

    for modo in MODOS_COMPARATIVA:
        resultado_modo = datos["comparativa"][modo]
        assert set(resultado_modo) == CAMPOS_RESULTADO_MODO
        assert isinstance(resultado_modo["pulsos_termicos_ejecutados"], int)
        assert isinstance(resultado_modo["violaciones_ecologicas"], int)
        for campo in ("litros_totales_agua", "consumo_energia_wh", "integridad_membrana_final_pct"):
            assert isinstance(resultado_modo[campo], (int, float))

    assert set(datos["conjeturas_validadas"]) == CONJETURAS
    assert set(datos["detalle_verificacion"]) == CONJETURAS
    for nombre, verificacion in datos["detalle_verificacion"].items():
        assert verificacion["validada"] == datos["conjeturas_validadas"][nombre]
        assert verificacion["indicadores"]
        for indicador in verificacion["indicadores"].values():
            assert set(indicador) == {"valor", "umbral", "operador", "cumple"}
            assert isinstance(indicador["cumple"], bool)
        assert isinstance(verificacion["causas_no_validacion"], list)
    informativos = datos["detalle_verificacion"]["conjetura_2_autorreparacion"]["indicadores_informativos"]
    assert set(informativos) == {
        "pulsos_regenerados",
        "pulsos_totales",
        "tiempo_desprendimiento_t95_promedio_seg",
        "impedancia_promedio_tras_pulso_ohms",
    }
    assert isinstance(informativos["pulsos_regenerados"], int)
    assert isinstance(informativos["pulsos_totales"], int)

    # 24 h con paso de 5 min.
    assert len(datos["series_temporales"]) == 288
    assert set(datos["series_temporales"][0]) == {
        "minuto",
        "humedad_relativa_pct",
        "temperatura_c",
        "impedancia_promedio_neuro_ohms",
        "impedancia_promedio_temporizador_ohms",
        "litros_acumulados_neuro",
        "litros_acumulados_temporizador",
        "energia_acumulada_neuro_wh",
        "energia_acumulada_temporizador_wh",
        "integridad_promedio_neuro_pct",
        "integridad_promedio_temporizador_pct",
    }
    assert datos["bitacora"]
    assert set(datos["bitacora"][0]) == {"minuto", "nodo_id", "regla_activada", "motivo"}


def test_ejecutar_simulacion_escenario_invalido_devuelve_422():
    payload = {**PAYLOAD_SIMULACION_PRD, "escenario": "HURACAN"}
    assert cliente.post(RUTA_SIMULACION, json=payload).status_code == 422


# ---------------------------------------------------------------------------
# Análisis de robustez
# ---------------------------------------------------------------------------
RUTA_BARRIDO = "/api/v1/analisis/barrido-salinidad"
RUTA_SENSIBILIDAD = "/api/v1/analisis/sensibilidad"
RUTA_INCERTIDUMBRE = "/api/v1/analisis/incertidumbre"
PAYLOAD_INCERTIDUMBRE = {
    "escenario": "INCRUSTACION_SALINA_RAPIDA",
    "humedad_ambiente_inicial_pct": 85.0,
    "tasa_salinizacion": "ALTA",
    "n_muestras": 5,
}
PAYLOAD_SENSIBILIDAD = {
    "escenario": "DIA_NORMAL",
    "humedad_ambiente_inicial_pct": 85.0,
    "tasa_salinizacion": "ALTA",
    "parametro": "EFICACIA_MAXIMA_PULSO",
    "valores": [0.90, 0.94],
}


def test_barrido_salinidad():
    respuesta = cliente.post(RUTA_BARRIDO, json={"semillas": [42]})
    assert respuesta.status_code == 200
    puntos = respuesta.json()["puntos"]
    cargas = [punto["carga_salina_ohm_l_m2"] for punto in puntos]
    assert cargas == sorted(cargas)
    assert len(puntos) == 6
    assert puntos[0]["recuperacion_neuro_media"] == pytest.approx(88.85, abs=0.01)


def test_sensibilidad():
    respuesta = cliente.post(RUTA_SENSIBILIDAD, json=PAYLOAD_SENSIBILIDAD)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["parametro"] == "EFICACIA_MAXIMA_PULSO"
    estados = [punto["conjeturas_validadas"]["conjetura_1_eficiencia"] for punto in datos["puntos"]]
    assert estados == [False, True]


@pytest.mark.parametrize("semillas", [[1, 1], [1, 2, 3, 4, 5, 6], []])
def test_barrido_rechaza_semillas_invalidas(semillas):
    assert cliente.post(RUTA_BARRIDO, json={"semillas": semillas}).status_code == 422


@pytest.mark.parametrize("valor", [0.0, 1.2])
def test_sensibilidad_rechaza_eficacia_fuera_de_rango(valor):
    payload = {**PAYLOAD_SENSIBILIDAD, "valores": [valor]}
    assert cliente.post(RUTA_SENSIBILIDAD, json=payload).status_code == 422


def test_endpoints_de_analisis_publicados_en_openapi():
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert RUTA_BARRIDO in rutas
    assert RUTA_SENSIBILIDAD in rutas
    assert RUTA_INCERTIDUMBRE in rutas


def test_incertidumbre():
    respuesta = cliente.post(RUTA_INCERTIDUMBRE, json=PAYLOAD_INCERTIDUMBRE)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert len(datos["muestras"]) == 5
    assert 0.0 <= datos["probabilidad_c1"] <= 1.0
    assert set(datos["recuperacion"]) == {"p5", "p50", "p95", "n_validos"}


@pytest.mark.parametrize(
    "cambios",
    [
        {"n_muestras": 2},
        {"eficacia_min": 0.95, "eficacia_max": 0.90},
        {"flujo_min": 0.0},
        {"flujo_max": 25.0},
        {"eficacia_max": 1.5},
    ],
)
def test_incertidumbre_rechaza_configuracion_invalida(cambios):
    assert cliente.post(RUTA_INCERTIDUMBRE, json={**PAYLOAD_INCERTIDUMBRE, **cambios}).status_code == 422


# ---------------------------------------------------------------------------
# Transferencia a otro sitio, robustez de la respuesta y dimensionamiento
# ---------------------------------------------------------------------------
RUTA_ROBUSTEZ = "/api/v1/analisis/robustez-respuesta"
RUTA_DIMENSIONAMIENTO = "/api/v1/analisis/dimensionamiento"
RUTA_SITIOS = "/api/v1/sitios"
SITIO_EJEMPLO = {
    "nombre": "SITIO_PRUEBA_01",
    "flujo_niebla_maximo_l_m2_h": 1.83,
    "temperatura_media_c": 28.0,
    "amplitud_temperatura_c": 5.0,
    "amplitud_humedad_pct": 12.0,
}
PAYLOAD_DIMENSIONAMIENTO = {
    "personas": 50,
    "estandar": "OMS_20",
    "escenario": "DIA_NORMAL",
    "humedad_ambiente_inicial_pct": 85.0,
}


def test_simulacion_con_sitio_y_eficacia():
    payload = {**PAYLOAD_SIMULACION_PRD, "sitio": SITIO_EJEMPLO, "eficacia_maxima_pulso": 0.95}
    respuesta = cliente.post(RUTA_SIMULACION, json=payload)
    assert respuesta.status_code == 200
    usados = respuesta.json()["parametros_usados"]
    assert usados["nombre_sitio"] == "SITIO_PRUEBA_01"
    assert usados["flujo_niebla_maximo_l_m2_h"] == pytest.approx(1.83)
    assert usados["eficacia_maxima_pulso"] == pytest.approx(0.95)
    assert usados["temperatura_media_c"] == pytest.approx(28.0)


def test_simulacion_sin_sitio_informa_los_parametros_por_defecto():
    usados = cliente.post(RUTA_SIMULACION, json=PAYLOAD_SIMULACION_PRD).json()["parametros_usados"]
    assert usados["nombre_sitio"] == "CABO_DE_LA_VELA"
    assert usados["flujo_niebla_maximo_l_m2_h"] == pytest.approx(6.0)
    assert usados["eficacia_maxima_pulso"] == pytest.approx(0.90)


@pytest.mark.parametrize(
    "cambios",
    [
        {"nombre": "sitio en minúsculas"},
        {"nombre": "A" * 41},
        {"nombre": ""},
        {"flujo_niebla_maximo_l_m2_h": 0.0},
        {"flujo_niebla_maximo_l_m2_h": 20.5},
        {"temperatura_media_c": 46.0},
        {"amplitud_temperatura_c": -1.0},
        {"amplitud_humedad_pct": 31.0},
    ],
)
def test_simulacion_rechaza_perfil_de_sitio_invalido(cambios):
    payload = {**PAYLOAD_SIMULACION_PRD, "sitio": {**SITIO_EJEMPLO, **cambios}}
    assert cliente.post(RUTA_SIMULACION, json=payload).status_code == 422


@pytest.mark.parametrize("eficacia", [0.0, 1.2])
def test_simulacion_rechaza_eficacia_fuera_de_rango(eficacia):
    payload = {**PAYLOAD_SIMULACION_PRD, "eficacia_maxima_pulso": eficacia}
    assert cliente.post(RUTA_SIMULACION, json=payload).status_code == 422


def test_barrido_con_flujo_y_eficacia():
    payload = {"semillas": [42], "duracion_horas": 6, "flujo_niebla_maximo_l_m2_h": 1.83, "eficacia_maxima_pulso": 0.8}
    datos = cliente.post(RUTA_BARRIDO, json=payload).json()
    assert datos["flujo_niebla_maximo_l_m2_h"] == pytest.approx(1.83)
    assert datos["eficacia_maxima_pulso"] == pytest.approx(0.8)
    assert set(datos["cruce"]) == {"estado", "incrustacion_diaria_ohm", "carga_salina_ohm_l_m2"}


@pytest.mark.parametrize("cambios", [{"flujo_niebla_maximo_l_m2_h": 0.0}, {"eficacia_maxima_pulso": 1.5}])
def test_barrido_rechaza_parametros_fuera_de_rango(cambios):
    assert cliente.post(RUTA_BARRIDO, json={"semillas": [42], **cambios}).status_code == 422


def test_robustez_respuesta():
    respuesta = cliente.post(RUTA_ROBUSTEZ, json={"semillas": [42]})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert len(datos["combinaciones"]) == 9
    assert datos["combinaciones_con_cruce"] == 6
    assert len(datos["combinaciones"][0]["barrido"]["puntos"]) == 6


@pytest.mark.parametrize(
    "cambios",
    [{"duracion_horas": 12}, {"duracion_horas": 80}, {"semillas": [1, 2, 3, 4]}, {"semillas": [7, 7]}, {"numero_nodos": 9}],
)
def test_robustez_rechaza_configuracion_invalida(cambios):
    assert cliente.post(RUTA_ROBUSTEZ, json=cambios).status_code == 422


def test_dimensionamiento():
    respuesta = cliente.post(RUTA_DIMENSIONAMIENTO, json=PAYLOAD_DIMENSIONAMIENTO)
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["consumo_l_persona_dia"] == pytest.approx(20.0)
    assert [d["origen_flujo"] for d in datos["dimensiones"]] == ["SUPUESTO", "CALIBRADO_MAX", "CALIBRADO_MIN"]
    assert datos["dimensiones"][0]["nodos_requeridos"] == 32


@pytest.mark.parametrize(
    "cambios",
    [
        {"personas": 0},
        {"personas": 1001},
        {"estandar": "OMS_50"},
        {"escenario": "HURACAN"},
        {"humedad_ambiente_inicial_pct": 101.0},
    ],
)
def test_dimensionamiento_rechaza_configuracion_invalida(cambios):
    payload = {**PAYLOAD_DIMENSIONAMIENTO, **cambios}
    assert cliente.post(RUTA_DIMENSIONAMIENTO, json=payload).status_code == 422


def test_dimensionamiento_exige_personas():
    payload = {clave: valor for clave, valor in PAYLOAD_DIMENSIONAMIENTO.items() if clave != "personas"}
    assert cliente.post(RUTA_DIMENSIONAMIENTO, json=payload).status_code == 422


def test_sitios():
    respuesta = cliente.get(RUTA_SITIOS)
    assert respuesta.status_code == 200
    perfiles = respuesta.json()
    assert [perfil["nombre"] for perfil in perfiles] == [
        "CABO_DE_LA_VELA",
        "CABO_DE_LA_VELA_CALIBRADO_MAX",
        "CABO_DE_LA_VELA_CALIBRADO_MIN",
    ]
    assert set(perfiles[0]) == set(SITIO_EJEMPLO)


def test_perfil_de_sitios_se_acepta_en_la_simulacion():
    perfil = cliente.get(RUTA_SITIOS).json()[1]
    payload = {**PAYLOAD_SIMULACION_PRD, "duracion_horas": 2, "sitio": perfil}
    usados = cliente.post(RUTA_SIMULACION, json=payload).json()["parametros_usados"]
    assert usados["flujo_niebla_maximo_l_m2_h"] == pytest.approx(1.83)


def test_endpoints_nuevos_publicados_en_openapi():
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert RUTA_ROBUSTEZ in rutas
    assert RUTA_DIMENSIONAMIENTO in rutas
    assert RUTA_SITIOS in rutas


def test_incertidumbre_informa_la_ventaja_en_recuperacion():
    datos = cliente.post(RUTA_INCERTIDUMBRE, json=PAYLOAD_INCERTIDUMBRE).json()
    assert 0.0 <= datos["probabilidad_ventaja_recuperacion"] <= 1.0
    assert set(datos["ventaja_recuperacion"]) == {"p5", "p50", "p95", "n_validos"}
    assert "ventaja_recuperacion_pts" in datos["muestras"][0]


def test_version_del_servicio():
    assert cliente.get("/api/v1/health").json()["version"] == "0.3.0"
