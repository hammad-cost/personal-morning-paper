import { act, fireEvent, render, screen } from '@testing-library/react'
import { emailEdition, updateSettings } from '../api'
import { sampleEdition } from '../test/edition'
import Paper from './Paper'

vi.mock('../api', () => ({
  sendSignal: vi.fn(), swapStory: vi.fn(), getBrain: vi.fn(), downloadPdf: vi.fn(),
  emailEdition: vi.fn(), updateSettings: vi.fn(),
}))
vi.mock('../copilot/config', () => ({ hasCopilot: () => false, copilotApiKey: '' }))

const profile = { name: 'Iqra', paper_title: 'THE IQRA TIMES', topic_weights: {}, daily_email: true }
const account = { id: 'u1', email: 'iqra@uni.edu', signOut: vi.fn() }

describe('Papers by email', () => {
  afterEach(() => vi.resetAllMocks())

  it('emails the paper to the signed-in reader and confirms where it went', async () => {
    emailEdition.mockResolvedValue({ sent_to: 'iqra@uni.edu' })
    render(<Paper profile={profile} edition={sampleEdition} account={account} emailReady />)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: /email me this paper/i })))
    expect(emailEdition).toHaveBeenCalledWith(sampleEdition.id)
    expect(screen.getByRole('status')).toHaveTextContent('Sent to iqra@uni.edu')
  })

  it('shows the server message when sending fails', async () => {
    emailEdition.mockRejectedValue(new Error("That's enough emails for today. Try again tomorrow."))
    render(<Paper profile={profile} edition={sampleEdition} account={account} emailReady />)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: /email me this paper/i })))
    expect(screen.getByRole('alert')).toHaveTextContent(/enough emails for today/i)
  })

  it('switches the morning email on and off', async () => {
    updateSettings.mockResolvedValue({})
    render(<Paper profile={profile} edition={sampleEdition} account={account} emailReady />)
    const box = screen.getByRole('checkbox', { name: /email me my paper every morning/i })
    expect(box).toBeChecked()
    await act(async () => fireEvent.click(box))
    expect(updateSettings).toHaveBeenCalledWith({ daily_email: false })
    expect(box).not.toBeChecked()
  })

  it('hides email controls in local mode or when email is not set up', () => {
    const { rerender } = render(<Paper profile={profile} edition={sampleEdition} />)
    expect(screen.queryByRole('button', { name: /email me this paper/i })).toBeNull()
    rerender(<Paper profile={profile} edition={sampleEdition} account={account} emailReady={false} />)
    expect(screen.queryByRole('checkbox')).toBeNull()
  })
})
