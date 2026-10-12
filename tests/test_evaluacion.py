"""Pruebas de la propia suite de evaluacion (T-29). Verifican que el evaluador compare bien
y que las preguntas cumplan lo que exige la spec (seccion 8). No usan LLM ni base."""
import re
from collections import Counter
from decimal import Decimal

import pytest
import yaml

from tests.evaluacion import (comparar_filas, coincide_valor, contiene_alguna, contiene_todas,
                              idioma_de_texto, resumir)
from tests.run_eval import PREGUNTAS, cargar_preguntas


# --- comparacion de valores y filas --------------------------------------------
@pytest.mark.parametrize("ref,obt,esperado", [
    (60, 60, True), (60, 60.0, True), (60, Decimal("60"), True), (60, "60", True), (60, 61, False),
    (345.67, 345.6667, True), (345.67, 346, False),
    ("Argentina", "argentina", True), ("Juan", "Juan Pérez", True), ("Chile", "Uruguay", False),
    (None, None, True), (5, None, False), (5, "abc", False),
])
def test_coincide_valor(ref, obt, esperado):
    assert coincide_valor(ref, obt, tolerancia=0.01) is esperado


def test_comparar_filas_tolera_columnas_extra_y_otro_orden():
    ref = [{"pais": "Chile", "n": 6}, {"pais": "Uruguay", "n": 7}]
    obt = [{"total": 7, "pais": "Uruguay", "otra": "x"}, {"pais": "Chile", "total": 6}]
    assert comparar_filas(ref, obt)[0]


def test_comparar_filas_detecta_cifra_incorrecta():
    ok, detalle = comparar_filas([{"n": 24}], [{"total_pedidos": 47}])
    assert not ok and "faltan" in detalle


def test_comparar_filas_exacto_exige_la_misma_cantidad():
    ref = [{"id": 1}, {"id": 2}]
    obt = [{"id": 1}, {"id": 2}, {"id": 3}]
    assert comparar_filas(ref, obt)[0]
    assert not comparar_filas(ref, obt, exacto=True)[0]


def test_comparar_filas_sin_referencia_espera_cero_filas():
    assert comparar_filas([], [])[0]
    assert not comparar_filas([], [{"nombre": "x"}])[0]


def test_comparar_filas_agente_sin_datos():
    assert not comparar_filas([{"n": 1}], [])[0]


# --- textos --------------------------------------------------------------------
def test_idioma_de_texto():
    assert idioma_de_texto("El plazo para devolver un producto es de 30 días.") == "es"
    assert idioma_de_texto("You have 30 days from the delivery date to return it.") == "en"
    assert idioma_de_texto("30") == "?"


def test_contiene():
    assert contiene_todas("Plazo de 30 días corridos", ["30", "CORRIDOS"])
    assert not contiene_todas("Plazo de 30 días", ["30", "corridos"])
    assert contiene_alguna("cubre golpes", ["líquidos", "golpes"])


def test_resumir_agrupa_por_tipo_y_calcula_porcentajes():
    base = {"ruta_ok": True, "respuesta_ok": True, "idioma_ok": True, "seguro": True, "aprobada": True,
            "latencia_s": 10.0}
    res = resumir([{**base, "tipo": "sql"}, {**base, "tipo": "sql", "aprobada": False, "ruta_ok": False,
                                              "latencia_s": 20.0},
                   {**base, "tipo": "rag"}])
    assert res["sql"]["n"] == 2 and res["sql"]["pct_aprobadas"] == 50 and res["sql"]["pct_ruta"] == 50
    assert res["sql"]["latencia_media_s"] == 15.0 and res["sql"]["pct_bajo_limite"] == 50
    assert res["TOTAL"]["n"] == 3 and res["TOTAL"]["aprobadas"] == 2
    assert res["TOTAL"]["latencia_neta_media_s"] is None          # sin dato, no inventa


def test_resumir_calcula_la_latencia_neta():
    base = {"ruta_ok": True, "respuesta_ok": True, "idioma_ok": True, "seguro": True, "aprobada": True,
            "tipo": "sql", "latencia_s": 12.0, "latencia_neta_s": 4.0}
    assert resumir([base, {**base, "latencia_neta_s": 6.0}])["sql"]["latencia_neta_media_s"] == 5.0


# --- integridad del archivo de preguntas --------------------------------------------
PREGUNTAS_YAML = cargar_preguntas()


def test_ids_unicos_y_campos_obligatorios():
    ids = [p["id"] for p in PREGUNTAS_YAML]
    assert len(ids) == len(set(ids))
    for p in PREGUNTAS_YAML:
        assert {"id", "tipo", "pregunta", "idioma", "ruta"} <= set(p), p["id"]
        assert p["idioma"] in ("es", "en")


def test_cumple_los_minimos_de_la_spec():
    """Spec seccion 8: SQL>=6, RAG>=5, hibridas>=3, fuera de alcance>=3, maliciosas>=3, total>=20."""
    c = Counter(p["tipo"] for p in PREGUNTAS_YAML)
    assert c["sql"] >= 6 and c["rag"] >= 5 and c["hibrida"] >= 3
    assert c["fuera_de_alcance"] >= 3 and c["maliciosa"] >= 3
    assert len(PREGUNTAS_YAML) >= 20


@pytest.mark.parametrize("tipo", ["sql", "rag", "hibrida", "fuera_de_alcance", "maliciosa"])
def test_cada_tipo_tiene_preguntas_en_ambos_idiomas(tipo):
    idiomas = {p["idioma"] for p in PREGUNTAS_YAML if p["tipo"] == tipo}
    assert idiomas == {"es", "en"}


def test_las_consultas_de_referencia_pasan_el_validador():
    from src.sql_tool.validator import validar_sql
    for p in PREGUNTAS_YAML:
        for sql in [p.get("sql_referencia")] + list((p.get("variables") or {}).values()):
            if sql:
                r = validar_sql(re.sub(r"\{\w+\}", "1", " ".join(sql.split())))
                assert r.ok, f"{p['id']}: {r.motivo}"


def test_el_yaml_se_puede_leer_de_nuevo():
    assert yaml.safe_load(PREGUNTAS.read_text(encoding="utf-8")) == PREGUNTAS_YAML
