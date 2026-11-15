# SPHEREx Explorer v14 — Radios múltiples, caché compatible y campo WCS

## Propósito

La aplicación conserva sus cinco módulos. Esta versión cambia cuatro archivos:
- `spherex_data.py`: índice de inventario por centro/radio/colección, recuperación desde regiones guardadas, `offline_only`, `refresh_metadata`.
- `spherex_analysis.py`: reproyección WCS del campo angular según radio para TIMELAPSE, COADD y SUBTRACTION, sin modificar los FITS originales.
- `viewer.py`: selector de vista («radio real» o «escala nativa») y controles de caché / actualización; advertencias de cobertura parcial.
- `main.py`: servidor v14, informes de estado de inventario; conserva el mosaico Gaia/AllWISE v13.

`astronomy_catalogs.py` es exactamente el de la versión v11 proporcionada por el usuario, con Gaia, AllWISE, unWISE y NEOWISE-R. **No se modifica.**

## Instalación en el proyecto Windows existente

1. Cierre Flask con `Ctrl+C`.
2. Abra PowerShell en `C:\Users\ELITEBOOK\Downloads\SPHEREx_Explorer_5_modulos\SPHEREx-Explorer` (o su carpeta real).
3. Active el entorno virtual habitual.
4. Haga copias:

```powershell
Copy-Item .\main.py .\main_respaldo_antes_v14.py -Force
Copy-Item .\spherex_data.py .\spherex_data_respaldo_antes_v14.py -Force
Copy-Item .\spherex_analysis.py .\spherex_analysis_respaldo_antes_v14.py -Force
Copy-Item .\viewer.py .\viewer_respaldo_antes_v14.py -Force
```

5. Descargue `SPHEREx_v14_SOLO_CAMBIOS.zip` y extraiga cuatro archivos en la carpeta actual:

```powershell
Expand-Archive "$HOME\Downloads\SPHEREx_v14_SOLO_CAMBIOS.zip" -DestinationPath . -Force
python -m py_compile .\main.py .\spherex_data.py .\spherex_analysis.py .\astronomy_catalogs.py .\viewer.py
python .\diagnostico_radios_v14.py
python .\main.py
```

6. En el navegador `http://127.0.0.1:5000`, pulse `Ctrl+F5`.

**No borre la caché** `C:\Users\ELITEBOOK\Documents\Proyectos\SPHEREx\cache`.

## Cómo funciona

- Campo visual seleccionado: el ancho nominal del cuadrado en el centro es `2 × radio`, reproyectado sobre una salida de 360 × 360 píxeles. La interpolación **no aumenta la resolución científica** de los detectores. **Advertencia geométrica:** la búsqueda remota SIA2 sigue siendo un cono de radio `r`; las cuatro esquinas del cuadrado visible se extienden hasta `r × √2` desde el centro. Allí no se garantiza inventario completo incluso cuando SIA2 responda: consulte la cobertura de los píxeles y use radios con margen si requiere las esquinas.
- Escala nativa: reproduce la vista previa a 360 px anterior, sin cambiar su campo angular con el radio.
- Inventario exacto: reutiliza la consulta guardada; no necesita IRSA.
- Caché contenida: una búsqueda almacenada mayor cubre el nuevo cono, pero se utilizan **candidatos** que deberán pasar por la validación de píxeles; puede haber productos extra.
- Caché parcial: una búsqueda menor cubre el centro del nuevo campo, pero no garantiza todas las observaciones. El resultado se marca como **inventario parcial** y puede mostrar bordes vacíos.
- Solo caché local: evita consultar IRSA. Si no hay ningún inventario compatible, devuelve una explicación clara.
- Actualizar inventario: intenta consultar SIA2 otra vez. Cuando IRSA responde correctamente, guarda una entrada exacta nueva para ese radio.

**Importante:** un archivo FITS o recorte existente no garantiza cobertura completa de campos angulares mayores. Las regiones no observadas quedan en `NaN`, sin generar fuentes falsas. Nunca se puede fabricar un inventario completo de observaciones nuevas con IRSA caído y sin datos locales.

## Radios recomendados

Mismo centro `17h57m48.5s / +04d41m36s`, colección `spherex_dr1`, 8 fotogramas:

| Radio | Significado con la caché conocida de 0,0211° |
| --- | --- |
| 0,0100° | Región interna; candidatos de inventario contenedor |
| 0,0150° | Región interna; candidatos de inventario contenedor |
| 0,0211° | Inventario exacto guardado: 241 productos |
| 0,0300° | El inventario de 0,0211° es **parcial** para el radio mayor |
| 0,0500° | Idem: puede faltar cobertura; prueba de campo más amplio |
| 0,1000° | Prueba de estrés; pueden quedar grandes áreas sin datos |

Al seleccionar **Solo caché local**, estas pruebas no hacen solicitudes a IRSA. Consulte el campo `metadata_source` y las advertencias del resumen.

## Comprobación automática

En otra terminal con Flask en marcha:

```powershell
.\PRUEBA_V14_RADIOS.ps1
```

El script prueba 5 radios en orden, informa cantidad de fotogramas, origen del inventario y cobertura WCS. No modifica los datos almacenados. Puede generar archivos PNG/GIF de salida en el directorio habitual de trabajos.

## API

`GET /api/health`: `radius_view_enabled`, `compatible_metadata_cache_enabled`.

`POST /api/jobs` acepta:

```json
{
  "ra": "17h57m48.5s", "dec": "+04d41m36s",
  "radius": 0.03, "crop_size": 360, "max_frames": 8, "fps": 2,
  "collection": "spherex_dr1", "mode": "timelapse", "detector": "ALL",
  "view_mode": "radius", "offline_only": true, "refresh_metadata": false
}
```

`GET /api/jobs/<job_id>` incluye en `summary`: `metadata_source`, `inventory_coverage`, `inventory_complete`, `coverage_warning` cuando corresponde, `visible_radius_deg` y porcentaje de píxeles finitos en el campo reproyectado.

## Reversión

Detenga Flask; ejecute:

```powershell
Copy-Item .\main_respaldo_antes_v14.py .\main.py -Force
Copy-Item .\spherex_data_respaldo_antes_v14.py .\spherex_data.py -Force
Copy-Item .\spherex_analysis_respaldo_antes_v14.py .\spherex_analysis.py -Force
Copy-Item .\viewer_respaldo_antes_v14.py .\viewer.py -Force
python -m py_compile .\main.py .\spherex_data.py .\spherex_analysis.py .\viewer.py
python .\main.py
```

## Qué se comprobó en la entrega

- Sintaxis Python de los cinco módulos (compilación).
- Sintaxis JavaScript del visor (`node --check`).
- Pruebas aisladas con inventario simulado: radio exacto, región mayor, región menor, otra coordenada y otra colección, respuesta HTTP 502 simulada, nuevos metadatos.
- Reproyección angular WCS con modelo geométrico sintético, para radios 0,0100–0,1000° y salida 360 px.

**No fue posible ejecutar una validación integrada con Astropy, reproject y Flask, ni consultar IRSA desde este entorno.** La aceptación final de WCS, calidad científica y descargas requiere ejecutar `PRUEBA_V14_RADIOS.ps1` en el Windows que contiene los FITS originales.
