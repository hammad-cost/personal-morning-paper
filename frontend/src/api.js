// The only place the frontend talks to the backend.
// Vite proxies /api to http://localhost:8000 in dev.

async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    // FastAPI errors carry a human-readable "detail"; fall back to the status code.
    let detail = null
    try {
      detail = (await response.json()).detail
    } catch {
      // no JSON body
    }
    throw new Error(
      typeof detail === 'string' ? detail : `${options.method ?? 'GET'} /api${path} failed: ${response.status}`,
    )
  }
  return response.json()
}

export const getState = () => request('/state')

export const onboard = (profile) =>
  request('/onboard', { method: 'POST', body: JSON.stringify(profile) })

export const resetStore = () => request('/reset', { method: 'POST' })

export const getTodayEdition = () => request('/edition/today')

export const getGenerationStatus = () => request('/generation/status')

// keepalive lets a CLICK finish even while the browser is busy opening the article.
export const sendSignal = (signal) =>
  request('/signal', { method: 'POST', body: JSON.stringify(signal), keepalive: true })

export const getBrain = () => request('/brain')
