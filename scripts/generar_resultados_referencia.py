"""Genera los resultados de referencia del modelo como datos abiertos, sin red.

Importa el backend directamente (no llama a la API) y ejecuta:

- los cinco escenarios con humedad inicial de 45 % y 85 % (24 h, tasa ALTA,
  8 nodos, paso de 5 min, semilla 42);
- el barrido de salinidad con humedad inicial de 85 % y semillas 1 a 5;
- la robustez de la respuesta: el barrido con 3 flujos de niebla por 3
  eficacias del pulso, humedad inicial de 85 % y semilla 42.

Escribe en docs/datos/:

- resultados_escenarios.csv: una fila por escenario y humedad inicial;
- barrido_salinidad.csv: una fila por combinación de escenario y tasa;
- robustez_respuesta.csv: una fila por combinación de flujo y eficacia y por
  punto del barrido;
- resultados_completos.json: comparativa, conjeturas y detalle de verificación
  de cada corrida, el barrido completo, el resumen de la robustez y las
  condiciones de ejecución.

La salida es determinista: ejecutar el script dos veces produce archivos
idénticos. Uso, desde la raíz del proyecto:

    python scripts/generar_resultados_referencia.py

Con --comprobar, el script genera los archivos en un directorio temporal, los
compara byte a byte con los de docs/datos/ y termina con código 1 si alguno
difiere o falta, sin modificar docs/datos/:

    python scripts/generar_resultados_referencia.py --comprobar
"""

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path

# Se incluye la raíz del proyecto para importar el paquete backend.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from backend.analisis import ejecutar_barrido, ejecutar_robustez  # noqa: E402
from backend.main import VERSION_SERVICIO  # noqa: E402
from backend.schemas import (  # noqa: E402
    BarridoConfig,
    Escenario,
    RobustezConfig,
    SimulationConfig,
    TasaSalinizacion,
)
from backend.simulador import ejecutar_simulacion  # noqa: E402

CARPETA_POR_DEFECTO = RAIZ_PROYECTO / "docs" / "datos"
ARCHIVO_ESCENARIOS = "resultados_escenarios.csv"
ARCHIVO_BARRIDO = "barrido_salinidad.csv"
ARCHIVO_JSON = "resultados_completos.json"
ARCHIVO_ROBUSTEZ = "robustez_respuesta.csv"
ARCHIVOS = (ARCHIVO_ESCENARIOS, ARCHIVO_BARRIDO, ARCHIVO_JSON, ARCHIVO_ROBUSTEZ)

HUMEDADES_PCT = (45.0, 85.0)
DURACION_HORAS = 24
TASA = TasaSalinizacion.ALTA
SEMILLA = 42
SEMILLAS_BARRIDO = [1, 2, 3, 4, 5]
HUMEDAD_BARRIDO_PCT = 85.0
SEMILLAS_ROBUSTEZ = [SEMILLA]
CAMPO_HUMEDAD = "humedad_inicial_pct"

# Prefijo de columna de cada modo en resultados_escenarios.csv.
MODOS = {
    "neuro": "modo_neuro_simbolico",
    "temporizador": "modo_temporizador_fijo",
    "temporizador_tope": "modo_temporizador_tope_ecologico",
}
# Campo de ResultadoModo y sufijo de la columna.
CAMPOS_MODO = {
    "litros_totales_agua": "litros",
    "pulsos_termicos_ejecutados": "pulsos",
    "consumo_energia_wh": "energia_wh",
    "integridad_membrana_final_pct": "integridad_final_pct",
    "degradacion_acumulada_pct": "degradacion_pct",
    "violaciones_ecologicas": "violaciones",
    "recuperacion_caudal_promedio_pct": "recuperacion_pct",
}
CLAVE_IMPACTO = "impacto_comunitario"
# Campos de ImpactoComunitario que se agregan al final de cada fila, por modo.
CAMPOS_IMPACTO = ("personas_acceso_basico", "rendimiento_l_m2_dia")
CONJETURAS = {
    "c1": "conjetura_1_eficiencia",
    "c2": "conjetura_2_autorreparacion",
    "c3": "conjetura_3_saber_territorial",
}
# Columna, conjetura e indicador que decide la validación.
INDICADORES = [
    ("c1_recuperacion_pct", "c1", "recuperacion_caudal_promedio_pct"),
    ("c1_ahorro_energia_pct", "c1", "ahorro_energia_pulsos_pct"),
    ("c2_tiempo_regeneracion_s", "c2", "tiempo_regeneracion_promedio_seg"),
    ("c2_perdida_termica_pct", "c2", "perdida_integridad_termica_pct"),
    ("c3_violaciones", "c3", "violaciones_ecologicas"),
    ("c3_rendimiento_nocturno_l_m2_noche", "c3", "rendimiento_nocturno_l_m2_noche"),
]
# Columna, conjetura e indicador informativo.
INFORMATIVOS = [
    ("c1_reduccion_degradacion_pct", "c1", "reduccion_degradacion_pct"),
    ("c2_pulsos_regenerados", "c2", "pulsos_regenerados"),
    ("c2_pulsos_totales", "c2", "pulsos_totales"),
    ("c2_t95_promedio_s", "c2", "tiempo_desprendimiento_t95_promedio_seg"),
    ("c2_impedancia_tras_pulso_ohm", "c2", "impedancia_promedio_tras_pulso_ohms"),
    ("c3_rendimiento_temporizador_l_m2_noche", "c3", "rendimiento_nocturno_temporizador_l_m2_noche"),
]


def _vacio_si_nulo(valor):
    """Representa un valor nulo como celda vacía en el CSV."""
    return "" if valor is None else valor


def fila_escenario(escenario: str, humedad: float, resultado: dict) -> dict:
    """Aplana una respuesta de simulación en una fila de resultados_escenarios.csv."""
    fila = {"escenario": escenario, CAMPO_HUMEDAD: humedad}
    comparativa = resultado["comparativa"]
    for prefijo, clave_modo in MODOS.items():
        for campo, sufijo in CAMPOS_MODO.items():
            fila[f"{prefijo}_{sufijo}"] = _vacio_si_nulo(comparativa[clave_modo][campo])
    detalle = resultado["detalle_verificacion"]
    for corta, clave in CONJETURAS.items():
        fila[f"{corta}_validada"] = resultado["conjeturas_validadas"][clave]
    for columna, corta, indicador in INDICADORES:
        fila[columna] = _vacio_si_nulo(detalle[CONJETURAS[corta]]["indicadores"][indicador]["valor"])
    for columna, corta, indicador in INFORMATIVOS:
        fila[columna] = _vacio_si_nulo(detalle[CONJETURAS[corta]]["indicadores_informativos"].get(indicador))
    for corta, clave in CONJETURAS.items():
        fila[f"{corta}_causas"] = ";".join(detalle[clave]["causas_no_validacion"])
    for prefijo, clave_modo in MODOS.items():
        for campo in CAMPOS_IMPACTO:
            fila[f"{prefijo}_{campo}"] = resultado[CLAVE_IMPACTO][clave_modo][campo]
    return fila


def ejecutar_escenarios() -> list[tuple[str, float, dict]]:
    """Ejecuta los cinco escenarios con cada humedad inicial y devuelve las respuestas serializadas."""
    corridas = []
    for humedad in HUMEDADES_PCT:
        for escenario in Escenario:
            cfg = SimulationConfig(
                duracion_horas=DURACION_HORAS,
                escenario=escenario,
                humedad_ambiente_inicial_pct=humedad,
                tasa_salinizacion=TASA,
                semilla=SEMILLA,
            )
            corridas.append((escenario.value, humedad, ejecutar_simulacion(cfg).model_dump(mode="json")))
    return corridas


def filas_robustez(robustez: dict) -> list[dict]:
    """Aplana la robustez serializada: una fila por combinación de flujo y eficacia y por punto del barrido.

    Cada fila lleva el flujo, la eficacia y el cruce de su combinación, seguidos
    de los campos del punto y de la humedad inicial.
    """
    filas = []
    for combinacion in robustez["combinaciones"]:
        barrido = combinacion["barrido"]
        cruce = barrido["cruce"]
        for punto in barrido["puntos"]:
            filas.append(
                {
                    "flujo_niebla_maximo_l_m2_h": combinacion["flujo_niebla_maximo_l_m2_h"],
                    "eficacia_maxima_pulso": combinacion["eficacia_maxima_pulso"],
                    "cruce_estado": cruce["estado"],
                    "cruce_incrustacion_diaria_ohm": _vacio_si_nulo(cruce["incrustacion_diaria_ohm"]),
                    "cruce_carga_salina_ohm_l_m2": _vacio_si_nulo(cruce["carga_salina_ohm_l_m2"]),
                    **punto,
                    CAMPO_HUMEDAD: HUMEDAD_BARRIDO_PCT,
                }
            )
    return filas


def escribir_csv(ruta: Path, filas: list[dict]) -> None:
    """Escribe filas homogéneas en CSV UTF-8 con encabezado."""
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        # Fin de línea LF para que el archivo sea idéntico en cualquier sistema operativo.
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def condiciones() -> dict:
    """Condiciones de ejecución que se registran en el JSON para reproducir los datos."""
    return {
        "version_servicio": VERSION_SERVICIO,
        "escenarios": {
            "duracion_horas": DURACION_HORAS,
            "tasa_salinizacion": TASA.value,
            "numero_nodos": 8,
            "paso_minutos": 5,
            "semilla": SEMILLA,
            "humedades_iniciales_pct": list(HUMEDADES_PCT),
        },
        "barrido": {CAMPO_HUMEDAD: HUMEDAD_BARRIDO_PCT, "duracion_horas": DURACION_HORAS, "semillas": SEMILLAS_BARRIDO},
        "robustez": {CAMPO_HUMEDAD: HUMEDAD_BARRIDO_PCT, "duracion_horas": DURACION_HORAS, "semillas": SEMILLAS_ROBUSTEZ},
        "nota": (
            "Las corridas omiten series_temporales y bitacora; se reproducen con POST "
            "/api/v1/simulacion/ejecutar y la misma configuración."
        ),
    }


def generar(carpeta: Path = CARPETA_POR_DEFECTO) -> list[Path]:
    """Ejecuta el modelo y escribe los cuatro archivos; devuelve sus rutas.

    La carpeta de destino solo la fija el propio script: la constante
    CARPETA_POR_DEFECTO o un directorio de tempfile.TemporaryDirectory(). Nunca
    proviene de la línea de comandos ni de variables de entorno.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    corridas = ejecutar_escenarios()
    barrido = ejecutar_barrido(
        BarridoConfig(humedad_ambiente_inicial_pct=HUMEDAD_BARRIDO_PCT, semillas=SEMILLAS_BARRIDO)
    ).model_dump(mode="json")
    robustez = ejecutar_robustez(
        RobustezConfig(humedad_ambiente_inicial_pct=HUMEDAD_BARRIDO_PCT, semillas=SEMILLAS_ROBUSTEZ)
    ).model_dump(mode="json")

    rutas = [carpeta / nombre for nombre in ARCHIVOS]
    escribir_csv(rutas[0], [fila_escenario(escenario, humedad, r) for escenario, humedad, r in corridas])
    escribir_csv(rutas[1], [{**punto, CAMPO_HUMEDAD: HUMEDAD_BARRIDO_PCT} for punto in barrido["puntos"]])
    escribir_csv(rutas[3], filas_robustez(robustez))

    completos = {
        "condiciones": condiciones(),
        "escenarios": [
            {
                "escenario": escenario,
                CAMPO_HUMEDAD: humedad,
                "comparativa": resultado["comparativa"],
                "conjeturas_validadas": resultado["conjeturas_validadas"],
                "detalle_verificacion": resultado["detalle_verificacion"],
                CLAVE_IMPACTO: resultado[CLAVE_IMPACTO],
            }
            for escenario, humedad, resultado in corridas
        ],
        "barrido_salinidad": barrido,
        "robustez_respuesta": {
            clave: valor for clave, valor in robustez.items() if clave != "combinaciones"
        },
    }
    with rutas[2].open("w", encoding="utf-8", newline="\n") as archivo:
        json.dump(completos, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")
    return rutas


def comparar_con_referencia(carpeta_generada: Path, carpeta_referencia: Path = CARPETA_POR_DEFECTO) -> list[str]:
    """Compara byte a byte los archivos de ARCHIVOS en ambas carpetas.

    Devuelve los nombres de los archivos que difieren o que faltan en alguna de
    las dos carpetas; una lista vacía indica que coinciden.
    """
    diferentes = []
    for nombre in ARCHIVOS:
        generado = carpeta_generada / nombre
        referencia = carpeta_referencia / nombre
        if not (generado.is_file() and referencia.is_file()) or generado.read_bytes() != referencia.read_bytes():
            diferentes.append(nombre)
    return diferentes


def main(argv: list[str] | None = None) -> int:
    """Genera los datos de referencia en docs/datos/ o, con --comprobar, verifica que estén al día.

    Devuelve 0 si los archivos se escribieron o coinciden con la referencia, y
    1 si --comprobar encuentra archivos distintos o ausentes.
    """
    parser = argparse.ArgumentParser(description="Genera los resultados de referencia del modelo en CSV y JSON.")
    parser.add_argument(
        "--comprobar",
        action="store_true",
        help="Genera en un directorio temporal y compara con docs/datos/ sin modificarlo.",
    )
    argumentos = parser.parse_args(argv)
    if not argumentos.comprobar:
        for ruta in generar():
            print(f"Escrito: {ruta}")
        return 0

    with tempfile.TemporaryDirectory() as temporal:
        carpeta_temporal = Path(temporal)
        generar(carpeta_temporal)
        diferentes = comparar_con_referencia(carpeta_temporal)
    if diferentes:
        print(f"Difieren de {CARPETA_POR_DEFECTO} o faltan: {', '.join(diferentes)}")
        print("Regenerar con: python scripts/generar_resultados_referencia.py")
        return 1
    print(f"Los {len(ARCHIVOS)} archivos de {CARPETA_POR_DEFECTO} coinciden con el modelo actual.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
