"""Structural checks; HTTP contract tests are part of a later stage."""
import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
MODULES = ("main", "spherex_data", "spherex_analysis", "astronomy_catalogs", "viewer")

def test_all_five_modules_compile():
    for name in MODULES:
        path = PACKAGE / f"{name}.py"
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

def test_internal_imports_are_package_relative():
    for name in MODULES:
        tree = ast.parse((PACKAGE / f"{name}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.level == 0 and node.module in MODULES), (name, node.module)
            if isinstance(node, ast.Import):
                assert not any(alias.name in MODULES for alias in node.names), name

def test_expected_api_routes_are_preserved():
    source = (PACKAGE / "main.py").read_text(encoding="utf-8")
    for route in ("/api/health", "/api/collections", "/api/observations",
                  "/api/jobs", "/api/catalog_overlay", "/api/wise_images",
                  "/api/spectrum", "/api/spectrum/tasks"):
        assert route in source
