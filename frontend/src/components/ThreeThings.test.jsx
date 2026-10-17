import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { sendSignal } from '../api'
import { sampleEdition } from '../test/edition'
import Paper from './Paper'
import { pickThreeThings } from './ThreeTakeaways'

vi.mock('../api', () => ({ sendSignal: vi.fn(), swapStory: vi.fn(), getBrain: vi.fn(), downloadPdf: vi.fn() }))
vi.mock('../copilot/config', () => ({ hasCopilot: () => false, copilotApiKey: '' }))

const takeaways = sampleEdition.three_takeaways // a1, a2, a3
const articles = sampleEdition.articles

describe('pickThreeThings', () => {
  it('puts what you got right first and what you missed last', () => {
    const things = pickThreeThings(takeaways, articles, { a3: true, a1: false })
    expect(things.map((t) => [t.article_id, t.status])).toEqual([['a3', 'right'], ['a2', null], ['a1', 'wrong']])
  })

  it('drops skipped stories and adds a story you answered right', () => {
    const extra = { ...articles[0], id: 'a9', headline: 'Quantum chips got smaller' }
    const list = [...articles.map((a) => (a.id === 'a2' ? { ...a, skipped: true } : a)), extra]
    const things = pickThreeThings(takeaways, list, { a9: true })
    expect(things.map((t) => t.text)).toEqual(['Quantum chips got smaller', takeaways[0].text, takeaways[2].text])
  })
})

describe('3 Things in the paper', () => {
  const profile = { name: 'Iqra', paper_title: 'THE IQRA TIMES', topic_weights: {} }
  const edition = {
    ...sampleEdition,
    recall_quiz: [{ question: 'Who was named director?', options: ['A NASA veteran', 'A chef', 'A pilot'], answer_index: 0, article_id: 'a3' }],
  }

  beforeEach(() => {
    window.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
    sendSignal.mockResolvedValue({ applied: true, topic_weights: {} })
  })
  afterEach(() => vi.resetAllMocks())

  it('is not at the top of the feed: it ends the feed and updates after the brain check', async () => {
    window.localStorage.setItem('vale.view', 'feed')
    render(<Paper profile={profile} edition={edition} />)
    const end = screen.getByRole('region', { name: 'End of paper' })
    const things = within(end).getByRole('region', { name: /3 things you learned today/i })
    expect(screen.getAllByRole('region', { name: /3 things you learned today/i })).toHaveLength(1)
    expect(within(things).getByText(/answer the brain checks/i)).toBeInTheDocument()

    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'A NASA veteran' })))
    expect(within(things).getByText(/you got 1 of 1 brain-check question right/i)).toBeInTheDocument()
    const first = within(things).getAllByRole('listitem')[0]
    expect(first).toHaveTextContent(takeaways[2].text)
    expect(first).toHaveTextContent('Remembered')
  })
})
