# 4 · APIs utilizadas

Base: `https://api.fabric.microsoft.com/v1` (token `https://api.fabric.microsoft.com/.default`), salvo indicación.

| Área | Operación | Endpoint | Identidad | Estado | Módulo |
|---|---|---|---|---|---|
| Capacidades | List Capacities | `GET /capacities` | User/SP | GA | fabric.py |
| Workspaces | Create / List / Assign to capacity / Delete | `POST /workspaces` · `GET /workspaces` · `POST /workspaces/{id}/assignToCapacity` · `DELETE /workspaces/{id}` | User/SP | GA | fabric.py |
| Workspaces | Add Role Assignment | `POST /workspaces/{id}/roleAssignments` | User/SP | GA | fabric.py |
| Dominios (admin) | Create / List / Delete | `POST /admin/domains` · `GET /admin/domains` · `DELETE /admin/domains/{id}` | User/SP, Fabric admin | GA | fabric.py |
| Dominios (admin) | Assign Workspaces By Ids | `POST /admin/domains/{id}/assignWorkspaces` | Fabric admin | GA | fabric.py |
| Dominios (admin) | Role Assignments Bulk Assign | `POST /admin/domains/{id}/roleAssignments/bulkAssign` | Fabric admin | GA | fabric.py |
| Tags (admin) | Bulk Create / List / Delete | `POST /admin/tags/bulkCreateTags` · `GET /admin/tags` · `DELETE /admin/tags/{id}` | User/SP, Fabric admin | GA | fabric.py |
| Tags | Apply Tags | `POST /workspaces/{ws}/items/{id}/applyTags` | User/SP | GA | fabric.py |
| Ítems | Create / List / Update / Delete / Update Definition / Get Definition | `/workspaces/{ws}/items[...]` | User/SP | GA | fabric.py, policies.py |
| Lakehouse | Create Lakehouse | `POST /workspaces/{ws}/lakehouses` | User/SP | GA | fabric.py |
| Lakehouse | Load Table | `POST /workspaces/{ws}/lakehouses/{lh}/tables/{t}/load` | User/SP | **Preview**, sin esquemas | data.py |
| OneLake (DFS) | Upload file / List paths | `https://onelake.dfs.fabric.microsoft.com/{ws}/{lh}/Files/...` (SDK ADLS Gen2) | User/SP | GA | data.py |
| Job Scheduler | Run On Demand (RunNotebook) | `POST /workspaces/{ws}/items/{nb}/jobs/instances?jobType=RunNotebook` | User/SP | GA | fabric.py |
| Etiquetas (admin) | Bulk Set / Bulk Remove Labels | `POST /admin/items/bulkSetLabels` · `POST /admin/items/bulkRemoveLabels` | **Solo usuario**, Fabric admin, 25 req/h | GA | fabric.py |
| OneLake security | Create Or Update / List Data Access Roles | `PUT/GET /workspaces/{ws}/items/{lh}/dataAccessRoles` | User/SP | GA | security.py |
| Fabric Policies | Create Policy Set | `POST /workspaces/{ws}/policySets` (definición `policySet.json`, formato `Beta`) | User/SP | **Preview** | policies.py |
| Fabric Policies | Activate / Deactivate | `POST /workspaces/{ws}/policySets/{id}/activate?allowReplace=true` · `/deactivate` | Capacity admin | **Preview** | policies.py |
| Fabric Policies | Get Active For Capacity | `GET /capacities/{id}/policySets/active` | User/SP | **Preview** | policies.py |
| Tenant settings (admin) | List Tenant Settings | `GET /admin/tenantsettings` | Fabric admin | GA | commands.py |
| Auditoría | Get Activity Events | `GET https://api.powerbi.com/v1.0/myorg/admin/activityevents` (token Power BI) | Fabric admin | GA | commands.py |
| MCP | Servidor remoto Fabric Core | `https://api.fabric.microsoft.com/v1/mcp/core` | User | — | .vscode/mcp.json |

## Notas sobre las APIs en preview

- **Policy sets**: la documentación todavía muestra dos formas para el efecto de una regla (`"effects": [{"type": "Allow"}]` en el esquema de la definición y `"then": [{"effect": "Allow"}]` en un ejemplo de la API de creación). El repo usa la del **esquema oficial** (`policySet/definition/1.0.0`). Si la API rechaza la definición, prueba la otra forma en `policies/*.json`.
- Los identificadores de `item.type` son los de la API (`Notebook`, `DataPipeline`, `Lakehouse`, `Warehouse`, `SemanticModel`, `Report`…), no los nombres de la interfaz.
- `workspace.id` acepta solo IDs; `workspace.name` se rechaza con `UnsupportedPropertyValue`. Por eso las definiciones usan placeholders `{{ws.*}}` que `fabdemo` sustituye al desplegar.
- **Load Table** no admite lakehouses con esquemas: `lh_finanzas` se crea sin ellos.

## Referencias

- Fabric REST API: https://learn.microsoft.com/rest/api/fabric/
- Fabric policies: https://learn.microsoft.com/fabric/governance/fabric-policies-overview
- Policy set definition: https://learn.microsoft.com/rest/api/fabric/articles/item-management/definitions/policyset-definition
- Item creation policy: https://learn.microsoft.com/fabric/governance/fabric-policies-item-creation
- Protection policies: https://learn.microsoft.com/fabric/governance/protection-policies-overview
