import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ReaderProfileCard from './ReaderProfileCard'

const profile = {
  name: 'Ayesha',
  paper_title: 'THE AYESHA CHRONICLE',
  bio: 'CS student',
  topics: { 'AI Agents': 10, Space: 5, 'Celebrity Gossip': -10 },
}

describe('ReaderProfileCard', () => {
  it('lets the reader name their paper by typing or picking an idea', async () => {
    const dispatch = vi.fn()
    const user = userEvent.setup()
    render(<ReaderProfileCard profile={{ ...profile, name: 'Iqra', paper_title: 'THE IQRA CHRONICLE' }} dispatch={dispatch} />)

    await user.click(screen.getByRole('button', { name: 'THE IQRA TIMES' }))
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'SET_PAPER_TITLE', title: 'THE IQRA TIMES' })

    const field = screen.getByLabelText('Name your paper')
    await user.clear(field)
    await user.type(field, 'The Morning Iqra{Enter}')
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'SET_PAPER_TITLE', title: 'The Morning Iqra' })
  })

  it('renders masthead, pills and weights', () => {
    render(<ReaderProfileCard profile={profile} dispatch={() => {}} />)
    expect(screen.getByRole('heading', { name: 'THE AYESHA CHRONICLE' })).toBeInTheDocument()
    expect(screen.getByLabelText('AI Agents, weight 10')).toBeInTheDocument()
    expect(screen.getByLabelText('Space, weight 5')).toBeInTheDocument()
    expect(screen.getByLabelText('Celebrity Gossip, weight -10, blocked')).toBeInTheDocument()
    expect(screen.getByText(/never show/i)).toBeInTheDocument()
  })

  it('dispatches edits from the pill buttons and the add form', async () => {
    const dispatch = vi.fn()
    const user = userEvent.setup()
    render(<ReaderProfileCard profile={profile} dispatch={dispatch} />)

    const pill = screen.getByLabelText('Space, weight 5')
    await user.click(within(pill).getByRole('button', { name: 'Raise Space' }))
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'SET_WEIGHT', topic: 'Space', weight: 6 })

    await user.click(within(pill).getByRole('button', { name: 'Remove Space' }))
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'REMOVE_TOPIC', topic: 'Space' })

    await user.type(screen.getByLabelText('Add a topic'), 'Quantum Computing{Enter}')
    expect(dispatch).toHaveBeenLastCalledWith({
      type: 'ADD_TOPICS',
      topics: [{ name: 'Quantum Computing', level: 'core' }],
    })
  })
})
