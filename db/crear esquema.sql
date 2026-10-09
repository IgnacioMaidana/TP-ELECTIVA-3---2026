/* =====================================================================
   TP Integrador - AI Engineering
   Dominio: E-commerce de tecnologia
   Motor: SQL Server (ejecutar en SSMS)
   Archivo: 01_crear_esquema_ecommerce.sql

   Contenido:
     1. Creacion de la base de datos
     2. Creacion de tablas (7 tablas)
     3. Indices
     4. Usuario de solo lectura para el agente (opcional)

   El script es re-ejecutable: elimina y recrea las tablas.
   ===================================================================== */

IF DB_ID(N'EcommerceTech') IS NULL
    CREATE DATABASE EcommerceTech;
GO

USE EcommerceTech;
GO

/* ---------------------------------------------------------------------
   Limpieza (orden inverso a las dependencias)
   --------------------------------------------------------------------- */
DROP TABLE IF EXISTS dbo.resenas;
DROP TABLE IF EXISTS dbo.envios;
DROP TABLE IF EXISTS dbo.detalle_pedidos;
DROP TABLE IF EXISTS dbo.pedidos;
DROP TABLE IF EXISTS dbo.productos;
DROP TABLE IF EXISTS dbo.categorias;
DROP TABLE IF EXISTS dbo.clientes;
GO

/* ---------------------------------------------------------------------
   1. categorias
   --------------------------------------------------------------------- */
CREATE TABLE dbo.categorias (
    id_categoria  INT IDENTITY(1,1) NOT NULL,
    nombre        NVARCHAR(100)     NOT NULL,
    descripcion   NVARCHAR(300)     NULL,
    CONSTRAINT PK_categorias        PRIMARY KEY (id_categoria),
    CONSTRAINT UQ_categorias_nombre UNIQUE (nombre)
);
GO

/* ---------------------------------------------------------------------
   2. clientes
   --------------------------------------------------------------------- */
CREATE TABLE dbo.clientes (
    id_cliente      INT IDENTITY(1,1) NOT NULL,
    nombre          NVARCHAR(80)      NOT NULL,
    apellido        NVARCHAR(80)      NOT NULL,
    email           NVARCHAR(150)     NOT NULL,
    telefono        NVARCHAR(30)      NULL,
    pais            NVARCHAR(60)      NOT NULL,
    provincia       NVARCHAR(80)      NULL,
    ciudad          NVARCHAR(80)      NOT NULL,
    direccion       NVARCHAR(200)     NULL,
    fecha_registro  DATE              NOT NULL CONSTRAINT DF_clientes_fecha DEFAULT (CAST(GETDATE() AS DATE)),
    activo          BIT               NOT NULL CONSTRAINT DF_clientes_activo DEFAULT (1),
    CONSTRAINT PK_clientes       PRIMARY KEY (id_cliente),
    CONSTRAINT UQ_clientes_email UNIQUE (email)
);
GO

/* ---------------------------------------------------------------------
   3. productos
   --------------------------------------------------------------------- */
CREATE TABLE dbo.productos (
    id_producto     INT IDENTITY(1,1) NOT NULL,
    id_categoria    INT               NOT NULL,
    nombre          NVARCHAR(150)     NOT NULL,
    marca           NVARCHAR(80)      NOT NULL,
    descripcion     NVARCHAR(500)     NULL,
    precio          DECIMAL(10,2)     NOT NULL,
    stock           INT               NOT NULL CONSTRAINT DF_productos_stock DEFAULT (0),
    garantia_meses  INT               NOT NULL CONSTRAINT DF_productos_garantia DEFAULT (12),
    activo          BIT               NOT NULL CONSTRAINT DF_productos_activo DEFAULT (1),
    fecha_alta      DATE              NOT NULL CONSTRAINT DF_productos_alta DEFAULT (CAST(GETDATE() AS DATE)),
    CONSTRAINT PK_productos           PRIMARY KEY (id_producto),
    CONSTRAINT FK_productos_categoria FOREIGN KEY (id_categoria) REFERENCES dbo.categorias (id_categoria),
    CONSTRAINT CK_productos_precio    CHECK (precio > 0),
    CONSTRAINT CK_productos_stock     CHECK (stock >= 0),
    CONSTRAINT CK_productos_garantia  CHECK (garantia_meses >= 0)
);
GO

/* ---------------------------------------------------------------------
   4. pedidos
   --------------------------------------------------------------------- */
CREATE TABLE dbo.pedidos (
    id_pedido     INT IDENTITY(1,1) NOT NULL,
    id_cliente    INT               NOT NULL,
    fecha_pedido  DATETIME2(0)      NOT NULL CONSTRAINT DF_pedidos_fecha DEFAULT (SYSDATETIME()),
    estado        NVARCHAR(20)      NOT NULL CONSTRAINT DF_pedidos_estado DEFAULT (N'pendiente'),
    metodo_pago   NVARCHAR(30)      NOT NULL,
    total         DECIMAL(12,2)     NOT NULL CONSTRAINT DF_pedidos_total DEFAULT (0),
    CONSTRAINT PK_pedidos         PRIMARY KEY (id_pedido),
    CONSTRAINT FK_pedidos_cliente FOREIGN KEY (id_cliente) REFERENCES dbo.clientes (id_cliente),
    CONSTRAINT CK_pedidos_estado  CHECK (estado IN (N'pendiente', N'pagado', N'enviado', N'entregado', N'cancelado', N'devuelto')),
    CONSTRAINT CK_pedidos_pago    CHECK (metodo_pago IN (N'tarjeta_credito', N'tarjeta_debito', N'transferencia', N'mercadopago', N'efectivo')),
    CONSTRAINT CK_pedidos_total   CHECK (total >= 0)
);
GO

/* ---------------------------------------------------------------------
   5. detalle_pedidos (relacion N:M entre pedidos y productos)
   --------------------------------------------------------------------- */
CREATE TABLE dbo.detalle_pedidos (
    id_detalle       INT IDENTITY(1,1) NOT NULL,
    id_pedido        INT               NOT NULL,
    id_producto      INT               NOT NULL,
    cantidad         INT               NOT NULL,
    precio_unitario  DECIMAL(10,2)     NOT NULL,
    descuento_pct    DECIMAL(5,2)      NOT NULL CONSTRAINT DF_detalle_desc DEFAULT (0),
    subtotal AS CAST(cantidad * precio_unitario * (1 - descuento_pct / 100.0) AS DECIMAL(12,2)) PERSISTED,
    CONSTRAINT PK_detalle_pedidos   PRIMARY KEY (id_detalle),
    CONSTRAINT FK_detalle_pedido    FOREIGN KEY (id_pedido)   REFERENCES dbo.pedidos (id_pedido),
    CONSTRAINT FK_detalle_producto  FOREIGN KEY (id_producto) REFERENCES dbo.productos (id_producto),
    CONSTRAINT UQ_detalle_pedprod   UNIQUE (id_pedido, id_producto),
    CONSTRAINT CK_detalle_cantidad  CHECK (cantidad > 0),
    CONSTRAINT CK_detalle_precio    CHECK (precio_unitario > 0),
    CONSTRAINT CK_detalle_desc      CHECK (descuento_pct BETWEEN 0 AND 100)
);
GO

/* ---------------------------------------------------------------------
   6. envios (relacion 1:1 opcional con pedidos)
   --------------------------------------------------------------------- */
CREATE TABLE dbo.envios (
    id_envio                INT IDENTITY(1,1) NOT NULL,
    id_pedido               INT               NOT NULL,
    empresa_transporte      NVARCHAR(80)      NOT NULL,
    numero_seguimiento      NVARCHAR(50)      NULL,
    fecha_envio             DATE              NULL,
    fecha_entrega_estimada  DATE              NULL,
    fecha_entrega_real      DATE              NULL,
    estado_envio            NVARCHAR(20)      NOT NULL CONSTRAINT DF_envios_estado DEFAULT (N'preparando'),
    costo_envio             DECIMAL(10,2)     NOT NULL CONSTRAINT DF_envios_costo DEFAULT (0),
    CONSTRAINT PK_envios        PRIMARY KEY (id_envio),
    CONSTRAINT FK_envios_pedido FOREIGN KEY (id_pedido) REFERENCES dbo.pedidos (id_pedido),
    CONSTRAINT UQ_envios_pedido UNIQUE (id_pedido),
    CONSTRAINT CK_envios_estado CHECK (estado_envio IN (N'preparando', N'en_transito', N'entregado', N'devuelto', N'perdido')),
    CONSTRAINT CK_envios_costo  CHECK (costo_envio >= 0)
);
GO

/* ---------------------------------------------------------------------
   7. resenas
   --------------------------------------------------------------------- */
CREATE TABLE dbo.resenas (
    id_resena     INT IDENTITY(1,1) NOT NULL,
    id_producto   INT               NOT NULL,
    id_cliente    INT               NOT NULL,
    calificacion  TINYINT           NOT NULL,
    comentario    NVARCHAR(500)     NULL,
    fecha         DATE              NOT NULL CONSTRAINT DF_resenas_fecha DEFAULT (CAST(GETDATE() AS DATE)),
    CONSTRAINT PK_resenas          PRIMARY KEY (id_resena),
    CONSTRAINT FK_resenas_producto FOREIGN KEY (id_producto) REFERENCES dbo.productos (id_producto),
    CONSTRAINT FK_resenas_cliente  FOREIGN KEY (id_cliente)  REFERENCES dbo.clientes (id_cliente),
    CONSTRAINT UQ_resenas_cli_prod UNIQUE (id_cliente, id_producto),
    CONSTRAINT CK_resenas_calif    CHECK (calificacion BETWEEN 1 AND 5)
);
GO

/* ---------------------------------------------------------------------
   Indices sobre claves foraneas y columnas de filtro frecuentes
   --------------------------------------------------------------------- */
CREATE INDEX IX_productos_categoria  ON dbo.productos (id_categoria);
CREATE INDEX IX_pedidos_cliente      ON dbo.pedidos (id_cliente);
CREATE INDEX IX_pedidos_fecha        ON dbo.pedidos (fecha_pedido);
CREATE INDEX IX_pedidos_estado       ON dbo.pedidos (estado);
CREATE INDEX IX_detalle_producto     ON dbo.detalle_pedidos (id_producto);
CREATE INDEX IX_resenas_producto     ON dbo.resenas (id_producto);
CREATE INDEX IX_clientes_pais        ON dbo.clientes (pais);
GO

/* ---------------------------------------------------------------------
   Descripciones de tablas (metadatos utiles para el prompt del agente)
   --------------------------------------------------------------------- */
EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'Categorias de productos (notebooks, perifericos, etc.)',
     @level0type = N'SCHEMA', @level0name = N'dbo', @level1type = N'TABLE', @level1name = N'categorias';
EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'Clientes registrados en la tienda',
     @level0type = N'SCHEMA', @level0name = N'dbo', @level1type = N'TABLE', @level1name = N'clientes';
EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'Catalogo de productos con precio, stock y garantia en meses',
     @level0type = N'SCHEMA', @level0name = N'dbo', @level1type = N'TABLE', @level1name = N'productos';
EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'Cabecera de pedidos: cliente, fecha, estado, metodo de pago y total',
     @level0type = N'SCHEMA', @level0name = N'dbo', @level1type = N'TABLE', @level1name = N'pedidos';
EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'Lineas de cada pedido: producto, cantidad, precio unitario y descuento',
     @level0type = N'SCHEMA', @level0name = N'dbo', @level1type = N'TABLE', @level1name = N'detalle_pedidos';
EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'Envio asociado a un pedido: transportista, fechas y estado',
     @level0type = N'SCHEMA', @level0name = N'dbo', @level1type = N'TABLE', @level1name = N'envios';
EXEC sys.sp_addextendedproperty @name = N'MS_Description', @value = N'Resenas de productos hechas por clientes (calificacion 1 a 5)',
     @level0type = N'SCHEMA', @level0name = N'dbo', @level1type = N'TABLE', @level1name = N'resenas';
GO

/* ---------------------------------------------------------------------
   OPCIONAL: usuario de SOLO LECTURA para el agente
   - Requiere autenticacion mixta (SQL Server + Windows) en la instancia.
   - CAMBIAR la contrasena antes de ejecutar.
   - El agente debe conectarse con este usuario, nunca con 'sa'.
   --------------------------------------------------------------------- */
/*
USE master;
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'agente_ro')
    CREATE LOGIN agente_ro WITH PASSWORD = N'CambiarEstaClave_123!', CHECK_POLICY = ON;
GO
USE EcommerceTech;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'agente_ro')
    CREATE USER agente_ro FOR LOGIN agente_ro;
ALTER ROLE db_datareader ADD MEMBER agente_ro;
DENY INSERT, UPDATE, DELETE, ALTER, EXECUTE ON SCHEMA::dbo TO agente_ro;
GO
*/

/* ---------------------------------------------------------------------
   Verificacion rapida
   --------------------------------------------------------------------- */
SELECT t.name AS tabla, COUNT(c.column_id) AS columnas
FROM sys.tables t
JOIN sys.columns c ON c.object_id = t.object_id
GROUP BY t.name
ORDER BY t.name;
GO
