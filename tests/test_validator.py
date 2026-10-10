"""Pruebas del validador de SQL (T-13). Cubre RF-13, RNF-01, CA-11, CA-12.

Contrato:  validar_sql(sql) -> objeto con
    .ok      bool   True si se puede ejecutar
    .motivo  str    por que se rechazo (vacio si ok)
    .sql     str    SQL final listo para ejecutar (con TOP si faltaba)
"""
import pytest

from src.sql_tool.validator import validar_sql

# ---------------------------------------------------------------------------
# 1) Consultas que SI deben aceptarse
# ---------------------------------------------------------------------------
PERMITIDAS = [
    # --- basicas ---
    "SELECT COUNT(*) FROM dbo.clientes",
    "SELECT TOP 5 nombre, precio FROM productos ORDER BY precio DESC",
    "SELECT pais, COUNT(*) AS total FROM clientes GROUP BY pais",
    "select  *  from CLIENTES",                       # mayusculas/minusculas y espacios
    "SELECT 1",
    "SELECT 1;",                                      # un unico ';' final se tolera
    "SELECT * FROM clientes;\n",
    # --- CTE ---
    "WITH v AS (SELECT id_producto, SUM(cantidad) AS u FROM detalle_pedidos "
    "GROUP BY id_producto) SELECT TOP 3 * FROM v ORDER BY u DESC",
    # --- JOINs ---
    "SELECT TOP 10 c.nombre, c.apellido, p.id_pedido, e.estado_envio "
    "FROM pedidos p JOIN clientes c ON c.id_cliente = p.id_cliente "
    "JOIN envios e ON e.id_pedido = p.id_pedido WHERE e.estado_envio = 'en_transito'",
    "SELECT cat.nombre AS categoria, SUM(d.subtotal) AS ingresos "
    "FROM detalle_pedidos d JOIN productos pr ON pr.id_producto = d.id_producto "
    "JOIN categorias cat ON cat.id_categoria = pr.id_categoria "
    "JOIN pedidos p ON p.id_pedido = d.id_pedido "
    "WHERE p.estado <> 'cancelado' GROUP BY cat.nombre ORDER BY ingresos DESC",
    "SELECT c.nombre, COUNT(p.id_pedido) AS pedidos "
    "FROM clientes c LEFT JOIN pedidos p ON p.id_cliente = c.id_cliente "
    "GROUP BY c.nombre",
    # regla de devolucion (30 dias desde la entrega real)
    "SELECT p.id_pedido, e.fecha_entrega_real FROM pedidos p "
    "JOIN envios e ON e.id_pedido = p.id_pedido "
    "WHERE p.id_cliente = 12 AND e.fecha_entrega_real IS NOT NULL "
    "AND DATEDIFF(DAY, e.fecha_entrega_real, GETDATE()) <= 30",
    # --- subconsultas ---
    "SELECT nombre FROM productos WHERE id_producto IN "
    "(SELECT id_producto FROM resenas WHERE calificacion = 5)",
    "SELECT nombre, precio FROM productos WHERE precio > (SELECT AVG(precio) FROM productos)",
    "SELECT c.nombre FROM clientes c WHERE NOT EXISTS "
    "(SELECT 1 FROM pedidos p WHERE p.id_cliente = c.id_cliente)",
    "SELECT t.pais, t.total FROM (SELECT pais, COUNT(*) AS total FROM clientes GROUP BY pais) t "
    "WHERE t.total > 5",
    "SELECT id_cliente, COUNT(*) AS n FROM pedidos GROUP BY id_cliente HAVING COUNT(*) > 5",
    # --- textos que contienen palabras o simbolos "peligrosos" (son datos, no codigo) ---
    "SELECT * FROM clientes WHERE nombre = 'DROP TABLE'",
    "SELECT * FROM clientes WHERE nombre = 'a--b'",
    "SELECT TOP 5 * FROM resenas WHERE comentario LIKE '%update%'",
]


@pytest.mark.parametrize("sql", PERMITIDAS)
def test_consultas_legitimas_se_aceptan(sql):
    resultado = validar_sql(sql)
    assert resultado.ok, f"Deberia aceptarse: {sql!r} -> {resultado.motivo}"


# ---------------------------------------------------------------------------
# 2) Consultas que DEBEN rechazarse: (sql, por que es peligrosa)
# ---------------------------------------------------------------------------
BLOQUEADAS = [
    # --- ejecucion de comandos del sistema operativo ---
    ("EXEC xp_cmdshell 'dir'", "xp_cmdshell"),
    ("exec master..xp_cmdshell 'whoami'", "xp_cmdshell con prefijo de base"),
    ("EXEC sp_configure 'xp_cmdshell', 1", "procedimiento de sistema"),
    ("COPY clientes FROM PROGRAM 'cmd.exe /c dir'", "COPY ... FROM PROGRAM"),
    ("LOAD DATA INFILE '/etc/passwd' INTO TABLE clientes", "LOAD DATA INFILE"),
    ("SELECT * FROM clientes INTO OUTFILE '/tmp/clientes.txt'", "INTO OUTFILE"),
    # --- destruccion de datos ---
    ("TRUNCATE TABLE pedidos", "TRUNCATE"),
    ("DELETE FROM clientes", "DELETE sin filtro"),
    ("DELETE FROM clientes WHERE id_cliente = 1", "DELETE con filtro"),
    ("ALTER TABLE clientes ADD columna_nueva INT", "ALTER TABLE"),
    ("DROP TABLE clientes", "DROP TABLE"),
    ("DROP DATABASE EcommerceTech", "DROP DATABASE"),
    # --- modificacion de permisos ---
    ("GRANT ALL PRIVILEGES ON clientes TO public", "GRANT"),
    ("CREATE USER hacker FOR LOGIN hacker", "CREATE USER"),
    ("ALTER USER agente_ro WITH PASSWORD = 'x'", "ALTER USER"),
    ("REVOKE SELECT ON clientes FROM agente_ro", "REVOKE"),
    # --- patrones de bypass ---
    ("SELECT * FROM clientes WHERE nombre = 'x' OR 1=1", "tautologia numerica"),
    ("SELECT * FROM clientes WHERE nombre = 'x' OR 'a'='a'", "tautologia de texto"),
    ("SELECT nombre FROM clientes UNION SELECT name FROM sys.sql_logins", "UNION SELECT"),
    ("SELECT * FROM clientes UNION ALL SELECT * FROM clientes", "UNION ALL"),
    ("SELECT * FROM clientes -- comentario", "comentario de linea"),
    ("SELECT * FROM clientes /* comentario */", "comentario de bloque"),
    ("SELECT * FROM clientes WHERE id_cliente = 1 -- AND activo = 1", "comentario que anula condiciones"),
    # --- mayusculas y minusculas mezcladas ---
    ("dRoP tAbLe clientes", "DROP con mayusculas mezcladas"),
    ("DeLeTe FrOm pedidos", "DELETE con mayusculas mezcladas"),
    ("SeLeCt * FrOm clientes; DrOp TaBlE clientes", "sentencias encadenadas"),
    # --- INSERT / UPDATE (incluso disfrazados) ---
    ("INSERT INTO categorias (nombre) VALUES ('x')", "INSERT directo"),
    ("UPDATE productos SET precio = 0", "UPDATE directo"),
    ("SELECT * FROM clientes; INSERT INTO categorias (nombre) VALUES ('x')", "INSERT encadenado"),
    ("SELECT 1 /* ; */ INSERT INTO clientes (nombre) VALUES ('x')", "INSERT tras comentario"),
    ("SELECT * FROM clientes -- ; INSERT INTO categorias (nombre) VALUES ('x')", "INSERT dentro de comentario"),
    ("SELECT * FROM clientes WHERE 1=1; UPDATE productos SET precio = 0", "UPDATE encadenado"),
    # --- otras bases, sistema y tablas no permitidas ---
    ("SELECT * FROM master.dbo.sysdatabases", "otra base de datos"),
    ("SELECT * FROM msdb.dbo.sysjobs", "base msdb"),
    ("SELECT * FROM sys.sql_logins", "tabla del sistema"),
    ("SELECT * FROM INFORMATION_SCHEMA.TABLES", "metadatos"),
    ("SELECT * FROM otra_tabla", "tabla fuera de las 7 permitidas"),
    ("USE master", "cambio de base"),
    # --- otros ---
    ("SELECT * INTO copia FROM clientes", "SELECT INTO crea una tabla"),
    ("WAITFOR DELAY '00:00:30'", "puede colgar el servidor"),
    ("SELECT * FROM clientes; WAITFOR DELAY '00:00:30'", "WAITFOR encadenado"),
    ("SELECT * FROM OPENROWSET('SQLNCLI', 'Server=x;', 'SELECT 1')", "fuente externa"),
    ("SELECT * FROM OPENQUERY(servidor, 'SELECT 1')", "servidor vinculado"),
    ("SELECT @@version", "variables del sistema"),
    ("SELECT * FROM clientes; DROP TABLE clientes", "dos sentencias"),
    ("SELECT 1;;", "punto y coma duplicado"),
    ("SELECT * FROM clientes WHERE nombre = 'abc", "comilla sin cerrar"),
    ("", "consulta vacia"),
    ("   ", "solo espacios"),
]


@pytest.mark.parametrize("sql,motivo", BLOQUEADAS)
def test_consultas_peligrosas_se_rechazan(sql, motivo):
    resultado = validar_sql(sql)
    assert not resultado.ok, f"Deberia rechazarse ({motivo}): {sql!r}"
    assert resultado.motivo, "Un rechazo debe explicar el motivo"
    assert resultado.sql == "", "Un rechazo no debe devolver SQL ejecutable"


# ---------------------------------------------------------------------------
# 3) Comportamiento: el validador tambien transforma el SQL
# ---------------------------------------------------------------------------
def test_agrega_top_si_falta():
    resultado = validar_sql("SELECT * FROM productos")
    assert resultado.ok
    assert "TOP" in resultado.sql.upper()


def test_agrega_top_con_el_limite_pedido():
    resultado = validar_sql("SELECT * FROM productos", max_filas=25)
    assert "TOP 25" in resultado.sql.upper()


def test_respeta_top_existente():
    resultado = validar_sql("SELECT TOP 5 * FROM productos")
    assert resultado.sql.upper().count("TOP") == 1


def test_quita_el_punto_y_coma_final():
    resultado = validar_sql("SELECT TOP 5 * FROM productos;")
    assert resultado.ok
    assert not resultado.sql.rstrip().endswith(";")


# ---------------------------------------------------------------------------
# 4) Decisiones de diseno (reglas de negocio, tambien documentadas en el plan)
# ---------------------------------------------------------------------------
# - "SELECT 1;"                    -> SE ACEPTA (un solo ';' final)
# - cualquier comentario -- o /* */ -> SE RECHAZA
# - "... WHERE nombre = 'DROP TABLE'" -> SE ACEPTA: es un dato entre comillas.
#   El analisis de sintaxis separa codigo de datos; rechazarla seria un falso
#   positivo que bloquearia busquedas legitimas (por ejemplo resenas que
#   mencionen "update"). El riesgo no cambia: un texto no se ejecuta.
# - WAITFOR y fuentes externas (OPENROWSET, OPENQUERY...) -> SE RECHAZAN
