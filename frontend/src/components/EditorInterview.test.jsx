import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { onboard } from '../api'
import EditorInterview from './EditorInterview'

// Mock CopilotKit: capture the registered tools and context so tests can play the AI.
const copilot = vi.hoisted(() => ({ tools: [], contexts: {} }))

vi.mock('@copilotkit/react-core/v2', () => ({
  CopilotKit: ({ children }) => children,
  CopilotChat: () => <div data-testid="copilot-chat" />,
  useFrontendTools: (tools) => {
    copilot.tools = tools
  },
  useAgentContext: ({ description, value }) => {
    copilot.contexts[description.split(':')[0]] = value
  },
}))
vi.mock('@copilotkit/react-core/v2/styles.css', () => ({}))
vi.mock('../api', () => ({ onboard: vi.fn() }))

const callTool = (name, args) => {
  const tool = copilot.tools.find((t) => t.name === name)
  return act(() => tool.handler(args, {}))
}

describe('EditorInterview', () => {
  afterEach(() => vi.resetAllMocks())

  it('fills the profile card live as the Editor calls tools', async () => {
    render(<EditorInterview onDone={() => {}} onFallback={() => {}} />)
    expect(screen.getByTestId('copilot-chat')).toBeInTheDocument()

    await callTool('setReaderName', { name: 'Ayesha' })
    await callTool('addTopics', { topics: [{ name: 'AI Agents', level: 'core' }, { name: 'Cybersecurity', level: 'core' }] })
    await callTool('blockTopics', { topics: ['Celebrity Gossip'] })
    await callTool('setBio', { bio: 'CS student' })

    expect(screen.getByRole('heading', { name: 'THE AYESHA CHRONICLE' })).toBeInTheDocument()
    expect(screen.getByLabelText('AI Agents, weight 10')).toBeInTheDocument()
    expect(screen.getByLabelText('Celebrity Gossip, weight -10, blocked')).toBeInTheDocument()
    expect(screen.getByText(/CS student/)).toBeInTheDocument()
  })

  it('shares the profile draft, including hand edits, with the chat', async () => {
    const user = userEvent.setup()
    render(<EditorInterview onDone={() => {}} onFallback={() => {}} />)
    await callTool('addTopics', { topics: [{ name: 'Space', level: 'casual' }] })
    await user.click(screen.getByRole('button', { name: 'Raise Space' }))
    expect(copilot.contexts.readerProfileDraft.topics).toEqual({ Space: 6 })
    expect(copilot.contexts['Your instructions as the newspaper editor. Follow them exactly.']).toMatch(/one short question/i)
  })

  it('finishOnboarding saves the profile and hands over the new state', async () => {
    const state = { onboarded: true }
    onboard.mockResolvedValue(state)
    const onDone = vi.fn()
    render(<EditorInterview onDone={onDone} onFallback={() => {}} />)

    expect(await callTool('finishOnboarding', {})).toMatch(/not ready/i)
    expect(onboard).not.toHaveBeenCalled()

    await callTool('setReaderName', { name: 'Ayesha' })
    await callTool('addTopics', { topics: [{ name: 'AI Agents', level: 'core' }] })
    await callTool('finishOnboarding', {})

    expect(onboard).toHaveBeenCalledWith({
      name: 'Ayesha',
      paper_title: 'THE AYESHA CHRONICLE',
      bio: '',
      topic_weights: { 'AI Agents': 10 },
    })
    expect(onDone).toHaveBeenCalledWith(state)
  })

  it('offers Quick setup as a fallback', async () => {
    const onFallback = vi.fn()
    const user = userEvent.setup()
    render(<EditorInterview onDone={() => {}} onFallback={onFallback} />)
    await user.click(screen.getByRole('button', { name: /switch to quick setup/i }))
    expect(onFallback).toHaveBeenCalled()
  })
})
