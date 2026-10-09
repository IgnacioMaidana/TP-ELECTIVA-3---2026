"""Verifica que los datos cargados cumplan el enunciado y las reglas de consistencia.

Uso:  python -m scripts.verificar_datos
Sale con codigo 1 si alguna comprobacion falla.
"""
import sys

from scripts.generar_datos import CLIENTE_CASOS_LIMITE
from src.db import get_connection

TABLAS = ["categorias", "clientes", "productos", "pedidos",
          "detalle_pedidos", "envios", "resenas"]
MINIMO_FILAS = 16  # "mas de 15 registros por tabla"

# Cada comprobacion: (descripcion, consulta que cuenta filas INCORRECTAS; debe dar 0)
COMPROBACIONES = [
    ("pedidos.total = suma de subtotales",
     """SELECT COUNT(*) FROM dbo.pedidos p
        LEFT JOIN (SELECT id_pedido, SUM(subtotal) AS s FROM dbo.detalle_pedidos
                   GROUP BY id_pedido) d ON d.id_pedido = p.id_pedido
        WHERE p.total <> ISNULL(d.s, 0)"""),
    ("todo pedido tiene al menos una linea",
     """SELECT COUNT(*) FROM dbo.pedidos p
        WHERE NOT EXISTS (SELECT 1 FROM dbo.detalle_pedidos d WHERE d.id_pedido = p.id_pedido)"""),
    ("pedidos pendiente/pagado/cancelado no tienen envio",
     """SELECT COUNT(*) FROM dbo.envios e JOIN dbo.pedidos p ON p.id_pedido = e.id_pedido
        WHERE p.estado IN (N'pendiente', N'pagado', N'cancelado')"""),
    ("pedidos enviado/entregado/devuelto tienen envio",
     """SELECT COUNT(*) FROM dbo.pedidos p
        WHERE p.estado IN (N'enviado', N'entregado', N'devuelto')
          AND NOT EXISTS (SELECT 1 FROM dbo.envios e WHERE e.id_pedido = p.id_pedido)"""),
    ("fecha_entrega_real solo si el envio esta entregado",
     """SELECT COUNT(*) FROM dbo.envios
        WHERE (estado_envio = N'entregado' AND fecha_entrega_real IS NULL)
           OR (estado_envio <> N'entregado' AND fecha_entrega_real IS NOT NULL)"""),
    ("entrega posterior al envio y no futura",
     """SELECT COUNT(*) FROM dbo.envios
        WHERE fecha_entrega_real < fecha_envio
           OR fecha_entrega_real > CAST(GETDATE() AS DATE)"""),
    ("pedidos enviado tienen envio en transito",
     """SELECT COUNT(*) FROM dbo.pedidos p JOIN dbo.envios e ON e.id_pedido = p.id_pedido
        WHERE p.estado = N'enviado' AND e.estado_envio <> N'en_transito'"""),
    ("resenas solo de clientes que recibieron el producto",
     """SELECT COUNT(*) FROM dbo.resenas r
        WHERE NOT EXISTS (
            SELECT 1 FROM dbo.detalle_pedidos d
            JOIN dbo.pedidos p ON p.id_pedido = d.id_pedido
            JOIN dbo.envios e ON e.id_pedido = p.id_pedido
            WHERE p.id_cliente = r.id_cliente AND d.id_producto = r.id_producto
              AND e.fecha_entrega_real IS NOT NULL)"""),
    ("pedidos posteriores al registro del cliente",
     """SELECT COUNT(*) FROM dbo.pedidos p JOIN dbo.clientes c ON c.id_cliente = p.id_cliente
        WHERE CAST(p.fecha_pedido AS DATE) < c.fecha_registro"""),
]


def main() -> int:
    fallos = 0
    with get_connection(admin=True) as con:
        print(f"1) Filas por tabla (minimo exigido: {MINIMO_FILAS})")
        for t in TABLAS:
            n = con.execute(f"SELECT COUNT(*) FROM dbo.{t}").fetchone()[0]
            ok = n >= MINIMO_FILAS
            fallos += not ok
            print(f"   [{'OK' if ok else 'FALLA'}] {t:<16} {n:>5}")

        print("\n2) Reglas de consistencia (deben dar 0 filas incorrectas)")
        for descripcion, sql in COMPROBACIONES:
            n = con.execute(sql).fetchone()[0]
            fallos += n != 0
            print(f"   [{'OK' if n == 0 else 'FALLA'}] {descripcion}  (incorrectas: {n})")

        print(f"\n3) Casos limite del cliente {CLIENTE_CASOS_LIMITE} (regla de 30 dias, RF-17)")
        filas = con.execute(
            """SELECT p.id_pedido, p.estado, e.estado_envio, e.fecha_entrega_real,
                      DATEDIFF(DAY, e.fecha_entrega_real, CAST(GETDATE() AS DATE)) AS dias
               FROM dbo.pedidos p LEFT JOIN dbo.envios e ON e.id_pedido = p.id_pedido
               WHERE p.id_cliente = ? AND (e.fecha_entrega_real IS NOT NULL
                     OR p.estado IN (N'enviado', N'cancelado'))
               ORDER BY p.fecha_pedido""", CLIENTE_CASOS_LIMITE).fetchall()
        print("   id_pedido  estado      envio        entrega_real  dias_desde_entrega")
        for f in filas:
            dias = "-" if f.dias is None else f.dias
            print(f"   {f.id_pedido:<10} {f.estado:<11} {str(f.estado_envio):<12} "
                  f"{str(f.fecha_entrega_real):<13} {dias}")
        print("   (si se generaron hoy, deben aparecer 5, 29, 30, 31 y 60 dias)")

    print("\nRESULTADO:", "TODO OK" if fallos == 0 else f"{fallos} comprobaciones fallaron")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
