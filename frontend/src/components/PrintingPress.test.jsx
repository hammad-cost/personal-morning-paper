import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { getGenerationStatus, getTodayEdition } from '../api'
import { sampleEdition } from '../test/edition'
import PrintingPress from './PrintingPress'

vi.mock('../api', () => ({ getTodayEdition: vi.fn(), getGenerationStatus: vi.fn() }))

const deferred = () => {
  let resolve, reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('PrintingPress', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.resetAllMocks()
  })

  it('shows the real press step while the edition is made, then hands it over', async () => {
    vi.useFakeTimers()
    const pending = deferred()
    getTodayEdition.mockReturnValue(pending.promise)
    getGenerationStatus.mockResolvedValue({ state: 'running', step: 'writing', step_index: 2 })
    const onReady = vi.fn()
    render(<PrintingPress onReady={onReady} pollMs={100} />)

    expect(screen.getByText('Gathering articles')).toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(150))

    const current = screen.getByText('Writing your summaries').closest('li')
    expect(current).toHaveAttribute('aria-current', 'step')
    expect(screen.getByText('Gathering articles').closest('li')).toHaveTextContent('(done)')
    expect(screen.getByText('Setting the type').closest('li')).not.toHaveTextContent('(done)')

    await act(async () => pending.resolve(sampleEdition))
    expect(onReady).toHaveBeenCalledWith(sampleEdition)
  })

  it('shows the error and lets the reader try again', async () => {
    getTodayEdition.mockRejectedValueOnce(new Error('Not enough fresh news found for your topics.'))
    getTodayEdition.mockResolvedValueOnce(sampleEdition)
    getGenerationStatus.mockResolvedValue({ state: 'error', step: null, step_index: -1 })
    const onReady = vi.fn()
    const user = userEvent.setup()
    render(<PrintingPress onReady={onReady} />)

    expect(await screen.findByRole('alert')).toHaveTextContent(/not enough fresh news/i)
    await user.click(screen.getByRole('button', { name: /try again/i }))
    await vi.waitFor(() => expect(onReady).toHaveBeenCalledWith(sampleEdition))
    expect(getTodayEdition).toHaveBeenCalledTimes(2)
  })
})
