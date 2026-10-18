# 1 · Requisitos de instalación y configuración del tenant

## 1.1 En tu equipo

| Herramienta | Versión | Para qué |
|---|---|---|
| Python | 3.11 o superior | La CLI `fabdemo` (solo depende de `azure-identity`, `azure-storage-file-datalake` y `requests`) |
| Azure CLI (`az`) | reciente | Autenticación del presentador (`az login`) y alta de grupos/apps en Entra |
| Git | — | Versionar las directivas (demo 4) |
| VS Code + GitHub Copilot (modo Agent) | — | Demo 5 (servidor MCP de Fabric) |
| Fabric CLI (`pip install ms-fabric-cli`) | opcional | Exploración en vivo (`fab ls`, `fab label`…); ver docs/03 |

```powershell
py -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -e .
fabdemo -h
```

## 1.2 Identidad del presentador

Una cuenta de usuario (no un service principal: la API de etiquetas `bulkSetLabels` solo admite usuarios) con:

| Rol | Dónde | Para qué |
|---|---|---|
| **Fabric Administrator** | Entra ID (rol de directorio) | Dominios, tags, etiquetas, tenant settings, activity events, directivas de tenant |
| **Capacity admin** de la capacidad de demo | Portal de administración de Fabric › Capacity settings | Activar policy sets de capacidad |
| Etiquetas `General` y `Confidencial-Finanzas` en su label policy | Purview › Information Protection | `bulkSetLabels` exige que el admin tenga la etiqueta publicada |
| **Information Protection Admin** (o superior) | Purview | Crear la protection policy (paso manual) |
| Miembro del grupo de certificadores | Tenant setting *Certification* | Certificar en vivo (demo 1) |

```powershell
az login --tenant <tenant-id> --allow-no-subscriptions
```

## 1.3 Capacidad

- Una capacidad **F** (F2 es suficiente) **dedicada a la demo**. La directiva de la demo 3 bloquea la creación de ítems en toda la capacidad.
- **Región soportada por Fabric Policies (preview)**: hoy *no* funcionan en **West Europe, North Europe ni West US**. `fabdemo check` lo comprueba. Una capacidad en *Spain Central*, *France Central* o *UK South* son buenas opciones (confírmalo en tu tenant).
- La capacidad debe estar **activa** (no pausada) durante el despliegue y las demos.

## 1.4 Entra ID: grupos y personas

Tres grupos de seguridad y dos service principals que actúan como «personas» de prueba:

```powershell
# Grupos
az ad group create --display-name "Ingenieros-Prod"    --mail-nickname ingenieros-prod
az ad group create --display-name "Finanzas-Analistas" --mail-nickname finanzas-analistas
az ad group create --display-name "Analistas-Norte"    --mail-nickname analistas-norte
az ad group create --display-name "Fabric-API-SPs"     --mail-nickname fabric-api-sps   # para el tenant setting de SPs

# Personas (repite para fabdemo-outsider)
$app = az ad app create --display-name fabdemo-engineer --query appId -o tsv
$sp  = az ad sp create --id $app --query id -o tsv
az ad app credential reset --id $app --display-name fabdemo --years 1 --query password -o tsv   # → FABDEMO_ENGINEER_SECRET
az ad group member add --group "Ingenieros-Prod" --member-id $sp      # solo el engineer
az ad group member add --group "Fabric-API-SPs"  --member-id $sp      # los dos

# IDs que pide config.toml
az ad group show -g "Ingenieros-Prod" --query id -o tsv
az account show --query tenantId -o tsv
```

En `config.toml`: `client_id` = appId y `object_id` = id del service principal (`$sp`).
Las personas **no necesitan permisos de API en Entra**: Fabric autoriza a los service principals mediante el tenant setting.

> ¿Prefieres usuarios reales en lugar de SPs? Usa `type = "browser"` en `[personas.*]` y añade el `object_id` del usuario.
> Para la demo 2 en el portal es más visual usar un usuario real (ventana InPrivate).

## 1.5 Purview

| Elemento | Configuración |
|---|---|
| Etiqueta **General** | Sin protección. Ámbito: *Files & other data assets* |
| Etiqueta **Confidencial-Finanzas** | **Control de acceso** activado. Ámbito: *Files & other data assets* |
| Label policy | Publica ambas etiquetas al presentador (y a los grupos de Finanzas) |
| Protection policy | Manual, ver [docs/03](03-pasos-manuales.md#demo-2--protection-policy). **Créala ≥ 24 h antes** |
| Licencias | Microsoft 365 E3/E5 (Information Protection) |

GUID de las etiquetas (Security & Compliance PowerShell):

```powershell
Connect-IPPSSession
Get-Label | Select-Object DisplayName, ImmutableId
```

## 1.6 Tenant settings de Fabric

Portal de administración › Tenant settings. `fabdemo check` los busca por título y muestra su estado.

| Tenant setting | Valor | Demo |
|---|---|---|
| **Users can create Fabric items** | Habilitado | deploy |
| **Service principals can call Fabric public APIs** (Developer settings) | Habilitado para `Fabric-API-SPs` | Personas, CI/CD |
| **Policies (preview)** | Habilitado (al menos para el presentador) | 3 · 4 |
| **Allow users to apply sensitivity labels for content** (Information protection) | Habilitado | 1 · 2 |
| **Certification** (Endorsement and discovery) | Habilitado, presentador como certificador | 1 |
| **Domain admins can set default sensitivity labels for their domains** | Opcional | 1 |
| Ajuste del **servidor MCP de Fabric**, si aparece en tu tenant | Habilitado | 5 |

Además:

- **Admin monitoring workspace**: se crea la primera vez que un admin lo abre. Govern lo usa para los insights de administrador y se refresca **una vez al día**.
- **OneLake security** en `lh_finanzas`: si `fabdemo security apply` devuelve error, abre el lakehouse › *Manage OneLake security* para habilitarla y repite.

## 1.7 Comprobación final

```powershell
fabdemo check
```

Debe salir sin ✗. Los `?` son ajustes que no ha encontrado por título: revísalos a mano en el portal.
