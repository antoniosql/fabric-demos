# 2 · Guion de las demos

## Cronología de preparación

| Cuándo | Qué | Comando |
|---|---|---|
| T-3 días | Requisitos y `check` en verde | `fabdemo check` |
| T-2 días | Despliegue completo | `fabdemo deploy` |
| T-2 días | Protection policy en Purview (tarda hasta 24 h) | manual, [docs/03](03-pasos-manuales.md) |
| T-1 día | Ítems sin gobernar (Govern de admin se refresca a diario) | `fabdemo demo1 drift` |
| T-1 día | Etiqueta confidencial y comprobación | `fabdemo demo2 label` · `fabdemo demo2 probe` |
| T-1 día | Ensayo de las demos 3-4 completo y vuelta atrás | `demo3 apply v2` · `demo3 probe` · `demo3 off` |
| T-30 min | Actividad reciente y volumen | `fabdemo data stream --every 60 --batches 30` (en otra terminal) |
| T-15 min | Pestañas abiertas: OneLake Catalog (Explore, Govern, Secure), Policies center, Purview Audit | — |

> Consejo: ejecuta los comandos con `-v` durante la sesión: se ve cada llamada a la API y refuerza el mensaje «todo esto es código».

---

## Demo 1 · Del rojo al verde en Govern

**Qué se ve:** un dominio con ítems sin descripción, sin etiqueta y sin certificar, que se gobierna siguiendo las recommended actions.

Preparado la víspera:

```powershell
fabdemo demo1 drift      # 4 ítems «sin gobernar» por workspace del dominio
fabdemo demo1 status
```

En directo:

1. OneLake Catalog › **Govern** como propietario (*My items*) y como admin, filtrando por el dominio **MIDP Finanzas**.
2. Mostrar la cobertura de etiquetas y descripciones y seguir una *recommended action* hasta el **Item explorer**.
3. Gobernar a mano `lh_finanzas` desde el portal: descripción, etiqueta **General** y **certificación** (el endorsement no tiene API).
4. Lo demás, con código:
   ```powershell
   fabdemo -v demo1 fix --all
   ```
5. Refrescar la vista del propietario. (La de admin se actualizará al día siguiente: cuéntalo.)

Volver atrás: `fabdemo demo1 reset`

---

## Demo 2 · Un lakehouse que desaparece

**Qué se ve:** la etiqueta *Confidencial-Finanzas* activa una protection policy y un usuario con rol de workspace pierde el acceso.

Preparado: protection policy creada ≥ 24 h antes ([docs/03](03-pasos-manuales.md)) y la etiqueta aplicada la víspera.

```powershell
fabdemo demo2 probe --persona outsider     # antes de etiquetar: ✓ metadatos y ✓ datos
fabdemo -v demo2 label                     # bulkSetLabels sobre lh_finanzas
fabdemo demo2 probe --persona outsider     # con la policy aplicada: ✗
fabdemo demo2 probe --persona engineer     # si el engineer está en el grupo permitido: ✓
fabdemo audit --hours 24 --contains Label  # rastro en el registro de actividad
```

En el portal: entra con el usuario externo en una ventana InPrivate y abre `lh_finanzas`.

Volver atrás: `fabdemo demo2 unlabel`

---

## Demo 3 · Solo ingeniería crea en Prod (y la trampa de la allow list)

**Qué se ve:** con solo la regla R1, nadie puede crear nada fuera de esa combinación en toda la capacidad. La regla R2 lo arregla.

```powershell
fabdemo demo3 probe --persona outsider     # línea base: todo ✓

fabdemo -v demo3 apply v1                  # R1 sola (pide confirmación)
# … esperar hasta 15 min (explica el modelo mientras tanto) …
fabdemo demo3 probe --persona outsider     # ✗ en todas partes, también en Dev  ← la trampa
fabdemo demo3 probe --persona engineer     # ✓ Notebook/DataPipeline solo en Prod

fabdemo -v demo3 apply v2                  # R1 + R2 (NoneOf Prod)
fabdemo demo3 probe --persona outsider     # ✗ en Prod, ✓ en Dev
fabdemo audit --hours 1 --contains Policy
```

En el portal: **Govern › Policies center** muestra el policy set activo y su acción (*Advanced*).

Volver atrás: `fabdemo demo3 off`

> Mientras una directiva esté activa, `deploy` y `demo1 drift` también pueden quedar bloqueados. Desactívala antes de redesplegar.

---

## Demo 4 · Directivas como código

**Qué se ve:** la directiva vive en el repositorio, se revisa con un diff, se despliega por API y se activa explícitamente.

```powershell
code policies/item-creation.v2-corregida.json    # p. ej. añade "Lakehouse" a item.type
fabdemo demo4 diff                               # repositorio vs. desplegado
fabdemo -v demo4 deploy item-creation.v2-corregida.json
fabdemo demo4 activate                           # la activación NO viaja por Git
fabdemo demo4 export                             # lo desplegado → out/policySet.exported.json
git add policies ; git commit -m "Permitir Lakehouse en Prod a Ingenieros-Prod"
```

Punto extra: conectar `MIDP-Gobierno-Admin` a Git desde el portal y enseñar que el policy set aparece versionado, pero activarlo sigue siendo una acción aparte.

---

## Demo 5 · El catálogo también es para agentes

```powershell
fabdemo demo5
code .
```

En VS Code: *MCP: List Servers* › **fabric** › Start (inicia sesión con Entra). En Copilot Chat (modo Agent):

- «¿Existe ya un lakehouse de clientes certificado en el dominio Finanzas?»
- «Lista los ítems del workspace MIDP-Fin-Prod-Analytics que no tienen descripción.»

Mensaje: si los metadatos están vacíos (demo 1 sin hacer), el agente tampoco encuentra nada y acaba creando duplicados.

---

## Extra · OneLake security (bloque Secure)

```powershell
fabdemo security show
fabdemo -v security apply     # rol AnalistasNorte: RLS region='Norte' y CLS sin iban/email en clientes
```

En el portal: OneLake Catalog › **Secure › View security roles** y *View users in role*.

## Limpieza

```powershell
fabdemo demo3 off
fabdemo teardown --yes
```

La protection policy y las etiquetas de Purview no se borran: elimínalas a mano si ya no las necesitas.
