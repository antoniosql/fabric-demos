"""Implementación de los comandos de fabdemo."""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta, timezone

from .auth import admin_credential, persona_credential
from .client import FabricApiError, FabricClient
from .config import ROOT, Config, State, render
from . import fabric as fx
from . import policies as pol
from . import security as sec
from .data import ONELAKE_DFS, Loader

FIN_WS = ("prod_analytics", "prod_reporting", "dev")
PROD_WS = ("prod_analytics", "prod_reporting")
POLICY_SET_NAME = "PolicySet-Capacidad-Demo"
UNSUPPORTED_REGIONS = {"westeurope", "northeurope", "westus"}

DESCRIPCIONES = {
    "lh_finanzas": "Lakehouse del dominio Finanzas: clientes y facturación diaria. Propietario: equipo de Datos Financieros.",
    "nb_generar_datos": "Genera cargas masivas de facturas sintéticas para pruebas de volumen.",
}


class Ctx:
    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.cfg = Config.load()
        self.state = State.load(dry_run)
        self.dry = dry_run
        self.cred = None if dry_run else admin_credential(self.cfg)
        self.c = FabricClient(self.cred, dry_run=dry_run, verbose=verbose)

    def persona(self, name: str) -> FabricClient:
        cred = None if self.dry else persona_credential(self.cfg, name)
        return FabricClient(cred, dry_run=self.dry, verbose=True, label=name)

    def ws(self, key: str) -> str:
        return self.state.require("workspaces")[key]

    @property
    def capacity(self) -> str:
        return self.cfg.get("tenant.capacity_id")


def _h(title: str) -> None:
    print(f"\n=== {title} ===")


# =================================================================== check
TENANT_SETTINGS = [
    (r"^policies|fabric polic", "Policies (preview) — crear y activar policy sets", "Demos 3-4"),
    (r"service principals can", "Service principals pueden usar las APIs de Fabric", "Personas SP / CI"),
    (r"apply sensitivity labels", "Allow users to apply sensitivity labels for content", "Demos 1-2"),
    (r"users can create fabric items", "Users can create Fabric items", "deploy"),
    (r"default sensitivity label", "Domain admins can set default sensitivity labels", "Opcional"),
    (r"certif", "Certification (endorsement)", "Demo 1"),
    (r"\bmcp\b", "Fabric MCP server", "Demo 5"),
]


def cmd_check(ctx: Ctx, args) -> None:
    ok = True
    _h("Configuración")
    unset = ctx.cfg.unset_values()
    if unset:
        print("  ⚠ Siguen con el GUID de ejemplo:", ", ".join(unset))
        ok = False
    else:
        print("  ✓ config/config.toml completo")

    _h("Identidad del presentador")
    try:
        ctx.c.get("/workspaces")
        print("  ✓ token de Fabric obtenido")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        return

    _h("Capacidad")
    cap = fx.get_capacity(ctx.c, ctx.capacity)
    if not cap:
        print(f"  ✗ No veo la capacidad {ctx.capacity} (¿eres capacity admin?). Capacidades visibles:")
        for cp in ctx.c.paged("/capacities"):
            print(f"      {cp.get('id')}  {cp.get('displayName')} · {cp.get('sku')} · {cp.get('region')} · {cp.get('state')}")
        ok = False
    else:
        region = (cap.get("region") or "").replace(" ", "").lower()
        print(f"  {cap.get('displayName')} · {cap.get('sku')} · {cap.get('region')} · {cap.get('state')}")
        if region in UNSUPPORTED_REGIONS:
            print("  ✗ Fabric Policies (preview) NO está disponible en esta región. Las demos 3-4 fallarán.")
            ok = False
        if cap.get("state") not in (None, "Active"):
            print("  ✗ La capacidad no está activa (¿pausada?)")
            ok = False

    _h("Tenant settings (requiere Fabric admin)")
    try:
        settings = list(ctx.c.paged("/admin/tenantsettings"))
        for rx, desc, demo in TENANT_SETTINGS:
            found = [s for s in settings if re.search(rx, s.get("title", ""), re.I)]
            if not found:
                print(f"  ? {desc} [{demo}] — no encontrado por título, revísalo en el portal")
            for s in found:
                mark = "✓" if s.get("enabled") else "✗"
                groups = ", ".join(g.get("name", "") for g in s.get("enabledSecurityGroups") or [])
                print(f"  {mark} {s.get('title')} [{demo}]{'  → grupos: ' + groups if groups else ''}")
    except FabricApiError as e:
        print(f"  ✗ No puedo leer tenant settings: {e}")

    _h("Personas")
    for name in (ctx.cfg.get("personas") or {}):
        try:
            ctx.persona(name).get("/workspaces")
            print(f"  ✓ {name} puede llamar a la API de Fabric")
        except SystemExit as e:
            print(f"  ✗ {name}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {name}: {e}")
    print("\n" + ("Todo listo." if ok else "Revisa los avisos anteriores antes de desplegar."))


# ================================================================== deploy
def cmd_deploy(ctx: Ctx, args) -> None:
    cfg, st, c = ctx.cfg, ctx.state, ctx.c
    steps = args.only.split(",") if args.only else ["platform", "data", "notebook", "security"]

    if "platform" in steps:
        _h("Dominio, workspaces, roles y tags")
        dom = fx.ensure_domain(c, cfg.domain_name, cfg.get("domain.description", ""))
        st.set("domain_id", dom)
        fx.assign_domain_admins(c, dom, cfg.get("domain.admin_user_ids", []))

        ws = {}
        for key in (*FIN_WS, "gobierno"):
            ws[key] = fx.ensure_workspace(c, cfg.ws_name(key), ctx.capacity, f"Demo MIDP · {key}")
        st.set("workspaces", ws)
        fx.assign_domain_workspaces(c, dom, [ws[k] for k in FIN_WS])

        g = cfg.get("groups")
        for k in PROD_WS:
            fx.ensure_role(c, ws[k], g["ingenieros_prod"], "Group", "Contributor")
            fx.ensure_role(c, ws[k], g["finanzas_analistas"], "Group", "Viewer")
        fx.ensure_role(c, ws["prod_analytics"], g["analistas_norte"], "Group", "Viewer")
        for name, p in (cfg.get("personas") or {}).items():
            ptype = "ServicePrincipal" if p.get("type") == "sp" else "User"
            for k in FIN_WS:
                fx.ensure_role(c, ws[k], p["object_id"], ptype, "Contributor")

        st.set("tags", fx.ensure_domain_tags(c, dom, cfg.get("tags.names", [])))

    if "data" in steps:
        _h("Lakehouse y carga inicial")
        ws_id = ctx.ws("prod_analytics")
        lh = fx.ensure_lakehouse(c, ws_id, cfg.get("data.lakehouse"), "")  # sin descripción: la pone la demo 1
        st.set("lakehouse_id", lh)
        st.set("lakehouse_ws_id", ws_id)
        Loader(c, ctx.cred, ws_id, lh).seed(cfg.get("data.seed_days", 30), cfg.get("data.rows_per_day", 1500),
                                            cfg.get("data.customers", 400))

    if "notebook" in steps:
        _h("Notebook de carga masiva")
        ipynb = render((ROOT / "notebooks" / "nb_generar_datos.ipynb").read_text(encoding="utf-8"), cfg, st)
        nb = fx.ensure_notebook(c, ctx.ws("prod_analytics"), cfg.get("data.notebook"), ipynb, "")
        st.set("notebook_id", nb)

    if "security" in steps:
        _h("OneLake security (RLS/CLS)")
        try:
            sec.apply_roles(c, st.require("lakehouse_ws_id"), st.require("lakehouse_id"), cfg, st)
        except FabricApiError as e:
            print(f"  ⚠ {e}\n    ¿Está activada OneLake security en el lakehouse? Ver docs/03-pasos-manuales.md")

    print("\nDespliegue terminado. Siguiente: `fabdemo status` y docs/02-guion-demos.md")


# ==================================================================== data
def cmd_data(ctx: Ctx, args) -> None:
    cfg, st, c = ctx.cfg, ctx.state, ctx.c
    loader = Loader(c, ctx.cred, st.require("lakehouse_ws_id"), st.require("lakehouse_id"))
    customers = cfg.get("data.customers", 400)
    if args.action == "load":
        day0 = date.fromisoformat(args.date) if args.date else date.today()
        for k in range(args.days):
            loader.append_day(day0 + timedelta(days=k), args.rows, customers, bad_rows=args.bad_rows)
    elif args.action == "stream":
        print(f"Simulando {args.batches} lotes cada {args.every}s (Ctrl+C para parar)")
        try:
            for b in range(args.batches):
                loader.append_day(date.today(), args.rows, customers, bad_rows=args.bad_rows)
                if b < args.batches - 1:
                    time.sleep(0 if ctx.dry else args.every)
        except KeyboardInterrupt:
            print("Parado.")
    elif args.action == "reseed":
        loader.seed(args.days, args.rows, customers)
    elif args.action == "notebook":
        status = fx.run_notebook(c, st.require("lakehouse_ws_id"), st.require("notebook_id"))
        print(f"Notebook: {status}")


# ================================================================== demo 1
DRIFT_LAKEHOUSES = ["copia_facturas_v2", "test_ingesta_sap", "backup_clientes_old", "facturas_final_FINAL",
                    "lh_pruebas_juan", "staging_tmp", "export_excel_cfo", "lh_nuevo"]
DRIFT_NOTEBOOKS = ["tmp analisis q3", "exploracion rapida", "Notebook 1", "prueba cruce clientes",
                   "copia de nb_generar_datos", "borrador kpis", "Notebook 7", "limpieza manual"]


def cmd_demo1(ctx: Ctx, args) -> None:
    cfg, st, c = ctx.cfg, ctx.state, ctx.c
    if args.action == "drift":
        _h("Generando ítems sin gobernar")
        created = st.get("drift_items", [])
        n = cfg.get("drift.items_per_workspace", 4)
        stamp = datetime.now().strftime("%H%M")
        for w, key in enumerate(FIN_WS):
            for i in range(n):
                is_lh = i % 2 == 0
                pool = DRIFT_LAKEHOUSES if is_lh else DRIFT_NOTEBOOKS
                base = pool[(w * n + i) // 2 % len(pool)]
                name = f"{base}_{stamp}" if is_lh else f"{base} {stamp}"
                itype = "Lakehouse" if is_lh else "Notebook"
                try:
                    it = fx.create_item(c, ctx.ws(key), name, itype)
                except FabricApiError as e:
                    print(f"  ⚠ {name}: {e.code or e.status} (¿hay una directiva activa?)")
                    continue
                created.append({"ws": ctx.ws(key), "id": it["id"], "type": itype, "name": name})
                fx.log(f"{cfg.ws_name(key)} / {name}")
        st.set("drift_items", created)
        print("\nEl Govern de admin se refresca una vez al día: genera el drift la víspera.")
    elif args.action == "fix":
        _h("Gobernando los activos principales")
        tags = st.get("tags", {})
        core = [(st.require("lakehouse_ws_id"), st.require("lakehouse_id"), "Lakehouse", "lh_finanzas"),
                (st.require("lakehouse_ws_id"), st.require("notebook_id"), "Notebook", "nb_generar_datos")]
        for ws_id, item_id, itype, name in core:
            fx.set_description(c, ws_id, item_id, DESCRIPCIONES[name])
            fx.apply_tags(c, ws_id, item_id, [tags[t] for t in ("Facturación",) if t in tags])
            fx.log(f"{name}: descripción y tag")
        items = [{"id": i, "type": t} for _, i, t, _ in core]
        if args.all:
            for d in st.get("drift_items", []):
                fx.set_description(c, d["ws"], d["id"], "Ítem temporal pendiente de clasificar por el propietario.")
                items.append({"id": d["id"], "type": d["type"]})
            fx.log(f"{len(st.get('drift_items', []))} ítems temporales descritos")
        fx.set_labels(c, items, cfg.get("labels.general"))
        print("\nEndorsement (certificar lh_finanzas) no tiene API: hazlo en vivo desde el portal.")
    elif args.action == "reset":
        _h("Borrando ítems sin gobernar")
        for d in st.get("drift_items", []):
            try:
                fx.delete_item(c, d["ws"], d["id"])
                fx.log(f"borrado {d['name']}")
            except FabricApiError as e:
                print(f"  ⚠ {d['name']}: {e}")
        st.set("drift_items", [])
    elif args.action == "status":
        _h("Estado de gobierno por workspace")
        for key in FIN_WS:
            items = [i for i in fx.list_items(c, ctx.ws(key)) if i.get("type") not in ("SQLEndpoint",)]
            sin_desc = [i for i in items if not i.get("description")]
            print(f"  {cfg.ws_name(key):<28} ítems: {len(items):>3} · sin descripción: {len(sin_desc):>3}")


# ================================================================== demo 2
def _probe_lakehouse(pc: FabricClient, persona_cred, ws_id: str, lh_id: str, dry: bool) -> None:
    try:
        it = pc.get(f"/workspaces/{ws_id}/items/{lh_id}")
        print(f"  ✓ metadatos visibles: {(it or {}).get('displayName', '(dry-run)')}")
    except FabricApiError as e:
        print(f"  ✗ metadatos: {e.status} {e.code}")
    if dry:
        print("  [onelake] LIST Tables/ (dry-run)")
        return
    try:
        from azure.storage.filedatalake import DataLakeServiceClient
        fs = DataLakeServiceClient(ONELAKE_DFS, credential=persona_cred).get_file_system_client(ws_id)
        names = [p.name.split("/")[-1] for p in fs.get_paths(path=f"{lh_id}/Tables", recursive=False)]
        print(f"  ✓ datos accesibles en OneLake: {', '.join(names) or '(sin tablas)'}")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ datos en OneLake: {type(e).__name__} {str(e).splitlines()[0][:120]}")


def cmd_demo2(ctx: Ctx, args) -> None:
    cfg, st, c = ctx.cfg, ctx.state, ctx.c
    lh = [{"id": st.require("lakehouse_id"), "type": "Lakehouse"}]
    if args.action == "label":
        _h("Etiquetando lh_finanzas como Confidencial-Finanzas")
        fx.set_labels(c, lh, cfg.get("labels.confidencial_finanzas"))
        print("\nLa protection policy (Purview) puede tardar hasta 24 h en aplicarse.")
    elif args.action == "unlabel":
        fx.remove_labels(c, lh)
        fx.log("Etiqueta retirada")
    elif args.action == "probe":
        _h(f"¿Qué ve '{args.persona}' de lh_finanzas?")
        pc = ctx.persona(args.persona)
        _probe_lakehouse(pc, pc.credential, st.require("lakehouse_ws_id"), st.require("lakehouse_id"), ctx.dry)


# ================================================================== demo 3
def _deploy_and_maybe_activate(ctx: Ctx, file: str, activate: bool) -> str:
    path = pol.resolve_policy_file(file)
    policy = pol.load_policy(path, ctx.cfg, ctx.state)
    ps = pol.deploy_policy_set(ctx.c, ctx.ws("gobierno"), POLICY_SET_NAME, policy,
                               f"Desplegado desde {path.name}")
    ctx.state.set("policy_set_id", ps)
    if activate:
        pol.activate(ctx.c, ctx.ws("gobierno"), ps, ctx.capacity)
    return ps


def cmd_demo3(ctx: Ctx, args) -> None:
    st = ctx.state
    if args.action == "apply":
        _h(f"Directiva de creación de ítems · {args.version}")
        f = {"v1": "item-creation.v1-trampa.json", "v2": "item-creation.v2-corregida.json"}[args.version]
        if args.version == "v1" and not args.yes:
            print("⚠ v1 bloquea la creación de casi todo en TODA la capacidad.")
            if input("¿Continuar? [s/N] ").strip().lower() != "s":
                return
        _deploy_and_maybe_activate(ctx, f, activate=True)
    elif args.action == "off":
        pol.deactivate(ctx.c, ctx.ws("gobierno"), st.require("policy_set_id"))
    elif args.action == "status":
        act = pol.active_for_capacity(ctx.c, ctx.capacity)
        print(f"Activo en la capacidad: {act.get('displayName') if act else 'ninguno'}")
    elif args.action == "probe":
        _h(f"Probando creación de ítems como '{args.persona}'")
        pc = ctx.persona(args.persona)
        types = args.types.split(",")
        stamp = datetime.now().strftime("%H%M%S")
        header = f"  {'workspace':<28}" + "".join(f"{t:<15}" for t in types)
        print(header)
        for key in FIN_WS:
            row = f"  {ctx.cfg.ws_name(key):<28}"
            for t in types:
                try:
                    it = fx.create_item(pc, ctx.ws(key), f"probe_{t}_{stamp}", t)
                    row += f"{'✓ permitido':<15}"
                    if not args.keep and it:
                        try:
                            fx.delete_item(pc, ctx.ws(key), it["id"])
                        except FabricApiError:
                            pass
                except FabricApiError as e:
                    row += f"{'✗ ' + (e.code or str(e.status))[:12]:<15}"
            print(row)
        print("\nRecuerda: la directiva tarda hasta 15 min en aplicarse tras activarla.")


# ================================================================== demo 4
def cmd_demo4(ctx: Ctx, args) -> None:
    st, c = ctx.state, ctx.c
    ws = ctx.ws("gobierno")
    if args.action == "diff":
        local = pol.load_policy(pol.resolve_policy_file(args.file), ctx.cfg, st)
        remote = pol.get_deployed(c, ws, st.require("policy_set_id"))
        d = pol.diff(local, remote)
        print(d or "Sin diferencias: lo desplegado coincide con el repositorio.")
    elif args.action == "deploy":
        _deploy_and_maybe_activate(ctx, args.file, activate=False)
        print("Desplegado (no activado). La activación es un paso explícito: `fabdemo demo4 activate`.")
    elif args.action == "activate":
        pol.activate(c, ws, st.require("policy_set_id"), ctx.capacity)
    elif args.action == "export":
        remote = pol.get_deployed(c, ws, st.require("policy_set_id"))
        out = ROOT / "out" / "policySet.exported.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(remote, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Exportado a {out}")


# ================================================================== demo 5
PROMPTS = [
    "¿Existe ya un lakehouse de clientes certificado en el dominio Finanzas?",
    "Lista los ítems del workspace MIDP-Fin-Prod-Analytics que no tienen descripción.",
    "¿Qué roles tiene el grupo Ingenieros-Prod en los workspaces de Finanzas?",
    "Antes de crear un lakehouse nuevo de facturas, busca si ya hay uno que pueda reutilizar.",
]


def cmd_demo5(ctx: Ctx, args) -> None:
    _h("Gobierno con agentes (MCP de Fabric)")
    print("Servidor MCP configurado en .vscode/mcp.json →", json.loads((ROOT / ".vscode" / "mcp.json").read_text())["servers"]["fabric"]["url"])
    print("Abre esta carpeta en VS Code, inicia el servidor 'fabric' (MCP: List Servers) y prueba en Copilot Chat (modo Agent):\n")
    for p in PROMPTS:
        print(f"  » {p}")


# ================================================================ security
def cmd_security(ctx: Ctx, args) -> None:
    st = ctx.state
    if args.action == "apply":
        sec.apply_roles(ctx.c, st.require("lakehouse_ws_id"), st.require("lakehouse_id"), ctx.cfg, st)
    else:
        sec.show_roles(ctx.c, st.require("lakehouse_ws_id"), st.require("lakehouse_id"))


# =================================================================== audit
def cmd_audit(ctx: Ctx, args) -> None:
    _h(f"Actividad de las últimas {args.hours} h" + (f" que contiene '{args.contains}'" if args.contains else ""))
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=args.hours)
    rows = []
    cursor = start
    while cursor < end:  # la API exige que inicio y fin sean el mismo día UTC
        day_end = min(end, datetime.combine(cursor.date(), datetime.max.time(), tzinfo=timezone.utc))
        path = (f"/admin/activityevents?startDateTime='{cursor:%Y-%m-%dT%H:%M:%S}'"
                f"&endDateTime='{day_end:%Y-%m-%dT%H:%M:%S}'")
        while path:
            data = ctx.c.powerbi("GET", path) or {}
            rows += data.get("activityEventEntities", [])
            path = data.get("continuationUri") if not data.get("lastResultSet") else None
        cursor = datetime.combine(cursor.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    needle = (args.contains or "").lower()
    rows = [r for r in rows if not needle or needle in json.dumps(r, ensure_ascii=False).lower()]
    for r in sorted(rows, key=lambda x: x.get("CreationTime", ""))[-args.limit:]:
        print(f"  {r.get('CreationTime', '')[:19]}  {r.get('UserId', ''):<32} {r.get('Activity', ''):<28} "
              f"{r.get('ItemName') or r.get('ArtifactName') or ''}  {r.get('WorkSpaceName') or ''}")
    print(f"\n{len(rows)} eventos. (La auditoría puede tardar ~30 min en reflejar actividad reciente.)")


# ================================================================== status
def cmd_status(ctx: Ctx, args) -> None:
    _h("Estado local (.state/state.json)")
    print(json.dumps(ctx.state.data, indent=2, ensure_ascii=False))
    if ctx.state.get("workspaces"):
        _h("Directiva activa en la capacidad")
        act = pol.active_for_capacity(ctx.c, ctx.capacity)
        print(f"  {act.get('displayName') if act else 'ninguna'}")


# ================================================================ teardown
def cmd_teardown(ctx: Ctx, args) -> None:
    st, c = ctx.state, ctx.c
    if not args.yes:
        print("Esto borra los workspaces, el dominio y los tags de la demo. Repite con --yes.")
        return
    if st.get("policy_set_id") and st.get("workspaces"):
        try:
            pol.deactivate(c, ctx.ws("gobierno"), st.get("policy_set_id"))
        except FabricApiError as e:
            print(f"  ⚠ {e}")
    for key, ws_id in (st.get("workspaces") or {}).items():
        try:
            fx.delete_workspace(c, ws_id)
            fx.log(f"workspace {key} borrado")
        except FabricApiError as e:
            print(f"  ⚠ {key}: {e}")
    for name, tag_id in (st.get("tags") or {}).items():
        try:
            fx.delete_tag(c, tag_id)
        except FabricApiError as e:
            print(f"  ⚠ tag {name}: {e}")
    if st.get("domain_id"):
        try:
            fx.delete_domain(c, st.get("domain_id"))
            fx.log("dominio borrado")
        except FabricApiError as e:
            print(f"  ⚠ dominio: {e}")
    st.data = {}
    st.save()
    print("Teardown terminado.")
