"""Diagnóstico local de radios SPHEREx v14. No hace solicitudes a Internet."""
from backend.spherex_explorer.spherex_data import parse_coordinates, search_spherex_with_retry

RADIOS = (0.0100, 0.0150, 0.0211, 0.0221, 0.0300, 0.0500, 0.1000)
RA = "17h57m48.5s"
DEC = "+04d41m36s"
COLLECTION = "spherex_dr1"

if __name__ == "__main__":
    coord = parse_coordinates(RA, DEC)
    print("RADIOS SPHEREx v14 — INVENTARIO LOCAL SIN INTERNET")
    print(f"Centro: {RA} / {DEC}, colección: {COLLECTION}")
    print("El número de candidatos NO equivale a cobertura completa del nuevo radio.\n")
    for r in RADIOS:
        try:
            records, origin = search_spherex_with_retry(
                coord, r, COLLECTION, attempts=1, offline=True
            )
            status = {
                "cache": "CONSULTA EXACTA",
                "stale-cache": "CONSULTA EXACTA",
                "cache-contenida": "CANDIDATOS DE CONSULTA MAYOR",
                "cache-parcial": "PARCIAL (faltan observaciones posibles)",
            }.get(origin, origin)
            print(f"{r:7.4f}° | {len(records):4d} candidatos | {status}")
        except RuntimeError:
            print(f"{r:7.4f}° | SIN INVENTARIO LOCAL COMPATIBLE")
