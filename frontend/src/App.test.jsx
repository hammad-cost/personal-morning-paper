import { render, screen } from '@testing-library/react'
import { getGenerationStatus, getState, getTodayEdition } from './api'
import App from './App'
import { sampleEdition } from './test/edition'

vi.mock('./api', () => ({ getState: vi.fn(), getTodayEdition: vi.fn(), getGenerationStatus: vi.fn() }))

const profile = {
  onboarded: true,
  name: 'Ayesha',
  paper_title: 'THE AYESHA CHRONICLE',
  bio: '',
  topic_weights: {},
  source_weights: {},
  created_at: null,
}

describe('App', () => {
  beforeEach(() => {
    getGenerationStatus.mockResolvedValue({ state: 'idle', step: null, step_index: -1 })
  })
  afterEach(() => vi.resetAllMocks())

  it('shows onboarding when not onboarded', async () => {
    getState.mockResolvedValue({ onboarded: false, profile: { ...profile, onboarded: false }, today_edition_id: null })
    render(<App />)
    expect(await screen.findByText(/every great paper starts with its reader/i)).toBeInTheDocument()
    expect(getTodayEdition).not.toHaveBeenCalled()
  })

  it('runs the press and then shows the paper with the masthead when onboarded', async () => {
    getState.mockResolvedValue({ onboarded: true, profile, today_edition_id: null })
    getTodayEdition.mockResolvedValue(sampleEdition)
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'THE AYESHA CHRONICLE' })).toBeInTheDocument()
    expect(screen.getByText(/edition no\. 1/i)).toBeInTheDocument()
    expect(screen.getByText(/today's paper: 4 min/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Rogue AI agents broke into live systems' })).toBeInTheDocument()
    expect(screen.queryByText(/every great paper starts with its reader/i)).not.toBeInTheDocument()
  })

  it('shows an error when the backend is unreachable', async () => {
    getState.mockRejectedValue(new Error('network'))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not reach the newsroom/i)
  })
})
