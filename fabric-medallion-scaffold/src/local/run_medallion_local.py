#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runner LOCAL del medallion FraSoHome (sin tenant de Fabric).

Reproduce con pandas el mismo flujo que los notebooks PySpark de `src/notebooks/`:
    Landing (CSV) -> Bronze (raw + trazabilidad) -> Silver (limpio/tipado/dedupe) -> Gold (star schema)

Es idempotente: cada ejecucion sobrescribe la carpeta de salida (`output/` por defecto).
La logica esta dirigida por las configuraciones metadata-driven de `config/ingestion/*.json`,
exactamente igual que la version Fabric.

Uso:
    python src/local/run_medallion_local.py [--data DIR] [--config DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- #
# Parsers robustos para los problemas de calidad intencionales de FraSoHome
# --------------------------------------------------------------------------- #
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_SLASH_FMTS = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
               "%d/%m/%y %H:%M:%S", "%d/%m/%y %H:%M", "%d/%m/%y")
_ISO_FMTS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def parse_datetime(value):
    """Convierte fechas heterogeneas (ISO, DD/MM/YY, texto en espanol) a datetime."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None
    for fmt in _ISO_FMTS + _SLASH_FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    # Texto en espanol: "14 de septiembre de 2025 08:25" / "10 de Enero de 2022"
    m = re.match(r"(\d{1,2})\s+de\s+([A-Za-zñÑáéíóú]+)\s+de\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", s, re.I)
    if m:
        d, mes, y, hh, mm = m.groups()
        mes_n = _MESES.get(_strip_accents(mes.lower()))
        if mes_n:
            return datetime(int(y), mes_n, int(d), int(hh or 0), int(mm or 0))
    return None


def parse_decimal(value):
    """Convierte importes con coma decimal y/o simbolo de moneda a float."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in ("nan", "none", "null"):
        return None
    s = re.sub(r"[€$£\s]", "", s)
    if "." in s and "," in s:            # formato europeo: 1.461,32
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                        # 127,74
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def normalize_id(value):
    """Normaliza IDs: trim, colapsa espacios y mayusculas (c0030 -> C0030)."""
    if value is None:
        return None
    s = re.sub(r"\s+", "", str(value).strip()).upper()
    return s or None


def clean_text(value):
    if value is None:
        return None
    s = re.sub(r"\s+", " ", str(value).strip())
    return s or None


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# --------------------------------------------------------------------------- #
# Capas
# --------------------------------------------------------------------------- #
def load_configs(config_dir: Path) -> list[dict]:
    cfgs = []
    for p in sorted(glob.glob(str(config_dir / "*.json"))):
        cfgs.append(json.loads(Path(p).read_text(encoding="utf-8")))
    return cfgs


def to_bronze(cfg: dict, data_dir: Path, batch_id: str, ts: datetime) -> pd.DataFrame:
    """Ingesta fiel al origen (todo string) + columnas de trazabilidad."""
    fname = Path(cfg["source_file"]).name
    df = pd.read_csv(data_dir / fname, dtype=str, keep_default_na=False, na_values=[""])
    df["_input_file_name"] = fname
    df["_ingestion_timestamp"] = ts
    df["_batch_id"] = batch_id
    return df


def to_silver(cfg: dict, bronze: pd.DataFrame) -> pd.DataFrame:
    """Tipado, normalizacion, reglas de calidad y deduplicacion por clave de negocio."""
    df = bronze.copy()
    s = cfg.get("silver", {})

    for col in s.get("id_normalize_columns", []):
        if col in df.columns:
            df[col] = df[col].map(normalize_id)
    for col in s.get("date_columns", []):
        if col in df.columns:
            df[col] = df[col].map(parse_datetime)
    for col in s.get("decimal_columns", []):
        if col in df.columns:
            df[col] = df[col].map(parse_decimal)
    # texto: limpiar columnas object restantes (no meta, no ya tipadas)
    typed = set(s.get("date_columns", [])) | set(s.get("decimal_columns", []))
    for col in df.columns:
        if col.startswith("_") or col in typed:
            continue
        if df[col].dtype == object:
            df[col] = df[col].map(clean_text)

    df["_source_system"] = cfg["source_system"]

    # Reglas de calidad
    reasons = [[] for _ in range(len(df))]
    bk = cfg["business_key"]
    for i, (_, row) in enumerate(df.iterrows()):
        if any(pd.isna(row.get(k)) or row.get(k) in (None, "") for k in bk):
            reasons[i].append("clave_negocio_nula")
        for col in s.get("decimal_columns", []):
            v = row.get(col)
            if v is not None and not pd.isna(v) and v < 0 and "descuento" not in col:
                reasons[i].append(f"{col}_negativo")
        for col in s.get("date_columns", []):
            v = row.get(col)
            if isinstance(v, datetime) and v.year > datetime.now().year + 1:
                reasons[i].append(f"{col}_fuera_de_rango")
    df["_dq_reasons"] = ["; ".join(r) for r in reasons]
    df["_is_valid"] = df["_dq_reasons"] == ""

    # Deduplicacion por clave de negocio (conserva el mas reciente)
    order_cols = [c for c in s.get("dedup_order_by", []) if c in df.columns]
    if order_cols:
        df = df.sort_values(order_cols, na_position="first")
    df = df.drop_duplicates(subset=bk, keep="last").reset_index(drop=True)
    return df


def build_gold(silver: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Modelo en estrella: dimensiones + fact_ventas (online + POS unificadas)."""
    gold: dict[str, pd.DataFrame] = {}

    # Dimensiones
    if "crm.clientes" in silver:
        c = silver["crm.clientes"]
        gold["dim_cliente"] = c[[col for col in
            ["customer_id", "nombre", "apellidos", "email", "ciudad", "provincia",
             "pais", "tier_fidelizacion", "estado_cliente"] if col in c.columns]].copy()
    if "erp.productos" in silver:
        p = silver["erp.productos"]
        gold["dim_producto"] = p[[col for col in
            ["product_id", "nombre_producto", "categoria", "subcategoria", "marca",
             "precio_venta", "coste_unitario"] if col in p.columns]].copy()
    if "erp.tiendas" in silver:
        t = silver["erp.tiendas"]
        gold["dim_tienda"] = t[[col for col in
            ["store_id", "nombre_tienda", "canal", "ciudad", "provincia", "region"]
            if col in t.columns]].copy()

    # Hecho: lineas online + lineas POS unificadas
    parts = []
    if "retail.lineas_pedido" in silver and "retail.pedidos" in silver:
        lp = silver["retail.lineas_pedido"]
        ped = silver["retail.pedidos"][["order_id", "customer_id", "fecha_pedido"]]
        online = lp.merge(ped, on="order_id", how="left")
        parts.append(pd.DataFrame({
            "venta_id": online["order_line_id"],
            "fecha": pd.to_datetime(online["fecha_pedido"], errors="coerce"),
            "customer_id": online["customer_id"],
            "product_id": online["product_id"],
            "store_id": None,
            "canal": "ONLINE",
            "cantidad": pd.to_numeric(online.get("cantidad"), errors="coerce"),
            "importe_linea": online.get("importe_linea"),
        }))
    if "pos.ventas" in silver:
        v = silver["pos.ventas"]
        parts.append(pd.DataFrame({
            "venta_id": v["ticket_line_id"],
            "fecha": pd.to_datetime(v["fecha_hora"], errors="coerce"),
            "customer_id": v.get("customer_id"),
            "product_id": v["product_id"],
            "store_id": v.get("store_id"),
            "canal": "POS",
            "cantidad": pd.to_numeric(v.get("cantidad"), errors="coerce"),
            "importe_linea": v.get("importe_linea"),
        }))
    if parts:
        fact = pd.concat(parts, ignore_index=True)
        fact["fecha_key"] = fact["fecha"].dt.strftime("%Y%m%d")
        gold["fact_ventas"] = fact
        # dim_fecha
        fechas = fact["fecha"].dropna().dt.normalize().drop_duplicates().sort_values()
        gold["dim_fecha"] = pd.DataFrame({
            "fecha_key": fechas.dt.strftime("%Y%m%d"),
            "fecha": fechas.dt.date,
            "anio": fechas.dt.year, "mes": fechas.dt.month, "dia": fechas.dt.day,
        })
    return gold


def check_integrity(gold: dict[str, pd.DataFrame]) -> list[str]:
    msgs = []
    if "fact_ventas" in gold and "dim_producto" in gold:
        prods = set(gold["dim_producto"]["product_id"].dropna())
        orphan = gold["fact_ventas"]["product_id"].dropna()
        n = (~orphan.isin(prods)).sum()
        msgs.append(f"fact_ventas: {n} lineas con product_id sin dimension (huerfanas)")
    if "fact_ventas" in gold and "dim_cliente" in gold:
        cli = set(gold["dim_cliente"]["customer_id"].dropna())
        oc = gold["fact_ventas"]["customer_id"].dropna()
        n = (~oc.isin(cli)).sum()
        msgs.append(f"fact_ventas: {n} lineas con customer_id sin dimension (huerfanas)")
    return msgs


# --------------------------------------------------------------------------- #
def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path, index=False)
    except Exception:               # sin pyarrow/fastparquet -> CSV de respaldo
        df.to_csv(path.with_suffix(".csv"), index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="Medallion FraSoHome local (pandas).")
    ap.add_argument("--data", default=str(ROOT / "data" / "retail_omnicanal"))
    ap.add_argument("--config", default=str(ROOT / "config" / "ingestion"))
    ap.add_argument("--out", default=str(ROOT / "output"))
    args = ap.parse_args()

    data_dir, config_dir, out_dir = Path(args.data), Path(args.config), Path(args.out)
    batch_id = f"local-{uuid.uuid4().hex[:8]}"
    ts = datetime.now(timezone.utc).replace(tzinfo=None)
    print(f"== Medallion FraSoHome (local) · batch_id={batch_id} ==\n")

    configs = load_configs(config_dir)
    silver_tables: dict[str, pd.DataFrame] = {}

    print(f"{'tabla':28} {'bronze':>8} {'silver':>8} {'rechazos':>9}")
    print("-" * 58)
    for cfg in configs:
        key = f"{cfg['target_schema']}.{cfg['target_table']}"
        bronze = to_bronze(cfg, data_dir, batch_id, ts)
        silver = to_silver(cfg, bronze)
        silver_tables[key] = silver
        write_parquet(bronze, out_dir / "bronze" / cfg["target_schema"] / f"{cfg['target_table']}.parquet")
        write_parquet(silver, out_dir / "silver" / cfg["target_schema"] / f"{cfg['target_table']}.parquet")
        rechazos = int((~silver["_is_valid"]).sum())
        print(f"{key:28} {len(bronze):>8} {len(silver):>8} {rechazos:>9}")

    print("\n== Gold (star schema) ==")
    gold = build_gold(silver_tables)
    for name, df in gold.items():
        write_parquet(df, out_dir / "gold" / f"{name}.parquet")
        print(f"  {name:16} {len(df):>8} filas")

    print("\n== Integridad referencial ==")
    for m in check_integrity(gold):
        print("  -", m)

    print(f"\nSalida escrita en: {out_dir}")
    print("OK. Reejecutable (idempotente): sobrescribe la salida en cada corrida.")


if __name__ == "__main__":
    main()
