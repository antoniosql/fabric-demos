# Ensayo en el portal · paso a paso

Complementa a [2026-11-26-ensayo.md](2026-11-26-ensayo.md), que cubre lo que se ensayó desde la línea de comandos.
Aquí están las acciones del portal (actos 1 a 4 y reset), cada una con lo que debe salir y qué hacer si no sale.

- **Cifras esperadas:** son las del lakehouse a 26-11-2026, calculadas leyendo las tablas Delta. No son las de
  las diapositivas (ver el ensayo de la línea de comandos).
- **Nombres de los menús:** los nombres entre comillas (`New semantic view`, `Publish`…) salen del README y de
  Learn (preview, 2026-11). Si alguno ha cambiado en el portal, anótalo en la casilla del paso.
- **Plan B:** cada 📸 es una captura para `capturas/`. Nómbralas con el número del paso, por ejemplo
  `1.3-publish-ok.png`. Graba la pantalla de todo el recorrido en un solo vídeo.

Workspace: https://app.fabric.microsoft.com/groups/0f1bd308-e416-483b-b590-43cff70f8106

---

## 0 · Antes de empezar (10 min)

- [ ] **0.1** Capacidad `f4mvp` activa (`python scripts/fabdemo.py check`).
- [ ] **0.2** Navegador:
  - Sesión iniciada con la cuenta de la demo.
  - Zoom al 125-150 % para que se lea en el proyector.
  - Marcadores, notificaciones y otras pestañas cerrados.
- [ ] **0.3** Ten abiertos en el editor `schema.yaml`, `metrics-ventas.yaml` y `metrics-portabilidad.yaml`.
  Los subes desde `c:\repos\fabric-demos\fabric-semantic-views\`.
- [ ] **0.4** Abre el workspace y comprueba que contiene exactamente el lakehouse `lh_frasohome`, su SQL
  analytics endpoint y los 3 notebooks. No debe haber ningún modelo semántico `frasohome_ventas` ni ningún
  Data Agent. Si quedan de otro ensayo, sigue primero el apartado «Reset».
- [ ] **0.5** Abre el notebook `01_prep_vista_semantica`. La última ejecución es la de hoy (lanzada por API).
  En la celda de cifras debe salir:

  | ventas_brutas | devoluciones | ventas_netas | suma_con_signo |
  |---:|---:|---:|---:|
  | 1602458.02 | 127963.92 | 1474494.1 | 1474494.1 |

  También debe salir `Movimientos: 4931 · fuera del calendario o sin fecha: 40`, y la consulta de `store_id`
  duplicados vacía.
  📸 `0.5-notebook01-cifras.png`. Esta es la pestaña que enseñarás en el paso 1.6.

---

## Acto 1 · De tabla gold a vista publicada (objetivo: 8 min)

### 1.1 Crear la vista
- [ ] En el workspace, abre el lakehouse `lh_frasohome`.
- [ ] En la cinta, pulsa **New semantic view** y ponle de nombre `frasohome_ventas`. Escríbelo exactamente
  así: es el `name` de los dos YAML.
- **Debe salir:** una carpeta `frasohome_ventas` bajo `Context/Semantic Views/`, con un YAML de inicio.
- **Si no aparece el botón:** el tenant o el workspace no tiene la preview activa, o el workspace está
  conectado a Git o a un pipeline de despliegue. Revisa la configuración del workspace.
- 📸 `1.1-new-semantic-view.png`

### 1.2 Enseñar y borrar el YAML de inicio
- [ ] Abre el YAML de inicio y apunta qué trae, para comentarlo en la sesión.
- [ ] Bórralo.
- 📸 `1.2-yaml-inicio.png` (antes de borrarlo)

### 1.3 Subir los dos YAML
- [ ] Clic derecho en la carpeta `frasohome_ventas` → **Upload** → `schema.yaml`.
- [ ] Repite la subida con `metrics-ventas.yaml`. Sube los dos ficheros, **no** `metrics-portabilidad.yaml`:
  ese es para el acto 3.
- **Debe salir:** los dos ficheros en la carpeta. Ábrelos y comprueba que la versión es `0.2.0.dev0`.
- 📸 `1.3-yaml-subidos.png`

### 1.4 Publicar
- [ ] Clic derecho en la carpeta → **Publish**. **Cronometra** esta primera publicación: _____ min.
- **Debe salir:** publicación correcta sin errores. Puede haber avisos, que debes **apuntar**: ninguno
  debería aparecer hasta el acto 3.
- **Si falla:**

  | Mensaje | Causa probable | Arreglo |
  |---|---|---|
  | Tabla o `source` no encontrado | El lakehouse no tiene esquemas | Comprueba que existe `dbo.gold_fact_movimientos` en el explorador del lakehouse |
  | Relación muchos a uno no válida | Claves repetidas en la dimensión | Hoy no las hay: las claves de tiendas, productos, CRM y scoring son únicas. Si aparece, apunta qué relación falla |
  | Error de DAX en una métrica | Nombre de tabla o columna mal escrito | Las métricas usan `'movimientos'`, `'fecha'` y `'cliente_score'`, que son los `name` de los datasets |
  | Conflicto de nombres | Una métrica se llama igual que una tabla o columna | No debería ocurrir con `metrics-ventas.yaml` |

- 📸 `1.4-publish-ok.png` con el mensaje de resultado y los avisos.

### 1.5 Enseñar el TMDL generado
- [ ] En el explorador del lakehouse, ve a `SystemContext/Semantic Views/frasohome_ventas/`.
- [ ] Abre el TMDL. Localiza la medida `Ventas netas` (`[Ventas brutas] - [Importe devoluciones]`) y la tabla
  `movimientos`.
- [ ] En el workspace, comprueba que ha aparecido el **modelo semántico** `frasohome_ventas` (Direct Lake, de
  solo lectura).
- 📸 `1.5-tmdl.png` y `1.5-modelo-en-workspace.png`

### 1.6 Validar en DQV
- [ ] Abre el modelo `frasohome_ventas` → **DAX query view** (DQV).
- [ ] Ejecuta la consulta del guion:
  ```dax
  EVALUATE ROW("Brutas", [Ventas brutas], "Devoluciones", [Importe devoluciones], "Netas", [Ventas netas])
  ```
  **Debe salir:** Brutas **1.602.458,02** · Devoluciones **127.963,92** · Netas **1.474.494,10**.
  Enséñalo junto a la pestaña del notebook 01 (paso 0.5).
- [ ] Solo en el ensayo, ejecuta también esta consulta, que prueba el resto de métricas:
  ```dax
  EVALUATE ROW(
    "Tasa devolucion", [Tasa devolucion], "Margen bruto", [Margen bruto], "Margen pct", [Margen pct],
    "Pedidos", [Pedidos], "Ticket medio", [Ticket medio], "Clientes en riesgo", [Clientes en riesgo])
  ```

  | Métrica | Esperado | Nota |
  |---|---:|---|
  | Tasa devolucion | 0,0799 (7,99 %) | |
  | Margen bruto | 564.797,06 | 553 líneas de venta no tienen margen (no hay coste), así que sale por debajo |
  | Margen pct | 0,3525 | |
  | Pedidos | 1.852 | Puede salir 1.853: `DISTINCTCOUNT` cuenta el `doc_id` en blanco como un valor más |
  | Ticket medio | 865,26 | O 864,79 si Pedidos sale 1.853 |
  | Clientes en riesgo | 116 | |

- [ ] **Prueba de la inteligencia de tiempo** (pendiente del README: `SAMEPERIODLASTYEAR` sin marcar la tabla
  de fechas):
  ```dax
  EVALUATE
  SUMMARIZECOLUMNS('fecha'[anio],
    "Netas", [Ventas netas], "Netas año ant.", [Ventas netas año anterior], "Crec.", [Crecimiento interanual])
  ```

  | anio | Netas | Netas año ant. | Crec. |
  |---|---:|---:|---:|
  | 2024 | 334.284,69 | (en blanco) | (en blanco) |
  | 2025 | 1.133.102,42 | 334.284,69 | 2,3897 (+239 %) |
  | 2026 | −3.458,31 | 1.133.102,42 | −1,0031 |

  Si «Netas año ant.» sale en blanco en 2025, `SAMEPERIODLASTYEAR` no funciona sin marcar la tabla de fechas.
  **En ese caso, no hagas en directo la segunda pregunta del acto 2.**
  Además, la suma de los tres años (1.463.928,80) no coincide con el total (1.474.494,10): los
  10.565,30 € que faltan son los 40 movimientos con fecha fuera del calendario o sin fecha. Si haces la
  consulta en la sesión, decide si lo cuentas como ejemplo de calidad de datos (README, «Cosas que comprobar»).
- [ ] Consulta por canal, que servirá para validar la respuesta del agente:
  ```dax
  EVALUATE
  SUMMARIZECOLUMNS('fecha'[anio], 'movimientos'[canal_movimiento], "Netas", [Ventas netas])
  ```

  | anio | ONLINE | POS |
  |---|---:|---:|
  | 2024 | 341.572,48 | −7.287,79 |
  | 2025 | 288.162,16 | 844.940,26 |
  | 2026 | −1.225,49 | −2.232,82 |

- 📸 `1.6-dqv-row.png`, `1.6-dqv-tiempo.png` y `1.6-dqv-canal.png`
- ⏱ Tiempo del acto 1: _____ min (objetivo: 8)

---

## Acto 2 · El agente responde con la definición (objetivo: 4 min)

### 2.1 Crear el Data Agent
- [ ] En el workspace: **New item** → **Data agent**. Nombre: `da_frasohome_ventas`.
- [ ] **Add data source** → elige el modelo semántico `frasohome_ventas` (no el lakehouse).
- [ ] Opcional: en las instrucciones del agente, escribe «Responde en español con importes en euros». Prueba
  primero sin instrucciones: el mensaje de la sesión es que la definición viene de la vista.
- **Si falla:** la capacidad no es F de pago o el tenant no tiene activados Copilot o el Data Agent.
- 📸 `2.1-agente-fuente.png`

### 2.2 Primera pregunta
- [ ] Pregunta: «¿Cuáles fueron las ventas netas por canal en 2025?»
- **Debe salir:** ONLINE **288.162,16** y POS **844.940,26** (total 1.133.102,42).
- [ ] Despliega los pasos del agente y enseña la **DAX generada**. Debe usar la medida `[Ventas netas]`, no
  sumar `importe_signed`.
- **Si da otra cifra:** mira si ha filtrado por año con `'fecha'[anio]`, que es lo correcto, o con otra
  columna. Repite la pregunta con «usa la medida Ventas netas».
- 📸 `2.2-respuesta.png` y `2.2-dax.png`

### 2.3 Segunda pregunta
- [ ] Pregunta: «¿Cuánto crecieron las ventas netas en 2025 frente a 2024?»
- **Debe salir:** alrededor de **+239 %** (de 334.284,69 a 1.133.102,42). Prepara la explicación: en 2024 casi
  no hay datos de POS (3 pedidos), así que el crecimiento es de cobertura de datos, no de negocio.
- **Si el paso 1.6 mostró que `SAMEPERIODLASTYEAR` no funciona:** cambia en directo a «¿Cuáles fueron las
  ventas netas de 2024 y de 2025?».
- 📸 `2.3-respuesta.png` y `2.3-dax.png`
- ⏱ Tiempo del acto 2: _____ min (objetivo: 4)

---

## Acto 3 · ¿Cuánto Ossie entiende Fabric? (objetivo: 6 min)

### 3.1 Subir y publicar
- [ ] Clic derecho en la carpeta `frasohome_ventas` → **Upload** → `metrics-portabilidad.yaml`.
- [ ] **Publish**.
- **Deben salir tres avisos** (según Learn, 2026-11). Apunta el texto literal de cada uno:
  - [ ] Dialecto `ANSI_SQL` ignorado en «Ventas brutas dos dialectos»: se publica la versión DAX. Texto: ______
  - [ ] «Ventas brutas solo SQL» omitida por no tener dialecto DAX. Texto: ______
  - [ ] `ai_context` descartado. Texto: ______
- [ ] Comprueba en el modelo (DQV o TMDL) que existe `Ventas brutas dos dialectos` y que **no** existe
  `Ventas brutas solo SQL`:
  ```dax
  EVALUATE ROW("Dos dialectos", [Ventas brutas dos dialectos])
  ```
  **Debe salir:** 1.602.458,02, igual que Ventas brutas.
- **Si los avisos no coinciden** (por ejemplo, el publish falla en lugar de avisar): apúntalo y ajusta la
  narrativa del acto 3. Es justo lo que el acto quiere enseñar.
- 📸 `3.1-avisos.png` y `3.1-medidas.png`

### 3.2 Opcional: conflicto de nombres
- [ ] Crea un YAML temporal **solo para el ensayo** con una métrica llamada `movimientos`. Súbelo, publica y
  comprueba que el publish falla.
- [ ] Bórralo y vuelve a publicar para dejar la vista correcta.
- 📸 `3.2-error-nombre.png`. Si la sesión va justa de tiempo, enseña esta captura en lugar de hacerlo en directo.
- ⏱ Tiempo del acto 3: _____ min (objetivo: 6)

---

## Acto 4 · Shortcut (solo enseñar, no ejecutar)
- [ ] Prepara una captura de cómo se crearía un shortcut desde otro lakehouse a
  `Context/Semantic Views/frasohome_ventas`: **New shortcut** → OneLake → este lakehouse → esa carpeta.
  No lo crees.
- 📸 `4-shortcut.png`

---

## Reset (cuando acabes el ensayo, para dejarlo listo para esta tarde)

Sigue este orden. Borrar la carpeta **no** borra el modelo.

- [ ] **R.1** En el lakehouse, borra la carpeta `Context/Semantic Views/frasohome_ventas`. Solo esa carpeta,
  no la carpeta padre `Semantic Views`.
- [ ] **R.2** En el workspace, borra el modelo semántico `frasohome_ventas`.
- [ ] **R.3** Borra el Data Agent `da_frasohome_ventas`.
- [ ] **R.4** `SystemContext/Semantic Views/frasohome_ventas` se queda: solo se limpia al publicar otra vista,
  y no impide repetir la demo.
- [ ] **R.5** **No** ejecutes `fabdemo.py run 99`: borra `gold_fact_movimientos` y `gold_dim_fecha`, y
  tendrías que volver a ejecutar el notebook 01 antes de la sesión. Si lo ejecutas, después lanza
  `python scripts/fabdemo.py run 01`, que tarda unos 2 min.
- [ ] **R.6** `python scripts/fabdemo.py status` debe mostrar otra vez solo el lakehouse, el SQL endpoint y
  los 3 notebooks.

---

## Para rellenar al terminar

| | |
|---|---|
| Primera publicación (1.4) | ___ min |
| Tiempo de los actos 1 / 2 / 3 | ___ / ___ / ___ min (objetivo 8 / 4 / 6) |
| ¿Funciona `SAMEPERIODLASTYEAR`? | sí / no |
| ¿El agente usó `[Ventas netas]`? | sí / no |
| Avisos del acto 3 como se esperaba | sí / no (diferencias: ___) |
| CU consumidas (Capacity Metrics app) | ___ |
| Capturas y vídeo en `capturas/` | sí / no |
