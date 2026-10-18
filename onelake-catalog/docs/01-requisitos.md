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

Tres grupos de seguridad y tres usuarios de prueba. Usa un dominio verificado del tenant para los UPN. Crea solo los grupos que aún no existan y ejecuta la creación de usuarios una sola vez, con una cuenta con permisos para crear usuarios y grupos en Entra ID.

```powershell
# Grupos
az ad group create --display-name "Ingenieros-Prod"    --mail-nickname ingenieros-prod
az ad group create --display-name "Finanzas-Analistas" --mail-nickname finanzas-analistas
az ad group create --display-name "Analistas-Norte"    --mail-nickname analistas-norte

# Sustituye por un dominio verificado que aparezca en `az ad domain list`.
$upnSuffix = "vernedev.onmicrosoft.com"

# Contraseña común y sencilla para este tenant de demo.
$demoPassword = "Demo2026!"

function New-DemoUser($displayName, $upn) {
    az ad user create --display-name $displayName --user-principal-name $upn `
        --password $demoPassword --query id -o tsv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear $upn." }
}

$engineerId = New-DemoUser "Demo Ingeniería" "fabdemo-engineer@$upnSuffix"
$analystId  = New-DemoUser "Demo Analista Norte" "fabdemo-analista-norte@$upnSuffix"
$outsiderId = New-DemoUser "Demo Externo" "fabdemo-outsider@$upnSuffix"

# Ingeniería solo pertenece a Ingenieros-Prod.
az ad group member add --group "Ingenieros-Prod" --member-id $engineerId

# El analista pertenece a ambos grupos para superar la protection policy
# y probar el filtrado RLS/CLS de OneLake.
az ad group member add --group "Finanzas-Analistas" --member-id $analystId
az ad group member add --group "Analistas-Norte" --member-id $analystId

# El externo no se añade a ningún grupo de negocio.

# IDs para config.toml: tenant, grupos y object IDs de los usuarios.
az account show --query tenantId -o tsv
az ad group show -g "Ingenieros-Prod" --query id -o tsv
az ad group show -g "Finanzas-Analistas" --query id -o tsv
az ad group show -g "Analistas-Norte" --query id -o tsv
az ad user show --id "fabdemo-engineer@$upnSuffix" --query id -o tsv
az ad user show --id "fabdemo-outsider@$upnSuffix" --query id -o tsv
```

Los tres usuarios comparten la contraseña `Demo2026!`; no se fuerza el cambio en el primer inicio de sesión. Es una credencial solo para la demo: úsala únicamente en un tenant de pruebas.

El `object_id` de `config.toml` es el ID de objeto del usuario (los `$engineerId` y `$outsiderId` anteriores); `login_hint` es su UPN. `Analista Norte` se prueba iniciando sesión en el portal con ese usuario. **No lo añadas a `[personas.*]`**: el despliegue asigna Contributor a las personas configuradas, mientras que el grupo `Analistas-Norte` debe conservar el rol Viewer y el filtrado RLS/CLS.

Si prefieres probar con service principals en vez de usuarios interactivos, crea el grupo adicional `Fabric-API-SPs`, agrega ambos SP y habilita para ese grupo el tenant setting *Service principals can call Fabric public APIs*. Mantén entonces comentada la configuración de navegador y usa los bloques de SP alternativos de `config.toml`.

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
