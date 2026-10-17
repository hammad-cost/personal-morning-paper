import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { sendSignal } from '../api'
import { sampleEdition } from '../test/edition'
import Paper from './Paper'
import RecallCheck from './RecallCheck'

vi.mock('../api', () => ({ sendSignal: vi.fn(), swapStory: vi.fn(), getBrain: vi.fn(), pdfUrl: () => '' }))
vi.mock('../copilot/config', () => ({ hasCopilot: () => false, copilotApiKey: '' }))

const quiz = [
  { question: 'What breached live systems?', options: ['Rogue AI agents', 'A solar flare', 'A typo'], answer_index: 0, article_id: 'a1' },
  { question: 'How much did backlogs grow?', options: ['10%', '131%', '50%'], answer_index: 1, article_id: 'a2' },
  { question: 'What deepened?', options: ['A sanctions row', 'A lake', 'A recession'], answer_index: 0, article_id: 'a3' },
]
const group = (n) => screen.getByRole('group', { name: `Answers for question ${n}` })

describe('RecallCheck', () => {
  it('gives instant feedback: right answers and wrong ones with the correct answer shown', () => {
    const onAnswer = vi.fn()
    render(<RecallCheck quiz={quiz} articles={sampleEdition.articles} onAnswer={onAnswer} />)
    expect(screen.getByRole('heading', { name: /can you name 3 things/i })).toBeInTheDocument()

    fireEvent.click(within(group(1)).getByRole('button', { name: 'Rogue AI agents' }))
    expect(onAnswer).toHaveBeenLastCalledWith(quiz[0], true)
    expect(screen.getByText(/^Right\./)).toBeInTheDocument()

    fireEvent.click(within(group(2)).getByRole('button', { name: /10%/ }))
    expect(onAnswer).toHaveBeenLastCalledWith(quiz[1], false)
    expect(screen.getByText(/not quite: it was “131%”/i)).toBeInTheDocument()
  })

  it('locks each question after one answer', () => {
    const onAnswer = vi.fn()
    render(<RecallCheck quiz={quiz} articles={sampleEdition.articles} onAnswer={onAnswer} />)
    fireEvent.click(within(group(1)).getByRole('button', { name: 'A typo' }))
    within(group(1)).getAllByRole('button').forEach((b) => expect(b).toBeDisabled())
    fireEvent.click(within(group(1)).getByRole('button', { name: /rogue ai agents/i }))
    expect(onAnswer).toHaveBeenCalledTimes(1)
  })

  it('shows the score once all three are answered', () => {
    render(<RecallCheck quiz={quiz} articles={sampleEdition.articles} />)
    expect(screen.queryByText(/of 3/)).toBeNull()
    fireEvent.click(within(group(1)).getByRole('button', { name: 'Rogue AI agents' }))
    fireEvent.click(within(group(2)).getByRole('button', { name: /131%/ }))
    fireEvent.click(within(group(3)).getByRole('button', { name: 'A lake' }))
    expect(screen.getByText('2 of 3')).toBeInTheDocument()
  })

  it('leaves out questions about skipped stories, and hides itself with none left', () => {
    const articles = sampleEdition.articles.map((a) => (a.id === 'a2' ? { ...a, skipped: true } : a))
    const { rerender } = render(<RecallCheck quiz={quiz} articles={articles} />)
    expect(screen.queryByText('How much did backlogs grow?')).toBeNull()
    expect(screen.getAllByRole('group')).toHaveLength(2)
    rerender(<RecallCheck quiz={[]} articles={articles} />)
    expect(screen.queryByRole('heading', { name: /can you name 3 things/i })).toBeNull()
  })
})

describe('Recall check in the paper', () => {
  afterEach(() => vi.resetAllMocks())

  it('sits after "You\'re all caught up" and sends QUIZ signals', async () => {
    sendSignal.mockResolvedValue({ applied: true, topic_weights: {} })
    render(<Paper profile={{ paper_title: 'T', topic_weights: {} }} edition={{ ...sampleEdition, recall_quiz: quiz }} />)
    const end = screen.getByRole('region', { name: 'End of paper' })
    expect(within(end).getByRole('heading', { name: /can you name 3 things/i })).toBeInTheDocument()

    await act(async () => fireEvent.click(within(group(2)).getByRole('button', { name: /131%/ })))
    expect(sendSignal).toHaveBeenCalledWith({ action: 'QUIZ_RIGHT', edition_id: sampleEdition.id, article_id: 'a2' })
    await act(async () => fireEvent.click(within(group(3)).getByRole('button', { name: 'A lake' })))
    expect(sendSignal).toHaveBeenLastCalledWith({ action: 'QUIZ_WRONG', edition_id: sampleEdition.id, article_id: 'a3' })
  })
})
