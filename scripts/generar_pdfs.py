"""Genera los PDFs de TechNova Store que usa el RAG (T-16).

Uso (desde la raiz del repositorio, con el entorno virtual activo):

    python -m scripts.generar_pdfs

Produce en data/pdfs/:
  - politica_devoluciones_garantias.pdf
  - catalogo_especificaciones.pdf

Coherencia con la base de datos: las categorias, productos, precios y meses de
garantia se toman de CATALOGO (scripts/generar_datos.py), la misma fuente que
puebla las tablas. Asi los PDFs y la BD nunca se contradicen.

Las reglas del PDF de politicas deben coincidir con spec.md (RF-17, seccion 3.3):
  - Plazo de devolucion: 30 dias corridos desde la ENTREGA REAL.
  - Garantia: meses por categoria, tambien desde la entrega real.
"""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from scripts.generar_datos import CATALOGO

TIENDA = "TechNova Store"
DESTINO = Path(__file__).resolve().parent.parent / "data" / "pdfs"

# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------
_base = getSampleStyleSheet()
TITULO = ParagraphStyle("Titulo", parent=_base["Title"], fontSize=20, spaceAfter=6)
SUBTITULO = ParagraphStyle("Subtitulo", parent=_base["Normal"], fontSize=10,
                           textColor=colors.HexColor("#555555"), alignment=1, spaceAfter=14)
H1 = ParagraphStyle("H1", parent=_base["Heading1"], fontSize=14, spaceBefore=12, spaceAfter=6,
                    textColor=colors.HexColor("#1F3A5F"), keepWithNext=1)
H2 = ParagraphStyle("H2", parent=_base["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=4,
                    keepWithNext=1)
TEXTO = ParagraphStyle("Texto", parent=_base["Normal"], fontSize=10, leading=14, spaceAfter=6)
NOTA = ParagraphStyle("Nota", parent=TEXTO, backColor=colors.HexColor("#EEF3F9"),
                      borderPadding=6, spaceBefore=4, spaceAfter=10)
PRODUCTO = ParagraphStyle("Producto", parent=TEXTO, leftIndent=8, spaceAfter=2)


def p(texto, estilo=TEXTO):
    """Parrafo con el texto escapado (los datos de la BD pueden traer & o <)."""
    return Paragraph(escape(texto), estilo)


def pr(texto, estilo=TEXTO):
    """Parrafo con marcado reportlab ya preparado (negritas con <b>)."""
    return Paragraph(texto, estilo)


def lista(items):
    return ListFlowable([ListItem(p(i), leftIndent=14) for i in items],
                        bulletType="bullet", start="-", leftIndent=14)


def tabla(filas, anchos):
    t = Table(filas, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#AAAAAA")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def construir(ruta: Path, titulo: str, contenido: list) -> None:
    """Escribe el PDF con pie de pagina 'documento - Pagina N' (la pagina que se cita en el RAG)."""
    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(2 * cm, 1.2 * cm, f"{TIENDA} - {titulo}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.restoreState()

    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(ruta), pagesize=A4, title=f"{TIENDA} - {titulo}", author=TIENDA,
                            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    doc.build(contenido, onFirstPage=pie, onLaterPages=pie)


# ---------------------------------------------------------------------------
# PDF 1: politica de devoluciones y garantias
# ---------------------------------------------------------------------------
def contenido_politica() -> list:
    garantias = [["Categoría", "Garantía (meses)"]]
    for nombre, _desc, meses, _prods in CATALOGO:
        garantias.append([nombre, str(meses)])

    c = [
        p("Política de Devoluciones y Garantías", TITULO),
        p(f"{TIENDA} - Versión vigente para todos los pedidos", SUBTITULO),

        p("1. Alcance", H1),
        p(f"Esta política rige para todas las compras realizadas en la tienda online {TIENDA} "
          "con envío a Argentina, Uruguay, Chile, Paraguay, España y México. Distingue dos "
          "derechos diferentes: la devolución (por cualquier motivo, dentro de un plazo corto) "
          "y la garantía (por defectos de fabricación, durante un plazo más largo que depende "
          "de la categoría del producto)."),

        p("2. Plazo de devolución", H1),
        pr("El cliente puede devolver un producto dentro de los <b>30 días corridos contados "
           "desde la fecha de entrega real del pedido</b>. La fecha de entrega real es el día "
           "en que el transportista registra la entrega en la dirección del cliente. No se "
           "cuenta desde la fecha de compra ni desde la fecha de envío.", NOTA),
        p("Ejemplo: un pedido entregado el 1 de octubre puede devolverse hasta el 31 de octubre "
          "inclusive. El día 30 todavía está dentro del plazo; a partir del día 31 el plazo "
          "está vencido."),
        p("Pedidos sin plazo de devolución activo", H2),
        lista([
            "Pedidos que todavía no fueron entregados (en preparación o en tránsito): el plazo "
            "empieza a correr recién cuando se registra la entrega.",
            "Pedidos cancelados: no hay producto entregado que devolver.",
            "Pedidos que ya fueron devueltos: la devolución ya está registrada.",
        ]),
        p("Cancelación antes del envío", H2),
        p("Un pedido puede cancelarse sin costo mientras no haya sido enviado. En ese caso se "
          "reembolsa el importe completo al mismo medio de pago."),

        p("3. Condiciones para devolver un producto", H1),
        lista([
            "El producto debe estar en buen estado, sin signos de uso intensivo, golpes o daños.",
            "Debe devolverse en su embalaje original, con todos sus accesorios, manuales y cables.",
            "Debe presentarse el número de pedido como comprobante de compra.",
            "Los dispositivos con cuenta personal (smartphones, tablets, smartwatches, consolas) "
            "deben restablecerse a valores de fábrica y cerrar la sesión de la cuenta del cliente.",
        ]),
        p("Productos que no admiten devolución por arrepentimiento", H2),
        lista([
            "Auriculares intrauditivos con el sello de higiene abierto, salvo que presenten una falla.",
            "Productos con daños causados por el cliente, como golpes, líquidos o modificaciones.",
            "Cables y accesorios con signos evidentes de uso.",
            "Licencias de software ya activadas.",
        ]),
        p("Estas excepciones no afectan el derecho a la garantía cuando el producto tiene un "
          "defecto de fabricación."),

        p("4. Proceso de devolución", H1),
        lista([
            "Paso 1: solicitar la devolución escribiendo a devoluciones@technova.example con el "
            "número de pedido, el producto y el motivo. Se recomienda adjuntar fotos.",
            "Paso 2: recibir la confirmación y la etiqueta de envío de retorno en un máximo de "
            "2 días hábiles.",
            "Paso 3: enviar el paquete dentro de los 5 días corridos siguientes a la confirmación.",
            "Paso 4: el producto se inspecciona en un máximo de 3 días hábiles desde que llega al "
            "centro de devoluciones.",
            "Paso 5: si se aprueba, se emite el reembolso o el cambio.",
        ]),
        p("Costo del envío de retorno", H2),
        p("El envío de retorno es gratuito cuando el producto llegó defectuoso, dañado o distinto "
          "al pedido. En las devoluciones por arrepentimiento el costo del envío de retorno está "
          "a cargo del cliente. El costo del envío original no se reembolsa, salvo en los casos "
          "de falla o error de la tienda."),

        p("5. Reembolsos y cambios", H1),
        p("Una vez aprobada la devolución, el reembolso se realiza al mismo medio de pago "
          "utilizado en la compra, en los siguientes plazos:"),
        tabla([["Medio de pago", "Plazo del reembolso"],
               ["Tarjeta de crédito", "Hasta 10 días hábiles"],
               ["Tarjeta de débito", "Hasta 10 días hábiles"],
               ["MercadoPago", "Hasta 5 días hábiles"],
               ["Transferencia bancaria", "Hasta 5 días hábiles"],
               ["Efectivo", "Hasta 7 días hábiles, por transferencia a una cuenta del cliente"]],
              [6 * cm, 11 * cm]),
        Spacer(1, 8),
        p("Cambio por otro producto", H2),
        p("Dentro del mismo plazo de 30 días desde la entrega real, el cliente puede optar por "
          "cambiar el producto por otro. Si el nuevo producto cuesta más, abona la diferencia; "
          "si cuesta menos, se reintegra la diferencia."),

        p("6. Entregas con demora", H1),
        p("La fecha de entrega estimada se informa al confirmar el envío. Si la fecha de entrega "
          "real supera a la estimada en más de 2 días corridos, la tienda reintegra el costo "
          "del envío. El reintegro se acredita automáticamente, sin necesidad de reclamo."),

        # La tabla de garantias se mantiene entera en una pagina: si se parte, el RAG recupera solo
        # una parte de las filas y no puede responder "cual es la garantia mas corta".
        KeepTogether([
            p("7. Garantía", H1),
            pr("Todos los productos nuevos tienen garantía contra defectos de fabricación. El plazo "
               "de la garantía <b>se cuenta desde la fecha de entrega real</b> y depende de la "
               "categoría del producto:", TEXTO),
            tabla(garantias, [9 * cm, 8 * cm]),
        ]),
        Spacer(1, 8),
        p("Qué hace la tienda ante un defecto cubierto", H2),
        p("Ante un defecto de fabricación cubierto, la tienda repara el producto, lo reemplaza "
          "por uno equivalente o reembolsa el importe, a su criterio. La resolución se realiza "
          "en un máximo de 30 días corridos desde que el producto llega al centro de servicio."),
        p("Qué no cubre la garantía", H2),
        lista([
            "Golpes, caídas, contacto con líquidos, sobretensión o uso indebido.",
            "Modificaciones, reparaciones o aperturas realizadas por terceros no autorizados.",
            "Desgaste normal, incluida la disminución natural de la capacidad de las baterías.",
            "Consumibles, como tinta, tóner o almohadillas, y software de terceros.",
        ]),

        p("8. Diferencia entre devolución y garantía", H1),
        tabla([["", "Devolución", "Garantía"],
               ["Motivo", "Cualquiera (arrepentimiento o defecto)", "Defecto de fabricación"],
               ["Plazo", "30 días desde la entrega real", "6 a 36 meses según categoría"],
               ["Resultado", "Reembolso o cambio", "Reparación, reemplazo o reembolso"],
               ["Estado del producto", "Sin uso, embalaje original", "Puede estar usado"]],
              [4 * cm, 6.5 * cm, 6.5 * cm]),
        Spacer(1, 8),

        p("9. Contacto", H1),
        p("Atención al cliente: devoluciones@technova.example. Horario: lunes a viernes de 9 a 18 "
          "horas (GMT-3). Tiempo máximo de primera respuesta: 2 días hábiles."),
    ]
    return c


# ---------------------------------------------------------------------------
# PDF 2: catalogo y especificaciones tecnicas
# ---------------------------------------------------------------------------
# Texto de apoyo por categoria: (guia de compra, contenido de la caja, compatibilidad)
EXTRAS = {
    "Notebooks": ("Elegir según el uso: las ultralivianas priorizan la batería y el peso; "
                  "los modelos Pro ofrecen más memoria y almacenamiento para trabajo exigente.",
                  "Notebook, cargador, manual y tarjeta de garantía.",
                  "Compatible con Windows y con los principales navegadores y suites de oficina."),
    "Smartphones": ("La gama media equilibra precio y rendimiento; los modelos Pro y X suman "
                    "más almacenamiento y mejores cámaras.",
                    "Teléfono, cable USB-C, herramienta para la bandeja SIM y manual.",
                    "Compatible con redes 4G; los modelos con 5G lo indican en su descripción."),
    "Tablets": ("Las tablets de 8 pulgadas son ideales para lectura; las de 10 y 11 pulgadas "
                "para estudio y entretenimiento.",
                "Tablet, cable de carga y manual.",
                "Compatible con aplicaciones de lectura, video y videollamadas."),
    "Monitores": ("La resolución y la frecuencia de actualización definen el uso: Full HD para "
                  "oficina, QHD y 144 Hz para juegos, ultrapanorámico para productividad.",
                  "Monitor, base, cable HDMI, cable de alimentación y manual.",
                  "Conexión HDMI; compatible con notebooks y computadoras de escritorio."),
    "Teclados": ("Los mecánicos ofrecen mejor tacto y durabilidad; los inalámbricos y Bluetooth "
                 "ganan en comodidad y orden del escritorio.",
                 "Teclado, receptor o cable según el modelo, y manual.",
                 "Compatible con Windows, Linux y macOS."),
    "Mouses": ("Los modelos gamer ofrecen mayor precisión (DPI); el ergonómico vertical reduce "
               "la fatiga de la muñeca.",
               "Mouse, receptor USB o cable, pilas cuando corresponde, y manual.",
               "Compatible con Windows, Linux y macOS."),
    "Auriculares": ("Los intrauditivos son los más portátiles; los de diadema ofrecen más "
                    "autonomía; los gamer incluyen micrófono.",
                    "Auriculares, estuche o cable de carga y almohadillas de repuesto.",
                    "Conexión Bluetooth o cable según el modelo; compatibles con celulares y PC."),
    "Parlantes": ("El tamaño determina la potencia y la autonomía; la barra de sonido mejora "
                  "el audio de televisores.",
                  "Parlante, cable de carga y manual.",
                  "Conexión Bluetooth; la barra de sonido suma entrada HDMI y óptica."),
    "Almacenamiento": ("Los discos sólidos NVMe son los más rápidos; el disco externo sirve "
                       "para copias de seguridad. Es la categoría con mayor garantía.",
                       "Unidad de almacenamiento, cable cuando corresponde y manual.",
                       "Los discos NVMe requieren una ranura M.2 compatible."),
    "Routers y redes": ("El router Wi-Fi 6 cubre hogares medianos; el sistema en malla elimina "
                        "zonas sin señal; el switch amplía las conexiones por cable.",
                        "Equipo, fuente de alimentación, cable de red y guía de instalación.",
                        "Compatible con cualquier proveedor de internet por fibra o cable."),
    "Impresoras": ("La láser monocromática es la más económica por página; la de tanque de tinta "
                   "es multifunción; la fotográfica es portátil.",
                   "Impresora, cable de alimentación, cartuchos o tinta iniciales y manual.",
                   "Impresión desde PC y celulares."),
    "Cámaras web": ("Full HD alcanza para videollamadas; la de 4K con enfoque automático es "
                    "para transmisión profesional.",
                    "Cámara, cable USB y manual; el modelo Stream Cam incluye trípode.",
                    "Conexión USB; compatible con las principales plataformas de videollamadas."),
    "Consolas": ("La versión One incluye más almacenamiento; la Lite es más compacta y "
                 "económica. El control se vende por separado.",
                 "Consola, cable HDMI, cable de alimentación y manual.",
                 "Compatible con televisores con entrada HDMI."),
    "Micrófonos": ("El USB es para empezar sin otros equipos; el XLR es para uso profesional "
                   "con interfaz de audio; el de solapa es para entrevistas.",
                   "Micrófono, cable o receptor según el modelo y soporte.",
                   "El modelo XLR requiere una interfaz de audio."),
    "Smartwatches": ("Los relojes con GPS registran recorridos; la pulsera de actividad es la "
                     "opción más económica.",
                     "Reloj o pulsera, cargador y manual.",
                     "Compatible con smartphones Android y iOS."),
    "Cables y accesorios": ("Accesorios de uso diario. Es la categoría con menor garantía, de "
                            "6 meses.",
                            "Producto y manual breve.",
                            "Puertos USB-C y HDMI estándar."),
}


def contenido_catalogo() -> list:
    c = [
        p("Catálogo de Productos y Especificaciones Técnicas", TITULO),
        p(f"{TIENDA} - {len(CATALOGO)} categorías, {sum(len(x[3]) for x in CATALOGO)} productos", SUBTITULO),
        p("Cómo leer este catálogo", H1),
        p("Los precios están expresados en dólares estadounidenses (USD). La garantía se indica "
          "en meses y se cuenta desde la fecha de entrega real del pedido. Las condiciones de "
          "devolución y garantía figuran en el documento Política de Devoluciones y Garantías."),
    ]
    for nombre, descripcion, meses, productos in CATALOGO:
        guia, caja, compat = EXTRAS[nombre]
        bloque = [
            p(f"Categoría: {nombre}", H1),
            p(descripcion + f". Garantía de la categoría: {meses} meses."),
            p("Guía de compra", H2), p(guia),
            p("Contenido de la caja", H2), p(caja),
            p("Compatibilidad", H2), p(compat),
            p("Productos", H2),
        ]
        c.append(KeepTogether(bloque))
        for pnombre, marca, pdesc, precio in productos:
            c.append(KeepTogether([
                pr(f"<b>{escape(pnombre)}</b> - Marca {escape(marca)}", PRODUCTO),
                p(f"Precio: USD {precio} | Garantía: {meses} meses", PRODUCTO),
                p(f"Especificaciones: {pdesc}.", PRODUCTO),
                Spacer(1, 4),
            ]))
    return c


def main() -> None:
    construir(DESTINO / "politica_devoluciones_garantias.pdf",
              "Política de Devoluciones y Garantías", contenido_politica())
    construir(DESTINO / "catalogo_especificaciones.pdf",
              "Catálogo y Especificaciones Técnicas", contenido_catalogo())
    print(f"PDFs generados en {DESTINO}")


if __name__ == "__main__":
    main()
