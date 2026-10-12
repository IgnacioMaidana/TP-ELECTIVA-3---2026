"""Verificacion barata del idioma de la pregunta.

El router (LLM) a veces se equivoca con preguntas cortas o llenas de terminos de la base
("run: UPDATE clientes SET activo = 0") y responde en el idioma equivocado. Esta funcion
cuenta palabras funcionales de cada idioma y corrige al router solo cuando la evidencia
es clara: al menos 2 palabras de un idioma y ninguna del otro.
"""
import re

_ES = {"el", "la", "los", "las", "de", "que", "en", "y", "un", "una", "por", "con", "para", "es",
       "son", "se", "del", "al", "hay", "su", "más", "como", "tu", "sus", "este", "esta", "qué",
       "cuál", "cuáles", "cuántos", "cuántas", "cómo", "quién", "dónde", "cuándo", "sobre", "entre",
       "pero", "muy", "también", "lo", "mi", "tienen", "tiene", "están", "fueron", "puedo", "dame"}
_EN = {"the", "is", "are", "of", "and", "to", "in", "you", "your", "for", "with", "that", "this",
       "there", "have", "has", "not", "was", "were", "from", "can", "by", "an", "it", "on", "be",
       "what", "which", "how", "many", "much", "does", "do", "did", "any", "than", "more", "most",
       "each", "about", "who", "when", "where", "show", "give", "pretend", "run", "ignore"}


def contar_palabras(texto: str):
    """Devuelve (palabras en castellano, palabras en ingles) encontradas en el texto."""
    palabras = re.findall(r"[a-záéíóúñü]+", texto.lower())
    return sum(p in _ES for p in palabras), sum(p in _EN for p in palabras)


def corregir_idioma(texto: str, idioma_router: str) -> str:
    """Devuelve el idioma del router, salvo que el texto lo contradiga con claridad."""
    es, en = contar_palabras(texto)
    if en >= 2 and es == 0:
        return "en"
    if es >= 2 and en == 0:
        return "es"
    return idioma_router
