import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { hasCopilot } from '../copilot/config'
import Onboarding from './Onboarding'

vi.mock('../copilot/config', () => ({ hasCopilot: vi.fn() }))
vi.mock('./EditorInterview', () => ({ default: () => <p>Editor interview</p> }))
vi.mock('../api', () => ({ onboard: vi.fn() }))

describe('Onboarding', () => {
  afterEach(() => vi.resetAllMocks())

  it('offers both paths and opens the Editor chat', async () => {
    hasCopilot.mockReturnValue(true)
    const user = userEvent.setup()
    render(<Onboarding onOnboarded={() => {}} />)
    expect(screen.getByText(/every great paper starts with its reader/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /talk to the editor/i }))
    expect(await screen.findByText('Editor interview')).toBeInTheDocument()
  })

  it('opens Quick setup', async () => {
    hasCopilot.mockReturnValue(true)
    const user = userEvent.setup()
    render(<Onboarding onOnboarded={() => {}} />)
    await user.click(screen.getByRole('button', { name: /quick setup/i }))
    expect(screen.getByRole('form', { name: /quick setup/i })).toBeInTheDocument()
  })

  it('disables the Editor chat when no CopilotKit key is set', () => {
    hasCopilot.mockReturnValue(false)
    render(<Onboarding onOnboarded={() => {}} />)
    expect(screen.getByRole('button', { name: /talk to the editor/i })).toBeDisabled()
    expect(screen.getByText(/VITE_COPILOTKIT_PUBLIC_API_KEY/)).toBeInTheDocument()
  })
})
