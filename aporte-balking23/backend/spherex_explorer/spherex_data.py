"""Infraestructura compartida de SPHEREx Explorer: configuración, IRSA, FITS, caché y estado.

Módulo extraído sin reescribir los algoritmos del backend monolítico WISE_FIX.

"""

import io

import os

import json

import csv

import time

import uuid

import hashlib

import copy

import re

from pathlib import Path

from urllib.parse import urlencode, quote, urlsplit, urlunsplit

from threading import Lock, local

from functools import wraps

from collections import Counter

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import numpy as np

import pyvo

from requests.adapters import HTTPAdapter

from urllib3.util.retry import Retry

from flask import (

    Flask,

    jsonify,

    request,

    send_file,

    Response,

    url_for

)

from astropy.coordinates import SkyCoord

from astropy import units as u

from astropy.io import fits

from astropy.wcs import WCS

from astropy.wcs.utils import proj_plane_pixel_scales

from astropy.nddata import Cutout2D

from astropy.nddata.utils import NoOverlapError

from astropy.visualization import ZScaleInterval

from astropy.time import Time

from astropy.stats import sigma_clipped_stats

from PIL import Image, ImageDraw, ImageFont

# Reproyección astrométrica para comparar imágenes compatibles.

try:

    from reproject import reproject_interp

except ImportError:

    reproject_interp = None

# Archivos oficiales: ESA Gaia Archive e IRSA (NASA/IPAC).

GAIA_TAP_SYNC_URL = "https://gea.esac.esa.int/tap-server/tap/sync"

IRSA_TAP_SYNC_URL = "https://irsa.ipac.caltech.edu/TAP/sync"

IRSA_IBE_SEARCH_BASE = "https://irsa.ipac.caltech.edu/ibe/search"

IRSA_IBE_DATA_BASE = "https://irsa.ipac.caltech.edu/ibe/data"

# Servidores documentados de IRSA. Se consultan de manera secuencial

# solamente si falla el servidor principal (no se mezcla contenido de terceros).

IRSA_IBE_HOSTS = (

    "https://irsa.ipac.caltech.edu",

    "https://irsawebops2.ipac.caltech.edu",

    "https://irsawebops1.ipac.caltech.edu",

)

WISE_API_VERSION = "wise-sia2-first-v5"

WISE_SIA_MAXREC = 600

WISE_METADATA_CACHE_TTL = 30 * 60

WISE_MAX_RESULTS = 30

CATALOG_CACHE_TTL = 30 * 60

CATALOG_MAX_SOURCES = 350

CATALOG_QUERY_TIMEOUT = 28

MAX_SPECTRUM_POINTS = 102  # observaciones muestreadas; NO equivale a 102 canales de un cubo

SPECTRUM_CACHE_TTL = 24 * 3600

SPHEREX_AWS_BUCKET = "nasa-irsa-spherex"

SPHEREX_AWS_REGION = "us-east-1"

# ============================================================

# 1. CONFIGURACION GENERAL

# ============================================================

app = Flask(__name__)

SPHEREX_SIA_URL = "https://irsa.ipac.caltech.edu/SIA?"

DEFAULT_COLLECTION = "spherex_dr1"

# Resolución científica fija de salida para TIMELAPSE, COADD y SUBTRACTION.

FIXED_CROP_SIZE = 512

ALLOWED_MODES = {"timelapse", "coadd", "subtraction"}

ALLOWED_DETECTORS = {"ALL", "D1", "D2", "D3", "D4", "D5", "D6"}

# Concurrencia controlada: cuatro descargas/procesamientos.

MAX_WORKERS = 4

# Reintentos de red y tiempos de espera.

IRSA_ATTEMPTS = 3

CONNECT_TIMEOUT = 15

READ_TIMEOUT = 90

# Los metadatos se reutilizan durante 30 minutos.

METADATA_CACHE_TTL = 30 * 60

# SPHEREx: margen del recorte remoto respecto del recorte final.

# Ejemplo: salida 360x360 -> petición remota aproximada 450x450.

REMOTE_CUTOUT_MARGIN = 1.25

# Versiones de caché: cambiar estos valores invalida las cachés

# correspondientes cuando se modifique el algoritmo.

PIXEL_CACHE_VERSION = "pixels-v7-flags-int-qa"

FRAME_CACHE_VERSION = "integrated-v5-science-metadata"

ALLOWED_COLLECTIONS = {

    # El cubo DR1 de 102 canales requiere un lector de FITS 3D distinto;

    # esta lista es exclusivamente para imágenes espectrales L2 bidimensionales.

    "spherex_dr1",

    "spherex_dr1_deep",

    "spherex_qr3",

    "spherex_qr3_deep"

}

# Cache location is configurable and is never served as a public static directory.

# Set SPHEREX_CACHE_DIR (or CACHE_DIR) to reuse an existing scientific cache.

# By default, use the repository's cache/ directory.

CACHE_DIR = Path(

    os.environ.get("SPHEREX_CACHE_DIR")

    or os.environ.get("CACHE_DIR")

    or (Path(__file__).resolve().parents[2] / "cache")

).expanduser().resolve()

CUTOUT_CACHE_DIR = CACHE_DIR / "cutouts"

FULL_FITS_CACHE_DIR = CACHE_DIR / "fits"

PIXEL_CACHE_DIR = CACHE_DIR / "pixels"

FRAME_CACHE_DIR = CACHE_DIR / "frames_v2"

METADATA_CACHE_DIR = CACHE_DIR / "metadata"

JOB_OUTPUT_DIR = CACHE_DIR / "jobs"

WISE_METADATA_CACHE_DIR = CACHE_DIR / "wise" / "metadata"

WISE_PREVIEW_CACHE_DIR = CACHE_DIR / "wise" / "previews"

CATALOG_CACHE_DIR = CACHE_DIR / "catalogs"

OVERLAY_CACHE_DIR = CACHE_DIR / "overlays"

SPECTRUM_CACHE_DIR = CACHE_DIR / "spectra"

for folder in (

    CUTOUT_CACHE_DIR,

    FULL_FITS_CACHE_DIR,

    PIXEL_CACHE_DIR,

    FRAME_CACHE_DIR,

    METADATA_CACHE_DIR,

    JOB_OUTPUT_DIR,

    WISE_METADATA_CACHE_DIR,

    WISE_PREVIEW_CACHE_DIR,

    CATALOG_CACHE_DIR,

    OVERLAY_CACHE_DIR,

    SPECTRUM_CACHE_DIR

):

    folder.mkdir(parents=True, exist_ok=True)

# Sesión HTTP independiente por hilo.

THREAD_LOCAL = local()

# Bloqueos para evitar descargas duplicadas del mismo archivo.

CACHE_LOCKS = {}

CACHE_LOCKS_GUARD = Lock()

# Gestión de trabajos.

JOBS = {}

JOB_FUTURES = {}

JOBS_LOCK = Lock()

ACTIVE_JOB_ID = None

# Solo se admite un trabajo de generación a la vez.

# Dentro de cada trabajo se utilizan MAX_WORKERS trabajadores.

JOB_EXECUTOR = ThreadPoolExecutor(

    max_workers=1,

    thread_name_prefix="SPHEREx-Job"

)

# ============================================================

# 2. UTILIDADES GENERALES

# ============================================================

SPHEREX_PIXEL_FLAGS = {

    0: "TRANSIENT", 1: "OVERFLOW", 2: "SUR_ERROR",

    6: "NONFUNC", 7: "DICHROIC", 9: "MISSING_DATA",

    10: "HOT", 11: "COLD", 14: "PHANMISS",

    15: "NONLINEAR", 17: "PERSIST", 19: "OUTLIER",

    20: "CROSSTALK", 21: "SOURCE", 22: "GHOST",

    23: "GHOST_FPA", 24: "GHOST_EXT", 25: "STREAK",

    26: "BLOOM", 27: "SNOWBALL", 28: "HALO",

    29: "SATELLITE_HALO",

}

SPHEREX_CAUTION_BITS = (

    0, 1, 2, 6, 7, 9, 10, 11, 14, 15, 17,

    19, 20, 22, 23, 24, 25, 26, 27, 28, 29,

)

SPHEREX_CAUTION_MASK = sum(1 << bit for bit in SPHEREX_CAUTION_BITS)

def make_hash(value):

    return hashlib.sha256(

        value.encode("utf-8")

    ).hexdigest()

def atomic_replace(source_path, destination_path):

    os.replace(str(source_path), str(destination_path))

def get_cache_lock(key):

    with CACHE_LOCKS_GUARD:

        if key not in CACHE_LOCKS:

            CACHE_LOCKS[key] = Lock()

        return CACHE_LOCKS[key]

def now_string():

    return Time.now().utc.isot

def update_job(job_id, **changes):

    with JOBS_LOCK:

        if job_id in JOBS:

            JOBS[job_id].update(changes)

            JOBS[job_id]["updated_at"] = now_string()

def get_job_copy(job_id):

    with JOBS_LOCK:

        if job_id not in JOBS:

            return None

        return copy.deepcopy(JOBS[job_id])

def public_job(job):

    """Elimina rutas locales y objetos internos antes de enviar JSON."""

    if job is None:

        return None

    excluded = {

        "frame_paths",

        "gif_path",

        "result_path",

        "science_fits_path",

        "future"

    }

    public = {

        key: value

        for key, value in job.items()

        if key not in excluded

    }

    # Las cabeceras WCS se conservan internamente para dibujar capas de

    # catálogos, pero no se envían repetidamente al navegador.

    public["frames"] = [

        {key: value for key, value in frame.items() if key != "wcs_header"}

        for frame in job.get("frames", [])

    ]

    return public

def get_http_session():

    session = getattr(THREAD_LOCAL, "session", None)

    if session is None:

        retry_config = Retry(

            total=3,

            connect=3,

            read=2,

            status=3,

            backoff_factor=0.7,

            status_forcelist=(429, 500, 502, 503, 504),

            allowed_methods=frozenset(["GET"]),

            respect_retry_after_header=True

        )

        adapter = HTTPAdapter(

            max_retries=retry_config,

            pool_connections=MAX_WORKERS,

            pool_maxsize=MAX_WORKERS

        )

        session = requests.Session()

        session.mount("https://", adapter)

        session.mount("http://", adapter)

        session.headers.update({

            "User-Agent": "SPHEREx-Explorer/1.0"

        })

        THREAD_LOCAL.session = session

    return session

def parse_coordinates(ra_value, dec_value):

    ra_text = str(ra_value).strip()

    dec_text = str(dec_value).strip()

    if not ra_text or not dec_text:

        raise ValueError("RA y Dec son obligatorias.")

    if any(

        char in ra_text.lower()

        for char in ("h", "m", "s", ":")

    ):

        ra_unit = u.hourangle

    else:

        ra_unit = u.deg

    coord = SkyCoord(

        ra=ra_text,

        dec=dec_text,

        unit=(ra_unit, u.deg),

        frame="icrs"

    )

    if not np.isfinite(coord.ra.deg) or not np.isfinite(coord.dec.deg):

        raise ValueError("Las coordenadas deben ser finitas.")

    return coord

def parse_bool(value, default=True):

    if value is None:

        return default

    if isinstance(value, bool):

        return value

    return str(value).strip().lower() not in {

        "0", "false", "off", "no", "n"

    }

def parse_request_parameters(source):

    ra = source.get("ra")

    dec = source.get("dec")

    if (
        ra is None
        or dec is None
        or str(ra).strip() == ""
        or str(dec).strip() == ""
    ):
        raise ValueError("Debe proporcionar los parámetros RA y Dec.")

    coord = parse_coordinates(ra, dec)

    radius = float(source.get("radius", 0.02))

    fps = int(source.get("fps", 2))

    max_frames = int(source.get("max_frames", 8))

    collection = str(

        source.get("collection", DEFAULT_COLLECTION)

    ).strip()

    use_cutouts = parse_bool(

        source.get("use_cutouts", True),

        default=True

    )

    offline_only = parse_bool(source.get("offline_only", False), default=False)

    refresh_metadata = parse_bool(source.get("refresh_metadata", False), default=False)

    if offline_only:

        refresh_metadata = False

    mode = str(source.get("mode", "timelapse")).strip().lower()

    detector_filter = str(source.get("detector", "ALL")).strip().upper()

    # Resolución API ajustable. La interfaz existente usa 360 por defecto.

    # Radio de consulta SIA2; view_mode=radius ajusta además el campo WCS visible.

    crop_size = int(source.get("crop_size", FIXED_CROP_SIZE))

    if not 128 <= crop_size <= 1024:

        raise ValueError("crop_size debe estar entre 128 y 1024 píxeles.")

    if not np.isfinite(radius) or not 0 < radius <= 5:

        raise ValueError("El radio de búsqueda debe estar entre 0 y 5 grados.")

    view_mode = str(source.get("view_mode", "radius")).strip().lower()

    if view_mode not in ("radius", "native"):

        raise ValueError("view_mode debe ser radius o native.")

    # La salida sigue siendo 360 × 360; solo cambia la escala angular/WCS.

    # Grandes radios pueden carecer de cobertura, y se informan como tal.

    if not 1 <= fps <= 20:

        raise ValueError("FPS debe estar entre 1 y 20.")

    if mode not in ALLOWED_MODES:

        raise ValueError("El modo debe ser timelapse, coadd o subtraction.")

    if mode == "timelapse":

        if not 4 <= max_frames <= 20:

            raise ValueError(

                "Para TIMELAPSE, los fotogramas deben estar entre 4 y 20."

            )

    elif mode == "coadd":

        if not 2 <= max_frames <= 20:

            raise ValueError(

                "Para COADD, las observaciones deben estar entre 2 y 20."

            )

    elif mode == "subtraction":

        if not 2 <= max_frames <= 20:

            raise ValueError(

                "Para SUBTRACTION, las observaciones deben estar entre 2 y 20."

            )

    if collection not in ALLOWED_COLLECTIONS:

        raise ValueError("La colección SPHEREx seleccionada no es válida.")

    if detector_filter not in ALLOWED_DETECTORS:

        raise ValueError("Detector no válido. Utilice ALL o D1–D6.")

    params = {

        "ra_input": str(ra),

        "dec_input": str(dec),

        "radius": radius,

        "fps": fps,

        "crop_size": crop_size,

        "max_frames": max_frames,

        "collection": collection,

        "use_cutouts": use_cutouts,

        "mode": mode,

        "detector_filter": detector_filter,

        "view_mode": view_mode,

        "offline_only": offline_only,

        "refresh_metadata": refresh_metadata

    }

    return params, coord

def get_column(row, column_name):

    try:

        value = row[column_name]

        if np.ma.is_masked(value):

            return None

        if value is None:

            return None

        if str(value).strip() in ("", "--", "None"):

            return None

        if isinstance(value, np.generic):

            value = value.item()

        return value

    except (KeyError, IndexError, TypeError, ValueError):

        return None

def metadata_cache_path(coord, radius, collection):

    key = (

        f"spherex-metadata-v3-cloud-bandpass|{collection}|"

        f"{coord.ra.deg:.9f}|"

        f"{coord.dec.deg:.9f}|"

        f"{radius:.9f}"

    )

    return METADATA_CACHE_DIR / f"{make_hash(key)}.json"

def load_metadata_cache(path):

    try:

        with open(path, "r", encoding="utf-8") as file:

            records = json.load(file)

        if isinstance(records, list):

            return records

    except (OSError, json.JSONDecodeError):

        pass

    return None

def save_metadata_cache(path, records):

    temporary = path.with_name(

        f"{path.stem}.{time.time_ns()}.tmp"

    )

    try:

        with open(temporary, "w", encoding="utf-8") as file:

            json.dump(records, file, ensure_ascii=False)

        atomic_replace(temporary, path)

    finally:

        if temporary.exists():

            temporary.unlink(missing_ok=True)

# La caché previa almacenaba archivos hash sin coordenadas/radio legibles.

# Los .context.json registran en adelante la huella de cada consulta.

def _metadata_context_path(cache_path):

    return cache_path.with_suffix(".context.json")

def _remember_metadata_region(coord, radius, collection, cache_path):

    """Registra procedencia del inventario; no modifica los 241 registros históricos."""

    context_path = _metadata_context_path(cache_path)

    if context_path.exists():

        return

    context = {

        "version": 1, "ra_deg": float(coord.ra.deg),

        "dec_deg": float(coord.dec.deg), "radius_deg": float(radius),

        "collection": collection, "metadata_file": cache_path.name,

    }

    with get_cache_lock("metadata-index:" + cache_path.name):

        if not context_path.exists():

            save_json_atomic(context, context_path)

def _cached_regions(coord, collection):

    """Busca regiones conocidas, incluida la caché heredada de radio 0.0211°.

        La compatibilidad se decide mediante separación angular entre centros,

        nunca solo comparando números de radio.

        """

    candidates = []

    seen = set()

    # Compatibilidad hacia atrás sin renombrar las cachés antiguas.

    # Para nuevas consultas se escribe un .context.json automáticamente.

    for historic_radius in (0.0211, 0.02, 0.03, 0.05, 0.01, 0.015, 0.1):

        path = metadata_cache_path(coord, historic_radius, collection)

        if path.exists() and load_metadata_cache(path) is not None:

            _remember_metadata_region(coord, historic_radius, collection, path)

    for context_path in METADATA_CACHE_DIR.glob("*.context.json"):

        try:

            context = json.loads(context_path.read_text(encoding="utf-8"))

            if context.get("collection") != collection:

                continue

            filename = context.get("metadata_file")

            if not isinstance(filename, str) or Path(filename).name != filename:

                continue

            path = METADATA_CACHE_DIR / filename

            if path.name in seen or not path.exists():

                continue

            r = float(context["radius_deg"])

            ra, dec = float(context["ra_deg"]), float(context["dec_deg"])

            if not (0 < r <= 5) or not all(np.isfinite([ra, dec, r])):

                continue

            saved_coord = SkyCoord(ra=ra*u.deg, dec=dec*u.deg, frame="icrs")

            separation_deg = float(saved_coord.separation(coord).deg)

            # Solo reutilizar campos cuyo cono guardado contiene el centro actual.

            if separation_deg > r:

                continue

            records = load_metadata_cache(path)

            if records is None or not records:

                continue

            seen.add(path.name)

            candidates.append((r, separation_deg, records, path))

        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):

            continue

    return candidates

def _compatible_cached_metadata(coord, radius, collection):

    candidates = _cached_regions(coord, collection)

    sufficient = [item for item in candidates if item[0] + 1e-10 >= radius + item[1]]

    if sufficient:

        # Elegir el cono contenido más pequeño para evitar exceso de candidatos.

        r, sep, records, path = min(sufficient, key=lambda x: (x[0], x[1]))

        return records, "cache-contenida", {

            "search_region_complete": True,

            "inventory_coverage": "superset-candidate",

            "cached_radius_deg": r, "separation_deg": sep,

        }

    if candidates:

        # Datos reales, pero INVENTARIO INCOMPLETO para el radio solicitado.

        r, sep, records, path = max(candidates, key=lambda x: (x[0] - x[1], len(x[2])))

        return records, "cache-parcial", {

            "search_region_complete": False,

            "inventory_coverage": "partial",

            "cached_radius_deg": r, "separation_deg": sep,

        }

    return None

def metadata_coverage_from_source(source):

    """Clasifica procedencia de datos sin atribuir cobertura no verificada."""

    if source == "cache-parcial":

        return "parcial"

    if source == "cache-contenida":

        return "candidatos-de-region-contenida"

    if source in ("cache", "stale-cache", "irsa-sia2"):

        return "consulta-del-radio-solicitado"

    return "desconocida"

def detector_from_bandpass(*values):

    """Identifica D1-D6 desde metadatos SIA2, obs_id o nombre del FITS."""

    text = " ".join(str(value or "") for value in values).upper()

    match = re.search(r"(?:^|[^A-Z0-9])D([1-6])(?:$|[^A-Z0-9])", text)

    if match:

        return f"D{match.group(1)}"

    # Los nombres SPHEREx suelen contener fragmentos como _2D1_spx.

    match = re.search(r"D([1-6])", text)

    if match:

        return f"D{match.group(1)}"

    return None

def cloud_access_to_https(cloud_access):

    """Convierte el cloud_access S3 público de IRSA en una URL HTTPS anónima."""

    if not cloud_access:

        return None

    try:

        if isinstance(cloud_access, bytes):

            cloud_access = cloud_access.decode("utf-8", errors="replace")

        info = (

            json.loads(cloud_access)

            if isinstance(cloud_access, str)

            else cloud_access

        )

        aws = info.get("aws", {}) if isinstance(info, dict) else {}

        bucket = str(aws.get("bucket_name") or "").strip()

        key = str(aws.get("key") or "").lstrip("/").strip()

        region = str(aws.get("region") or "").strip()

        if not bucket or not key:

            return None

        if not region:

            region = (

                SPHEREX_AWS_REGION

                if bucket == SPHEREX_AWS_BUCKET

                else "us-east-1"

            )

        encoded_key = quote(key, safe="/")

        return f"https://{bucket}.s3.{region}.amazonaws.com/{encoded_key}"

    except (TypeError, ValueError, json.JSONDecodeError):

        return None

def select_dominant_spectral_group(records):

    """Para visualización temporal elige un detector; λ fina se verifica después."""

    groups = {}

    for record in records:

        detector = (

            record.get("detector")

            or detector_from_bandpass(record.get("bandpass"), record.get("obs_id"), record.get("url"))

            or "UNKNOWN"

        )

        bandpass = str(record.get("bandpass") or detector).strip().upper()

        key = (detector, bandpass or "UNKNOWN")

        groups.setdefault(key, []).append(record)

    usable = [

        (key, items)

        for key, items in groups.items()

        if key != ("UNKNOWN", "UNKNOWN")

    ]

    if not usable:

        return records, None

    selected_key, selected_records = max(

        usable,

        key=lambda item: (len(item[1]), item[0])

    )

    return selected_records, {

        "detector": selected_key[0],

        "bandpass": selected_key[1],

        "observations_in_group": len(selected_records)

    }

def search_spherex_with_retry(

    coord,

    radius,

    collection,

    attempts=IRSA_ATTEMPTS,

    refresh=False,

    offline=False

):

    cache_path = metadata_cache_path(coord, radius, collection)

    cached = load_metadata_cache(cache_path)

    if (

        not refresh and cached is not None

        and cache_path.exists()

        and time.time() - cache_path.stat().st_mtime < METADATA_CACHE_TTL

    ):

        _remember_metadata_region(coord, radius, collection, cache_path)

        print("Metadatos SPHEREx recuperados desde caché local.")

        return cached, "cache"

    # Si existe inventario exacto, es válido incluso después de 30 min:

    # al fallar IRSA se preferiría ese mismo inventario sin pedir otra descarga.

    if cached is not None and not refresh:

        _remember_metadata_region(coord, radius, collection, cache_path)

        print("Inventario del radio exacto recuperado desde caché local.")

        return cached, "cache"

    compatible = _compatible_cached_metadata(coord, radius, collection)

    # Si disponemos de una región que contiene el cono solicitado,

    # evitamos bloquear el visor durante los 3 reintentos HTTP 502.

    if compatible and compatible[1] == "cache-contenida" and not refresh:

        print("IRSA opcional: se usarán candidatos reales de una consulta mayor guardada.")

        return compatible[0], "cache-contenida"

    stale_cache = cached

    last_error = None

    # Si tenemos solo una región menor, intentar una consulta nueva rápidamente.

    # Si IRSA sigue caído, mostrar resultados parciales claramente identificados.

    attempts = min(attempts, 1) if (compatible or stale_cache) else attempts

    if offline:

        attempts = 0

    for attempt in range(1, attempts + 1):

        try:

            print(f"Consulta IRSA SIA2: intento {attempt}/{attempts}")

            service = pyvo.dal.SIA2Service(

                SPHEREX_SIA_URL,

                check_baseurl=False,

                session=get_http_session()

            )

            result_table = service.search(

                pos=(coord.ra.deg, coord.dec.deg, radius),

                collection=collection

            )

            records = []

            for row in result_table:

                access_url = get_column(row, "access_url")

                cloud_access = get_column(row, "cloud_access")

                cloud_url = cloud_access_to_https(cloud_access)

                # No descartamos una observación si falta access_url: IRSA

                # también publica la ubicación alternativa en cloud_access.

                primary_url = str(access_url).strip() if access_url else None

                if not primary_url and not cloud_url:

                    continue

                obs_id = str(get_column(row, "obs_id") or "")

                bandpass = str(

                    get_column(row, "energy_bandpassname")

                    or get_column(row, "bandpass")

                    or ""

                )

                detector = detector_from_bandpass(

                    bandpass,

                    obs_id,

                    primary_url,

                    cloud_url

                )

                time_value = get_column(row, "t_min")

                try:

                    time_value = float(time_value)

                    if not np.isfinite(time_value):

                        time_value = None

                except (ValueError, TypeError):

                    time_value = None

                records.append({

                    "url": primary_url or cloud_url,

                    "cloud_url": cloud_url if primary_url else None,

                    "access_source": "irsa" if primary_url else "aws-public",

                    "observation_time": time_value,

                    "obs_id": obs_id,

                    "em_min": get_column(row, "em_min"),

                    "em_max": get_column(row, "em_max"),

                    "bandpass": bandpass,

                    "detector": detector,

                    "instrument": str(

                        get_column(row, "instrument_name") or ""

                    )

                })

            records.sort(

                key=lambda item: (

                    item["observation_time"] is None,

                    item["observation_time"]

                    if item["observation_time"] is not None

                    else float("inf")

                )

            )

            if not records:

                raise RuntimeError(

                    "IRSA respondió, pero no devolvió productos con "

                    "access_url ni cloud_access utilizable."

                )

            save_metadata_cache(cache_path, records)

            _remember_metadata_region(coord, radius, collection, cache_path)

            print(f"Consulta SPHEREx exitosa: {len(records)} productos.")

            return records, "irsa-sia2"

        except Exception as error:

            last_error = error

            print(f"Error consultando IRSA SIA2: {error}")

            if attempt < attempts:

                delay = 2 ** attempt

                print(f"Nuevo intento en {delay} segundos...")

                time.sleep(delay)

    if stale_cache is not None:

        print("IRSA no respondió o se seleccionó solo caché; se usará el inventario exacto anterior.")

        return stale_cache, "stale-cache"

    if compatible:

        records, source, details = compatible

        print("AVISO: IRSA no respondió. Inventario local PARCIAL; "

              f"radio guardado {details['cached_radius_deg']:.4f}°, "

              f"radio solicitado {radius:.4f}°.")

        return records, "cache-parcial"

    raise RuntimeError(

        f"No fue posible consultar IRSA SIA2: {last_error}. "

        "No hay inventario local compatible con esas coordenadas. "

        "Sin IRSA no es posible descubrir nuevos productos oficiales."

    ) from last_error

def validate_fits_file(path):

    try:

        with fits.open(

            path,

            mode="readonly",

            memmap=True,

            lazy_load_hdus=True

        ) as hdul:

            return any(

                hdu.data is not None and np.ndim(hdu.data) == 2

                for hdu in hdul

            )

    except Exception:

        return False

def stream_download(url, destination, params=None, quick=False):

    # Consultas espectrales: una solicitud breve y sin reintentos automáticos

    # para no bloquear decenas de segundos cada fotograma.

    session = requests.Session() if quick else get_http_session()

    temporary = destination.with_name(

        f"{destination.stem}.{os.getpid()}.{time.time_ns()}.part"

    )

    try:

        with session.get(

            url,

            params=params,

            stream=True,

            timeout=(10, 22) if quick else (CONNECT_TIMEOUT, READ_TIMEOUT)

        ) as response:

            response.raise_for_status()

            with open(temporary, "wb") as output:

                for chunk in response.iter_content(

                    chunk_size=1024 * 1024

                ):

                    if chunk:

                        output.write(chunk)

        if (

            not temporary.exists()

            or temporary.stat().st_size == 0

        ):

            raise RuntimeError("La descarga devolvió un archivo vacío.")

        if not validate_fits_file(temporary):

            raise RuntimeError(

                "La respuesta no contiene un FITS SPHEREx válido."

            )

        atomic_replace(temporary, destination)

        size_mb = destination.stat().st_size / (1024 * 1024)

        return size_mb

    except Exception:

        if temporary.exists():

            temporary.unlink(missing_ok=True)

        raise

    finally:

        if quick:

            session.close()

def remote_cutout_size(crop_size):

    """

        Pide un margen alrededor del recorte final.

        La unidad pix se interpreta sobre los ejes de la imagen SPHEREx.

        """

    return max(

        96,  # IRSA es más consistente con recortes >=96 px en modo espectro.

        crop_size + 16,

        int(np.ceil(crop_size * REMOTE_CUTOUT_MARGIN))

    )

def download_full_fits_cached(fits_url):

    key = make_hash(fits_url)

    destination = FULL_FITS_CACHE_DIR / f"{key}.fits"

    with get_cache_lock(f"full:{key}"):

        if (

            destination.exists()

            and destination.stat().st_size > 0

            and validate_fits_file(destination)

        ):

            print("FITS completo recuperado desde caché.")

            return destination, "full-cache"

        if destination.exists():

            destination.unlink(missing_ok=True)

        size_mb = stream_download(

            fits_url,

            destination

        )

        print(

            f"FITS completo guardado en caché "

            f"({size_mb:.2f} MB)."

        )

        return destination, "full-download"

def obtain_fits_product(

    record,

    coord,

    crop_size,

    use_cutouts,

    allow_full_fallback=True

):

    """Obtiene FITS: primero recorte IRSA. Espectros rápidos evitan FITS completos."""

    urls = []

    primary = record.get("url")

    cloud = record.get("cloud_url")

    if primary:

        urls.append((primary, record.get("access_source", "irsa")))

    if cloud and cloud != primary:

        urls.append((cloud, "aws-public"))

    if not urls:

        raise RuntimeError("El producto SPHEREx no contiene una URL descargable.")

    errors = []

    for fits_url, source_type in urls:

        if use_cutouts and source_type == "irsa" and "/ibe/data/" in fits_url:

            cutout_pixels = remote_cutout_size(crop_size)

            cutout_key = make_hash(

                f"{fits_url}|{coord.ra.deg:.9f}|{coord.dec.deg:.9f}|"

                f"{cutout_pixels}|cutout-v2"

            )

            cutout_path = CUTOUT_CACHE_DIR / f"{cutout_key}.fits"

            with get_cache_lock(f"cutout:{cutout_key}"):

                if (

                    cutout_path.exists()

                    and cutout_path.stat().st_size > 0

                    and validate_fits_file(cutout_path)

                ):

                    return cutout_path, "cutout-cache"

                if cutout_path.exists():

                    cutout_path.unlink(missing_ok=True)

                try:

                    params = {

                        "center": (

                            f"{coord.ra.deg:.9f},{coord.dec.deg:.9f}"

                        ),

                        "size": f"{cutout_pixels}pix",

                        "gzip": "false"

                    }

                    size_mb = stream_download(

                        fits_url,

                        cutout_path,

                        params=params,

                        quick=not allow_full_fallback

                    )

                    print(f"Recorte SPHEREx IRSA guardado ({size_mb:.2f} MB).")

                    return cutout_path, "cutout-download"

                except Exception as error:

                    errors.append(f"Recorte IRSA: {error}")

                    print(f"Recorte remoto no disponible: {error}")

        if not allow_full_fallback:

            errors.append(f"Descarga completa omitida para consulta rápida ({source_type})")

            continue

        try:

            fits_path, download_source = download_full_fits_cached(fits_url)

            if source_type == "aws-public":

                return fits_path, "aws-" + download_source

            return fits_path, download_source

        except Exception as error:

            errors.append(f"Descarga {source_type}: {error}")

            print(f"No se pudo descargar desde {source_type}: {error}")

    raise RuntimeError(

        "No se pudo obtener el FITS desde IRSA ni desde AWS. "

        + " | ".join(errors[-4:])

    )

def first_image_hdu(hdul):

    """Prioriza IMAGE; si no existe, utiliza la primera extensión 2D."""

    candidates = [

        hdu for hdu in hdul

        if hdu.data is not None and np.ndim(hdu.data) == 2

    ]

    for hdu in candidates:

        if str(hdu.name).upper() == "IMAGE":

            return hdu

    return candidates[0] if candidates else None

def wavelength_from_metadata(header, record):

    """

        Obtiene longitud de onda en micrómetros.

        Prefiere una longitud central explícita del FITS; si no existe,

        estima el centro geométrico con los límites espectrales SIA.

        """

    for key in ("CENTWAVE", "WAVELEN", "WAVELENGTH"):

        value = header.get(key)

        if value is None:

            continue

        try:

            value = float(value)

        except (TypeError, ValueError):

            continue

        unit_text = str(

            header.get("WAVEUNIT", header.get("CUNIT3", "um"))

        ).strip().lower()

        if unit_text in ("m", "meter", "meters"):

            value *= 1e6

        elif unit_text in ("nm", "nanometer", "nanometers"):

            value *= 1e-3

        elif unit_text in ("angstrom", "angstroms", "a"):

            value *= 1e-4

        return float(value)

    em_min = record.get("em_min")

    em_max = record.get("em_max")

    try:

        lo = float(em_min)

        hi = float(em_max)

        if np.isfinite(lo) and np.isfinite(hi) and lo > 0 and hi > 0:

            return float(np.sqrt(lo * hi) * 1e6)

    except (TypeError, ValueError):

        pass

    return None

def interpolate_wcs_wave(hdul, image_wcs, target_coord):

    """Consulta WCS-WAVE en la coordenada, no el centro global del detector.

        La tabla oficial tiene X,Y en coordenadas FITS (base 1) y VALUES[Y,X,(λ,Δλ)]

        en micrómetros. Interpolación bilineal: aproximada para visualización;

        para fotometría de precisión emplear CWAVE/CBAND del producto de calibración.

        """

    if "WCS-WAVE" not in hdul:

        return None, None

    try:

        table = hdul["WCS-WAVE"].data

        if table is None or len(table) == 0:

            return None, None

        xgrid = np.asarray(table["X"][0], dtype=float).ravel()

        ygrid = np.asarray(table["Y"][0], dtype=float).ravel()

        values = np.asarray(table["VALUES"][0], dtype=float)

        if (len(xgrid) < 2 or len(ygrid) < 2 or

                values.shape != (len(ygrid), len(xgrid), 2)):

            return None, None

        if not np.all(np.diff(xgrid) > 0) or not np.all(np.diff(ygrid) > 0):

            return None, None

        xpix, ypix = image_wcs.world_to_pixel(target_coord)

        xpix, ypix = float(xpix) + 1.0, float(ypix) + 1.0

        if not (xgrid[0] <= xpix <= xgrid[-1] and ygrid[0] <= ypix <= ygrid[-1]):

            return None, None

        xi = int(np.clip(np.searchsorted(xgrid, xpix, side="right") - 1, 0, len(xgrid)-2))

        yi = int(np.clip(np.searchsorted(ygrid, ypix, side="right") - 1, 0, len(ygrid)-2))

        fx = (xpix-xgrid[xi]) / (xgrid[xi+1]-xgrid[xi])

        fy = (ypix-ygrid[yi]) / (ygrid[yi+1]-ygrid[yi])

        v00, v10 = values[yi, xi], values[yi, xi+1]

        v01, v11 = values[yi+1, xi], values[yi+1, xi+1]

        result = ((1-fy)*((1-fx)*v00+fx*v10)

                  +fy*((1-fx)*v01+fx*v11))

        if not np.all(np.isfinite(result)) or result[0] <= 0 or result[1] <= 0:

            return None, None

        return float(result[0]), float(result[1])

    except (ValueError, TypeError, IndexError, KeyError, AttributeError):

        return None, None

def decode_spherex_flags(bitmask):

    """Traduce bits de FLAGS sin confundir SOURCE con un defecto."""

    if bitmask is None:

        return []

    value = int(bitmask) & 0xFFFFFFFF

    names = [name for bit, name in SPHEREX_PIXEL_FLAGS.items() if value & (1 << bit)]

    remaining = value & ~sum(1 << bit for bit in SPHEREX_PIXEL_FLAGS)

    if remaining:

        names += [f"UNKNOWN_BIT_{bit}" for bit in range(32) if remaining & (1 << bit)]

    return names

def auxiliary_cutout(hdul, extname, target_coord, size, celestial_wcs):

    """Recorta una extensión 2D sobre la misma grilla astronómica de IMAGE."""

    if extname not in hdul:

        return None

    hdu = hdul[extname]

    if hdu.data is None or np.ndim(hdu.data) != 2:

        return None

    # Los recortes IRSA deben entregar FLAGS/VARIANCE con el mismo WCS de IMAGE.

    if hdu.data.shape != first_image_hdu(hdul).data.shape:

        return None

    try:

        is_flags = extname.upper() == "FLAGS"

        # No convertir las máscaras bit a float32: los bits altos pueden perderse.

        dtype = np.int64 if is_flags else np.float32

        return np.array(Cutout2D(

            np.asarray(hdu.data, dtype=dtype), position=target_coord,

            size=(size, size), wcs=celestial_wcs, mode="partial",

            fill_value=0 if is_flags else np.nan

        ).data, dtype=dtype, copy=True)

    except (ValueError, NoOverlapError):

        return None

def metadata_from_header(header, cutout_wcs, record):

    detector = (

        record.get("detector")

        or detector_from_bandpass(record.get("bandpass"), record.get("obs_id"))

        or header.get("DETECTOR")

        or header.get("DET_ID")

        or header.get("DETNUM")

        or header.get("DETECT")

    )

    if detector is not None:

        detector = str(detector).strip().upper()

        if detector.isdigit():

            detector = f"D{detector}"

    bandpass = (

        record.get("bandpass")

        or header.get("BANDPASS")

        or header.get("FILTER")

        or header.get("BAND")

    )

    try:

        pixel_scales = proj_plane_pixel_scales(cutout_wcs) * 3600.0

        pixel_scale_arcsec = [

            float(value) for value in pixel_scales

        ]

    except Exception:

        pixel_scale_arcsec = None

    return {

        "detector": detector,

        "bandpass": str(bandpass) if bandpass is not None else None,

        "wavelength_um": wavelength_from_metadata(header, record),

        "bunit": str(header.get("BUNIT", "")),

        "pixel_scale_arcsec": pixel_scale_arcsec,

        "wcs_header": cutout_wcs.to_header(relax=True).tostring(

            sep="\n",

            endcard=False,

            padding=False

        )

    }

def fits_to_pixel_array(

    fits_path,

    target_coord,

    crop_size,

    record

):

    """

        Extrae el recorte centrado en target_coord y conserva los metadatos

        WCS, detector, banda, longitud de onda y unidad de los datos.

        """

    with fits.open(

        fits_path,

        mode="readonly",

        memmap=True,

        lazy_load_hdus=True

    ) as hdul:

        image_hdu = first_image_hdu(hdul)

        if image_hdu is None:

            raise ValueError("No se encontró una extensión FITS bidimensional.")

        data = np.asarray(image_hdu.data, dtype=np.float32)

        wcs = WCS(

            image_hdu.header,

            fobj=hdul

        ).celestial

        if not wcs.has_celestial:

            raise ValueError("La extensión de imagen no contiene WCS celeste.")

        cutout = Cutout2D(

            data,

            position=target_coord,

            size=(crop_size, crop_size),

            wcs=wcs,

            mode="partial",

            fill_value=np.nan

        )

        array = np.array(cutout.data, dtype=np.float32, copy=True)

        if array.shape != (crop_size, crop_size):

            raise RuntimeError(

                f"El recorte obtenido tiene forma {array.shape}; "

                f"se esperaba {(crop_size, crop_size)}."

            )

        if not np.isfinite(array).any():

            return None, None

        metadata = metadata_from_header(

            image_hdu.header,

            cutout.wcs,

            record

        )

        wavelength, bandwidth = interpolate_wcs_wave(hdul, wcs, target_coord)

        metadata["wavelength_method"] = (

            "WCS-WAVE bilinear (aproximada)" if wavelength is not None

            else "SIA/FITS detector-wide (estimada)"

        )

        if wavelength is not None:

            metadata["wavelength_um"] = wavelength

        metadata["bandwidth_um"] = bandwidth

        metadata["valid_fraction"] = float(np.isfinite(array).mean())

        flags = auxiliary_cutout(hdul, "FLAGS", target_coord, crop_size, wcs)

        variance = auxiliary_cutout(hdul, "VARIANCE", target_coord, crop_size, wcs)

        metadata["flags_available"] = flags is not None

        metadata["variance_available"] = variance is not None

        if flags is not None:

            # Evaluar únicamente el área con datos de IMAGE, no el relleno del cutout.

            flags_valid = (flags[np.isfinite(array)].astype(np.int64) & 0xFFFFFFFF)

            cy, cx = crop_size // 2, crop_size // 2

            center_is_valid = bool(np.isfinite(array[cy, cx]))

            center_flag = (int(flags[cy, cx]) & 0xFFFFFFFF) if center_is_valid else None

            aperture_data = array[max(0, cy-1):cy+2, max(0, cx-1):cx+2]

            aperture_flags = flags[max(0, cy-1):cy+2, max(0, cx-1):cx+2]

            aperture_bits = (aperture_flags[np.isfinite(aperture_data)].astype(np.int64) & 0xFFFFFFFF)

            metadata["flagged_fraction"] = (

                float(np.count_nonzero(flags_valid) / flags_valid.size)

                if flags_valid.size else None

            )

            metadata["bad_flag_fraction"] = (

                float(np.count_nonzero(flags_valid & SPHEREX_CAUTION_MASK) / flags_valid.size)

                if flags_valid.size else None

            )

            metadata["aperture_bad_flag_fraction"] = (

                float(np.count_nonzero(aperture_bits & SPHEREX_CAUTION_MASK) / aperture_bits.size)

                if aperture_bits.size else None

            )

            metadata["center_flag_bitmask"] = center_flag

            metadata["center_flag_names"] = decode_spherex_flags(center_flag)

            metadata["center_has_caution_flags"] = (

                bool(center_flag & SPHEREX_CAUTION_MASK) if center_flag is not None else None

            )

        else:

            metadata["flagged_fraction"] = None

            metadata["bad_flag_fraction"] = None

            metadata["aperture_bad_flag_fraction"] = None

            metadata["center_flag_bitmask"] = None

            metadata["center_flag_names"] = []

            metadata["center_has_caution_flags"] = None

        if variance is not None:

            metadata["variance_median"] = (

                float(np.nanmedian(variance[np.isfinite(variance) & (variance > 0)]))

                if np.any(np.isfinite(variance) & (variance > 0)) else None

            )

        # SIA2 suele identificar el detector de forma más consistente que

        # algunas cabeceras FITS antiguas o productos con nombres distintos.

        metadata["detector"] = (

            record.get("detector")

            or metadata.get("detector")

            or detector_from_bandpass(record.get("bandpass"), record.get("obs_id"))

        )

        metadata["bandpass"] = (

            record.get("bandpass") or metadata.get("bandpass")

        )

        return array, metadata, variance

def pixel_cache_path(

    record,

    coord,

    crop_size,

    use_cutouts,

    detector_filter="ALL"

):

    key = (

        f"{PIXEL_CACHE_VERSION}|"

        f"{record['url']}|"

        f"{coord.ra.deg:.9f}|"

        f"{coord.dec.deg:.9f}|"

        f"{crop_size}|"

        f"{use_cutouts}|"

        f"{detector_filter}"

    )

    return PIXEL_CACHE_DIR / f"{make_hash(key)}.npy"

def save_numpy_atomic(array, destination):

    temporary = destination.with_name(

        f"{destination.stem}.{time.time_ns()}.tmp"

    )

    try:

        with open(temporary, "wb") as file:

            np.save(file, array, allow_pickle=False)

        atomic_replace(temporary, destination)

    finally:

        if temporary.exists():

            temporary.unlink(missing_ok=True)

def save_json_atomic(data, destination):

    temporary = destination.with_name(

        f"{destination.stem}.{time.time_ns()}.tmp"

    )

    try:

        with open(temporary, "w", encoding="utf-8") as file:

            json.dump(data, file, ensure_ascii=False)

        atomic_replace(temporary, destination)

    finally:

        if temporary.exists():

            temporary.unlink(missing_ok=True)

def process_one_record(

    index,

    record,

    coord,

    crop_size,

    use_cutouts,

    detector_filter="ALL",

    allow_full_fallback=True

):

    """

        Reutiliza la matriz y sus metadatos desde caché. Si no existen,

        obtiene FITS/recorte remoto y extrae datos mediante WCS.

        """

    array_path = pixel_cache_path(

        record,

        coord,

        crop_size,

        use_cutouts,

        detector_filter

    )

    metadata_path = array_path.with_suffix(".json")

    variance_path = array_path.with_name(array_path.stem + "_variance.npy")

    with get_cache_lock(f"pixels:{array_path.name}"):

        if array_path.exists() and metadata_path.exists():

            try:

                array = np.load(array_path, allow_pickle=False)

                with open(metadata_path, "r", encoding="utf-8") as file:

                    metadata = json.load(file)

                if (

                    array.shape == (crop_size, crop_size)

                    and metadata.get("wcs_header")

                    and (not metadata.get("variance_available") or variance_path.exists())

                ):

                    return index, array, "pixel-cache", metadata, None

            except Exception:

                pass

            array_path.unlink(missing_ok=True)

            metadata_path.unlink(missing_ok=True)

            variance_path.unlink(missing_ok=True)

        try:

            fits_path, download_source = obtain_fits_product(

                record,

                coord,

                crop_size,

                use_cutouts,

                allow_full_fallback=allow_full_fallback

            )

            array, metadata, variance = fits_to_pixel_array(

                fits_path,

                coord,

                crop_size,

                record

            )

            if array is None:

                return index, None, "omitted", None, None

            detector = (

                record.get("detector")

                or metadata.get("detector")

                or detector_from_bandpass(record.get("bandpass"), record.get("obs_id"))

            )

            metadata["detector"] = detector

            metadata["bandpass"] = record.get("bandpass") or metadata.get("bandpass")

            if detector_filter != "ALL":

                if detector is None or detector != detector_filter:

                    return index, None, "detector-filtered", metadata, None

            save_numpy_atomic(array, array_path)

            if variance is not None:

                save_numpy_atomic(variance, variance_path)

            save_json_atomic(metadata, metadata_path)

            return index, array, download_source, metadata, None

        except Exception as error:

            return index, None, "error", None, str(error)

