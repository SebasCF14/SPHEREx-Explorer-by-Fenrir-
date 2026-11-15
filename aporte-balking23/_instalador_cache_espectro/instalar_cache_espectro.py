"""Parche conservador para reutilizar cubos DR1 FITS locales antes de IRSA.

Ejecutar desde la raiz del proyecto SPHEREx Explorer:
    python instalar_cache_espectro.py

Solo modifica backend/spherex_explorer/spherex_analysis.py y crea respaldo.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import sys

MARKER = '    # SPX_LOCAL_CUBE_FIRST_V1\n'
FUNCTION = 'def get_dr1_cube_spectrum('
SEARCH_ANCHOR = '    if progress is not None:\n        progress(stage="search", message='

INJECTION = '''    # SPX_LOCAL_CUBE_FIRST_V1
    # Reutilizar un cubo FITS DR1 descargado si su WCS cubre estas coordenadas.
    # El caché JSON exacto ya se revisó arriba; esto ayuda con posiciones cercanas.
    try:
        local_cubes = sorted(
            FULL_FITS_CACHE_DIR.glob("cube_dr1_*.fits"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        local_cubes = []

    for local_cube in local_cubes:
        try:
            # extract_dr1_cube_spectrum valida WCS, forma del cubo, NHITS y
            # longitudes de onda. No inventa los canales sin datos.
            spectrum, missing = extract_dr1_cube_spectrum(local_cube, coord)
            if not spectrum:
                continue

            response = {
                "collection": "spherex_dr1",
                "data_product": SPHEREX_CUBE_COLLECTION,
                "method": "dr1_all_sky_cube_102",
                "metadata_source": "local-cube-cache",
                "target": {
                    "ra_deg": float(coord.ra.deg),
                    "dec_deg": float(coord.dec.deg),
                },
                "measurement": "signal_proxy",
                "count": len(spectrum),
                "raw_count": len(spectrum),
                "observations_attempted": 102,
                "observations_skipped": 102 - len(spectrum),
                "nominal_channels": 102,
                "valid_channels": len(spectrum),
                "missing_channels": missing,
                "samples_raw": spectrum,
                "spectrum": spectrum,
                "scientific_note": (
                    "Cubo all-sky DR1: señal superficial (MJy/sr), mediana de 3x3 "
                    "por canal con NHITS>0; no es flujo fotométrico PSF de una fuente. "
                    "No se interpolan canales sin datos. Los canales 51-52 carecen de datos. "
                    "Pueden existir artefactos de mosaico (striping)."
                ),
            }
            save_json_atomic(response, cache_path)
            if progress is not None:
                progress(
                    stage="cache",
                    message="Espectro extraído de un cubo FITS DR1 local, sin descarga.",
                )
            return response
        except Exception:
            # Puede ser un tile de otra región, un FITS incompatible o dañado.
            # Nunca se borra aquí; se continúa con los demás o con IRSA.
            continue

'''


def main() -> int:
    root = Path(__file__).resolve().parent
    target = root / 'backend' / 'spherex_explorer' / 'spherex_analysis.py'
    if not target.is_file():
        print('ERROR: No encuentro backend/spherex_explorer/spherex_analysis.py')
        print('Copia este instalador a la raiz de spherex-explorer e intentalo de nuevo.')
        return 1

    original = target.read_text(encoding='utf-8-sig')
    if MARKER in original:
        print('El parche ya esta instalado. No se modifico ningun archivo.')
        return 0

    start = original.find(FUNCTION)
    if start < 0:
        print('ERROR: No encuentro get_dr1_cube_spectrum. No se modifico nada.')
        return 1
    end = original.find('\ndef ', start + len(FUNCTION))
    if end < 0:
        end = len(original)
    section = original[start:end]
    pos = section.find(SEARCH_ANCHOR)
    if pos < 0 or 'FULL_FITS_CACHE_DIR' not in original or 'extract_dr1_cube_spectrum' not in original:
        print('ERROR: La version del backend difiere de la revisada. No se modifico nada.')
        return 1

    updated = original[:start + pos] + INJECTION + original[start + pos:]
    try:
        ast.parse(updated, filename=str(target))
    except SyntaxError as exc:
        print(f'ERROR: El codigo actualizado no paso la validacion: {exc}')
        return 1

    backup = target.with_name(
        f'{target.stem}.backup_{datetime.now():%Y%m%d_%H%M%S}.py'
    )
    backup.write_text(original, encoding='utf-8')
    target.write_text(updated, encoding='utf-8')
    print('Parche instalado correctamente.')
    print(f'Respaldo: {backup}')
    print(f'Actualizado: {target}')
    print('Reinicia Flask y prueba las mismas coordenadas y otras cercanas.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
