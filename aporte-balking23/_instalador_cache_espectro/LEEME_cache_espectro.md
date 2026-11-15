# Caché local de cubos espectrales DR1 — SPHEREx Explorer

Este parche solo modifica `backend/spherex_explorer/spherex_analysis.py` y crea un respaldo fechado.

El backend ya dispone de caché JSON para consultas repetidas y caché de FITS por identificador de producto. El cambio añade una búsqueda **local primero**: antes de consultar IRSA, intenta extraer el espectro desde cubos `cache/fits/cube_dr1_*.fits` que ya estén guardados. La extracción existente comprueba la cobertura WCS, `NHITS`, las extensiones y las longitudes de onda. Si ningún cubo sirve, utiliza la consulta original a IRSA.

No cambia TIMELAPSE, COADD, SUBTRACTION ni la interfaz. No borra FITS ni inventa valores de los canales 51 y 52. No garantiza acelerar consultas fuera de los cubos disponibles.

## Instalar (PowerShell)

Desde la raíz del proyecto, copia el instalador descargado y ejecútalo:

```powershell
cd "C:\Users\dilan\Documents\spherex-explorer"
Copy-Item "$HOME\Downloads\instalar_cache_espectro.py" . -Force
.\.venv\Scripts\python.exe .\instalar_cache_espectro.py
.\.venv\Scripts\python.exe -m py_compile .\backend\spherex_explorer\spherex_analysis.py
```

Reinicia Flask en la terminal 1 y vuelve a consultar el espectro. Si el cubo ya cubre esas coordenadas, el resultado tendrá `metadata_source: local-cube-cache`, salvo que el caché JSON exacto responda primero (`cube-spectrum-cache`).

## Verificación

Para medir el tiempo en una consulta directa, con Flask detenido o sin una consulta activa:

```powershell
@'
import time
from astropy.coordinates import SkyCoord
import astropy.units as u
from backend.spherex_explorer.spherex_analysis import get_dr1_cube_spectrum
p = SkyCoord(ra=269.46875*u.deg, dec=4.693333*u.deg)
t0 = time.perf_counter()
r = get_dr1_cube_spectrum(p, 0.02)
print('Segundos:', round(time.perf_counter()-t0, 2))
print('Fuente:', r.get('metadata_source'))
print('Canales:', r.get('valid_channels'), '/', r.get('nominal_channels'))
'@ | .\.venv\Scripts\python.exe -
```

Si necesitas revertir, reemplaza `spherex_analysis.py` por el respaldo `spherex_analysis.backup_YYYYMMDD_HHMMSS.py` creado por el instalador y reinicia Flask.
