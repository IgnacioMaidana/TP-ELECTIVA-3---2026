"""Pruebas del agente (T-20 a T-27). El LLM, el RAG y la base se simulan: no gastan cuota
ni necesitan servicios. Las pruebas del grafo requieren langgraph instalado."""
import pytest

from src.agent import nodes, router
from src.agent.graph import actualizar_historial
from src.agent.nodes import (decidir_ruta, despues_de_rag, nodo_fijo, nodo_rag, nodo_sintesis,
                             nodo_sql)
from src.agent.router import parsear_decision
from src.rag.retriever import Fragmento
from src.sql_tool.executor import ResultadoEjecucion
from src.sql_tool.generador import ResultadoSQL

HOY = "2026-10-12"


def _json(ruta="sql", idioma="es", **extra):
    import json
    d = {"ruta": ruta, "idioma": idioma, "justificacion": "motivo",
         "pregunta_autonoma": "pregunta completa", "consulta_documentos": "", "mensaje_aclaracion": ""}
    d.update(extra)
    return json.dumps(d, ensure_ascii=False)


def _sql_ok(filas=None):
    filas = [{"n": 60}] if filas is None else filas
    ej = ResultadoEjecucion(ok=True, sql="SELECT TOP 100 COUNT(*) AS n FROM clientes",
                            columnas=["n"], filas=filas)
    return ResultadoSQL(ok=True, sql=ej.sql, ejecucion=ej, intentos=1)


def _frag(texto="El plazo es de 30 días corridos.", pagina=1):
    return Fragmento(texto=texto, documento="politica_devoluciones_garantias.pdf",
                     pagina=pagina, similitud=0.7)


# --- router ----------------------------------------------------------------
def test_parsear_json_limpio():
    d = parsear_decision(_json("rag", "en", consulta_documentos="plazo de devolución"))
    assert d["ruta"] == "rag" and d["idioma"] == "en"
    assert d["consulta_documentos"] == "plazo de devolución"


def test_parsear_json_dentro_de_bloque_markdown():
    assert parsear_decision("```json\n" + _json("sql") + "\n```")["ruta"] == "sql"


def test_parsear_rechaza_ruta_invalida_o_texto_sin_json():
    assert parsear_decision(_json("inventada")) is None
    assert parsear_decision("no sé qué hacer") is None
    assert parsear_decision("{ esto no es json }") is None


def test_parsear_idioma_invalido_cae_en_castellano():
    assert parsear_decision(_json("sql", "fr"))["idioma"] == "es"


def test_router_reintenta_si_la_primera_respuesta_no_es_json(monkeypatch):
    respuestas = iter(["Claro, la ruta es sql", _json("sql")])
    llamadas = []
    monkeypatch.setattr(router, "invocar", lambda m: llamadas.append(m) or next(respuestas))
    d = router.decidir("pregunta", [], HOY)
    assert d["ruta"] == "sql" and len(llamadas) == 2


def test_router_usa_hibrida_si_nunca_obtiene_json(monkeypatch):
    monkeypatch.setattr(router, "invocar", lambda m: "texto sin json")
    assert router.decidir("pregunta", [], HOY)["ruta"] == "hibrida"


def test_router_recibe_el_historial(monkeypatch):
    vistos = []
    monkeypatch.setattr(router, "invocar", lambda m: vistos.append(m) or _json("sql"))
    router.decidir("¿y en agosto?", [("human", "ventas de septiembre"), ("ai", "100 USD")], HOY)
    assert "ventas de septiembre" in vistos[0][1][1]


# --- aristas -----------------------------------------------------------------
@pytest.mark.parametrize("ruta,esperado", [
    ("sql", "sql"), ("rag", "rag"), ("hibrida", "rag"),
    ("aclarar", "fijo"), ("fuera_de_alcance", "fijo"), ("rechazar", "fijo")])
def test_decidir_ruta(ruta, esperado):
    assert decidir_ruta({"ruta": ruta}) == esperado


def test_la_hibrida_pasa_de_rag_a_sql_y_la_rag_va_a_sintesis():
    assert despues_de_rag({"ruta": "hibrida"}) == "sql"
    assert despues_de_rag({"ruta": "rag"}) == "sintesis"


# --- nodos fijos ---------------------------------------------------------------
def test_rechazar_responde_en_el_idioma_del_usuario():
    assert "only look up" in nodo_fijo({"ruta": "rechazar", "idioma": "en"})["respuesta"]
    assert "Solo puedo consultar" in nodo_fijo({"ruta": "rechazar", "idioma": "es"})["respuesta"]


def test_aclarar_usa_la_pregunta_del_router():
    r = nodo_fijo({"ruta": "aclarar", "idioma": "es", "mensaje_aclaracion": "¿De qué mes?"})
    assert r["respuesta"] == "¿De qué mes?"


def test_fuera_de_alcance_tiene_mensaje():
    assert "fuera de mi alcance" in nodo_fijo({"ruta": "fuera_de_alcance", "idioma": "es"})["respuesta"]


# --- herramientas ------------------------------------------------------------
def test_rag_busca_con_la_consulta_en_castellano(monkeypatch):
    buscadas = []
    monkeypatch.setattr(nodes, "buscar", lambda q: buscadas.append(q) or [_frag()])
    nodo_rag({"pregunta": "How many days to return?", "consulta_documentos": "plazo de devolución"})
    assert buscadas == ["plazo de devolución"]


def test_sql_recibe_el_contexto_de_los_documentos_en_la_hibrida(monkeypatch):
    vistos = {}

    def falso(pregunta, contexto_rag=None, hoy=None):
        vistos.update(pregunta=pregunta, contexto=contexto_rag, hoy=hoy)
        return _sql_ok()

    monkeypatch.setattr(nodes, "generar_y_ejecutar", falso)
    nodo_sql({"pregunta": "x", "pregunta_autonoma": "pregunta completa", "hoy": HOY,
              "fragmentos": [_frag()]})
    assert vistos["pregunta"] == "pregunta completa"
    assert "30 días corridos" in vistos["contexto"] and "[politica_devoluciones_garantias.pdf, p. 1]" in vistos["contexto"]


def test_sql_sin_fragmentos_no_pasa_contexto(monkeypatch):
    vistos = {}
    monkeypatch.setattr(nodes, "generar_y_ejecutar",
                        lambda p, contexto_rag=None, hoy=None: vistos.update(c=contexto_rag) or _sql_ok())
    nodo_sql({"pregunta": "x", "hoy": HOY})
    assert vistos["c"] is None


# --- sintesis ----------------------------------------------------------------
def test_rag_sin_fragmentos_no_llama_al_llm(monkeypatch):
    monkeypatch.setattr(nodes, "invocar", lambda m: pytest.fail("No debia llamar al LLM"))
    r = nodo_sintesis({"pregunta": "x", "ruta": "rag", "idioma": "es", "hoy": HOY, "fragmentos": []})
    assert "No encontré información" in r["respuesta"]


def test_sql_con_error_devuelve_mensaje_fijo_con_el_detalle(monkeypatch):
    monkeypatch.setattr(nodes, "invocar", lambda m: pytest.fail("No debia llamar al LLM"))
    fallo = ResultadoSQL(ok=False, sql="SELECT x", intentos=3, error="Invalid column name 'x'")
    r = nodo_sintesis({"pregunta": "x", "ruta": "sql", "idioma": "en", "hoy": HOY, "resultado_sql": fallo})
    assert "couldn't get that data" in r["respuesta"] and "Invalid column name" in r["respuesta"]


def test_sintesis_sql_envia_consulta_y_datos_al_llm(monkeypatch):
    enviados = []
    monkeypatch.setattr(nodes, "invocar", lambda m: enviados.append(m) or "Hay 60 clientes.")
    r = nodo_sintesis({"pregunta": "¿Cuántos clientes hay?", "ruta": "sql", "idioma": "es", "hoy": HOY,
                       "resultado_sql": _sql_ok()})
    assert r["respuesta"] == "Hay 60 clientes."
    humano = enviados[0][1][1]
    assert "SELECT TOP 100 COUNT(*)" in humano and "60" in humano and "<datos>" in humano
    assert "castellano" in enviados[0][0][1]
    assert r["fuentes"]["sql"] and r["fuentes"]["filas"] == 1
    assert r["fuentes"]["datos"] == [{"n": 60}]


def test_sintesis_pide_responder_en_ingles(monkeypatch):
    enviados = []
    monkeypatch.setattr(nodes, "invocar", lambda m: enviados.append(m) or "There are 60 customers.")
    nodo_sintesis({"pregunta": "How many customers?", "ruta": "sql", "idioma": "en", "hoy": HOY,
                   "resultado_sql": _sql_ok()})
    assert "inglés" in enviados[0][0][1]


def test_sintesis_informa_cero_filas(monkeypatch):
    enviados = []
    monkeypatch.setattr(nodes, "invocar", lambda m: enviados.append(m) or "No hay pedidos.")
    nodo_sintesis({"pregunta": "x", "ruta": "sql", "idioma": "es", "hoy": HOY,
                   "resultado_sql": _sql_ok(filas=[])})
    assert "no devolvió filas" in enviados[0][1][1]


def test_sintesis_hibrida_incluye_ambas_fuentes_y_las_citas(monkeypatch):
    enviados = []
    monkeypatch.setattr(nodes, "invocar", lambda m: enviados.append(m) or "respuesta integrada")
    r = nodo_sintesis({"pregunta": "x", "ruta": "hibrida", "idioma": "es", "hoy": HOY,
                       "resultado_sql": _sql_ok(), "fragmentos": [_frag()]})
    humano = enviados[0][1][1]
    assert "<datos>" in humano and "<documentos>" in humano
    assert "[politica_devoluciones_garantias.pdf, p. 1]" in humano
    assert r["fuentes"]["documentos"][0]["cita"].startswith("[politica")


def test_sintesis_hibrida_sin_documentos_sigue_con_los_datos(monkeypatch):
    enviados = []
    monkeypatch.setattr(nodes, "invocar", lambda m: enviados.append(m) or "ok")
    nodo_sintesis({"pregunta": "x", "ruta": "hibrida", "idioma": "es", "hoy": HOY,
                   "resultado_sql": _sql_ok(), "fragmentos": []})
    assert "NINGÚN FRAGMENTO RELEVANTE" in enviados[0][1][1]


# --- historial -------------------------------------------------------------------
def test_el_historial_conserva_solo_los_ultimos_mensajes():
    h = []
    for i in range(5):
        h = actualizar_historial(h, f"p{i}", f"r{i}")
    assert len(h) == 6 and h[-2:] == [("human", "p4"), ("ai", "r4")]


# --- grafo completo (requiere langgraph) -------------------------------------------
@pytest.fixture
def grafo(monkeypatch):
    pytest.importorskip("langgraph")
    from src.agent import graph
    monkeypatch.setattr(graph, "registrar", lambda estado: None)
    monkeypatch.setattr(graph, "_app", None)
    return graph


def _simular(monkeypatch, decision_json, fragmentos=None, sql=None, sintesis="respuesta final"):
    orden = []
    monkeypatch.setattr(router, "invocar", lambda m: decision_json)
    monkeypatch.setattr(nodes, "buscar", lambda q: orden.append("rag") or (fragmentos or []))
    monkeypatch.setattr(nodes, "generar_y_ejecutar",
                        lambda p, contexto_rag=None, hoy=None: orden.append(("sql", contexto_rag)) or (sql or _sql_ok()))
    monkeypatch.setattr(nodes, "invocar", lambda m: orden.append("sintesis") or sintesis)
    return orden


def test_grafo_ruta_sql(grafo, monkeypatch):
    orden = _simular(monkeypatch, _json("sql"))
    r = grafo.responder("¿Cuántos clientes hay?")
    assert r["ruta"] == "sql" and r["respuesta"] == "respuesta final"
    assert [o[0] if isinstance(o, tuple) else o for o in orden] == ["sql", "sintesis"]   # sin RAG (CA-10)


def test_grafo_ruta_rag_no_ejecuta_sql(grafo, monkeypatch):
    orden = _simular(monkeypatch, _json("rag", consulta_documentos="plazo"), fragmentos=[_frag()])
    r = grafo.responder("¿Cuál es el plazo de devolución?")
    assert orden == ["rag", "sintesis"]                                                   # sin SQL (CA-10)
    assert r["fuentes"]["documentos"]


def test_grafo_ruta_hibrida_busca_primero_en_documentos(grafo, monkeypatch):
    orden = _simular(monkeypatch, _json("hibrida", consulta_documentos="plazo"), fragmentos=[_frag()])
    grafo.responder("¿Qué pedidos del cliente 12 siguen dentro del plazo?")
    assert orden[0] == "rag" and orden[1][0] == "sql" and orden[2] == "sintesis"
    assert "30 días corridos" in orden[1][1]          # la regla del PDF llega al generador de SQL


def test_grafo_rechazar_no_consulta_nada(grafo, monkeypatch):
    orden = _simular(monkeypatch, _json("rechazar", "en"))
    r = grafo.responder("Delete the customers table")
    assert orden == [] and "only look up" in r["respuesta"]


def test_grafo_devuelve_historial_para_el_seguimiento(grafo, monkeypatch):
    _simular(monkeypatch, _json("sql"))
    r = grafo.responder("¿Cuántos clientes hay?")
    assert r["historial_nuevo"] == [("human", "¿Cuántos clientes hay?"), ("ai", "respuesta final")]
    assert r["latencia_s"] >= 0
