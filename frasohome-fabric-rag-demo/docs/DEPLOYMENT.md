# Guía de despliegue

## 1. Autenticación

Si PowerShell indica que algún script `.ps1` no está firmado, desbloquéalos en la copia local:

```powershell
Get-ChildItem .\scripts\*.ps1 | Unblock-File
```

Configura `.env` con service principal o managed identity siguiendo `docs/NON_INTERACTIVE_AUTH.md`. Los scripts cargan esas variables y evitan `fab auth login` interactivo.

```powershell
.\scripts\bootstrap.ps1
```

Nota: Rayfin CLI se instala automáticamente durante `deploy_app.ps1`. En caso de requerir una sesión Rayfin previa, ejecuta `npx rayfin login` desde el directorio `app/frasohome-returnops-app`.

## 2. Crear SQL Database

```powershell
.\scripts\deploy_fabric_sql.ps1
```

Después de crearla, copia el server name desde **Settings > Connection strings** en Fabric.

## 3. Preparar usuario SQL de despliegue

Antes de ejecutar `apply_sql.ps1`, la identidad que use `sqlcmd` debe existir como usuario de la base de datos. Si usas service principal, entra una vez con un administrador Microsoft Entra de la SQL Database y ejecuta este SQL usando su Application (client) ID:

```sql
SELECT DB_NAME() AS current_database;

DECLARE @principalName sysname = N'frasohome-fabric-deployer';
DECLARE @clientId uniqueidentifier = '<FAB_SPN_CLIENT_ID>';
DECLARE @sid binary(16) = CONVERT(binary(16), @clientId);
DECLARE @sidLiteral varchar(max) = CONVERT(varchar(max), @sid, 1);
DECLARE @sql nvarchar(max);

IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @principalName AND sid <> @sid)
BEGIN
    SET @sql = N'DROP USER ' + QUOTENAME(@principalName) + N';';
    EXEC (@sql);
END;

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @principalName)
BEGIN
    SET @sql = N'CREATE USER ' + QUOTENAME(@principalName) + N' WITH SID = ' + @sidLiteral + N', TYPE = E;';
    EXEC (@sql);
END;

SET @sql = N'ALTER ROLE db_owner ADD MEMBER ' + QUOTENAME(@principalName) + N';';
EXEC (@sql);

SELECT
    DB_NAME() AS current_database,
    name,
    type_desc,
    IIF(sid = @sid, 1, 0) AS sid_matches_client_id
FROM sys.database_principals
WHERE name = @principalName;
```

Si `DROP USER` falla porque ese usuario posee objetos o esquemas, usa otro `@principalName` nuevo para el mismo `@clientId`, por ejemplo `frasohome-fabric-deployer-spn`.

Además del usuario SQL, la identidad debe tener permiso **Read** sobre el item SQL Database en Fabric. Si sigue apareciendo `Cannot open server ... requested by the login`, revisa en Fabric que el service principal o el grupo donde está tenga acceso al workspace o al item de base de datos.

`apply_sql.ps1` no puede crear ese usuario por sí mismo cuando se autentica con esa misma identidad: necesita el usuario para poder abrir conexión.

## 4. Aplicar SQL

```powershell
.\scripts\apply_sql.ps1
```

Este paso crea:

- Esquemas `fraso` y `rag`.
- Tablas operacionales.
- Tablas RAG.
- Datos de demo.
- Stored procedures.
- Roles/grants de ejemplo.

## 5. Publicar UDF

```powershell
.\scripts\publish_udf.ps1
```

El script intenta localizar el item id de la SQL Database con `fab api` y renderiza:

- `fabric/items/FrasoHome_RAG_UDF.UserDataFunction/definition.json`
- `fabric/items/config.yml`

Después ejecuta:

```powershell
cd fabric/items
fab deploy --config config.yml
```

Si la conexión por alias no aparece en el portal, créala desde **Manage connections** en el item UDF y usa el alias configurado en `.env`.

## 6. Habilitar endpoint público UDF

En el portal de Fabric:

1. Abre `FrasoHome_RAG_UDF`.
2. Publica si el portal lo solicita.
3. Habilita public endpoint para `answerReturnCase`.
4. Copia la URL pública en `VITE_UDF_FUNCTION_URL`.

## 7. App registration para invocar UDF

Crea una app registration en Entra ID para el frontend. Añade redirect URI:

- `http://localhost:5173`
- La URL final de tu Fabric App cuando la tengas desplegada.

Concede permisos delegados necesarios para invocar User Data Functions / Power BI API según tu tenant y otorga admin consent si aplica.

## 8. Desplegar Fabric App

```powershell
.\scripts\deploy_app.ps1
```

El script genera `.env.local`, instala dependencias y ejecuta:

```powershell
npx rayfin up --workspace-id $env:FABRIC_WORKSPACE_ID --yes
```

## 9. Probar

Abre la URL de la Fabric App y ejecuta la pregunta demo.
