"""Archivos externos: Gaia DR3, AllWISE, NEOWISE-R, búsqueda IBE/SIA2 y overlays.
Este módulo no importa Flask ni el programa principal.
Gaia v9: respaldo ARI; AllWISE v10: VizieR Harvard; v11: recortes unWISE neo1.
"""

from .spherex_data import (
    atomic_replace,
    CATALOG_CACHE_DIR,
    CATALOG_CACHE_TTL,
    CATALOG_MAX_SOURCES,
    CATALOG_QUERY_TIMEOUT,
    CONNECT_TIMEOUT,
    csv,
    GAIA_TAP_SYNC_URL,
    get_http_session,
    ImageDraw,
    ImageFont,
    IRSA_IBE_HOSTS,
    IRSA_IBE_SEARCH_BASE,
    IRSA_TAP_SYNC_URL,
    json,
    make_hash,
    np,
    Path,
    re,
    READ_TIMEOUT,
    requests,
    save_json_atomic,
    time,
    Time,
    urlencode,
    urlsplit,
    urlunsplit,
    WISE_API_VERSION,
    WISE_METADATA_CACHE_DIR,
    WISE_METADATA_CACHE_TTL,
    WISE_SIA_MAXREC,
)
from .spherex_analysis import format_mjd
from urllib.parse import parse_qs, quote, unquote

# Gaia DR3: la réplica pública de ARI Heidelberg actúa como respaldo de ESA.
GAIA_ARI_TAP_SYNC_URL = "https://gaia.ari.uni-heidelberg.de/tap/sync"
GAIA_ESA_TIMEOUT = (5, 12)  # conexión y lectura, sin reintentos automáticos


# Respaldo oficial AWS S3 y archivos FITS locales, sin alterar otros módulos.
WISE_LOCAL_FITS_DIR = WISE_METADATA_CACHE_DIR.parent / "local_fits"
WISE_FULL_FITS_CACHE_DIR = WISE_METADATA_CACHE_DIR.parent / "fits_originales"
WISE_AWS_BASE = "https://nasa-irsa-wise.s3.us-west-2.amazonaws.com"
WISE_FITS_MAX_BYTES = 140 * 1024 * 1024
WISE_LOCAL_FITS_DIR.mkdir(parents=True, exist_ok=True)
for _wise_dataset in ("allwise", "neowiser"):
    (WISE_LOCAL_FITS_DIR / _wise_dataset).mkdir(parents=True, exist_ok=True)
WISE_FULL_FITS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# unWISE es un conjunto de coadds, NO exposiciones individuales NEOWISE-R L1b.
# El endpoint /cutout_fits de unWISE admite tamaños de hasta 1024 píxeles.
UNWISE_URL = "https://unwise.me/cutout_fits"
UNWISE_VERSION = "neo1"  # versión probada directamente por el usuario
UNWISE_PIXEL_SCALE_ARCSEC = 2.75
UNWISE_MIN_SIZE = 100
UNWISE_MAX_SIZE = 1024
UNWISE_MAX_RADIUS_DEG = 0.35
UNWISE_MAX_TAR_BYTES = 32 * 1024 * 1024
UNWISE_MAX_FITS_BYTES = 16 * 1024 * 1024
UNWISE_CACHE_DIR = WISE_METADATA_CACHE_DIR.parent / "unwise_cutouts"
UNWISE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def safe_float(value):
    try:
        if value is None or np.ma.is_masked(value):
            return None
        text_value = str(value).strip()
        if text_value in ("", "--", "None", "null"):
            return None
        result = float(text_value)
        return result if np.isfinite(result) else None
    except (TypeError, ValueError):
        return None

def parse_csv_response(response, source_label):
    """Convierte respuestas CSV de servicios TAP/IBE en diccionarios."""
    text = response.content.decode("utf-8-sig", errors="replace").strip()

    if not text:
        return []

    if text.startswith("<"):
        raise RuntimeError(
            f"{source_label} devolvió XML/HTML en vez de CSV: "
            f"{text[:250]}"
        )

    useful_lines = [
        line for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    if not useful_lines:
        return []

    reader = csv.DictReader(useful_lines)
    rows = []

    for raw_row in reader:
        normalized = {
            str(key).strip().lower(): (
                value.strip() if isinstance(value, str) else value
            )
            for key, value in raw_row.items()
            if key is not None
        }
        rows.append(normalized)

    return rows

def execute_tap_csv(endpoint, adql, source_label, *, fast_failure=False):
    """Consulta TAP por POST y GET y devuelve únicamente registros oficiales.

    fast_failure evita reintentos HTTP automáticos al detectar que ESA no está
    accesible, permitiendo pasar a ARI sin bloquear innecesariamente la interfaz.
    El resto de los catálogos conserva su comportamiento previo.
    """
    arguments = {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql}
    errors = []
    session = requests.Session() if fast_failure else get_http_session()
    if fast_failure:
        session.headers.update({"User-Agent": "SPHEREx-Explorer/1.0"})
    timeout = GAIA_ESA_TIMEOUT if fast_failure else (10, CATALOG_QUERY_TIMEOUT)
    try:
        for method in ("POST", "GET"):
            try:
                if method == "POST":
                    response = session.post(endpoint, data=arguments, timeout=timeout)
                else:
                    response = session.get(endpoint, params=arguments, timeout=timeout)
                response.raise_for_status()
                return parse_csv_response(response, source_label)
            except (requests.RequestException, RuntimeError) as error:
                errors.append(f"{method}: {type(error).__name__}: {str(error)[:220]}")
    finally:
        if fast_failure:
            session.close()
    raise RuntimeError(f"{source_label}: no respondió el archivo TAP. " + " | ".join(errors))

def query_gaia_ari_lightweight(ra_deg, dec_deg, radius_deg):
    """Respaldo TAP optimizado: campos de posiciones y movimiento, sin ORDER BY.

    El plan ligero evita la consulta anterior de 350 fuentes, 11 columnas y
    ordenamiento; las 120 fuentes iniciales son un subconjunto exploratorio,
    NO un censo Gaia completo ni necesariamente las 120 más brillantes.

    Ante un timeout se reduce TOP, conservando el origen real de los datos.
    """
    endpoint = GAIA_ARI_TAP_SYNC_URL
    errors = []
    for limit in (120, 30, 5):
        adql = (
            f"SELECT TOP {limit} source_id, ra, dec, pmra, pmdec, "
            "phot_g_mean_mag "
            "FROM gaiadr3.gaia_source_lite "
            "WHERE 1 = CONTAINS(POINT('ICRS', ra, dec), "
            f"CIRCLE('ICRS', {ra_deg:.10f}, {dec_deg:.10f}, {radius_deg:.10f}))"
        )
        arguments = {
            "REQUEST": "doQuery", "LANG": "ADQL",
            "FORMAT": "csv", "QUERY": adql,
        }
        try:
            # GET fue el método que ya devolvió CSV real desde PowerShell.
            # Usar requests.get sin el adaptador global evita reintentos en cascada.
            response = requests.get(
                endpoint,
                params=arguments,
                timeout=(8, 22),
                headers={"User-Agent": "SPHEREx-Explorer/1.0"},
            )
            response.raise_for_status()
            rows = parse_csv_response(response, "ARI Heidelberg / Gaia DR3")
            if rows and not all("ra" in row and "dec" in row for row in rows):
                raise RuntimeError("El CSV de ARI no contiene las columnas RA y Dec.")
            return rows, limit
        except (requests.RequestException, RuntimeError) as error:
            errors.append(f"TOP {limit}: {type(error).__name__}: {str(error)[:200]}")
    raise RuntimeError(
        "ARI Heidelberg no respondió a las consultas ligeras: " +
        " | ".join(errors)
    )

# Catálogo AllWISE de VizieR (CDS), servido por el espejo de Harvard.
# Este servicio devuelve posiciones/fotometría, NO imágenes FITS.
ALLWISE_VIZIER_HARVARD_URL = "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv"
ALLWISE_VIZIER_CATALOG_ID = "II/328/allwise"


def parse_vizier_allwise_tsv(raw_text):
    """Analiza TSV ASU de VizieR sin confundir cabeceras/unidades con fuentes.

    Solo acepta tablas reconocibles con RAJ2000 y DEJ2000 en grados.
    No intenta interpretar páginas HTML de error como registros del catálogo.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise RuntimeError("VizieR devolvió una respuesta vacía.")
    stripped = raw_text.lstrip()
    if stripped.startswith("<") or "<html" in stripped[:500].lower():
        raise RuntimeError("VizieR devolvió HTML/XML en vez de una tabla TSV.")
    lines = [line for line in raw_text.splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    header_index = None
    header = None
    for index, line in enumerate(lines):
        names = [cell.strip().lower() for cell in line.split("\t")]
        if "raj2000" in names and "dej2000" in names:
            header_index = index
            header = names
            break
    if header is None:
        raise RuntimeError(
            "La respuesta de VizieR no contiene columnas RAJ2000 y DEJ2000. "
            "Es posible que el catálogo no esté disponible o la consulta haya fallado."
        )
    rows = []
    ix_ra = header.index("raj2000")
    ix_dec = header.index("dej2000")
    for line in lines[header_index + 1:]:
        cells = [cell.strip() for cell in line.split("\t")]
        if len(cells) < len(header):
            continue
        ra = safe_float(cells[ix_ra])
        dec = safe_float(cells[ix_dec])
        # Saltar las dos líneas habituales de unidades/rayas y datos inválidos.
        if ra is None or dec is None or not (0 <= ra < 360 and -90 <= dec <= 90):
            continue
        row = dict(zip(header, cells))
        rows.append(row)
    return rows


def query_allwise_vizier_harvard(ra_deg, dec_deg, radius_arcmin):
    """Recupera AllWISE II/328 desde VizieR/Harvard si IRSA TAP falla.

    Consulta ligera y limitada; las 120 primeras fuentes no son un censo del
    campo ni necesariamente las más brillantes. Documenta la procedencia.
    """
    errors = []
    for limit in (120, 30, 10):
        params = {
            "-source": ALLWISE_VIZIER_CATALOG_ID,
            "-c": f"{ra_deg:.10f} {dec_deg:.10f}",
            "-c.rs": f"{float(radius_arcmin) * 60.0:.5f}",
            "-out": "RAJ2000,DEJ2000,W1mag,W2mag",
            "-out.max": str(limit),
        }
        try:
            # No usar la sesión compartida: los reintentos sobre 502 pueden
            # bloquear durante varios minutos el botón del catálogo.
            with requests.Session() as session:
                session.headers.update({"User-Agent": "SPHEREx-Explorer/1.0"})
                response = session.get(
                    ALLWISE_VIZIER_HARVARD_URL,
                    params=params, timeout=(8, 26)
                )
                response.raise_for_status()
                rows = parse_vizier_allwise_tsv(
                    response.content.decode("utf-8-sig", errors="replace")
                )
            return rows, limit
        except (requests.RequestException, RuntimeError) as error:
            errors.append(f"max {limit}: {type(error).__name__}: {str(error)[:180]}")
    raise RuntimeError(
        "El respaldo AllWISE de VizieR/Harvard no respondió: " +
        " | ".join(errors)
    )


def catalog_cache_path(catalog, coord, radius_arcmin):
    key = (
        f"catalog-v1|{catalog}|{coord.ra.deg:.8f}|"
        f"{coord.dec.deg:.8f}|{radius_arcmin:.4f}"
    )
    return CATALOG_CACHE_DIR / f"{make_hash(key)}.json"

def query_catalog_sources(coord, radius_arcmin, catalog):
    """Consulta Gaia DR3 o AllWISE y reutiliza resultados durante 30 minutos."""
    catalog = "allwise" if catalog in ("wise", "allwise") else catalog
    if catalog not in ("gaia", "allwise"):
        raise ValueError("El catálogo debe ser gaia o allwise.")
    if not 0.1 <= float(radius_arcmin) <= 30:
        raise ValueError("El radio del catálogo debe estar entre 0.1 y 30 arcmin.")

    cache_path = catalog_cache_path(catalog, coord, radius_arcmin)
    try:
        if cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age <= CATALOG_CACHE_TTL:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and isinstance(cached.get("sources"), list):
                    return (
                        cached["sources"],
                        cached.get("archive", ""),
                        cached.get("catalog_id", ""),
                        "cache"
                    )
    except (OSError, json.JSONDecodeError):
        pass

    radius_deg = float(radius_arcmin) / 60.0
    ra_deg = float(coord.ra.deg)
    dec_deg = float(coord.dec.deg)

    if catalog == "gaia":
        archive_name = "ESA Gaia Archive"
        catalog_id = "gaiadr3.gaia_source"
        adql = f"""
            SELECT TOP {CATALOG_MAX_SOURCES}
                source_id, ra, dec, parallax, pmra, pmdec,
                phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag,
                bp_rp, radial_velocity
            FROM gaiadr3.gaia_source
            WHERE CONTAINS(
                POINT('ICRS', ra, dec),
                CIRCLE('ICRS', {ra_deg:.10f}, {dec_deg:.10f}, {radius_deg:.10f})
            ) = 1
            ORDER BY phot_g_mean_mag ASC
        """
        # ESA sigue siendo el archivo principal. Si no responde, ARI consulta
        # exactamente el mismo release DR3; se identifica su procedencia.
        catalog_metadata_source = "esa-tap"
        try:
            rows = execute_tap_csv(
                GAIA_TAP_SYNC_URL, adql, archive_name, fast_failure=True
            )
        except (requests.RequestException, RuntimeError) as esa_error:
            try:
                rows, ari_limit = query_gaia_ari_lightweight(
                    ra_deg, dec_deg, radius_deg
                )
                archive_name = "ARI Heidelberg (Gaia DR3 de ESA/DPAC)"
                catalog_id = "gaiadr3.gaia_source_lite"
                catalog_metadata_source = f"ari-tap-fallback-light-{ari_limit}"
            except (requests.RequestException, RuntimeError) as ari_error:
                if cache_path.exists():
                    try:
                        old = json.loads(cache_path.read_text(encoding="utf-8"))
                        if isinstance(old, dict) and isinstance(old.get("sources"), list):
                            return (
                                old["sources"], old.get("archive", archive_name),
                                old.get("catalog_id", catalog_id), "stale-cache",
                            )
                    except (OSError, ValueError):
                        pass
                raise RuntimeError(
                    "Gaia DR3 no disponible desde ESA ni ARI Heidelberg. "
                    f"ESA: {esa_error} | ARI: {ari_error}"
                ) from ari_error
        sources = [{
            "source_id": row.get("source_id"),
            "ra": safe_float(row.get("ra")),
            "dec": safe_float(row.get("dec")),
            "parallax_mas": safe_float(row.get("parallax")),
            "pm_ra_mas_yr": safe_float(row.get("pmra")),
            "pm_dec_mas_yr": safe_float(row.get("pmdec")),
            "g_mag": safe_float(row.get("phot_g_mean_mag")),
            "bp_mag": safe_float(row.get("phot_bp_mean_mag")),
            "rp_mag": safe_float(row.get("phot_rp_mean_mag")),
            "bp_rp": safe_float(row.get("bp_rp")),
            "radial_velocity_km_s": safe_float(row.get("radial_velocity"))
        } for row in rows]
    else:
        archive_name = "NASA/IPAC Infrared Science Archive (IRSA)"
        catalog_id = "allwise_p3as_psd"
        adql = f"""
            SELECT TOP {CATALOG_MAX_SOURCES}
                designation, ra, dec,
                w1mpro, w1sigmpro, w2mpro, w2sigmpro,
                w3mpro, w3sigmpro, w4mpro, w4sigmpro, ph_qual
            FROM allwise_p3as_psd
            WHERE CONTAINS(
                POINT('ICRS', ra, dec),
                CIRCLE('ICRS', {ra_deg:.10f}, {dec_deg:.10f}, {radius_deg:.10f})
            ) = 1
        """
        catalog_metadata_source = "irsa-tap"
        try:
            rows = execute_tap_csv(
                IRSA_TAP_SYNC_URL, adql, archive_name, fast_failure=True
            )
            sources = [{
                "designation": row.get("designation"),
                "ra": safe_float(row.get("ra")),
                "dec": safe_float(row.get("dec")),
                "w1_mag": safe_float(row.get("w1mpro")),
                "w1_error": safe_float(row.get("w1sigmpro")),
                "w2_mag": safe_float(row.get("w2mpro")),
                "w2_error": safe_float(row.get("w2sigmpro")),
                "w3_mag": safe_float(row.get("w3mpro")),
                "w4_mag": safe_float(row.get("w4mpro")),
                "photometric_quality": row.get("ph_qual")
            } for row in rows]
        except (requests.RequestException, RuntimeError) as irsa_error:
            try:
                rows, limit_used = query_allwise_vizier_harvard(
                    ra_deg, dec_deg, radius_arcmin
                )
                sources = [{
                    "designation": row.get("allwise") or None,
                    "ra": safe_float(row.get("raj2000")),
                    "dec": safe_float(row.get("dej2000")),
                    "w1_mag": safe_float(row.get("w1mag")),
                    "w1_error": None,
                    "w2_mag": safe_float(row.get("w2mag")),
                    "w2_error": None,
                    "w3_mag": None,
                    "w4_mag": None,
                    "photometric_quality": None
                } for row in rows]
                archive_name = "VizieR Harvard (AllWISE, CDS)"
                catalog_id = ALLWISE_VIZIER_CATALOG_ID
                catalog_metadata_source = f"vizier-harvard-asu-tsv-{limit_used}"
            except (requests.RequestException, RuntimeError) as vizier_error:
                if cache_path.exists():
                    try:
                        old = json.loads(cache_path.read_text(encoding="utf-8"))
                        if isinstance(old, dict) and isinstance(old.get("sources"), list):
                            return (old["sources"], old.get("archive", archive_name),
                                    old.get("catalog_id", catalog_id), "stale-cache")
                    except (OSError, ValueError):
                        pass
                raise RuntimeError(
                    "AllWISE no disponible desde IRSA ni VizieR Harvard. "
                    f"IRSA: {irsa_error} | VizieR: {vizier_error}"
                ) from vizier_error

    payload = {"archive": archive_name, "catalog_id": catalog_id, "sources": sources}
    try:
        temporary = cache_path.with_name(f"{cache_path.stem}.{time.time_ns()}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        atomic_replace(temporary, cache_path)
    except OSError:
        pass

    return sources, archive_name, catalog_id, catalog_metadata_source

def draw_catalog_overlay(image, sources, wcs, catalog, epoch_mjd=None):
    """Proyecta coordenadas ICRS sobre píxeles mediante la solución WCS del FITS."""
    if wcs is None or not getattr(wcs, "has_celestial", False):
        raise RuntimeError("La imagen no contiene una solución WCS celeste válida.")

    output = image.convert("RGB")
    draw = ImageDraw.Draw(output)
    width, height = output.size
    valid_sources = [
        source for source in sources
        if source.get("ra") is not None and source.get("dec") is not None
    ][:350]

    visible = 0
    color = (95, 224, 255) if catalog == "gaia" else (255, 190, 95)
    if valid_sources:
        ra_values = np.asarray([source["ra"] for source in valid_sources], dtype=float)
        dec_values = np.asarray([source["dec"] for source in valid_sources], dtype=float)
        if catalog == "gaia" and epoch_mjd is not None:
            # Gaia DR3 posiciones a época 2016.0: PMRA incluye cos(dec).
            years = float(Time(epoch_mjd, format="mjd").jyear - 2016.0)
            if np.isfinite(years):
                for i, entry in enumerate(valid_sources):
                    pmra = entry.get("pm_ra_mas_yr")
                    pmdec = entry.get("pm_dec_mas_yr")
                    if pmra is not None and pmdec is not None:
                        cosine = np.cos(np.deg2rad(dec_values[i]))
                        if abs(cosine) > 1e-8:
                            ra_values[i] += years * pmra / (3600000.0*cosine)
                            dec_values[i] += years * pmdec / 3600000.0
        try:
            x_values, y_values = wcs.world_to_pixel_values(ra_values, dec_values)
        except Exception as error:
            raise RuntimeError(f"No se pudieron proyectar las fuentes sobre la imagen: {error}")

        for x, y in zip(np.asarray(x_values), np.asarray(y_values)):
            if not np.isfinite(x) or not np.isfinite(y):
                continue
            if x < -5 or y < -5 or x > width + 5 or y > height + 5:
                continue
            radius = 3
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline=color, width=1)
            visible += 1

    label = "Gaia DR3" if catalog == "gaia" else "AllWISE"
    legend = f"{label} | {visible} fuentes en campo"
    font = ImageFont.load_default()
    try:
        bounds = draw.textbbox((0, 0), legend, font=font)
        text_width = bounds[2] - bounds[0]
        text_height = bounds[3] - bounds[1]
    except AttributeError:
        text_width, text_height = draw.textsize(legend, font=font)
    box_width = min(width - 8, text_width + 18)
    box_height = text_height + 12
    draw.rectangle((5, 5, 5 + box_width, 5 + box_height), fill=(4, 10, 20))
    draw.text((13, 10), legend, fill=color, font=font)
    return output, visible

def _unwise_cutout_reference(coord, radius_deg, band):
    """Referencia interna sin URL arbitraria; nunca se trata como imagen L1b."""
    if band not in (1, 2):
        raise ValueError("unWISE neo1 solo admite bandas W1 y W2.")
    if not (0 < radius_deg <= UNWISE_MAX_RADIUS_DEG):
        raise ValueError(
            f"El radio unWISE debe ser mayor que cero y no superar "
            f"{UNWISE_MAX_RADIUS_DEG} grados para un recorte de 1024 píxeles."
        )
    if not (0 <= coord.ra.deg < 360 and -90 <= coord.dec.deg <= 90):
        raise ValueError("Coordenadas unWISE fuera de rango.")
    import math
    n = max(UNWISE_MIN_SIZE, int(math.ceil(
        2.0 * radius_deg * 3600.0 / UNWISE_PIXEL_SCALE_ARCSEC
    )))
    if n > UNWISE_MAX_SIZE:
        raise ValueError("Región demasiado extensa para un recorte unWISE.")
    return ("unwise://cutout?" + urlencode({
        "version": UNWISE_VERSION,
        "ra": f"{coord.ra.deg:.9f}",
        "dec": f"{coord.dec.deg:.9f}",
        "size": n,
        "bands": band
    }))


def _unwise_parameters(cutout_reference):
    """Acepta solo referencias locales del servicio unWISE y parámetros seguros."""
    parsed = urlsplit(cutout_reference)
    if (parsed.scheme != "unwise" or parsed.netloc != "cutout"
            or parsed.path not in ("", "/") or parsed.fragment):
        raise ValueError("Referencia de recorte unWISE no autorizada.")
    raw = parse_qs(parsed.query, keep_blank_values=True)
    expected = {"version", "ra", "dec", "size", "bands"}
    if set(raw) != expected or any(len(values) != 1 for values in raw.values()):
        raise ValueError("Parámetros unWISE incompletos o duplicados.")
    version = raw["version"][0]
    ra = float(raw["ra"][0]); dec = float(raw["dec"][0])
    size = int(raw["size"][0]); band = int(raw["bands"][0])
    if (version != UNWISE_VERSION or band not in (1, 2)
            or size < UNWISE_MIN_SIZE or size > UNWISE_MAX_SIZE
            or not np.isfinite(ra) or not np.isfinite(dec)
            or not (0 <= ra < 360 and -90 <= dec <= 90)):
        raise ValueError("Parámetros de recorte unWISE fuera de rango.")
    return {"version": version, "ra": ra, "dec": dec,
            "size": size, "bands": band}


def _unwise_valid_image(raw, ra, dec):
    """Valida cabecera, dimensión, píxeles y que el centro pertenezca al WCS."""
    import io
    from astropy.io import fits
    from astropy.wcs import WCS
    if len(raw) < 2880 or not raw[:80].startswith(b"SIMPLE  ="):
        return False
    try:
        with fits.open(io.BytesIO(raw), memmap=False) as hdul:
            hdu = next((h for h in hdul if getattr(h, "data", None) is not None
                        and getattr(h.data, "ndim", 0) == 2), None)
            if hdu is None:
                return False
            wcs = WCS(hdu.header).celestial
            if not wcs.has_celestial:
                return False
            x, y = wcs.world_to_pixel_values(ra, dec)
            x = float(np.asarray(x).item())
            y = float(np.asarray(y).item())
            height, width = hdu.data.shape
            return (np.isfinite(x) and np.isfinite(y)
                    and 0 <= x < width and 0 <= y < height
                    and bool(np.isfinite(hdu.data).any()))
    except Exception:
        # Archivos malformados o WCS no interpretable: probar otro miembro.
        return False


def _unwise_fetch_fits(cutout_reference):
    """Descarga un TAR.GZ acotado, extrae solo la imagen FITS y guarda caché.

    Nunca extrae rutas del TAR a disco (evita path traversal). Elige únicamente
    un miembro de intensidad W1/W2 cuyo WCS contenga las coordenadas pedidas.
    """
    import tarfile
    from threading import Lock
    params = _unwise_parameters(cutout_reference)
    cache_key = make_hash(f"unwise-v11|{cutout_reference}")
    cache_path = UNWISE_CACHE_DIR / f"{cache_key}.fits"
    # El mismo FITS se comparte entre la API de inventario, PNG y descarga.
    if cache_path.is_file() and 2880 <= cache_path.stat().st_size <= UNWISE_MAX_FITS_BYTES:
        with cache_path.open("rb") as saved:
            existing = saved.read()
        if _unwise_valid_image(existing, params["ra"], params["dec"]):
            return cache_path, True
    # Las consultas idénticas se serializan para evitar descargas simultáneas.
    try:
        from .spherex_data import get_cache_lock
        lock = get_cache_lock("unwise-v11|" + cache_key)
    except ImportError:
        lock = Lock()
    with lock:
        if cache_path.is_file() and 2880 <= cache_path.stat().st_size <= UNWISE_MAX_FITS_BYTES:
            with cache_path.open("rb") as saved:
                existing = saved.read()
            if _unwise_valid_image(existing, params["ra"], params["dec"]):
                return cache_path, True
        tar_path = UNWISE_CACHE_DIR / f"{cache_key}.{time.time_ns()}.tar.gz"
        tmp_fits = UNWISE_CACHE_DIR / f"{cache_key}.{time.time_ns()}.tmp"
        try:
            # Solicitamos solo la imagen, no varianza/cobertura, para minimizar I/O.
            query = dict(params)
            query["file_img_m"] = "on"
            total = 0
            with requests.Session() as session:
                with session.get(UNWISE_URL, params=query, stream=True,
                                 timeout=(12, 90), allow_redirects=True) as response:
                    if urlsplit(response.url).hostname not in ("unwise.me", "www.unwise.me"):
                        raise RuntimeError("Redirección unWISE a un host no permitido.")
                    response.raise_for_status()
                    expected_length = int(response.headers.get("Content-Length", "0") or 0)
                    if expected_length > UNWISE_MAX_TAR_BYTES:
                        raise RuntimeError("Archivo unWISE demasiado grande.")
                    if int(response.status_code) != 200:
                        raise RuntimeError("Servicio unWISE devolvió estado inesperado.")
                    with tar_path.open("wb") as target:
                        for chunk in response.iter_content(chunk_size=256 * 1024):
                            if chunk:
                                total += len(chunk)
                                if total > UNWISE_MAX_TAR_BYTES:
                                    raise RuntimeError("Respuesta unWISE supera el límite seguro.")
                                target.write(chunk)
            if total == 0:
                raise RuntimeError("El servicio unWISE devolvió una respuesta vacía.")
            found_image = None
            with tarfile.open(tar_path, mode="r:gz") as archive:
                for member in archive:
                    # Nunca construir una ruta local a partir del nombre del TAR.
                    if not member.isfile() or "/" in member.name or "\\" in member.name:
                        continue
                    if not re.fullmatch(rf"unwise-[0-9A-Za-z]+-w{params['bands']}-img-m\.fits",
                                        member.name):
                        continue
                    if member.size < 2880 or member.size > UNWISE_MAX_FITS_BYTES:
                        continue
                    stream = archive.extractfile(member)
                    if stream is None:
                        continue
                    content = stream.read(UNWISE_MAX_FITS_BYTES + 1)
                    if len(content) != member.size:
                        continue
                    if _unwise_valid_image(content, params["ra"], params["dec"]):
                        found_image = content
                        break
            if found_image is None:
                raise RuntimeError("unWISE no devolvió un FITS de intensidad válido para el campo solicitado.")
            tmp_fits.write_bytes(found_image)
            atomic_replace(tmp_fits, cache_path)
            return cache_path, False
        except (tarfile.TarError, OSError) as exc:
            raise RuntimeError(f"El archivo unWISE no pudo procesarse: {exc}") from exc
        finally:
            tar_path.unlink(missing_ok=True)
            tmp_fits.unlink(missing_ok=True)


def _query_unwise_images(coord, radius_deg, band):
    """El recorte es un coadd (sin fecha de exposición individual)."""
    reference = _unwise_cutout_reference(coord, radius_deg, band)
    _, from_cache = _unwise_fetch_fits(reference)  # valida antes de anunciar éxito
    item = {
        "dataset": "unWISE neo1 · imagen combinada",
        "band": band,
        "observation_date": "Coadd multiepoca; sin fecha individual",
        "mjd_obs": None,
        "product_type": "coadd",
        "coadd_version": UNWISE_VERSION,
        "image_url": reference,
        "cutout_url": reference,
        "source": "unwise-cutout-fits",
    }
    return [item], "unwise-cache" if from_cache else "unwise-cutout-service"


def wise_metadata_cache_path(
    dataset,
    coord,
    radius_deg,
    band,
    max_results
):
    cache_key = (
        f"{WISE_API_VERSION}|{dataset}|{coord.ra.deg:.9f}|"
        f"{coord.dec.deg:.9f}|{radius_deg:.9f}|"
        f"{band}|{max_results}"
    )
    return WISE_METADATA_CACHE_DIR / f"{make_hash(cache_key)}.json"

def wise_cutout_url(image_url, coord, radius_deg):
    """Construye un recorte angular directamente en el servicio IBE oficial."""
    params = {
        "center": f"{coord.ra.deg:.9f},{coord.dec.deg:.9f}",
        "size": f"{2.0 * radius_deg:.8f}deg",
        "gzip": "false"
    }
    return f"{image_url}?{urlencode(params)}"

def _wise_metadata_get(url, params, timeout=(8, 28)):
    """Consulta WISE sin reintentos ocultos de red.

    Mantiene HTTPS y la configuración de proxy del usuario, pero evita que
    cada intento se multiplique por los reintentos generales del backend.
    """
    with requests.Session() as session:
        session.headers.update({"User-Agent": "SPHEREx-Explorer/1.1 (WISE acquisition)"})
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response

def query_ibe_inventory(endpoint, search_params):
    """Consulta IRSA IBE con rutas alternativas oficiales y errores trazables.

    Se prueban menos columnas si el archivo rechaza las opcionales; el
    primer servidor que responde con datos válidos determina las URLs FITS.
    """
    marker = "/ibe/search/"
    if marker not in endpoint:
        raise ValueError("Ruta IBE de metadatos no válida")
    path = endpoint.split(marker, 1)[1]
    errors = []
    columns_full = str(search_params.get("columns", ""))
    essentials = ("coadd_id,band" if "p3am_cdd" in path
                  else "scan_id,frame_num,band")
    column_variants = list(dict.fromkeys([columns_full, essentials]))
    for host in IRSA_IBE_HOSTS:
        url = f"{host}{marker}{path}"
        for columns in column_variants:
            params = dict(search_params)
            params["columns"] = columns
            try:
                response = _wise_metadata_get(url, params=params, timeout=(8, 28))
                response.raise_for_status()
                rows = parse_csv_response(response, f"IRSA IBE ({host})")
                return rows, host
            except (requests.RequestException, RuntimeError, ValueError) as error:
                errors.append(f"{host} [{columns}]: {type(error).__name__}: {str(error)[:180]}")
                # Cambiar la lista de columnas solo tiene sentido ante un
                # error de validación (HTTP 400), no ante fallos 502 o de red.
                if isinstance(error, requests.HTTPError):
                    status = getattr(getattr(error, "response", None), "status_code", None)
                    if status != 400:
                        break
                elif isinstance(error, requests.RequestException):
                    break
    summary = " | ".join(errors[-6:])
    raise RuntimeError(
        "No se logró consultar IRSA IBE en sus servidores oficiales. "
        f"Detalles: {summary}"
    )

def wise_aws_url_from_ibe(image_url):
    """Mapea exclusivamente FITS WISE oficiales IBE a la ruta S3 publicada por IRSA."""
    parts = urlsplit(image_url)
    if parts.scheme != "https" or f"https://{parts.netloc}" not in IRSA_IBE_HOSTS:
        raise ValueError("La URL FITS no pertenece a un host IRSA permitido")
    expression = (r"^/ibe/data/wise/"
                  r"(allwise/p3am_cdd|neowiser/p1bm_frm)/"
                  r"([A-Za-z0-9_+./-]+\.fits)$")
    match = re.fullmatch(expression, parts.path, flags=re.IGNORECASE)
    if match is None or ".." in parts.path.split("/"):
        raise ValueError("La ruta FITS WISE no es una imagen de intensidad compatible")
    collection, suffix = match.groups()
    dataset, product_id = collection.split("/")
    return f"{WISE_AWS_BASE}/wise/{dataset}/images/{product_id}/{suffix}"


def _wise_download_aws_file(aws_url):
    """Descarga de forma limitada y conserva el FITS S3 para reutilizarlo."""
    if not aws_url.startswith(WISE_AWS_BASE + "/wise/"):
        raise ValueError("URL S3 no autorizada")
    path = WISE_FULL_FITS_CACHE_DIR / f"{make_hash(aws_url)}.fits"
    if path.is_file() and 0 < path.stat().st_size <= WISE_FITS_MAX_BYTES:
        return path
    temporary = path.with_name(f"{path.stem}-{time.time_ns()}.tmp")
    size = 0
    try:
        with requests.Session() as session:
            with session.get(aws_url, stream=True, timeout=(10, 75)) as response:
                response.raise_for_status()
                expected = int(response.headers.get("Content-Length", "0") or 0)
                if expected > WISE_FITS_MAX_BYTES:
                    raise RuntimeError("FITS original demasiado grande para el respaldo S3")
                with temporary.open("wb") as target:
                    for chunk in response.iter_content(chunk_size=1024*1024):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > WISE_FITS_MAX_BYTES:
                            raise RuntimeError("FITS S3 supera el límite local de tamaño")
                        target.write(chunk)
        if size < 2880:
            raise RuntimeError("La descarga S3 no contiene un FITS completo")
        with temporary.open("rb") as check:
            if not check.read(80).startswith(b"SIMPLE"):
                raise RuntimeError("La respuesta S3 no parece ser un archivo FITS")
        atomic_replace(temporary, path)
        return path
    finally:
        temporary.unlink(missing_ok=True)


def _wise_local_fits_path(image_url):
    """Permite leer solo nombres simples existentes dentro de local_fits."""
    parts = urlsplit(image_url)
    if (parts.scheme != "local-wise" or parts.netloc != "fits"
            or not parts.path.startswith("/")):
        raise ValueError("Referencia local WISE no válida")
    pieces = unquote(parts.path.lstrip("/")).split("/")
    if (len(pieces) != 2 or pieces[0] not in ("allwise", "neowiser")
            or not pieces[1] or pieces[1] != Path(pieces[1]).name
            or not pieces[1].lower().endswith(".fits")):
        raise ValueError("Ruta FITS local no permitida")
    candidate = (WISE_LOCAL_FITS_DIR / pieces[0] / pieces[1]).resolve()
    if candidate.parent != (WISE_LOCAL_FITS_DIR / pieces[0]).resolve() or not candidate.is_file():
        raise ValueError("No se encontró el archivo FITS local")
    return candidate


def _wise_cutout_from_full_fits(path, cutout_url):
    """Recorta con WCS en memoria, conserva cabecera y devuelve FITS válido.

    El servidor Flask existente espera bytes de FITS, sin saber si vienen de
    IBE, S3 o una copia local. Nunca devuelve el archivo completo como recorte.
    """
    import io
    from astropy.io import fits
    from astropy.coordinates import SkyCoord
    from astropy.wcs import WCS
    from astropy.nddata import Cutout2D
    import astropy.units as u

    params = parse_qs(urlsplit(cutout_url).query)
    center = str(params.get("center", [""])[0]).split(",")
    width_text = str(params.get("size", [""])[0]).strip().lower()
    if len(center) != 2 or not width_text.endswith("deg"):
        raise ValueError("El recorte WISE exige center=RA,Dec y size en grados")
    ra, dec = float(center[0]), float(center[1])
    width = float(width_text[:-3])
    if not (0 <= ra < 360 and -90 <= dec <= 90 and 0 < width <= 10):
        raise ValueError("Coordenadas o tamaño del recorte fuera de rango")

    with fits.open(path, memmap=True) as hdul:
        image_hdu = next((h for h in hdul if getattr(h, "data", None) is not None
                          and getattr(h.data, "ndim", 0) == 2), None)
        if image_hdu is None:
            raise RuntimeError("El FITS no tiene imagen bidimensional")
        wcs = WCS(image_hdu.header).celestial
        if not wcs.has_celestial:
            raise RuntimeError("El FITS no contiene WCS celeste")
        cutout = Cutout2D(np.asarray(image_hdu.data, dtype=np.float32),
                          position=SkyCoord(ra, dec, unit="deg", frame="icrs"),
                          size=(width*u.deg, width*u.deg), wcs=wcs,
                          mode="partial", fill_value=np.nan, copy=True)
        header = image_hdu.header.copy()
        header.update(cutout.wcs.to_header())
        output = io.BytesIO()
        fits.PrimaryHDU(data=np.asarray(cutout.data, dtype=np.float32),
                        header=header).writeto(output)
        return output.getvalue()


def wise_request_with_host_fallback(cutout_url):
    """IBE -> AWS S3 (FITS íntegro + recorte WCS) o FITS local seguro."""
    parts = urlsplit(cutout_url)
    if parts.scheme == "unwise":
        path, _ = _unwise_fetch_fits(cutout_url)
        return path.read_bytes()
    if parts.scheme == "local-wise":
        return _wise_cutout_from_full_fits(_wise_local_fits_path(cutout_url), cutout_url)
    if parts.scheme != "https" or f"https://{parts.netloc}" not in IRSA_IBE_HOSTS:
        raise ValueError("Origen del FITS fuera de IRSA/local-wise")
    ordered = [f"https://{parts.netloc}"] + [
        host for host in IRSA_IBE_HOSTS if host != f"https://{parts.netloc}"]
    problems = []
    for host in ordered:
        h = urlsplit(host)
        alternative = urlunsplit((h.scheme, h.netloc, parts.path, parts.query, ""))
        try:
            response = get_http_session().get(alternative, timeout=(8, 30))
            response.raise_for_status()
            if not response.content[:80].startswith(b"SIMPLE"):
                raise RuntimeError("IBE devolvió un documento en vez de FITS")
            return response.content
        except (requests.RequestException, RuntimeError) as error:
            problems.append(f"{h.netloc}: {type(error).__name__}: {str(error)[:120]}")

    # El archivo debe estar identificado por metadatos reales; no se adivina
    # qué exposición cubre una coordenada a partir de su RA/Dec.
    try:
        aws_url = wise_aws_url_from_ibe(cutout_url)
        original = _wise_download_aws_file(aws_url)
        return _wise_cutout_from_full_fits(original, cutout_url)
    except Exception as error:
        problems.append(f"AWS S3: {type(error).__name__}: {str(error)[:180]}")
    raise RuntimeError("Fallo al obtener FITS WISE desde IBE y S3: " + " | ".join(problems))


def _wise_find_local_frames(coord, radius_deg, dataset, band, max_results):
    """Descubre solo imágenes FITS locales cuya WCS cubra la posición."""
    from astropy.io import fits
    from astropy.wcs import WCS
    pattern = (r"[0-9A-Za-z_+.-]+-w([1-4])-int-(1b|3)\.fits")
    output = []
    for path in sorted((WISE_LOCAL_FITS_DIR / dataset).glob("*.fits"))[:2000]:
        match = re.fullmatch(pattern, path.name, flags=re.IGNORECASE)
        if match is None or int(match.group(1)) != band:
            continue
        kind = "neowiser" if match.group(2).lower() == "1b" else "allwise"
        if kind != dataset:
            continue
        try:
            with fits.open(path, memmap=True) as hdul:
                hdu = next((h for h in hdul if getattr(h, "data", None) is not None
                            and getattr(h.data, "ndim", 0) == 2), None)
                if hdu is None:
                    continue
                shape = hdu.data.shape
                wcs = WCS(hdu.header).celestial
                if not wcs.has_celestial:
                    continue
                x, y = wcs.world_to_pixel_values(float(coord.ra.deg), float(coord.dec.deg))
                if not (np.isfinite(x) and np.isfinite(y)
                        and 0 <= x < shape[1] and 0 <= y < shape[0]):
                    continue
                header = hdu.header
                mjd = safe_float(header.get("MJD-OBS") or header.get("MJDOBS")
                                 or header.get("MJD_OBS") or header.get("MID-OBS")
                                 or header.get("MJDMEAN"))
                date = format_mjd(mjd) if mjd is not None else str(header.get("DATE-OBS") or "Fecha no disponible")
            image_url = f"local-wise://fits/{dataset}/{quote(path.name)}"
            record = {"dataset": "NEOWISE-R L1b" if dataset == "neowiser" else "AllWISE Atlas",
                      "band": band, "image_url": image_url,
                      "cutout_url": wise_cutout_url(image_url, coord, radius_deg),
                      "observation_date": date, "mjd_obs": mjd,
                      "quality": None, "source": "local-fits",
                      "obs_id": path.name}
            if kind == "neowiser":
                m = re.match(r"^(.+?)([0-9]{3})-w[12]-int-1b\.fits$", path.name, re.I)
                if m:
                    record["scan_id"], record["frame_num"] = m.group(1), int(m.group(2))
            else:
                record["coadd_id"] = path.name.split("-w")[0]
            output.append(record)
        except (OSError, RuntimeError, ValueError, TypeError):
            continue
    output.sort(key=lambda r: (r.get("mjd_obs") is None,
                  r.get("mjd_obs") if r.get("mjd_obs") is not None else float("inf"),
                  r["obs_id"]))
    if len(output) > max_results:
        idx = np.linspace(0, len(output)-1, max_results, dtype=int)
        output = [output[int(i)] for i in idx]
    return output


def _wise_stale_cache_any_max_results(coord, radius_deg, dataset, band, max_results):
    """Recupera inventarios previos aunque se haya cambiado max_results.

    Solo se reutilizan coincidencias EXACTAS de centro, radio, banda y dataset.
    La caché antigua puede estar incompleta, por eso se identifica como parcial.
    """
    for path in sorted(WISE_METADATA_CACHE_DIR.glob("*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:200]:
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(rows, list) or not rows:
                continue
            first = rows[0]
            if not isinstance(first, dict):
                continue
            cutout = str(first.get("cutout_url") or "")
            part = urlsplit(cutout)
            params = parse_qs(part.query)
            center = str(params.get("center", [""])[0]).split(",")
            angular = str(params.get("size", [""])[0])
            if (len(center) != 2 or abs(float(center[0])-coord.ra.deg) > 1e-6
                    or abs(float(center[1])-coord.dec.deg) > 1e-6
                    or abs(float(angular.removesuffix("deg"))-2*radius_deg) > 1e-6):
                continue
            match = [dict(r) for r in rows
                     if (isinstance(r, dict) and int(r.get("band", -1)) == band
                         and ("/wise/neowiser/" in str(r.get("image_url", ""))) == (dataset == "neowiser")
                         and ("/wise/allwise/" in str(r.get("image_url", ""))) == (dataset == "allwise"))]
            if match:
                if len(match) > max_results:
                    ids = np.linspace(0,len(match)-1,max_results,dtype=int)
                    match = [match[int(i)] for i in ids]
                return match
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return []

def _spectrum_wise_band_range(band):
    """Selección aproximada para limitar resultados SIA2; banda exacta se verifica con la URL."""
    return {1: "2.8e-6 4.0e-6", 2: "4.1e-6 5.3e-6",
            3: "7.0e-6 17.0e-6", 4: "18.0e-6 28.0e-6"}[band]

def _extract_wise_sia_records(rows, dataset, band, coord, radius_deg):
    """Filtra imagen científica de intensidad (no máscara/uncertainty/tabla).

    Conserva solamente URLs oficiales IBE a las que se puede pedir un recorte.
    Nunca confunde imágenes WISE acumuladas con exposiciones NEOWISE L1b.
    """
    expected_marker = "-w%d-int-" % band
    expected_dataset = "/ibe/data/wise/%s/" % dataset
    records = []
    seen = set()
    for row in rows:
        raw_url = str(row.get("access_url") or "").strip()
        parts = urlsplit(raw_url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if (parts.scheme != "https" or origin not in IRSA_IBE_HOSTS
                or expected_dataset not in parts.path.lower()
                or expected_marker not in parts.path.lower()
                or not parts.path.lower().endswith(".fits")
                or raw_url in seen):
            continue
        seen.add(raw_url)
        basename = Path(parts.path).name
        raw_time = safe_float(row.get("t_min"))
        rec = {
            "dataset": "NEOWISE-R L1b" if dataset == "neowiser" else "AllWISE Atlas",
            "band": int(band),
            "observation_date": format_mjd(raw_time) if raw_time is not None else "Fecha no disponible",
            "mjd_obs": raw_time,
            "image_url": raw_url,
            "cutout_url": wise_cutout_url(raw_url, coord, radius_deg),
            "obs_id": row.get("obs_id") or "",
            "quality": None,
            "source": "irsa-sia2"
        }
        if dataset == "neowiser":
            match = re.match(r"^(.+?)([0-9]{3})-w[1-2]-int-1b\.fits$", basename, re.I)
            if match:
                rec["scan_id"] = match.group(1)
                rec["frame_num"] = int(match.group(2))
        else:
            match = re.match(r"^(.+)-w[1-4]-int-3\.fits$", basename, re.I)
            if match:
                rec["coadd_id"] = match.group(1)
        records.append(rec)
    records.sort(key=lambda item: (item.get("mjd_obs") is None,
                     item.get("mjd_obs") if item.get("mjd_obs") is not None else float("inf"),
                     item["image_url"]))
    return records

def query_wise_via_sia2(coord, radius_deg, dataset, band, max_results):
    """Descubre FITS oficiales vía SIA v2, con consulta ligera para NEOWISE.

    NEOWISE-R contiene muchas exposiciones. Se limita el inventario inicial
    para no sobrecargar la respuesta; si no responde, se intenta CLOSEST,
    que devuelve la exposición más próxima (no una muestra temporal).
    """
    collection = "neowiser" if dataset == "neowiser" else "wise_allwise"
    params = {
        "COLLECTION": collection,
        "POS": f"CIRCLE {coord.ra.deg:.9f} {coord.dec.deg:.9f} {radius_deg:.9f}",
        "BAND": _spectrum_wise_band_range(band),
        "DPTYPE": "image",
        "RESPONSEFORMAT": "CSV",
        "MAXREC": min(120, WISE_SIA_MAXREC) if dataset == "neowiser" else WISE_SIA_MAXREC
    }
    errors = []
    for host in IRSA_IBE_HOSTS[:2]:
        endpoint = f"{host}/SIA"
        modes = ("limited", "closest") if dataset == "neowiser" else ("limited",)
        for mode in modes:
            request_params = dict(params)
            if mode == "closest":
                # IRSA SIA v2: CLOSEST admite COLLECTION si POS=CIRCLE.
                request_params["CLOSEST"] = "COLLECTION"
                request_params["MAXREC"] = 20
            try:
                response = _wise_metadata_get(endpoint, params=request_params, timeout=(8, 28))
                rows = parse_csv_response(response, f"IRSA SIA v2 ({host})")
                records = _extract_wise_sia_records(rows, dataset, band, coord, radius_deg)
                if records:
                    if len(records) > max_results:
                        ix = np.linspace(0, len(records) - 1, max_results, dtype=int)
                        records = [records[i] for i in ix]
                    source = "irsa_sia2:" + host
                    if mode == "closest":
                        source += ":closest-only"
                    return records, source
                errors.append(f"{host} ({mode}): sin imágenes W{band} en {len(rows)} registros")
            except (requests.RequestException, RuntimeError, ValueError) as error:
                errors.append(f"{host} ({mode}): {type(error).__name__}: {str(error)[:200]}")
                # Si incluso un intermediario rechaza la consulta, probar el
                # modo liviano antes de pasar al host alternativo.
    raise RuntimeError("SIA v2 no devolvió imágenes consultables. " + " | ".join(errors[-6:]))

def query_wise_images(
    coord,
    radius_deg,
    dataset,
    band,
    max_results
):
    """
    Consulta inventarios de imágenes del IRSA Image Back End (IBE).

    dataset='neowiser': exposiciones individuales NEOWISE-R L1b.
    dataset='allwise': atlas coadds AllWISE.
    dataset='unwise': coadd unWISE neo1 W1/W2 obtenido directamente por RA/Dec.
    """
    if dataset == "unwise":
        return _query_unwise_images(coord, radius_deg, band)
    if dataset == "neowiser":
        endpoint = (
            f"{IRSA_IBE_SEARCH_BASE}/wise/neowiser/p1bm_frm"
        )
        columns = "scan_id,frame_num,band,date_obs,mjd_obs,qual_frame"
    elif dataset == "allwise":
        endpoint = (
            f"{IRSA_IBE_SEARCH_BASE}/wise/allwise/p3am_cdd"
        )
        columns = "coadd_id,band,mid_obs"
    else:
        raise ValueError("dataset debe ser neowiser o allwise.")

    if dataset == "neowiser" and band not in (1, 2):
        raise ValueError("NEOWISE-R solo dispone de bandas W1 y W2.")
    if dataset == "allwise" and band not in (1, 2, 3, 4):
        raise ValueError("AllWISE admite las bandas W1, W2, W3 y W4.")

    cache_path = wise_metadata_cache_path(
        dataset,
        coord,
        radius_deg,
        band,
        max_results
    )

    try:
        if cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age <= WISE_METADATA_CACHE_TTL:
                cached = json.loads(
                    cache_path.read_text(encoding="utf-8")
                )
                if isinstance(cached, list):
                    return cached, "cache"
    except (OSError, json.JSONDecodeError):
        pass

    # Los FITS oficiales importados voluntariamente funcionan sin APIs de red.
    local_frames = _wise_find_local_frames(coord, radius_deg, dataset, band, max_results)
    if local_frames:
        return local_frames, "local-fits-offline"

    # Preferir SIA v2, recomendado por IRSA para nuevas búsquedas. IBE
    # continúa como respaldo, sin multiplicar tiempos con reintentos ocultos.
    sia_error = None
    try:
        sia_records, sia_source = query_wise_via_sia2(
            coord, radius_deg, dataset, band, max_results
        )
        if sia_records:
            save_json_atomic(sia_records, cache_path)
            return sia_records, sia_source
    except (RuntimeError, requests.RequestException, ValueError) as error:
        sia_error = error

    # IRSA IBE SIZE define el ancho y alto angular de la región cuadrada.
    diameter_deg = 2.0 * radius_deg

    try:
        rows, responding_host = query_ibe_inventory(
            endpoint,
            {
                "POS": f"{coord.ra.deg:.9f},{coord.dec.deg:.9f}",
                "SIZE": f"{diameter_deg:.8f}",
                "INTERSECT": "OVERLAPS",
                "where": f"band={band}",
                "columns": columns,
                "ct": "CSV"
            }
        )
    except RuntimeError as ibe_error:
        # La caché anterior se informa explícitamente como desactualizada.
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(cached, list) and cached:
                    return cached, "stale-cache-offline"
            except (OSError, ValueError):
                pass
        # Si cambió max_results, aún puede existir un inventario oficial
        # previo para exactamente las mismas coordenadas y apertura angular.
        historical = _wise_stale_cache_any_max_results(
            coord, radius_deg, dataset, band, max_results)
        if historical:
            return historical, "stale-cache-misma-region"
        raise RuntimeError(
            "La consulta oficial WISE/NEOWISE no respondió. "
            f"SIA v2: {sia_error}; IBE: {ibe_error}. "
            "Comprueba DNS, HTTPS/443, proxy y VPN en la computadora."
        ) from ibe_error
    records = []

    for row in rows:
        try:
            if dataset == "neowiser":
                scan_id = str(row.get("scan_id") or "").strip()
                frame_num = int(float(row.get("frame_num")))
                row_band = int(float(row.get("band")))

                if len(scan_id) < 2:
                    continue

                scangrp = scan_id[-2:]
                filename = (
                    f"{scan_id}{frame_num:03d}-w{row_band}-int-1b.fits"
                )
                relative_path = (
                    f"wise/neowiser/p1bm_frm/{scangrp}/"
                    f"{scan_id}/{frame_num:03d}/{filename}"
                )

                image_url = (
                    f"{responding_host}/ibe/data/{relative_path}"
                )

                observation_date = (
                    row.get("date_obs")
                    or row.get("mjd_obs")
                    or ""
                )
                mjd = safe_float(row.get("mjd_obs"))

                record = {
                    "dataset": "NEOWISE-R L1b",
                    "scan_id": scan_id,
                    "frame_num": frame_num,
                    "band": row_band,
                    "observation_date": observation_date,
                    "mjd_obs": mjd,
                    "quality": row.get("qual_frame"),
                    "image_url": image_url
                }

            else:
                coadd_id = str(row.get("coadd_id") or "").strip()
                row_band = int(float(row.get("band")))

                if len(coadd_id) < 4:
                    continue

                coadd_group = coadd_id[:2]
                coadd_ra = coadd_id[:4]
                filename = f"{coadd_id}-w{row_band}-int-3.fits"

                relative_path = (
                    f"wise/allwise/p3am_cdd/{coadd_group}/"
                    f"{coadd_ra}/{coadd_id}/{filename}"
                )

                image_url = (
                    f"{responding_host}/ibe/data/{relative_path}"
                )

                observation_date = row.get("mid_obs") or ""

                record = {
                    "dataset": "AllWISE Atlas",
                    "coadd_id": coadd_id,
                    "band": row_band,
                    "observation_date": observation_date,
                    "mjd_obs": None,
                    "image_url": image_url
                }

            record["cutout_url"] = wise_cutout_url(
                record["image_url"],
                coord,
                radius_deg
            )
            records.append(record)

        except (TypeError, ValueError, KeyError):
            continue

    # NEOWISE: ordenar por tiempo para conservar el orden temporal.
    if dataset == "neowiser":
        records.sort(
            key=lambda item: (
                item.get("mjd_obs")
                if item.get("mjd_obs") is not None
                else float("inf")
            )
        )
    else:
        records.sort(
            key=lambda item: item.get("observation_date") or ""
        )

    total_records = len(records)

    if total_records > max_results:
        indexes = np.linspace(
            0,
            total_records - 1,
            max_results,
            dtype=int
        )
        records = [records[index] for index in indexes]

    try:
        temporary = cache_path.with_name(
            f"{cache_path.stem}.{time.time_ns()}.tmp"
        )
        temporary.write_text(
            json.dumps(records, ensure_ascii=False),
            encoding="utf-8"
        )
        atomic_replace(temporary, cache_path)
    except OSError:
        pass

    return records, f"irsa_ibe:{urlsplit(responding_host).netloc}"

