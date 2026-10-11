"""Pruebas de la recuperacion (T-19). De INTEGRACION: necesitan el modelo de embeddings
y los documentos indexados (python -m src.rag.ingest).

Las pruebas de "fuera de alcance" dependen del umbral RAG_UMBRAL; si fallan,
calibrarlo con python -m scripts.calibrar_rag.
"""
import pytest

from src import config
from src.rag.retriever import buscar, formatear_contexto

pytestmark = pytest.mark.skipif(
    not config.DIR_VECTORSTORE.exists() or not any(config.DIR_VECTORSTORE.iterdir()),
    reason="Sin indice: ejecutar python -m src.rag.ingest")

# (pregunta, documento esperado o "" si vale cualquiera, textos aceptables: basta con que aparezca uno)
CASOS = [
    ("¿Cuál es el plazo para devolver un producto?", "politica", ("30 días corridos",)),
    ("How many days do I have to return a product?", "politica", ("30 días corridos",)),
    ("¿Desde cuándo se cuenta el plazo de devolución?", "politica", ("entrega real",)),
    # La garantia de almacenamiento figura en AMBOS documentos (politica y catalogo): vale cualquiera
    ("¿Cuántos meses de garantía tienen los discos de almacenamiento?", "",
     ("Almacenamiento 36", "36 meses")),
    ("¿Cómo se reembolsa un pago hecho con MercadoPago?", "politica", ("MercadoPago",)),
    ("What are the specifications of the Aurora Book 14?", "catalogo", ("Aurora Book 14",)),
    ("¿Qué incluye la caja de las cámaras web?", "catalogo", ("Cámara",)),
]


@pytest.mark.parametrize("pregunta,documento,textos", CASOS)
def test_recupera_el_fragmento_correcto(pregunta, documento, textos):
    fragmentos = buscar(pregunta)
    assert fragmentos, f"Sin resultados para: {pregunta}"
    assert any(documento in f.documento for f in fragmentos)
    assert any(t in f.texto for f in fragmentos for t in textos), \
        f"Ningun fragmento contiene {textos}: {[f.texto[:60] for f in fragmentos]}"


def test_los_fragmentos_traen_cita_y_estan_ordenados():
    fragmentos = buscar("¿Qué no cubre la garantía?")
    assert fragmentos
    assert fragmentos[0].cita.startswith("[") and ", p. " in fragmentos[0].cita
    similitudes = [f.similitud for f in fragmentos]
    assert similitudes == sorted(similitudes, reverse=True)


@pytest.mark.parametrize("pregunta", [
    "¿Quién ganó el Mundial de fútbol 2022?",
    "What is the capital of Australia?",
])
def test_pregunta_fuera_de_alcance_no_devuelve_nada(pregunta):
    assert buscar(pregunta) == []


def test_formatear_contexto_incluye_la_cita():
    fragmentos = buscar("¿Cuál es el plazo para devolver un producto?")
    assert fragmentos[0].cita in formatear_contexto(fragmentos)
