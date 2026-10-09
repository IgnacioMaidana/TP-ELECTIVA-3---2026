/* =====================================================================
   Usuario de SOLO LECTURA para el agente (agente_ro)
   Ejecutar en SSMS conectado con autenticacion de Windows (como admin).

   REQUISITOS
   - La instancia debe tener habilitada la autenticacion mixta
     (SQL Server and Windows Authentication mode) y haberse reiniciado.
   - Antes de ejecutar: cambiar la contrasena (DEBE coincidir con
     DB_PASSWORD del archivo .env).
   - Evitar en la contrasena los caracteres  ;  {  }  =  porque rompen
     la cadena de conexion de pyodbc.
   ===================================================================== */

USE master;
GO

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'agente_ro')
    CREATE LOGIN agente_ro
        WITH PASSWORD = N'agente12343',
             CHECK_POLICY = ON,
             DEFAULT_DATABASE = EcommerceTech;
GO

USE EcommerceTech;
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'agente_ro')
    CREATE USER agente_ro FOR LOGIN agente_ro;
GO

-- Solo lectura
ALTER ROLE db_datareader ADD MEMBER agente_ro;

-- Bloqueo explicito de escritura y cambios de esquema
DENY INSERT, UPDATE, DELETE, ALTER, EXECUTE ON SCHEMA::dbo TO agente_ro;
DENY CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE FUNCTION TO agente_ro;
GO

-- Verificacion: debe listar db_datareader
SELECT r.name AS rol
FROM sys.database_role_members m
JOIN sys.database_principals r ON r.principal_id = m.role_principal_id
JOIN sys.database_principals u ON u.principal_id = m.member_principal_id
WHERE u.name = N'agente_ro';
GO
