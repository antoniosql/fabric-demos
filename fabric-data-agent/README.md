# Fabric Data Agent — Demo (FraSoHome)

Despliegue **desde cero** de la demo *"Fabric Data Agents: el chatbot que sí sabe de tus datos"*


El script crea un **workspace** de Fabric, lo asigna a tu **capacidad**, crea un **Lakehouse**, sube
los datos del modelo retail de **FraSoHome** e importa dos notebooks: uno que **construye las tablas y
crea/publica el Data Agent** con el SDK, y otro que lo **evalúa** con un set de referencia.

---

## Contenido del repo

```
fabric-data-agent/
├── README.md
├── config.example.json          # Plantilla de configuración (rellena config.local.json)
├── .gitignore
├── data/                         # Modelo retail FraSoHome + set de evaluación
│   ├── FS_Clientes.csv           # -> DimCustomer
│   ├── FS_Tiendas.csv            # -> DimStore
│   ├── FS_Productos.csv          # -> DimProduct
│   ├── FS_VentasResumenDiario.csv# -> FactSalesDaily
│   ├── FS_StockDiario.csv        # -> FactStockDaily
│   ├── FS_DevolucionesFact.csv   # -> FactReturns
│   ├── FS_Alertas_Stockout.csv   # -> AlertasStockout
│   └── FS_TestSet_Metrico_Mixto.csv   # ground truth para la evaluación
├── notebooks/
│   ├── 00_setup_data_agent.ipynb # carga tablas + crea/configura/publica el Data Agent (SDK)
│   └── 01_evaluate_agent.ipynb   # evalúa el agente con el set de referencia
└── scripts/
    ├── FabricApi.psm1            # Módulo auxiliar (REST Fabric + subida a OneLake)
    ├── deploy.ps1               # Despliegue de infraestructura + notebooks
    └── cleanup.ps1             # Borra el workspace (no la capacidad)
```

---

## Requisitos previos

1. **PowerShell 7+** (`pwsh`) y **Azure CLI** (`az`).
2. Un usuario que pueda crear workspaces, **asignarlos a la capacidad** y sea **administrador de la
   capacidad**.
3. La **capacidad Fabric** activa y con soporte para Data Agents.
4. Tenant switch de **Copilot / funciones basadas en Azure OpenAI** habilitado, y (según región) el
   de **cross-geo processing/storing for AI**.

---

## Despliegue

```powershell
# 1) Autentícate en el tenant correcto
az login --tenant <TU_TENANT_ID>

# 2) Copia la config y rellénala
Copy-Item config.example.json config.local.json
#   Edita config.local.json: tenantId, subscriptionId, capacityResourceId, capacityName

# 3) Despliega la infraestructura y los notebooks
./scripts/deploy.ps1
```

Después, en el portal de Fabric:

1. Abre **`00_setup_data_agent`** y ejecútalo de arriba a abajo. Esto:
   - carga los CSV en tablas Delta (`DimCustomer`, `FactSalesDaily`, …),
   - crea el **FraSoHome BI Agent**, le pone instrucciones y ejemplos, añade el Lakehouse y lo **publica**.
2. Abre el **FraSoHome BI Agent** y prueba preguntas (en inglés).
3. Ejecuta **`01_evaluate_agent`** para medir la calidad con el set de referencia.

> Los notebooks se importan con el Lakehouse ya asociado como **lakehouse por defecto**.

---

## Qué hace el despliegue (`deploy.ps1`)

1. Tokens de acceso vía Azure CLI (Fabric API y OneLake storage).
2. Localiza la capacidad indicada en `config.local.json`.
3. Crea (o reutiliza) el workspace `FraSoHome-Data-Agent` y lo **asigna a la capacidad**.
4. Crea (o reutiliza) el Lakehouse `lh_frasohome`.
5. Sube los CSV a `Files/frasohome/`.
6. Importa los notebooks de setup y evaluación con el Lakehouse por defecto vinculado.

Es **idempotente**.

> **Nota técnica (fix aplicado):** el endpoint `assignToCapacity` devuelve **202 sin cabecera
> `Location`** (no expone una operación consultable), a diferencia de la creación de items. Por eso el
> módulo usa `Wait-FabricWorkspaceCapacity`, que **sondea `GET /workspaces/{id}`** hasta que
> `capacityId` refleja la asignación, en lugar del polling genérico de operaciones.

---

## La demo

Modelo retail *gold* de FraSoHome con preguntas de negocio en lenguaje natural:

| Pregunta | Qué enseña |
| --- | --- |
| Net online sales between 2026-02-01 and 2026-02-15 | Filtro por canal y periodo |
| Which store had the highest net sales on 2026-02-10? | Ranking por tienda |
| Which return reasons drive the highest refund amount? | Postventa y coste |
| Which products have a high-priority stockout alert? | Priorización operativa |
| Show me the sales by product for MAD01 | **Prueba negativa**: `FactSalesDaily` no tiene grano de producto |

La evaluación usa `FS_TestSet_Metrico_Mixto.csv` como *ground truth* y `evaluate_data_agent`.

---

## Limpieza

```powershell
./scripts/cleanup.ps1        # pide confirmación; borra el workspace, no la capacidad
```

---

## Notas

- Data Agents: **solo inglés**, respuestas limitadas a **25 filas × 25 columnas**, **sin** datos no
  estructurados. Consulta permisos (RLS/CLS) y políticas de Purview.
- El SDK (`fabric-data-agent-sdk`) está en **preview**; el agente se consume tras publicarlo por su
  **endpoint MCP**. La API usada: `create_data_agent`, `update_settings(ai_instructions=…)`,
  `add_staging_datasource(...)`, `publish_staging(...)`.
- `config.local.json` está en `.gitignore` para no versionar tus identificadores.
