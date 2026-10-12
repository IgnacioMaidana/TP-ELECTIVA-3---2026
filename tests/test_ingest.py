"""Pruebas de la ingesta (T-18). No usan modelo ni ChromaDB: solo lectura y fragmentacion.

Requieren los PDFs en data/pdfs (python -m scripts.generar_pdfs).
"""
import pytest

from src import config
from src.rag.ingest import construir_fragmentos, dividir_texto, limpiar_pagina

PDFS = sorted(config.DIR_PDFS.glob("*.pdf"))


# --- fragmentacion -----------------------------------------------------------
def test_texto_corto_es_un_solo_fragmento():
    assert dividir_texto("Una oración corta.", max_chars=450) == ["Una oración corta."]


def test_texto_vacio_no_genera_fragmentos():
    assert dividir_texto("   \n  ") == []


def test_ningun_fragmento_supera_el_maximo():
    texto = " ".join(f"Oración número {i} con algunas palabras de relleno." for i in range(60))
    for f in dividir_texto(texto, max_chars=200, solape=40):
        assert len(f) <= 200


def test_una_oracion_muy_larga_se_parte_por_palabras():
    texto = " ".join(f"palabra{i}" for i in range(200))      # sin puntos, como una tabla
    fragmentos = dividir_texto(texto, max_chars=100, solape=20)
    assert len(fragmentos) > 1
    assert all(len(f) <= 100 for f in fragmentos)


def test_hay_solapamiento_entre_fragmentos_consecutivos():
    texto = " ".join(f"Oración número {i} con algunas palabras de relleno." for i in range(30))
    fragmentos = dividir_texto(texto, max_chars=200, solape=60)
    inicio_siguiente = fragmentos[1].split()[0:2]
    assert " ".join(inicio_siguiente) in fragmentos[0]


def test_se_quita_el_pie_de_pagina():
    texto = "Contenido importante.\nTechNova Store - Política de Devoluciones y Garantías Página 2"
    assert "Página" not in limpiar_pagina(texto)
    assert "Contenido importante." in limpiar_pagina(texto)


# --- PDFs reales -----------------------------------------------------------
def test_hay_al_menos_2_pdfs():
    assert len(PDFS) >= 2, "El enunciado exige 2 PDFs como minimo (CA-18)"


@pytest.mark.parametrize("pdf", PDFS, ids=[p.name for p in PDFS])
def test_cada_fragmento_tiene_documento_y_pagina(pdf):
    fragmentos = construir_fragmentos(pdf)
    assert fragmentos
    for f in fragmentos:
        assert f["documento"] == pdf.name
        assert isinstance(f["pagina"], int) and f["pagina"] >= 1
        assert 20 <= len(f["texto"]) <= config.RAG_CHUNK_CHARS
        assert "Página" not in f["texto"]


def test_ids_son_unicos():
    ids = [f["id"] for pdf in PDFS for f in construir_fragmentos(pdf)]
    assert len(ids) == len(set(ids))


def test_la_regla_de_30_dias_esta_en_algun_fragmento():
    politica = next(p for p in PDFS if "politica" in p.name)
    textos = " ".join(f["texto"] for f in construir_fragmentos(politica))
    assert "30 días corridos" in textos
    assert "entrega real" in textos


def test_los_fragmentos_llevan_el_titulo_de_su_seccion():
    politica = next(p for p in PDFS if "politica" in p.name)
    fragmentos = construir_fragmentos(politica)
    con_plazo = [f for f in fragmentos if "30 días corridos" in f["texto"]]
    assert any(f["texto"].startswith("2. Plazo de devolución:") for f in con_plazo)
    catalogo = next(p for p in PDFS if "catalogo" in p.name)
    assert any(f["texto"].startswith("Categoría: Notebooks:") and "Aurora Book 14" in f["texto"]
               for f in construir_fragmentos(catalogo))


def test_no_quedan_pies_de_pagina_en_los_fragmentos():
    for pdf in PDFS:
        for f in construir_fragmentos(pdf):
            assert "TechNova Store - Política" not in f["texto"]
            assert "TechNova Store - Catálogo" not in f["texto"]


def test_la_tabla_de_garantias_queda_completa_en_un_solo_fragmento():
    """Si la tabla se parte, el RAG no puede responder preguntas de minimo/maximo (hallazgo RAG-09)."""
    from scripts.generar_datos import CATALOGO
    politica = next(p for p in PDFS if "politica" in p.name)
    fragmentos = construir_fragmentos(politica)
    categorias = [c[0] for c in CATALOGO]
    assert any(all(f"{c} " in f["texto"] for c in categorias) for f in fragmentos), \
        "Ningun fragmento contiene las 16 categorias de la tabla de garantias"
