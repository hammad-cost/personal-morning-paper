import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { downloadPdf, emailEdition, sendSignal, swapStory, updateSettings } from '../api'
import { BRAND } from '../brand'
import { hasCopilot } from '../copilot/config'
import ArchiveDrawer from './ArchiveDrawer'
import BrainPanel from './BrainPanel'
import BroadsheetGrid, { readingOrder } from './BroadsheetGrid'
import CaughtUp from './CaughtUp'
import FeedView from './FeedView'
import Masthead from './Masthead'
import RecallCheck, { RECALL_ID } from './RecallCheck'
import SideColumn from './SideColumn'
import ThreeTakeaways from './ThreeTakeaways'

// CopilotKit is large; the Editor Desk loads the first time it is opened.
const EditorDesk = lazy(() => import('./EditorDesk'))

// The broadsheet reading page for one edition, plus the learning signals it sends.

export const FADE_MS = 250
export const UNDO_MS = 5000
export const SWAP_REPEAT_MS = 60_000
export const VIEW_KEY = 'vale.view'
export const LIMIT_MESSAGE = "That's today's paper. See you tomorrow."

// Feed on phones, broadsheet on wider screens, unless the reader picked one before.
function initialView() {
  try {
    const saved = window.localStorage.getItem(VIEW_KEY)
    if (saved === 'feed' || saved === 'broadsheet') return saved
  } catch {
    // storage blocked: fall through to the screen-size default
  }
  return typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 767px)').matches ? 'feed' : 'broadsheet'
}

function Paper({ profile, edition, onPrintNext, onOpenEdition, extraEditionsLeft, account = null, emailReady = false }) {
  const [view, setView] = useState(initialView)
  const [paper, setPaper] = useState(edition)
  const [weights, setWeights] = useState(profile.topic_weights)
  const [skipStates, setSkipStates] = useState({}) // id -> 'fading' | 'notice'
  const [brainOpen, setBrainOpen] = useState(false)
  const [brainVersion, setBrainVersion] = useState(0)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [deskOpen, setDeskOpen] = useState(false)
  const [deskLoaded, setDeskLoaded] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [dailyEmail, setDailyEmail] = useState(profile.daily_email !== false)
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

  const changeView = (next) => {
    setView(next)
    try {
      window.localStorage.setItem(VIEW_KEY, next)
    } catch {
      // not saved; the choice still applies now
    }
  }

  // Feed ♡: tap again to take it back.
  const like = (article) => {
    const liked = !article.liked
    patchArticle(article.id, { liked })
    signal(liked ? 'LIKE' : 'UNLIKE', article).catch(() => patchArticle(article.id, { liked: !liked }))
  }

  const [emailing, setEmailing] = useState(false)
  const emailPaper = async () => {
    setError(null)
    setNotice(null)
    setEmailing(true)
    try {
      const { sent_to: to } = await emailEdition(paper.id)
      setNotice(`Sent to ${to}. Check your inbox for the PDF.`)
    } catch (e) {
      setError(e.message)
    } finally {
      setEmailing(false)
    }
  }

  const toggleDailyEmail = async (on) => {
    setDailyEmail(on)
    try {
      await updateSettings({ daily_email: on })
    } catch (e) {
      setDailyEmail(!on)
      setError(e.message)
    }
  }

  const readOriginal = (article) => {
    if (article.clicked) return
    patchArticle(article.id, { clicked: true })
    signal('CLICK', article).catch(() => patchArticle(article.id, { clicked: false }))
  }

  const answerQuiz = (question, correct) => {
    sendSignal({ action: correct ? 'QUIZ_RIGHT' : 'QUIZ_WRONG', edition_id: paper.id, article_id: question.article_id })
      .then(learned)
      .catch(() => {})
  }

  // Jump to the recall check (also used by the Editor Desk's quizMe tool).
  const openQuiz = () => {
    const el = document.getElementById(RECALL_ID)
    if (!el) return 'There is no recall check for this edition.'
    el.scrollIntoView({ block: 'start' })
    el.focus({ preventScroll: true })
    return 'Opened the recall check at the end of the paper.'
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

  // The desk's tool must answer before the paper is replaced by the press.
  const printLimitReached = extraEditionsLeft === 0
  const printNextFromDesk = () => {
    if (printLimitReached) return LIMIT_MESSAGE
    setTimeout(onPrintNext, 1500)
    return 'Printing the next edition now with the updated weights. The Printing Press will open in a moment.'
  }

  const closeBrain = useCallback(() => setBrainOpen(false), [])
  const closeArchive = useCallback(() => setArchiveOpen(false), [])
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
        tools={{
          onDownload: () => downloadPdf(paper.id).catch((e) => setError(e.message)),
          onSignOut: account?.signOut,
          onEmail: account && emailReady && !emailing ? emailPaper : undefined,
          onBrain: () => setBrainOpen(true),
          onArchive: onOpenEdition ? () => setArchiveOpen(true) : undefined,
          onEditorDesk: hasCopilot() ? openDesk : undefined,
          onPrintNext: printLimitReached ? undefined : onPrintNext,
        }}
        printNote={printLimitReached ? LIMIT_MESSAGE : null}
        view={view}
        onViewChange={changeView}
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
      {notice && (
        <p role="status" className="mt-2 text-center text-sm">
          {notice}
        </p>
      )}

      {view === 'feed' ? (
        <main className="mt-4">
          <FeedView
            stories={readingOrder(visible, paper.sections)}
            sections={paper.sections}
            takeaways={paper.three_takeaways}
            quiz={paper.recall_quiz}
            articles={articles}
            weights={weights}
            cardProps={(a) => ({ skipState: skipStates[a.id], onSkip: skip, onUndo: undo, onReadOriginal: readOriginal, onLike: like })}
            onAnswer={answerQuiz}
          />
        </main>
      ) : (
        <>
          <ThreeTakeaways takeaways={paper.three_takeaways} />
          <main className="mt-6">
            <BroadsheetGrid
              articles={visible}
              sections={paper.sections}
              weights={weights}
              side={<SideColumn edition={paper} />}
              cardProps={(a) => ({ skipState: skipStates[a.id], onSkip: skip, onUndo: undo, onReadOriginal: readOriginal })}
            />
            <CaughtUp storyCount={articles.filter((a) => !a.skipped).length}>
              <RecallCheck quiz={paper.recall_quiz} articles={articles} onAnswer={answerQuiz} />
            </CaughtUp>
          </main>
        </>
      )}

      <footer className="mt-6 text-center font-meta text-[11px] uppercase tracking-widest text-ink-muted">
        {account?.email && <span className="block normal-case tracking-normal">Signed in as {account.email}</span>}
        {account && emailReady && (
          <label className="my-2 flex items-center justify-center gap-2 normal-case tracking-normal text-ink">
            <input type="checkbox" checked={dailyEmail} onChange={(e) => toggleDailyEmail(e.target.checked)} className="accent-[var(--accent)]" />
            Email me my paper every morning
          </label>
        )}
        {profile.name ? `Printed for ${profile.name} by ` : 'Printed by '}
        <span className="font-headline text-sm font-black normal-case tracking-normal text-ink">{BRAND}</span>
      </footer>

      <BrainPanel open={brainOpen} onClose={closeBrain} refreshKey={brainVersion} />
      {onOpenEdition && (
        <ArchiveDrawer
          open={archiveOpen}
          onClose={closeArchive}
          currentId={paper.id}
          onOpen={onOpenEdition}
          onPrintNext={onPrintNext}
        />
      )}
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
            onPrintNext={onPrintNext ? printNextFromDesk : undefined}
            onQuiz={openQuiz}
          />
        </Suspense>
      )}
    </div>
  )
}

export default Paper
