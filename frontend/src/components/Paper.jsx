import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { sendSignal, swapStory } from '../api'
import { hasCopilot } from '../copilot/config'
import BrainPanel from './BrainPanel'
import BroadsheetGrid, { readingOrder } from './BroadsheetGrid'
import CaughtUp from './CaughtUp'
import Masthead from './Masthead'
import SideColumn from './SideColumn'
import ThreeTakeaways from './ThreeTakeaways'

// CopilotKit is large; the Editor Desk loads the first time it is opened.
const EditorDesk = lazy(() => import('./EditorDesk'))

// The broadsheet reading page for one edition, plus the learning signals it sends.

export const FADE_MS = 250
export const UNDO_MS = 5000
export const SWAP_REPEAT_MS = 60_000

function Paper({ profile, edition }) {
  const [paper, setPaper] = useState(edition)
  const [weights, setWeights] = useState(profile.topic_weights)
  const [skipStates, setSkipStates] = useState({}) // id -> 'fading' | 'notice'
  const [brainOpen, setBrainOpen] = useState(false)
  const [brainVersion, setBrainVersion] = useState(0)
  const [deskOpen, setDeskOpen] = useState(false)
  const [deskLoaded, setDeskLoaded] = useState(false)
  const [error, setError] = useState(null)
  const timers = useRef({})
  const paperRef = useRef(paper)
  paperRef.current = paper
  const articles = paper.articles

  useEffect(() => () => Object.values(timers.current).flat().forEach(clearTimeout), [])

  const clearTimers = (id) => {
    ;(timers.current[id] ?? []).forEach(clearTimeout)
    delete timers.current[id]
  }
  const setSkipState = (id, state) =>
    setSkipStates((prev) => {
      const next = { ...prev }
      if (state) next[id] = state
      else delete next[id]
      return next
    })
  const patchArticle = (id, changes) =>
    setPaper((prev) => ({ ...prev, articles: prev.articles.map((a) => (a.id === id ? { ...a, ...changes } : a)) }))

  const learned = (res) => {
    setWeights(res.topic_weights)
    setBrainVersion((v) => v + 1)
    return res
  }
  const signal = (action, article) =>
    sendSignal({ action, edition_id: paper.id, article_id: article.id }).then(learned)

  const skip = (article) => {
    setError(null)
    clearTimers(article.id)
    patchArticle(article.id, { skipped: true })
    setSkipState(article.id, 'fading')
    timers.current[article.id] = [
      setTimeout(() => setSkipState(article.id, 'notice'), FADE_MS),
      setTimeout(() => setSkipState(article.id, null), FADE_MS + UNDO_MS),
    ]
    signal('SKIP', article).catch(() => {
      clearTimers(article.id)
      patchArticle(article.id, { skipped: false })
      setSkipState(article.id, null)
      setError('Could not skip that story. Is the backend running?')
    })
  }

  const undo = (article) => {
    clearTimers(article.id)
    patchArticle(article.id, { skipped: false })
    setSkipState(article.id, null)
    signal('UNSKIP', article).catch(() => setError('Could not undo the skip.'))
  }

  const readOriginal = (article) => {
    if (article.clicked) return
    patchArticle(article.id, { clicked: true })
    signal('CLICK', article).catch(() => patchArticle(article.id, { clicked: false }))
  }

  // ----- Editor Desk handlers -----
  const adjustInterest = async (topic, delta, words) => {
    const res = learned(await sendSignal({ action: 'COPILOT', topic, delta, note: words }))
    return res.signal?.weight ?? res.topic_weights[topic]
  }
  // Guards against the model repeating a swap: one at a time, and no identical re-swap within a minute.
  const swapping = useRef(null)
  const recentSwaps = useRef({}) // article id -> { topic, at }
  const swap = async (story, topic) => {
    const recent = recentSwaps.current[story.id]
    if (recent && recent.topic === topic.trim().toLowerCase() && Date.now() - recent.at < SWAP_REPEAT_MS) {
      return { ...paperRef.current.articles.find((a) => a.id === story.id), alreadySwapped: true }
    }
    if (swapping.current) {
      await swapping.current.catch(() => {})
      return swap(story, topic)
    }
    swapping.current = swapStory(paper.id, story.id, topic)
    try {
      const updated = await swapping.current
      recentSwaps.current[story.id] = { topic: topic.trim().toLowerCase(), at: Date.now() }
      setPaper(updated)
      return updated.articles.find((a) => a.id === story.id)
    } finally {
      swapping.current = null
    }
  }

  const closeBrain = useCallback(() => setBrainOpen(false), [])
  const openDesk = () => {
    setDeskLoaded(true)
    setDeskOpen((v) => !v)
  }

  // Skipped stories stay hidden, except while they fade or offer Undo.
  const visible = articles.filter((a) => !a.skipped || skipStates[a.id])
  const stories = readingOrder(articles.filter((a) => !a.skipped), paper.sections).map((a, i) => ({
    number: i + 1,
    id: a.id,
    topic: a.topic,
    headline: a.headline,
    summary: a.summary,
    why_it_matters: a.why_it_matters,
    source: a.source_name,
    source_name: a.source_name,
    is_lead: a.is_lead,
    is_explore: a.is_explore,
  }))

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:py-8">
      <Masthead
        title={profile.paper_title}
        date={new Date(`${paper.date}T12:00:00`)}
        edition={paper.edition_number}
        readingMinutes={paper.reading_minutes}
        tools={{ onBrain: () => setBrainOpen(true), onEditorDesk: hasCopilot() ? openDesk : undefined }}
      />
      {paper.writer === 'fallback' && (
        <p className="mt-2 text-center font-meta text-xs text-ink-muted">
          Printed without the AI editor today: summaries are the publishers&apos; own text.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-center text-sm text-accent">
          {error}
        </p>
      )}

      <ThreeTakeaways takeaways={paper.three_takeaways} />

      <main className="mt-6">
        <BroadsheetGrid
          articles={visible}
          sections={paper.sections}
          weights={weights}
          side={<SideColumn edition={paper} />}
          cardProps={(a) => ({ skipState: skipStates[a.id], onSkip: skip, onUndo: undo, onReadOriginal: readOriginal })}
        />
        <CaughtUp storyCount={articles.filter((a) => !a.skipped).length} />
      </main>

      <BrainPanel open={brainOpen} onClose={closeBrain} refreshKey={brainVersion} />
      {deskLoaded && (
        <Suspense fallback={null}>
          <EditorDesk
            open={deskOpen}
            onOpenChange={setDeskOpen}
            stories={stories}
            weights={weights}
            edition={paper}
            onAdjust={adjustInterest}
            onSwap={swap}
          />
        </Suspense>
      )}
    </div>
  )
}

export default Paper
