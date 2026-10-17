import { accessToken } from './auth/supabase'

// The only place the frontend talks to the backend (address: see apiBase.js).
import { API_BASE } from './apiBase'

export { API_BASE, assetUrl } from './apiBase'

async function authHeaders() {
  const token = await accessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()), ...options.headers },
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

export const printNextEdition = () => request('/edition/next', { method: 'POST' })

export const listEditions = () => request('/editions')

export const getEdition = (id) => request(`/edition/${encodeURIComponent(id)}`)

export const pdfUrl = (id) => `${API_BASE}/api/edition/${encodeURIComponent(id)}/pdf`

// Fetch the PDF with the reader's login, then hand it to the browser as a download.
export async function downloadPdf(id) {
  const response = await fetch(pdfUrl(id), { headers: await authHeaders() })
  if (!response.ok) throw new Error(`Could not download the PDF (${response.status})`)
  const name = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') || '')?.[1] || `vale-${id}.pdf`
  const url = URL.createObjectURL(await response.blob())
  const link = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return name
}

// keepalive lets a CLICK finish even while the browser is busy opening the article.
export const sendSignal = (signal) =>
  request('/signal', { method: 'POST', body: JSON.stringify(signal), keepalive: true })

export const getBrain = () => request('/brain')

// Email an edition (PDF attached) to the signed-in reader's own address.
export const emailEdition = (id) => request(`/edition/${encodeURIComponent(id)}/email`, { method: 'POST' })

export const updateSettings = (settings) => request('/settings', { method: 'POST', body: JSON.stringify(settings) })

export const swapStory = (editionId, articleId, topic) =>
  request(`/edition/${encodeURIComponent(editionId)}/swap`, {
    method: 'POST',
    body: JSON.stringify({ article_id: articleId, topic }),
  })
