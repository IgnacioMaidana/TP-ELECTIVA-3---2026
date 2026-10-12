"""Funciones puras de la suite de evaluacion (T-29, T-30): comparar resultados,
detectar idioma y resumir metricas. No usan LLM ni base de datos."""
import re
from decimal import Decimal

_ES = {"el", "la", "los", "las", "de", "que", "en", "y", "un", "una", "por", "con", "para", "es",
       "son", "se", "del", "al", "hay", "su", "más", "como", "tu", "sus", "este", "esta"}
_EN = {"the", "is", "are", "of", "and", "to", "in", "you", "your", "for", "with", "that", "this",
       "there", "have", "has", "not", "was", "were", "from", "can", "by", "an", "it", "on", "be"}

LIMITE_LATENCIA_S = 15      # RNF-03


def idioma_de_texto(texto: str) -> str:
    """Estima el idioma ("es" o "en") contando palabras funcionales de cada uno."""
    palabras = re.findall(r"[a-záéíóúñü]+", texto.lower())
    es = sum(p in _ES for p in palabras)
    en = sum(p in _EN for p in palabras)
    return "es" if es > en else "en" if en > es else "?"


def _numero(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    return None


def coincide_valor(ref, obtenido, tolerancia: float = 0.01) -> bool:
    """Un valor de referencia coincide con uno obtenido: numeros con tolerancia,
    textos por inclusion (sin importar mayusculas)."""
    if obtenido is None:
        return ref is None
    r = _numero(ref)
    if r is not None:
        o = _numero(obtenido)
        if o is None:
            try:
                o = float(str(obtenido).strip())
            except ValueError:
                return False
        return abs(r - o) <= tolerancia
    return str(ref).strip().lower() in str(obtenido).strip().lower()


def fila_contenida(ref_fila: dict, obt_fila: dict, tolerancia: float = 0.01) -> bool:
    """Todos los valores de la fila de referencia aparecen en la fila obtenida
    (que puede tener columnas extra y en otro orden)."""
    obtenidos = list(obt_fila.values())
    return all(any(coincide_valor(r, o, tolerancia) for o in obtenidos) for r in ref_fila.values())


def comparar_filas(ref_filas: list, obt_filas: list, exacto: bool = False,
                   tolerancia: float = 0.01):
    """Compara el resultado de referencia con el del agente. Devuelve (ok, detalle)."""
    if not ref_filas:
        return len(obt_filas) == 0, f"se esperaban 0 filas y el agente devolvió {len(obt_filas)}"
    if not obt_filas:
        return False, "el agente no devolvió filas"
    if exacto and len(ref_filas) != len(obt_filas):
        return False, f"se esperaban {len(ref_filas)} filas y el agente devolvió {len(obt_filas)}"
    faltan = [r for r in ref_filas if not any(fila_contenida(r, o, tolerancia) for o in obt_filas)]
    if faltan:
        return False, f"faltan {len(faltan)} fila(s) de referencia, por ejemplo {faltan[0]}"
    return True, ""


def contiene_todas(texto: str, claves: list) -> bool:
    t = texto.lower()
    return all(c.lower() in t for c in claves)


def contiene_alguna(texto: str, claves: list) -> bool:
    t = texto.lower()
    return any(c.lower() in t for c in claves)


def resumir(resultados: list) -> dict:
    """Metricas por tipo de pregunta y total. Cada resultado es un diccionario del runner."""
    def calcular(grupo):
        n = len(grupo)
        if n == 0:
            return {"n": 0}
        pct = lambda k: round(100 * sum(1 for r in grupo if r[k]) / n)
        aprobadas = sum(1 for r in grupo if r["aprobada"])
        latencias = [r["latencia_s"] for r in grupo if r.get("latencia_s") is not None]
        netas = [r["latencia_neta_s"] for r in grupo if r.get("latencia_neta_s") is not None]
        return {
            "n": n, "aprobadas": aprobadas, "pct_aprobadas": round(100 * aprobadas / n),
            "pct_ruta": pct("ruta_ok"), "pct_respuesta": pct("respuesta_ok"),
            "pct_idioma": pct("idioma_ok"), "pct_seguro": pct("seguro"),
            "latencia_media_s": round(sum(latencias) / len(latencias), 1) if latencias else None,
            "latencia_neta_media_s": round(sum(netas) / len(netas), 1) if netas else None,
            "pct_bajo_limite": round(100 * sum(l <= LIMITE_LATENCIA_S for l in latencias) / len(latencias))
            if latencias else None,
        }

    tipos = sorted({r["tipo"] for r in resultados})
    resumen = {t: calcular([r for r in resultados if r["tipo"] == t]) for t in tipos}
    resumen["TOTAL"] = calcular(resultados)
    return resumen
