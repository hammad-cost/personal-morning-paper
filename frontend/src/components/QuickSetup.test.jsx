import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { onboard } from '../api'
import QuickSetup from './QuickSetup'

vi.mock('../api', () => ({ onboard: vi.fn() }))

describe('QuickSetup', () => {
  afterEach(() => vi.resetAllMocks())

  it('submits the right payload', async () => {
    const state = { onboarded: true }
    onboard.mockResolvedValue(state)
    const onDone = vi.fn()
    const user = userEvent.setup()
    render(<QuickSetup onDone={onDone} />)

    const submit = screen.getByRole('button', { name: /print my first edition/i })
    expect(submit).toBeDisabled()

    await user.type(screen.getByLabelText(/your name/i), 'Ayesha')
    await user.click(screen.getByRole('button', { name: 'AI Agents' }))
    await user.click(screen.getByRole('button', { name: 'Cybersecurity' }))
    await user.type(screen.getByLabelText(/one line about you/i), 'CS student')
    await user.click(submit)

    expect(onboard).toHaveBeenCalledWith({
      name: 'Ayesha',
      paper_title: 'THE AYESHA CHRONICLE',
      bio: 'CS student',
      topic_weights: { 'AI Agents': 10, Cybersecurity: 10 },
    })
    expect(onDone).toHaveBeenCalledWith(state)
  })

  it('sends the paper name the reader picked', async () => {
    onboard.mockResolvedValue({ onboarded: true })
    const user = userEvent.setup()
    render(<QuickSetup onDone={() => {}} />)
    await user.type(screen.getByLabelText(/your name/i), 'Iqra')
    await user.click(screen.getByRole('button', { name: 'Space' }))
    await user.click(screen.getByRole('button', { name: 'THE IQRA DAILY' }))
    await user.click(screen.getByRole('button', { name: /print my first edition/i }))
    expect(onboard).toHaveBeenCalledWith(expect.objectContaining({ name: 'Iqra', paper_title: 'THE IQRA DAILY' }))
  })

  it('shows an error if saving fails', async () => {
    onboard.mockRejectedValue(new Error('down'))
    const user = userEvent.setup()
    render(<QuickSetup onDone={() => {}} />)
    await user.type(screen.getByLabelText(/your name/i), 'Ayesha')
    await user.click(screen.getByRole('button', { name: 'Space' }))
    await user.click(screen.getByRole('button', { name: /print my first edition/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not save/i)
  })
})
