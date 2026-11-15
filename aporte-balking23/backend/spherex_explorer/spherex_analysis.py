"""Procesamiento científico de SPHEREx: timelapse, apilado, diferencias y espectros DR1.
Usa servicios y estado centralizados en spherex_data.
"""

from . import spherex_data as data
from .spherex_data import (
    as_completed,
    atomic_replace,
    CONNECT_TIMEOUT,
    Counter,
    decode_spherex_flags,
    detector_from_bandpass,
    fits,
    FRAME_CACHE_DIR,
    FRAME_CACHE_VERSION,
    FULL_FITS_CACHE_DIR,
    get_cache_lock,
    get_http_session,
    Image,
    JOB_EXECUTOR,
    JOB_FUTURES,
    JOB_OUTPUT_DIR,
    JOBS,
    JOBS_LOCK,
    json,
    make_hash,
    MAX_WORKERS,
    now_string,
    np,
    Path,
    pixel_cache_path,
    process_one_record,
    READ_TIMEOUT,
    reproject_interp,
    save_json_atomic,
    search_spherex_with_retry,
    select_dominant_spectral_group,
    sigma_clipped_stats,
    SPECTRUM_CACHE_DIR,
    SPECTRUM_CACHE_TTL,
    SPHEREX_CAUTION_MASK,
    ThreadPoolExecutor,
    time,
    Time,
    u,
    update_job,
    uuid,
    WCS,
    ZScaleInterval,
)

SPHEREX_CUBE_CACHE_VERSION = "dr1-cube-20261112-v1"

SPHEREX_CUBE_COLLECTION = "spherex_dr1_cube"

SPHEREX_CUBE_MAX_BYTES = 650 * 1024 * 1024

def wcs_from_metadata(metadata):
    header_text = metadata.get("wcs_header")
    if not header_text:
        raise RuntimeError("Falta la cabecera WCS para alinear las imágenes.")

    header = fits.Header.fromstring(header_text, sep="\n")
    wcs = WCS(header).celestial

    if not wcs.has_celestial:
        raise RuntimeError("No se pudo reconstruir el WCS celeste.")

    return wcs

def align_arrays_to_reference(arrays, metadata_list):
    """
    Reproyecta los recortes a la cuadrícula WCS del primer fotograma.
    Es necesaria para sumar o restar imágenes de distintas observaciones.
    """
    if reproject_interp is None:
        raise RuntimeError(
            "Para COADD y SUBTRACTION debe instalar reproject: "
            "python -m pip install reproject"
        )

    if not arrays:
        raise RuntimeError("No hay imágenes para alinear.")

    reference_wcs = wcs_from_metadata(metadata_list[0])
    output_shape = arrays[0].shape

    aligned = []

    for array, metadata in zip(arrays, metadata_list):
        input_wcs = wcs_from_metadata(metadata)

        projected, footprint = reproject_interp(
            (array, input_wcs),
            reference_wcs,
            shape_out=output_shape,
            order="bilinear"
        )

        projected = np.asarray(projected, dtype=np.float32)
        projected[footprint <= 0] = np.nan
        aligned.append(projected)

    return aligned

def compatibility_group_key(metadata):
    detector = metadata.get("detector") or "UNKNOWN"
    bandpass = metadata.get("bandpass")

    if bandpass:
        spectral_key = f"BAND:{bandpass}"
    else:
        wavelength = metadata.get("wavelength_um")
        if wavelength is None:
            spectral_key = "UNKNOWN-BAND"
        else:
            spectral_key = f"WAVE:{round(float(wavelength), 2):.2f}"

    unit_key = metadata.get("bunit") or "UNKNOWN-UNIT"
    return detector, f"{spectral_key}|UNIT:{unit_key}"

def select_compatible_group(arrays, metadata_list, records):
    """Selecciona el conjunto más numeroso de misma banda efectiva y unidad.

    En SPHEREx D1..D6 el filtro varía en el detector: D1 solo no garantiza
    λ igual entre exposiciones. Se agrupa por λ local de WCS-WAVE.
    """
    eligible = []
    for pivot in range(len(metadata_list)):
        if metadata_list[pivot].get("wavelength_um") is None:
            continue
        matches = [i for i, current in enumerate(metadata_list)
                   if narrow_spectral_compatibility(metadata_list[pivot], current)]
        if len(matches) >= 2:
            eligible.append(matches)
    if not eligible:
        raise RuntimeError(
            "No hay dos observaciones del mismo detector con longitud de onda "
            "local compatible. Evite combinar distintos canales LVF."
        )
    indexes = max(eligible, key=lambda v: (len(v), -v[0]))
    indexes.sort(key=lambda i: (
        records[i].get("observation_time") is None,
        records[i].get("observation_time") if records[i].get("observation_time") is not None else float("inf")
    ))
    return indexes

def narrow_spectral_compatibility(metadata_a, metadata_b):
    """No promedia longitudes distintas del detector de filtro variable.

    El detector y la unidad deben coincidir. Si ambos centros son conocidos,
    permitimos diferencias <= mitad del ancho de banda más estrecho; si no
    conocemos anchura, tolerancia conservadora de 0.5% en λ.
    """
    if (metadata_a.get("detector") != metadata_b.get("detector") or
        not metadata_a.get("detector") or
        metadata_a.get("bunit") != metadata_b.get("bunit")):
        return False
    a, b = metadata_a.get("wavelength_um"), metadata_b.get("wavelength_um")
    if a is None or b is None or a <= 0 or b <= 0:
        return False
    bw_a, bw_b = metadata_a.get("bandwidth_um"), metadata_b.get("bandwidth_um")
    if bw_a is not None and bw_b is not None and bw_a > 0 and bw_b > 0:
        tolerance = 0.5 * min(bw_a, bw_b)
    else:
        tolerance = 0.005 * min(a, b)
    return abs(a-b) <= tolerance

def load_variance_for_record(record, coord, crop_size, use_cutouts, detector_filter):
    """Lee la varianza de la caché para combinar o restar mapas científicamente."""
    pixels_path = pixel_cache_path(record, coord, crop_size, use_cutouts, detector_filter)
    path = pixels_path.with_name(pixels_path.stem + "_variance.npy")
    if not path.exists():
        return None
    try:
        result = np.load(path, allow_pickle=False)
        if result.shape != (crop_size, crop_size):
            return None
        return np.asarray(result, dtype=np.float32)
    except (OSError, ValueError):
        return None

def weighted_coadd(aligned_arrays, aligned_variances):
    """Media por 1/var cuando hay al menos dos mediciones válidas por píxel.

    Si falta varianza se hace media no ponderada en ese píxel, sin simular
    información sobre incertidumbre. La covarianza introducida por reproject
    no está modelada.
    """
    stack = np.stack(aligned_arrays).astype(np.float32)
    valid = np.isfinite(stack)
    counts = np.sum(valid, axis=0)
    total = np.sum(np.where(valid, stack, 0.0), axis=0, dtype=np.float64)
    mean = np.full(counts.shape, np.nan, dtype=np.float32)
    np.divide(total, counts, out=mean, where=counts >= 2)
    variance_output = np.full(counts.shape, np.nan, dtype=np.float32)
    if any(item is None for item in aligned_variances):
        return mean, counts, variance_output, "media aritmética (varianza incompleta)"
    var_stack = np.stack(aligned_variances).astype(np.float64)
    good = valid & np.isfinite(var_stack) & (var_stack > 0)
    weights = np.zeros(stack.shape, dtype=np.float64)
    np.divide(1.0, var_stack, out=weights, where=good)
    good_counts = np.sum(good, axis=0)
    weight_sum = weights.sum(axis=0)
    weighted_sum = np.sum(np.where(good, stack, 0.0) * weights, axis=0)
    enough = (counts >= 2) & (good_counts >= 2) & (weight_sum > 0)
    np.divide(weighted_sum, weight_sum, out=mean, where=enough)
    np.divide(1.0, weight_sum, out=variance_output, where=enough)
    return mean, counts, variance_output, "media con pesos inversos a la varianza (fallback por píxel)"

def difference_with_background(first, last):
    """Resta corregida por un offset robusto; no intenta ajustar PSF."""
    mask = np.isfinite(first) & np.isfinite(last)
    if not mask.any():
        raise RuntimeError("No hay píxeles comunes entre las dos observaciones.")
    raw_difference = last[mask].astype(np.float64) - first[mask].astype(np.float64)
    _, median, _ = sigma_clipped_stats(raw_difference, sigma=3, maxiters=4)
    offset = float(median) if np.isfinite(median) else 0.0
    difference = np.where(mask, last - first - offset, np.nan).astype(np.float32)
    return difference, mask, offset

def write_science_fits(path, data, wcs_header, bunit, counts, variance, mode):
    """Exporta producto numérico reproducible con WCS y cobertura; PNG solo vista previa."""
    header = fits.Header.fromstring(wcs_header, sep="\n")
    header["BUNIT"] = str(bunit or "UNKNOWN")
    header["PRODUCT"] = (mode.upper(), "SPHEREx Explorer processing mode")
    header.add_history("WCS aligned; see COVERAGE and VARIANCE extensions")
    primary = fits.PrimaryHDU(data=np.asarray(data, dtype=np.float32), header=header)
    primary.header["EXTNAME"] = "IMAGE"
    cover = fits.ImageHDU(data=np.asarray(counts, dtype=np.int16), name="COVERAGE")
    hdus = [primary, cover]
    if variance is not None:
        uncertainty = fits.ImageHDU(data=np.asarray(variance, dtype=np.float32), name="VARIANCE")
        uncertainty.header["BUNIT"] = f"({str(bunit or 'UNKNOWN')})**2"
        hdus.append(uncertainty)
    temporary = path.with_name(f"{path.stem}.{time.time_ns()}.tmp.fits")
    try:
        fits.HDUList(hdus).writeto(temporary, overwrite=True, checksum=True)
        atomic_replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def make_difference_image(array):
    """Rojo=positivo, azul=negativo, gris~cero, negro=sin cobertura."""
    finite = np.isfinite(array)
    values = array[finite]
    if not values.size:
        raise RuntimeError("No hay datos comunes válidos para generar la resta.")
    limit = float(np.percentile(np.abs(values), 99))
    if not np.isfinite(limit) or limit <= 0:
        limit = 1.0
    normalized = np.zeros(array.shape, dtype=np.float32)
    normalized[finite] = np.clip(array[finite] / limit, -1, 1)
    pos = np.clip(normalized, 0, 1)
    neg = np.clip(-normalized, 0, 1)
    neutral = 1 - np.abs(normalized)
    rgb = np.zeros(array.shape + (3,), dtype=np.uint8)
    rgb[..., 0] = np.rint(225 * pos + 38 * neutral).astype(np.uint8)
    rgb[..., 1] = np.rint(38 * neutral).astype(np.uint8)
    rgb[..., 2] = np.rint(225 * neg + 38 * neutral).astype(np.uint8)
    rgb[~finite] = (0, 0, 0)
    return Image.fromarray(rgb, mode="RGB")

def save_result_png(image, destination):
    temporary = destination.with_name(
        f"{destination.stem}.{time.time_ns()}.tmp.png"
    )

    try:
        image.save(temporary, format="PNG")
        atomic_replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)

def calculate_shared_limits(arrays):
    valid_arrays = []

    for array in arrays:
        if array is None:
            continue

        values = array[np.isfinite(array)]

        if values.size:
            valid_arrays.append(values)

    if not valid_arrays:
        raise RuntimeError(
            "No hay píxeles válidos para normalizar."
        )

    all_values = np.concatenate(valid_arrays)

    try:
        vmin, vmax = ZScaleInterval().get_limits(all_values)

    except Exception:
        vmin, vmax = np.percentile(
            all_values,
            [1, 99]
        )

    if (
        not np.isfinite(vmin)
        or not np.isfinite(vmax)
        or vmax <= vmin
    ):
        vmin, vmax = np.percentile(
            all_values,
            [1, 99]
        )

    if vmax <= vmin:
        vmin = float(np.nanmin(all_values))
        vmax = float(np.nanmax(all_values))

    if vmax <= vmin:
        vmax = vmin + 1.0

    return float(vmin), float(vmax)

def array_to_grayscale_image(array, vmin, vmax):
    clean = np.nan_to_num(
        array,
        nan=vmin,
        posinf=vmax,
        neginf=vmin
    )

    normalized = (
        clean - vmin
    ) / (vmax - vmin)

    normalized = np.clip(
        normalized,
        0,
        1
    )

    pixels = np.rint(
        normalized * 255
    ).astype(np.uint8)

    return Image.fromarray(pixels, mode="L")

def sequence_cache_key(records, coord, crop_size, collection):
    urls = "|".join(
        record["url"]
        for record in records
    )

    key = (
        f"{FRAME_CACHE_VERSION}|"
        f"{collection}|"
        f"{coord.ra.deg:.9f}|"
        f"{coord.dec.deg:.9f}|"
        f"{crop_size}|"
        f"{urls}"
    )

    return make_hash(key)

def format_mjd(value):
    if value is None:
        return "Fecha no disponible"

    try:
        return Time(
            float(value),
            format="mjd",
            scale="utc"
        ).isot.replace("T", " ") + " UTC"

    except Exception:
        return "Fecha no disponible"

def _radius_view_wcs(coord, radius_deg, crop_size):
    """WCS TAN consistente de 360²; el ancho angular central es 2×radio."""
    target = WCS(naxis=2)
    target.wcs.crpix = [(crop_size+1)/2.0, (crop_size+1)/2.0]
    target.wcs.crval = [float(coord.ra.deg), float(coord.dec.deg)]
    step = (2.0 * float(radius_deg)) / float(crop_size)
    target.wcs.cdelt = [-step, step]
    target.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    target.wcs.cunit = ["deg", "deg"]
    return target


def _reproject_radius_view(arrays, metadata, coord, radius_deg, crop_size):
    """Reproyecta los píxeles reales; conserva NaN donde no existe cobertura.

    No inventa detalles al ampliar, ni extrapola valores fuera del FITS.
    """
    if reproject_interp is None:
        raise RuntimeError("La vista por radio requiere el paquete reproject.")
    wcs_out = _radius_view_wcs(coord, radius_deg, crop_size)
    projected = []
    fractions = []
    for array, meta in zip(arrays, metadata):
        source_wcs = wcs_from_metadata(meta)
        result, footprint = reproject_interp(
            (np.asarray(array, dtype=np.float32), source_wcs), wcs_out,
            shape_out=(crop_size, crop_size), order="bilinear"
        )
        result = np.asarray(result, dtype=np.float32)
        result[np.asarray(footprint) <= 0] = np.nan
        result[~np.isfinite(result)] = np.nan
        projected.append(result)
        fractions.append(round(float(np.isfinite(result).mean())*100.0, 2))
    new_header = wcs_out.to_header(relax=True).tostring(
        sep="\n", endcard=False, padding=False
    )
    new_metadata = []
    for meta, cov in zip(metadata, fractions):
        copy = dict(meta)
        copy["wcs_header"] = new_header
        copy["view_coverage_percent"] = cov
        copy["view_radius_deg"] = float(radius_deg)
        new_metadata.append(copy)
    return projected, new_metadata, fractions


def run_job(job_id, params, coord):

    try:
        update_job(
            job_id,
            status="running",
            stage="search",
            message="Consultando observaciones en IRSA...",
            progress=0,
            total=0
        )

        print("\\n====================================")
        print("CONSULTA SPHEREx")
        print("====================================")
        print(f"RA: {coord.ra.deg:.6f} grados")
        print(f"Dec: {coord.dec.deg:.6f} grados")
        print(f"Radio de búsqueda: {params['radius']} grados")
        print(f"Resolución de salida: {params['crop_size']} × {params['crop_size']} px (fija)")
        print(f"Colección: {params['collection']}")
        print(f"Modo: {params['mode']}")
        print(f"Detector: {params['detector_filter']}")
        print(f"Máximo de fotogramas: {params['max_frames']}")
        print(f"Trabajadores simultáneos: {MAX_WORKERS}")

        records, metadata_source = search_spherex_with_retry(
            coord,
            params["radius"],
            params["collection"],
            refresh=params.get("refresh_metadata", False),
            offline=params.get("offline_only", False)
        )

        total_available = len(records)

        if total_available == 0:
            raise RuntimeError(
                "No se encontraron observaciones para esas coordenadas."
            )

        detector_filter = params["detector_filter"]
        if detector_filter != "ALL":
            records = [
                record for record in records
                if (record.get("detector") or detector_from_bandpass(
                    record.get("bandpass"), record.get("obs_id"), record.get("url")
                )) == detector_filter
            ]
            if not records:
                raise RuntimeError(
                    f"La búsqueda encontró {total_available} producto(s), "
                    f"pero ninguno está identificado como {detector_filter}. "
                    "Se utiliza energy_bandpassname de SIA2 para identificar D1-D6."
                )

        observations_after_detector_filter = len(records)
        records, selected_spectral_group = select_dominant_spectral_group(records)
        if not records:
            raise RuntimeError("No hay observaciones dentro de un grupo espectral válido.")

        total_found = len(records)

        if total_found > params["max_frames"]:
            indexes = np.linspace(
                0,
                total_found - 1,
                params["max_frames"],
                dtype=int
            )
            selected_records = [records[index] for index in indexes]
        else:
            selected_records = records

        total_selected = len(selected_records)

        print(f"Observaciones encontradas: {total_found}")
        print(f"Fotogramas seleccionados: {total_selected}")

        update_job(
            job_id,
            stage="download",
            message="Descargando y procesando observaciones...",
            total=total_selected,
            progress=0,
            observations_found=total_found,
            observations_selected=total_selected,
            observations_before_bandpass_group=observations_after_detector_filter,
            selected_spectral_group=selected_spectral_group,
            metadata_source=metadata_source
        )

        arrays_by_index = [None] * total_selected
        sources_by_index = ["pending"] * total_selected
        metadata_by_index = [None] * total_selected
        errors = []
        completed = 0

        worker_count = min(MAX_WORKERS, total_selected)

        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="SPHEREx-Worker"
        ) as executor:

            futures = [
                executor.submit(
                    process_one_record,
                    index,
                    record,
                    coord,
                    params["crop_size"],
                    params["use_cutouts"],
                    params["detector_filter"]
                )
                for index, record in enumerate(selected_records)
            ]

            for future in as_completed(futures):
                completed += 1

                try:
                    index, array, source, metadata, error = future.result()

                    arrays_by_index[index] = array
                    sources_by_index[index] = source
                    metadata_by_index[index] = metadata

                    if error:
                        errors.append({
                            "frame": index + 1,
                            "message": error
                        })

                    print(
                        f"Progreso: {completed}/{total_selected} "
                        f"| Fotograma {index + 1} "
                        f"| Estado: {source}"
                    )

                except Exception as error:
                    errors.append({
                        "frame": completed,
                        "message": str(error)
                    })

                update_job(
                    job_id,
                    progress=completed,
                    message=(
                        f"Procesando observaciones: "
                        f"{completed}/{total_selected}"
                    )
                )

        valid_indexes = [
            index
            for index, array in enumerate(arrays_by_index)
            if array is not None and metadata_by_index[index] is not None
        ]

        if not valid_indexes:
            raise RuntimeError(
                "No se obtuvieron imágenes válidas. "
                "Revise la colección, el detector seleccionado y la cobertura."
            )

        valid_arrays = [arrays_by_index[index] for index in valid_indexes]
        valid_records = [selected_records[index] for index in valid_indexes]
        valid_sources = [sources_by_index[index] for index in valid_indexes]
        valid_metadata = [metadata_by_index[index] for index in valid_indexes]

        view_mode = params.get("view_mode", "radius")
        view_coverage = None
        native_metadata = valid_metadata
        if view_mode == "radius":
            valid_arrays, valid_metadata, view_coverage = _reproject_radius_view(
                valid_arrays, valid_metadata, coord,
                params["radius"], params["crop_size"]
            )
            # Excluir imágenes que no tienen señal alguna en el campo solicitado.
            keep = [i for i, arr in enumerate(valid_arrays) if np.isfinite(arr).any()]
            if not keep:
                raise RuntimeError(
                    "Ningún FITS disponible cubre el radio visible solicitado. "
                    "Se necesitan observaciones más amplias desde IRSA/AWS; "
                    "el programa no rellena datos inexistentes."
                )
            valid_arrays = [valid_arrays[i] for i in keep]
            valid_metadata = [valid_metadata[i] for i in keep]
            native_metadata = [native_metadata[i] for i in keep]
            valid_records = [valid_records[i] for i in keep]
            valid_sources = [valid_sources[i] for i in keep]
            view_coverage = [view_coverage[i] for i in keep]

        mode = params["mode"]
        job_folder = JOB_OUTPUT_DIR / job_id
        job_folder.mkdir(parents=True, exist_ok=True)

        frame_paths = []
        frame_metadata = []
        frame_cache_count = 0
        rendered_count = 0
        result_path = None
        gif_path = None
        result_type = None
        result_url = None
        science_fits_path = None

        # ----------------------------------------------------
        # MODO COADD / SUBTRACTION
        # ----------------------------------------------------
        if mode in ("coadd", "subtraction"):

            update_job(
                job_id,
                stage="alignment",
                message="Buscando observaciones compatibles y alineando WCS..."
            )

            compatible_indexes = select_compatible_group(
                valid_arrays,
                valid_metadata,
                valid_records
            )

            if mode == "subtraction":
                compatible_indexes = [
                    i for i in compatible_indexes
                    if valid_records[i].get("observation_time") is not None
                ]
                if len(compatible_indexes) < 2:
                    raise RuntimeError(
                        "SUBTRACTION requiere al menos dos observaciones "
                        "compatibles con fecha MJD conocida."
                    )

            selected_arrays = [valid_arrays[i] for i in compatible_indexes]
            selected_metadata = [valid_metadata[i] for i in compatible_indexes]
            selected_records_for_mode = [valid_records[i] for i in compatible_indexes]

            aligned_arrays = align_arrays_to_reference(
                selected_arrays,
                selected_metadata
            )
            unaligned_variances = [
                load_variance_for_record(
                    record, coord, params["crop_size"], params["use_cutouts"], detector_filter
                ) for record in selected_records_for_mode
            ]
            # Los mapas de varianza están en WCS nativo, aun si la imagen
            # ya fue reproyectada al radio. Recuperar el WCS original.
            if view_mode == "radius":
                # Reconocer la entrada mediante obs_id/URL para mantener índices.
                original_map = {id(rec): orig for rec, orig in zip(valid_records, native_metadata)}
                reproj_variances = []
                for rec, var in zip(selected_records_for_mode, unaligned_variances):
                    if var is None:
                        reproj_variances.append(None)
                        continue
                    wcs_src = wcs_from_metadata(original_map[id(rec)])
                    wcs_dst = wcs_from_metadata(selected_metadata[0])
                    revar, footprint = reproject_interp(
                        (var, wcs_src), wcs_dst,
                        shape_out=(params["crop_size"], params["crop_size"]),
                        order="bilinear"
                    )
                    revar = np.asarray(revar, dtype=np.float32)
                    revar[np.asarray(footprint) <= 0] = np.nan
                    reproj_variances.append(revar)
                unaligned_variances = reproj_variances
            reference_wcs = wcs_from_metadata(selected_metadata[0])
            aligned_variances = []
            for variance, meta in zip(unaligned_variances, selected_metadata):
                if variance is None:
                    aligned_variances.append(None)
                else:
                    projection, footprint = reproject_interp(
                        (variance, wcs_from_metadata(meta)), reference_wcs,
                        shape_out=aligned_arrays[0].shape, order="bilinear"
                    )
                    projection = np.asarray(projection, dtype=np.float32)
                    projection[footprint <= 0] = np.nan
                    aligned_variances.append(projection)
            output_variance = None
            background_offset = None
            if mode == "coadd":
                result_array, counts, output_variance, combination_method = weighted_coadd(
                    aligned_arrays, aligned_variances
                )
                coverage_pixels = int(np.count_nonzero(counts >= 2))
                coverage_percent = round(100.0 * coverage_pixels / counts.size, 1)
                if not coverage_pixels:
                    raise RuntimeError(
                        "Las observaciones COADD no tienen píxeles comunes "
                        "en al menos dos épocas; pruebe otras fechas o detector."
                    )
                vmin, vmax = calculate_shared_limits([result_array])
                result_image = array_to_grayscale_image(
                    result_array,
                    vmin,
                    vmax
                )
                result_label = "COADD · combinación de observaciones"
                result_type = "coadd"
                result_filename = "SPHEREx_COADD.png"

            else:
                first, last = aligned_arrays[0], aligned_arrays[-1]
                coverage_mask = np.isfinite(first) & np.isfinite(last)
                coverage_pixels = int(np.count_nonzero(coverage_mask))
                coverage_percent = round(100.0 * coverage_pixels / first.size, 1)
                if not coverage_pixels:
                    raise RuntimeError(
                        "No hay cobertura común entre la primera y última época. "
                        "Seleccione otro detector o intervalo de fechas."
                    )
                # Restar fondo robusto evita declarar cambios globales artificiales.
                result_array, coverage_mask, background_offset = difference_with_background(first, last)
                counts = coverage_mask.astype(np.int16) * 2
                if aligned_variances[0] is not None and aligned_variances[-1] is not None:
                    output_variance = aligned_variances[0] + aligned_variances[-1]
                    output_variance[~coverage_mask] = np.nan
                combination_method = "última menos primera; offset robusto eliminado"
                result_image = make_difference_image(result_array)
                result_label = "SUBTRACTION · última época menos primera época"
                result_type = "subtraction"
                result_filename = "SPHEREx_SUBTRACTION.png"

            result_path = job_folder / result_filename
            save_result_png(result_image, result_path)
            science_fits_path = job_folder / f"SPHEREx_{mode.upper()}.fits"
            write_science_fits(
                science_fits_path, result_array,
                selected_metadata[0]["wcs_header"],
                selected_metadata[0].get("bunit"), counts, output_variance, mode
            )

            frame_paths = [result_path]
            frame_metadata = [{
                "index": 0,
                "label": result_label,
                "observation_date": (
                    f"{format_mjd(selected_records_for_mode[0].get('observation_time'))}"
                    " → "
                    f"{format_mjd(selected_records_for_mode[-1].get('observation_time'))}"
                ),
                "mjd": None,
                "obs_id": "",
                "detector": selected_metadata[0].get("detector"),
                "bandpass": selected_metadata[0].get("bandpass"),
                "wavelength_um": selected_metadata[0].get("wavelength_um"),
                "bandwidth_um": selected_metadata[0].get("bandwidth_um"),
                "wavelength_method": selected_metadata[0].get("wavelength_method"),
                "bunit": selected_metadata[0].get("bunit"),
                "wcs_header": selected_metadata[0].get("wcs_header"),
                "source": "processed",
                "image_url": f"/api/jobs/{job_id}/frames/0.png"
            }]

            result_url = f"/api/jobs/{job_id}/result.png"

            summary = {
                "observations_found": total_found,
                "observations_before_detector_filter": total_available,
                "observations_before_bandpass_group": observations_after_detector_filter,
                "selected_spectral_group": selected_spectral_group,
                "observations_selected": total_selected,
                "observations_used": len(selected_arrays),
                "coverage_pixels": coverage_pixels,
                "coverage_percent": coverage_percent,
                "coverage_note": (
                    "Las zonas negras no contienen cobertura común suficiente; "
                    "no deben interpretarse como cambios astronómicos."
                ),
                "frames_generated": 1,
                "frames_from_cache": sum(
                    1 for source in valid_sources
                    if source in ("pixel-cache", "cutout-cache", "full-cache")
                ),
                "frames_omitted": total_selected - len(valid_indexes),
                "metadata_source": metadata_source,
                "worker_count": worker_count,
                "mode": mode,
                "compatible_group": list(
                    compatibility_group_key(selected_metadata[0])
                ),
                "combination_method": combination_method,
                "background_offset": background_offset,
                "result_fits_url": f"/api/jobs/{job_id}/result.fits",
                "spectral_compatibility": "mismo detector, unidad y longitud de onda local (LVF)",
                "variance_note": (
                    "Varianza reproyectada aproximada; correlaciones de interpolación no modeladas."
                    if output_variance is not None else "Varianza no disponible."
                ),
                "calibration_note": (
                    "El resultado conserva la unidad BUNIT del producto; "
                    "no se aplica una calibración fotométrica adicional."
                ),
                "errors": errors,
                "result_size_mb": round(
                    result_path.stat().st_size / (1024 * 1024),
                    3
                )
            }

        # ----------------------------------------------------
        # MODO TIMELAPSE
        # ----------------------------------------------------
        else:
            update_job(
                job_id,
                stage="normalization",
                message="Alineando observaciones y calculando escala de brillo..."
            )

            # La reproyección mejora la estabilidad visual del timelapse.
            # Si la dependencia opcional no está instalada, se conservan
            # los recortes WCS centrados en el objetivo.
            display_wcs_headers = [
                metadata.get("wcs_header") for metadata in valid_metadata
            ]
            if reproject_interp is not None and len(valid_arrays) > 1:
                try:
                    display_arrays = align_arrays_to_reference(
                        valid_arrays,
                        valid_metadata
                    )
                    # Tras la reproyección todos los fotogramas comparten la
                    # cuadrícula WCS del primero, también para las capas Gaia/WISE.
                    reference_header = valid_metadata[0].get("wcs_header")
                    display_wcs_headers = [
                        reference_header for _ in valid_metadata
                    ]
                except Exception as alignment_error:
                    print(
                        "Aviso: no se pudo alinear el timelapse; "
                        f"se conservarán los recortes originales: {alignment_error}"
                    )
                    display_arrays = valid_arrays
            else:
                display_arrays = valid_arrays

            vmin, vmax = calculate_shared_limits(display_arrays)

            sequence_key = sequence_cache_key(
                valid_records,
                coord,
                params["crop_size"],
                params["collection"]
            )
            sequence_key = make_hash(
                f"radius-view-v14|{sequence_key}|"
                f"{params['radius']:.9f}|{view_mode}"
            )

            for frame_number, (array, record, source, metadata, display_wcs_header) in enumerate(
                zip(
                    display_arrays,
                    valid_records,
                    valid_sources,
                    valid_metadata,
                    display_wcs_headers
                ),
                start=1
            ):

                frame_key = make_hash(
                    f"{FRAME_CACHE_VERSION}|{sequence_key}|"
                    f"{frame_number}|{record['url']}|{vmin}|{vmax}"
                )

                cached_png = FRAME_CACHE_DIR / f"{frame_key}.png"

                with get_cache_lock(f"frame:{frame_key}"):

                    image = None

                    if cached_png.exists() and cached_png.stat().st_size > 0:
                        try:
                            with Image.open(cached_png) as cached:
                                image = cached.convert("L").copy()
                            frame_cache_count += 1
                        except Exception:
                            cached_png.unlink(missing_ok=True)

                    if image is None:
                        image = array_to_grayscale_image(array, vmin, vmax)
                        temporary_png = cached_png.with_name(
                            f"{cached_png.stem}.{time.time_ns()}.tmp.png"
                        )

                        try:
                            image.save(temporary_png, format="PNG")
                            atomic_replace(temporary_png, cached_png)
                        finally:
                            if temporary_png.exists():
                                temporary_png.unlink(missing_ok=True)

                        rendered_count += 1

                frame_paths.append(cached_png)

                frame_metadata.append({
                    "index": frame_number - 1,
                    "label": f"Fotograma {frame_number}",
                    "observation_date": format_mjd(
                        record.get("observation_time")
                    ),
                    "mjd": record.get("observation_time"),
                    "obs_id": record.get("obs_id", ""),
                    "detector": metadata.get("detector"),
                    "bandpass": metadata.get("bandpass"),
                    "wavelength_um": metadata.get("wavelength_um"),
                    "bandwidth_um": metadata.get("bandwidth_um"),
                    "wavelength_method": metadata.get("wavelength_method"),
                    "flags_available": metadata.get("flags_available"),
                    "flagged_fraction": metadata.get("flagged_fraction"),
                    "bad_flag_fraction": metadata.get("bad_flag_fraction"),
                    "aperture_bad_flag_fraction": metadata.get("aperture_bad_flag_fraction"),
                    "center_flag_bitmask": metadata.get("center_flag_bitmask"),
                    "center_flag_names": metadata.get("center_flag_names"),
                    "center_has_caution_flags": metadata.get("center_has_caution_flags"),
                    "variance_available": metadata.get("variance_available"),
                    "valid_fraction": metadata.get("valid_fraction"),
                    "bunit": metadata.get("bunit"),
                    "wcs_header": display_wcs_header,
                    "source": source,
                    "image_url": (
                        f"/api/jobs/{job_id}/frames/{frame_number - 1}.png"
                    )
                })

            update_job(
                job_id,
                stage="gif",
                message="Generando animación GIF...",
                frames=frame_metadata,
                normalization={
                    "method": "ZScale común",
                    "vmin": vmin,
                    "vmax": vmax
                }
            )

            pil_frames = []

            for path in frame_paths:
                with Image.open(path) as image:
                    pil_frames.append(image.convert("L").copy())

            gif_path = job_folder / "spherex_timelapse.gif"
            duration_ms = int(1000 / params["fps"])

            pil_frames[0].save(
                gif_path,
                format="GIF",
                save_all=True,
                append_images=pil_frames[1:],
                duration=duration_ms,
                loop=0,
                optimize=False,
                disposal=2
            )

            for image in pil_frames:
                image.close()

            result_type = "timelapse"
            result_url = f"/api/jobs/{job_id}/animation.gif"

            summary = {
                "observations_found": total_found,
                "observations_before_detector_filter": total_available,
                "observations_before_bandpass_group": observations_after_detector_filter,
                "selected_spectral_group": selected_spectral_group,
                "observations_selected": total_selected,
                "frames_generated": len(frame_paths),
                "frames_from_cache": frame_cache_count,
                "frames_rendered": rendered_count,
                "frames_omitted": total_selected - len(valid_indexes),
                "acquisition_sources": dict(Counter(valid_sources)),
                "metadata_source": metadata_source,
                "worker_count": worker_count,
                "remote_cutouts_enabled": params["use_cutouts"],
                "errors": errors,
                "gif_size_mb": round(
                    gif_path.stat().st_size / (1024 * 1024),
                    3
                )
            }

        if view_coverage is not None:
            summary["visible_radius_deg"] = float(params["radius"])
            summary["view_mode"] = "radius"
            summary["visible_coverage_percent_min"] = min(view_coverage)
            summary["visible_coverage_percent_max"] = max(view_coverage)
            summary["visible_coverage_percent_mean"] = round(float(np.mean(view_coverage)), 2)
            summary["view_note"] = (
                "Campo angular ±radio alrededor del objetivo, "
                "reproyectado a 360×360 px. Los bordes sin datos se mantienen vacíos."
            )
        else:
            summary["view_mode"] = "native"
        summary["inventory_coverage"] = data.metadata_coverage_from_source(metadata_source)
        summary["inventory_complete"] = metadata_source in ("cache", "stale-cache", "irsa-sia2")
        if metadata_source == "cache-parcial":
            summary["coverage_warning"] = (
                "INVENTARIO PARCIAL: IRSA no respondió. "
                "Se usan productos reales de una búsqueda guardada más pequeña. "
                "Pueden faltar observaciones de este radio."
            )
        elif metadata_source == "cache-contenida":
            summary["coverage_warning"] = (
                "Candidatos procedentes de una búsqueda guardada mayor; "
                "se verificó cobertura de píxeles pero no se reconsultó el inventario remoto."
            )

        update_job(
            job_id,
            status="completed",
            stage="completed",
            message=f"Proceso {mode.upper()} completado correctamente.",
            progress=total_selected,
            total=total_selected,
            frames=frame_metadata,
            frame_paths=[str(path) for path in frame_paths],
            gif_path=str(gif_path) if gif_path else None,
            result_path=str(result_path) if result_path else None,
            science_fits_path=str(science_fits_path) if science_fits_path else None,
            science_fits_url=(f"/api/jobs/{job_id}/result.fits" if science_fits_path else None),
            gif_url=(
                f"/api/jobs/{job_id}/animation.gif"
                if gif_path else None
            ),
            result_url=result_url,
            result_type=result_type,
            summary=summary
        )

        print("\\n====================================")
        print("RESUMEN DEL PROCESAMIENTO")
        print("====================================")
        print(f"Modo: {mode}")
        print(f"Observaciones encontradas: {total_found}")
        print(f"Observaciones seleccionadas: {total_selected}")
        print(f"Imágenes válidas: {len(valid_indexes)}")
        print(f"Resultado: {result_type}")
        print("PROCESAMIENTO COMPLETADO")
        print("====================================\\n")

    except Exception as error:
        print(f"ERROR EN TRABAJO SPHEREx: {error}")

        update_job(
            job_id,
            status="failed",
            stage="failed",
            message="No se pudo completar el procesamiento.",
            error=str(error)
        )

    finally:
        with JOBS_LOCK:
            if data.ACTIVE_JOB_ID == job_id:
                data.ACTIVE_JOB_ID = None
            JOB_FUTURES.pop(job_id, None)

def start_job(params, coord):

    with JOBS_LOCK:

        if data.ACTIVE_JOB_ID is not None:
            active = JOBS.get(data.ACTIVE_JOB_ID)

            if (
                active is not None
                and active.get("status") not in ("completed", "failed")
            ):
                return None, None

        job_id = uuid.uuid4().hex[:12]

        job = {
            "id": job_id,
            "status": "queued",
            "stage": "queued",
            "message": "Consulta en cola...",
            "progress": 0,
            "total": 0,
            "created_at": now_string(),
            "updated_at": now_string(),
            "target": {
                "ra": coord.ra.deg,
                "dec": coord.dec.deg
            },
            "params": params,
            "frames": [],
            "frame_paths": [],
            "gif_path": None,
            "result_path": None,
            "science_fits_path": None,
            "science_fits_url": None,
            "gif_url": None,
            "result_url": None,
            "result_type": None,
            "summary": None,
            "error": None
        }

        JOBS[job_id] = job
        data.ACTIVE_JOB_ID = job_id

        try:
            future = JOB_EXECUTOR.submit(
                run_job,
                job_id,
                params,
                coord
            )

            JOB_FUTURES[job_id] = future

        except Exception:
            data.ACTIVE_JOB_ID = None
            JOBS.pop(job_id, None)
            raise

    return job_id, future

def download_dr1_cube_cached(record, progress=None):
    """Descarga un FITS 3D completo con límite de tamaño y caché atómica.

    El Cutout Service de las imágenes L2 no sirve para estos cubos HiPS 3D.
    Se valida la existencia del HDU IMAGE 3D y 102 planos espectrales.
    """
    candidates = [record.get("url"), record.get("cloud_url")]
    urls = [url for url in candidates if url and str(url).startswith("https://")]
    if not urls:
        raise RuntimeError("SIA2 no devolvió una URL HTTPS de cubo FITS.")

    identifier = record.get("obs_id") or urls[0]
    cache_key = make_hash(f"{SPHEREX_CUBE_CACHE_VERSION}|{identifier}")
    destination = FULL_FITS_CACHE_DIR / f"cube_dr1_{cache_key}.fits"

    def notify(stage, message, downloaded=0, total=0):
        if progress is not None:
            progress(stage=stage, message=message, downloaded_bytes=downloaded, total_bytes=total)

    with get_cache_lock(f"cube:{cache_key}"):
        if destination.is_file() and destination.stat().st_size > 0:
            try:
                with fits.open(destination, memmap=True, lazy_load_hdus=True) as hdul:
                    if "IMAGE" in hdul and len(hdul["IMAGE"].data.shape) == 3 \
                            and hdul["IMAGE"].data.shape[0] == 102 and "SPECTRAL_CHANNELS" in hdul:
                        notify("cache", "Cubo DR1 encontrado en caché.", destination.stat().st_size, destination.stat().st_size)
                        return destination, "cube-cache"
            except Exception:
                pass
            destination.unlink(missing_ok=True)

        attempts = []
        for url in urls:
            temporary = destination.with_name(f"{destination.stem}.{time.time_ns()}.part")
            try:
                with get_http_session().get(url, stream=True,
                        timeout=(CONNECT_TIMEOUT, max(READ_TIMEOUT, 120))) as response:
                    response.raise_for_status()
                    length = int(response.headers.get("Content-Length", "0") or 0)
                    if length > SPHEREX_CUBE_MAX_BYTES:
                        raise RuntimeError("FITS supera el límite de 650 MiB.")
                    written = 0
                    notify("download", "Descargando cubo FITS DR1…", 0, length)
                    last_reported = -1
                    with temporary.open("wb") as output:
                        for block in response.iter_content(chunk_size=1024 * 1024):
                            if not block:
                                continue
                            written += len(block)
                            if written > SPHEREX_CUBE_MAX_BYTES:
                                raise RuntimeError("Descarga excede el límite de 650 MiB.")
                            output.write(block)
                            # Se limita la frecuencia de avisos, sin guardar bytes en memoria.
                            marker = written // (5 * 1024 * 1024)
                            if marker != last_reported:
                                last_reported = marker
                                notify("download", "Descargando cubo FITS DR1…", written, length)
                notify("validation", "Verificando estructura FITS y sus 102 canales…", written, length)
                with fits.open(temporary, memmap=True, lazy_load_hdus=True) as hdul:
                    if "IMAGE" not in hdul or len(hdul["IMAGE"].data.shape) != 3 \
                            or hdul["IMAGE"].data.shape[0] != 102 or "SPECTRAL_CHANNELS" not in hdul:
                        raise RuntimeError("El archivo no es un cubo espectral DR1 de 102 canales.")
                atomic_replace(temporary, destination)
                notify("download_complete", "Cubo DR1 descargado y validado.", written, written)
                return destination, "cube-download"
            except Exception as error:
                attempts.append(f"{url[:110]}: {type(error).__name__}: {error}")
                notify("retry", f"Descarga fallida: {type(error).__name__}; comprobando alternativa…")
            finally:
                temporary.unlink(missing_ok=True)
        raise RuntimeError("Falló la descarga del cubo desde IRSA/AWS. " + " | ".join(attempts))

def extract_dr1_cube_spectrum(fits_path, coord):
    """Extrae un quick-look para cada canal, sin interpolar puntos faltantes.

    La matriz FITS se guarda como (lambda, y, x). El valor presentado es la
    mediana superficial de una apertura 3x3 centrada en las coordenadas WCS.
    No es espectrofotometría PSF de una fuente puntual.
    """
    with fits.open(fits_path, memmap=True, lazy_load_hdus=True) as hdul:
        for required in ("IMAGE", "NHITS", "FLAGS", "SPECTRAL_CHANNELS"):
            if required not in hdul:
                raise RuntimeError(f"Falta la extensión FITS requerida: {required}")
        image_hdu = hdul["IMAGE"]
        data = image_hdu.data
        hits = hdul["NHITS"].data
        flags = hdul["FLAGS"].data
        if data.ndim != 3 or data.shape[0] != 102:
            raise RuntimeError(f"Forma inesperada del cubo: {data.shape}")
        if hits.shape != data.shape or flags.shape != data.shape:
            raise RuntimeError("NHITS/FLAGS tienen dimensiones incompatibles con IMAGE.")

        # El FITS de SPHEREx define los ejes astronómicos en WCS con fobj.
        wcs = WCS(image_hdu.header, fobj=hdul).celestial
        x, y = wcs.world_to_pixel(coord)
        if not (np.isfinite(x) and np.isfinite(y)):
            raise RuntimeError("La proyección WCS del objetivo no es finita.")
        x = int(np.rint(x))
        y = int(np.rint(y))
        if not (1 <= x < data.shape[2] - 1 and 1 <= y < data.shape[1] - 1):
            raise RuntimeError("El objetivo cae fuera de la apertura central válida del tile HiPS.")

        # No extraer un espectro si el centro de la huella está fuera de la imagen.
        table = hdul["SPECTRAL_CHANNELS"].data
        column_names = {name.upper(): name for name in (getattr(table, "names", None) or table.dtype.names)}
        if "WAVELENGTH" not in column_names:
            raise RuntimeError("SPECTRAL_CHANNELS carece de columna WAVELENGTH.")
        wave_name = column_names["WAVELENGTH"]
        wave = np.asarray(table[wave_name], dtype=float)
        if wave.shape != (102,):
            raise RuntimeError("Se esperaban 102 longitudes de onda en SPECTRAL_CHANNELS.")
        wave_unit_text = hdul["SPECTRAL_CHANNELS"].columns[wave_name].unit
        if wave_unit_text:
            wave = (wave * u.Unit(wave_unit_text)).to_value(u.um)
        # Si la tabla omite TUNIT, los productos actuales definen micrómetros.
        if not (0.65 < np.nanmin(wave) and np.nanmax(wave) < 5.5):
            raise RuntimeError("Longitudes de onda no compatibles con µm; revisar TUNIT.")

        aperture = data[:, y-1:y+2, x-1:x+2]
        counts = hits[:, y-1:y+2, x-1:x+2]
        flag_aperture = flags[:, y-1:y+2, x-1:x+2]
        # Mantener NaN de huecos y excluir contribuciones sin observaciones.
        valid = np.isfinite(aperture) & (counts > 0)
        results = []
        missing = []
        for channel in range(102):
            channel_number = channel + 1
            if channel_number in (51, 52):
                missing.append({"channel": channel_number, "reason": "Canal sin datos (BLANKCH)"})
                continue
            useful = valid[channel]
            if not useful.any():
                missing.append({"channel": channel_number, "reason": "Sin cobertura válida (NHITS=0 o NaN)"})
                continue
            value = float(np.median(aperture[channel][useful]))
            bitmask = 0
            for val in flag_aperture[channel][useful].ravel():
                bitmask |= int(val) & 0xFFFFFFFF
            results.append({
                "channel": channel_number,
                "wavelength_um": float(wave[channel]),
                "signal_proxy": value,
                "unit": str(image_hdu.header.get("BUNIT", "MJy/sr")),
                "detector": f"D{channel // 17 + 1}",
                "bandpass": f"SPHEREx-D{channel // 17 + 1}",
                "wavelength_method": "DR1 SPECTRAL_CHANNELS",
                "center_flag_bitmask": int(flag_aperture[channel, 1, 1]) & 0xFFFFFFFF,
                "center_flag_names": decode_spherex_flags(int(flag_aperture[channel, 1, 1])),
                "center_has_caution_flags": bool(bitmask & SPHEREX_CAUTION_MASK),
                "aperture_bad_flag_fraction": float(np.count_nonzero(
                    (flag_aperture[channel][useful].astype(np.int64) & SPHEREX_CAUTION_MASK) != 0
                ) / np.count_nonzero(useful)),
                "nhits_median": float(np.median(counts[channel][useful])),
                "valid_pixels": int(np.count_nonzero(useful)),
                "obs_id": Path(fits_path).stem,
                "observation_time_mjd": None,
            })
        return sorted(results, key=lambda p: p["wavelength_um"]), missing

def get_dr1_cube_spectrum(coord, radius, progress=None):
    """Devuelve respuesta compatible con el gráfico JS existente, usando SIA2.

    No reemplaza el cubo por una línea inventada si IRSA está desconectado.
    """
    if not 0 < radius <= 5:
        raise ValueError("Radio inválido; se requiere 0 < radius <= 5 grados.")
    cache_key = make_hash(
        f"dr1-cube-spectrum-v1|{coord.ra.deg:.8f}|{coord.dec.deg:.8f}"
    )
    cache_path = SPECTRUM_CACHE_DIR / f"{cache_key}.json"
    if cache_path.exists() and time.time() - cache_path.stat().st_mtime < SPECTRUM_CACHE_TTL:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("measurement") == "signal_proxy" and cached.get("data_product") == SPHEREX_CUBE_COLLECTION:
                cached["metadata_source"] = "cube-spectrum-cache"
                return cached
        except (OSError, ValueError):
            pass

    # SPX_LOCAL_CUBE_FIRST_V1
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

    if progress is not None:
        progress(stage="search", message="Buscando cubos espectrales DR1 en IRSA…")

    # Consulta angular pequeña, independiente del radio de búsqueda para L2.
    # No recorrer varias decenas de tiles: probar solo tres como máximo.
    records, source = search_spherex_with_retry(coord, 0.002, SPHEREX_CUBE_COLLECTION)
    if not records:
        raise RuntimeError("IRSA SIA2 no devolvió tiles para spherex_dr1_cube.")
    failures = []
    for record in records[:3]:
        try:
            fits_path, download_source = download_dr1_cube_cached(record, progress=progress)
            if progress is not None:
                progress(stage="extraction", message="Extrayendo señal de los 102 canales…")
            spectrum, missing = extract_dr1_cube_spectrum(fits_path, coord)
            if not spectrum:
                failures.append(f"{record.get('obs_id')}: sin canales válidos en esa posición")
                continue
            response = {
                "collection": "spherex_dr1",
                "data_product": SPHEREX_CUBE_COLLECTION,
                "method": "dr1_all_sky_cube_102",
                "metadata_source": f"{source}/{download_source}",
                "target": {"ra_deg": float(coord.ra.deg), "dec_deg": float(coord.dec.deg)},
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
            return response
        except Exception as error:
            failures.append(f"{record.get('obs_id')}: {type(error).__name__}: {error}")
    raise RuntimeError("No fue posible extraer el espectro de los tiles encontrados: " + " | ".join(failures))

def select_balanced_spectrum_records(records, limit):
    """Evita que muestrear solo por fecha elimine detectores del espectro."""
    groups = {}
    for record in records:
        detector = record.get("detector") or detector_from_bandpass(
            record.get("bandpass"), record.get("obs_id"), record.get("url")
        ) or "UNKNOWN"
        groups.setdefault(detector, []).append(record)
    if len(records) <= limit:
        return records
    # Intercalado por detector, con fechas distribuidas dentro de cada detector.
    for det, items in list(groups.items()):
        indices = np.linspace(0, len(items)-1, min(limit, len(items)), dtype=int)
        groups[det] = [items[int(i)] for i in indices]
    result = []
    while len(result) < limit and any(groups.values()):
        for detector in sorted(groups):
            if groups[detector] and len(result) < limit:
                result.append(groups[detector].pop(0))
    return result

def aggregate_spectral_points(raw_points):
    """Reduce columnas verticales: mediana por detector y bin ~0.5% en λ.

    Agrupar tomas repetidas no significa reconstruir los 102 canales del cubo DR1.
    Conservamos los valores por observación en samples_raw para trazabilidad.
    """
    buckets = {}
    for point in raw_points:
        wavelength = point.get("wavelength_um")
        if wavelength is None or wavelength <= 0:
            continue
        key = (point.get("detector"), round(np.log(wavelength) / np.log(1.005)))
        buckets.setdefault(key, []).append(point)
    result = []
    for items in buckets.values():
        wave = np.array([item["wavelength_um"] for item in items], dtype=float)
        signal = np.array([item["signal_proxy"] for item in items], dtype=float)
        representative = dict(items[0])
        representative["wavelength_um"] = float(np.median(wave))
        representative["signal_proxy"] = float(np.median(signal))
        representative["observations_aggregated"] = len(items)
        representative["signal_scatter_mad"] = float(1.4826*np.median(np.abs(signal-np.median(signal))))
        representative["obs_id"] = items[0]["obs_id"] if len(items)==1 else "multiple"
        # No heredar sin más los flags de la primera exposición: conservar
        # la unión de advertencias y la peor fracción de la serie agrupada.
        combined_flags = 0
        for item in items:
            combined_flags |= int(item.get("center_flag_bitmask") or 0) & 0xFFFFFFFF
        representative["center_flag_bitmask"] = combined_flags
        representative["center_flag_names"] = decode_spherex_flags(combined_flags)
        representative["center_has_caution_flags"] = bool(combined_flags & SPHEREX_CAUTION_MASK)
        for key in ("flagged_fraction", "bad_flag_fraction", "aperture_bad_flag_fraction"):
            valid = [float(item[key]) for item in items if item.get(key) is not None]
            representative[key] = max(valid) if valid else None
        result.append(representative)
    return sorted(result, key=lambda item: item["wavelength_um"])

