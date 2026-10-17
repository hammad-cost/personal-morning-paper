import { getGenerationStatus, getState, getTodayEdition, onboard, resetStore } from './api'
import { accessToken } from './auth/supabase'

vi.mock('./auth/supabase', () => ({ accessToken: vi.fn(async () => null) }))

describe('api', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ ok: true }) })
  })

  it('getState calls GET /api/state', async () => {
    await getState()
    expect(fetch).toHaveBeenCalledWith('/api/state', expect.any(Object))
  })

  it('onboard POSTs the profile as JSON', async () => {
    await onboard({ name: 'Ayesha' })
    const [url, options] = fetch.mock.calls[0]
    expect(url).toBe('/api/onboard')
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({ name: 'Ayesha' })
  })

  it('resetStore POSTs /api/reset', async () => {
    await resetStore()
    expect(fetch).toHaveBeenCalledWith('/api/reset', expect.objectContaining({ method: 'POST' }))
  })

  it('throws on a non-OK response', async () => {
    fetch.mockResolvedValue({ ok: false, status: 500 })
    await expect(getState()).rejects.toThrow(/500/)
  })

  it("uses FastAPI's detail message when there is one", async () => {
    fetch.mockResolvedValue({ ok: false, status: 503, json: () => Promise.resolve({ detail: 'Not enough fresh news' }) })
    await expect(getTodayEdition()).rejects.toThrow('Not enough fresh news')
  })

  it('edition calls hit the right endpoints', async () => {
    await getTodayEdition()
    await getGenerationStatus()
    expect(fetch.mock.calls.map((c) => c[0])).toEqual(['/api/edition/today', '/api/generation/status'])
  })

  it("sends the reader's login token when signed in", async () => {
    accessToken.mockResolvedValueOnce('jwt-abc')
    await getState()
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer jwt-abc')
  })

  it('sends no Authorization header in local mode', async () => {
    await getState()
    expect(fetch.mock.calls[0][1].headers.Authorization).toBeUndefined()
  })
})
