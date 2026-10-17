import { useCallback, useEffect, useRef, useState } from 'react'
import { sendSignal } from '../api'
import BrainPanel from './BrainPanel'
import BroadsheetGrid from './BroadsheetGrid'
import CaughtUp from './CaughtUp'
import Masthead from './Masthead'
import SideColumn from './SideColumn'
import ThreeTakeaways from './ThreeTakeaways'

// The broadsheet reading page for one edition, plus the learning signals it sends.

export const FADE_MS = 250
export const UNDO_MS = 5000

function Paper({ profile, edition }) {
  const [articles, setArticles] = useState(edition.articles)
  const [weights, setWeights] = useState(profile.topic_weights)
  const [skipStates, setSkipStates] = useState({}) // id -> 'fading' | 'notice'
  const [brainOpen, setBrainOpen] = useState(false)
  const [brainVersion, setBrainVersion] = useState(0)
  const [error, setError] = useState(null)
  const timers = useRef({})

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
  const patchArticle = (id, changes) => setArticles((prev) => prev.map((a) => (a.id === id ? { ...a, ...changes } : a)))

  const signal = (action, article) =>
    sendSignal({ action, edition_id: edition.id, article_id: article.id }).then((res) => {
      setWeights(res.topic_weights)
      setBrainVersion((v) => v + 1)
      return res
    })

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

  const closeBrain = useCallback(() => setBrainOpen(false), [])

  // Skipped stories stay hidden, except while they fade or offer Undo.
  const visible = articles.filter((a) => !a.skipped || skipStates[a.id])

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:py-8">
      <Masthead
        title={profile.paper_title}
        date={new Date(`${edition.date}T12:00:00`)}
        edition={edition.edition_number}
        readingMinutes={edition.reading_minutes}
        tools={{ onBrain: () => setBrainOpen(true) }}
      />
      {edition.writer === 'fallback' && (
        <p className="mt-2 text-center font-meta text-xs text-ink-muted">
          Printed without the AI editor today: summaries are the publishers&apos; own text.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-2 text-center text-sm text-accent">
          {error}
        </p>
      )}

      <ThreeTakeaways takeaways={edition.three_takeaways} />

      <main className="mt-6">
        <BroadsheetGrid
          articles={visible}
          sections={edition.sections}
          weights={weights}
          side={<SideColumn edition={edition} />}
          cardProps={(a) => ({ skipState: skipStates[a.id], onSkip: skip, onUndo: undo, onReadOriginal: readOriginal })}
        />
        <CaughtUp storyCount={articles.filter((a) => !a.skipped).length} />
      </main>

      <BrainPanel open={brainOpen} onClose={closeBrain} refreshKey={brainVersion} />
    </div>
  )
}

export default Paper
