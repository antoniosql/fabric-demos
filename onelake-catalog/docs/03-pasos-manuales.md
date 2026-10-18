# 3 · Pasos manuales en Purview y Fabric

La demo 2 combina tres cosas distintas: una etiqueta de sensibilidad creada en Purview, una política que publica esa etiqueta a usuarios y una *protection policy* de Fabric que usa la etiqueta para controlar el acceso al ítem. Crear la etiqueta por sí solo no restringe el acceso.

## Demo 2 · Preparación completa de etiquetas y protección

Haz estos pasos al menos **24 horas antes** del ensayo. La propagación de etiquetas, membresías de grupos y protection policies puede tardar; la protección puede tardar hasta 24 horas en detectar los ítems etiquetados.

### 1. Requisitos y permisos

Antes de abrir Purview, confirma lo siguiente:

- El tenant tiene licencias Microsoft 365 que habilitan Microsoft Purview Information Protection (por ejemplo, E3/E5) para los usuarios que administran y usan etiquetas.
- La persona que crea y administra etiquetas tiene un rol de Purview adecuado, como **Information Protection Admin**. Para crear la protection policy también se requiere **Information Protection Admin** o superior.
- Los grupos de Entra existen y tienen las personas de demo correspondientes:
  - `Finanzas-Analistas`: grupo permitido para conservar acceso al ítem protegido.
  - `Ingenieros-Prod`: grupo permitido opcional, necesario si quieres que el probe de Ingeniería siga dando acceso después de etiquetar.
  - `Analistas-Norte`: se usa para OneLake security; también añade este grupo a la publicación de etiquetas si quieres que el analista pueda aplicarlas desde el portal.
- Los usuarios de demo son usuarios internos del tenant, no invitados externos. Las protection policies de Fabric no admiten invitados.
- En el portal de administración de Fabric, habilita **Allow users to apply sensitivity labels for content**. Es necesario para que Fabric aplique las etiquetas y para hacer cumplir las protection policies.
- Si Purview pide facturación para usar protection policies con Fabric, configura el modelo *pay-as-you-go* de Purview con una suscripción de Azure. La necesidad puede depender de las características habilitadas en el tenant.

Para esta demo se necesitan dos etiquetas:

| Etiqueta | Ámbito | Protección de la etiqueta | Uso |
|---|---|---|---|
| `General` | **Files & other data assets** | Ninguna; sin cifrado ni control de acceso | Etiquetado normal en la demo 1 |
| `Confidencial-Finanzas` | **Files & other data assets** | **Control access** (cifrado) | Activa la protection policy de la demo 2 |

> No actives cifrado en `General`. La etiqueta `Confidencial-Finanzas` debe incluir el ámbito **Files & other data assets** y el ajuste **Control access**; si falta cualquiera de ellos, no aparecerá como opción válida al crear la protection policy.

### 2. Crear la etiqueta `General`

1. Abre el [portal de Microsoft Purview](https://purview.microsoft.com/) con la cuenta que tenga permisos de Information Protection.
2. Ve a **Solutions → Information Protection → Sensitivity labels**.
3. Pulsa **Create** (o **Create a label**, según la experiencia del tenant) y crea una etiqueta independiente:
   - **Name / Display name**: `General`
   - **Description for users**: `Información general de la demo Finanzas.`
   - **Tooltip**: `Datos que no requieren protección adicional.`
4. En **Define the scope for this label**, selecciona **Files & other data assets**. No hace falta habilitar los ámbitos de emails o reuniones para esta demo.
5. En la configuración de protección, deja desactivadas las opciones de cifrado, marca de agua o control de acceso. Esta etiqueta solo clasifica el contenido.
6. Termina el asistente y guarda la etiqueta.

### 3. Crear la etiqueta `Confidencial-Finanzas`

1. Antes de crearla, busca `Confidencial-Finanzas` en **Sensitivity labels**. Si ya existe, **no la vuelvas a crear**: edítala y comprueba que tenga el ámbito **Files & other data assets** y **Control access** activado; después continúa en el paso 4 para publicarla.
2. Si no existe, en **Sensitivity labels** selecciona **Create → Label** y crea una etiqueta independiente:
   - **Name / Display name**: `Confidencial-Finanzas`
   - **Description for users**: `Información financiera confidencial de la demo.`
   - **Tooltip**: `El acceso está limitado a los grupos autorizados por la política de protección.`
3. Selecciona el ámbito **Files & other data assets**.
4. En la configuración de protección, elige **Control access** (puede mostrarse dentro de **Protect items** o **Encryption**, según la experiencia del portal). Configura el control para que se aplique al contenido; la lista final de quién conserva acceso se define en la protection policy de Fabric, en el siguiente paso.
5. Si el asistente muestra opciones para asignar permisos de cifrado, asegúrate de que no excluyan a los grupos que permitirás en la protection policy (`Finanzas-Analistas` y, opcionalmente, `Ingenieros-Prod`). La protección de la etiqueta y la protection policy son controles relacionados pero distintos; verifica el resultado con los probes antes de la demo.
6. No añadas encabezados, pies de página ni marcas de agua; no son necesarios para esta demostración.
7. Revisa y crea la etiqueta.

**Si al guardar aparece `A compliance rule with name 'Confidencial-Finanzas' already exists in scenario(s) 'MipProtection'`:** cierra el error y vuelve a la lista de etiquetas. Actualiza la página y busca la etiqueta; puede haberse creado en un intento anterior. Si aparece, reutilízala y continúa, no repitas la creación. Si no aparece, comprueba desde Security & Compliance PowerShell:

```powershell
Connect-IPPSSession
Get-Label | Select-Object DisplayName, Name, ImmutableId
```

Si `Get-Label` devuelve la etiqueta, reutiliza su `ImmutableId` aunque no aparezca inmediatamente en el portal. Si no la devuelve, no borres reglas o etiquetas de Purview al azar: verifica que estás en el tenant correcto, espera unos minutos y vuelve a consultar. Si el conflicto persiste, prueba un nombre único para la etiqueta (por ejemplo, `Confidencial-Finanzas-Demo`) y usa ese mismo nombre en la protection policy; si también falla, hace falta que un administrador de Purview investigue la regla residual antes de seguir.

### 4. Publicar las etiquetas a las identidades de la demo

Las etiquetas no estarán disponibles para usuarios ni servicios hasta que se publiquen mediante una *label policy*.

1. En **Information Protection**, abre **Publishing policies** (también puede llamarse **Label policies**) y selecciona **Publish labels**.
2. Crea una política, por ejemplo `Demo OneLake Catalog - publicar etiquetas`.
3. Selecciona **General** y **Confidencial-Finanzas**.
4. En **Assign admin units**, deja **Full directory** salvo que el tenant use unidades administrativas que debas delimitar.
5. En **Choose users and groups**, incluye las identidades que participarán en la demo: como mínimo el presentador y el grupo `Finanzas-Analistas`; añade `Ingenieros-Prod` y `Analistas-Norte` si esos usuarios deben poder aplicar etiquetas desde el portal. Añade la cuenta del externo solo si necesitas que esa cuenta vea las etiquetas en sus aplicaciones; publicarlas no le dará permiso sobre el ítem protegido.
6. En los ajustes de política, conserva los valores predeterminados: no fuerces una etiqueta predeterminada ni la justificación de cambio para esta demo.
7. Revisa y envía la política. Al completar el asistente, la política queda publicada automáticamente.

La CLI aplica la etiqueta confidencial por API como el presentador; la publicación permite también aplicar etiquetas manualmente desde el portal. Espera hasta 24 horas a que se propaguen los cambios, especialmente si acabas de crear grupos o cambiar sus miembros.

### 5. Obtener los IDs de las etiquetas para `config.toml`

Abre Security & Compliance PowerShell e inicia sesión:

```powershell
Connect-IPPSSession
Get-Label | Select-Object DisplayName, ImmutableId
```

Copia el `ImmutableId` de cada etiqueta en `config/config.toml`:

```toml
[labels]
general = "<ImmutableId de General>"
confidencial_finanzas = "<ImmutableId de Confidencial-Finanzas>"
```

No pongas el nombre visible en esos campos. Comprueba también que las etiquetas no tengan un ID vacío o el GUID de ejemplo `00000000-0000-0000-0000-000000000000`.

### 6. Crear la protection policy de Fabric

La protection policy es distinta de la *label policy*: asocia la etiqueta confidencial con una lista de grupos autorizados y bloquea a los demás usuarios que tenían acceso al ítem.

1. Abre [Protection policies en Purview](https://purview.microsoft.com/informationprotection/protectionpolicy) y selecciona **New protection policy**.
2. Nombre: `Demo OneLake Catalog - Finanzas confidencial`. Añade una descripción que indique que limita el acceso a los ítems Fabric etiquetados `Confidencial-Finanzas`.
3. En **Choose the sensitivity label used to detect sensitive items**, selecciona **Confidencial-Finanzas**. Si no aparece, revisa que la etiqueta esté publicada, tenga el ámbito **Files & other data assets** y esté configurada con **Control access**.
4. En **Choose data sources**, selecciona **Microsoft Fabric**. No selecciones otras fuentes.
5. En **Define access control settings**, añade:
   - **Finanzas-Analistas**: necesario para permitir al grupo analista.
   - **Ingenieros-Prod**: opcional; añádelo para que el probe de Ingeniería también conserve el acceso.
   - No añadas `Analistas-Norte` por separado si sus miembros ya pertenecen a `Finanzas-Analistas`.
   - No añadas el usuario/grupo `outsider`; esa identidad debe quedar fuera para que se vea el bloqueo.
6. Si aparece **Allow users to retain full control**, actívalo para que los usuarios/grupos autorizados que ya tenían control total conserven ese permiso. La policy no concede acceso a personas que no se agreguen a la lista autorizada.
7. Elige activar la política inmediatamente, revisa la configuración y selecciona **Submit**.
8. Espera hasta 24 horas antes de considerar que la policy no está funcionando. Se aplica a ítems Fabric compatibles en todos los workspaces, no solo al workspace de la demo.

Límites y comportamiento: hasta 50 protection policies por tenant; hasta 100 usuarios y grupos por policy; no se admiten invitados; no se integra con CI/CD. La política bloquea usuarios fuera de la lista para los ítems que tengan la etiqueta asociada. El usuario que aplica la etiqueta no queda bloqueado por esa misma policy. Verifica, por tanto, que `demo2 label` se ejecuta con el presentador y que `outsider` no es el emisor de la etiqueta.

### 7. Ensayar y comprobar el resultado

Primero confirma que el usuario externo tiene acceso antes de etiquetar; esto verifica que el bloqueo posterior no se debe a que le falte un rol de workspace:

```powershell
fabdemo demo2 probe --persona outsider
```

La salida esperada antes de etiquetar indica acceso correcto a metadatos y datos. Aplica la etiqueta como presentador y repite las pruebas:

```powershell
fabdemo -v demo2 label
fabdemo demo2 probe --persona outsider
fabdemo demo2 probe --persona engineer
```

Resultado esperado: `outsider` pierde el acceso; `engineer` lo conserva si `Ingenieros-Prod` está en la lista permitida de la policy y pertenece a ese grupo. En OneLake Catalog puedes abrir los detalles de `lh_finanzas` y su pestaña **Permissions** para mostrar quién conserva acceso y quién queda restringido.

Para volver al estado inicial y repetir:

```powershell
fabdemo demo2 unlabel
```

La retirada de la etiqueta no borra la protection policy. Déjala desactivada o elimínala manualmente cuando termines la demo, si ya no la necesitas.

Referencias oficiales: [crear y publicar etiquetas de confidencialidad](https://learn.microsoft.com/purview/create-sensitivity-labels), [introducción a las etiquetas de confidencialidad](https://learn.microsoft.com/purview/get-started-with-sensitivity-labels), [protección de acceso en Fabric](https://learn.microsoft.com/fabric/governance/protection-policies-overview) y [crear y administrar protection policies](https://learn.microsoft.com/fabric/governance/protection-policies-create).

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
