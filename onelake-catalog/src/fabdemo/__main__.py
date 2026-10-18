"""CLI de fabdemo. Ejecuta `fabdemo -h` o `python -m fabdemo -h`."""
from __future__ import annotations

import argparse
import sys

from . import commands as cmd
from .client import FabricApiError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fabdemo", description="Demos de gobierno del OneLake Catalog (MIDP)")
    p.add_argument("--dry-run", action="store_true", help="no llama a Fabric; imprime las peticiones")
    p.add_argument("-v", "--verbose", action="store_true", help="muestra cada llamada a la API")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="comprueba config, capacidad, tenant settings y personas")

    d = sub.add_parser("deploy", help="despliega dominio, workspaces, roles, tags, lakehouse, datos y seguridad")
    d.add_argument("--only", help="pasos separados por comas: platform,data,notebook,security")

    da = sub.add_parser("data", help="simula cargas de datos")
    da.add_argument("action", choices=["load", "stream", "reseed", "notebook"])
    da.add_argument("--days", type=int, default=1)
    da.add_argument("--rows", type=int, default=1500)
    da.add_argument("--date", help="YYYY-MM-DD (por defecto hoy)")
    da.add_argument("--bad-rows", type=int, default=0, help="filas con problemas de calidad por lote")
    da.add_argument("--every", type=int, default=60, help="segundos entre lotes (stream)")
    da.add_argument("--batches", type=int, default=10, help="número de lotes (stream)")

    d1 = sub.add_parser("demo1", help="Govern: del rojo al verde")
    d1.add_argument("action", choices=["drift", "status", "fix", "reset"])
    d1.add_argument("--all", action="store_true", help="fix: incluye también los ítems temporales")

    d2 = sub.add_parser("demo2", help="Etiquetas y protection policies")
    d2.add_argument("action", choices=["label", "unlabel", "probe"])
    d2.add_argument("--persona", default="outsider")

    d3 = sub.add_parser("demo3", help="Fabric Policies: solo ingeniería crea en Prod")
    d3.add_argument("action", choices=["apply", "off", "status", "probe"])
    d3.add_argument("version", nargs="?", choices=["v1", "v2"], default="v2")
    d3.add_argument("--persona", default="outsider")
    d3.add_argument("--types", default="Notebook,DataPipeline,Lakehouse")
    d3.add_argument("--keep", action="store_true", help="no borra los ítems de prueba creados")
    d3.add_argument("--yes", action="store_true", help="no pide confirmación")

    d4 = sub.add_parser("demo4", help="Directivas como código")
    d4.add_argument("action", choices=["diff", "deploy", "activate", "export"])
    d4.add_argument("file", nargs="?", default="item-creation.v2-corregida.json")

    sub.add_parser("demo5", help="Gobierno con agentes (MCP)")

    s = sub.add_parser("security", help="roles de OneLake security (RLS/CLS)")
    s.add_argument("action", choices=["apply", "show"])

    a = sub.add_parser("audit", help="actividad reciente (Power BI/Fabric activity events)")
    a.add_argument("--hours", type=int, default=2)
    a.add_argument("--contains", help="filtra por texto, p. ej. Policy, Label, Create")
    a.add_argument("--limit", type=int, default=50)

    sub.add_parser("status", help="estado del despliegue")

    t = sub.add_parser("teardown", help="borra todo lo desplegado")
    t.add_argument("--yes", action="store_true")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # emojis y tildes en la consola de Windows
    ctx = cmd.Ctx(dry_run=args.dry_run, verbose=args.verbose)
    handler = getattr(cmd, f"cmd_{args.command}")
    try:
        handler(ctx, args)
    except FabricApiError as e:
        print(f"\n✗ Error de la API de Fabric: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
