"""Configuración del paquete (versión reducida para la demo de vistas semánticas).

Basado en `tenerife-summer-sessions-2026`, pero solo con las fuentes que alimentan la vista
`frasohome_ventas`: no se cargan `pagos_tienda` ni `stock_diario`.
"""

BRONZE_FILES_PATH = "Files/bronze"

RAW_TABLES = {
    "crm": "crm.csv",
    "devoluciones_online": "devoluciones_online.csv",
    "devoluciones_tienda": "devoluciones_tienda.csv",
    "lineas_pedido": "lineas_pedido.csv",
    "pedidos": "pedidos.csv",
    "productos": "productos.csv",
    "tiendas": "tiendas.csv",
    "ventas_pos": "ventas_pos.csv",
}

BRONZE_PREFIX = "bronze_"
SILVER_PREFIX = "silver_"
GOLD_PREFIX = "gold_"

CANONICAL_TIERS = ["Bronce", "Plata", "Oro", "Platino"]
CANONICAL_CATEGORIES = ["Decoracion", "Iluminacion", "Muebles", "Textil hogar"]
RETURN_REASON_LABELS = [
    "Talla o medidas",
    "Defecto o producto incompleto",
    "No cumple expectativa",
    "Cambio de opinion",
    "Logistica o transporte",
    "Fraude o excepcion",
]

# Cifras de referencia del caso (calculadas sobre fact_transacciones.csv de Tenerife).
# El notebook 00 las compara con las del lakehouse; no hace fallar la ejecución.
REFERENCE_FIGURES = {
    "ventas_brutas": 1791175.72,
    "devoluciones": 136742.44,
    "ventas_netas": 1654433.28,
}
