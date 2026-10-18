# 3 · Pasos sin API pública

No todo el gobierno de Fabric se puede automatizar todavía. Estos pasos se hacen en el portal y conviene contarlo en la sesión: también es un dato.

## Demo 2 · Protection policy

Purview portal › **Information Protection › Protection policies** › *Create policy*:

1. **Label**: `Confidencial-Finanzas` (debe tener control de acceso y ámbito *Files & other data assets*).
2. **Data sources**: Microsoft Fabric.
3. **Allow access**: grupo `Finanzas-Analistas` (y, si quieres que el probe del engineer salga ✓, también `Ingenieros-Prod`).
4. Crear y esperar: **hasta 24 h** en aplicarse.

Límites: 50 policies por tenant, 100 usuarios/grupos por policy, sin invitados, sin integración con CI/CD.

## Demo 2 (opcional) · DLP

Purview › **Data Loss Prevention › Policies** › ubicación *Fabric and Power BI workspaces*, con la acción *Restrict access* sobre modelos semánticos (preview). Útil para enseñar el indicador de cobertura de DLP en Govern.

## Demo 1 · Endorsement

No hay API para promocionar o certificar. En el ítem › *Settings › Endorsement* › **Certified**. Requiere el tenant setting *Certification* y que el presentador esté en el grupo de certificadores (o sea admin del dominio con certificación delegada).

## Demo 1 · Etiqueta por defecto del dominio

Admin portal › **Domains** › `MIDP Finanzas` › *Default sensitivity label*. Requiere el tenant setting *Domain admins can set default sensitivity labels for their domains*.

## OneLake security en el lakehouse

Si `fabdemo security apply` falla: abre `lh_finanzas` › **Manage OneLake security** y habilítala. Después repite el comando.

## Admin monitoring

Admin portal › *Admin monitoring* (o el workspace homónimo): ábrelo una vez para que se cree. Govern usa sus datos y se refresca a diario.

## Fabric CLI para explorar en vivo (opcional)

```powershell
pip install ms-fabric-cli
fab auth login
fab ls                                     # workspaces
fab ls "MIDP-Fin-Prod-Analytics.Workspace" # ítems

# Etiquetas: requiere un JSON local con id → nombre
fab config set local_definition_labels .\labels.json
fab label list-local
fab label set "MIDP-Fin-Prod-Analytics.Workspace/lh_finanzas.Lakehouse" -n "Confidencial-Finanzas" -f
```
