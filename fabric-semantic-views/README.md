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
  Platform, ni tener private links a nivel de workspace (restricción de la preview). Si el workspace de
  Tenerife está conectado a Git, crea uno nuevo para esta demo.
- Lakehouse con las tablas de [`tenerife-summer-sessions-2026`](https://github.com/antoniosql/materiales-sesiones/tree/main/tenerife-summer-sessions-2026) (notebooks 00-03): `gold_fact_transacciones`,
  `gold_cliente_score`, `silver_crm`, `silver_productos` y `silver_tiendas`.
- Permiso **Write** en el lakehouse y rol **Contributor** o superior en el workspace.
- Configuración del tenant para Copilot y el Data Agent activada.
- Versión probada: vistas semánticas en preview pública, formato `version: 0.2.0.dev0`.
  [HUECO: fecha del ensayo y resultado].

## Ficheros

| Fichero | Para qué |
|---|---|
| `prep_vista_semantica.py` | Crea `gold_fact_movimientos` (con `fecha` sin hora) y `gold_dim_fecha`, y saca las cifras de referencia |
| `schema.yaml` | Datasets y relaciones de la vista `frasohome_ventas` |
| `metrics-ventas.yaml` | Las once métricas oficiales en DAX, con inteligencia de tiempo |
| `metrics-portabilidad.yaml` | Acto 3: dialecto `ANSI_SQL`, métrica sin DAX y `ai_context` |
| `reset_vista_semantica.py` | Borra las tablas de la demo (los pasos del portal, en el propio fichero) |

## Guion con tiempos (18 min)

**Acto 1 · de tabla gold a vista publicada (8 min)**
1. Lakehouse → cinta **New semantic view** → nombre `frasohome_ventas`. Enseñar el YAML de inicio y borrarlo.
2. Clic derecho en la carpeta → **Upload** → `schema.yaml` y `metrics-ventas.yaml`.
3. Clic derecho en la carpeta → **Publish**. La primera publicación tarda.
4. `SystemContext/Semantic Views/frasohome_ventas/`: abrir el TMDL generado.
5. **Validate in DQV**:
   `EVALUATE ROW("Brutas", [Ventas brutas], "Devoluciones", [Importe devoluciones], "Netas", [Ventas netas])`
   y compararlo con la salida de `prep_vista_semantica.py`.

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

1. Ejecutar los notebooks 00-03 de [Tenerife](https://github.com/antoniosql/materiales-sesiones/tree/main/tenerife-summer-sessions-2026/notebooks) en el lakehouse de la demo.
2. Ejecutar `prep_vista_semantica.py` en un notebook del mismo lakehouse. Apuntar las cuatro cifras de
   referencia y comprobar que la consulta de `store_id` duplicados no devuelve filas: si devuelve alguna, la
   relación `movimientos_a_tiendas` no puede ser de muchos a uno y hay que deduplicar en silver o quitar
   la relación.
3. Hacer un ensayo completo y grabar el plan B.

## Reset

`reset_vista_semantica.py`, con los pasos del portal que trae al principio: borrar la carpeta de la vista
y el modelo generado (son independientes), borrar el Data Agent y eliminar las dos tablas de la demo.

## Plan B

Capturas de cada paso en `capturas/` (carpeta por crear) y vídeo del ensayo completo. [HUECO: grabar en el ensayo].

## Coste

No hay recursos de Azure aparte de la capacidad de Fabric. Las vistas semánticas no tienen medidor propio:
usan almacenamiento OneLake y los medidores de Direct Lake. El Data Agent consume CU de la capacidad.
Si la capacidad es de pago por uso, ponla en pausa al terminar. [HUECO: CU consumidas en el ensayo].

## Cosas que comprobar en el ensayo

- Que la inteligencia de tiempo (`SAMEPERIODLASTYEAR`) funciona sin marcar `gold_dim_fecha` como tabla de
  fechas. La vista no deja marcarla y el modelo generado es de solo lectura.
- Que los nombres de columna de las tablas gold coinciden con los de `prep_vista_semantica.py`.
- Si el lakehouse no tiene esquemas, quitar `dbo.` de los `source` de `schema.yaml`.
- Los movimientos con fecha de 2017, 2030 o 2031, o sin fecha, quedan fuera del calendario: decidir si se
  cuenta en la sesión como ejemplo de calidad de datos.

## Datos

Usa el caso `retail_omnicanal` de FraSoHome (fuente de verdad: `antoniosql/frasohome-demos`,
`datos/retail_omnicanal/`), cargado y limpiado por los notebooks de Tenerife. Sobre el CSV
`fact_transacciones.csv` salen las tres cifras del gancho de la sesión: 1.791.175,72 € de ventas brutas,
1.654.433,28 € de ventas menos devoluciones y 1.640.580,02 € de suma con signo (66 líneas de venta con
importe negativo). `prep_vista_semantica.py` las recalcula sobre el lakehouse.
