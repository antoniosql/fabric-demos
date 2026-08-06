# FraSoHome ReturnOps 360 · Microsoft Fabric RAG Demo

Repositorio de demostración para la sesión **Microsoft Fabric Databases: desarrollando una solución RAG** en *Charlemos de SQL Server*.

La demo despliega por código una aplicación RAG empresarial para **FraSoHome**, un retailer ficticio de hogar y decoración. El caso central es una solicitud de devolución de un sofá modular con daño durante el transporte. La solución combina:

- **SQL Database in Microsoft Fabric** para datos operacionales, políticas, chunks, recuperación SQL y auditoría.
- **Fabric User Data Functions** como backend Python serverless para orquestar el RAG.
- **Fabric Apps / Rayfin** como frontend web desplegable en Fabric.
- **Fabric CLI (`fab`)**, `sqlcmd`, Python y Node.js para automatizar el despliegue.

> La demo está diseñada para que pueda ejecutarse incluso si las capacidades vectoriales SQL preview no están disponibles en tu tenant. Por defecto usa recuperación híbrida determinista en T-SQL + ranking en Python. El script `database/sql/90_optional_vector_preview.sql` deja preparado el camino para `vector`/`VECTOR_DISTANCE` cuando lo tengas habilitado.

## Arquitectura

```text
Usuario / agente soporte
        │
        ▼
Fabric App · Rayfin · React/Vite
        │  POST con token Entra
        ▼
Fabric User Data Function · answerReturnCase
        │  conexión Fabric administrada por alias
        ▼
SQL Database in Microsoft Fabric
  ├─ fraso.Customers / Orders / Products / Stock / ReturnCases
  ├─ rag.Documents / Chunks / ChunkEmbeddings
  ├─ rag.usp_get_return_case_context
  ├─ rag.usp_get_candidate_chunks
  └─ rag.AnswerAudit
```

## Requisitos

Herramientas locales:

- Python 3.10 o superior.
- Node.js 20 o superior.
- `sqlcmd` moderno con autenticación Microsoft Entra y soporte de `--authentication-method`.
- Fabric CLI, instalado desde el entorno Python del repo.

Herramientas instaladas automáticamente:

- Rayfin CLI (`@microsoft/rayfin-cli`), se instala como `devDependency` en el script `deploy_app.ps1`.

Requisitos en Microsoft Fabric:

- Tenant con Microsoft Fabric habilitado.
- Workspace con permisos suficientes.
- Capacidad Fabric asignada.
- Fabric Apps habilitado en el tenant si quieres desplegar la app Rayfin.
- User Data Functions habilitado si quieres publicar el backend serverless.

## Preparar entorno e identidades en Entra

Antes de ejecutar los scripts, prepara una identidad no interactiva para automatizar Fabric CLI y `sqlcmd`. La opción más simple para una demo local o pipeline básico es un **service principal con secreto**. Para runners en Azure, usa **managed identity** siempre que puedas.

### 1. Instala herramientas locales

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

node --version
npm --version
sqlcmd --version
fab --version
```

Si los scripts `.ps1` aparecen bloqueados tras descargar un ZIP:

```powershell
Get-ChildItem .\scripts\*.ps1 | Unblock-File
```

### 2. Crea el service principal de despliegue

En Microsoft Entra admin center:

1. Ve a **Identity > Applications > App registrations > New registration**.
2. Nombre sugerido: `frasohome-fabric-deployer`.
3. Usa **Accounts in this organizational directory only**.
4. Crea un **client secret** en **Certificates & secrets** y guarda el valor en un almacén seguro.
5. Copia el **Directory (tenant) ID** y el **Application (client) ID**.

Alternativa con Azure CLI, si tienes permisos para crear aplicaciones en Entra:

```powershell
az ad app create --display-name "frasohome-fabric-deployer"
az ad sp create --id "<application-client-id>"
az ad app credential reset --id "<application-client-id>" --display-name "frasohome-demo" --years 1
```

Rellena `.env` con:

```dotenv
FABRIC_TENANT_ID="00000000-0000-0000-0000-000000000000"
FAB_SPN_CLIENT_ID="00000000-0000-0000-0000-000000000000"
FAB_SPN_CLIENT_SECRET="<client-secret>"
FABRIC_SQL_AUTH_MODE="service-principal"
FABRIC_UDF_AUTH_MODE="service-principal"
```

No subas `.env` ni secretos al repositorio.

### 3. Autoriza la identidad en Fabric

En Fabric Admin Portal:

1. Abre **Tenant settings**.
2. Habilita **Allow service principals to use Fabric APIs**.
3. Limita el ajuste a un grupo de seguridad, por ejemplo `fabric-automation`.
4. Añade el service principal `frasohome-fabric-deployer` a ese grupo.

Puedes crear el grupo y añadir el service principal con Azure CLI:

```powershell
az ad group create --display-name "fabric-automation" --mail-nickname "fabric-automation"
$spObjectId = az ad sp show --id "<application-client-id>" --query id -o tsv
az ad group member add --group "fabric-automation" --member-id $spObjectId
```

Después, en el workspace de Fabric:

1. Abre **Manage access**.
2. Añade el service principal o el grupo de seguridad.
3. Asigna al menos **Contributor** para crear/desplegar items; usa **Admin** solo si tu tenant lo requiere para operaciones concretas.

### 4. Opción con managed identity

Si ejecutas los scripts desde una VM, Azure DevOps agent, Function, Container App u otro recurso Azure con managed identity:

1. Activa una **system-assigned managed identity** o asigna una **user-assigned managed identity**.
2. Añade esa identidad al grupo autorizado en Fabric Admin Portal.
3. Añade esa identidad al workspace de Fabric.
4. Crea su usuario en la SQL Database después de crear la base, igual que con el service principal.

Variables para managed identity del sistema:

```dotenv
FAB_MANAGED_IDENTITY="true"
FABRIC_SQL_AUTH_MODE="managed-identity"
FABRIC_UDF_AUTH_MODE="managed-identity"
```

Variables para user-assigned managed identity:

```dotenv
FAB_MANAGED_IDENTITY="true"
FAB_SPN_CLIENT_ID="00000000-0000-0000-0000-000000000000"
FABRIC_SQL_AUTH_MODE="managed-identity"
FABRIC_SQL_MANAGED_IDENTITY_CLIENT_ID="00000000-0000-0000-0000-000000000000"
FABRIC_UDF_AUTH_MODE="managed-identity"
FABRIC_UDF_MANAGED_IDENTITY_CLIENT_ID="00000000-0000-0000-0000-000000000000"
```

### 5. Crea la app registration del frontend

La identidad anterior automatiza despliegue y pruebas. La app React necesita otra app registration pública para que el usuario final inicie sesión con MSAL:

1. Crea una app registration llamada `frasohome-returnops-app`.
2. En **Authentication**, añade plataforma **Single-page application**.
3. Añade redirect URI `http://localhost:5173`.
4. Tras desplegar la Fabric App, añade también su URL final como redirect URI.
5. Copia el **Application (client) ID** y el **Directory (tenant) ID**.

Rellena:

```dotenv
VITE_ENTRA_CLIENT_ID="00000000-0000-0000-0000-000000000000"
```

`VITE_ENTRA_TENANT_ID` se genera desde `FABRIC_TENANT_ID` al ejecutar `scripts/deploy_app.ps1`; solo necesitas definirlo aparte si el frontend usa otro tenant.

Más detalle y variantes con certificado o federated credentials: [Autenticación no interactiva](docs/NON_INTERACTIVE_AUTH.md).

## Estructura del repositorio

```text
.
├─ app/frasohome-returnops-app/       # Frontend Fabric App / Rayfin / React
├─ database/sql/                      # DDL, seed data, procs y smoke tests
├─ fabric/items/                      # Item definition para fab deploy
├─ scripts/                           # Automatización local
├─ tools/                             # Utilidades de test y embeddings demo
├─ docs/                              # Guía de despliegue, arquitectura y guion de demo
└─ .github/workflows/                 # Pipeline ejemplo para items Fabric
```

## Entorno Python local

Crea un entorno virtual e instala las dependencias Python desde la raíz del repositorio.

En macOS/Linux o Git Bash:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Despliegue rápido

1. Copia el archivo de variables:

```powershell
Copy-Item .env.example .env
```

Si PowerShell indica que `bootstrap.ps1` no está firmado, el archivo está marcado como descargado de Internet. Desbloquea los scripts antes de ejecutarlos:

```powershell
Get-ChildItem .\scripts\*.ps1 | Unblock-File
```

Si tu política local sigue bloqueando scripts en esa sesión, usa:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

2. Edita `.env` con el workspace y nombres de recursos:

```bash
FABRIC_WORKSPACE_NAME="FrasoHome Fabric RAG Demo"
FABRIC_WORKSPACE_ID="00000000-0000-0000-0000-000000000000"
FABRIC_SQL_DATABASE_NAME="FrasoHomeRagDB"
```

3. Instala prerequisitos de la demo:

```powershell
.\scripts\bootstrap.ps1
```

Para evitar autenticación interactiva con navegador, configura `FABRIC_TENANT_ID`, las variables `FAB_*` de identidad y `FABRIC_SQL_AUTH_MODE` descritas en [Autenticación no interactiva](docs/NON_INTERACTIVE_AUTH.md). Los scripts reutilizan `FABRIC_TENANT_ID` como `FAB_TENANT_ID` cuando `fab` lo necesita; Rayfin aún puede requerir sesión interactiva para `deploy_app.ps1` porque sus opciones de service principal aparecen en la ayuda pero no están soportadas actualmente.

4. Crea la SQL Database en Fabric:

```powershell
.\scripts\deploy_fabric_sql.ps1
```

5. Prepara la identidad para conectar a la SQL Database.

`apply_sql.ps1` no puede crear el usuario con el que va a autenticarse, porque ese usuario ya debe existir para que `sqlcmd` pueda abrir conexión. Una vez creada la base, entra con un administrador Microsoft Entra de la SQL Database y crea el usuario de despliegue. Para SQL Database in Fabric, el patrón más directo para service principals es crear el usuario con el **Application (client) ID**:

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

Además del usuario SQL, la identidad debe tener permiso **Read** sobre el item SQL Database en Fabric. Si sigue apareciendo `Cannot open server ... requested by the login`, revisa en Fabric que el service principal o el grupo donde está tenga acceso al workspace o al item `FrasoHomeRagDB`.

Ese rol amplio es práctico para una demo porque los scripts crean esquemas, tablas, procedimientos y permisos. Después de ejecutar `apply_sql.ps1`, si quieres una identidad de ejecución con permisos mínimos, usa el rol `frasohome_rag_executor` creado por `database/sql/06_create_security.sql`. Cambia el placeholder por un usuario, grupo, service principal o managed identity que exista realmente en Entra:

```sql
CREATE USER [<runtime-user-upn-or-display-name>] FROM EXTERNAL PROVIDER;
ALTER ROLE frasohome_rag_executor ADD MEMBER [<runtime-user-upn-or-display-name>];
```

El error `Principal '<nombre>' could not be found` significa que SQL no encuentra esa identidad en Entra o que ese tipo de principal no está soportado con ese nombre.

6. Copia el **server name** de la conexión SQL desde Fabric y completa `.env`:

```bash
FABRIC_SQL_SERVER="tcp:<server>.database.fabric.microsoft.com,1433"
FABRIC_SQL_DATABASE_NAME="FrasoHomeRagDB"
```

7. Aplica DDL, datos de demo y procedimientos:

```powershell
.\scripts\apply_sql.ps1
```

8. Publica la User Data Function:

```powershell
.\scripts\publish_udf.ps1
```

9. En el portal de Fabric, abre el item `FrasoHome_RAG_UDF`, confirma/publica si el portal lo solicita, habilita el endpoint público de `answerReturnCase` y copia su URL en `.env`:

```bash
VITE_UDF_FUNCTION_URL="https://.../answerReturnCase"
```

10. Configura una app registration en Microsoft Entra para el frontend y rellena:

```bash
VITE_ENTRA_CLIENT_ID="..."
```

El tenant se toma de `FABRIC_TENANT_ID` durante `deploy_app.ps1`.

11. Despliega la Fabric App:

```powershell
.\scripts\deploy_app.ps1
```

## Despliegue de una sola vez

El script `deploy_all.ps1` automatiza la mayor parte del flujo, pero hay dos datos que normalmente siguen necesitando confirmación manual según el tenant: el TDS endpoint de la SQL Database y la URL pública de la User Data Function.

```powershell
.\scripts\deploy_all.ps1
```

## Smoke test de base de datos

```powershell
.\scripts\smoke_test_sql.ps1
```

## Ingesta realista de políticas Markdown

Además de los datos semilla SQL, el repo incluye un flujo más parecido a producción para convertir políticas Markdown en conocimiento RAG:

```text
docs/policies/*.md
        │
        ▼
tools/ingest_policy_markdown.py
        ├─ lee frontmatter
        ├─ genera chunks por secciones/párrafos
        ├─ calcula embeddings deterministas de demo
        └─ emite SQL idempotente
        │
        ▼
scripts/ingest_policy_markdown.ps1
        └─ inserta en rag.Documents, rag.Chunks y rag.ChunkEmbeddings con sqlcmd
```

Ejecuta:

```powershell
.\scripts\ingest_policy_markdown.ps1
```

El script lee por defecto `docs/policies`, genera `database/generated/ingest_policy_markdown.sql`, lo aplica en la SQL Database y ejecuta `database/sql/98_smoke_test_markdown_ingestion.sql`.

El smoke test comprueba que los documentos Markdown `MD-POL-DMG-010` y `MD-POL-VIP-011` aparecen entre los chunks candidatos para una pregunta similar a la demo:

```text
El cliente Gold quiere devolver un sofá modular comprado online hace 34 días. Indica que llegó con una pata dañada, conserva fotos del embalaje y solicita reemplazo urgente. ¿Debemos aprobar devolución, reemplazo o revisión manual?
```

Los embeddings generados son deterministas y locales (`demo-hash-embedding-v1`) para que la demo no dependa de servicios externos. En una implantación real, esa función sería el punto natural para llamar a Azure OpenAI / Foundry embeddings y guardar el vector resultante en `rag.ChunkEmbeddings` o en una columna `vector` si está habilitada.

## Búsqueda híbrida lexical + vectorial

La recuperación base de la UDF usa `rag.usp_get_candidate_chunks`: filtra por contexto del caso y calcula un score lexical de negocio con T-SQL. Para enseñar un patrón híbrido más realista, el repo añade `rag.usp_get_hybrid_candidate_chunks`.

Ese procedimiento combina:

- **Lexical score**: coincidencias por país, canal, categoría, vigencia y señales como daño, embalaje, fotos, reemplazo, stock, cliente Gold/Platinum o producto voluminoso.
- **Vector score**: similitud coseno entre el embedding de la pregunta y los embeddings guardados en `rag.ChunkEmbeddings`.
- **Hybrid score**: mezcla ponderada de ambos scores.

Ejecuta una búsqueda híbrida de prueba:

```powershell
.\scripts\hybrid_search.ps1
```

El script:

1. Aplica `database/sql/07_create_hybrid_search.sql`.
2. Genera el embedding de la pregunta con `tools/render_hybrid_search_sql.py`.
3. Renderiza `database/generated/hybrid_search_query.sql`.
4. Ejecuta `rag.usp_get_hybrid_candidate_chunks` con `sqlcmd`.

Pesos configurables:

```dotenv
RAG_HYBRID_LEXICAL_WEIGHT="0.55"
RAG_HYBRID_VECTOR_WEIGHT="0.45"
```

Por defecto los embeddings son deterministas de demo. Para usar embeddings reales de Azure OpenAI en la ingesta y en la consulta, configura:

```dotenv
RAG_EMBEDDING_PROVIDER="azure-openai"
RAG_USE_EXTERNAL_MODELS="true"
AZURE_OPENAI_ENDPOINT="https://<recurso>.openai.azure.com"
AZURE_OPENAI_API_KEY="<api-key>"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT="<deployment-name>"
AZURE_OPENAI_API_VERSION="2024-10-21"
```

La regla importante es que documentos y preguntas deben usar el mismo proveedor y modelo de embeddings.

## Probar la User Data Function desde consola

```powershell
python -m pip install -r requirements.txt
python tools/call_udf.py --auth-mode service-principal --return-case-id "RET-2026-004219"
```

## Pregunta demo

```text
El cliente quiere devolver un sofá modular comprado online hace 34 días. Indica que llegó con una pata dañada, conserva fotos del embalaje y solicita reemplazo urgente. ¿Debemos aprobar devolución, reemplazo o revisión manual?
```

Respuesta esperada:

```text
Recomendación: aprobar reemplazo prioritario condicionado a validación visual.
```

Con evidencias de:

- `POL-DMG-002` · daños en transporte.
- `POL-MUE-003` · productos voluminosos.
- `POL-VIP-004` · priorización de clientes Gold.

## Notas importantes

- No pongas secretos de Azure OpenAI, Foundry o claves de API en el frontend.
- El backend de demo genera una respuesta determinista y auditable. Puedes activar un LLM real sustituyendo la función `_generate_answer` en `function_app.py` por una llamada a Azure OpenAI / Foundry gestionada desde backend.
- `fab deploy` publica los items definidos bajo `fabric/items`; la SQL Database se crea con `fab create` porque las bases de datos SQL se inicializan como servicio de Fabric y luego se configuran con T-SQL.
- Rayfin despliega la experiencia de aplicación estática/autenticada; el RAG, la lógica de backend y la auditoría viven en User Data Functions y SQL Database in Fabric.
