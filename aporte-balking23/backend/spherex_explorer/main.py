"""Punto de entrada Flask: rutas, API y servidor del SPHEREx Explorer modular.
Ejecutar desde la raiz: python -m backend.spherex_explorer.main.
"""

from . import spherex_data as data
from .spherex_data import (
    ALLOWED_COLLECTIONS,
    ALLOWED_DETECTORS,
    ALLOWED_MODES,
    app,
    as_completed,
    atomic_replace,
    CACHE_DIR,
    CATALOG_MAX_SOURCES,
    Counter,
    DEFAULT_COLLECTION,
    detector_from_bandpass,
    first_image_hdu,
    fits,
    get_cache_lock,
    get_job_copy,
    Image,
    io,
    JOBS_LOCK,
    json,
    jsonify,
    make_hash,
    MAX_SPECTRUM_POINTS,
    MAX_WORKERS,
    np,
    OVERLAY_CACHE_DIR,
    parse_coordinates,
    parse_request_parameters,
    Path,
    process_one_record,
    proj_plane_pixel_scales,
    public_job,
    reproject_interp,
    request,
    requests,
    Response,
    save_json_atomic,
    search_spherex_with_retry,
    send_file,
    SkyCoord,
    SPECTRUM_CACHE_DIR,
    SPECTRUM_CACHE_TTL,
    ThreadPoolExecutor,
    time,
    url_for,
    WCS,
    WISE_MAX_RESULTS,
    WISE_PREVIEW_CACHE_DIR,
    ZScaleInterval,
)
from .spherex_analysis import (
    aggregate_spectral_points,
    get_dr1_cube_spectrum,
    select_balanced_spectrum_records,
    start_job,
    wcs_from_metadata,
)
from .astronomy_catalogs import (
    draw_catalog_overlay,
    query_catalog_sources,
    query_wise_images,
    wise_request_with_host_fallback,
)
from .viewer import VIEWER_HTML
from concurrent.futures import ThreadPoolExecutor as _SpectrumExecutor
from threading import Lock as _SpectrumLock
from uuid import uuid4 as _spectrum_uuid

# Los cubos DR1 pueden tardar en descargarse. Su procesamiento corre fuera
# de la petición HTTP, conservando el estado para mostrar progreso real.
SPECTRUM_TASKS = {}
SPECTRUM_TASKS_LOCK = _SpectrumLock()
SPECTRUM_TASK_EXECUTOR = _SpectrumExecutor(max_workers=1, thread_name_prefix="SPHEREx-Cube")


def _run_spectrum_task(task_id, coord, radius):
    def report(**updates):
        with SPECTRUM_TASKS_LOCK:
            task = SPECTRUM_TASKS.get(task_id)
            if task is not None:
                task.update(updates)
                task["status"] = "running"
        if updates.get("stage") != "download":
            app.logger.info("[espectro %s] %s", task_id, updates.get("message", updates.get("stage", "")))

    try:
        report(stage="search", message="Consultando SIA2 para el cubo DR1…")
        payload = get_dr1_cube_spectrum(coord, radius, progress=report)
        with SPECTRUM_TASKS_LOCK:
            SPECTRUM_TASKS[task_id].update({
                "status": "completed", "stage": "completed",
                "message": f"Espectro listo: {len(payload.get('spectrum', []))} canales válidos.",
                "result": payload,
            })
    except Exception as exc:
        app.logger.exception("Error en extracción del cubo DR1")
        with SPECTRUM_TASKS_LOCK:
            SPECTRUM_TASKS[task_id].update({
                "status": "failed", "stage": "failed",
                "message": "Falló la extracción del cubo DR1.",
                "error": f"{type(exc).__name__}: {exc}",
            })


@app.route("/api/spectrum/tasks", methods=["POST"])
def start_spectrum_task_route():
    try:
        body = request.get_json(silent=True) or {}
        coord = parse_coordinates(body.get("ra"), body.get("dec"))
        radius = float(body.get("radius", 0.02))
        collection = str(body.get("collection", "spherex_dr1"))
        if collection not in ("spherex_dr1", "spherex_dr1_deep"):
            return jsonify({"error": "Los trabajos de cubo requieren colección DR1."}), 400
        if not 0 < radius <= 5:
            return jsonify({"error": "Radio inválido."}), 400
        task_key = f"{coord.ra.deg:.8f}|{coord.dec.deg:.8f}"
        with SPECTRUM_TASKS_LOCK:
            for task_id, old in SPECTRUM_TASKS.items():
                if old.get("key") == task_key and old["status"] in ("queued", "running"):
                    return jsonify({"task_id": task_id, "status": old["status"]}), 202
            # Mantener como máximo 30 entradas, sin borrar las que estén activas.
            for task_id, old in list(SPECTRUM_TASKS.items()):
                if len(SPECTRUM_TASKS) < 30:
                    break
                if old["status"] in ("completed", "failed"):
                    del SPECTRUM_TASKS[task_id]
            task_id = _spectrum_uuid().hex[:12]
            SPECTRUM_TASKS[task_id] = {
                "id": task_id, "key": task_key, "status": "queued",
                "stage": "queued", "message": "Consulta de cubo DR1 en cola…",
                "downloaded_bytes": 0, "total_bytes": 0,
                "error": None, "result": None,
            }
        SPECTRUM_TASK_EXECUTOR.submit(_run_spectrum_task, task_id, coord, radius)
        return jsonify({"task_id": task_id, "status": "queued"}), 202
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/spectrum/tasks/<task_id>", methods=["GET"])
def get_spectrum_task_route(task_id):
    with SPECTRUM_TASKS_LOCK:
        task = SPECTRUM_TASKS.get(task_id)
        if task is None:
            return jsonify({"error": "Trabajo espectral desconocido."}), 404
        public = {key: value for key, value in task.items() if key != "key"}
    return jsonify(public)

@app.route("/", methods=["GET"])
def home():
    return Response(
        VIEWER_HTML,
        mimetype="text/html"
    )

@app.route("/api/health", methods=["GET"])
def health():
    with JOBS_LOCK:
        active = data.ACTIVE_JOB_ID

    return jsonify({
        "status": "OK",
        "service": "SPHEREx Explorer",
        "wise_backend_version": "WISE-UNWISE-CUTOUT-v14-RADIOS",
        "architecture": "modular-5-files-v1",
        "archive": "IRSA",
        "default_collection": DEFAULT_COLLECTION,
        "max_workers": MAX_WORKERS,
        "active_job": active,
        "remote_cutouts": True,
        "available_modes": sorted(ALLOWED_MODES),
        "crop_size_range_px": [128, 1024],
        "radius_view_enabled": True,
        "compatible_metadata_cache_enabled": True,
        "spectrum_enabled": True,
        "cube_spectrum_progress_enabled": True,
        "metadata_inventory_enabled": True,
        "science_fits_export_enabled": True,
        "url_queries_enabled": True,
        "spherex_dr1_cube_channel_count": 102,
        "spherex_dr1_cube_processing_enabled": True,
        "catalog_enabled": True,
        "catalog_overlay_enabled": True,
        "wise_sia2_fallback_enabled": True,
        "unwise_cutout_enabled": True,
        "spherex_cloud_fallback_enabled": True,
        "catalog_archives": {
            "gaia": "ESA Gaia Archive TAP / Gaia DR3",
            "allwise": "NASA/IPAC IRSA TAP / allwise_p3as_psd"
        },
        "image_archives": {
            "spherex": "NASA/IPAC IRSA SIA2 + IBE cutouts + AWS public fallback",
            "wise_allwise": "NASA/IPAC IRSA IBE + AWS S3 + FITS local",
            "neowiser": "NASA/IPAC IRSA IBE + AWS S3 + FITS local",
            "unwise": "unWISE cutout_fits neo1 W1/W2 · coadds multiepoca"
        },
        "wcs_reprojection_enabled": reproject_interp is not None,
        "cache_directory": str(CACHE_DIR)
    })

@app.route("/api/collections", methods=["GET"])
def get_collections():
    """Inventario explícito: no confundir imágenes L2 con cubos 3D."""
    return jsonify({
        "image_collections": sorted(ALLOWED_COLLECTIONS),
        "recommended_image_collections": ["spherex_dr1", "spherex_qr3"],
        "available_cube_collection": "spherex_dr1_cube",
        "cube_channels": 102,
        "cube_mode_supported": True,
        "note": "El cubo DR1 es FITS 3D y no se analiza con las funciones L2 de este backend.",
        "update_policy": "SIA2 consultado con caché de 30 min, puede retrasarse 1 día vs. IRSA GUI.",
        "archive_documentation": "https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-access/"
    })

@app.route("/api/observations", methods=["GET"])
def get_observations():
    """Inspección rápida de metadatos antes de lanzar un trabajo costoso."""
    try:
        coord = parse_coordinates(request.args.get("ra"), request.args.get("dec"))
        radius = float(request.args.get("radius", 0.02))
        collection = request.args.get("collection", DEFAULT_COLLECTION)
        if not 0 < radius <= 5 or collection not in ALLOWED_COLLECTIONS:
            return jsonify({"error": "Radio o colección no válidos."}), 400
        records, metadata_source = search_spherex_with_retry(coord, radius, collection)
        counts = Counter(record.get("detector") or "UNKNOWN" for record in records)
        # No publicamos URLs de acceso en masa; la cantidad indicada es total.
        return jsonify({
            "collection": collection, "metadata_source": metadata_source,
            "inventory_coverage": data.metadata_coverage_from_source(metadata_source),
            "inventory_complete": metadata_source in ("cache", "stale-cache", "irsa-sia2"),
            "total": len(records), "by_detector": dict(counts),
            "first_date_mjd": next((r["observation_time"] for r in records if r["observation_time"] is not None), None),
            "last_date_mjd": next((r["observation_time"] for r in reversed(records) if r["observation_time"] is not None), None),
            "note": "Inventario, no confirmación de 102 canales disponibles en este campo."
        })
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        return jsonify({"error": "Falló la consulta de observaciones.", "details": str(error)}), 502

@app.route("/api/query", methods=["GET"])
def start_job_from_url():
    """Permite crear trabajos insertando RA, Dec y parámetros en una URL."""
    try:
        params, coord = parse_request_parameters(request.args)
        job_id, _ = start_job(params, coord)
        if job_id is None:
            return jsonify({"error": "Hay un procesamiento activo."}), 429
        return jsonify({
            "job_id": job_id,
            "status_url": f"/api/jobs/{job_id}",
            "message": "Trabajo aceptado; consulte status_url para el resultado."
        }), 202
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400

@app.route("/api/jobs", methods=["POST"])
def create_job_route():
    try:
        source = request.get_json(silent=True) or {}
        params, coord = parse_request_parameters(source)

        job_id, future = start_job(
            params,
            coord
        )

        if job_id is None:
            return jsonify({
                "status": "processing",
                "message": (
                    "Ya existe una consulta en proceso. "
                    "Espera a que termine antes de iniciar otra."
                )
            }), 429

        return jsonify({
            "status": "accepted",
            "job_id": job_id,
            "message": "Consulta SPHEREx iniciada."
        }), 202

    except (ValueError, TypeError) as error:
        return jsonify({
            "error": str(error)
        }), 400

    except Exception as error:
        app.logger.exception("No se pudo iniciar el trabajo.")
        return jsonify({
            "error": "No se pudo iniciar la consulta.",
            "details": str(error)
        }), 500

@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_route(job_id):
    job = get_job_copy(job_id)

    if job is None:
        return jsonify({
            "error": "No existe ese trabajo."
        }), 404

    return jsonify(public_job(job))


def _catalog_sources_mosaic_360(wcs, width, height, catalog):
    """Consulta Gaia/AllWISE en una malla WCS de 3 x 3 sobre TODO el fotograma.

    No estira los marcadores ni modifica sus coordenadas reales. Cada celda
    consulta un cono limitado y selecciona fuentes ubicadas dentro de la
    celda; evita que las primeras 120 fuentes de una consulta grande queden
    concentradas en un solo sector o incluso fuera de la imagen.
    """
    side = 3
    max_per_tile = 18
    x_edges = np.linspace(0, width, side + 1)
    y_edges = np.linspace(0, height, side + 1)

    # El radio de cada cono corresponde a la mitad de la diagonal de la celda.
    # Margen del 12 % para cubrir esquinas ante rotaciones leves del WCS.
    scales_arcsec = np.asarray(proj_plane_pixel_scales(wcs), dtype=float) * 3600.0
    if scales_arcsec.size < 2 or not np.all(np.isfinite(scales_arcsec[:2])):
        raise RuntimeError("Escala WCS no disponible para montar catálogo 360 px.")
    tile_width, tile_height = width / side, height / side
    tile_radius_arcmin = 0.56 * np.hypot(
        tile_width * abs(float(scales_arcsec[0])),
        tile_height * abs(float(scales_arcsec[1]))
    ) / 60.0
    if tile_radius_arcmin > 30.0:
        raise RuntimeError("El campo WCS es demasiado extenso para el mosaico de 3 x 3.")
    tile_radius_arcmin = max(0.1, tile_radius_arcmin)

    tile_tasks = []
    for row in range(side):
        for col in range(side):
            px = (x_edges[col] + x_edges[col + 1]) / 2.0 - 0.5
            py = (y_edges[row] + y_edges[row + 1]) / 2.0 - 0.5
            ra, dec = wcs.pixel_to_world_values(px, py)
            sky = SkyCoord(float(np.asarray(ra).item()),
                           float(np.asarray(dec).item()), unit="deg", frame="icrs")
            tile_tasks.append((row, col, sky))

    def fetch_one(row, col, sky):
        sources, _, _, _ = query_catalog_sources(sky, tile_radius_arcmin, catalog)
        found = []
        for source in sources:
            ra, dec = source.get("ra"), source.get("dec")
            if ra is None or dec is None:
                continue
            try:
                x, y = wcs.world_to_pixel_values(float(ra), float(dec))
                x, y = float(np.asarray(x).item()), float(np.asarray(y).item())
            except (TypeError, ValueError):
                continue
            # La malla cubre todo el fotograma, sin modificar la posición WCS.
            if (np.isfinite(x) and np.isfinite(y)
                    and x_edges[col] <= x + 0.5 < x_edges[col + 1]
                    and y_edges[row] <= y + 0.5 < y_edges[row + 1]):
                found.append(source)
        brightness_key = "g_mag" if catalog == "gaia" else "w1_mag"
        # Ordenar las fuentes recibidas por brillo cuando exista magnitud.
        found.sort(key=lambda item: (
            item.get(brightness_key) is None,
            float(item.get(brightness_key)) if item.get(brightness_key) is not None else 99.0
        ))
        return row, col, found[:max_per_tile]

    results = []
    failures = []
    # Hasta 3 consultas independientes en paralelo. La caché propia de
    # astronomy_catalogs.py evita descargas repetidas en fotogramas siguientes.
    with ThreadPoolExecutor(max_workers=3) as executor:
        pending = {
            executor.submit(fetch_one, row, col, sky): (row, col)
            for row, col, sky in tile_tasks
        }
        for future in as_completed(pending):
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append(f"celda {pending[future]}: {type(exc).__name__}")

    if failures:
        app.logger.warning(
            "Mosaico %s incompleto (%s/9 celdas fallidas): %s",
            catalog, len(failures), ", ".join(failures)
        )
    if not results:
        raise RuntimeError("No respondió ninguna celda del mosaico astronómico.")

    unique = {}
    for _, _, sources in sorted(results):
        for source in sources:
            identity = (source.get("source_id") or source.get("designation") or
                        (round(float(source["ra"]), 7), round(float(source["dec"]), 7)))
            unique[identity] = source
    app.logger.info(
        "Mosaico %s: %s fuentes seleccionadas, %s/9 celdas disponibles; "
        "imagen %sx%s px, radio por celda %.3f arcmin",
        catalog, len(unique), len(results), width, height, tile_radius_arcmin
    )
    return list(unique.values())

@app.route(
    "/api/jobs/<job_id>/frames/<int:frame_index>.png",
    methods=["GET"]
)
def get_job_frame(job_id, frame_index):
    job = get_job_copy(job_id)
    if job is None:
        return jsonify({"error": "Trabajo no encontrado."}), 404

    paths = job.get("frame_paths", [])
    if not 0 <= frame_index < len(paths):
        return jsonify({"error": "Fotograma no encontrado."}), 404

    path = Path(paths[frame_index])
    if not path.exists():
        return jsonify({"error": "El archivo del fotograma no existe."}), 404

    overlay = str(request.args.get("overlay", "none")).strip().lower()
    if overlay == "none":
        return send_file(path, mimetype="image/png", conditional=True, max_age=3600)
    if overlay not in ("gaia", "allwise"):
        return jsonify({"error": "Capa de catálogo no válida."}), 400

    try:
        frame_metadata = (job.get("frames") or [])[frame_index]
        wcs_header = frame_metadata.get("wcs_header")
        if not wcs_header:
            return jsonify({"error": "Este fotograma no conserva WCS para superponer el catálogo."}), 422

        target = job.get("target") or {}
        coord = SkyCoord(float(target["ra"]), float(target["dec"]), unit="deg", frame="icrs")
        wcs = wcs_from_metadata({"wcs_header": wcs_header})
        with Image.open(path) as source_image:
            base_image = source_image.convert("RGB")

        # El visor ya es de 360 x 360 px. Para mostrar marcadores sobre todo
        # el campo consultamos una malla WCS de 3 x 3, sin estirar posiciones.
        center_x, center_y = wcs.world_to_pixel(coord)
        if (not np.isfinite(center_x) or not np.isfinite(center_y)
                or abs(center_x - base_image.width / 2) > base_image.width * 0.35
                or abs(center_y - base_image.height / 2) > base_image.height * 0.35):
            app.logger.warning("WCS overlay descentrado: x=%s y=%s, se conserva imagen original", center_x, center_y)
            response = send_file(path, mimetype="image/png", max_age=30)
            response.headers["X-Overlay-Warning"] = "wcs-center-mismatch"
            return response
        sources = _catalog_sources_mosaic_360(
            wcs, base_image.width, base_image.height, overlay
        )
        overlay_key = make_hash(
            f"spherex-overlay-mosaic360-v1|{path}|{path.stat().st_mtime_ns}|{overlay}|"
            f"{coord.ra.deg:.8f}|{coord.dec.deg:.8f}|{base_image.width}x{base_image.height}"
        )
        overlay_path = OVERLAY_CACHE_DIR / f"{overlay_key}.png"

        with get_cache_lock(f"overlay:{overlay_key}"):
            if not overlay_path.exists():
                rendered, visible_count = draw_catalog_overlay(
                    base_image, sources, wcs, overlay,
                    epoch_mjd=frame_metadata.get("mjd")
                )
                temporary = overlay_path.with_name(f"{overlay_path.stem}.{time.time_ns()}.tmp.png")
                try:
                    rendered.save(temporary, format="PNG")
                    atomic_replace(temporary, overlay_path)
                finally:
                    if temporary.exists():
                        temporary.unlink(missing_ok=True)
            else:
                visible_count = None

        response = send_file(overlay_path, mimetype="image/png", conditional=True, max_age=3600)
        response.headers["X-Catalog-Overlay"] = overlay
        if visible_count is not None:
            response.headers["X-Visible-Sources"] = str(visible_count)
        return response

    except Exception as error:
        app.logger.warning("Capa %s no disponible; se sirve fotograma original: %s", overlay, error)
        response = send_file(path, mimetype="image/png", max_age=30)
        response.headers["X-Overlay-Warning"] = "catalog-unavailable"
        return response

@app.route(
    "/api/jobs/<job_id>/animation.gif",
    methods=["GET"]
)
def get_job_gif(job_id):
    job = get_job_copy(job_id)

    if job is None:
        return jsonify({"error": "Trabajo no encontrado."}), 404

    if job.get("status") != "completed":
        return jsonify({
            "error": "La animación todavía no está lista."
        }), 409

    gif_path = job.get("gif_path")

    if not gif_path or not Path(gif_path).exists():
        return jsonify({
            "error": "No se encontró el GIF generado."
        }), 404

    return send_file(
        gif_path,
        mimetype="image/gif",
        as_attachment=True,
        download_name="SPHEREx_timelapse.gif"
    )

@app.route("/api/jobs/<job_id>/result.png", methods=["GET"])
def get_job_result(job_id):
    job = get_job_copy(job_id)

    if job is None:
        return jsonify({"error": "Trabajo no encontrado."}), 404

    result_path = job.get("result_path")

    if not result_path or not Path(result_path).exists():
        return jsonify({"error": "No existe un resultado PNG para este trabajo."}), 404

    return send_file(
        result_path,
        mimetype="image/png",
        as_attachment=True,
        download_name=(
            "SPHEREx_COADD.png"
            if job.get("result_type") == "coadd"
            else "SPHEREx_SUBTRACTION.png"
        )
    )

@app.route("/api/jobs/<job_id>/result.fits", methods=["GET"])
def get_job_science_fits(job_id):
    """Descarga IMAGE+COVERAGE+VARIANCE (si disponible) sin estiramiento PNG."""
    job = get_job_copy(job_id)
    if job is None:
        return jsonify({"error": "Trabajo no encontrado."}), 404
    if job.get("status") != "completed":
        return jsonify({"error": "El trabajo aún no finalizó."}), 409
    path_str = job.get("science_fits_path")
    if not path_str or not Path(path_str).is_file():
        return jsonify({"error": "No existe un FITS de este trabajo."}), 404
    return send_file(path_str, mimetype="application/fits", as_attachment=True,
                     download_name=Path(path_str).name)

@app.route("/api/spectrum", methods=["GET"])
def get_spectrum():
    try:
        coord = parse_coordinates(
            request.args.get("ra"),
            request.args.get("dec")
        )
        radius = float(request.args.get("radius", 0.02))
        collection = str(
            request.args.get("collection", DEFAULT_COLLECTION)
        ).strip()
        # DR1 usa por defecto el cubo de 102 canales; QR3 sigue con L2.
        # method=l2 permite comparar con las exposiciones originales.
        method = str(request.args.get("method", "auto")).strip().lower()
        if method not in ("auto", "cube", "l2"):
            return jsonify({"error": "method debe ser auto, cube o l2"}), 400
        if method == "cube" or (method == "auto" and collection.startswith("spherex_dr1")):
            if not collection.startswith("spherex_dr1"):
                return jsonify({"error": "El cubo espectral solo existe en DR1; use method=l2 para QR3."}), 400
            try:
                return jsonify(get_dr1_cube_spectrum(coord, radius))
            except Exception as error:
                app.logger.exception("No se pudo obtener el cubo DR1")
                return jsonify({
                    "error": "No fue posible obtener el espectro de 102 canales DR1.",
                    "details": str(error),
                    "hint": "Se evitó mostrar los 6 puntos L2 como si fueran el cubo. "
                            "Para comparar el método anterior use ?method=l2. "
                            "Compruebe la conexión con IRSA y el espacio libre (cubo ~300 MB)."
                }), 502
        max_points = int(request.args.get("max_points", MAX_SPECTRUM_POINTS))
        detector_filter = str(
            request.args.get("detector", "ALL")
        ).strip().upper()

        if not 0 < radius <= 5:
            return jsonify({"error": "El radio debe estar entre 0 y 5 grados."}), 400
        if collection not in ALLOWED_COLLECTIONS:
            return jsonify({"error": "Colección no válida."}), 400
        if not 1 <= max_points <= MAX_SPECTRUM_POINTS:
            return jsonify({"error": f"max_points debe estar entre 1 y {MAX_SPECTRUM_POINTS}."}), 400
        if detector_filter not in ALLOWED_DETECTORS:
            return jsonify({"error": "Detector no válido."}), 400

        # Resultados de espectro reutilizables durante un día, sin nuevas descargas.
        spec_key = make_hash(
            f"spectrum-v5-flags-quality|{coord.ra.deg:.8f}|{coord.dec.deg:.8f}|{radius:.5f}|"
            f"{collection}|{detector_filter}|{max_points}"
        )
        spec_file = SPECTRUM_CACHE_DIR / f"{spec_key}.json"
        if spec_file.exists() and time.time() - spec_file.stat().st_mtime < SPECTRUM_CACHE_TTL:
            try:
                cached = json.loads(spec_file.read_text(encoding="utf-8"))
                cached["metadata_source"] = "spectrum-cache"
                return jsonify(cached)
            except (OSError, ValueError, KeyError):
                pass

        records, metadata_source = search_spherex_with_retry(
            coord,
            radius,
            collection
        )

        if detector_filter != "ALL":
            records = [
                record for record in records
                if (record.get("detector") or detector_from_bandpass(
                    record.get("bandpass"), record.get("obs_id"), record.get("url")
                )) == detector_filter
            ]
            if not records:
                raise RuntimeError(
                    f"No hay productos SPHEREx identificados para {detector_filter}."
                )

        selected = select_balanced_spectrum_records(records, max_points)

        results = []
        skipped_details = []

        with ThreadPoolExecutor(
            max_workers=min(MAX_WORKERS, len(selected) or 1),
            thread_name_prefix="SPHEREx-Spectrum"
        ) as executor:

            futures = [
                executor.submit(
                    process_one_record,
                    index,
                    record,
                    coord,
                    32,
                    True,
                    detector_filter,
                    False  # No descargar FITS completos de 60MB si falla el recorte
                )
                for index, record in enumerate(selected)
            ]

            for future in as_completed(futures):
                index, array, source, metadata, error = future.result()

                if error or array is None or metadata is None:
                    skipped_details.append({
                        "obs_id": selected[index].get("obs_id"),
                        "reason": str(error)[:240] if error else "Sin píxeles/cobertura válida",
                    })
                    continue

                wavelength = metadata.get("wavelength_um")
                if wavelength is None:
                    skipped_details.append({"obs_id": selected[index].get("obs_id"),
                                            "reason": "Longitud de onda no disponible"})
                    continue

                center_y = array.shape[0] // 2
                center_x = array.shape[1] // 2
                aperture = array[
                    max(0, center_y - 1):center_y + 2,
                    max(0, center_x - 1):center_x + 2
                ]

                if not np.isfinite(aperture).any():
                    skipped_details.append({"obs_id": selected[index].get("obs_id"),
                                            "reason": "Apertura central sin píxeles válidos"})
                    continue
                signal_proxy = float(np.nanmedian(aperture))
                if not np.isfinite(signal_proxy):
                    skipped_details.append({"obs_id": selected[index].get("obs_id"),
                                            "reason": "Señal central no finita"})
                    continue

                results.append({
                    "wavelength_um": float(wavelength),
                    "bandwidth_um": metadata.get("bandwidth_um"),
                    "wavelength_method": metadata.get("wavelength_method"),
                    "flagged_fraction": metadata.get("flagged_fraction"),
                    "bad_flag_fraction": metadata.get("bad_flag_fraction"),
                    "aperture_bad_flag_fraction": metadata.get("aperture_bad_flag_fraction"),
                    "center_flag_bitmask": metadata.get("center_flag_bitmask"),
                    "center_flag_names": metadata.get("center_flag_names"),
                    "center_has_caution_flags": metadata.get("center_has_caution_flags"),
                    "variance_median": metadata.get("variance_median"),
                    "signal_proxy": signal_proxy,
                    "detector": metadata.get("detector"),
                    "bandpass": metadata.get("bandpass"),
                    "unit": metadata.get("bunit") or "unidad no indicada",
                    "observation_time_mjd": selected[index].get("observation_time"),
                    "obs_id": selected[index].get("obs_id", "")
                })

        results.sort(key=lambda item: item["wavelength_um"])
        aggregated = aggregate_spectral_points(results)

        payload = {
            "target": {
                "ra_deg": coord.ra.deg,
                "dec_deg": coord.dec.deg
            },
            "collection": collection,
            "metadata_source": metadata_source,
            "count": len(aggregated),
            "raw_count": len(results),
            "observations_attempted": len(selected),
            "observations_skipped": len(selected) - len(results),
            "skipped_details": skipped_details,
            "measurement": "signal_proxy",
            "scientific_note": (
                "signal_proxy es la mediana de una apertura central 3x3, NO "
                "fotometría PSF ni espectro científicamente calibrado. "
                "La λ local se aproxima con WCS-WAVE; muestras repetidas de λ "
                "similar se agrupan por mediana. 102 canales corresponde al cubo "
                "DR1, no a estas exposiciones L2 independientes. "
                "SOURCE no implica pixel defectuoso; bad_flag_fraction indica "
                "banderas de precaución distintas de SOURCE. "
                "La interpretación de calidad es orientativa, no un filtro fotométrico validado."
            ),
            "spectrum": aggregated,
            "samples_raw": results
        }
        if results:
            try:
                save_json_atomic(payload, spec_file)
            except OSError:
                pass
        return jsonify(payload)

    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        app.logger.exception("Error en análisis espectral.")
        return jsonify({
            "error": "No se pudo completar el análisis espectral.",
            "details": str(error)
        }), 502

@app.route("/api/catalog_overlay", methods=["GET"])
def get_catalog_overlay():
    """Devuelve posiciones y propiedades astrométricas/fotométricas."""
    try:
        coord = parse_coordinates(request.args.get("ra"), request.args.get("dec"))
        radius_arcmin = float(request.args.get("radius", 5.0))
        catalog = str(request.args.get("catalog", "gaia")).strip().lower()
        if catalog == "wise":
            catalog = "allwise"

        sources, archive_name, catalog_id, metadata_source = query_catalog_sources(
            coord, radius_arcmin, catalog
        )
        return jsonify({
            "archive": archive_name,
            "catalog": "gaia_dr3" if catalog == "gaia" else "allwise",
            "catalog_id": catalog_id,
            "query_protocol": (
                "VizieR ASU/TSV" if catalog == "allwise" and "VizieR" in archive_name
                else "TAP / ADQL"
            ),
            "metadata_source": metadata_source,
            "target": {"ra_deg": float(coord.ra.deg), "dec_deg": float(coord.dec.deg)},
            "radius_arcmin": radius_arcmin,
            "count": len(sources),
            "limit": CATALOG_MAX_SOURCES,
            "sources": sources,
            "note": (
                "Gaia DR3 contiene posiciones, astrometría y fotometría, no fotografías ópticas. "
                "La superposición sobre imágenes requiere WCS válido."
                if catalog == "gaia" else
                "AllWISE es un catálogo de fuentes infrarrojas; esta consulta ligera "
                "puede incluir solo posiciones y magnitudes W1/W2, sin errores ni calidad fotométrica."
            )
        })
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except requests.RequestException as error:
        app.logger.exception("Error de conexión con un archivo oficial.")
        return jsonify({"error": "No se pudo conectar con el archivo astronómico oficial.", "details": str(error)}), 502
    except Exception as error:
        app.logger.exception("Error consultando catálogo oficial.")
        return jsonify({"error": "No se pudo consultar el catálogo oficial.", "details": str(error)}), 502

@app.route("/api/wise_images", methods=["GET"])
def get_wise_images():
    """Devuelve metadatos y URLs FITS/cutout del archivo oficial IRSA."""
    try:
        coord = parse_coordinates(
            request.args.get("ra"),
            request.args.get("dec")
        )

        radius_deg = float(request.args.get("radius", 0.02))
        dataset = str(
            request.args.get("dataset", "neowiser")
        ).strip().lower()
        band = int(request.args.get("band", 1))
        max_results = int(request.args.get("max_results", 12))

        if not 0 < radius_deg <= 5:
            return jsonify({
                "error": "El radio debe estar entre 0 y 5 grados."
            }), 400

        if dataset not in ("neowiser", "allwise", "unwise"):
            return jsonify({
                "error": "Seleccione neowiser, allwise o unwise."
            }), 400

        if not 1 <= max_results <= WISE_MAX_RESULTS:
            return jsonify({
                "error": f"max_results debe estar entre 1 y {WISE_MAX_RESULTS}."
            }), 400

        records, metadata_source = query_wise_images(
            coord,
            radius_deg,
            dataset,
            band,
            max_results
        )

        images = []
        for index, record in enumerate(records):
            item = dict(record)
            if dataset == "unwise":
                item["cutout_url"] = url_for(
                    "wise_image_fits",
                    dataset=dataset,
                    ra=f"{coord.ra.deg:.9f}",
                    dec=f"{coord.dec.deg:.9f}",
                    radius=f"{radius_deg:.9f}",
                    band=band,
                    index=index,
                    max_results=max_results
                )
                item["image_url"] = item["cutout_url"]
                item["source_archive"] = "https://unwise.me/imgsearch/"
            item["preview_url"] = url_for(
                "wise_image_preview",
                dataset=dataset,
                ra=f"{coord.ra.deg:.9f}",
                dec=f"{coord.dec.deg:.9f}",
                radius=f"{radius_deg:.9f}",
                band=band,
                index=index,
                max_results=max_results
            )
            images.append(item)

        return jsonify({
            "archive": ("unWISE (coadds WISE/NEOWISE)" if dataset == "unwise"
                        else "NASA/IPAC Infrared Science Archive (IRSA)"),
            "service": ("unWISE Cutout Service · FITS/WCS (neo1)"
                        if dataset == "unwise"
                        else "FITS local con WCS (archivo original)"
                        if str(metadata_source).startswith("local-fits")
                        else "Inventario IRSA recuperado de caché"
                        if "cache" in str(metadata_source)
                        else "IRSA Simple Image Access v2"
                        if str(metadata_source).startswith("irsa_sia2")
                        else "IRSA Image Back End (IBE)"),
            "dataset": dataset,
            "band": band,
            "target": {
                "ra_deg": coord.ra.deg,
                "dec_deg": coord.dec.deg
            },
            "radius_deg": radius_deg,
            "total_selected": len(images),
            "metadata_source": metadata_source,
            "images": images,
            "note": (
                "unWISE neo1 es un coadd multiepoca de WISE y NEOWISE-R temprano; "
                "no representa exposiciones individuales ni una curva temporal."
                if dataset == "unwise" else
                "Las URLs FITS y de recorte se construyen siguiendo la documentación "
                "de IRSA. NEOWISE-R corresponde a exposiciones individuales y AllWISE "
                "a imágenes atlas combinadas."
            )
        })

    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except (requests.RequestException, RuntimeError) as error:
        app.logger.exception("Error consultando imágenes infrarrojas.")
        if dataset == "unwise":
            return jsonify({
                "error": "No se pudo descargar o validar el FITS unWISE.",
                "details": str(error),
                "diagnostic": "Revisar conectividad con unwise.me, TAR.GZ, WCS y caché."
            }), 502
        return jsonify({
            "error": ("No se pudieron consultar imágenes WISE/NEOWISE "
                      "desde IRSA IBE ni SIA v2. Revisa los detalles técnicos."),
            "details": str(error),
            "diagnostic": ("Verifica por separado el servicio IRSA IBE y SIA v2.")
        }), 502
    except Exception as error:
        app.logger.exception("Error en adquisición WISE/NEOWISE.")
        return jsonify({
            "error": "No se pudieron recuperar las imágenes WISE/NEOWISE: " + str(error)[:200],
            "details": str(error)
        }), 502

@app.route("/api/wise_fits", methods=["GET"])
def wise_image_fits():
    """Descarga del recorte FITS unWISE científico a través del backend local."""
    try:
        coord = parse_coordinates(request.args.get("ra"), request.args.get("dec"))
        dataset = str(request.args.get("dataset", "unwise")).strip().lower()
        radius_deg = float(request.args.get("radius", 0.02))
        band = int(request.args.get("band", 1))
        index = int(request.args.get("index", 0))
        max_results = int(request.args.get("max_results", 5))
        if dataset != "unwise" or not (0 < radius_deg <= 0.35):
            return jsonify({"error": "Solo se admite recorte unWISE con radio <= 0.35°."}), 400
        if index != 0 or not (1 <= max_results <= WISE_MAX_RESULTS):
            return jsonify({"error": "Índice de recorte unWISE no válido."}), 400
        records, _ = query_wise_images(coord, radius_deg, dataset, band, max_results)
        content = wise_request_with_host_fallback(records[0]["cutout_url"])
        return send_file(
            io.BytesIO(content), mimetype="application/fits", as_attachment=True,
            download_name=f"unWISE_neo1_W{band}_{coord.ra.deg:.5f}_{coord.dec.deg:.5f}.fits"
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        app.logger.exception("Error descargando FITS unWISE")
        return jsonify({"error": "No se pudo descargar el FITS unWISE.",
                        "details": str(error)}), 502


@app.route("/api/wise_preview", methods=["GET"])
def wise_image_preview():
    """Descarga un recorte FITS IRSA y genera PNG con capa opcional de catálogo."""
    try:
        coord = parse_coordinates(request.args.get("ra"), request.args.get("dec"))
        dataset = str(request.args.get("dataset", "neowiser")).strip().lower()
        radius_deg = float(request.args.get("radius", 0.02))
        band = int(request.args.get("band", 1))
        index = int(request.args.get("index", 0))
        max_results = int(request.args.get("max_results", 12))
        overlay = str(request.args.get("overlay", "none")).strip().lower()

        if dataset not in ("neowiser", "allwise", "unwise"):
            return jsonify({"error": "Dataset no válido."}), 400
        if not 0 < radius_deg <= 5:
            return jsonify({"error": "Radio no válido."}), 400
        if not 0 <= index < WISE_MAX_RESULTS:
            return jsonify({"error": "Índice de imagen no válido."}), 400
        if not 1 <= max_results <= WISE_MAX_RESULTS:
            return jsonify({"error": "max_results no válido."}), 400
        if overlay not in ("none", "gaia", "allwise"):
            return jsonify({"error": "Capa de catálogo no válida."}), 400

        records, _ = query_wise_images(coord, radius_deg, dataset, band, max_results)
        if index >= len(records):
            return jsonify({"error": "No existe una imagen para ese índice."}), 404

        cutout_url = records[index]["cutout_url"]
        cache_key = f"wise-preview-v2|{cutout_url}|overlay:{overlay}"
        preview_path = WISE_PREVIEW_CACHE_DIR / f"{make_hash(cache_key)}.png"

        with get_cache_lock(cache_key):
            if not preview_path.exists():
                fits_bytes = wise_request_with_host_fallback(cutout_url)
                with fits.open(io.BytesIO(fits_bytes), memmap=False) as hdul:
                    image_hdu = first_image_hdu(hdul)
                    if image_hdu is None:
                        raise RuntimeError("El FITS no contiene una imagen bidimensional.")
                    image_data = np.asarray(image_hdu.data, dtype=np.float32)
                    image_wcs = WCS(image_hdu.header, fobj=hdul).celestial

                finite = np.isfinite(image_data)
                if not finite.any():
                    raise RuntimeError("El recorte FITS no contiene píxeles válidos.")
                clean = np.where(finite, image_data, np.nan)
                vmin, vmax = ZScaleInterval().get_limits(clean)
                if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
                    vmin, vmax = float(np.nanmin(clean)), float(np.nanmax(clean))
                if vmax <= vmin:
                    vmax = vmin + 1.0
                normalized = np.clip(
                    (np.nan_to_num(clean, nan=vmin) - vmin) / (vmax - vmin),
                    0.0, 1.0
                )
                pixels = (normalized * 255.0).astype(np.uint8)
                image = Image.fromarray(pixels, mode="L").convert("RGB")

                if overlay != "none":
                    try:
                        scales_arcsec = proj_plane_pixel_scales(image_wcs) * 3600.0
                        half_diagonal_arcmin = 0.5 * np.sqrt(
                            (image_data.shape[1] * float(scales_arcsec[0])) ** 2
                            + (image_data.shape[0] * float(scales_arcsec[1])) ** 2
                        ) / 60.0
                    except Exception:
                        half_diagonal_arcmin = radius_deg * 60.0 * np.sqrt(2.0)
                    overlay_radius = min(3.0, max(0.1, half_diagonal_arcmin * 1.2))
                    sources, _, _, _ = query_catalog_sources(coord, overlay_radius, overlay)
                    image, visible_count = draw_catalog_overlay(
                        image, sources, image_wcs, overlay,
                        epoch_mjd=records[index].get("mjd_obs")
                    )
                    app.logger.info("Capa %s sobre WISE: %s fuentes visibles.", overlay, visible_count)

                temporary = preview_path.with_name(f"{preview_path.stem}.{time.time_ns()}.tmp.png")
                try:
                    image.save(temporary, format="PNG")
                    atomic_replace(temporary, preview_path)
                finally:
                    if temporary.exists():
                        temporary.unlink(missing_ok=True)

        return send_file(
            preview_path,
            mimetype="image/png",
            as_attachment=False,
            download_name=f"{dataset}_W{band}_preview.png",
            conditional=True,
            max_age=3600
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except (requests.RequestException, RuntimeError) as error:
        app.logger.exception("Error descargando recorte FITS de IRSA.")
        return jsonify({"error": "No se pudo descargar el recorte FITS desde IRSA: " + str(error)[:250],
                        "details": str(error)}), 502
    except Exception as error:
        app.logger.exception("Error generando vista previa WISE/NEOWISE.")
        return jsonify({"error": "No se pudo generar la vista previa.", "details": str(error)}), 502

@app.route("/api/get_sky_timelapse", methods=["GET"])
def legacy_timelapse_route():
    """Mantiene compatibilidad con la URL de GIF utilizada en pruebas."""
    try:
        legacy_args = request.args.to_dict()
        legacy_args.setdefault("mode", "timelapse")
        params, coord = parse_request_parameters(legacy_args)

        job_id, future = start_job(params, coord)

        if job_id is None:
            return jsonify({
                "status": "processing",
                "message": "Ya existe una consulta en proceso."
            }), 429

        future.result()
        job = get_job_copy(job_id)

        if job is None:
            return jsonify({"error": "No se pudo recuperar el resultado."}), 500

        if job.get("status") != "completed":
            return jsonify({
                "error": job.get("error") or "Falló la generación del GIF."
            }), 502

        if not job.get("gif_path"):
            return jsonify({
                "error": "La ruta de compatibilidad solo entrega timelapse GIF."
            }), 400

        return send_file(
            job["gif_path"],
            mimetype="image/gif",
            as_attachment=False,
            download_name="SPHEREx_timelapse.gif"
        )

    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        app.logger.exception("Error en la ruta de compatibilidad.")
        return jsonify({
            "error": "No se pudo generar la secuencia.",
            "details": str(error)
        }), 500

if __name__ == "__main__":

    print("====================================")
    print("SPHEREx Explorer v14 - RADIOS MULTIPLES Y CACHE WCS")
    print("====================================")
    print(f"Trabajadores simultáneos: {MAX_WORKERS}")
    print(f"Colección predeterminada: {DEFAULT_COLLECTION}")
    print("Recortes remotos IRSA: ACTIVADOS")
    print("Fallback SPHEREx AWS público: ACTIVADO")
    print("Capas Gaia DR3 / AllWISE sobre WCS: ACTIVADAS")
    print("Modos: TIMELAPSE / COADD / SUBTRACTION")
    print("Radios: WCS ±radio / escala nativa + caché compatible")
    print(f"Reproyección WCS: {'DISPONIBLE' if reproject_interp else 'NO INSTALADA'}")
    print("Catálogo Gaia DR3: ESA Gaia Archive TAP")
    print("Catálogo AllWISE: NASA/IPAC IRSA TAP")
    print("Imágenes WISE/NEOWISE: IRSA IBE/SIA v2 + AWS S3 + FITS local")
    print("Análisis espectral: ENDPOINT DISPONIBLE")
    print("Normalización: ZScale común")
    print(f"Caché: {CACHE_DIR}")
    print("Visor web: http://127.0.0.1:5000")
    print("API de salud: http://127.0.0.1:5000/api/health")
    print("API espectral: http://127.0.0.1:5000/api/spectrum")
    print("API de catálogos: http://127.0.0.1:5000/api/catalog_overlay")
    print("API de imágenes WISE/NEOWISE: http://127.0.0.1:5000/api/wise_images")
    print("====================================")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )

