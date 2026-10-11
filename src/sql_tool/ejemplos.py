"""Ejemplos pregunta -> T-SQL que se muestran al LLM (T-11, few-shot).

Cada ejemplo ensena UNA idea al modelo (ver el campo "ensena"). Reglas:
  - El SQL de cada ejemplo debe pasar validar_sql() y ejecutarse sin error;
    tests/test_ejemplos_sql.py lo comprueba.
  - Las definiciones de negocio (venta valida, buena resena, plazo de
    devolucion...) deben coincidir con spec.md seccion 3.3 y con el prompt.
  - Hay preguntas en castellano e ingles (RF-01, RF-02).
"""

EJEMPLOS = [
    {
        "pregunta": "¿Cuántos clientes compran por cada categoría?",
        "ensena": "COUNT DISTINCT, JOIN de 4 tablas y venta válida",
        "sql": (
            "SELECT cat.nombre AS categoria, COUNT(DISTINCT p.id_cliente) AS clientes\n"
            "FROM pedidos p\n"
            "JOIN detalle_pedidos d ON d.id_pedido = p.id_pedido\n"
            "JOIN productos pr ON pr.id_producto = d.id_producto\n"
            "JOIN categorias cat ON cat.id_categoria = pr.id_categoria\n"
            "WHERE p.estado IN ('pagado', 'enviado', 'entregado')\n"
            "GROUP BY cat.nombre\n"
            "ORDER BY clientes DESC"
        ),
    },
    {
        "pregunta": "¿Cuántas buenas reseñas (mayores a 3) hay?",
        "ensena": "definición de buena reseña y conteo simple",
        "sql": "SELECT COUNT(*) AS buenas_resenas FROM resenas WHERE calificacion > 3",
    },
    {
        "pregunta": "¿Cuántos pedidos se entregaron después de la fecha estimada?",
        "ensena": "comparar dos columnas de fecha de la misma tabla",
        "sql": (
            "SELECT COUNT(*) AS entregas_tardias\n"
            "FROM envios\n"
            "WHERE estado_envio = 'entregado'\n"
            "  AND fecha_entrega_real > fecha_entrega_estimada"
        ),
    },
    {
        "pregunta": "What is the best-selling product?",
        "ensena": "pregunta en inglés, ranking con TOP 1 y unidades vendidas",
        "sql": (
            "SELECT TOP 1 pr.nombre AS producto, SUM(d.cantidad) AS unidades_vendidas\n"
            "FROM detalle_pedidos d\n"
            "JOIN productos pr ON pr.id_producto = d.id_producto\n"
            "JOIN pedidos p ON p.id_pedido = d.id_pedido\n"
            "WHERE p.estado IN ('pagado', 'enviado', 'entregado')\n"
            "GROUP BY pr.id_producto, pr.nombre\n"
            "ORDER BY unidades_vendidas DESC"
        ),
    },
    {
        "pregunta": "¿Qué categoría tiene más ventas?",
        "ensena": "ventas = ingresos (SUM de subtotal), no unidades",
        "sql": (
            "SELECT TOP 1 cat.nombre AS categoria, SUM(d.subtotal) AS ingresos\n"
            "FROM detalle_pedidos d\n"
            "JOIN productos pr ON pr.id_producto = d.id_producto\n"
            "JOIN categorias cat ON cat.id_categoria = pr.id_categoria\n"
            "JOIN pedidos p ON p.id_pedido = d.id_pedido\n"
            "WHERE p.estado IN ('pagado', 'enviado', 'entregado')\n"
            "GROUP BY cat.id_categoria, cat.nombre\n"
            "ORDER BY ingresos DESC"
        ),
    },
    {
        "pregunta": "¿Qué pedidos del cliente 12 siguen dentro del plazo de devolución?",
        "ensena": "regla de 30 días desde la entrega real (RF-17)",
        "sql": (
            "SELECT p.id_pedido, e.fecha_entrega_real,\n"
            "       DATEDIFF(DAY, e.fecha_entrega_real, CAST(GETDATE() AS DATE)) AS dias_desde_entrega\n"
            "FROM pedidos p\n"
            "JOIN envios e ON e.id_pedido = p.id_pedido\n"
            "WHERE p.id_cliente = 12\n"
            "  AND p.estado = 'entregado'\n"
            "  AND e.estado_envio = 'entregado'\n"
            "  AND DATEDIFF(DAY, e.fecha_entrega_real, CAST(GETDATE() AS DATE)) <= 30\n"
            "ORDER BY e.fecha_entrega_real DESC"
        ),
    },
    {
        "pregunta": "What were the top 5 best-selling products last month?",
        "ensena": "rango de fechas del mes anterior",
        "sql": (
            "SELECT TOP 5 pr.nombre AS producto, SUM(d.cantidad) AS unidades_vendidas\n"
            "FROM detalle_pedidos d\n"
            "JOIN productos pr ON pr.id_producto = d.id_producto\n"
            "JOIN pedidos p ON p.id_pedido = d.id_pedido\n"
            "WHERE p.estado IN ('pagado', 'enviado', 'entregado')\n"
            "  AND p.fecha_pedido >= DATEFROMPARTS(YEAR(DATEADD(MONTH, -1, GETDATE())),\n"
            "                                      MONTH(DATEADD(MONTH, -1, GETDATE())), 1)\n"
            "  AND p.fecha_pedido < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)\n"
            "GROUP BY pr.id_producto, pr.nombre\n"
            "ORDER BY unidades_vendidas DESC"
        ),
    },
    {
        "pregunta": "¿Qué productos tienen una calificación promedio menor a 3?",
        "ensena": "promedio con CAST a FLOAT y HAVING",
        "sql": (
            "SELECT pr.nombre AS producto,\n"
            "       AVG(CAST(r.calificacion AS FLOAT)) AS promedio,\n"
            "       COUNT(*) AS cantidad_resenas\n"
            "FROM resenas r\n"
            "JOIN productos pr ON pr.id_producto = r.id_producto\n"
            "GROUP BY pr.id_producto, pr.nombre\n"
            "HAVING AVG(CAST(r.calificacion AS FLOAT)) < 3\n"
            "ORDER BY promedio"
        ),
    },
    {
        "pregunta": "¿Cuántos pedidos, ingresos y unidades vendimos el mes pasado?",
        "ensena": "al unir pedidos con detalle_pedidos NO sumar pedidos.total ni contar pedidos sin DISTINCT",
        "sql": (
            "SELECT COUNT(DISTINCT p.id_pedido) AS total_pedidos,\n"
            "       SUM(d.subtotal) AS ingresos,\n"
            "       SUM(d.cantidad) AS unidades\n"
            "FROM pedidos p\n"
            "JOIN detalle_pedidos d ON d.id_pedido = p.id_pedido\n"
            "WHERE p.estado IN ('pagado', 'enviado', 'entregado')\n"
            "  AND p.fecha_pedido >= DATEFROMPARTS(YEAR(DATEADD(MONTH, -1, GETDATE())),\n"
            "                                      MONTH(DATEADD(MONTH, -1, GETDATE())), 1)\n"
            "  AND p.fecha_pedido < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"
        ),
    },
]
