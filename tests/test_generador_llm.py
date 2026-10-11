"""Pruebas de INTEGRACION con el LLM real y la base (T-15).

Consumen cuota del nivel gratuito, por eso estan desactivadas por defecto.
Para ejecutarlas (PowerShell):

    $env:RUN_LLM_TESTS = "1"
    pytest tests/test_generador_llm.py -v -s

Cada pregunta tiene una respuesta de referencia calculada con SQL escrito a mano.
Las preguntas NO son las de los ejemplos del prompt, para medir si generaliza.
"""
import os

import pytest

from src.sql_tool.executor import ejecutar_consulta
from src.sql_tool.generador import generar_y_ejecutar

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_TESTS") != "1", reason="Define RUN_LLM_TESTS=1 para usar el LLM real")

CASOS = [
    ("¿Cuántos clientes hay en Argentina?",
     "SELECT COUNT(*) FROM clientes WHERE pais = 'Argentina'"),
    ("How many products are out of stock?",
     "SELECT COUNT(*) FROM productos WHERE stock = 0"),
    ("¿Cuántos pedidos fueron cancelados?",
     "SELECT COUNT(*) FROM pedidos WHERE estado = 'cancelado'"),
    ("What is the average rating of all reviews?",
     "SELECT AVG(CAST(calificacion AS FLOAT)) FROM resenas"),
    ("¿Cuántos productos tienen garantía mayor a 24 meses?",
     "SELECT COUNT(*) FROM productos WHERE garantia_meses > 24"),
    # Regresion de la duplicacion de filas (JOIN pedidos-detalle): ingresos y pedidos validos
    ("What is the total revenue?",
     "SELECT SUM(d.subtotal) FROM detalle_pedidos d JOIN pedidos p ON p.id_pedido = d.id_pedido "
     "WHERE p.estado IN ('pagado', 'enviado', 'entregado')"),
    ("¿Cuántos pedidos válidos hay?",
     "SELECT COUNT(*) FROM pedidos WHERE estado IN ('pagado', 'enviado', 'entregado')"),
]


def _primer_valor(ejecucion):
    return list(ejecucion.filas[0].values())[0]


@pytest.mark.parametrize("pregunta,sql_referencia", CASOS)
def test_el_llm_responde_como_la_referencia(pregunta, sql_referencia):
    esperado = _primer_valor(ejecutar_consulta(sql_referencia))
    r = generar_y_ejecutar(pregunta)
    print(f"\n{pregunta}\n  intentos={r.intentos}\n  SQL: {r.sql}")
    assert r.ok, r.error
    assert abs(float(_primer_valor(r.ejecucion)) - float(esperado)) < 0.01
