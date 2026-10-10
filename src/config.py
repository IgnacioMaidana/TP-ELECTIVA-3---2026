"""Configuracion central del proyecto.

Lee las variables del archivo .env (en la raiz del repositorio) y las expone
como constantes. Ningun otro modulo debe leer os.environ directamente.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def _bool(nombre: str, defecto: bool = False) -> bool:
    """Convierte una variable de entorno a booleano (yes/true/1/si)."""
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "yes", "si", "sí"}


# --- LLM (nivel gratuito) ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_PAUSA_SEGUNDOS = float(os.getenv("LLM_PAUSA_SEGUNDOS", "4"))

# --- SQL Server ---
DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_NAME = os.getenv("DB_NAME", "EcommerceTech")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
DB_TRUST_CERT = _bool("DB_TRUST_CERT", True)

# Conexion de administracion (solo scripts de carga de datos)
DB_ADMIN_TRUSTED = _bool("DB_ADMIN_TRUSTED", True)
DB_ADMIN_USER = os.getenv("DB_ADMIN_USER", "")
DB_ADMIN_PASSWORD = os.getenv("DB_ADMIN_PASSWORD", "")

# Conexion de solo lectura (la usa el agente)
DB_USER = os.getenv("DB_USER", "agente_ro")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# --- RAG ---
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
)
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))

# --- SQL ---
SQL_MAX_ROWS = int(os.getenv("SQL_MAX_ROWS", "100"))
SQL_RETRIES = int(os.getenv("SQL_RETRIES", "2"))
SQL_TIMEOUT_SEGUNDOS = int(os.getenv("SQL_TIMEOUT_SEGUNDOS", "15"))

# --- Observabilidad ---
LANGSMITH_TRACING = _bool("LANGSMITH_TRACING", False)
