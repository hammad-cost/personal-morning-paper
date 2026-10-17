// Where the backend lives. Locally Vite forwards /api to http://localhost:8000, so this is
// empty. Online, VITE_API_BASE is the backend's own address (e.g. https://vale-api.onrender.com).
export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').trim().replace(/\/$/, '')

// Pictures and logos the backend serves (/api/images/..., /api/logos/...) live on the API server.
export const assetUrl = (url) => (url && url.startsWith('/api/') ? `${API_BASE}${url}` : url)
