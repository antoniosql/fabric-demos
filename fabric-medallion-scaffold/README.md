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
│   ├── fabric_client.py      # Fabric REST API + auth interactivo, idempotente
│   ├── deploy.py             # crea dominio/workspaces/lakehouses/capacidad (dry-run por defecto)
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
python infra/deploy.py                 # DRY-RUN: muestra el plan
python infra/deploy.py --apply         # crea dominio, workspaces por capa, lakehouses y asigna capacidad
python infra/deploy.py --design collapsed --apply   # variante de equipo pequeño (Caso A)
```

Después: sube `config/ingestion/` y `data/` a `LH_Landing/Files/` y ejecuta los notebooks
`NB_Load_Bronze_Retail` → `NB_Transform_Bronze_To_Silver` → `NB_Build_Gold_Star`
(o con `fab notebook run`, ver `.agent/reference/fabric_cli_notes.md`).

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
