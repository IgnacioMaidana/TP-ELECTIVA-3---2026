"""Genera y carga datos sinteticos en la base EcommerceTech.

Uso (desde la raiz del repositorio, con el entorno virtual activo):

    python -m scripts.generar_datos                 # genera y carga en SQL Server
    python -m scripts.generar_datos --sin-bd        # solo genera y resume (no toca la BD)
    python -m scripts.generar_datos --hoy 2026-10-08  # fija la "fecha de hoy"

Caracteristicas:
  - Semilla fija (SEMILLA): mismos datos en cada ejecucion para una misma fecha.
  - Las fechas son relativas a "hoy" (pedidos de los ultimos 12 meses).
  - Es re-ejecutable: borra los datos existentes y vuelve a cargarlos.
  - Usa la conexion de ADMINISTRACION (el usuario agente_ro no puede escribir).
  - Moneda: dolares estadounidenses (USD).

Reglas de consistencia:
  - pedidos.total = suma de detalle_pedidos.subtotal.
  - Solo hay envio para pedidos en estado enviado, entregado o devuelto.
  - fecha_entrega_real existe solo si el envio esta entregado.
  - Las resenas son de clientes que recibieron ese producto.
  - El cliente CLIENTE_CASOS_LIMITE tiene pedidos entregados hace 5, 29, 30,
    31 y 60 dias, mas uno devuelto, uno en transito y uno cancelado, para
    probar la regla de devolucion de 30 dias desde la entrega (RF-17).
"""
import argparse
import random
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from faker import Faker

SEMILLA = 42
N_CLIENTES = 60
N_PEDIDOS = 250
N_RESENAS = 120
CLIENTE_CASOS_LIMITE = 12

# ---------------------------------------------------------------------------
# Catalogo fijo: (categoria, descripcion, garantia_meses, [(nombre, marca, descripcion, precio)])
# 16 categorias x 3 productos = 48 productos. Marcas ficticias.
# La garantia es por categoria y debe coincidir con el PDF de politicas.
# ---------------------------------------------------------------------------
CATALOGO = [
    ("Notebooks", "Computadoras portátiles para trabajo, estudio y uso general", 12, [
        ("Aurora Book 14", "Aurora", "Notebook ultraliviana de 14 pulgadas, 16 GB de RAM y SSD de 512 GB", 899),
        ("Aurora Book 15 Pro", "Aurora", "Notebook de 15.6 pulgadas, 32 GB de RAM y SSD de 1 TB", 1499),
        ("Nordik Flex 13", "Nordik", "Notebook 2 en 1 convertible de 13 pulgadas, 16 GB de RAM y SSD de 512 GB", 1099)]),
    ("Smartphones", "Teléfonos inteligentes de distintas gamas", 12, [
        ("Vexa S5", "Vexa", "Smartphone de 6.5 pulgadas, 128 GB de almacenamiento y batería de 4500 mAh", 329),
        ("Vexa S5 Pro", "Vexa", "Smartphone de 6.7 pulgadas, 256 GB y triple cámara", 599),
        ("Pulsar X", "Pulsar", "Smartphone de 6.1 pulgadas con pantalla OLED, 256 GB y conectividad 5G", 849)]),
    ("Tablets", "Tabletas para lectura, estudio y entretenimiento", 12, [
        ("Orbix Tab 10", "Orbix", "Tablet de 10.1 pulgadas con 64 GB de almacenamiento", 199),
        ("Orbix Tab 11 Pro", "Orbix", "Tablet de 11 pulgadas, 128 GB, con lápiz óptico incluido", 449),
        ("Kairo Pad 8", "Kairo", "Tablet compacta de 8 pulgadas con 32 GB de almacenamiento", 129)]),
    ("Monitores", "Pantallas para escritorio, oficina y diseño", 24, [
        ("Helix 24 FHD", "Helix", "Monitor IPS de 24 pulgadas Full HD a 75 Hz", 159),
        ("Helix 27 QHD", "Helix", "Monitor de 27 pulgadas resolución QHD a 144 Hz", 329),
        ("Tekna UltraWide 34", "Tekna", "Monitor curvo ultrapanorámico de 34 pulgadas a 100 Hz", 549)]),
    ("Teclados", "Teclados mecánicos, inalámbricos y compactos", 12, [
        ("Tekna K1 Mecánico", "Tekna", "Teclado mecánico retroiluminado con switches rojos", 69),
        ("Tekna K3 Inalámbrico", "Tekna", "Teclado inalámbrico de tamaño completo con receptor USB", 49),
        ("Nordik Slim Bluetooth", "Nordik", "Teclado delgado con conexión Bluetooth para varios dispositivos", 39)]),
    ("Mouses", "Mouses ópticos, ergonómicos y para juegos", 12, [
        ("Kairo M1", "Kairo", "Mouse óptico inalámbrico de 1600 DPI", 19),
        ("Kairo M5 Gamer", "Kairo", "Mouse gamer con iluminación RGB y sensor de 16000 DPI", 49),
        ("Nordik Ergo", "Nordik", "Mouse vertical ergonómico inalámbrico", 59)]),
    ("Auriculares", "Auriculares con y sin cable para música y juegos", 12, [
        ("Pulsar Buds Pro", "Pulsar", "Auriculares inalámbricos con cancelación de ruido", 129),
        ("Pulsar Over-Ear 300", "Pulsar", "Auriculares de diadema Bluetooth con 40 horas de batería", 189),
        ("Orbix Gamer H5", "Orbix", "Auriculares gamer con micrófono y sonido envolvente virtual 7.1", 79)]),
    ("Parlantes", "Parlantes portátiles y barras de sonido", 12, [
        ("Vexa Boom Mini", "Vexa", "Parlante Bluetooth portátil con 12 horas de batería y resistencia al agua IPX7", 49),
        ("Vexa Boom Max", "Vexa", "Parlante Bluetooth de alta potencia con 20 horas de batería", 169),
        ("Aurora Soundbar 2.1", "Aurora", "Barra de sonido 2.1 con subwoofer inalámbrico", 249)]),
    ("Almacenamiento", "Discos sólidos, externos y memorias", 36, [
        ("Helix SSD 500 GB", "Helix", "Disco sólido NVMe de 500 GB", 59),
        ("Helix SSD 1 TB", "Helix", "Disco sólido NVMe de 1 TB", 99),
        ("Tekna Externo 2 TB", "Tekna", "Disco externo de 2 TB con conexión USB 3.0", 89)]),
    ("Routers y redes", "Equipos para redes domésticas y de oficina", 24, [
        ("Nordik Router AX1800", "Nordik", "Router Wi-Fi 6 de doble banda", 89),
        ("Nordik Mesh x2", "Nordik", "Sistema Wi-Fi 6 en malla de 2 unidades para hasta 400 metros cuadrados", 199),
        ("Kairo Switch 8", "Kairo", "Switch gigabit de 8 puertos", 35)]),
    ("Impresoras", "Impresoras láser, de tinta y fotográficas", 12, [
        ("Orbix Print Laser", "Orbix", "Impresora láser monocromática", 139),
        ("Orbix Print Tank", "Orbix", "Impresora multifunción con tanque de tinta recargable", 229),
        ("Kairo Foto 4x6", "Kairo", "Impresora fotográfica portátil de formato 4x6", 119)]),
    ("Cámaras web", "Cámaras para videollamadas y transmisión", 12, [
        ("Tekna Cam 1080", "Tekna", "Cámara web Full HD con micrófono integrado", 39),
        ("Tekna Cam 4K Pro", "Tekna", "Cámara web 4K con enfoque automático", 99),
        ("Helix Stream Cam", "Helix", "Cámara web Full HD a 60 cuadros con trípode", 59)]),
    ("Consolas", "Consolas de videojuegos y controles", 12, [
        ("Pulsar Console One", "Pulsar", "Consola de videojuegos con 1 TB de almacenamiento", 499),
        ("Pulsar Console Lite", "Pulsar", "Consola compacta de videojuegos con 512 GB", 349),
        ("Pulsar Pad", "Pulsar", "Control inalámbrico con vibración", 69)]),
    ("Micrófonos", "Micrófonos para streaming, podcast y reuniones", 12, [
        ("Aurora Mic USB", "Aurora", "Micrófono de condensador USB con patrón cardioide", 79),
        ("Aurora Mic Pro XLR", "Aurora", "Micrófono profesional con conexión XLR", 189),
        ("Kairo Lavalier", "Kairo", "Micrófono de solapa inalámbrico", 45)]),
    ("Smartwatches", "Relojes inteligentes y pulseras de actividad", 12, [
        ("Vexa Watch 2", "Vexa", "Reloj inteligente con pantalla AMOLED de 1.4 pulgadas y GPS", 149),
        ("Vexa Watch Sport", "Vexa", "Reloj deportivo con GPS y resistencia al agua de 5 ATM", 229),
        ("Kairo Band 5", "Kairo", "Pulsera de actividad con monitor de sueño y frecuencia cardíaca", 39)]),
    ("Cables y accesorios", "Cables, cargadores y adaptadores", 6, [
        ("Helix Cable USB-C 2 m", "Helix", "Cable USB-C a USB-C de 2 metros", 12),
        ("Helix Cargador GaN 65 W", "Helix", "Cargador rápido de 65 W con tecnología GaN", 35),
        ("Kairo Hub USB-C 7 en 1", "Kairo", "Hub USB-C con HDMI, USB 3.0 y lector de tarjetas", 45)]),
]

UBICACIONES = {
    "Argentina": [("Buenos Aires", "La Plata"), ("Buenos Aires", "Mar del Plata"),
                  ("CABA", "Ciudad Autónoma de Buenos Aires"), ("Córdoba", "Córdoba"),
                  ("Santa Fe", "Rosario"), ("Mendoza", "Mendoza"),
                  ("Tucumán", "San Miguel de Tucumán"), ("Salta", "Salta"),
                  ("Neuquén", "Neuquén"), ("Entre Ríos", "Paraná")],
    "Uruguay": [("Montevideo", "Montevideo"), ("Canelones", "Las Piedras")],
    "Chile": [("Región Metropolitana", "Santiago"), ("Valparaíso", "Viña del Mar")],
    "Paraguay": [("Central", "Asunción")],
    "España": [("Madrid", "Madrid"), ("Cataluña", "Barcelona")],
    "México": [("Ciudad de México", "Ciudad de México"), ("Jalisco", "Guadalajara")],
}
PESOS_PAIS = {"Argentina": 70, "Uruguay": 8, "Chile": 8, "Paraguay": 4, "España": 5, "México": 5}

METODOS_PAGO = ["tarjeta_credito", "tarjeta_debito", "mercadopago", "transferencia", "efectivo"]
PESOS_PAGO = [40, 20, 20, 15, 5]
TRANSPORTES = ["Andreani", "OCA", "Correo Argentino", "DHL Express"]

COMENTARIOS = {
    5: ["Excelente producto, superó mis expectativas.",
        "Muy buena calidad, llegó rápido y bien embalado.",
        "Lo recomiendo, funciona perfecto.",
        "Impecable relación precio-calidad."],
    4: ["Muy bueno en general, cumple lo que promete.",
        "Buen producto, el envío tardó un poco más de lo esperado.",
        "Cumple bien, lo volvería a comprar."],
    3: ["Es correcto, nada del otro mundo.",
        "Cumple, pero esperaba un poco más por el precio."],
    2: ["Regular, tuvo algunos problemas de funcionamiento.",
        "No es del todo lo que esperaba según la descripción."],
    1: ["No funcionó correctamente, tuve que reclamar.",
        "Muy mala experiencia, el producto llegó defectuoso.",
        "No lo recomiendo."],
}

CENTAVO = Decimal("0.01")


def _normalizar(texto: str) -> str:
    """Quita tildes y simbolos para armar emails validos."""
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _subtotal(cantidad: int, precio: Decimal, descuento: Decimal) -> Decimal:
    """Replica la columna calculada detalle_pedidos.subtotal de SQL Server."""
    bruto = Decimal(cantidad) * precio * (Decimal(1) - descuento / Decimal(100))
    return bruto.quantize(CENTAVO, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Generacion por tabla
# ---------------------------------------------------------------------------
def generar_catalogo(rng: random.Random, hoy: date):
    """Devuelve (categorias, productos)."""
    categorias, productos = [], []
    for id_cat, (nombre, desc, garantia, prods) in enumerate(CATALOGO, start=1):
        categorias.append({"id_categoria": id_cat, "nombre": nombre, "descripcion": desc})
        for (pnombre, marca, pdesc, precio) in prods:
            productos.append({
                "id_producto": len(productos) + 1,
                "id_categoria": id_cat,
                "nombre": pnombre,
                "marca": marca,
                "descripcion": pdesc,
                "precio": Decimal(precio).quantize(CENTAVO),
                "stock": rng.randint(5, 150),
                "garantia_meses": garantia,
                "activo": True,
                # Alta anterior al periodo de pedidos (12 meses)
                "fecha_alta": hoy - timedelta(days=rng.randint(400, 900)),
            })
    # 3 productos agotados (activos) y 2 discontinuados
    elegidos = rng.sample(range(len(productos)), 5)
    for i in elegidos[:3]:
        productos[i]["stock"] = 0
    for i in elegidos[3:]:
        productos[i]["stock"] = 0
        productos[i]["activo"] = False
    return categorias, productos


def generar_clientes(rng: random.Random, fake: Faker, hoy: date):
    """Devuelve la lista de clientes."""
    paises = list(PESOS_PAIS)
    pesos = list(PESOS_PAIS.values())
    clientes = []
    for i in range(1, N_CLIENTES + 1):
        pais = "Argentina" if i == CLIENTE_CASOS_LIMITE else rng.choices(paises, pesos)[0]
        provincia, ciudad = rng.choice(UBICACIONES[pais])
        nombre, apellido = fake.first_name(), fake.last_name()
        # El cliente de los casos limite se registro hace mucho tiempo
        dias = 800 if i == CLIENTE_CASOS_LIMITE else rng.randint(20, 900)
        clientes.append({
            "id_cliente": i,
            "nombre": nombre,
            "apellido": apellido,
            "email": f"{_normalizar(nombre)}.{_normalizar(apellido)}{i}@example.com",
            "telefono": fake.phone_number()[:30],
            "pais": pais,
            "provincia": provincia,
            "ciudad": ciudad,
            "direccion": fake.street_address()[:200],
            "fecha_registro": hoy - timedelta(days=dias),
            "activo": rng.random() > 0.08,
        })
    return clientes


def _estado_y_envio(rng: random.Random, f_pedido: date, hoy: date):
    """Elige el estado del pedido segun su antiguedad y arma el envio si corresponde."""
    edad = (hoy - f_pedido).days
    if edad < 2:
        estado = rng.choices(["pendiente", "pagado"], [30, 70])[0]
    elif edad < 8:
        estado = rng.choices(["pagado", "enviado", "entregado", "cancelado"], [10, 50, 30, 10])[0]
    else:
        estado = rng.choices(["entregado", "devuelto", "cancelado"], [85, 7, 8])[0]

    if estado in ("pendiente", "pagado", "cancelado"):
        return estado, None

    f_envio = f_pedido + timedelta(days=min(rng.randint(1, 3), max(edad - 1, 0)))
    estimada = f_envio + timedelta(days=rng.randint(2, 6))
    if estado == "enviado":
        return estado, {"f_envio": f_envio, "estimada": estimada, "real": None,
                        "estado_envio": "en_transito"}
    real = estimada + timedelta(days=rng.randint(-1, 3))
    real = max(f_envio + timedelta(days=1), min(real, hoy))
    return estado, {"f_envio": f_envio, "estimada": estimada, "real": real,
                    "estado_envio": "entregado"}


def _casos_limite(hoy: date):
    """Pedidos fijos del cliente CLIENTE_CASOS_LIMITE para probar la regla de 30 dias."""
    casos = []

    def entregado(dias_desde_entrega, estado="entregado"):
        real = hoy - timedelta(days=dias_desde_entrega)
        return {
            "f_pedido": real - timedelta(days=5), "estado": estado,
            "envio": {"f_envio": real - timedelta(days=3), "estimada": real, "real": real,
                      "estado_envio": "entregado"},
        }

    for dias in (5, 29, 30, 31, 60):
        casos.append(entregado(dias))
    casos.append(entregado(12, estado="devuelto"))
    casos.append({  # en transito: sin fecha de entrega real
        "f_pedido": hoy - timedelta(days=4), "estado": "enviado",
        "envio": {"f_envio": hoy - timedelta(days=2), "estimada": hoy + timedelta(days=2),
                  "real": None, "estado_envio": "en_transito"},
    })
    casos.append({"f_pedido": hoy - timedelta(days=10), "estado": "cancelado", "envio": None})
    for c in casos:
        c["id_cliente"] = CLIENTE_CASOS_LIMITE
    return casos


def _elegir_productos(rng, productos, pesos, k):
    """Elige k productos distintos, con probabilidad segun popularidad."""
    elegidos = {}
    while len(elegidos) < k:
        p = rng.choices(productos, weights=pesos)[0]
        elegidos[p["id_producto"]] = p
    return list(elegidos.values())


def generar_pedidos(rng: random.Random, hoy: date, clientes, productos):
    """Devuelve (pedidos, detalles, envios)."""
    borradores = _casos_limite(hoy)

    # Productos con popularidad desigual (hay "mas vendidos")
    orden = list(range(len(productos)))
    rng.shuffle(orden)
    pesos = [0.0] * len(productos)
    for rango, idx in enumerate(orden):
        pesos[idx] = 1 / (rango + 1) ** 0.6

    # Pedidos aleatorios: primero la fecha, luego un cliente ya registrado
    for _ in range(N_PEDIDOS - len(borradores)):
        # ~15% de los pedidos son de las ultimas 2 semanas (hay pedidos en curso)
        dias = rng.randint(0, 13) if rng.random() < 0.15 else rng.randint(0, 364)
        f_pedido = hoy - timedelta(days=dias)
        candidatos = [c for c in clientes if c["fecha_registro"] <= f_pedido]
        estado, envio = _estado_y_envio(rng, f_pedido, hoy)
        borradores.append({"id_cliente": rng.choice(candidatos)["id_cliente"],
                           "f_pedido": f_pedido, "estado": estado, "envio": envio})

    # Hora del dia y orden cronologico (los ids siguen el orden de fecha)
    for b in borradores:
        b["fecha_pedido"] = datetime.combine(
            b["f_pedido"], time(rng.randint(8, 22), rng.randint(0, 59), 0))
    borradores.sort(key=lambda b: b["fecha_pedido"])

    pedidos, detalles, envios = [], [], []
    for id_pedido, b in enumerate(borradores, start=1):
        k = rng.choices([1, 2, 3, 4], [40, 30, 20, 10])[0]
        total = Decimal("0.00")
        for p in _elegir_productos(rng, productos, pesos, k):
            if p["precio"] < 30:
                cantidad = rng.randint(1, 5)
            else:
                cantidad = rng.choices([1, 2, 3, 4], [70, 20, 7, 3])[0]
            descuento = Decimal(rng.choices([0, 5, 10, 15], [75, 10, 10, 5])[0])
            detalles.append({
                "id_detalle": len(detalles) + 1, "id_pedido": id_pedido,
                "id_producto": p["id_producto"], "cantidad": cantidad,
                "precio_unitario": p["precio"], "descuento_pct": descuento,
            })
            total += _subtotal(cantidad, p["precio"], descuento)

        pedidos.append({
            "id_pedido": id_pedido, "id_cliente": b["id_cliente"],
            "fecha_pedido": b["fecha_pedido"], "estado": b["estado"],
            "metodo_pago": rng.choices(METODOS_PAGO, PESOS_PAGO)[0],
            "total": total,
        })

        if b["envio"]:
            e = b["envio"]
            envios.append({
                "id_envio": len(envios) + 1, "id_pedido": id_pedido,
                "empresa_transporte": rng.choice(TRANSPORTES),
                "numero_seguimiento": f"TRK{rng.randint(10**9, 10**10 - 1)}",
                "fecha_envio": e["f_envio"], "fecha_entrega_estimada": e["estimada"],
                "fecha_entrega_real": e["real"], "estado_envio": e["estado_envio"],
                "costo_envio": Decimal(rng.choice([0, 8, 12, 15, 25])).quantize(CENTAVO),
            })
    return pedidos, detalles, envios


def generar_resenas(rng: random.Random, hoy: date, pedidos, detalles, envios):
    """Resenas solo de clientes que recibieron el producto."""
    cliente_de = {p["id_pedido"]: p["id_cliente"] for p in pedidos}
    entrega_de = {e["id_pedido"]: e["fecha_entrega_real"] for e in envios
                  if e["fecha_entrega_real"] is not None}
    elegibles = {}
    for d in detalles:
        if d["id_pedido"] in entrega_de:
            clave = (cliente_de[d["id_pedido"]], d["id_producto"])
            f = entrega_de[d["id_pedido"]]
            elegibles[clave] = min(f, elegibles.get(clave, f))
    pares = sorted(elegibles.items())
    muestra = rng.sample(pares, min(N_RESENAS, len(pares)))

    resenas = []
    for (id_cliente, id_producto), f_entrega in sorted(muestra):
        calif = rng.choices([5, 4, 3, 2, 1], [35, 30, 15, 10, 10])[0]
        comentario = None if rng.random() < 0.10 else rng.choice(COMENTARIOS[calif])
        resenas.append({
            "id_resena": len(resenas) + 1, "id_producto": id_producto,
            "id_cliente": id_cliente, "calificacion": calif, "comentario": comentario,
            "fecha": min(hoy, f_entrega + timedelta(days=rng.randint(2, 25))),
        })
    return resenas


def generar(hoy: date) -> dict:
    """Genera todos los datos en memoria (sin tocar la base)."""
    rng = random.Random(SEMILLA)
    Faker.seed(SEMILLA)
    fake = Faker("es_AR")
    categorias, productos = generar_catalogo(rng, hoy)
    clientes = generar_clientes(rng, fake, hoy)
    pedidos, detalles, envios = generar_pedidos(rng, hoy, clientes, productos)
    resenas = generar_resenas(rng, hoy, pedidos, detalles, envios)
    return {"categorias": categorias, "clientes": clientes, "productos": productos,
            "pedidos": pedidos, "detalle_pedidos": detalles, "envios": envios,
            "resenas": resenas}


# ---------------------------------------------------------------------------
# Carga en SQL Server
# ---------------------------------------------------------------------------
# Orden de insercion (padres primero) y columnas. subtotal es calculada: no se inserta.
TABLAS = [
    ("categorias", ["id_categoria", "nombre", "descripcion"]),
    ("clientes", ["id_cliente", "nombre", "apellido", "email", "telefono", "pais",
                  "provincia", "ciudad", "direccion", "fecha_registro", "activo"]),
    ("productos", ["id_producto", "id_categoria", "nombre", "marca", "descripcion", "precio",
                   "stock", "garantia_meses", "activo", "fecha_alta"]),
    ("pedidos", ["id_pedido", "id_cliente", "fecha_pedido", "estado", "metodo_pago", "total"]),
    ("detalle_pedidos", ["id_detalle", "id_pedido", "id_producto", "cantidad",
                         "precio_unitario", "descuento_pct"]),
    ("envios", ["id_envio", "id_pedido", "empresa_transporte", "numero_seguimiento",
                "fecha_envio", "fecha_entrega_estimada", "fecha_entrega_real",
                "estado_envio", "costo_envio"]),
    ("resenas", ["id_resena", "id_producto", "id_cliente", "calificacion", "comentario", "fecha"]),
]


def cargar(con, datos: dict) -> None:
    """Borra los datos existentes e inserta los generados, en una sola transaccion."""
    cur = con.cursor()
    try:
        for tabla, _ in reversed(TABLAS):          # hijos primero
            cur.execute(f"DELETE FROM dbo.{tabla}")
        for tabla, columnas in TABLAS:
            filas = [tuple(r[c] for c in columnas) for r in datos[tabla]]
            marcas = ", ".join("?" for _ in columnas)
            sql = f"INSERT INTO dbo.{tabla} ({', '.join(columnas)}) VALUES ({marcas})"
            cur.execute(f"SET IDENTITY_INSERT dbo.{tabla} ON")
            cur.executemany(sql, filas)
            cur.execute(f"SET IDENTITY_INSERT dbo.{tabla} OFF")
        con.commit()
    except Exception:
        con.rollback()
        raise


def resumir(datos: dict) -> None:
    """Muestra cuantas filas se generaron por tabla."""
    print("Filas generadas:")
    for tabla, _ in TABLAS:
        print(f"  {tabla:<16} {len(datos[tabla]):>5}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera y carga datos sinteticos.")
    parser.add_argument("--hoy", help="Fecha de referencia AAAA-MM-DD (por defecto, hoy)")
    parser.add_argument("--sin-bd", action="store_true", help="Solo generar; no conectar a la BD")
    args = parser.parse_args()

    hoy = date.fromisoformat(args.hoy) if args.hoy else date.today()
    print(f"Fecha de referencia: {hoy}  |  semilla: {SEMILLA}")
    datos = generar(hoy)
    resumir(datos)

    if args.sin_bd:
        print("\n--sin-bd: no se modifico la base de datos.")
        return

    from src.db import get_connection
    with get_connection(admin=True) as con:
        cargar(con, datos)
    print("\nCarga completada. Verificar con:  python -m scripts.verificar_datos")


if __name__ == "__main__":
    main()
