
import { useEffect, useRef, useState } from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Investigador from './pages/Investigador'
import DiwoHero from './components/DiwoHero'
import { apiClient } from './services/apiClient'
import './App.css'

const collections = [
  { value: 'spherex_dr1', label: 'SPHEREx DR1' },
  { value: 'spherex_dr1_deep', label: 'SPHEREx DR1 Deep' },
  { value: 'spherex_qr3', label: 'SPHEREx QR3' },
  { value: 'spherex_qr3_deep', label: 'SPHEREx QR3 Deep' },
]

const detectors = ['ALL', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6']

const modes = [
  {
    value: 'timelapse',
    label: 'TIMELAPSE',
    description: 'Compare real infrared observations over time.',
  },
  {
    value: 'coadd',
    label: 'COADD',
    description: 'Combine compatible observations into one aligned image.',
  },
  {
    value: 'subtraction',
    label: 'SUBTRACTION',
    description: 'Reveal differences between compatible observations.',
  },
]

const fieldStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
}

const inputStyle = {
  width: '100%',
  padding: '10px',
  borderRadius: '8px',
  border: '1px solid #64748b',
  background: '#111827',
  color: '#ffffff',
  boxSizing: 'border-box',
}

const gridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
  gap: '16px',
  marginBottom: '20px',
}

const errorStyle = {
  color: '#fca5a5',
  marginTop: '16px',
}

const imageStyle = {
  display: 'block',
  width: '100%',
  maxHeight: '540px',
  objectFit: 'contain',
  margin: '0 auto',
}

function validateCoordinates(ra, dec, radius) {
  const raw = [ra, dec, radius].map(value => String(value).trim())
  const values = raw.map(Number)

  if (
    raw.some(value => value === '') ||
    !values.every(Number.isFinite)
  ) {
    return {
      error: 'Please enter valid numeric coordinates and radius.',
    }
  }

  const [raValue, decValue, radiusValue] = values

  if (raValue < 0 || raValue >= 360) {
    return {
      error: 'Right ascension must be between 0 and less than 360 degrees.',
    }
  }

  if (decValue < -90 || decValue > 90) {
    return {
      error: 'Declination must be between -90 and 90 degrees.',
    }
  }

  if (radiusValue <= 0 || radiusValue > 5) {
    return {
      error: 'Search radius must be greater than 0 and at most 5 degrees.',
    }
  }

  return { raValue, decValue, radiusValue }
}

function percentFraction(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${(value * 100).toFixed(1)}%`
    : 'Not available'
}

function percentAlready(value) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${value.toFixed(1)}%`
    : 'Not available'
}

function numberOrNA(value, digits = 4) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(digits)
    : 'Not available'
}

function ScientificMetadata({ frame, job }) {
  if (!frame) return null

  const summary = job?.summary || {}

  return (
    <div style={{ marginTop: '20px' }}>
      <h3>Scientific Image Information</h3>

      {frame.label && (
        <p><strong>Image:</strong> {frame.label}</p>
      )}

      {frame.obs_id && (
        <p><strong>Observation ID:</strong> {frame.obs_id}</p>
      )}

      <p>
        <strong>Observation date:</strong>{' '}
        {frame.observation_date || 'Not available'}
      </p>

      <p>
        <strong>Detector / bandpass:</strong>{' '}
        {frame.detector || '—'} / {frame.bandpass || '—'}
      </p>

      <p>
        <strong>Wavelength:</strong>{' '}
        {typeof frame.wavelength_um === 'number'
          ? `${numberOrNA(frame.wavelength_um)} µm`
          : 'Not available'}
      </p>

      {frame.wavelength_method && (
        <p>
          <strong>Wavelength method:</strong>{' '}
          {frame.wavelength_method}
        </p>
      )}

      {frame.bunit && (
        <p><strong>Image units:</strong> {frame.bunit}</p>
      )}

      {typeof frame.valid_fraction === 'number' && (
        <p>
          <strong>Valid pixels:</strong>{' '}
          {percentFraction(frame.valid_fraction)}
        </p>
      )}

      {typeof frame.bad_flag_fraction === 'number' && (
        <p>
          <strong>Problematic-flag fraction:</strong>{' '}
          {percentFraction(frame.bad_flag_fraction)}
        </p>
      )}

      {typeof frame.flagged_fraction === 'number' && (
        <p>
          <strong>All flagged pixels:</strong>{' '}
          {percentFraction(frame.flagged_fraction)}
        </p>
      )}

      {typeof frame.center_has_caution_flags === 'boolean' && (
        <p>
          <strong>Central caution flags:</strong>{' '}
          {frame.center_has_caution_flags
            ? 'Present'
            : 'None reported'}
        </p>
      )}

      {typeof summary.coverage_percent === 'number' && (
        <p>
          <strong>Shared coverage:</strong>{' '}
          {percentAlready(summary.coverage_percent)}
        </p>
      )}

      {summary.combination_method && (
        <p>
          <strong>Combination method:</strong>{' '}
          {summary.combination_method}
        </p>
      )}

      <p className="viewer-note">
        Flagged pixels are not necessarily defective.
        SOURCE flags and problematic quality flags must
        be interpreted separately. Wavelength values
        may be approximate.
      </p>

      {summary.coverage_note && (
        <p className="viewer-note">{summary.coverage_note}</p>
      )}
    </div>
  )
}

function Observer() {
  const [section, setSection] = useState('general')

  const [ra, setRa] = useState('0')
  const [dec, setDec] = useState('0')
  const [radius, setRadius] = useState('0.02')
  const [collection, setCollection] = useState('spherex_dr1')

  const [inventory, setInventory] = useState(null)
  const [loading, setLoading] = useState(false)
  const [searchError, setSearchError] = useState('')

  const [mode, setMode] = useState('timelapse')
  const [detector, setDetector] = useState('D1')
  const [maxFrames, setMaxFrames] = useState(4)
  const [fps, setFps] = useState(2)
  const [viewMode, setViewMode] = useState('radius')

  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [jobError, setJobError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const [frameIndex, setFrameIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [displayMode, setDisplayMode] = useState('frames')
  const [overlay, setOverlay] = useState('none')

  const searchController = useRef(null)
  const submitController = useRef(null)

  useEffect(() => {
    return () => {
      searchController.current?.abort()
      submitController.current?.abort()
    }
  }, [])

  // Poll the backend without overlapping requests.
  useEffect(() => {
    if (!jobId) return undefined

    const controller = new AbortController()
    let timer
    let stopped = false

    async function poll() {
      try {
        const result = await apiClient.getJob(
          jobId,
          controller.signal
        )

        if (stopped) return

        setJob(result)

        const status = String(
          result.status || ''
        ).toLowerCase()

        if (status === 'completed') {
          setFrameIndex(0)
          setPlaying(result.result_type === 'timelapse')
          return
        }

        if (
          ['failed', 'error', 'cancelled', 'canceled']
            .includes(status)
        ) {
          setJobError(
            result.error ||
            result.message ||
            'Processing failed.'
          )
          setPlaying(false)
          return
        }

        timer = setTimeout(poll, 2000)
      } catch (error) {
        if (!stopped && !controller.signal.aborted) {
          setJobError(
            error.message ||
            'Unable to retrieve processing status.'
          )
          setPlaying(false)
        }
      }
    }

    poll()

    return () => {
      stopped = true
      clearTimeout(timer)
      controller.abort()
    }
  }, [jobId])

  const frames = Array.isArray(job?.frames)
    ? job.frames
    : []

  const completed = job?.status === 'completed'

  const processing =
    submitting ||
    (Boolean(jobId) && !completed && !jobError)

  const resultMode =
    job?.result_type ||
    job?.params?.mode ||
    mode

  const isTimelapseResult = resultMode === 'timelapse'

  const currentFrame = frames[frameIndex] || null

  const currentImageUrl =
    completed && currentFrame
      ? currentFrame.image_url ||
        apiClient.getFrameUrl(
          job.id || jobId,
          frameIndex,
          overlay === 'none' ? null : overlay
        )
      : null

  const displayedFrameUrl =
    completed && currentFrame
      ? overlay === 'none'
        ? currentImageUrl
        : apiClient.getFrameUrl(
            job.id || jobId,
            frameIndex,
            overlay
          )
      : null

  const processedResultUrl =
    completed && !isTimelapseResult
      ? job?.result_url ||
        apiClient.getResultImageUrl(job.id || jobId)
      : null

  const mainImageUrl = isTimelapseResult
    ? displayedFrameUrl
    : processedResultUrl

  // Playback individual PNGs to synchronize metadata.
  useEffect(() => {
    if (
      !playing ||
      !completed ||
      !isTimelapseResult ||
      section !== 'general' ||
      displayMode !== 'frames' ||
      frames.length < 2
    ) {
      return undefined
    }

    const sourceFps = Number(job?.params?.fps) || 2

    const timer = setInterval(() => {
      setFrameIndex(index =>
        (index + 1) % frames.length
      )
    }, 1000 / (sourceFps * speed))

    return () => clearInterval(timer)
  }, [
    playing,
    completed,
    isTimelapseResult,
    section,
    displayMode,
    frames.length,
    job?.params?.fps,
    speed,
  ])

  function changeMode(value) {
    setMode(value)

    setMaxFrames(current =>
      Math.max(
        value === 'timelapse' ? 4 : 2,
        Number(current) || 4
      )
    )
  }

  function moveFrame(direction) {
    if (!frames.length) return

    setPlaying(false)
    setDisplayMode('frames')

    setFrameIndex(index =>
      (index + direction + frames.length) % frames.length
    )
  }

  async function searchObservations(event) {
    event.preventDefault()

    setSearchError('')
    setInventory(null)

    const values = validateCoordinates(ra, dec, radius)

    if (values.error) {
      setSearchError(values.error)
      return
    }

    searchController.current?.abort()

    const controller = new AbortController()
    searchController.current = controller

    setLoading(true)

    try {
      const result = await apiClient.getObservations(
        {
          ra: values.raValue,
          dec: values.decValue,
          radius: values.radiusValue,
          collection,
        },
        controller.signal
      )

      if (!controller.signal.aborted) {
        setInventory(result)
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setSearchError(
          error.message || 'Observation search failed.'
        )
      }
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }

  async function processObservation(event) {
    event.preventDefault()

    if (processing) return

    const values = validateCoordinates(ra, dec, radius)

    if (values.error) {
      setJobError(values.error)
      return
    }

    const count = Number(maxFrames)
    const minCount = mode === 'timelapse' ? 4 : 2

    if (
      !Number.isInteger(count) ||
      count < minCount ||
      count > 20
    ) {
      setJobError(
        `The selected mode requires ${minCount}–20 observations.`
      )
      return
    }

    const framesPerSecond = Number(fps)

    if (
      !Number.isInteger(framesPerSecond) ||
      framesPerSecond < 1 ||
      framesPerSecond > 20
    ) {
      setJobError(
        'Playback FPS must be an integer from 1 to 20.'
      )
      return
    }

    setJobError('')
    setJob(null)
    setJobId(null)
    setFrameIndex(0)
    setPlaying(false)
    setDisplayMode('frames')
    setOverlay('none')

    submitController.current?.abort()

    const controller = new AbortController()
    submitController.current = controller

    setSubmitting(true)

    try {
      const response = await apiClient.createJob(
        {
          ra: values.raValue,
          dec: values.decValue,
          radius: values.radiusValue,
          collection,
          mode,
          detector,
          max_frames: count,
          fps: framesPerSecond,
          view_mode: viewMode,
          use_cutouts: true,
        },
        controller.signal
      )

      if (!controller.signal.aborted) {
        if (!response.job_id) {
          throw new Error(
            'The server did not return a job ID.'
          )
        }

        setJobId(response.job_id)
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setJobError(
          error.message || 'Unable to start processing.'
        )
      }
    } finally {
      if (!controller.signal.aborted) {
        setSubmitting(false)
      }
    }
  }

  const modeInfo = modes.find(item => item.value === mode)

  const progress = Number(job?.progress)
  const total = Number(job?.total)

  const progressPercent =
    Number.isFinite(progress) &&
    Number.isFinite(total) &&
    total > 0
      ? Math.min(
          100,
          Math.max(0, 100 * progress / total)
        )
      : 0

  return (
    <main className="observer-page">
      <Link className="back-link" to="/">
        ← Back to home
      </Link>

      <h1>Explore the Universe</h1>

      <p>
        Discover astronomical observations
        from a new perspective.
      </p>

      {/* OBSERVATION SEARCH */}

      <section className="observer-panel">
        <h2>Search SPHEREx Observations</h2>

        <p>
          Explore real observation metadata from the
          NASA/IPAC Infrared Science Archive (IRSA).
        </p>

        <form onSubmit={searchObservations}>
          <div style={gridStyle}>
            <label style={fieldStyle}>
              Right Ascension (RA°)

              <input
                type="number"
                step="any"
                min="0"
                max="359.999999"
                value={ra}
                onChange={event => setRa(event.target.value)}
                style={inputStyle}
                required
              />
            </label>

            <label style={fieldStyle}>
              Declination (Dec°)

              <input
                type="number"
                step="any"
                min="-90"
                max="90"
                value={dec}
                onChange={event => setDec(event.target.value)}
                style={inputStyle}
                required
              />
            </label>

            <label style={fieldStyle}>
              Search Radius (degrees)

              <input
                type="number"
                step="any"
                min="0.000001"
                max="5"
                value={radius}
                onChange={event => setRadius(event.target.value)}
                style={inputStyle}
                required
              />
            </label>

            <label style={fieldStyle}>
              Data Collection

              <select
                value={collection}
                onChange={event =>
                  setCollection(event.target.value)
                }
                style={inputStyle}
              >
                {collections.map(item => (
                  <option
                    key={item.value}
                    value={item.value}
                  >
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <button type="submit" disabled={loading}>
            {loading
              ? 'Searching IRSA...'
              : 'Search Observations'}
          </button>
        </form>

        {searchError && (
          <p role="alert" style={errorStyle}>
            {searchError}
          </p>
        )}

        {inventory && (
          <div style={{ marginTop: '24px' }}>
            <h3>Observation Inventory</h3>

            <p>
              <strong>Total products:</strong>{' '}
              {inventory.total ?? 'Not available'}
            </p>

            <p>
              <strong>Collection:</strong>{' '}
              {inventory.collection || collection}
            </p>

            <p>
              <strong>Metadata source:</strong>{' '}
              {inventory.metadata_source || 'Not available'}
            </p>

            <p>
              <strong>Inventory complete:</strong>{' '}
              {inventory.inventory_complete
                ? 'Yes'
                : 'Not confirmed'}
            </p>

            <p>
              <strong>Inventory coverage:</strong>{' '}
              {inventory.inventory_coverage || 'Not specified'}
            </p>

            <h3>Products by Detector</h3>

            {Object.entries(
              inventory.by_detector || {}
            ).map(([name, count]) => (
              <p key={name}>
                <strong>{name}:</strong> {count} products
              </p>
            ))}

            <p>
              <strong>First observation (MJD):</strong>{' '}
              {inventory.first_date_mjd ?? 'Not available'}
            </p>

            <p>
              <strong>Last observation (MJD):</strong>{' '}
              {inventory.last_date_mjd ?? 'Not available'}
            </p>

            {inventory.note && (
              <p className="viewer-note">
                {inventory.note}
              </p>
            )}

            <p className="viewer-note">
              This inventory retrieves metadata only.
              Process an observation to generate images.
            </p>
          </div>
        )}
      </section>

      {/* OBSERVER TABS */}

      <div className="observer-tabs">
        <button
          className={
            section === 'general' ? 'active' : ''
          }
          aria-pressed={section === 'general'}
          onClick={() => setSection('general')}
        >
          General
        </button>

        <button
          className={
            section === 'infrared' ? 'active' : ''
          }
          aria-pressed={section === 'infrared'}
          onClick={() => {
            setSection('infrared')
            setPlaying(false)
          }}
        >
          Infrared
        </button>
      </div>

      {section === 'general' ? (
        <section className="observer-panel">
          <h2>Scientific Image Processing</h2>

          <p>
            Process real SPHEREx observations using
            TIMELAPSE, COADD or SUBTRACTION.
          </p>

          <form onSubmit={processObservation}>
            <div style={gridStyle}>
              <label style={fieldStyle}>
                Processing mode

                <select
                  value={mode}
                  onChange={event =>
                    changeMode(event.target.value)
                  }
                  style={inputStyle}
                  disabled={processing}
                >
                  {modes.map(item => (
                    <option
                      key={item.value}
                      value={item.value}
                    >
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>

              <label style={fieldStyle}>
                Detector

                <select
                  value={detector}
                  onChange={event =>
                    setDetector(event.target.value)
                  }
                  style={inputStyle}
                  disabled={processing}
                >
                  {detectors.map(item => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>

              <label style={fieldStyle}>
                Maximum observations (
                {mode === 'timelapse' ? '4' : '2'}–20)

                <input
                  type="number"
                  min={mode === 'timelapse' ? 4 : 2}
                  max="20"
                  step="1"
                  value={maxFrames}
                  onChange={event =>
                    setMaxFrames(event.target.value)
                  }
                  style={inputStyle}
                  disabled={processing}
                  required
                />
              </label>

              {mode === 'timelapse' && (
                <label style={fieldStyle}>
                  Frames per second (1–20)

                  <input
                    type="number"
                    min="1"
                    max="20"
                    step="1"
                    value={fps}
                    onChange={event =>
                      setFps(event.target.value)
                    }
                    style={inputStyle}
                    disabled={processing}
                    required
                  />
                </label>
              )}

              <label style={fieldStyle}>
                Image field of view

                <select
                  value={viewMode}
                  onChange={event =>
                    setViewMode(event.target.value)
                  }
                  style={inputStyle}
                  disabled={processing}
                >
                  <option value="radius">
                    Requested search radius
                  </option>

                  <option value="native">
                    Native image field
                  </option>
                </select>
              </label>
            </div>

            <p className="viewer-note">
              {modeInfo?.description}
            </p>

            <button
              type="submit"
              disabled={processing}
            >
              {processing
                ? 'Processing observation...'
                : `Process ${mode.toUpperCase()}`}
            </button>
          </form>

          {jobError && (
            <p role="alert" style={errorStyle}>
              {jobError}
            </p>
          )}

          {/* PROCESSING PROGRESS */}

          {processing && (
            <div
              role="status"
              aria-live="polite"
              style={{ marginTop: '16px' }}
            >
              <strong>
                Processing SPHEREx data...
              </strong>

              <p>
                Stage:{' '}
                {job?.stage
                  ? String(job.stage).replaceAll('-', ' ')
                  : 'Waiting for the server...'}

                {Number.isFinite(progress) &&
                Number.isFinite(total) &&
                total > 0
                  ? ` — ${progress} / ${total}`
                  : ''}
              </p>

              {total > 0 && (
                <div
                  role="progressbar"
                  aria-valuenow={progressPercent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  style={{
                    width: '100%',
                    height: '10px',
                    borderRadius: '6px',
                    background: '#334155',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${progressPercent}%`,
                      background: '#38bdf8',
                      transition: 'width 0.2s',
                    }}
                  />
                </div>
              )}

              <p className="viewer-note">
                FITS downloads and WCS alignment may
                take time. Keep this page open.
              </p>
            </div>
          )}

          {/* COMPLETED JOB */}

          {completed && (
            <div
              role="status"
              style={{ marginTop: '16px' }}
            >
              <strong>
                {resultMode.toUpperCase()} completed.
              </strong>

              <p>
                Job ID: <code>{job.id || jobId}</code>
                {' · '}
                {job.summary?.observations_used ??
                  job.observations_selected ??
                  '—'}{' '}
                observations selected/used.
              </p>

              {job.summary?.coverage_warning && (
                <p className="viewer-note">
                  {job.summary.coverage_warning}
                </p>
              )}
            </div>
          )}

          {/* SCIENTIFIC IMAGE VIEWER */}

          <div
            className="sky-viewer"
            style={{
              marginTop: '20px',
              minHeight: '280px',
            }}
          >
            {!completed && !processing && (
              <p>
                Choose a processing mode and select
                Process to display real SPHEREx data.
              </p>
            )}

            {processing && (
              <p>
                Retrieving and processing astronomical
                observations...
              </p>
            )}

            {completed &&
              isTimelapseResult &&
              displayMode === 'gif' &&
              job.gif_url && (
                <img
                  src={job.gif_url}
                  alt="SPHEREx timelapse animation"
                  style={imageStyle}
                />
              )}

            {completed &&
              displayMode === 'frames' &&
              mainImageUrl && (
                <img
                  key={mainImageUrl}
                  src={mainImageUrl}
                  alt={`SPHEREx ${resultMode} result`}
                  style={imageStyle}
                />
              )}

            {completed &&
              !mainImageUrl &&
              !(isTimelapseResult &&
                displayMode === 'gif' &&
                job.gif_url) && (
                <p>
                  The job completed but did not return
                  an image preview.
                </p>
              )}
          </div>

          {/* PLAYBACK CONTROLS */}

          {completed && (
            <>
              {isTimelapseResult &&
                frames.length > 1 && (
                  <div
                    className="viewer-controls"
                    style={{ marginTop: '16px' }}
                  >
                    <button
                      type="button"
                      onClick={() => moveFrame(-1)}
                      disabled={displayMode === 'gif'}
                    >
                      ◀ Previous
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setPlaying(value => !value)
                      }
                      disabled={displayMode === 'gif'}
                    >
                      {playing
                        ? '⏸ Pause'
                        : '▶ Play'}
                    </button>

                    <button
                      type="button"
                      onClick={() => moveFrame(1)}
                      disabled={displayMode === 'gif'}
                    >
                      Next ▶
                    </button>
                  </div>
                )}

              <div
                style={{
                  ...gridStyle,
                  marginTop: '16px',
                }}
              >
                {isTimelapseResult && (
                  <label style={fieldStyle}>
                    View

                    <select
                      style={inputStyle}
                      value={displayMode}
                      onChange={event => {
                        setDisplayMode(event.target.value)
                        setPlaying(
                          event.target.value === 'frames'
                        )
                      }}
                    >
                      <option value="frames">
                        Individual frames + metadata
                      </option>

                      {job.gif_url && (
                        <option value="gif">
                          Original GIF animation
                        </option>
                      )}
                    </select>
                  </label>
                )}

                {isTimelapseResult && (
                  <label style={fieldStyle}>
                    Playback speed

                    <select
                      style={inputStyle}
                      value={speed}
                      disabled={displayMode === 'gif'}
                      onChange={event =>
                        setSpeed(Number(event.target.value))
                      }
                    >
                      <option value={0.5}>0.5x</option>
                      <option value={1}>1x</option>
                      <option value={2}>2x</option>
                      <option value={4}>4x</option>
                    </select>
                  </label>
                )}

                {isTimelapseResult && (
                  <label style={fieldStyle}>
                    Catalog overlay (individual PNGs)

                    <select
                      style={inputStyle}
                      value={overlay}
                      disabled={displayMode === 'gif'}
                      onChange={event =>
                        setOverlay(event.target.value)
                      }
                    >
                      <option value="none">None</option>
                      <option value="gaia">Gaia DR3</option>
                      <option value="allwise">AllWISE</option>
                    </select>
                  </label>
                )}
              </div>

              {isTimelapseResult && (
                <p className="viewer-note">
                  Frame {frameIndex + 1} of {frames.length}
                </p>
              )}

              {displayMode === 'gif' &&
                isTimelapseResult && (
                  <p className="viewer-note">
                    The GIF uses its encoded playback
                    speed. Use individual frames for
                    synchronized metadata and overlays.
                  </p>
                )}

              {displayMode === 'frames' &&
                currentFrame && (
                  <ScientificMetadata
                    frame={currentFrame}
                    job={job}
                  />
                )}

              <div style={{ marginTop: '16px' }}>
                <h3>Scientific Downloads</h3>

                {job.gif_url && (
                  <p>
                    <a
                      href={job.gif_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open TIMELAPSE GIF
                    </a>
                  </p>
                )}

                {!isTimelapseResult &&
                  job.result_url && (
                    <p>
                      <a href={job.result_url}>
                        Download {resultMode.toUpperCase()} PNG
                      </a>
                    </p>
                  )}

                {job.science_fits_url && (
                  <p>
                    <a href={job.science_fits_url}>
                      Download scientific FITS
                    </a>
                  </p>
                )}
              </div>

              {job.summary?.errors?.length > 0 && (
                <div
                  role="alert"
                  style={errorStyle}
                >
                  <h3>Processing warnings</h3>

                  {job.summary.errors.map(
                    (item, index) => (
                      <p key={index}>
                        {typeof item === 'string'
                          ? item
                          : JSON.stringify(item)}
                      </p>
                    )
                  )}
                </div>
              )}
            </>
          )}
        </section>
      ) : (
        /* INFRARED VIEW */

        <section className="observer-panel">
          <h2>Infrared Exploration</h2>

          <p>
            Explore the real infrared observation
            from the latest completed processing job.
          </p>

          {!completed ? (
            <p className="viewer-note">
              Run a scientific processing job in the
              General tab to display real infrared
              imagery here.
            </p>
          ) : (
            <>
              <p>
                <strong>Result:</strong>{' '}
                {resultMode.toUpperCase()}
                {' · '}
                <strong>Detector:</strong>{' '}
                {currentFrame?.detector ||
                  job.params?.detector_filter ||
                  '—'}
              </p>

              {frames.length > 1 && (
                <label style={fieldStyle}>
                  Observation frame

                  <select
                    style={inputStyle}
                    value={frameIndex}
                    onChange={event => {
                      setFrameIndex(
                        Number(event.target.value)
                      )
                      setPlaying(false)
                    }}
                  >
                    {frames.map((item, index) => (
                      <option
                        key={index}
                        value={index}
                      >
                        {item.label ||
                          `Frame ${index + 1}`}
                        {' — '}
                        {item.observation_date ||
                          'Date unknown'}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <div
                className="sky-viewer"
                style={{ marginTop: '16px' }}
              >
                {(isTimelapseResult
                  ? displayedFrameUrl
                  : processedResultUrl) && (
                  <img
                    src={
                      isTimelapseResult
                        ? displayedFrameUrl
                        : processedResultUrl
                    }
                    alt="Real SPHEREx infrared observation"
                    style={imageStyle}
                  />
                )}
              </div>

              <ScientificMetadata
                frame={currentFrame}
                job={job}
              />

              <p className="viewer-note">
                Each SPHEREx detector covers a
                spectral band. These are actual
                processed observations, not simulated
                RGB colors or arbitrary demonstration
                channels.
              </p>
            </>
          )}
        </section>
      )}
    </main>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<DiwoHero />}
        />

        <Route
          path="/observador"
          element={<Observer />}
        />

        <Route
          path="/investigador"
          element={<Investigador />}
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
