import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { sampleEdition } from '../test/edition'
import BroadsheetGrid, { columnRule, groupBySection } from './BroadsheetGrid'
import Paper from './Paper'
import StoryCard from './StoryCard'
import ThreeTakeaways from './ThreeTakeaways'

const story = (id, topic, extra = {}) => ({
  id, topic, headline: `Headline ${id}`, summary: `Summary ${id}`, why_it_matters: `Why ${id}`,
  source_name: `Source ${id}`, url: `https://news.test/${id}`, score: 10, is_lead: false, is_explore: false,
  label: null, skipped: false, clicked: false, ...extra,
})

// Deliberately shuffled so order must come from `sections`, not from the array.
const articles = [
  story('a5', 'Space'),
  story('a2', 'Cybersecurity'),
  story('a1', 'AI Agents', { is_lead: true, score: 15 }),
  story('a3', 'AI Agents'),
  story('a4', 'Cybersecurity'),
  story('a6', 'World News', { is_explore: true, label: 'Something new' }),
]
const sections = ['AI Agents', 'Cybersecurity', 'Space', 'World News']

describe('BroadsheetGrid', () => {
  it('renders the lead story first', () => {
    render(<BroadsheetGrid articles={articles} sections={sections} />)
    const cards = screen.getAllByRole('article')
    expect(cards[0]).toHaveAccessibleName('Headline a1')
    expect(within(cards[0]).getByRole('heading', { level: 2 })).toHaveTextContent('Headline a1')
    expect(cards).toHaveLength(6)
  })

  it('prints sections in the given order, with their stories inside', () => {
    render(<BroadsheetGrid articles={articles} sections={sections} />)
    const headings = screen.getAllByRole('heading', { level: 2 }).slice(1).map((h) => h.textContent)
    expect(headings).toEqual(['AI Agents', 'Cybersecurity', 'Space', 'World News'])
    const cyber = screen.getByRole('region', { name: 'Cybersecurity' })
    expect(within(cyber).getAllByRole('article').map((a) => a.id)).toEqual(['story-a2', 'story-a4'])
  })

  it('draws a column rule only when a card has a neighbour to its right', () => {
    // 2 cards: rule after the first only.
    expect(columnRule(0, 2)).toBe('md:border-r lg:border-r')
    expect(columnRule(1, 2)).toBe('md:border-r-0 lg:border-r-0')
    // 4 cards: md rows (0,1)(2,3); lg rows (0,1,2)(3).
    expect([0, 1, 2, 3].map((i) => columnRule(i, 4))).toEqual([
      'md:border-r lg:border-r',
      'md:border-r-0 lg:border-r',
      'md:border-r lg:border-r-0',
      'md:border-r-0 lg:border-r-0',
    ])
  })

  it('groupBySection leaves out empty sections and keeps unknown topics at the end', () => {
    const { lead, sections: grouped } = groupBySection(
      [story('x1', 'Solo', { is_lead: true }), story('x2', 'Mystery')],
      ['Solo'],
    )
    expect(lead.id).toBe('x1')
    expect(grouped.map((s) => s.name)).toEqual(['Mystery'])
  })
})

describe('StoryCard', () => {
  it('shows the news photo with a credit, linking straight to the publisher', () => {
    const { container } = render(
      <StoryCard
        article={story('a1', 'AI Agents', { image_url: 'https://cdn.test/a1.jpg', publisher_url: 'https://pub.test/a1' })}
        lead
      />,
    )
    const img = container.querySelector('img')
    expect(img).toHaveAttribute('src', 'https://cdn.test/a1.jpg')
    expect(img).toHaveAttribute('referrerpolicy', 'no-referrer')
    expect(screen.getByText('Photo: Source a1')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /read original/i })).toHaveAttribute('href', 'https://pub.test/a1')
  })

  it('labels stand-in pictures honestly', () => {
    render(<StoryCard article={story('a4', 'Space', { image_url: '/api/images/x.jpg', image_credit: 'Topic photo: Wikimedia Commons · Rover (space exploration)' })} />)
    expect(screen.getByText('Topic photo: Wikimedia Commons · Rover (space exploration)')).toBeInTheDocument()
  })

  it('falls back to a text-only card when the photo fails or is missing', () => {
    const { container, rerender } = render(<StoryCard article={story('a2', 'Space', { image_url: 'https://cdn.test/broken.jpg' })} />)
    fireEvent.error(container.querySelector('img'))
    expect(container.querySelector('img')).toBeNull()
    expect(screen.queryByText(/photo:/i)).toBeNull()
    rerender(<StoryCard article={story('a3', 'Space')} />)
    expect(container.querySelector('img')).toBeNull()
  })

  it('Read Original opens the publisher URL in a new tab', () => {
    render(<StoryCard article={story('a1', 'AI Agents')} />)
    const link = screen.getByRole('link', { name: /read original/i })
    expect(link).toHaveAttribute('href', 'https://news.test/a1')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
  })

  it('shows tag, source, summary and why it matters', () => {
    render(<StoryCard article={story('a6', 'World News', { is_explore: true, label: 'Something new' })} />)
    expect(screen.getByText('Something new')).toBeInTheDocument()
    expect(screen.getByText('World News')).toBeInTheDocument()
    expect(screen.getByText('Source a6', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText('Source a6', { selector: 'cite' })).toBeInTheDocument()
    expect(screen.getByText('Summary a6')).toBeInTheDocument()
    expect(screen.getByText('Why a6')).toBeInTheDocument()
  })

  it('"Why this story?" explains the topic and weight', async () => {
    const user = userEvent.setup()
    render(<StoryCard article={story('a1', 'AI Agents', { is_lead: true })} weight={12} lead />)
    const why = screen.getByRole('button', { name: /why this story/i })
    expect(why).toHaveAttribute('aria-expanded', 'false')
    await user.click(why)
    expect(why).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(/you follow ai agents \(weight 12\)/i)).toBeInTheDocument()
    expect(screen.getByText(/it scored highest today/i)).toBeInTheDocument()
  })

  it('Skip is disabled until Step 6 wires it, and calls onSkip when given', async () => {
    const { rerender } = render(<StoryCard article={story('a1', 'AI Agents')} />)
    expect(screen.getByRole('button', { name: /skip/i })).toBeDisabled()
    const onSkip = vi.fn()
    rerender(<StoryCard article={story('a1', 'AI Agents')} onSkip={onSkip} />)
    await userEvent.setup().click(screen.getByRole('button', { name: /skip/i }))
    expect(onSkip).toHaveBeenCalledWith(expect.objectContaining({ id: 'a1' }))
  })
})

describe('ThreeTakeaways', () => {
  it('clicking a takeaway scrolls to its story', async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    const user = userEvent.setup()
    render(
      <>
        <ThreeTakeaways takeaways={sampleEdition.three_takeaways} />
        <BroadsheetGrid articles={sampleEdition.articles} sections={sampleEdition.sections} />
      </>,
    )
    await user.click(screen.getByRole('link', { name: 'Vulnerability backlogs more than doubled.' }))
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    expect(scrollIntoView.mock.contexts[0]).toBe(document.getElementById('story-a2'))
    expect(document.activeElement).toBe(document.getElementById('story-a2'))
  })
})

describe('Paper', () => {
  const profile = { paper_title: 'THE AYESHA CHRONICLE', topic_weights: { 'AI Agents': 10 } }

  it('lays out masthead, stories, then the caught-up ending with 3 Things last', async () => {
    render(<Paper profile={profile} edition={sampleEdition} />)
    expect(screen.getByRole('heading', { level: 1, name: 'THE AYESHA CHRONICLE' })).toBeInTheDocument()
    expect(screen.getByText(/edition no\. 1/i)).toBeInTheDocument()
    // 3 Things lives inside the ending, not at the top; no Connect the Dots / Vitamin.
    const end = screen.getByRole('region', { name: 'End of paper' })
    expect(within(end).getByRole('region', { name: /3 things you learned today/i })).toBeInTheDocument()
    expect(screen.queryByText('Both stories are about trust in automation.')).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Read slowly' })).toBeNull()
    expect(screen.getByRole('heading', { name: /you're all caught up/i })).toBeInTheDocument()
    // Download PDF fetches the edition's PDF (with the reader's login when signed in).
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, headers: new Headers(), blob: () => Promise.resolve(new Blob(['%PDF'])) })
    vi.stubGlobal('fetch', fetchMock)
    URL.createObjectURL = vi.fn(() => 'blob:pdf')
    URL.revokeObjectURL = vi.fn()
    fireEvent.click(screen.getByRole('button', { name: /download pdf/i }))
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/edition/ed-2026-10-17-1/pdf', expect.any(Object)))
    vi.unstubAllGlobals()
    expect(screen.queryByText(/printed without the ai editor/i)).not.toBeInTheDocument()
  })
})
