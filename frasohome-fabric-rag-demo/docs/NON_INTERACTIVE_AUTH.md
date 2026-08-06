# Autenticación no interactiva

Esta demo puede automatizar Fabric CLI (`fab`) y `sqlcmd` sin abrir navegador usando service principals o managed identities.

## Requisitos de tenant y permisos

- En Fabric Admin Portal, habilita **Allow service principals to use Fabric APIs** para el grupo de seguridad donde esté el service principal o la managed identity.
- Añade esa identidad al workspace con permisos suficientes para crear/desplegar items.
- Para ejecutar T-SQL, crea un usuario de base de datos para esa identidad después de crear la SQL Database y antes de lanzar `apply_sql.ps1`.
- No guardes secretos reales en Git. Usa `.env` local, GitHub Actions secrets, Azure DevOps secret variables o federated credentials.

Ejemplo orientativo para preparar la identidad en SQL, ejecutado una vez con un administrador Microsoft Entra de la base de datos. Para service principals en SQL Database in Fabric, usa el Application (client) ID como `SID`:

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

`apply_sql.ps1` no puede crear este usuario cuando se autentica con esa misma identidad, porque `sqlcmd` necesita que el usuario ya exista para abrir la conexión inicial.

Además del usuario SQL, la identidad debe tener permiso **Read** sobre el item SQL Database en Fabric. Si el login sigue fallando, revisa en Fabric que el service principal o el grupo donde está tenga acceso al workspace o al item de base de datos.

Para una identidad que solo invoque procedimientos de la demo después del despliegue, usa el rol limitado que crea `06_create_security.sql`:

```sql
CREATE USER [<runtime-user-upn-or-display-name>] FROM EXTERNAL PROVIDER;
ALTER ROLE frasohome_rag_executor ADD MEMBER [<runtime-user-upn-or-display-name>];
```

`FROM EXTERNAL PROVIDER` resuelve identidades existentes en Microsoft Entra; si aparece `Principal '<nombre>' could not be found`, revisa que el usuario, grupo, service principal o managed identity exista y que estás usando su nombre resoluble.

## Opción A: service principal con secreto

En `.env`:

```dotenv
FABRIC_TENANT_ID="00000000-0000-0000-0000-000000000000"
FAB_SPN_CLIENT_ID="00000000-0000-0000-0000-000000000000"
FAB_SPN_CLIENT_SECRET="<client-secret>"

FABRIC_SQL_AUTH_MODE="service-principal"
FABRIC_UDF_AUTH_MODE="service-principal"
```

Los scripts PowerShell cargan `.env`, reutilizan `FABRIC_TENANT_ID` como `FAB_TENANT_ID` para compatibilidad con `fab` y, para SQL, `apply_sql.ps1` invoca `sqlcmd` con `ActiveDirectoryServicePrincipal`.

## Opción B: service principal con certificado

En `.env`:

```dotenv
FABRIC_TENANT_ID="00000000-0000-0000-0000-000000000000"
FAB_SPN_CLIENT_ID="00000000-0000-0000-0000-000000000000"
FAB_SPN_CERT_PATH="C:\certs\fabric-spn.pfx"
FAB_SPN_CERT_PASSWORD="<certificate-password>"

FABRIC_SQL_AUTH_MODE="default"
```

El certificado aplica a Fabric CLI. Para `sqlcmd`, usa `FABRIC_SQL_AUTH_MODE="default"` si tu entorno expone credenciales compatibles con `ActiveDirectoryDefault`, o usa secreto/managed identity para la conexión SQL.

## Opción C: federated credential

En pipelines con OIDC, define:

```dotenv
FABRIC_TENANT_ID="00000000-0000-0000-0000-000000000000"
FAB_SPN_CLIENT_ID="00000000-0000-0000-0000-000000000000"
FAB_SPN_FEDERATED_TOKEN="<token-oidc>"

FABRIC_SQL_AUTH_MODE="default"
```

En GitHub Actions normalmente no se escribe el token en `.env`: se obtiene en el job y se expone como variable de entorno/secreto temporal.

## Opción D: managed identity

En una VM o recurso Azure con managed identity:

```dotenv
FAB_MANAGED_IDENTITY="true"
FABRIC_SQL_AUTH_MODE="managed-identity"
FABRIC_UDF_AUTH_MODE="managed-identity"
```

Para una user-assigned managed identity:

```dotenv
FAB_MANAGED_IDENTITY="true"
FAB_SPN_CLIENT_ID="00000000-0000-0000-0000-000000000000"
FABRIC_SQL_AUTH_MODE="managed-identity"
FABRIC_SQL_MANAGED_IDENTITY_CLIENT_ID="00000000-0000-0000-0000-000000000000"
FABRIC_UDF_AUTH_MODE="managed-identity"
FABRIC_UDF_MANAGED_IDENTITY_CLIENT_ID="00000000-0000-0000-0000-000000000000"
```

## Ejecutar

```powershell
.\scripts\bootstrap.ps1
.\scripts\deploy_fabric_sql.ps1
.\scripts\apply_sql.ps1
.\scripts\publish_udf.ps1
python tools/call_udf.py --auth-mode service-principal
```

## Limitación actual de Rayfin

Rayfin CLI todavía no soporta autenticación no interactiva (service principal) en `rayfin up`. Por eso `deploy_app.ps1` **requiere una sesión Rayfin interactiva** aún cuando todos los demás scripts se ejecuten sin navegador. 

Cuando `deploy_app.ps1` llama a `npx rayfin up`, se abrirá un navegador para autenticar tu cuenta personal de Fabric. Las identidades de service principal se usan solo para SQL, UDF y pruebas, no para el despliegue de la app.

Si necesitas un despliegue completamente automatizado, puedes:
1. Pre-autenticar en una sesión local: `npx rayfin login` desde `app/frasohome-returnops-app`
2. Cachear esa sesión y reutilizarla en pipelines CI/CD (depende de cómo tu runner maneje cookies/cache de Rayfin)

## Login del usuario final

La app React sigue usando MSAL en navegador para que un usuario final invoque la UDF con permisos delegados. Esa autenticación pertenece a la experiencia de usuario de la demo, no al despliegue automatizado. Service principal y managed identity se usan para automatizar despliegue, SQL y pruebas de consola.

## Referencias

- Fabric CLI authentication and environment variables: https://microsoft.github.io/fabric-cli/essentials/env_vars/
- Fabric CLI auth examples: https://microsoft.github.io/fabric-cli/examples/auth_examples/
- Rayfin CLI reference: https://learn.microsoft.com/en-us/fabric/apps/cli-reference
