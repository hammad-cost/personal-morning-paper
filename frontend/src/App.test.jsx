import { render, screen } from '@testing-library/react'
import { getState } from './api'
import App from './App'

vi.mock('./api', () => ({ getState: vi.fn() }))

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
  afterEach(() => vi.resetAllMocks())

  it('shows onboarding when not onboarded', async () => {
    getState.mockResolvedValue({ onboarded: false, profile: { ...profile, onboarded: false }, today_edition_id: null })
    render(<App />)
    expect(await screen.findByText(/every great paper starts with its reader/i)).toBeInTheDocument()
    expect(screen.queryByText('THE AYESHA CHRONICLE')).not.toBeInTheDocument()
  })

  it('shows the paper with the masthead when onboarded', async () => {
    getState.mockResolvedValue({ onboarded: true, profile, today_edition_id: null })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'THE AYESHA CHRONICLE' })).toBeInTheDocument()
    expect(screen.queryByText(/every great paper starts with its reader/i)).not.toBeInTheDocument()
  })

  it('shows an error when the backend is unreachable', async () => {
    getState.mockRejectedValue(new Error('network'))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not reach the newsroom/i)
  })
})
