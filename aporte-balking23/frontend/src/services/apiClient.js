
const API_BASE = '/api'

async function requestJson(endpoint, options = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...options.headers,
    },
  })

  const contentType = response.headers.get('content-type') || ''

  let data

  if (contentType.includes('application/json')) {
    data = await response.json()
  } else {
    data = await response.text()
  }

  if (!response.ok) {
    const message =
      typeof data === 'object' && data !== null
        ? data.error || data.message || `HTTP ${response.status}`
        : `HTTP ${response.status}: ${String(data).slice(0, 150)}`

    throw new Error(message)
  }

  return data
}

export const apiClient = {
  // Check backend availability.
  getHealth(signal) {
    return requestJson('/health', { signal })
  },

  // Retrieve SPHEREx collections.
  getCollections(signal) {
    return requestJson('/collections', { signal })
  },

  // Retrieve observations using backend query parameters.
  getObservations(params = {}, signal) {
    const query = new URLSearchParams()

    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        query.set(key, String(value))
      }
    })

    const suffix = query.toString()

    return requestJson(
      `/observations${suffix ? `?${suffix}` : ''}`,
      { signal }
    )
  },

  // Submit a scientific processing job.
  createJob(payload, signal) {
    return requestJson('/jobs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal,
    })
  },

  // Retrieve job status.
  getJob(jobId, signal) {
    return requestJson(
      `/jobs/${encodeURIComponent(jobId)}`,
      { signal }
    )
  },

  // Build a frame image URL.
  getFrameUrl(jobId, index, overlay = null) {
    const base =
      `${API_BASE}/jobs/${encodeURIComponent(jobId)}` +
      `/frames/${encodeURIComponent(index)}.png`

    return overlay
      ? `${base}?overlay=${encodeURIComponent(overlay)}`
      : base
  },

  // Build an animation URL.
  getAnimationUrl(jobId) {
    return `${API_BASE}/jobs/${encodeURIComponent(jobId)}/animation.gif`
  },

  // Build a processed image URL.
  getResultImageUrl(jobId) {
    return `${API_BASE}/jobs/${encodeURIComponent(jobId)}/result.png`
  },

  // Build a scientific FITS export URL.
  getResultFitsUrl(jobId) {
    return `${API_BASE}/jobs/${encodeURIComponent(jobId)}/result.fits`
  },
}
