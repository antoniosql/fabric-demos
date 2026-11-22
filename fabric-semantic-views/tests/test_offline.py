"""Pruebas sin tenant ni Spark: `python -m unittest discover -s tests` desde fabric-semantic-views/."""
from __future__ import annotations

import contextlib
import io
import json
import os
import py_compile
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fabdemo  # noqa: E402


class EnvFile(unittest.TestCase):
    def test_parse_and_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / ".env"
            env.write_text(
                "# comentario\nFABRIC_WORKSPACE_NAME=\"Mi WS\"\nFABRIC_LAKEHOUSE_NAME=lh_x  # nota\n"
                "FABRIC_LAKEHOUSE_SCHEMAS=false\n\nFABRIC_CAPACITY_NAME=cap1\n",
                encoding="utf-8",
            )
            cfg = fabdemo.load_config(env)
        self.assertEqual(cfg.workspace_name, "Mi WS")
        self.assertEqual(cfg.lakehouse_name, "lh_x")
        self.assertFalse(cfg.lakehouse_schemas)
        self.assertEqual(cfg.capacity_name, "cap1")
        self.assertEqual(cfg.auth_mode, "cli")

    def test_missing_file_gives_defaults(self):
        cfg = fabdemo.load_config(Path("no-existe.env"))
        self.assertTrue(cfg.workspace_name)
        self.assertTrue(cfg.lakehouse_schemas)


class NotebookConversion(unittest.TestCase):
    def test_cells_and_metadata(self):
        src = "# %% [markdown]\n# # Título\n#\n# texto\n\n# %%\nx = 1\n\nprint(x)\n\n# %%\n\n"
        nb = fabdemo.py_to_ipynb(src, {"default_lakehouse": "L"})
        self.assertEqual([c["cell_type"] for c in nb["cells"]], ["markdown", "code"])  # la celda vacía se descarta
        self.assertEqual("".join(nb["cells"][0]["source"]), "# Título\n\ntexto")
        self.assertEqual("".join(nb["cells"][1]["source"]), "x = 1\n\nprint(x)")
        self.assertEqual(nb["metadata"]["dependencies"]["lakehouse"]["default_lakehouse"], "L")

    def test_repo_notebooks_convert_and_compile(self):
        files = fabdemo.notebook_files()
        self.assertGreaterEqual(len(files), 3)
        for f in files:
            nb = fabdemo.py_to_ipynb(f.read_text(encoding="utf-8"))
            self.assertTrue(any(c["cell_type"] == "code" for c in nb["cells"]), f.name)
            json.dumps(nb)  # serializable
            code = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
            with tempfile.TemporaryDirectory() as d:
                tmp = Path(d) / "nb.py"
                tmp.write_text(code, encoding="utf-8")
                py_compile.compile(str(tmp), doraise=True)

    def test_package_modules_compile(self):
        for f in (ROOT / "src" / "frasohome_fabric").glob("*.py"):
            py_compile.compile(str(f), cfile=str(Path(tempfile.gettempdir()) / "x.pyc"), doraise=True)


class RepoContents(unittest.TestCase):
    def test_every_table_in_config_has_a_csv(self):
        sys.path.insert(0, str(ROOT / "src"))
        # config.py no importa pyspark, se puede cargar tal cual
        from frasohome_fabric import config  # noqa: PLC0415

        for csv_name in config.RAW_TABLES.values():
            self.assertTrue((ROOT / "data" / csv_name).is_file(), csv_name)

    def test_view_yaml_sources_are_built_by_the_notebooks(self):
        notebooks = "".join(f.read_text(encoding="utf-8") for f in fabdemo.notebook_files())
        for line in (ROOT / "schema.yaml").read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("source: dbo."):
                table = line.split("dbo.", 1)[1].strip()
                self.assertIn(table, notebooks)


@mock.patch.dict(os.environ, {}, clear=False)
class DryRun(unittest.TestCase):
    def setUp(self):
        for key in [k for k in os.environ if k.startswith("FABRIC_")]:
            os.environ.pop(key)  # restaurado por mock.patch.dict al terminar cada test

    def run_cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(out):
            env = Path(d) / ".env"
            env.write_text("FABRIC_CAPACITY_NAME=cap\nFABRIC_WORKSPACE_NAME=ws_test\nFABRIC_LAKEHOUSE_NAME=lh_test\n", encoding="utf-8")
            code = fabdemo.main(["--dry-run", "--env", str(env), *argv])
        return code, out.getvalue()

    def test_deploy_dry_run_with_run(self):
        code, out = self.run_cli("deploy", "--run")
        self.assertEqual(code, 0, out)
        self.assertIn("Workspace 'ws_test' creado", out)
        self.assertIn("Lakehouse 'lh_test' creado", out)
        self.assertIn("Files/bronze/crm.csv", out)
        self.assertIn("Files/src/frasohome_fabric/silver.py", out)
        for name in ("00_build_lakehouse", "01_prep_vista_semantica", "99_reset_vista_semantica"):
            self.assertIn(f"Notebook '{name}' creado", out)
        self.assertIn("Ejecutando '00_build_lakehouse'", out)
        self.assertIn("Ejecutando '01_prep_vista_semantica'", out)

    def test_capacity_is_required(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            env = Path(d) / ".env"
            env.write_text("FABRIC_WORKSPACE_NAME=ws_test\n", encoding="utf-8")
            code = fabdemo.main(["--dry-run", "--env", str(env), "deploy"])
        self.assertEqual(code, 1)
        self.assertIn("FABRIC_CAPACITY", out.getvalue())


if __name__ == "__main__":
    unittest.main()
