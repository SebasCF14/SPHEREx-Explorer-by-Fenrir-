"""SPHEREx Satellite Trail Detector — etapa 1: inspección de FITS.

Este módulo NO detecta satélites todavía. Inspecciona las extensiones
FITS y carga la imagen científica sin modificar el archivo original.
"""

from pathlib import Path
import argparse
import tempfile

import numpy as np


def load_fits(path):
    """Carga una imagen FITS 2D y devuelve sus datos y metadatos.

    Prioriza la extensión IMAGE. Si no existe, busca otra imagen 2D.
    No interpreta FLAGS ni modifica los valores científicos.
    """
    from astropy.io import fits

    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

    with fits.open(file_path, memmap=True) as hdul:
        extensions = [
            {
                "index": i,
                "name": hdu.name,
                "naxis": hdu.header.get("NAXIS", 0),
                "width": hdu.header.get("NAXIS1"),
                "height": hdu.header.get("NAXIS2"),
            }
            for i, hdu in enumerate(hdul)
        ]

        selected = None
        for hdu in hdul:
            if hdu.name.upper() == "IMAGE" and hdu.header.get("NAXIS") == 2:
                selected = hdu
                break

        if selected is None:
            for hdu in hdul:
                if hdu.header.get("NAXIS") == 2 and hdu.is_image:
                    selected = hdu
                    break

        if selected is None:
            raise ValueError("El FITS no contiene una imagen científica 2D.")

        # Copia independiente: se puede utilizar después de cerrar el FITS.
        image = np.array(selected.data, copy=True)
        header = selected.header.copy()
        primary_header = hdul[0].header.copy()

    return {
        "image": image,
        "hdu_name": selected.name,
        "extensions": extensions,
        "header": header,
        "primary_header": primary_header,
        "path": str(file_path.resolve()),
    }


def inspect_fits(path):
    """Imprime un resumen técnico, sin hacer detecciones."""
    result = load_fits(path)
    image = result["image"]
    valid_pixels = int(np.count_nonzero(np.isfinite(image)))

    print(f"\nArchivo: {Path(result['path']).name}")
    print("Extensiones FITS:")
    for ext in result["extensions"]:
        print(
            f"  [{ext['index']}] {ext['name']} "
            f"(NAXIS={ext['naxis']}, "
            f"ancho={ext['width']}, alto={ext['height']})"
        )

    print(f"\nImagen seleccionada: {result['hdu_name']}")
    print(f"Dimensiones: {image.shape}")
    print(f"Tipo de datos: {image.dtype}")
    print(f"Píxeles finitos: {valid_pixels} / {image.size}")

    print("Metadatos disponibles:")
    for key in ("DATE-OBS", "MJD-OBS", "EXPTIME", "DETECTOR", "FILTER"):
        value = result["header"].get(key)
        if value is None:
            value = result["primary_header"].get(key)
        if value is not None:
            print(f"  {key}: {value}")

    print("\nInspección completada. No se han detectado estelas todavía.")
    return result


def run_demo():
    """Genera un FITS sintético temporal para comprobar la lectura."""
    from astropy.io import fits

    rng = np.random.default_rng(42)
    image = rng.normal(100.0, 2.0, (64, 64)).astype(np.float32)
    image[30, 5:59] += 30.0  # Línea sintética; NO es una detección.
    flags = np.zeros_like(image, dtype=np.uint16)
    variance = np.full_like(image, 4.0)

    hdus = fits.HDUList([
        fits.PrimaryHDU(),
        fits.ImageHDU(image, name="IMAGE"),
        fits.ImageHDU(flags, name="FLAGS"),
        fits.ImageHDU(variance, name="VARIANCE"),
    ])
    with tempfile.TemporaryDirectory() as folder:
        test_path = Path(folder) / "demo_sintetica.fits"
        hdus.writeto(test_path)
        result = inspect_fits(test_path)
        assert result["image"].shape == (64, 64)
        assert result["hdu_name"] == "IMAGE"
        print("PRUEBA PASS: lectura FITS sintética correcta.")


def main():
    parser = argparse.ArgumentParser(
        description="Etapa 1: inspeccionar imágenes FITS para SPHEREx Explorer"
    )
    parser.add_argument("fits_path", nargs="?", help="Ruta a un archivo .fits")
    parser.add_argument(
        "--demo", action="store_true", help="Probar con datos sintéticos"
    )
    args = parser.parse_args()

    try:
        if args.demo:
            run_demo()
        elif args.fits_path:
            inspect_fits(args.fits_path)
        else:
            parser.error("Indica una ruta FITS o utiliza --demo.")
    except (OSError, ValueError, AssertionError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
