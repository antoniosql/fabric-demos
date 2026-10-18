# MIDP · OneLake Catalog — demos as code

Despliegue reproducible de las 5 demos de la sesión **«OneLake Catalog: el gobierno de Fabric cambia de casa»**
(MIDP Spanish Group). Todo se crea y se opera con las **REST APIs de Fabric** desde una CLI en Python puro (`fabdemo`):
dominio, workspaces, roles, tags, lakehouse con datos simulados, OneLake security, etiquetas, Fabric Policies y auditoría.

> ⚠️ **Usa un tenant y una capacidad de demo.** La directiva de la demo 3 bloquea la creación de ítems en **toda la
> capacidad**, y las Fabric Policies están en preview. Nunca lo despliegues sobre una capacidad compartida.

## En 5 minutos

```powershell
# 1. Requisitos: Python 3.11+, Azure CLI y un usuario Fabric admin + capacity admin (ver docs/01-requisitos.md)
git clone <este-repo> ; cd midp-onelake-catalog-demos
py -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -e .

# 2. Configuración
copy config\config.example.toml config\config.toml   # y rellena IDs de tenant, capacidad, grupos, etiquetas y personas
$env:FABDEMO_ENGINEER_SECRET = "..." ; $env:FABDEMO_OUTSIDER_SECRET = "..."
az login --tenant <tenant-id> --allow-no-subscriptions

# 3. Comprobar, ensayar y desplegar
fabdemo check                 # capacidad, región, tenant settings y personas
fabdemo --dry-run deploy      # ensayo sin tocar el tenant (imprime cada llamada)
fabdemo deploy                # despliegue real, idempotente
```

Después sigue el guion: [docs/02-guion-demos.md](docs/02-guion-demos.md).

## Qué despliega

```
MIDP Finanzas (dominio)  ── tags de dominio: Facturación · Contabilidad · Datos maestros · Fuente SAP
 ├─ MIDP-Fin-Prod-Analytics   lh_finanzas (clientes, facturas) · nb_generar_datos · roles OneLake security (RLS/CLS)
 ├─ MIDP-Fin-Prod-Reporting
 └─ MIDP-Fin-Dev
MIDP-Gobierno-Admin (fuera del dominio)  ── PolicySet-Capacidad-Demo (Fabric Policies)
```

| Grupo / persona | Prod-Analytics | Prod-Reporting | Dev |
|---|---|---|---|
| Ingenieros-Prod | Contributor | Contributor | — |
| Finanzas-Analistas | Viewer | Viewer | — |
| Analistas-Norte | Viewer (+ rol RLS/CLS) | — | — |
| persona `engineer` (SP, en Ingenieros-Prod) | Contributor | Contributor | Contributor |
| persona `outsider` (SP, sin grupos) | Contributor | Contributor | Contributor |

Las personas son Contributor en todo a propósito: así, lo que las bloquea en las demos son **las directivas y las
protection policies**, no los roles de workspace.

## Comandos

| Comando | Para qué |
|---|---|
| `fabdemo check` | Verifica config, capacidad (y su región), tenant settings y credenciales de las personas |
| `fabdemo deploy [--only platform,data,notebook,security]` | Despliegue idempotente |
| `fabdemo data load --days 3 --rows 5000 --bad-rows 20` | Carga incremental simulada (con filas erróneas opcionales) |
| `fabdemo data stream --every 30 --batches 20` | Lotes periódicos para simular actividad «en vivo» |
| `fabdemo data notebook` | Ejecuta el notebook Spark de carga masiva (1M filas por defecto) |
| `fabdemo demo1 drift \| status \| fix [--all] \| reset` | Govern: genera ítems sin gobernar y los corrige |
| `fabdemo demo2 label \| probe --persona outsider \| unlabel` | Etiqueta Confidencial y comprueba el acceso |
| `fabdemo demo3 apply v1 \| apply v2 \| probe --persona X \| status \| off` | Fabric Policies y la trampa de la allow list |
| `fabdemo demo4 diff \| deploy <fichero> \| activate \| export` | Directivas como código |
| `fabdemo demo5` | Configuración MCP y prompts para Copilot |
| `fabdemo security show \| apply` | Roles de OneLake security (RLS/CLS) |
| `fabdemo audit --hours 2 --contains Policy` | Actividad reciente desde el registro de actividad |
| `fabdemo status` / `fabdemo teardown --yes` | Estado del despliegue / borrar todo |

Todos aceptan `--dry-run` (no llama a Fabric) y `-v` (muestra cada llamada a la API, útil para enseñarla en la sesión).
El dry-run guarda sus IDs ficticios en `.state/state.dryrun.json`, separado del estado real.

Pruebas del cliente (sin tenant): `pip install -e .[dev]` y `pytest`.

## Estructura

```
config/config.example.toml   plantilla de configuración (config.toml queda fuera de git)
policies/*.json              directivas como código (placeholders {{ws.*}}, {{group.*}})
security/onelake-roles.json  roles de OneLake security con RLS y CLS
notebooks/*.ipynb            notebook Spark de carga masiva
.vscode/mcp.json             servidor MCP remoto de Fabric (demo 5)
src/fabdemo/                 CLI: client.py (REST, LRO, 429, paginación) · fabric.py · data.py · policies.py · security.py · commands.py
docs/                        requisitos, guion, pasos manuales y referencia de APIs
tests/                       pruebas del cliente REST (429, LRO, paginación) y de las plantillas
.state/                      IDs desplegados (fuera de git)
```

## Documentación

1. [Requisitos de instalación y configuración del tenant](docs/01-requisitos.md)
2. [Guion de las demos](docs/02-guion-demos.md)
3. [Pasos sin API (Purview, endorsement…)](docs/03-pasos-manuales.md)
4. [APIs utilizadas y su estado](docs/04-apis.md)
