# %% [markdown]
# # 00 · Construir el lakehouse de FraSoHome (bronze → silver → gold)
#
# Deja en el lakehouse por defecto las tablas que necesita la vista semántica `frasohome_ventas`:
# `gold_fact_transacciones`, `gold_cliente_score`, `silver_crm`, `silver_productos` y `silver_tiendas`.
#
# Parte de `tenerife-summer-sessions-2026`, simplificado: sin Great Expectations y sin AI Functions
# (los tiers y los motivos de devolución se normalizan con reglas), de modo que no hace falta un Environment.
#
# Requisitos: CSV en `Files/bronze` y el paquete en `Files/src/frasohome_fabric` (los sube `scripts/fabdemo.py deploy`).

# %%
import sys

repo_src = "/lakehouse/default/Files/src"
if repo_src not in sys.path:
    sys.path.insert(0, repo_src)

from notebookutils import mssparkutils

from frasohome_fabric.config import BRONZE_FILES_PATH, RAW_TABLES, REFERENCE_FIGURES

# Comprobación previa: los CSV y el paquete están donde deben.
bronze_files = {f.name for f in mssparkutils.fs.ls(BRONZE_FILES_PATH)}
missing = sorted(set(RAW_TABLES.values()) - bronze_files)
assert not missing, f"Faltan CSV en {BRONZE_FILES_PATH}: {missing}. Ejecuta `fabdemo.py deploy` o súbelos a mano."
assert "frasohome_fabric" in {f.name for f in mssparkutils.fs.ls("Files/src")}, "Falta Files/src/frasohome_fabric"
print("CSV en bronze:", sorted(bronze_files))

# %% [markdown]
# ## Bronze · los CSV tal cual, como tablas Delta

# %%
from frasohome_fabric.io import ingest_bronze_tables

bronze = ingest_bronze_tables(spark, BRONZE_FILES_PATH)
for name, df in bronze.items():
    print(f"bronze_{name}: {df.count()} filas, {len(df.columns)} columnas")

# %% [markdown]
# ## Silver · limpieza sintáctica (fechas, importes, ids) y semántica por reglas

# %%
from frasohome_fabric.io import write_delta_table
from frasohome_fabric.rules import classify_return_reason_rules, classify_tier_rules
from frasohome_fabric.silver import (
    silver_crm,
    silver_devoluciones_online,
    silver_devoluciones_tienda,
    silver_lineas_pedido,
    silver_pedidos,
    silver_productos,
    silver_tiendas,
    silver_ventas_pos,
)

silver = {
    "silver_crm": classify_tier_rules(silver_crm(spark.table("bronze_crm"))),
    "silver_productos": silver_productos(spark.table("bronze_productos")),
    "silver_tiendas": silver_tiendas(spark.table("bronze_tiendas")),
    "silver_pedidos": silver_pedidos(spark.table("bronze_pedidos")),
    "silver_lineas_pedido": silver_lineas_pedido(spark.table("bronze_lineas_pedido")),
    "silver_ventas_pos": silver_ventas_pos(spark.table("bronze_ventas_pos")),
    "silver_devoluciones_online": classify_return_reason_rules(
        silver_devoluciones_online(spark.table("bronze_devoluciones_online"))
    ),
    "silver_devoluciones_tienda": classify_return_reason_rules(
        silver_devoluciones_tienda(spark.table("bronze_devoluciones_tienda"))
    ),
}
for table_name, df in silver.items():
    write_delta_table(df, table_name)
    print(f"{table_name}: {spark.table(table_name).count()} filas")

# %% [markdown]
# ## Gold · tabla de hechos, features de cliente y scoring de fuga

# %%
from frasohome_fabric.gold import build_customer_features, build_customer_score, build_gold_fact

gold_fact = build_gold_fact(
    ventas_pos=spark.table("silver_ventas_pos"),
    pedidos=spark.table("silver_pedidos"),
    lineas_pedido=spark.table("silver_lineas_pedido"),
    devoluciones_online=spark.table("silver_devoluciones_online"),
    devoluciones_tienda=spark.table("silver_devoluciones_tienda"),
    crm=spark.table("silver_crm"),
    productos=spark.table("silver_productos"),
)
write_delta_table(gold_fact, "gold_fact_transacciones")

customer_features = build_customer_features(spark)
write_delta_table(customer_features, "gold_cliente_features")
write_delta_table(build_customer_score(customer_features), "gold_cliente_score")

for table_name in ["gold_fact_transacciones", "gold_cliente_features", "gold_cliente_score"]:
    print(f"{table_name}: {spark.table(table_name).count()} filas")

# %% [markdown]
# ## Comprobación · cifras de referencia
#
# Deben coincidir (±1 €) con las de la sesión: 1.791.175,72 € de ventas brutas, 136.742,44 € de
# devoluciones y 1.654.433,28 € de ventas netas.

# %%
actual = spark.sql("""
SELECT
  ROUND(SUM(CASE WHEN tipo_movimiento = 'VENTA' THEN importe_abs ELSE 0 END), 2)      AS ventas_brutas,
  ROUND(SUM(CASE WHEN tipo_movimiento = 'DEVOLUCION' THEN importe_abs ELSE 0 END), 2) AS devoluciones
FROM gold_fact_transacciones
""").first()
actual_figures = {
    "ventas_brutas": actual["ventas_brutas"],
    "devoluciones": actual["devoluciones"],
    "ventas_netas": round(actual["ventas_brutas"] - actual["devoluciones"], 2),
}
for name, expected in REFERENCE_FIGURES.items():
    ok = abs(actual_figures[name] - expected) <= 1.0
    print(f"{'OK  ' if ok else 'DIFIERE'} {name:14s} lakehouse={actual_figures[name]:>14,.2f}  referencia={expected:>14,.2f}")
