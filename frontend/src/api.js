// The only place the frontend talks to the backend.
// Vite proxies /api to http://localhost:8000 in dev.

async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    throw new Error(`${options.method ?? 'GET'} /api${path} failed: ${response.status}`)
  }
  return response.json()
}

export const getState = () => request('/state')

export const onboard = (profile) =>
  request('/onboard', { method: 'POST', body: JSON.stringify(profile) })

export const resetStore = () => request('/reset', { method: 'POST' })
