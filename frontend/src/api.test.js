import { getState, onboard, resetStore } from './api'

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
})
