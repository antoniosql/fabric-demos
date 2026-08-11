# Fabric Medallion Scaffold — FraSoHome

> Demo de la sesión **Dominios, Workspaces y Capacidades en Fabric — Diseña sin caos**
> (Microsoft Speakers Hub). Monta el **esqueleto medallón** de FraSoHome aplicando las cuatro
> decisiones de diseño: separación de **ítems**, **workspaces**, **dominios** y **capacidades**.

|  |  |
| --- | --- |
| **Caso** | Retail omnicanal de hogar y decoración (FraSoHome): CRM, e-commerce, POS, ERP |
| **Qué demuestra** | Diseño de dominio/workspaces/capacidad + medallión metadata-driven (Landing→Bronze→Silver→Gold) |
| **Stack** | Fabric (dominios, workspaces, Lakehouse, notebooks PySpark) · Python · REST API |
| **Datos** | `data/retail_omnicanal/*.csv` — fuentes FraSoHome con problemas de calidad reales |

---

## La idea en una frase

Cómo separes los **ítems** (lakehouses por capa o esquemas) condiciona tus **workspaces**, y estos
tus **dominios** y **capacidades**. Esta demo levanta ese esqueleto para FraSoHome y ejecuta un
medallión dirigido por metadatos que limpia y modela los datos hasta un *star schema*.

## Estructura

```
fabric-medallion-scaffold/
├── .agent/reference/         # "segundo cerebro" (naming, medallion, fab CLI) — NO versionado
├── agents.md · CLAUDE.md     # contexto de agente — NO versionado
├── .mcp/mcp.json             # MCP (fab CLI) — NO versionado
├── config/
│   ├── workspaces.json       # diseño: dominio, workspaces por capa, capacidad (separated | collapsed)
│   └── ingestion/*.json      # config metadata-driven por fuente (bronze + pistas de silver)
├── data/retail_omnicanal/    # muestra FraSoHome (CSV)
├── infra/                    # DESPLIEGUE (separado de la lógica de demo)
│   ├── fabric_client.py      # Fabric REST API + OneLake DFS API + auth interactivo, idempotente
│   ├── deploy.py             # crea infra, sube datos y publica notebooks (dry-run por defecto)
│   ├── upload_data.py        # sube config/ingestion/ + data/ a LH_Landing/Files (invocado por deploy.py)
│   ├── publish_notebooks.py  # publica src/notebooks/NB_*.py como notebooks Fabric (invocado por deploy.py)
│   ├── run_notebooks.py      # ejecuta NB_* en orden via `fab job run` (invocado por deploy.py)
│   └── teardown.py           # limpieza
├── src/                      # LÓGICA DE DEMO
│   ├── notebooks/            # NB_Load_Bronze_Retail · NB_Transform_Bronze_To_Silver · NB_Build_Gold_Star
│   └── local/run_medallion_local.py   # mismo flujo con pandas, sin tenant (para demo/pruebas)
├── tests/                    # pytest (nomenclatura + parsers)
├── pyproject.toml            # uv
└── .env.example
```

## Puesta en marcha

```bash
uv sync                       # crea .venv e instala dependencias
cp .env.example .env          # completa FABRIC_TENANT_ID y FABRIC_CAPACITY_ID
```

### 1) Demo local (sin tenant) — recomendada para presentar

Reproduce Landing→Bronze→Silver→Gold con pandas sobre los CSV de FraSoHome. Idempotente.

```bash
python src/local/run_medallion_local.py
```

Salida (`output/`): tablas `bronze/`, `silver/` y el *star schema* en `gold/`
(`dim_cliente`, `dim_producto`, `dim_tienda`, `dim_fecha`, `fact_ventas`), más un informe de
rechazos de calidad e integridad referencial (huérfanas), que evidencian las brechas intencionales
del caso.

### 2) Despliegue en Fabric

```bash
pip install ms-fabric-cli && fab auth login    # una vez: CLI para ejecutar los notebooks (fab job run)

python infra/deploy.py                 # DRY-RUN: muestra el plan completo (infra + datos + notebooks + ejecucion)
python infra/deploy.py --apply         # TODO de extremo a extremo: infra, datos, publica y ejecuta NB_* en orden
python infra/deploy.py --design collapsed --apply   # variante de equipo pequeño (Caso A)
python infra/deploy.py --apply --skip-upload --skip-notebooks --skip-run   # solo infraestructura
```

Un único `--apply` hace todo: `deploy.py` crea dominio/workspaces/lakehouses/capacidad y, con el
mismo login (Fabric REST API), invoca automáticamente:

- `infra/upload_data.py` — sube cada `config/ingestion/*.json` a `LH_Landing/Files/config/ingestion/`
  y su CSV asociado (`source_file`) a `landing_path`, vía OneLake DFS API.
- `infra/publish_notebooks.py` — publica `src/notebooks/NB_*.py` como notebooks Fabric (uno por capa
  Bronze/Silver/Gold), reejecutar actualiza la definición en vez de duplicar.
- `infra/run_notebooks.py` — ejecuta los tres notebooks en orden Bronze → Silver → Gold con
  `fab job run <workspace>.Workspace/<notebook>.Notebook` (síncrono, para en el primero que falle).
  Este paso usa el **Fabric CLI** (`fab`) como proceso aparte, no la Fabric REST API: requiere
  `pip install ms-fabric-cli` y `fab auth login` hechos de antemano (login propio del CLI, distinto
  del interactivo de los demás scripts).

Los tres también se pueden ejecutar sueltos (dry-run por defecto, `--apply` para de verdad):

```bash
python infra/upload_data.py --apply
python infra/publish_notebooks.py --apply     # requiere que los workspaces ya existan
python infra/run_notebooks.py --apply         # requiere `fab auth login`; notebooks ya publicados
```

### 3) Limpieza

```bash
python infra/teardown.py --apply       # elimina los workspaces de la demo
```

## Guion de la demo en vivo (5–7 min)

1. **Diseño**: abrir `config/workspaces.json` → dominio `Retail`, workspaces por capa, capacidad `CAP_Retail`.
2. **Plan**: `python infra/deploy.py` (dry-run) → se ve la separación ítems/workspaces/dominio/capacidad.
3. **Metadata-driven**: abrir un `config/ingestion/*.json` → así se parametriza la ingesta y el tipado.
4. **Medallión**: `python src/local/run_medallion_local.py` → Bronze fiel + trazabilidad, Silver limpio
   (fechas mixtas, `€`/coma decimal, IDs en minúscula), dedupe y *star schema* en Gold.
5. **Calidad**: comentar los rechazos y las huérfanas → por qué separar por capas ayuda al gobierno.

## Notas

- Idempotente de extremo a extremo: reejecutar deja el mismo estado.
- Autenticación interactiva (nunca desatendida). Sin secretos en el repo (`.env` ignorado).
- El "segundo cerebro" (`.agent/reference/`, `agents.md`, `CLAUDE.md`, `.mcp/`) se mantiene **local**
  y está excluido del control de versiones a propósito.
