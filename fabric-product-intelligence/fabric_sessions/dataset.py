from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

import pandas as pd


EXPECTED_FILES: dict[str, set[str]] = {
    "crm.csv": {
        "customer_id",
        "email",
        "fecha_alta_programa",
        "tier_fidelizacion",
        "consentimiento_marketing",
        "estado_cliente",
        "canal_preferido_declarado",
    },
    "productos.csv": {
        "product_id",
        "nombre_producto",
        "categoria",
        "subcategoria",
        "precio_venta",
        "coste_unitario",
        "estado_producto",
    },
    "tiendas.csv": {"store_id", "nombre_tienda", "canal", "ciudad", "provincia", "estado"},
    "pedidos.csv": {
        "order_id",
        "fecha_pedido",
        "customer_id",
        "importe_total",
        "moneda",
        "metodo_pago",
        "estado_pedido",
        "origen",
    },
    "lineas_pedido.csv": {
        "order_line_id",
        "order_id",
        "product_id",
        "cantidad",
        "precio_unitario",
        "descuento_pct",
        "importe_linea",
    },
    "ventas_pos.csv": {
        "ticket_line_id",
        "ticket_id",
        "fecha_hora",
        "store_id",
        "customer_id",
        "product_id",
        "cantidad",
        "precio_unitario",
        "descuento_pct",
        "descuento_importe",
        "importe_linea",
        "moneda",
        "canal",
    },
    "pagos_tienda.csv": {"payment_id", "ticket_id", "fecha_pago", "store_id", "metodo_pago", "importe_pagado"},
    "devoluciones_online.csv": {
        "return_id",
        "order_id",
        "order_line_id",
        "product_id",
        "fecha_devolucion",
        "cantidad_devuelta",
        "importe_reembolsado",
    },
    "devoluciones_tienda.csv": {
        "return_id",
        "fecha_devolucion",
        "store_id",
        "ticket_id_original",
        "customer_id",
        "product_id",
        "cantidad_devuelta",
        "importe_reembolsado",
    },
    "stock_diario.csv": {"fecha", "store_id", "product_id", "stock_cierre", "stock_reservado", "stock_minimo"},
    "fact_transacciones.csv": {
        "fact_id",
        "source_system",
        "canal_origen",
        "tipo_movimiento",
        "es_devolucion",
        "fecha_movimiento",
        "customer_id_std",
        "product_id_std",
        "flag_customer_in_crm",
        "flag_product_in_master",
        "importe_signed_num",
        "moneda",
        "flag_fecha_parseada",
        "flag_importe_parseado",
    },
}

EXPECTED_ROW_COUNTS = {
    "crm.csv": 103,
    "devoluciones_online.csv": 224,
    "devoluciones_tienda.csv": 211,
    "fact_transacciones.csv": 4973,
    "lineas_pedido.csv": 1949,
    "pagos_tienda.csv": 1646,
    "pedidos.csv": 656,
    "productos.csv": 101,
    "stock_diario.csv": 1940,
    "tiendas.csv": 8,
    "ventas_pos.csv": 2521,
}


@dataclass(frozen=True)
class DatasetIssue:
    severity: str
    file: str
    message: str


def validate_source_dataset(source_dir: Path) -> list[DatasetIssue]:
    issues: list[DatasetIssue] = []
    if not source_dir.exists():
        return [DatasetIssue("error", str(source_dir), "Source data path does not exist.")]
    if not source_dir.is_dir():
        return [DatasetIssue("error", str(source_dir), "Source data path must be a directory.")]

    for file_name, required_columns in EXPECTED_FILES.items():
        file_path = source_dir / file_name
        if not file_path.exists():
            issues.append(DatasetIssue("error", file_name, "Required CSV is missing."))
            continue
        header = pd.read_csv(file_path, nrows=0).columns
        missing = sorted(required_columns - set(header))
        if missing:
            issues.append(
                DatasetIssue("error", file_name, f"Missing required columns: {', '.join(missing)}")
            )
            continue
        rows = count_csv_rows(file_path)
        expected_rows = EXPECTED_ROW_COUNTS.get(file_name)
        if expected_rows is not None and rows != expected_rows:
            issues.append(
                DatasetIssue(
                    "warning",
                    file_name,
                    f"Expected {expected_rows} rows from baseline scan, found {rows}.",
                )
            )
    return issues


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def load_csvs(source_dir: Path, names: Iterable[str] | None = None) -> dict[str, pd.DataFrame]:
    selected = list(names or EXPECTED_FILES)
    return {name: pd.read_csv(source_dir / name, dtype=str, keep_default_na=False) for name in selected}


def normalize_id(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text.upper()


def parse_money(value: object) -> float | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    text = text.replace("€", "").replace("EUR", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", "-", ".", "-."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    text = "" if value is None else str(value).strip()
    if not text:
        return pd.NaT
    dayfirst = bool(re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", text))
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)
    if pd.isna(parsed) and dayfirst:
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=False)
    elif pd.isna(parsed):
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    return parsed


def yes_no(value: object) -> bool:
    text = "" if value is None else str(value).strip().lower()
    return text in {"1", "true", "yes", "si", "sí", "y"}
