"""Pruebas del generador de SQL (T-15). No usan LLM ni base: ambos se simulan."""
import pytest

from src import config
from src.sql_tool import generador
from src.sql_tool.executor import ResultadoEjecucion
from src.sql_tool.generador import extraer_sql, generar_y_ejecutar


# --- limpieza de la respuesta del LLM -------------------------------------
@pytest.mark.parametrize("texto,esperado", [
    ("SELECT 1", "SELECT 1"),
    ("```sql\nSELECT 1\n```", "SELECT 1"),
    ("```\nSELECT 1\n```", "SELECT 1"),
    ("```tsql\nSELECT COUNT(*) FROM clientes\n```", "SELECT COUNT(*) FROM clientes"),
    ("SQL: SELECT 1", "SELECT 1"),
    ("  \n SELECT 1 \n ", "SELECT 1"),
    ("Aqui va:\n```sql\nSELECT 1\n```\nListo.", "SELECT 1"),
])
def test_extraer_sql(texto, esperado):
    assert extraer_sql(texto) == esperado


# --- flujo con reintentos (LLM y ejecutor simulados) -----------------------
def _preparar(monkeypatch, respuestas_llm, resultados_ejecucion):
    """Simula el LLM y el ejecutor; devuelve las llamadas registradas."""
    llamadas = {"llm": [], "sql": []}
    respuestas, resultados = iter(respuestas_llm), iter(resultados_ejecucion)

    def llm_falso(mensajes):
        llamadas["llm"].append(list(mensajes))
        return next(respuestas)

    def ejecutor_falso(sql):
        llamadas["sql"].append(sql)
        return next(resultados)

    monkeypatch.setattr(generador, "invocar", llm_falso)
    monkeypatch.setattr(generador, "ejecutar_consulta", ejecutor_falso)
    return llamadas


def test_responde_al_primer_intento(monkeypatch):
    ok = ResultadoEjecucion(ok=True, sql="SELECT TOP 100 COUNT(*) AS n FROM clientes",
                            columnas=["n"], filas=[{"n": 60}])
    llamadas = _preparar(monkeypatch, ["```sql\nSELECT COUNT(*) AS n FROM clientes\n```"], [ok])
    r = generar_y_ejecutar("¿Cuántos clientes hay?")
    assert r.ok and r.intentos == 1
    assert r.ejecucion.filas == [{"n": 60}]
    assert llamadas["sql"] == ["SELECT COUNT(*) AS n FROM clientes"]   # sin markdown


def test_reintenta_con_el_error_y_corrige(monkeypatch):
    malo = ResultadoEjecucion(ok=False, etapa="ejecucion", error="Invalid column name 'x'")
    bueno = ResultadoEjecucion(ok=True, sql="SELECT 1", columnas=["n"], filas=[{"n": 1}])
    llamadas = _preparar(monkeypatch, ["SELECT x FROM clientes", "SELECT 1"], [malo, bueno])
    r = generar_y_ejecutar("pregunta")
    assert r.ok and r.intentos == 2
    assert len(r.historial) == 2
    # el segundo pedido al LLM incluye el error anterior
    ultimo = llamadas["llm"][1][-1][1]
    assert "Invalid column name" in ultimo


def test_se_rinde_tras_agotar_los_reintentos(monkeypatch):
    malo = ResultadoEjecucion(ok=False, etapa="validacion", error="Instrucción no permitida")
    n = config.SQL_RETRIES + 1
    _preparar(monkeypatch, ["DROP TABLE clientes"] * n, [malo] * n)
    r = generar_y_ejecutar("borra todo")
    assert not r.ok and r.intentos == n
    assert r.error == "Instrucción no permitida"


def test_no_sql_no_ejecuta_nada(monkeypatch):
    llamadas = _preparar(monkeypatch, ["NO_SQL"], [])
    r = generar_y_ejecutar("¿Quién ganó el Mundial?")
    assert r.sin_sql and not r.ok
    assert llamadas["sql"] == []


def test_el_historial_del_chat_llega_al_llm(monkeypatch):
    ok = ResultadoEjecucion(ok=True, sql="SELECT 1", columnas=["n"], filas=[{"n": 1}])
    llamadas = _preparar(monkeypatch, ["SELECT 1"], [ok])
    previo = [("human", "ventas de septiembre"), ("ai", "SELECT 1")]
    generar_y_ejecutar("¿y en agosto?", historial_chat=previo)
    roles = [m[0] for m in llamadas["llm"][0]]
    assert roles == ["system", "human", "ai", "human"]
