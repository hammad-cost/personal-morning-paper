import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { getBrain, sendSignal } from '../api'
import { sampleEdition } from '../test/edition'
import BrainPanel from './BrainPanel'
import Paper, { FADE_MS, UNDO_MS } from './Paper'

vi.mock('../api', () => ({ sendSignal: vi.fn(), getBrain: vi.fn() }))

const profile = { paper_title: 'THE AYESHA CHRONICLE', topic_weights: { 'AI Agents': 10, Cybersecurity: 8 } }
const brain = {
  topic_weights: { 'AI Agents': 10, Cybersecurity: 5, Crypto: -10 },
  source_weights: {},
  signals: [{ ts: '2026-10-17T08:00:00Z', action: 'SKIP', topic: 'Cybersecurity', delta: -3, text: 'Skipped a Cybersecurity story · Cybersecurity −3' }],
  min_weight: -15,
  max_weight: 25,
}

const card = (headline) => screen.queryByRole('article', { name: headline })
const skipButton = (headline) => within(card(headline)).getByRole('button', { name: /skip/i })

describe('Skip and Undo', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    sendSignal.mockResolvedValue({ applied: true, topic_weights: { 'AI Agents': 10, Cybersecurity: 5 } })
    getBrain.mockResolvedValue(brain)
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.resetAllMocks()
  })

  const HEADLINE = 'Vulnerability backlogs grew 131%'

  it('skip fades the card, offers Undo for 5 seconds, then the card is gone', async () => {
    render(<Paper profile={profile} edition={sampleEdition} />)
    await act(async () => fireEvent.click(skipButton(HEADLINE)))

    expect(sendSignal).toHaveBeenCalledWith({ action: 'SKIP', edition_id: sampleEdition.id, article_id: 'a2' })
    // Fading: still in the page for 250 ms, but hidden from screen readers.
    expect(card(HEADLINE)).toBeNull()
    const fading = document.getElementById('story-a2')
    expect(fading).toHaveAttribute('aria-hidden', 'true')
    expect(fading).toHaveClass('opacity-0')

    await act(() => vi.advanceTimersByTimeAsync(FADE_MS))
    expect(card(HEADLINE)).toBeNull()
    expect(screen.getByRole('status')).toHaveTextContent(/skipped/i)
    expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument()

    await act(() => vi.advanceTimersByTimeAsync(UNDO_MS))
    expect(screen.queryByRole('status')).toBeNull()
    expect(card(HEADLINE)).toBeNull()
    expect(screen.getByText(/2 stories, finished/i)).toBeInTheDocument()
  })

  it('undo restores the card and sends UNSKIP', async () => {
    render(<Paper profile={profile} edition={sampleEdition} />)
    await act(async () => fireEvent.click(skipButton(HEADLINE)))
    await act(() => vi.advanceTimersByTimeAsync(FADE_MS))

    await act(async () => fireEvent.click(screen.getByRole('button', { name: /undo/i })))
    expect(sendSignal).toHaveBeenLastCalledWith({ action: 'UNSKIP', edition_id: sampleEdition.id, article_id: 'a2' })
    expect(card(HEADLINE)).toBeInTheDocument()
    expect(card(HEADLINE)).not.toHaveAttribute('aria-hidden')

    // The old 5-second timer must not remove the restored card.
    await act(() => vi.advanceTimersByTimeAsync(UNDO_MS + FADE_MS))
    expect(card(HEADLINE)).toBeInTheDocument()
  })

  it('brings the card back if the skip could not be saved', async () => {
    sendSignal.mockRejectedValueOnce(new Error('offline'))
    render(<Paper profile={profile} edition={sampleEdition} />)
    await act(async () => fireEvent.click(skipButton(HEADLINE)))
    expect(screen.getByRole('alert')).toHaveTextContent(/could not skip/i)
    expect(card(HEADLINE)).not.toHaveAttribute('aria-hidden')
  })

  it('stories already skipped in the saved edition stay hidden', () => {
    const edition = { ...sampleEdition, articles: sampleEdition.articles.map((a) => (a.id === 'a2' ? { ...a, skipped: true } : a)) }
    render(<Paper profile={profile} edition={edition} />)
    expect(card(HEADLINE)).toBeNull()
  })

  it('Read Original sends one CLICK and "Why this story?" shows the new weight', async () => {
    render(<Paper profile={profile} edition={sampleEdition} />)
    const link = within(card(HEADLINE)).getByRole('link', { name: /read original/i })
    await act(async () => fireEvent.click(link))
    await act(async () => fireEvent.click(link))
    expect(sendSignal).toHaveBeenCalledTimes(1)
    expect(sendSignal).toHaveBeenCalledWith({ action: 'CLICK', edition_id: sampleEdition.id, article_id: 'a2' })

    await act(async () => fireEvent.click(within(card(HEADLINE)).getByRole('button', { name: /why this story/i })))
    expect(screen.getByText(/you follow cybersecurity \(weight 5\)/i)).toBeInTheDocument()
  })

  it('the Brain button opens the drawer', async () => {
    render(<Paper profile={profile} edition={sampleEdition} />)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Brain' })))
    expect(screen.getByRole('dialog', { name: 'The Brain' })).toHaveAttribute('aria-hidden', 'false')
    expect(getBrain).toHaveBeenCalled()
  })
})

describe('BrainPanel', () => {
  afterEach(() => vi.resetAllMocks())

  it('shows weight bars and the latest signals in plain words', async () => {
    getBrain.mockResolvedValue(brain)
    render(<BrainPanel open onClose={() => {}} refreshKey={0} />)
    const weights = await screen.findByRole('list', { name: 'Topic weights' })
    const rows = within(weights).getAllByRole('listitem')
    expect(rows.map((r) => r.textContent)).toEqual(['AI Agents+10', 'Cybersecurity+5', 'Crypto-10'])
    expect(screen.getByText('Skipped a Cybersecurity story · Cybersecurity −3')).toBeInTheDocument()
  })

  it('Escape closes it', async () => {
    getBrain.mockResolvedValue(brain)
    const onClose = vi.fn()
    render(<BrainPanel open onClose={onClose} refreshKey={0} />)
    await screen.findByRole('list', { name: 'Topic weights' })
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})
