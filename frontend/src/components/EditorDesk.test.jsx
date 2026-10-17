import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { sendSignal, swapStory } from '../api'
import { sampleEdition } from '../test/edition'
import Paper from './Paper'

// Mock CopilotKit: capture tools and context so the test can play the AI.
const copilot = vi.hoisted(() => ({ tools: [], contexts: {}, sidebar: null }))

vi.mock('@copilotkit/react-core/v2', () => ({
  CopilotKit: ({ children }) => children,
  CopilotSidebar: (props) => {
    copilot.sidebar = props
    return props.open ? <div data-testid="editor-desk">Editor Desk open</div> : null
  },
  useFrontendTools: (tools) => {
    copilot.tools = tools
  },
  useAgentContext: ({ description, value }) => {
    copilot.contexts[description.split(':')[0]] = value
  },
}))
vi.mock('@copilotkit/react-core/v2/styles.css', () => ({}))
vi.mock('../copilot/config', () => ({ hasCopilot: () => true, copilotApiKey: 'ck_pub_test' }))
vi.mock('../api', () => ({ sendSignal: vi.fn(), swapStory: vi.fn(), getBrain: vi.fn() }))

const profile = { paper_title: 'THE AYESHA CHRONICLE', topic_weights: { 'AI Agents': 10, Cybersecurity: 8, Politics: 5 } }
const callTool = (name, args) => act(() => copilot.tools.find((t) => t.name === name).handler(args, {}))

async function openDesk() {
  render(<Paper profile={profile} edition={sampleEdition} />)
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Editor Desk' })))
  // The desk is lazy-loaded; the first import in a test run can take a few seconds.
  return screen.findByTestId('editor-desk', {}, { timeout: 8000 })
}

describe('Editor Desk', () => {
  afterEach(() => vi.resetAllMocks())

  it('opens from the masthead and shares the numbered edition and weights', async () => {
    await openDesk()
    const edition = copilot.contexts.currentEdition
    expect(edition.stories.map((s) => [s.number, s.headline])).toEqual([
      [1, 'Rogue AI agents broke into live systems'],
      [2, 'Vulnerability backlogs grew 131%'],
      [3, 'Sanctions row deepens'],
    ])
    expect(copilot.contexts.topicWeights).toEqual(profile.topic_weights)
  })

  it('adjustInterest sends a COPILOT signal with the right delta', async () => {
    sendSignal.mockResolvedValue({
      applied: true,
      signal: { weight: 0 },
      topic_weights: { ...profile.topic_weights, Politics: 0 },
    })
    await openDesk()
    const reply = await callTool('adjustInterest', { topic: 'Politics', direction: 'less', readerWords: 'less politics' })
    expect(sendSignal).toHaveBeenCalledWith({ action: 'COPILOT', topic: 'Politics', delta: -5, note: 'less politics' })
    expect(reply).toMatch(/Politics is now weighted 0/)
    expect(copilot.contexts.topicWeights.Politics).toBe(0)
  })

  it('swapStory replaces the lead live', async () => {
    const fresh = {
      ...sampleEdition.articles[0],
      topic: 'Climate Tech',
      headline: 'Solar startup raises $40M',
      source_name: 'The Verge',
      swapped: true,
    }
    swapStory.mockResolvedValue({ ...sampleEdition, articles: [fresh, ...sampleEdition.articles.slice(1)], sections: ['Climate Tech', 'Cybersecurity', 'World News'] })
    await openDesk()
    await callTool('swapStory', { storyNumber: 1, topic: 'Climate Tech' })

    expect(swapStory).toHaveBeenCalledWith(sampleEdition.id, 'a1', 'Climate Tech')
    const lead = screen.getAllByRole('article')[0]
    expect(within(lead).getByRole('heading', { level: 2 })).toHaveTextContent('Solar startup raises $40M')
    expect(within(lead).getByText("Editor's swap")).toBeInTheDocument()
    expect(screen.queryByText('Rogue AI agents broke into live systems')).toBeNull()
  })

  it('quizMe is switched on and jumps to the recall check', async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    render(<Paper profile={profile} edition={{ ...sampleEdition, recall_quiz: [
      { question: 'Q?', options: ['x', 'y', 'z'], answer_index: 0, article_id: 'a1' },
    ] }} />)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Editor Desk' })))
    await screen.findByTestId('editor-desk', {}, { timeout: 8000 })
    const quizMe = copilot.tools.find((t) => t.name === 'quizMe')
    expect(quizMe.available).toBe(true)
    expect(await callTool('quizMe', {})).toMatch(/opened the recall check/i)
    expect(scrollIntoView.mock.contexts[0]).toBe(document.getElementById('recall-check'))
  })

  it('a repeated swap for the same story and topic does not swap twice', async () => {
    const fresh = { ...sampleEdition.articles[0], topic: 'Climate Tech', headline: 'Solar startup raises $40M', swapped: true }
    swapStory.mockResolvedValue({ ...sampleEdition, articles: [fresh, ...sampleEdition.articles.slice(1)] })
    await openDesk()
    // The model fires the same call twice, overlapping and again after it returns.
    const [first, second] = await act(() =>
      Promise.all(['Climate Tech', 'climate tech'].map((topic) =>
        copilot.tools.find((t) => t.name === 'swapStory').handler({ storyNumber: 1, topic }, {}),
      )),
    )
    const third = await callTool('swapStory', { storyNumber: 1, topic: 'Climate Tech' })
    expect(swapStory).toHaveBeenCalledTimes(1)
    expect(first).toMatch(/Done/)
    expect(second).toMatch(/already swapped/)
    expect(third).toMatch(/already swapped/)
  })
})
