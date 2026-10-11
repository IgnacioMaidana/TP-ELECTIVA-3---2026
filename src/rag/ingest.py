"""Ingesta de PDFs para el RAG (T-17).

Uso (desde la raiz del repositorio, con el entorno virtual activo):

    python -m src.rag.ingest

Pasos:
  1. Lee cada PDF de data/pdfs/ pagina por pagina (la pagina se conserva
     para poder citarla: RF-07).
  2. Divide cada pagina en fragmentos de ~RAG_CHUNK_CHARS caracteres, cortando
     en limites de oracion y con solapamiento.
  3. Calcula un embedding multilingue de cada fragmento.
  4. Guarda todo en ChromaDB (data/vectorstore/) con los metadatos
     {documento, pagina}.

Es idempotente: cada ejecucion borra la coleccion y la vuelve a crear.

Por que fragmentos tan cortos (~450 caracteres): el modelo de embeddings
(paraphrase-multilingual-MiniLM-L12-v2) procesa como maximo 128 tokens; un
fragmento mas largo se truncaria en silencio y se perderia su final.
"""
import re
from pathlib import Path

from pypdf import PdfReader

from src import config

_PIE_DE_PAGINA = re.compile(r"Página\s+\d+\s*$")
# Titulos de seccion de nuestros PDFs: "2. Plazo de devolucion" (politica) y "Categoria: X" (catalogo)
_TITULO_SECCION = re.compile(r"^(?:\d+\.\s+\S.*|Categoría:\s+\S.*)$")


def limpiar_pagina(texto: str) -> str:
    """Quita el pie de pagina ("... Página N") que repite cada hoja del PDF."""
    lineas = [l for l in texto.splitlines() if not _PIE_DE_PAGINA.search(l.strip())]
    return "\n".join(lineas)


def dividir_texto(texto: str, max_chars: int = None, solape: int = None) -> list:
    """Divide `texto` en fragmentos de hasta `max_chars` caracteres.

    Corta en limites de oracion; si una oracion es mas larga que el maximo (por
    ejemplo una tabla), la parte por palabras. Cada fragmento repite al inicio
    las ultimas palabras del anterior (hasta `solape` caracteres) para no perder
    contexto en los cortes.
    """
    max_chars = max_chars or config.RAG_CHUNK_CHARS
    solape = config.RAG_SOLAPE_CHARS if solape is None else solape

    texto = " ".join(texto.split())
    if not texto:
        return []

    unidades = []
    for oracion in re.split(r"(?<=[.!?])\s+", texto):
        while len(oracion) > max_chars:
            corte = oracion.rfind(" ", 0, max_chars)
            if corte <= 0:
                corte = max_chars
            unidades.append(oracion[:corte])
            oracion = oracion[corte:].lstrip()
        if oracion:
            unidades.append(oracion)

    fragmentos, actual = [], ""
    for unidad in unidades:
        if actual and len(actual) + 1 + len(unidad) > max_chars:
            fragmentos.append(actual)
            cola = actual[-solape:] if solape else ""
            cola = cola[cola.find(" ") + 1:] if " " in cola else ""   # empezar en palabra completa
            actual = f"{cola} {unidad}".strip()
            if len(actual) > max_chars:                               # el solape no entra: se descarta
                actual = unidad
        else:
            actual = f"{actual} {unidad}".strip()
    if actual:
        fragmentos.append(actual)
    return fragmentos


def construir_fragmentos(ruta_pdf: Path) -> list:
    """Devuelve los fragmentos de un PDF como diccionarios con su documento y pagina.

    Cada fragmento lleva como prefijo el titulo de su seccion ("2. Plazo de devolucion: ...").
    Sin ese contexto, un fragmento como "de los 30 dias corridos contados desde..." no
    menciona de que trata y la busqueda lo encuentra peor, sobre todo si la pregunta
    esta en otro idioma que el documento. El titulo vigente se arrastra entre paginas.
    """
    ruta_pdf = Path(ruta_pdf)
    resultado = []
    titulo = None
    paginas = [limpiar_pagina(p.extract_text() or "").splitlines() for p in PdfReader(str(ruta_pdf)).pages]
    # Encabezados y pies: lineas que se repiten en TODAS las paginas (ruido para la busqueda)
    repetidas = set()
    if len(paginas) > 1:
        repetidas = set.intersection(*[{l.strip() for l in lineas} for lineas in paginas]) - {""}
    for numero, lineas in enumerate(paginas, start=1):
        n = 0

        def emitir(bloque, titulo_actual):
            nonlocal n
            prefijo = f"{titulo_actual}: " if titulo_actual else ""
            for fragmento in dividir_texto(bloque, max_chars=config.RAG_CHUNK_CHARS - len(prefijo)):
                if len(fragmento) >= 20:
                    resultado.append({
                        "id": f"{ruta_pdf.name}::p{numero}::c{n}",
                        "texto": prefijo + fragmento,
                        "documento": ruta_pdf.name,
                        "pagina": numero,
                    })
                    n += 1

        bloque = []
        for linea in lineas:
            if linea.strip() in repetidas:
                continue
            if _TITULO_SECCION.match(linea.strip()):
                emitir(" ".join(bloque), titulo)       # cierra la seccion anterior
                bloque, titulo = [], linea.strip()
            else:
                bloque.append(linea)
        emitir(" ".join(bloque), titulo)
    return resultado


def ingestar(dir_pdfs: Path = None, dir_store: Path = None) -> dict:
    """Indexa todos los PDFs de `dir_pdfs`. Devuelve {documento: cantidad_de_fragmentos}."""
    import chromadb
    from sentence_transformers import SentenceTransformer

    dir_pdfs = Path(dir_pdfs or config.DIR_PDFS)
    dir_store = Path(dir_store or config.DIR_VECTORSTORE)

    pdfs = sorted(dir_pdfs.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No hay PDFs en {dir_pdfs}. Ejecutar: python -m scripts.generar_pdfs")

    fragmentos = [f for pdf in pdfs for f in construir_fragmentos(pdf)]

    print(f"Cargando modelo de embeddings ({config.EMBEDDING_MODEL}); la primera vez se descarga...")
    modelo = SentenceTransformer(config.EMBEDDING_MODEL)
    embeddings = modelo.encode([f["texto"] for f in fragmentos],
                               normalize_embeddings=True, show_progress_bar=False)

    cliente = chromadb.PersistentClient(path=str(dir_store))
    try:
        cliente.delete_collection(config.RAG_COLECCION)      # idempotente
    except Exception:
        pass
    coleccion = cliente.create_collection(config.RAG_COLECCION, metadata={"hnsw:space": "cosine"})
    coleccion.add(
        ids=[f["id"] for f in fragmentos],
        documents=[f["texto"] for f in fragmentos],
        embeddings=embeddings.tolist(),
        metadatas=[{"documento": f["documento"], "pagina": f["pagina"]} for f in fragmentos],
    )

    cuenta = {}
    for f in fragmentos:
        cuenta[f["documento"]] = cuenta.get(f["documento"], 0) + 1
    return cuenta


if __name__ == "__main__":
    for documento, n in ingestar().items():
        print(f"  {documento}: {n} fragmentos")
    print(f"Indexado en {config.DIR_VECTORSTORE}")
