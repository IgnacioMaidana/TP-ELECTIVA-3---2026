"""Grafo del agente con LangGraph (T-25).

    router --+--> rag --+--> sintesis --> FIN          (ruta rag)
             |          +--> sql --> sintesis --> FIN  (ruta hibrida: primero documentos, luego datos)
             +--> sql --> sintesis --> FIN             (ruta sql)
             +--> fijo --> FIN        (aclarar, fuera_de_alcance, rechazar)

Uso:
    resultado = responder("¿Cuántos clientes hay por país?", historial=[])
    print(resultado["respuesta"], resultado["ruta"])
"""
import time
from datetime import date

from langgraph.graph import END, START, StateGraph

from src.agent.logging_utils import registrar
from src.agent.nodes import (decidir_ruta, despues_de_rag, nodo_fijo, nodo_rag, nodo_router,
                             nodo_sintesis, nodo_sql)
from src.agent.state import EstadoAgente

MAX_MENSAJES_HISTORIAL = 6
_app = None


def construir_grafo():
    """Arma y compila el grafo."""
    g = StateGraph(EstadoAgente)
    g.add_node("router", nodo_router)
    g.add_node("rag", nodo_rag)
    g.add_node("sql", nodo_sql)
    g.add_node("sintesis", nodo_sintesis)
    g.add_node("fijo", nodo_fijo)

    g.add_edge(START, "router")
    g.add_conditional_edges("router", decidir_ruta, {"rag": "rag", "sql": "sql", "fijo": "fijo"})
    g.add_conditional_edges("rag", despues_de_rag, {"sql": "sql", "sintesis": "sintesis"})
    g.add_edge("sql", "sintesis")
    g.add_edge("sintesis", END)
    g.add_edge("fijo", END)
    return g.compile()


def _grafo():
    global _app
    if _app is None:
        _app = construir_grafo()
    return _app


def actualizar_historial(historial: list, pregunta: str, respuesta: str) -> list:
    """Agrega el turno actual y conserva solo los ultimos mensajes (RF-15)."""
    return (list(historial) + [("human", pregunta), ("ai", respuesta)])[-MAX_MENSAJES_HISTORIAL:]


def responder(pregunta: str, historial: list = None) -> dict:
    """Responde una pregunta. Devuelve el estado final mas la latencia y el historial nuevo."""
    inicio = time.monotonic()
    estado = _grafo().invoke({
        "pregunta": pregunta,
        "historial": list(historial or []),
        "hoy": date.today().isoformat(),
    })
    estado["latencia_s"] = round(time.monotonic() - inicio, 2)
    estado["historial_nuevo"] = actualizar_historial(historial or [], pregunta, estado["respuesta"])
    registrar(estado)
    return estado
