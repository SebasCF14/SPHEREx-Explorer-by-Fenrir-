"""Dependency-free Stage 1 verification. Run from repository root."""
from __future__ import annotations
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "spherex_explorer"
MODULES = ("main", "spherex_data", "spherex_analysis", "astronomy_catalogs", "viewer")
EXPECTED_ROUTES = (
    "/api/health", "/api/collections", "/api/observations",
    "/api/jobs", "/api/catalog_overlay", "/api/wise_images",
    "/api/wise_preview", "/api/wise_fits", "/api/spectrum",
    "/api/spectrum/tasks", "/api/get_sky_timelapse",
)

def verify():
    errors = []
    for name in MODULES:
        path = PACKAGE / f"{name}.py"
        if not path.is_file():
            errors.append(f"Missing: {path}")
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
            compile(tree, str(path), "exec")
        except (SyntaxError, ValueError) as exc:
            errors.append(f"Syntax error in {name}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in MODULES and node.level == 0:
                errors.append(f"Absolute internal import in {name}: {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in MODULES:
                        errors.append(f"Absolute internal import in {name}: {alias.name}")
        print(f"PASS syntax/import convention: {name}.py")
    main = (PACKAGE / "main.py").read_text(encoding="utf-8")
    for route in EXPECTED_ROUTES:
        if route not in main:
            errors.append(f"Expected route not found: {route}")
    data = (PACKAGE / "spherex_data.py").read_text(encoding="utf-8")
    for item in ('SPHEREX_CACHE_DIR', 'CACHE_DIR', 'spherex_dr1', 'spherex_qr3'):
        if item not in data:
            errors.append(f"Missing data configuration: {item}")
    catalogs = (PACKAGE / "astronomy_catalogs.py").read_text(encoding="utf-8")
    for item in ('GAIA_ARI_TAP_SYNC_URL', 'UNWISE_URL', 'UNWISE_VERSION'):
        if item not in catalogs:
            errors.append(f"Missing catalog integration: {item}")
    if errors:
        print("\nFAIL Stage 1:\n" + "\n".join(errors), file=sys.stderr)
        return 1
    print("\nPASS Stage 1: five modules parse, internal imports are relative, route markers remain.")
    print("NOTE: This does not validate Flask runtime, external services, or scientific output.")
    return 0

if __name__ == "__main__":
    raise SystemExit(verify())
