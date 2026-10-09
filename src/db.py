"""Conexiones a SQL Server.

Dos perfiles:
  - admin=True : permisos de escritura. SOLO para scripts de carga de datos.
  - admin=False: usuario de solo lectura (agente_ro). Es el que usa el agente.

Autoprueba:  python -m src.db
"""
import pyodbc

from src import config


def _cadena_conexion(admin: bool) -> str:
    """Arma la cadena de conexion segun el perfil solicitado."""
    partes = [
        f"DRIVER={{{config.DB_DRIVER}}}",
        f"SERVER={config.DB_SERVER}",
        f"DATABASE={config.DB_NAME}",
    ]
    if admin and config.DB_ADMIN_TRUSTED:
        partes.append("Trusted_Connection=yes")
    elif admin:
        partes += [f"UID={config.DB_ADMIN_USER}", f"PWD={config.DB_ADMIN_PASSWORD}"]
    else:
        partes += [f"UID={config.DB_USER}", f"PWD={config.DB_PASSWORD}"]
    if config.DB_TRUST_CERT:
        partes.append("TrustServerCertificate=yes")
    return ";".join(partes)


def get_connection(admin: bool = False, timeout: int = 15) -> pyodbc.Connection:
    """Devuelve una conexion nueva. El llamador es responsable de cerrarla."""
    return pyodbc.connect(_cadena_conexion(admin), timeout=timeout)


def _autoprueba() -> None:
    """Verifica ambas conexiones y que el usuario de lectura NO pueda escribir."""
    print("Drivers ODBC disponibles:", pyodbc.drivers())

    print("\n[1] Conexion ADMIN")
    with get_connection(admin=True) as con:
        usuario = con.execute("SELECT SUSER_SNAME()").fetchone()[0]
        print("    OK, conectado como:", usuario)

    print("\n[2] Conexion SOLO LECTURA")
    with get_connection(admin=False) as con:
        usuario = con.execute("SELECT SUSER_SNAME()").fetchone()[0]
        print("    OK, conectado como:", usuario)
        try:
            n = con.execute("SELECT COUNT(*) FROM dbo.categorias").fetchone()[0]
            print("    Lectura OK (filas en categorias):", n)
        except pyodbc.Error as e:
            print("    Lectura fallo:", e)

        try:
            con.execute("INSERT INTO dbo.categorias (nombre) VALUES (N'prueba_escritura')")
            con.rollback()
            print("    ATENCION: el usuario PUDO escribir. Revisar permisos.")
        except pyodbc.Error as e:
            print("    Escritura bloqueada correctamente:", str(e)[:90])


if __name__ == "__main__":
    _autoprueba()
