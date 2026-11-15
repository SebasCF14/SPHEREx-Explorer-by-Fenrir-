import { useEffect, useMemo, useRef, useState } from 'react'

const palette = {
  D1: '#7dd3fc', D2: '#86efac', D3: '#fde68a',
  D4: '#fdba74', D5: '#f9a8d4', D6: '#c4b5fd',
}
const W = 1000
const H = 480
const M = { left: 96, right: 32, top: 52, bottom: 70 }
const plotW = W - M.left - M.right
const plotH = H - M.top - M.bottom

function percentile(sorted, p) {
  const at = (sorted.length - 1) * p
  const lo = Math.floor(at)
  const hi = Math.ceil(at)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (at - lo)
}
function finite(value) {
  return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
}
function format(value) {
  return Math.abs(value) >= 0.01 && Math.abs(value) < 100
    ? value.toFixed(3)
    : value.toExponential(2)
}
async function readJson(response) {
  const result = await response.json()
  if (!response.ok) throw new Error(result.details || result.error || result.message || `HTTP ${response.status}`)
  return result
}
function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1500)
}

export default function SpectrumPanel({ ra, dec, radius, collection }) {
  const [result, setResult] = useState(null)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [scale, setScale] = useState('detail')
  const svgRef = useRef(null)
  const requestRef = useRef(null)

  useEffect(() => () => requestRef.current?.abort(), [])

  async function consult() {
    if (busy) return
    const values = [ra, dec, radius].map(v => String(v).trim())
    const numbers = values.map(Number)
    if (values.some(v => !v) || !numbers.every(Number.isFinite) ||
      numbers[0] < 0 || numbers[0] >= 360 ||
      numbers[1] < -90 || numbers[1] > 90 ||
      numbers[2] <= 0 || numbers[2] > 5) {
      setError('Enter valid RA, Dec and radius values in the observation form.')
      return
    }
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setBusy(true)
    setResult(null)
    setError('')
    setStatus('Requesting SPHEREx spectral data...')
    try {
      let payload
      if (collection.startsWith('spherex_dr1')) {
        const task = await readJson(await fetch('/api/spectrum/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ra: numbers[0], dec: numbers[1], radius: numbers[2], collection }),
          signal: controller.signal,
        }))
        if (!task.task_id) throw new Error('The server did not return a spectral task ID.')
        while (!controller.signal.aborted) {
          const progress = await readJson(await fetch(`/api/spectrum/tasks/${encodeURIComponent(task.task_id)}`, {
            cache: 'no-store', signal: controller.signal,
          }))
          if (progress.status === 'failed') throw new Error(progress.error || 'Spectral extraction failed.')
          if (progress.status === 'completed') {
            payload = progress.result
            break
          }
          const received = Number(progress.downloaded_bytes || 0)
          const total = Number(progress.total_bytes || 0)
          const transfer = received > 0
            ? ` · ${total > 0 ? `${(received / total * 100).toFixed(1)}%` : `${(received / 1048576).toFixed(1)} MiB`}`
            : ''
          setStatus(`${progress.message || 'Processing spectral cube...'}${transfer}`)
          await new Promise(resolve => window.setTimeout(resolve, 1300))
        }
      } else {
        const params = new URLSearchParams({
          ra: String(numbers[0]), dec: String(numbers[1]), radius: String(numbers[2]),
          collection, method: 'l2', detector: 'ALL', max_points: '16',
        })
        payload = await readJson(await fetch(`/api/spectrum?${params}`, { signal: controller.signal }))
      }
      if (!controller.signal.aborted) {
        setResult(payload)
        setStatus('Spectral query completed.')
      }
    } catch (e) {
      if (!controller.signal.aborted) {
        setError(e.message || 'Spectral query failed.')
        setStatus('')
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false)
    }
  }

  const points = useMemo(() => (Array.isArray(result?.spectrum) ? result.spectrum : [])
    .filter(p => finite(p.wavelength_um) && finite(p.signal_proxy))
    .map(p => ({
      ...p,
      x: Number(p.wavelength_um), y: Number(p.signal_proxy),
      channel: Number(p.channel),
    }))
    .sort((a, b) => a.x - b.x), [result])

  const graph = useMemo(() => {
    if (!points.length) return null
    const ys = points.map(p => p.y).sort((a, b) => a - b)
    let low = scale === 'detail' && ys.length >= 10 ? percentile(ys, 0.05) : ys[0]
    let high = scale === 'detail' && ys.length >= 10 ? percentile(ys, 0.95) : ys[ys.length - 1]
    const padding = high > low ? (high - low) * 0.12 : Math.max(Math.abs(high) * 0.15, 0.01)
    low -= padding
    high += padding
    const xs = points.map(p => p.x)
    const xMin = Math.min(...xs) - 0.04
    const xMax = Math.max(...xs) + 0.04
    return {
      low, high, xMin, xMax,
      x: value => M.left + (value - xMin) / (xMax - xMin) * plotW,
      y: value => M.top + (high - value) / (high - low) * plotH,
    }
  }, [points, scale])

  function downloadCsv() {
    if (!result) return
    const rows = ['channel,wavelength_um,signal_proxy,unit,detector,valid_pixels,nhits_median,status']
    const byChannel = new Map(points.filter(p => Number.isInteger(p.channel)).map(p => [p.channel, p]))
    const cube = result.data_product === 'spherex_dr1_cube'
    const source = cube
      ? Array.from({ length: 102 }, (_, i) => byChannel.get(i + 1) || { channel: i + 1 })
      : points
    for (const p of source) {
      const values = [p.channel ?? '', p.wavelength_um ?? '', p.signal_proxy ?? '',
        p.unit ?? '', p.detector ?? '', p.valid_pixels ?? '', p.nhits_median ?? '',
        finite(p.signal_proxy) ? 'valid' : 'missing']
      rows.push(values.map(v => `"${String(v).replaceAll('"', '""')}"`).join(','))
    }
    saveBlob(new Blob([rows.join('\r\n')], { type: 'text/csv;charset=utf-8' }), 'SPHEREx_spectrum_channels.csv')
  }

  async function downloadPng() {
    if (!svgRef.current) return
    const source = new XMLSerializer().serializeToString(svgRef.current)
    const blob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const img = new Image()
    try {
      await new Promise((resolve, reject) => {
        img.onload = resolve
        img.onerror = reject
        img.src = url
      })
      const canvas = document.createElement('canvas')
      canvas.width = W * 2
      canvas.height = H * 2
      const context = canvas.getContext('2d')
      context.scale(2, 2)
      context.drawImage(img, 0, 0, W, H)
      const png = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
      if (png) saveBlob(png, 'SPHEREx_spectrum.png')
    } catch (e) {
      setError(`PNG export failed: ${e.message}`)
    } finally {
      URL.revokeObjectURL(url)
    }
  }

  const cube = result?.data_product === 'spherex_dr1_cube'
  const missing = Array.isArray(result?.missing_channels) ? result.missing_channels : []
  const unit = points[0]?.unit || 'MJy/sr'
  const axisTicks = Array.from({ length: 6 }, (_, i) => i)

  return (
    <div style={{ marginTop: 32, paddingTop: 20, borderTop: '1px solid #334155' }}>
      <h2>SPHEREx Infrared Spectrum</h2>
      <p>Explore the measured surface brightness as a function of wavelength.</p>
      <button type="button" onClick={consult} disabled={busy}>
        {busy ? 'Retrieving spectrum...' : 'Query 102-channel spectrum'}
      </button>
      {status && <p role="status" className="viewer-note">{status}</p>}
      {error && <p role="alert" style={{ color: '#fca5a5' }}>{error}</p>}
      {graph && (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', marginTop: 16 }}>
            <label>
              Vertical scale{' '}
              <select value={scale} onChange={event => setScale(event.target.value)}
                style={{ padding: 8, color: 'white', background: '#111827', border: '1px solid #64748b', borderRadius: 8 }}>
                <option value="detail">Detail (5th–95th percentiles)</option>
                <option value="full">Full data range</option>
              </select>
            </label>
            <button type="button" onClick={downloadCsv}>Download CSV</button>
            <button type="button" onClick={downloadPng}>Download PNG</button>
          </div>
          <div style={{ marginTop: 16, overflowX: 'auto' }}>
            <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${W} ${H}`}
              width="100%" role="img" aria-label={`SPHEREx infrared spectrum with ${points.length} valid points`}
              style={{ background: '#08111e', border: '1px solid #334155', borderRadius: 10 }}>
              <rect width={W} height={H} fill="#08111e" />
              <text x={M.left} y={28} fontSize="19" fontWeight="bold" fill="#edf3ff">
                SPHEREx · {cube ? 'DR1 all-sky spectral cube' : 'L2 spectral measurements'}
              </text>
              <text x={M.left} y={45} fontSize="13" fill="#a7b8d1">
                {cube ? `${points.length}/102 channels with measurements · Missing: ${missing.map(m => m.channel).join(', ') || 'none'}` : `${points.length} observations`}
              </text>
              {axisTicks.map(i => {
                const y = M.top + i / 5 * plotH
                const value = graph.high - i / 5 * (graph.high - graph.low)
                return (
                  <g key={`y${i}`}>
                    <line x1={M.left} x2={W - M.right} y1={y} y2={y} stroke="#253951" />
                    <text x={M.left - 12} y={y + 5} textAnchor="end" fontSize="13" fill="#a7b8d1">{format(value)}</text>
                  </g>
                )
              })}
              {Array.from({ length: 7 }, (_, i) => {
                const x = M.left + i / 6 * plotW
                return (
                  <g key={`x${i}`}>
                    <line x1={x} x2={x} y1={M.top} y2={H - M.bottom} stroke="#253951" />
                    <text x={x} y={H - M.bottom + 22} textAnchor="middle" fontSize="13" fill="#a7b8d1">
                      {(graph.xMin + i / 6 * (graph.xMax - graph.xMin)).toFixed(2)}
                    </text>
                  </g>
                )
              })}
              <defs>
                <clipPath id="spectrum-plot-clip"><rect x={M.left} y={M.top} width={plotW} height={plotH} /></clipPath>
              </defs>
              {cube && points.slice(1).map((p, i) => {
                const previous = points[i]
                if (p.channel !== previous.channel + 1 || p.detector !== previous.detector) return null
                if ([p.y, previous.y].some(y => y < graph.low || y > graph.high)) return null
                return <line key={`line-${i}`} x1={graph.x(previous.x)} y1={graph.y(previous.y)}
                  x2={graph.x(p.x)} y2={graph.y(p.y)}
                  stroke={palette[p.detector] || '#7dd3fc'} strokeWidth="1.5" opacity="0.5" />
              })}
              {points.map((p, i) => {
                const x = graph.x(p.x)
                const outside = p.y < graph.low || p.y > graph.high
                const y = Math.max(M.top + 7, Math.min(H - M.bottom - 7, graph.y(p.y)))
                const tip = `Channel ${Number.isInteger(p.channel) ? p.channel : '—'} · ${p.x.toFixed(4)} µm · ${p.y.toPrecision(6)} ${unit}`
                return outside ? (
                  <path key={`point-${i}`} d={p.y > graph.high
                    ? `M ${x} ${M.top + 2} l -6 13 h 12 Z`
                    : `M ${x} ${H - M.bottom - 2} l -6 -13 h 12 Z`}
                    fill="#fb923c"><title>{tip} (outside detail scale)</title></path>
                ) : (
                  <circle key={`point-${i}`} cx={x} cy={y} r="4.5"
                    fill={palette[p.detector] || '#7dd3fc'} stroke="#08111e" strokeWidth="1">
                    <title>{tip}</title>
                  </circle>
                )
              })}
              <text x={W / 2} y={H - 19} textAnchor="middle" fontSize="17" fontWeight="bold" fill="#edf3ff">Wavelength (µm)</text>
              <text transform={`translate(24 ${H / 2}) rotate(-90)`} textAnchor="middle" fontSize="16" fontWeight="bold" fill="#edf3ff">
                Surface brightness ({unit})
              </text>
            </svg>
          </div>
          <p className="viewer-note">
            {cube
              ? '102 nominal channels; missing channels are not interpolated. Thin segments connect only consecutive measured channels from the same detector. Orange triangles mark values outside the detail scale; switch to Full data range to see them.'
              : 'Individual observations are not joined into a calibrated spectral continuum.'}
          </p>
          <p className="viewer-note">
            {result?.scientific_note || 'This visualization does not replace calibrated point-source spectrophotometry.'}
          </p>
        </>
      )}
    </div>
  )
}
