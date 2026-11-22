# Fabric Semantic Views — «ventas netas» se define una vez, con Apache Ossie

Demo de la sesión de MIDP **«Vistas semánticas en Fabric: “ventas netas” se define una vez, junto al dato,
con Apache Ossie»**. Define las métricas oficiales de FraSoHome como una vista semántica en YAML (formato
Apache Ossie) dentro del lakehouse, la publica como modelo Direct Lake de solo lectura y la consulta con un
Data Agent. El tercer acto enseña qué parte de Ossie entiende Fabric hoy.

> ⚠️ **Preview.** Las vistas semánticas están en preview pública desde el 17-11-2026. No se publican en
> workspaces conectados a Git o a pipelines de despliegue: usa un workspace de demo aparte.

## Mensaje que demuestra

«Ventas netas» se define una vez, en YAML de Apache Ossie, junto al dato en OneLake; Fabric lo compila a
un modelo de solo lectura que usan los informes y el Data Agent. Y Fabric solo entiende una parte de
Ossie: las métricas en DAX.

## Prerrequisitos y versión probada

- Workspace con capacidad **F de pago (F2 o superior)**: el Data Agent no funciona en trial.
- El workspace **no** puede estar conectado a Git, a pipelines de despliegue ni a soluciones de Power
  Platform, ni tener private links a nivel de workspace (restricción de la preview). Por eso la demo crea
  un workspace propio.
- Para el despliegue automático: Python 3.11+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
  y un usuario que pueda crear workspaces y asignarlos a la capacidad.
- Configuración del tenant para Copilot y el Data Agent activada.
- Versión probada: vistas semánticas en preview pública, formato `version: 0.2.0.dev0`.
  [HUECO: fecha del ensayo y resultado].

## Puesta en marcha desde cero

La demo es autocontenida: lleva los CSV, el código PySpark y los notebooks, y un script crea el workspace
y el lakehouse en tu tenant. No necesitas el repositorio de Tenerife.

```powershell
cd fabric-semantic-views
py -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env        # y rellena la capacidad, el nombre del workspace y del lakehouse
az login --tenant <tenant-id>

python scripts/fabdemo.py check              # config, login y capacidad
python scripts/fabdemo.py --dry-run deploy   # ensayo: imprime cada llamada sin tocar Fabric
python scripts/fabdemo.py deploy --run       # crea todo y ejecuta los notebooks 00 y 01
```

Todo se configura en `.env` (nunca se sube a git):

| Variable | Para qué | Por defecto |
|---|---|---|
| `FABRIC_TENANT_ID` | Tenant de Entra (opcional con un solo tenant) | — |
| `FABRIC_CAPACITY_ID` / `FABRIC_CAPACITY_NAME` | Capacidad F donde se crea el workspace (una de las dos) | — |
| `FABRIC_WORKSPACE_NAME` | Workspace de la demo (se reutiliza si existe) | `ws_frasohome_semantic_views` |
| `FABRIC_LAKEHOUSE_NAME` | Lakehouse con los CSV y las tablas | `lh_frasohome` |
| `FABRIC_LAKEHOUSE_SCHEMAS` | Crea el lakehouse con esquemas (`dbo.`), como asume `schema.yaml` | `true` |
| `FABRIC_AUTH_MODE` | `cli` (usa `az login`), `browser` o `devicecode` | `cli` |

Qué hace `deploy` (es idempotente: puedes repetirlo):

1. Crea el workspace en la capacidad indicada (o reutiliza el que ya exista con ese nombre).
2. Crea el lakehouse con esquemas habilitados.
3. Sube a OneLake los 8 CSV a `Files/bronze` y el paquete `src/frasohome_fabric` a `Files/src/frasohome_fabric`.
4. Publica los notebooks de `notebooks/` con el lakehouse como lakehouse por defecto.
5. Con `--run`, ejecuta `00_build_lakehouse` y `01_prep_vista_semantica` y espera a que terminen.

Otros comandos: `run 01` (re-ejecuta un notebook por prefijo), `status` (ítems del workspace) y
`teardown --yes` (borra el workspace si lo creó el script; si ya existía, solo el lakehouse y los notebooks).
Los IDs desplegados quedan en `.state/` (fuera de git).

> Si prefieres no usar el script, el equivalente manual es: crear el workspace y el lakehouse, subir
> `data/*.csv` a `Files/bronze` y `src/frasohome_fabric/` a `Files/src/frasohome_fabric`, y pegar los
> notebooks de `notebooks/` (celdas `# %%`) en notebooks de Fabric con ese lakehouse por defecto.

## Ficheros

| Fichero | Para qué |
|---|---|
| `.env.example` | Plantilla de configuración (workspace, lakehouse, capacidad…) |
| `scripts/fabdemo.py` | CLI de despliegue: workspace, lakehouse, datos, notebooks y ejecución |
| `data/*.csv` | Los 8 CSV crudos de FraSoHome (caso `retail_omnicanal`) |
| `src/frasohome_fabric/` | Código PySpark de la limpieza (copiado de Tenerife, ver abajo) |
| `notebooks/00_build_lakehouse.py` | Bronze → silver → gold: deja las cinco tablas que consume la vista |
| `notebooks/01_prep_vista_semantica.py` | Crea `gold_fact_movimientos` (con `fecha` sin hora) y `gold_dim_fecha`, y saca las cifras de referencia |
| `notebooks/99_reset_vista_semantica.py` | Borra las tablas de la demo (los pasos del portal, en el propio fichero) |
| `schema.yaml` | Datasets y relaciones de la vista `frasohome_ventas` |
| `metrics-ventas.yaml` | Las once métricas oficiales en DAX, con inteligencia de tiempo |
| `metrics-portabilidad.yaml` | Acto 3: dialecto `ANSI_SQL`, métrica sin DAX y `ai_context` |
| `tests/test_offline.py` | Pruebas sin tenant: `python -m unittest discover -s tests` |

Los notebooks se escriben como `.py` con celdas `# %%` (se revisan bien en git) y `deploy` los convierte a
`.ipynb` al publicarlos.

### Qué se reutilizó de Tenerife y qué cambia

`normalize.py`, `silver.py`, `gold.py` e `io.py` son copia literal de
[`tenerife-summer-sessions-2026`](https://github.com/antoniosql/materiales-sesiones/tree/main/tenerife-summer-sessions-2026).
Lo que se simplifica para que la demo sea autocontenida y barata:

- **Sin Great Expectations**: la calidad no es el tema de esta sesión, así que no hace falta un Environment.
- **Sin AI Functions**: `rules.py` normaliza los tiers de fidelización y los motivos de devolución con
  reglas. Ninguna métrica de la vista depende de esas columnas; solo salen como atributos de `clientes`.
  Los tiers no reconocibles (vacío, `N/A`) quedan a `NULL` en lugar de clasificarse con IA.
- **Solo 8 de los 11 CSV**: no se cargan `pagos_tienda` ni `stock_diario` (no alimentan la vista) ni la
  `fact_transacciones.csv` de referencia (el notebook 00 comprueba las cifras contra constantes).
- **Sin features de producto**: `gold_producto_features` necesita el stock y la vista no lo usa.

## Guion con tiempos (18 min)

**Acto 1 · de tabla gold a vista publicada (8 min)**
1. Lakehouse → cinta **New semantic view** → nombre `frasohome_ventas`. Enseñar el YAML de inicio y borrarlo.
2. Clic derecho en la carpeta → **Upload** → `schema.yaml` y `metrics-ventas.yaml`.
3. Clic derecho en la carpeta → **Publish**. La primera publicación tarda.
4. `SystemContext/Semantic Views/frasohome_ventas/`: abrir el TMDL generado.
5. **Validate in DQV**:
   `EVALUATE ROW("Brutas", [Ventas brutas], "Devoluciones", [Importe devoluciones], "Netas", [Ventas netas])`
   y compararlo con la salida del notebook `01_prep_vista_semantica`.

**Acto 2 · el agente responde con la definición (4 min)**
1. Nuevo Data Agent → **Add data source** → modelo `frasohome_ventas`.
2. Preguntas: «¿Cuáles fueron las ventas netas por canal en 2025?» y «¿Cuánto crecieron las ventas netas
   en 2025 frente a 2024?». Enseñar la DAX generada.

**Acto 3 · ¿cuánto Ossie entiende Fabric? (6 min)**
1. Subir `metrics-portabilidad.yaml` y publicar.
2. Leer los avisos: `ANSI_SQL` ignorado, «Ventas brutas solo SQL» omitida y `ai_context` descartado.
3. Opcional: crear una métrica llamada `movimientos`, igual que una tabla, y enseñar que el publish falla.

**Acto 4 (sin ejecutar, solo enseñar)**: shortcut desde otro lakehouse a `Context/Semantic Views/frasohome_ventas`.

## Preparación

1. Ejecutar «Puesta en marcha desde cero» (`deploy --run`). El notebook 00 termina imprimiendo las cifras
   del lakehouse frente a las de referencia (1.791.175,72 € de ventas brutas, 136.742,44 € de devoluciones
   y 1.654.433,28 € de ventas netas); deben salir con `OK`.
2. Abrir el log del notebook 01 y apuntar las cuatro cifras de referencia. Comprobar que la consulta de
   `store_id` duplicados no devuelve filas: si devuelve alguna, la relación `movimientos_a_tiendas` no puede
   ser de muchos a uno y hay que deduplicar en silver o quitar la relación.
3. Hacer un ensayo completo y grabar el plan B.

## Reset

`notebooks/99_reset_vista_semantica.py` (se despliega con el resto; ejecútalo con
`python scripts/fabdemo.py run 99`), con los pasos del portal que trae al principio: borrar la carpeta de la
vista y el modelo generado (son independientes), borrar el Data Agent y eliminar las dos tablas de la demo.
Para empezar de cero del todo: `python scripts/fabdemo.py teardown --yes` y volver a desplegar.

## Plan B

Capturas de cada paso en `capturas/` (carpeta por crear) y vídeo del ensayo completo. [HUECO: grabar en el ensayo].

## Coste

No hay recursos de Azure aparte de la capacidad de Fabric. Las vistas semánticas no tienen medidor propio:
usan almacenamiento OneLake y los medidores de Direct Lake. El Data Agent consume CU de la capacidad.
Si la capacidad es de pago por uso, ponla en pausa al terminar. [HUECO: CU consumidas en el ensayo].

## Cosas que comprobar en el ensayo

- Que la inteligencia de tiempo (`SAMEPERIODLASTYEAR`) funciona sin marcar `gold_dim_fecha` como tabla de
  fechas. La vista no deja marcarla y el modelo generado es de solo lectura.
- Que el notebook 01 no falla en su comprobación de columnas de `gold_fact_transacciones`.
- Si pones `FABRIC_LAKEHOUSE_SCHEMAS=false`, quitar `dbo.` de los `source` de `schema.yaml`.
- Los movimientos con fecha de 2017, 2030 o 2031, o sin fecha, quedan fuera del calendario: decidir si se
  cuenta en la sesión como ejemplo de calidad de datos.

## Datos

Usa el caso `retail_omnicanal` de FraSoHome (fuente de verdad: `antoniosql/frasohome-demos`,
`datos/retail_omnicanal/`), cargado y limpiado por `notebooks/00_build_lakehouse.py` (copia reducida del pipeline de Tenerife). Sobre el CSV
`fact_transacciones.csv` de referencia salen las tres cifras del gancho de la sesión: 1.791.175,72 € de ventas brutas,
1.654.433,28 € de ventas menos devoluciones y 1.640.580,02 € de suma con signo (66 líneas de venta con
importe negativo). El notebook 01 las recalcula sobre el lakehouse.
