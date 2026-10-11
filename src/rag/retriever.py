"""Recuperacion de fragmentos de los PDFs (T-19).

    fragmentos = buscar("¿Cuál es el plazo de devolución?")
    contexto = formatear_contexto(fragmentos)

`buscar` devuelve los fragmentos mas parecidos a la pregunta que superen el
umbral de similitud. Si ninguno lo supera devuelve una lista vacia: el agente
debe interpretarlo como "no hay informacion en los documentos" y no inventar
(RF-11, RNF-02).

La similitud es el coseno entre embeddings (1.0 = identicos, 0 = sin relacion).
El umbral por defecto (RAG_UMBRAL) es provisorio: calibrarlo con
python -m scripts.calibrar_rag
"""
from dataclasses import dataclass

from src import config

_modelo = None
_coleccion = None


@dataclass
class Fragmento:
    """Fragmento recuperado de un PDF."""

    texto: str
    documento: str
    pagina: int
    similitud: float

    @property
    def cita(self) -> str:
        """Referencia para citar la fuente (RF-07)."""
        return f"[{self.documento}, p. {self.pagina}]"


def _cargar():
    """Carga (una sola vez) el modelo de embeddings y la coleccion de ChromaDB."""
    global _modelo, _coleccion
    if _modelo is None:
        import chromadb
        from sentence_transformers import SentenceTransformer

        _modelo = SentenceTransformer(config.EMBEDDING_MODEL)
        cliente = chromadb.PersistentClient(path=str(config.DIR_VECTORSTORE))
        try:
            _coleccion = cliente.get_collection(config.RAG_COLECCION)
        except Exception as error:
            raise RuntimeError("No hay documentos indexados. Ejecutar: python -m src.rag.ingest") from error
    return _modelo, _coleccion


def precalentar() -> None:
    """Carga el modelo y el indice por adelantado (evita ~30 s en la primera pregunta)."""
    _cargar()


def buscar(pregunta: str, k: int = None, umbral: float = None) -> list:
    """Devuelve hasta `k` fragmentos con similitud >= `umbral`, del mas al menos parecido."""
    k = k or config.RAG_TOP_K
    umbral = config.RAG_UMBRAL if umbral is None else umbral

    modelo, coleccion = _cargar()
    consulta = modelo.encode([pregunta], normalize_embeddings=True).tolist()
    r = coleccion.query(query_embeddings=consulta, n_results=k)

    fragmentos = []
    for texto, meta, distancia in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
        similitud = 1.0 - distancia           # ChromaDB devuelve distancia coseno
        if similitud >= umbral:
            fragmentos.append(Fragmento(texto=texto, documento=meta["documento"],
                                        pagina=int(meta["pagina"]), similitud=round(similitud, 4)))
    return fragmentos


def formatear_contexto(fragmentos: list) -> str:
    """Texto listo para el prompt: cada fragmento precedido de su cita."""
    return "\n\n".join(f"{f.cita}\n{f.texto}" for f in fragmentos)
