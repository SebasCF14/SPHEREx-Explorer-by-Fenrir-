"""Visor HTML/CSS/JavaScript original, conservado sin cambios de diseño.

Para un futuro frontend React, basta con reemplazar este módulo.

"""



VIEWER_HTML = r"""

<!DOCTYPE html>

<html lang="es">

<head>

<meta charset="UTF-8">

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>SPHEREx Explorer</title>



<style>

:root {

    color-scheme: dark;

    --bg: #090d18;

    --panel: #111a2b;

    --panel2: #17243a;

    --line: #293b58;

    --text: #edf3ff;

    --muted: #9aabc5;

    --accent: #68c9e8;

    --accent2: #a5e6f4;

    --good: #55d6a1;

    --warn: #ffc66d;

    --bad: #ff7b85;

}



* { box-sizing: border-box; }



body {

    margin: 0;

    background:

        radial-gradient(circle at 50% -20%, #1c3556 0, transparent 42%),

        var(--bg);

    color: var(--text);

    font-family: Segoe UI, Arial, sans-serif;

    min-height: 100vh;

}



header {

    border-bottom: 1px solid var(--line);

    padding: 20px 5vw;

    display: flex;

    justify-content: space-between;

    align-items: center;

    gap: 16px;

}



.brand {

    display: flex;

    align-items: center;

    gap: 13px;

}



.logo {

    width: 42px;

    height: 42px;

    border-radius: 13px;

    display: grid;

    place-items: center;

    background: linear-gradient(135deg, #1b789a, #253d72);

    font-size: 21px;

}



h1 {

    margin: 0;

    font-size: 21px;

    letter-spacing: .4px;

}



.subtitle {

    margin-top: 3px;

    color: var(--muted);

    font-size: 12px;

}



.status-pill {

    border: 1px solid #32634f;

    background: #102c27;

    color: var(--good);

    border-radius: 99px;

    padding: 7px 12px;

    font-size: 12px;

}



main {

    width: min(1600px, 94vw);

    margin: 28px auto 60px;

}



.intro {

    margin-bottom: 22px;

}



.intro h2 {

    font-size: clamp(22px, 3vw, 31px);

    margin: 0 0 8px;

}



.intro p {

    margin: 0;

    color: var(--muted);

    line-height: 1.55;

    max-width: 780px;

}



.layout {

    display: grid;

    grid-template-columns: minmax(320px, 360px) minmax(0, 1fr);

    gap: 18px;

    align-items: start;

}



.panel {

    background: rgba(17, 26, 43, .94);

    border: 1px solid var(--line);

    border-radius: 16px;

    padding: 19px;

    box-shadow: 0 14px 40px rgba(0,0,0,.18);

}



.panel h3 {

    margin: 0 0 16px;

    font-size: 15px;

}



label {

    display: block;

    color: var(--muted);

    font-size: 12px;

    margin: 12px 0 6px;

}



input, select {

    width: 100%;

    background: #0b1424;

    border: 1px solid #344765;

    border-radius: 8px;

    padding: 10px 11px;

    color: var(--text);

    outline: none;

}



input:focus, select:focus {

    border-color: var(--accent);

}



.two {

    display: grid;

    grid-template-columns: 1fr 1fr;

    gap: 10px;

}



button, .download {

    border: 0;

    border-radius: 9px;

    padding: 10px 13px;

    cursor: pointer;

    font-weight: 600;

    color: #07131c;

    background: var(--accent);

    text-decoration: none;

    display: inline-flex;

    align-items: center;

    justify-content: center;

    gap: 7px;

}



button:hover, .download:hover {

    background: var(--accent2);

}



button:disabled {

    opacity: .4;

    cursor: not-allowed;

}



.primary {

    width: 100%;

    margin-top: 18px;

    padding: 12px;

}



.hint {

    color: var(--muted);

    font-size: 11px;

    line-height: 1.5;

    margin-top: 12px;

}



.viewer {

    min-height: 520px;

}



.image-stage {

    background: #03060c;

    border: 1px solid #27364d;

    border-radius: 12px;

    min-height: 620px;

    display: grid;

    place-items: center;

    overflow: hidden;

    padding: 18px;

}



#frameImage {

    width: min(100%, 580px);

    max-width: 580px;

    max-height: 580px;

    height: auto;

    object-fit: contain;

    image-rendering: auto;

    display: none;

    box-shadow: 0 0 35px rgba(69, 164, 207, .12);

}



.placeholder {

    text-align: center;

    color: var(--muted);

    max-width: 360px;

    line-height: 1.6;

}



.placeholder .symbol {

    font-size: 42px;

    margin-bottom: 12px;

    color: var(--accent);

}



.frame-info {

    display: flex;

    justify-content: space-between;

    align-items: center;

    gap: 12px;

    margin: 13px 0;

    flex-wrap: wrap;

}



.frame-title {

    font-weight: 650;

}



.frame-date {

    color: var(--muted);

    font-size: 12px;

    margin-top: 4px;

}



.controls {

    display: flex;

    flex-wrap: wrap;

    align-items: center;

    gap: 9px;

}



.controls button {

    min-width: 42px;

    padding: 10px 12px;

}



.controls select {

    width: auto;

    min-width: 90px;

}



#frameSlider {

    width: 100%;

    margin: 13px 0 4px;

    accent-color: var(--accent);

}



.progress-wrap {

    margin-top: 16px;

    background: #08111e;

    border: 1px solid var(--line);

    border-radius: 10px;

    padding: 12px;

}



.progress-label {

    display: flex;

    justify-content: space-between;

    gap: 10px;

    color: var(--muted);

    font-size: 12px;

    margin-bottom: 9px;

}



.progress-track {

    height: 7px;

    background: #26344a;

    border-radius: 99px;

    overflow: hidden;

}



#progressBar {

    width: 0;

    height: 100%;

    background: linear-gradient(90deg, #3a9fc4, #75dfd2);

    transition: width .25s ease;

}



.message {

    font-size: 12px;

    color: var(--muted);

    margin-top: 9px;

    line-height: 1.45;

}



.message.error { color: var(--bad); }

.message.success { color: var(--good); }
.message.warning { color: #f6bd60; }



.viewer-footer {

    display: flex;

    justify-content: space-between;

    align-items: center;

    flex-wrap: wrap;

    gap: 12px;

    margin-top: 15px;

}



.small-note {

    color: var(--muted);

    font-size: 11px;

    line-height: 1.5;

}



.download {

    display: none;

}



.stats {

    display: grid;

    grid-template-columns: repeat(3, 1fr);

    gap: 9px;

    margin-top: 14px;

}



.stat {

    background: var(--panel2);

    border: 1px solid var(--line);

    border-radius: 9px;

    padding: 11px;

}



.stat strong {

    display: block;

    font-size: 17px;

}



.stat span {

    color: var(--muted);

    font-size: 10px;

}



.analysis-grid {

    display: grid;

    grid-template-columns: 1fr 1fr;

    gap: 10px;

    margin-top: 12px;

}



.analysis-output {

    width: 100%;

    min-height: 120px;

    max-height: 300px;

    overflow: auto;

    white-space: pre-wrap;

    overflow-wrap: anywhere;

    background: #08111e;

    border: 1px solid var(--line);

    border-radius: 9px;

    color: var(--muted);

    padding: 12px;

    font-size: 11px;

    line-height: 1.5;

}



@media (max-width: 850px) {

    .layout { grid-template-columns: 1fr; }

    .viewer { min-height: 0; }

    .image-stage { min-height: 400px; }

    #frameImage { width: min(100%, 360px); max-height: 360px; }

}



@media (max-width: 520px) {

    header { padding: 15px 4vw; }

    .status-pill { display: none; }

    main { width: 94vw; margin-top: 18px; }

    .image-stage { min-height: 320px; }

    #frameImage { width: min(100%, 280px); max-height: 280px; }

    .panel { padding: 14px; }

    .stats { grid-template-columns: 1fr 1fr; }

}



.tools-hub {

    margin: 0 0 20px;

    padding: 18px;

    border: 1px solid var(--line);

    border-radius: 16px;

    background: linear-gradient(135deg, rgba(19, 38, 61, .96), rgba(13, 22, 38, .96));

    box-shadow: 0 12px 34px rgba(0,0,0,.16);

}



.tools-hub-heading {

    display: flex;

    justify-content: space-between;

    align-items: end;

    gap: 12px;

    margin-bottom: 13px;

}



.tools-hub-heading h3 {

    margin: 0 0 5px;

    font-size: 16px;

}



.tools-hub-heading p {

    margin: 0;

    color: var(--muted);

    font-size: 12px;

    line-height: 1.5;

}



.tools-count {

    color: var(--accent2);

    border: 1px solid var(--line);

    border-radius: 99px;

    padding: 5px 10px;

    font-size: 11px;

    white-space: nowrap;

}



.tool-shortcuts {

    display: grid;

    grid-template-columns: repeat(3, minmax(0, 1fr));

    gap: 10px;

}



.tool-shortcut {

    display: flex;

    align-items: center;

    gap: 12px;

    min-width: 0;

    padding: 13px;

    border: 1px solid #314766;

    border-radius: 12px;

    background: rgba(7, 17, 31, .72);

    color: var(--text);

    text-decoration: none;

    transition: border-color .18s ease, transform .18s ease, background .18s ease;

}



.tool-shortcut:hover {

    border-color: var(--accent);

    background: rgba(24, 55, 78, .78);

    transform: translateY(-2px);

}



.tool-icon {

    width: 38px;

    height: 38px;

    flex: 0 0 38px;

    display: grid;

    place-items: center;

    border-radius: 11px;

    color: #07131c;

    background: var(--accent);

    font-size: 20px;

    font-weight: 700;

}



.tool-shortcut strong {

    display: block;

    font-size: 13px;

    margin-bottom: 3px;

}



.tool-shortcut small {

    display: block;

    color: var(--muted);

    font-size: 11px;

    line-height: 1.4;

}



.tool-arrow {

    margin-left: auto;

    color: var(--accent2);

    font-size: 18px;

}



#catalog-tool, #spectrum-tool, #wise-tools {

    scroll-margin-top: 22px;

}



.fixed-resolution {

    min-height: 42px;

    display: flex;

    flex-direction: column;

    justify-content: center;

    gap: 2px;

    padding: 7px 11px;

    border: 1px solid #344765;

    border-radius: 8px;

    background: #0b1424;

}



.fixed-resolution strong {

    color: var(--accent2);

    font-size: 14px;

}



.fixed-resolution span {

    color: var(--muted);

    font-size: 10px;

}



.field-note {

    margin-top: 5px;

    color: var(--muted);

    font-size: 10px;

    line-height: 1.4;

}



.spectrum-chart-wrap {

    margin-top: 12px;

    padding: 8px;

    border: 1px solid var(--line);

    border-radius: 11px;

    background: #08111e;

}



#spectrumCanvas {

    display: block;

    width: 100%;

    height: auto;

    border-radius: 7px;

}



.spectrum-actions {

    display: flex;

    flex-wrap: wrap;

    gap: 8px;

    margin-top: 9px;

}



.spectrum-actions button {

    font-size: 11px;

    padding: 8px 11px;

}



.technical-details {

    margin-top: 12px;

    border: 1px solid var(--line);

    border-radius: 9px;

    background: #08111e;

}



.technical-details summary {

    cursor: pointer;

    padding: 10px 12px;

    color: var(--accent2);

    font-size: 11px;

    font-weight: 600;

}



.technical-details .analysis-output {

    margin: 0;

    border: 0;

    border-top: 1px solid var(--line);

}



@media (max-width: 850px) {

    .tool-shortcuts { grid-template-columns: 1fr; }

}



.wise-links {

    display: flex;

    flex-wrap: wrap;

    gap: 8px;

    margin-top: 12px;

}

.wise-links a {

    display: inline-block;

    padding: 8px 11px;

    border: 1px solid var(--border, #394150);

    border-radius: 9px;

    color: var(--text, #dbe4ef);

    text-decoration: none;

    font-size: 0.82rem;

}

.wise-links a:hover {

    border-color: var(--accent, #5da9dd);

}

#wisePreview {

    display: none;

    width: 100%;

    max-height: 440px;

    object-fit: contain;

    background: #05070b;

}



</style>

</head>



<body>

<header>

    <div class="brand">

        <div class="logo">✦</div>

        <div>

            <h1>SPHEREx Explorer</h1>

            <div class="subtitle">Exploración multimisiones · SPHEREx, WISE y Gaia DR3</div>

        </div>

    </div>

    <div class="status-pill">● Backend local</div>

</header>



<main>

    <section class="intro">

        <h2>Observa el cielo en infrarrojo</h2>

        <p>

            Consulta imágenes infrarrojas de SPHEREx y WISE/NEOWISE, y compara

            sus campos con fuentes astrométricas de Gaia DR3 y AllWISE.

        </p>

    </section>



    <section class="tools-hub" aria-label="Accesos rápidos a herramientas científicas">

        <div class="tools-hub-heading">

            <div>

                <h3>Herramientas científicas</h3>

                <p>Accede directamente a los módulos de análisis y consulta desde esta página.</p>

            </div>

            <span class="tools-count">3 módulos</span>

        </div>

        <div class="tool-shortcuts">

            <a class="tool-shortcut" href="#catalog-tool">

                <span class="tool-icon">✧</span>

                <span>

                    <strong>Catálogos astronómicos</strong>

                    <small>Consulta Gaia DR3 y AllWISE; superpone sus fuentes sobre las imágenes.</small>

                </span>

                <span class="tool-arrow">↗</span>

            </a>

            <a class="tool-shortcut" href="#spectrum-tool">

                <span class="tool-icon">∿</span>

                <span>

                    <strong>Análisis espectral</strong>

                    <small>Explora la señal por longitud de onda y exporta los resultados.</small>

                </span>

                <span class="tool-arrow">↗</span>

            </a>

            <a class="tool-shortcut" href="#wise-tools">

                <span class="tool-icon">◉</span>

                <span>

                    <strong>Imágenes WISE / NEOWISE</strong>

                    <small>Consulta exposiciones infrarrojas y atlas en distintas bandas.</small>

                </span>

                <span class="tool-arrow">↗</span>

            </a>

        </div>

    </section>



    <div class="layout">

        <section class="panel">

            <h3>Parámetros de observación</h3>



            <form id="queryForm">

                <label for="ra">Ascensión recta (RA)</label>

                <input id="ra" value="17h57m48.5s" required>



                <label for="dec">Declinación (Dec)</label>

                <input id="dec" value="+04d41m36s" required>



                <div class="two">

                    <div>

                        <label for="radius">Radio de búsqueda y vista (grados)</label>

                        <input id="radius" type="number" min="0.0001" max="5"

                               step="0.0001" value="0.02">

                    </div>

                    <div>

                        <label for="maxFrames" id="maxFramesLabel">Fotogramas del timelapse</label>

                        <input id="maxFrames" type="number" min="4" max="20"

                               step="1" value="8">

                        <div class="field-note" id="maxFramesHint">Entre 4 y 20 fotogramas.</div>

                    </div>

                </div>

                <label for="viewMode">Visualización del campo</label>
                <select id="viewMode">
                    <option value="radius" selected>Mostrar el radio seleccionado (WCS, 360 × 360)</option>
                    <option value="native">Escala nativa del detector (modo anterior)</option>
                </select>
                <div class="field-note">El radio define la mitad del ancho visible cuando se usa WCS. La imagen siempre mide 360 × 360 px; ampliar no añade resolución. Las esquinas del cuadrado pueden exceder el cono de búsqueda; sin IRSA puede haber cobertura parcial.</div>
                <div class="field-note" style="margin-top:8px;">
                    <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                        <input id="offlineOnly" type="checkbox" style="width:auto;">
                        Solo caché local (no esperar a IRSA)
                    </label>
                    <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                        <input id="refreshMetadata" type="checkbox" style="width:auto;">
                        Intentar actualizar inventario desde IRSA
                    </label>
                </div>



                <div class="two">

                    <div>

                        <label>Resolución de salida</label>

                        <div class="fixed-resolution">

                            <strong>360 × 360 px</strong>

                            <span>Fija para TIMELAPSE, COADD y SUBTRACTION</span>

                        </div>

                    </div>

                    <div id="fpsField">

                        <label for="fps">Velocidad del GIF (FPS)</label>

                        <input id="fps" type="number" min="1" max="20"

                               value="2">

                    </div>

                </div>



                <label for="collection">Colección de datos</label>

                <select id="collection">

                    <option value="spherex_dr1">SPHEREx DR1 · Wide</option>

                    <option value="spherex_dr1_deep">SPHEREx DR1 · Deep</option>

                    <option value="spherex_qr3">SPHEREx QR3 · Wide</option>

                    <option value="spherex_qr3_deep">SPHEREx QR3 · Deep</option>

                </select>



                <div class="two">

                    <div>

                        <label for="mode">Modo de procesamiento</label>

                        <select id="mode">

                            <option value="timelapse">Timelapse</option>

                            <option value="coadd">COADD</option>

                            <option value="subtraction">SUBTRACTION</option>

                        </select>

                    </div>

                    <div>

                        <label for="detector">Detector</label>

                        <select id="detector">

                            <option value="ALL">Todos</option>

                            <option value="D1">D1</option>

                            <option value="D2">D2</option>

                            <option value="D3">D3</option>

                            <option value="D4">D4</option>

                            <option value="D5">D5</option>

                            <option value="D6">D6</option>

                        </select>

                    </div>

                </div>



                <button class="primary" id="generateButton" type="submit">

                    ✦ Generar secuencia temporal

                </button>

            </form>



            <div class="hint">

                La salida se conserva siempre en 360 × 360 píxeles y se centra

                mediante el WCS de cada FITS. Para evitar mezclar bandas, cuando

                eliges «Todos» se selecciona el grupo detector/banda con más

                observaciones. COADD y SUBTRACTION requieren imágenes compatibles

                y reproyección WCS.

            </div>



            <div class="progress-wrap">

                <div class="progress-label">

                    <span id="stageLabel">Esperando consulta</span>

                    <span id="progressText">0/0</span>

                </div>

                <div class="progress-track">

                    <div id="progressBar"></div>

                </div>

                <div class="message" id="statusMessage">

                    Introduce las coordenadas y genera una secuencia.

                </div>

            </div>



            <div class="stats">

                <div class="stat">

                    <strong id="statFound">—</strong>

                    <span>Observaciones</span>

                </div>

                <div class="stat">

                    <strong id="statFrames">—</strong>

                    <span>Fotogramas</span>

                </div>

                <div class="stat">

                    <strong id="statCache">—</strong>

                    <span>Desde caché</span>

                </div>

            </div>

        </section>



        <section class="panel viewer">

            <h3>Visor infrarrojo temporal</h3>



            <div class="image-stage">

                <div class="placeholder" id="placeholder">

                    <div class="symbol">✧</div>

                    <strong>Sin secuencia cargada</strong>

                    <div>

                        Cuando finalice una consulta, aquí aparecerán

                        los recortes infrarrojos de cada observación.

                    </div>

                </div>

                <img id="frameImage" alt="Fotograma infrarrojo SPHEREx">

            </div>



            <div class="frame-info">

                <div>

                    <div class="frame-title" id="frameTitle">Esperando datos</div>

                    <div class="frame-date" id="frameDate">—</div>

                </div>

                <div class="small-note" id="frameCounter">0 / 0</div>

            </div>



            <input id="frameSlider" type="range" min="0" max="0"

                   value="0" disabled>



            <div class="analysis-grid" style="margin-top:8px;">

                <div>

                    <label for="frameOverlay">Superposición sobre SPHEREx</label>

                    <select id="frameOverlay">

                        <option value="none">Sin catálogo</option>

                        <option value="gaia">Gaia DR3 · fuentes estelares</option>

                        <option value="allwise">AllWISE · fuentes infrarrojas</option>

                    </select>

                </div>

                <div class="small-note" style="align-self:end;">

                    Las posiciones se proyectan con la solución WCS del FITS.

                </div>

            </div>



            <div class="controls">

                <button id="previousButton" disabled title="Fotograma anterior">◀</button>

                <button id="playButton" disabled>▶ Reproducir</button>

                <button id="nextButton" disabled title="Fotograma siguiente">▶|</button>

                <select id="speedSelect" disabled title="Velocidad">

                    <option value="0.5">0.5×</option>

                    <option value="1" selected>1×</option>

                    <option value="2">2×</option>

                    <option value="4">4×</option>

                </select>

            </div>



            <div class="viewer-footer">

                <div class="small-note" id="normalizationNote">

                    La escala de brillo se calculará al finalizar la adquisición.

                </div>

                <a class="download" id="downloadGif" href="#" download>

                    ↓ Descargar resultado

                </a>

            </div>

        </section>

    </div>



    <section class="panel" style="margin-top:18px;">

        <h3>Herramientas de análisis</h3>

        <div class="analysis-grid">

            <div id="catalog-tool">

                <label for="catalogType">Catálogo astronómico</label>

                <select id="catalogType">

                    <option value="gaia">Gaia DR3 · Archivo ESA</option>

                    <option value="wise">AllWISE · IRSA TAP</option>

                </select>

                <button id="catalogButton" style="width:100%;margin-top:9px;">

                    Consultar catálogo

                </button>

                <div class="field-note">

                    Después de consultar, selecciona Gaia DR3 o AllWISE en

                    «Superposición sobre SPHEREx», debajo del visor.

                </div>

            </div>

            <div id="spectrum-tool">

                <label>Espectro infrarrojo SPHEREx</label>

                <div class="small-note">

                    Consulta la señal central de las observaciones disponibles

                    en función de la longitud de onda.

                </div>

                <button id="spectrumButton" style="width:100%;margin-top:9px;">

                    Consultar espectro

                </button>

                <div class="spectrum-chart-wrap">

                    <canvas id="spectrumCanvas" width="1100" height="440"

                            aria-label="Gráfico de señal SPHEREx frente a longitud de onda"></canvas>

                </div>

                <div class="small-note" id="spectrumSummary" style="margin-top:8px;">

                    El gráfico aparecerá después de realizar una consulta.

                </div>

                <div class="spectrum-actions">

                    <button id="downloadSpectrumCSV" type="button" disabled>↓ Descargar CSV</button>

                    <button id="downloadSpectrumPNG" type="button" disabled>↓ Descargar gráfico PNG</button>

                </div>

            </div>

        </div>

        <details class="technical-details">

            <summary>Ver datos técnicos de la consulta (JSON)</summary>

            <pre class="analysis-output" id="analysisOutput">Gaia DR3 se consulta en ESA; AllWISE se consulta directamente en IRSA TAP; el análisis espectral usa SPHEREx.</pre>

        </details>

        <div class="small-note">

            Gaia DR3 no es un archivo de fotografías ópticas: proporciona un

            catálogo de fuentes, astrometría y fotometría. Sus posiciones ahora

            pueden superponerse sobre SPHEREx y WISE mediante las coordenadas WCS.

            La señal espectral SPHEREx se presenta como indicador de señal central

            (signal_proxy), no como flujo fotométrico calibrado.

        </div>

    </section>



    <section class="panel" id="wise-tools" style="margin-top:18px;">

        <h3>Imágenes infrarrojas WISE / NEOWISE / unWISE</h3>

        <div class="analysis-grid">

            <div>

                <label for="wiseDataset">Archivo de imágenes</label>

                <select id="wiseDataset">

                    <option value="neowiser">NEOWISE-R · exposiciones L1b</option>

                    <option value="allwise">AllWISE · atlas coadds</option>
                    <option value="unwise">unWISE · imágenes combinadas WISE/NEOWISE (neo1)</option>

                </select>

            </div>

            <div>

                <label for="wiseBand">Banda infrarroja</label>

                <select id="wiseBand">

                    <option value="1">W1 · 3.4 μm</option>

                    <option value="2">W2 · 4.6 μm</option>

                </select>

            </div>

            <div>

                <label for="wiseOverlay">Capa de catálogo</label>

                <select id="wiseOverlay">

                    <option value="none">Sin superposición</option>

                    <option value="gaia">Gaia DR3 · estrellas</option>

                    <option value="allwise">AllWISE · fuentes infrarrojas</option>

                </select>

            </div>

        </div>

        <button id="wiseImagesButton" style="width:100%;margin-top:12px;">

            Consultar imágenes oficiales

        </button>

        <div class="small-note" id="wiseStatus" style="margin-top:10px;">

            NEOWISE-R contiene exposiciones L1b individuales; AllWISE y unWISE

            muestran imágenes combinadas (coadds), no fotogramas de una época.

            Para unWISE, el radio máximo de consulta es 0.35° y las bandas son W1/W2.

        </div>

        <div class="image-stage" style="margin-top:12px;min-height:220px;">

            <div class="placeholder" id="wisePlaceholder">

                <strong>Sin imagen WISE / NEOWISE</strong>

                <div>Realiza una consulta para visualizar el primer recorte FITS.</div>

            </div>

            <img id="wisePreview" alt="Vista previa infrarroja WISE/NEOWISE">

        </div>

        <div class="small-note" id="wiseImageCaption"></div>

        <div id="wiseLinks" class="wise-links"></div>

        <pre class="analysis-output" id="wiseOutput">Los resultados astronómicos de IRSA / unWISE aparecerán aquí.</pre>

        <div class="small-note">

            AllWISE/NEOWISE usan archivos NASA/IPAC IRSA; unWISE usa recortes FITS

            de unWISE (coadds científicos). La vista previa PNG es solo visualización;

            el enlace FITS conserva los datos y su WCS. Los coadds no son exposiciones L1b.

        </div>

    </section>

</main>



<script>

const form = document.getElementById("queryForm");

const generateButton = document.getElementById("generateButton");

const statusMessage = document.getElementById("statusMessage");

const stageLabel = document.getElementById("stageLabel");

const progressText = document.getElementById("progressText");

const progressBar = document.getElementById("progressBar");



const frameImage = document.getElementById("frameImage");

const placeholder = document.getElementById("placeholder");

const frameTitle = document.getElementById("frameTitle");

const frameDate = document.getElementById("frameDate");

const frameCounter = document.getElementById("frameCounter");

const frameSlider = document.getElementById("frameSlider");

const frameOverlay = document.getElementById("frameOverlay");



const previousButton = document.getElementById("previousButton");

const nextButton = document.getElementById("nextButton");

const playButton = document.getElementById("playButton");

const speedSelect = document.getElementById("speedSelect");

const downloadGif = document.getElementById("downloadGif");



const statFound = document.getElementById("statFound");

const statFrames = document.getElementById("statFrames");

const statCache = document.getElementById("statCache");

const normalizationNote = document.getElementById("normalizationNote");

const catalogButton = document.getElementById("catalogButton");

const spectrumButton = document.getElementById("spectrumButton");

const catalogType = document.getElementById("catalogType");

const analysisOutput = document.getElementById("analysisOutput");

const wiseDataset = document.getElementById("wiseDataset");

const wiseBand = document.getElementById("wiseBand");

const wiseOverlay = document.getElementById("wiseOverlay");

const wiseImagesButton = document.getElementById("wiseImagesButton");

const wiseStatus = document.getElementById("wiseStatus");

const wisePreview = document.getElementById("wisePreview");

const wisePlaceholder = document.getElementById("wisePlaceholder");

const wiseImageCaption = document.getElementById("wiseImageCaption");

const wiseLinks = document.getElementById("wiseLinks");

const wiseOutput = document.getElementById("wiseOutput");

const modeSelect = document.getElementById("mode");

const maxFramesInput = document.getElementById("maxFrames");

const maxFramesLabel = document.getElementById("maxFramesLabel");

const maxFramesHint = document.getElementById("maxFramesHint");

const fpsField = document.getElementById("fpsField");

const spectrumCanvas = document.getElementById("spectrumCanvas");

const spectrumSummary = document.getElementById("spectrumSummary");

const downloadSpectrumCSVButton = document.getElementById("downloadSpectrumCSV");

const downloadSpectrumPNGButton = document.getElementById("downloadSpectrumPNG");



let currentJobId = null;

let frames = [];

let currentIndex = 0;

let playbackTimer = null;

let requestedFPS = 2;

let lastWiseImages = [];

let latestSpectrumResult = null;



function updateModeControls() {

    const mode = modeSelect.value;

    let minimum = 4;



    if (mode === "timelapse") {

        minimum = 4;

        maxFramesLabel.textContent = "Fotogramas del timelapse";

        maxFramesHint.textContent = "Entre 4 y 20 fotogramas. Si hay menos observaciones disponibles, se mostrarán las encontradas.";

        fpsField.hidden = false;

        generateButton.textContent = "✦ Generar secuencia temporal";

    } else if (mode === "coadd") {

        minimum = 2;

        maxFramesLabel.textContent = "Observaciones para COADD";

        maxFramesHint.textContent = "Entre 2 y 20 observaciones para combinar.";

        fpsField.hidden = true;

        generateButton.textContent = "✦ Generar imagen COADD";

    } else {

        minimum = 2;

        maxFramesLabel.textContent = "Observaciones para SUBTRACTION";

        maxFramesHint.textContent = "Entre 2 y 20 observaciones compatibles con fecha conocida.";

        fpsField.hidden = true;

        generateButton.textContent = "✦ Generar imagen SUBTRACTION";

    }



    maxFramesInput.min = String(minimum);

    maxFramesInput.max = "20";



    const current = Number(maxFramesInput.value);

    const normalized = Number.isFinite(current) ? Math.trunc(current) : minimum;

    maxFramesInput.value = String(Math.min(20, Math.max(minimum, normalized)));

}



modeSelect.addEventListener("change", updateModeControls);

updateModeControls();



function setMessage(message, type = "") {

    statusMessage.textContent = message;

    statusMessage.className = "message " + type;

}



function stopPlayback() {

    if (playbackTimer !== null) {

        clearInterval(playbackTimer);

        playbackTimer = null;

    }

    playButton.textContent = "▶ Reproducir";

}



function renderFrame(index) {

    if (!frames.length) return;



    currentIndex = Math.max(0, Math.min(index, frames.length - 1));

    const frame = frames[currentIndex];



    const frameUrl = new URL(frame.image_url, window.location.origin);

    if (frameOverlay.value !== "none" && playbackTimer === null) {

        frameUrl.searchParams.set("overlay", frameOverlay.value);

    } else {

        frameUrl.searchParams.delete("overlay");

    }

    // Mostrar primero el fotograma original, aunque el catálogo demore o falle.

    const baseUrl = new URL(frame.image_url, window.location.origin).toString();

    const requestedUrl = frameUrl.toString();

    frameImage.onerror = () => {

        frameImage.onerror = null;

        frameImage.src = baseUrl;

        normalizationNote.textContent = "La capa externa no respondió; se conserva la imagen SPHEREx original.";

    };

    frameImage.src = baseUrl;

    if (requestedUrl !== baseUrl) {

        const overlayImage = new Image();

        overlayImage.onload = () => {

            if (frames[currentIndex]?.image_url === frame.image_url

                && frameOverlay.value !== "none") {

                frameImage.src = requestedUrl;

            }

        };

        overlayImage.onerror = () => {

            normalizationNote.textContent = "Superposición no disponible; imagen SPHEREx original conservada.";

        };

        overlayImage.src = requestedUrl;

    }

    frameImage.style.display = "block";

    placeholder.style.display = "none";



    frameTitle.textContent = frame.label || `Fotograma ${currentIndex + 1}`;

    frameDate.textContent = frame.observation_date || "Fecha no disponible";

    frameCounter.textContent = `${currentIndex + 1} / ${frames.length}`;



    frameSlider.max = String(frames.length - 1);

    frameSlider.value = String(currentIndex);



    previousButton.disabled = frames.length <= 1;

    nextButton.disabled = frames.length <= 1;

}



function playSequence() {

    if (!frames.length) return;



    if (playbackTimer !== null) {

        stopPlayback();

        return;

    }



    const multiplier = Number(speedSelect.value || 1);

    const interval = 1000 / Math.max(1, requestedFPS * multiplier);



    playButton.textContent = "Ⅱ Pausar";



    playbackTimer = setInterval(() => {

        const nextIndex = currentIndex + 1;

        renderFrame(nextIndex >= frames.length ? 0 : nextIndex);

    }, interval);

}



function updateProgress(job) {

    const total = Number(job.total || 0);

    const progress = Number(job.progress || 0);

    const percentage = total > 0 ? (progress / total) * 100 : 0;



    progressBar.style.width = `${Math.max(0, Math.min(100, percentage))}%`;

    progressText.textContent = `${progress}/${total}`;

    stageLabel.textContent = job.stage || "Procesando";

    setMessage(job.message || "Procesando...");

}



async function pollJob(jobId) {

    try {

        const response = await fetch(`/api/jobs/${jobId}`);



        if (!response.ok) {

            throw new Error("No se pudo consultar el estado del trabajo.");

        }



        const job = await response.json();

        updateProgress(job);



        if (job.status === "completed") {

            stopPlayback();



            frames = job.frames || [];

            requestedFPS = Number(job.params.fps || 2);



            if (frames.length) {

                renderFrame(0);

                playButton.disabled = frames.length <= 1;

                speedSelect.disabled = frames.length <= 1;

                frameSlider.disabled = frames.length <= 1;

            }



            previousButton.disabled = frames.length <= 1;

            nextButton.disabled = frames.length <= 1;



            statFound.textContent = job.summary?.observations_found ?? "—";

            statFrames.textContent = job.summary?.frames_generated ?? frames.length;

            statCache.textContent = job.summary?.frames_from_cache ?? 0;



            const spectralGroup = job.summary?.selected_spectral_group;

            const outputSize = Number(job.params?.crop_size || 360);

            const resolutionText = `Salida ${outputSize} × ${outputSize} px`;

            if (job.result_type === "timelapse") {

                normalizationNote.textContent = spectralGroup

                    ? `Escala ZScale común · ${resolutionText} · Grupo: ${spectralGroup.detector} / ${spectralGroup.bandpass}`

                    : `Escala ZScale común · ${resolutionText}: permite comparar el brillo entre fotogramas.`;

            } else {

                const coverage = job.summary?.coverage_percent;

                normalizationNote.textContent = `${resolutionText} · Resultado ${String(job.result_type || "").toUpperCase()}` +

                    (coverage !== undefined ? ` · Cobertura válida: ${coverage}% · Negro = sin datos comparables.` : ".");

            }



            const resultUrl = job.result_url || job.gif_url;

            downloadGif.href = resultUrl || "#";

            downloadGif.textContent =

                job.result_type === "timelapse"

                    ? "↓ Descargar GIF"

                    : "↓ Descargar resultado PNG";

            downloadGif.style.display = resultUrl ? "inline-flex" : "none";



            generateButton.disabled = false;

            const coverageWarning = job.summary?.coverage_warning;
            const fraction = job.summary?.visible_coverage_percent_mean;
            const fovInfo = job.summary?.view_mode === "radius"
                ? ` Campo ±${Number(job.params?.radius).toFixed(4)}°; cobertura media ${fraction ?? "?"}%.`
                : " Vista en escala nativa.";
            const note = coverageWarning ? `${coverageWarning}${fovInfo}`
                : `Secuencia generada correctamente.${fovInfo}`;
            setMessage(note, coverageWarning ? "warning" : "success");

            stageLabel.textContent = "Completado";

            progressBar.style.width = "100%";

            progressText.textContent = `${job.progress}/${job.total}`;

            return;

        }



        if (job.status === "failed") {

            generateButton.disabled = false;

            setMessage(job.error || "La consulta no pudo completarse.", "error");

            stageLabel.textContent = "Error";

            return;

        }



        window.setTimeout(() => pollJob(jobId), 800);



    } catch (error) {

        generateButton.disabled = false;

        setMessage(error.message, "error");

        stageLabel.textContent = "Error de comunicación";

    }

}



form.addEventListener("submit", async (event) => {

    event.preventDefault();

    stopPlayback();



    frames = [];

    currentIndex = 0;

    frameOverlay.value = "none";

    frameImage.style.display = "none";

    placeholder.style.display = "block";

    downloadGif.style.display = "none";



    previousButton.disabled = true;

    nextButton.disabled = true;

    playButton.disabled = true;

    speedSelect.disabled = true;

    frameSlider.disabled = true;



    statFound.textContent = "—";

    statFrames.textContent = "—";

    statCache.textContent = "—";



    generateButton.disabled = true;

    progressBar.style.width = "0%";

    progressText.textContent = "0/0";

    stageLabel.textContent = "Enviando consulta";

    setMessage("Conectando con el backend SPHEREx...");



    const payload = {

        ra: document.getElementById("ra").value.trim(),

        dec: document.getElementById("dec").value.trim(),

        radius: Number(document.getElementById("radius").value),

        max_frames: Number(document.getElementById("maxFrames").value),

        fps: Number(document.getElementById("fps").value),

        collection: document.getElementById("collection").value,

        mode: document.getElementById("mode").value,

        detector: document.getElementById("detector").value,

        use_cutouts: true,
        view_mode: document.getElementById("viewMode").value,
        offline_only: document.getElementById("offlineOnly").checked,
        refresh_metadata: document.getElementById("refreshMetadata").checked

    };



    try {

        const response = await fetch("/api/jobs", {

            method: "POST",

            headers: {"Content-Type": "application/json"},

            body: JSON.stringify(payload)

        });



        const result = await response.json();



        if (response.status === 429) {

            throw new Error(

                result.message || "Ya existe una consulta en proceso."

            );

        }



        if (!response.ok) {

            throw new Error(result.error || "No se pudo iniciar la consulta.");

        }



        currentJobId = result.job_id;

        requestedFPS = payload.fps;



        pollJob(currentJobId);



    } catch (error) {

        generateButton.disabled = false;

        setMessage(error.message, "error");

        stageLabel.textContent = "No iniciado";

    }

});



previousButton.addEventListener("click", () => {

    stopPlayback();

    renderFrame(currentIndex - 1);

});



nextButton.addEventListener("click", () => {

    stopPlayback();

    renderFrame(currentIndex + 1);

});



playButton.addEventListener("click", playSequence);



speedSelect.addEventListener("change", () => {

    if (playbackTimer !== null) {

        stopPlayback();

        playSequence();

    }

});



frameSlider.addEventListener("input", () => {

    stopPlayback();

    renderFrame(Number(frameSlider.value));

});



frameOverlay.addEventListener("change", () => {

    if (frames.length) renderFrame(currentIndex);

});



function currentSkyParameters() {

    return {

        ra: document.getElementById("ra").value.trim(),

        dec: document.getElementById("dec").value.trim(),

        radius: document.getElementById("radius").value,

        collection: document.getElementById("collection").value

    };

}



function renderSpectrumChart(items) {

    const canvas = spectrumCanvas;

    const context = canvas.getContext("2d");

    const width = canvas.width;

    const height = canvas.height;



    context.clearRect(0, 0, width, height);

    context.fillStyle = "#08111e";

    context.fillRect(0, 0, width, height);



    const points = (Array.isArray(items) ? items : [])

        .map(item => ({

            x: item.wavelength_um === null ? NaN : Number(item.wavelength_um),

            y: item.signal_proxy === null ? NaN : Number(item.signal_proxy)

        }))

        .filter(point => Number.isFinite(point.x) && Number.isFinite(point.y))

        .sort((a, b) => a.x - b.x);



    if (!points.length) {

        context.fillStyle = "#9aabc5";

        context.font = "18px Segoe UI, Arial, sans-serif";

        context.textAlign = "center";

        context.fillText("Sin mediciones espectrales para mostrar", width / 2, height / 2);

        return;

    }



    const margin = {left: 92, right: 34, top: 34, bottom: 72};

    context.fillStyle = "#edf3ff";

    context.font = "bold 17px Segoe UI, Arial, sans-serif";

    context.textAlign = "left";

    context.textBaseline = "alphabetic";

    context.fillText(

        `SPHEREx · RA ${document.getElementById("ra").value.trim()} · Dec ${document.getElementById("dec").value.trim()}`,

        margin.left,

        23

    );



    const plotWidth = width - margin.left - margin.right;

    const plotHeight = height - margin.top - margin.bottom;



    let minX = Math.min(...points.map(point => point.x));

    let maxX = Math.max(...points.map(point => point.x));

    let minY = Math.min(...points.map(point => point.y));

    let maxY = Math.max(...points.map(point => point.y));



    if (maxX === minX) {

        minX -= 0.005;

        maxX += 0.005;

    } else {

        const pad = Math.max((maxX - minX) * 0.08, 0.0001);

        minX -= pad;

        maxX += pad;

    }

    if (maxY === minY) {

        const padding = Math.max(Math.abs(maxY) * 0.1, 1);

        minY -= padding;

        maxY += padding;

    } else {

        const padding = (maxY - minY) * 0.08;

        minY -= padding;

        maxY += padding;

    }



    const xMap = value => margin.left + ((value - minX) / (maxX - minX)) * plotWidth;

    const yMap = value => margin.top + (1 - (value - minY) / (maxY - minY)) * plotHeight;



    context.strokeStyle = "#243752";

    context.lineWidth = 1;

    context.fillStyle = "#9aabc5";

    context.font = "13px Segoe UI, Arial, sans-serif";



    for (let index = 0; index <= 5; index++) {

        const fraction = index / 5;

        const y = margin.top + fraction * plotHeight;

        const value = maxY - fraction * (maxY - minY);



        context.beginPath();

        context.moveTo(margin.left, y);

        context.lineTo(width - margin.right, y);

        context.stroke();



        context.textAlign = "right";

        context.textBaseline = "middle";

        context.fillText(value.toExponential(2), margin.left - 12, y);

    }



    for (let index = 0; index <= 5; index++) {

        const fraction = index / 5;

        const x = margin.left + fraction * plotWidth;

        const value = minX + fraction * (maxX - minX);



        context.beginPath();

        context.moveTo(x, margin.top);

        context.lineTo(x, height - margin.bottom);

        context.stroke();



        context.textAlign = "center";

        context.textBaseline = "top";

        context.fillText(value.toFixed(maxX - minX < 0.1 ? 4 : 2), x, height - margin.bottom + 12);

    }



    // No unir exposiciones de distintas fechas como una curva espectral calibrada.

    points.forEach(point => {

        const x = xMap(point.x);

        const y = yMap(point.y);

        context.beginPath();

        context.arc(x, y, 5, 0, Math.PI * 2);

        context.fillStyle = "#a5e6f4";

        context.fill();

        context.strokeStyle = "#07131c";

        context.lineWidth = 2;

        context.stroke();

    });



    context.fillStyle = "#edf3ff";

    context.font = "bold 16px Segoe UI, Arial, sans-serif";

    context.textAlign = "center";

    context.textBaseline = "alphabetic";

    context.fillText("Longitud de onda (µm) · puntos por observación", width / 2, height - 18);



    context.save();

    context.translate(25, height / 2);

    context.rotate(-Math.PI / 2);

    context.textAlign = "center";

    context.fillText("Señal central (signal_proxy)", 0, 0);

    context.restore();

}



function downloadSpectrumCSV() {

    const items = latestSpectrumResult?.spectrum || [];

    if (!items.length) return;



    const columns = [

        "wavelength_um",

        "signal_proxy",

        "detector",

        "bandpass",

        "unit",

        "observation_time_mjd",

        "obs_id"

    ];



    const escapeCSV = value => {

        const text = value === null || value === undefined ? "" : String(value);

        return `"${text.replace(/"/g, '""')}"`;

    };



    const rows = [

        columns.join(","),

        ...items.map(item => columns.map(column => escapeCSV(item[column])).join(","))

    ];



    const blob = new Blob(["\uFEFF" + rows.join("\r\n")], {

        type: "text/csv;charset=utf-8"

    });

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");

    link.href = url;

    link.download = "SPHEREx_espectro_signal_proxy.csv";

    document.body.appendChild(link);

    link.click();

    link.remove();

    window.setTimeout(() => URL.revokeObjectURL(url), 1000);

}



function downloadSpectrumPNG() {

    if (!latestSpectrumResult?.spectrum?.length) return;



    const link = document.createElement("a");

    link.href = spectrumCanvas.toDataURL("image/png");

    link.download = "SPHEREx_espectro_signal_proxy.png";

    document.body.appendChild(link);

    link.click();

    link.remove();

}



async function runSpectrumAnalysis() {

    const originalText = spectrumButton.textContent;

    spectrumButton.disabled = true;

    spectrumButton.textContent = "Consultando...";

    spectrumSummary.textContent = "Consultando observaciones espectrales en SPHEREx...";

    analysisOutput.textContent = "Consultando el servicio espectral...";

    latestSpectrumResult = null;

    downloadSpectrumCSVButton.disabled = true;

    downloadSpectrumPNGButton.disabled = true;

    renderSpectrumChart([]);



    try {

        const params = new URLSearchParams({

            ...currentSkyParameters(),

            max_points: "16",

            detector: document.getElementById("detector").value

        });



        let result;

        if (document.getElementById("collection").value.startsWith("spherex_dr1")) {

            // DR1: solicitar un trabajo y consultar su estado sin bloquear la conexión.

            const startResponse = await fetch("/api/spectrum/tasks", {

                method: "POST",

                headers: {"Content-Type": "application/json"},

                body: JSON.stringify(currentSkyParameters())

            });

            const startInfo = await startResponse.json();

            if (!startResponse.ok) {

                throw new Error(startInfo.error || "No se pudo iniciar el cubo DR1.");

            }

            const taskId = startInfo.task_id;

            while (true) {

                const pollResponse = await fetch(`/api/spectrum/tasks/${encodeURIComponent(taskId)}`, {

                    cache: "no-store"

                });

                const task = await pollResponse.json();

                if (!pollResponse.ok) {

                    throw new Error(task.error || "No se pudo consultar el progreso espectral.");

                }

                if (task.status === "failed") {

                    throw new Error(task.error || "Falló la extracción del cubo DR1.");

                }

                if (task.status === "completed") {

                    result = task.result;

                    break;

                }

                const got = Number(task.downloaded_bytes || 0);

                const total = Number(task.total_bytes || 0);

                const progressText = got > 0

                    ? total > 0

                        ? ` · ${(100 * got / total).toFixed(1)}% (${(got / 1048576).toFixed(0)} / ${(total / 1048576).toFixed(0)} MiB)`

                        : ` · ${(got / 1048576).toFixed(0)} MiB recibidos`

                    : "";

                spectrumSummary.textContent = `${task.message || "Procesando cubo DR1…"}${progressText}`;

                analysisOutput.textContent = JSON.stringify({

                    estado: task.status,

                    etapa: task.stage,

                    mensaje: task.message,

                    bytes_recibidos: got,

                    bytes_totales: total || null

                }, null, 2);

                await new Promise(resolve => setTimeout(resolve, 1300));

            }

        } else {

            // QR3 y modo L2: mantener el comportamiento original.

            const controller = new AbortController();

            const abortTimer = setTimeout(() => controller.abort(), 135000);

            let response;

            try {

                response = await fetch(`/api/spectrum?${params.toString()}`, {

                    signal: controller.signal

                });

            } finally {

                clearTimeout(abortTimer);

            }

            result = await response.json();

            if (!response.ok) {

                throw new Error(result.details || result.error || "La consulta espectral falló.");

            }

        }



        latestSpectrumResult = result;

        const items = result.spectrum || [];

        renderSpectrumChart(items);

        analysisOutput.textContent = JSON.stringify(result, null, 2);



        if (items.length) {

            spectrumSummary.textContent =

                (result.data_product === "spherex_dr1_cube"

                    ? `${items.length} canales con cobertura de 102 canales DR1 · `

                    : `${items.length} medición(es) de ${result.observations_attempted ?? items.length} seleccionadas · ${result.collection} · `) +

                `${result.scientific_note || "Indicador de señal por longitud de onda."}`;

            downloadSpectrumCSVButton.disabled = false;

            downloadSpectrumPNGButton.disabled = false;

        } else {

            spectrumSummary.textContent =

                "La consulta terminó, pero no devolvió mediciones espectrales válidas para esta posición y detector.";

        }



    } catch (error) {

        spectrumSummary.textContent = `Error: ${error.message}`;

        analysisOutput.textContent = `Error: ${error.message}`;

        renderSpectrumChart([]);

    } finally {

        spectrumButton.disabled = false;

        spectrumButton.textContent = originalText;

    }

}



downloadSpectrumCSVButton.addEventListener("click", downloadSpectrumCSV);

downloadSpectrumPNGButton.addEventListener("click", downloadSpectrumPNG);

renderSpectrumChart([]);



async function runAnalysis(endpoint, extraParameters, button) {

    const originalText = button.textContent;

    button.disabled = true;

    button.textContent = "Consultando...";

    analysisOutput.textContent = "Consultando el servicio astronómico...";



    try {

        const params = new URLSearchParams({

            ...currentSkyParameters(),

            ...extraParameters

        });



        const response = await fetch(`${endpoint}?${params.toString()}`);

        const result = await response.json();



        if (!response.ok) {

            throw new Error(result.error || result.details || "La consulta falló.");

        }



        analysisOutput.textContent = JSON.stringify(result, null, 2);



    } catch (error) {

        analysisOutput.textContent = `Error: ${error.message}`;

    } finally {

        button.disabled = false;

        button.textContent = originalText;

    }

}



catalogButton.addEventListener("click", () => {

    const radiusArcmin = Math.max(

        0.1,

        Math.min(30, Number(document.getElementById("radius").value) * 60)

    );



    runAnalysis(

        "/api/catalog_overlay",

        {

            catalog: catalogType.value,

            radius: radiusArcmin

        },

        catalogButton

    );

});



spectrumButton.addEventListener("click", runSpectrumAnalysis);





function updateWiseBands() {

    const hasFourBands = wiseDataset.value === "allwise";

    wiseBand.innerHTML = hasFourBands

        ? '<option value="1">W1 · 3.4 μm</option><option value="2">W2 · 4.6 μm</option><option value="3">W3 · 12 μm</option><option value="4">W4 · 22 μm</option>'

        : '<option value="1">W1 · 3.4 μm</option><option value="2">W2 · 4.6 μm</option>';

}

wiseDataset.addEventListener("change", updateWiseBands);

updateWiseBands();



function updateWisePreview() {

    if (!lastWiseImages.length) return;

    const first = lastWiseImages[0];

    const previewUrl = new URL(first.preview_url, window.location.origin);

    if (wiseOverlay.value !== "none") {

        previewUrl.searchParams.set("overlay", wiseOverlay.value);

    } else {

        previewUrl.searchParams.delete("overlay");

    }

    const basePreview = new URL(first.preview_url, window.location.origin).toString();

    wisePreview.onerror = () => {

        wisePreview.onerror = null;

        wisePreview.src = basePreview;

        wiseStatus.textContent = "Vista previa con capa no disponible; se intenta mostrar WISE sin superposición.";

    };

    wisePreview.src = previewUrl.toString();

    wisePreview.style.display = "block";

    wisePlaceholder.style.display = "none";

    const overlayLabel = wiseOverlay.value === "gaia"

        ? " · capa Gaia DR3"

        : wiseOverlay.value === "allwise"

            ? " · capa AllWISE"

            : "";

    wiseImageCaption.textContent =

        `${first.dataset} · Banda W${first.band} · ${first.observation_date || "Fecha no disponible"}${overlayLabel}`;

}



wiseOverlay.addEventListener("change", updateWisePreview);



wiseImagesButton.addEventListener("click", async () => {

    const originalText = wiseImagesButton.textContent;

    wiseImagesButton.disabled = true;

    const isUnwise = wiseDataset.value === "unwise";
    wiseImagesButton.textContent = isUnwise ? "Descargando unWISE..." : "Consultando IRSA...";

    wiseStatus.textContent = isUnwise
        ? "Descargando y validando el recorte FITS unWISE neo1..."
        : "Buscando metadatos en NASA/IPAC IRSA...";

    wiseOutput.textContent = isUnwise ? "Consultando unWISE cutout_fits..." : "Consultando IRSA IBE...";

    wiseLinks.innerHTML = "";

    lastWiseImages = [];

    wisePreview.style.display = "none";

    wisePlaceholder.style.display = "flex";

    wiseImageCaption.textContent = "";



    try {

        const params = new URLSearchParams({

            ...currentSkyParameters(),

            dataset: wiseDataset.value,

            band: wiseBand.value,

            max_results: "5"

        });



        const response = await fetch(`/api/wise_images?${params.toString()}`);

        const result = await response.json();



        if (!response.ok) {

            throw new Error(result.details || result.error || "La consulta WISE/NEOWISE falló.");

        }



        wiseOutput.textContent = JSON.stringify(result, null, 2);

        wiseStatus.textContent =

            `${result.total_selected} imagen(es) seleccionada(s) · Archivo: ${result.archive} · Servicio: ${result.service}`;



        if (result.images.length > 0) {

            lastWiseImages = result.images;

            updateWisePreview();



            result.images.forEach((item, index) => {

                const link = document.createElement("a");

                link.href = item.cutout_url;

                link.target = "_blank";

                link.rel = "noopener noreferrer";

                link.textContent =

                    `FITS ${index + 1} · W${item.band} · ${item.observation_date || "fecha no disponible"}`;

                link.title = wiseDataset.value === "unwise"
                    ? "Descargar el recorte FITS unWISE con WCS"
                    : "Abrir el recorte FITS desde IRSA";

                wiseLinks.appendChild(link);



                const previewLink = document.createElement("a");

                const previewUrl = new URL(item.preview_url, window.location.origin);

                if (wiseOverlay.value !== "none") {

                    previewUrl.searchParams.set("overlay", wiseOverlay.value);

                }

                previewLink.href = previewUrl.toString();

                previewLink.target = "_blank";

                previewLink.rel = "noopener noreferrer";

                previewLink.textContent = `PNG ${index + 1} · Vista previa`;

                previewLink.title = "Abrir la vista previa PNG con la capa seleccionada";

                wiseLinks.appendChild(previewLink);

            });

        } else {

            wiseStatus.textContent += " · No se encontraron imágenes en esa región.";

        }



    } catch (error) {

        wiseStatus.textContent = `Error: ${error.message}`;

        wiseOutput.textContent = `Error: ${error.message}`;

    } finally {

        wiseImagesButton.disabled = false;

        wiseImagesButton.textContent = originalText;

    }

});

</script>

</body>

</html>

"""


