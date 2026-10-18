"""Generación de datos sintéticos de Finanzas y carga en el lakehouse (OneLake + Load Table API).

Todo en Python puro: el CSV se genera en memoria, se sube a Files/ por la API DFS de OneLake
y se convierte en tabla Delta con la API Load Table (sin Spark).
"""
from __future__ import annotations

import csv
import io
import random
from datetime import date, datetime, timedelta

from azure.storage.filedatalake import DataLakeServiceClient

from .client import FabricClient
from .fabric import log

ONELAKE_DFS = "https://onelake.dfs.fabric.microsoft.com"

REGIONES = ["Norte", "Sur", "Este", "Oeste", "Centro"]
SEGMENTOS = ["Pyme", "Gran cuenta", "Sector público", "Particular"]
ESTADOS = ["Emitida", "Cobrada", "Vencida", "Anulada"]
NOMBRES = ["Atlántica", "Brigantia", "Cíes", "Dársena", "Estela", "Faro", "Galaica", "Hércules",
           "Iria", "Juncal", "Lonxa", "Mariña", "Nordés", "Orzán", "Pedra", "Riazor", "Sálvora", "Torre"]
FORMAS = ["Servicios", "Logística", "Ingeniería", "Alimentación", "Consultoría", "Energía", "Textil"]


def _rng(seed: str) -> random.Random:
    return random.Random(seed)


def gen_clientes(n: int) -> str:
    r = _rng("clientes")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["cliente_id", "nombre", "region", "segmento", "iban", "email", "fecha_alta"])
    for i in range(1, n + 1):
        nombre = f"{r.choice(NOMBRES)} {r.choice(FORMAS)} {r.choice(['SL', 'SA', 'SLU', 'Coop'])}"
        iban = "ES" + "".join(str(r.randint(0, 9)) for _ in range(22))
        alta = date(2018, 1, 1) + timedelta(days=r.randint(0, 2800))
        w.writerow([f"C{i:05d}", nombre, r.choice(REGIONES), r.choice(SEGMENTOS), iban,
                    f"contacto{i}@cliente{i % 97}.example", alta.isoformat()])
    return buf.getvalue()


def gen_facturas(day: date, rows: int, customers: int, bad_rows: int = 0) -> str:
    """Facturas de un día. bad_rows inyecta problemas de calidad (importes negativos, cliente vacío)."""
    r = _rng(f"facturas-{day.isoformat()}")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["factura_id", "cliente_id", "fecha", "importe", "iva", "estado", "region", "lote"])
    for i in range(rows):
        cli = r.randint(1, customers)
        importe = round(r.lognormvariate(6, 0.9), 2)
        region = REGIONES[cli % len(REGIONES)]
        cliente = f"C{cli:05d}"
        if i < bad_rows:
            importe, cliente = (-importe, cliente) if i % 2 else (importe, "")
        w.writerow([f"F{day:%Y%m%d}-{i:06d}", cliente, day.isoformat(), importe,
                    round(importe * 0.21, 2), r.choices(ESTADOS, [40, 45, 10, 5])[0], region,
                    day.strftime("%Y%m%d")])
    return buf.getvalue()


class Loader:
    def __init__(self, c: FabricClient, credential, ws_id: str, lh_id: str):
        self.c, self.ws, self.lh = c, ws_id, lh_id
        self.fs = None
        if not c.dry_run:
            svc = DataLakeServiceClient(account_url=ONELAKE_DFS, credential=credential)
            self.fs = svc.get_file_system_client(ws_id)

    def upload(self, rel_path: str, content: str) -> None:
        """rel_path relativo a Files/, p. ej. 'raw/facturas/20261017.csv'."""
        full = f"{self.lh}/Files/{rel_path}"
        if self.c.dry_run:
            print(f"  [onelake] PUT {full} ({len(content):,} bytes)")
            return
        self.fs.get_file_client(full).upload_data(content.encode("utf-8"), overwrite=True)

    def load_table(self, table: str, rel_path: str, mode: str, folder: bool = False) -> None:
        body = {
            "relativePath": f"Files/{rel_path}",
            "pathType": "Folder" if folder else "File",
            "mode": mode,
            "recursive": False,
            "formatOptions": {"format": "Csv", "header": True, "delimiter": ","},
        }
        if folder:
            body["fileExtension"] = "csv"
        self.c.post(f"/workspaces/{self.ws}/lakehouses/{self.lh}/tables/{table}/load", body)

    # ------------------------------------------------------------ alto nivel
    def seed(self, days: int, rows: int, customers: int) -> None:
        self.upload("raw/clientes/clientes.csv", gen_clientes(customers))
        self.load_table("clientes", "raw/clientes/clientes.csv", "Overwrite")
        log(f"clientes: {customers} filas")
        # Histórico: un CSV por día en una carpeta y una sola carga (Load Table sobre carpeta)
        start = date.today() - timedelta(days=days)
        for k in range(days):
            day = start + timedelta(days=k)
            self.upload(f"raw/facturas/historico/{day:%Y%m%d}.csv", gen_facturas(day, rows, customers))
        self.load_table("facturas", "raw/facturas/historico", "Overwrite", folder=True)
        log(f"facturas: {days} días × {rows} filas ({days * rows:,} filas)")

    def append_day(self, day: date, rows: int, customers: int, bad_rows: int = 0) -> None:
        """Simula la carga incremental de un día (o un lote intradía) en modo Append."""
        rel = f"raw/facturas/incremental/{day:%Y%m%d}_{datetime.now():%H%M%S}.csv"
        self.upload(rel, gen_facturas(day, rows, customers, bad_rows))
        self.load_table("facturas", rel, "Append")
        extra = f", {bad_rows} erróneas" if bad_rows else ""
        print(f"    + facturas {day.isoformat()} ({rows} filas{extra}) → {rel}")
