"""Acceso al LLM (decision D-18, D-19). Es el UNICO modulo que conoce al proveedor.

Para cambiar de proveedor (por ejemplo a un modelo local) solo se modifica
`obtener_modelo()`; el resto del proyecto usa `invocar()`.

Nivel gratuito: se respeta una pausa minima entre llamadas (LLM_PAUSA_SEGUNDOS)
y se reintenta con espera creciente ante errores de cuota o saturacion.
"""
import time
import warnings

from src import config

# El modelo usa muestreo fijo e ignora "temperature"; el aviso es informativo y repetitivo.
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

REINTENTOS = 3
ESPERA_INICIAL_SEGUNDOS = 10

_modelo = None
_ultima_llamada = 0.0
espera_acumulada_s = 0.0   # segundos dormidos por pausas y reintentos (para medir la latencia neta)


def obtener_modelo():
    """Crea (una sola vez) el modelo de chat configurado en el .env."""
    global _modelo
    if _modelo is None:
        if config.LLM_PROVIDER != "gemini":
            raise ValueError(f"Proveedor de LLM no soportado: {config.LLM_PROVIDER!r}")
        if not config.GOOGLE_API_KEY or not config.LLM_MODEL:
            raise ValueError("Falta GOOGLE_API_KEY o LLM_MODEL en el archivo .env")
        from langchain_google_genai import ChatGoogleGenerativeAI

        _modelo = ChatGoogleGenerativeAI(
            model=config.LLM_MODEL,
            google_api_key=config.GOOGLE_API_KEY,
            # Sin 'temperature': este modelo usa valores de muestreo fijos e ignora el
            # parametro (aviso UserWarning). Las respuestas pueden variar entre corridas.
        )
    return _modelo


def _a_texto(contenido) -> str:
    """Normaliza el contenido de la respuesta (texto o lista de bloques)."""
    if isinstance(contenido, str):
        return contenido
    partes = []
    for bloque in contenido:
        if isinstance(bloque, str):
            partes.append(bloque)
        elif isinstance(bloque, dict) and bloque.get("type", "text") == "text":
            partes.append(bloque.get("text", ""))
    return "".join(partes)


def _es_error_transitorio(error: Exception) -> bool:
    """True si conviene reintentar (cuota por minuto, servicio saturado)."""
    texto = str(error).lower()
    return any(s in texto for s in
               ("429", "resource_exhausted", "quota", "rate limit", "503", "unavailable", "overloaded"))


def invocar(mensajes) -> str:
    """Envia `mensajes` al LLM y devuelve el texto de la respuesta.

    `mensajes` es una lista de tuplas (rol, texto) con rol "system", "human" o "ai".
    """
    global _ultima_llamada, espera_acumulada_s
    espera = ESPERA_INICIAL_SEGUNDOS
    for intento in range(REINTENTOS + 1):
        pausa = config.LLM_PAUSA_SEGUNDOS - (time.monotonic() - _ultima_llamada)
        if pausa > 0:
            time.sleep(pausa)
            espera_acumulada_s += pausa
        _ultima_llamada = time.monotonic()
        try:
            return _a_texto(obtener_modelo().invoke(mensajes).content).strip()
        except Exception as error:
            if intento < REINTENTOS and _es_error_transitorio(error):
                time.sleep(espera)
                espera_acumulada_s += espera
                espera *= 2
                continue
            raise
