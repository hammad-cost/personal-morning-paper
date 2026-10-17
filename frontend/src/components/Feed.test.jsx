import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { sendSignal } from '../api'
import { sampleEdition } from '../test/edition'
import Paper, { FADE_MS, VIEW_KEY } from './Paper'

vi.mock('../api', () => ({ sendSignal: vi.fn(), swapStory: vi.fn(), getBrain: vi.fn(), pdfUrl: (id) => `/api/edition/${id}/pdf`, downloadPdf: vi.fn() }))
vi.mock('../copilot/config', () => ({ hasCopilot: () => false, copilotApiKey: '' }))

const profile = { name: 'Iqra', paper_title: 'THE IQRA TIMES', topic_weights: { 'AI Agents': 10, Cybersecurity: 8 } }
const edition = {
  ...sampleEdition,
  articles: sampleEdition.articles.map((a) => ({ ...a, image_url: `/api/images/${a.id}.jpg`, image_credit: `Photo: ${a.source_name}` })),
  recall_quiz: [{ question: 'What breached systems?', options: ['Agents', 'Bees', 'Rain'], answer_index: 0, article_id: 'a1' }],
}

// Capture IntersectionObserver so the test can "scroll" posts into view.
let observed = []
let fireIntersect = () => {}
beforeEach(() => {
  observed = []
  window.localStorage.clear()
  window.IntersectionObserver = class {
    constructor(cb) {
      fireIntersect = (els) => cb(els.map((target) => ({ target, isIntersecting: true })))
    }
    observe(el) {
      observed.push(el)
    }
    unobserve() {}
    disconnect() {}
  }
  Element.prototype.scrollIntoView = vi.fn()
  sendSignal.mockResolvedValue({ applied: true, topic_weights: profile.topic_weights })
})
afterEach(() => vi.resetAllMocks())

const openFeed = async () => {
  render(<Paper profile={profile} edition={edition} />)
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Feed' })))
}
const post = (headline) => screen.getByRole('article', { name: headline })

describe('Feed view', () => {
  it('shows posts like an Instagram feed: account row, photo, actions, caption, in reading order', async () => {
    await openFeed()
    const posts = screen.getAllByRole('article')
    expect(posts.map((p) => p.getAttribute('aria-label'))).toEqual([
      'Rogue AI agents broke into live systems',
      'Vulnerability backlogs grew 131%',
      'Sanctions row deepens',
    ])
    const first = posts[0]
    expect(within(first).getByText('Reuters', { selector: '.font-semibold:not(cite)' })).toBeInTheDocument()
    expect(first.querySelector('img[data-photo]')).toHaveAttribute('src', '/api/images/a1.jpg')
    expect(within(first).getByText('Photo: Reuters')).toBeInTheDocument()
    expect(within(first).getByRole('button', { name: 'More like this' })).toBeInTheDocument()
    expect(within(first).getByRole('link', { name: /read original at reuters/i })).toHaveAttribute('href', 'https://news.test/1')
    // No like counts anywhere.
    expect(screen.queryByText(/\d+ likes?/i)).toBeNull()
  })

  it('has story circles for each section that jump to them', async () => {
    await openFeed()
    const circles = within(screen.getByRole('navigation', { name: 'Sections' })).getAllByRole('button')
    expect(circles.map((c) => c.textContent)).toEqual(['AI Agents', 'Cybersecurity', 'World News'])
    fireEvent.click(circles[1])
    expect(Element.prototype.scrollIntoView.mock.contexts.at(-1)).toBe(document.getElementById('feed-section-cybersecurity'))
  })

  it('counts posts as read and ends with "You\'re all caught up" and the quiz', async () => {
    await openFeed()
    expect(screen.getByText('0 of 3')).toBeInTheDocument()
    act(() => fireIntersect(observed.slice(0, 2)))
    expect(screen.getByText('2 of 3')).toBeInTheDocument()
    // A read section's circle loses its red ring.
    expect(screen.getByRole('button', { name: 'AI Agents (read)' })).toBeInTheDocument()
    const end = screen.getByRole('region', { name: 'End of paper' })
    expect(within(end).getByRole('heading', { name: /you're all caught up/i })).toBeInTheDocument()
    expect(within(end).getByRole('heading', { name: /can you name 3 things/i })).toBeInTheDocument()
  })

  it('double-tap on the photo likes the story (LIKE signal), tapping ♡ again takes it back', async () => {
    vi.useFakeTimers()
    await openFeed()
    const photo = post('Vulnerability backlogs grew 131%').querySelector('img[data-photo]').parentElement
    await act(async () => {
      fireEvent.click(photo)
      fireEvent.click(photo)
    })
    expect(sendSignal).toHaveBeenCalledWith({ action: 'LIKE', edition_id: edition.id, article_id: 'a2' })
    const heart = within(post('Vulnerability backlogs grew 131%')).getByRole('button', { name: /liked/i })
    expect(heart).toHaveAttribute('aria-pressed', 'true')
    await act(async () => fireEvent.click(heart))
    expect(sendSignal).toHaveBeenLastCalledWith({ action: 'UNLIKE', edition_id: edition.id, article_id: 'a2' })
    vi.useRealTimers()
  })

  it('swipe left or ✕ skips with Undo, like the broadsheet', async () => {
    vi.useFakeTimers()
    await openFeed()
    const photo = post('Sanctions row deepens').querySelector('img[data-photo]').parentElement
    await act(async () => {
      fireEvent.pointerDown(photo, { clientX: 300 })
      fireEvent.pointerUp(photo, { clientX: 150 })
    })
    expect(sendSignal).toHaveBeenCalledWith({ action: 'SKIP', edition_id: edition.id, article_id: 'a3' })
    await act(() => vi.advanceTimersByTimeAsync(FADE_MS))
    expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('remembers the chosen view', async () => {
    await openFeed()
    expect(window.localStorage.getItem(VIEW_KEY)).toBe('feed')
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Broadsheet' })))
    expect(window.localStorage.getItem(VIEW_KEY)).toBe('broadsheet')
    expect(screen.queryByRole('navigation', { name: 'Sections' })).toBeNull()
  })
})

describe('Daily limit', () => {
  it('turns Print next edition off with a friendly note when no extras are left', () => {
    render(<Paper profile={profile} edition={edition} onPrintNext={vi.fn()} extraEditionsLeft={0} />)
    expect(screen.getByRole('button', { name: /print next edition/i })).toBeDisabled()
    expect(screen.getByText("That's today's paper. See you tomorrow.")).toBeInTheDocument()
  })

  it('keeps it on while extras remain', () => {
    render(<Paper profile={profile} edition={edition} onPrintNext={vi.fn()} extraEditionsLeft={1} />)
    expect(screen.getByRole('button', { name: /print next edition/i })).toBeEnabled()
  })
})

describe('20-story papers', () => {
  const twoParts = {
    ...edition,
    articles: [
      ...edition.articles.map((a) => ({ ...a, part: 1 })),
      { ...edition.articles[1], id: 'b1', headline: 'Part two story', part: 2, is_lead: false, is_explore: false, image_url: '/api/images/b1.jpg' },
    ],
    recall_quiz: [
      { question: 'Part one question?', options: ['a', 'b', 'c'], answer_index: 0, article_id: 'a1' },
      { question: 'Part two question?', options: ['a', 'b', 'c'], answer_index: 1, article_id: 'b1' },
    ],
  }

  it('feed: part 1, a Brain check, part 2, then the final Brain check', async () => {
    render(<Paper profile={profile} edition={twoParts} />)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Feed' })))
    const order = [...document.querySelectorAll('article[data-article-id], section[aria-label^="Brain check"], [aria-label="End of paper"]')]
      .map((el) => el.getAttribute('data-article-id') || el.getAttribute('aria-label'))
    expect(order).toEqual(['a1', 'a2', 'a3', 'Brain check, part 1', 'b1', 'End of paper'])
    expect(screen.getByRole('heading', { name: /brain check · part 1/i })).toBeInTheDocument()
    expect(screen.getByText('Part one question?')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /more for you · part 2/i })).toBeInTheDocument()
    const end = screen.getByRole('region', { name: 'End of paper' })
    expect(within(end).getByText('Part two question?')).toBeInTheDocument()
    expect(screen.getByText('0 of 4')).toBeInTheDocument()
  })

  it('broadsheet: the same two parts with a Brain check in between', () => {
    render(<Paper profile={profile} edition={twoParts} />)
    expect(screen.getByRole('heading', { name: /brain check · part 1/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /more for you · part 2/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /brain check · part 2/i })).toBeInTheDocument()
  })
})

describe('Citations', () => {
  it('every feed post cites its source, date and original link; opening it counts as a click', async () => {
    const cited = {
      ...edition,
      articles: edition.articles.map((a, i) =>
        i === 0 ? { ...a, published_at: '2026-10-16T09:30:00Z', publisher_url: 'https://www.reuters.com/technology/ai/rogue-agents-break-in/' } : a,
      ),
    }
    render(<Paper profile={profile} edition={cited} />)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Feed' })))
    const first = screen.getAllByRole('article')[0]
    expect(within(first).getByText('Reuters', { selector: 'cite' })).toBeInTheDocument()
    expect(within(first).getByText('Oct 16, 2026')).toBeInTheDocument()
    const link = within(first).getByRole('link', { name: /original source: reuters\.com\/technology/i })
    expect(link).toHaveAttribute('href', 'https://www.reuters.com/technology/ai/rogue-agents-break-in/')
    expect(link).toHaveAttribute('target', '_blank')
    await act(async () => fireEvent.click(link))
    expect(sendSignal).toHaveBeenCalledWith({ action: 'CLICK', edition_id: edition.id, article_id: 'a1' })
    // Every post has one.
    expect(screen.getAllByRole('link', { name: /^original source:/i })).toHaveLength(edition.articles.length)
  })
})

describe('Citation links', () => {
  it('names a Google News redirect instead of printing its code', async () => {
    const { shortLink } = await import('./StoryCard')
    expect(shortLink('https://news.google.com/rss/articles/CBMiowFBVV95cUxNVUFl?oc=5')).toBe('Original article (via Google News)')
    expect(shortLink('https://www.bbc.co.uk/news/articles/c1234')).toBe('bbc.co.uk/news/articles/c1234')
    expect(shortLink('https://example.com/' + 'x'.repeat(80))).toHaveLength(42)
  })
})

describe('Publisher logos', () => {
  it("uses the publisher's logo as the post's profile picture, and the initial if it fails", async () => {
    const withSites = {
      ...edition,
      articles: edition.articles.map((a, i) => (i === 0 ? { ...a, source_domain: 'reuters.com' } : i === 1 ? { ...a, publisher_url: 'https://www.cyberscoop.com/x' } : a)),
    }
    render(<Paper profile={profile} edition={withSites} />)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Feed' })))
    const [first, second] = screen.getAllByRole('article')
    const logo = first.querySelector('header img')
    expect(logo).toHaveAttribute('src', '/api/logos/reuters.com')
    expect(second.querySelector('header img')).toHaveAttribute('src', '/api/logos/cyberscoop.com')
    await act(async () => fireEvent.error(logo))
    expect(first.querySelector('header img')).toBeNull()
    expect(within(first.querySelector('header')).getByText('R')).toBeInTheDocument()
  })

  it('works out the site from links, but never from a Google News redirect', async () => {
    const { sourceDomain } = await import('./FeedView')
    expect(sourceDomain({ source_domain: 'bbc.co.uk' })).toBe('bbc.co.uk')
    expect(sourceDomain({ url: 'https://www.theverge.com/a' })).toBe('theverge.com')
    expect(sourceDomain({ url: 'https://news.google.com/rss/articles/x' })).toBeNull()
  })
})
