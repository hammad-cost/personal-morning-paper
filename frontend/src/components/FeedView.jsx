import { ArrowUpRight, Heart, HelpCircle, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import RecallCheck from './RecallCheck'
import { articleLink, SkippedNotice, WhyThisStory } from './StoryCard'
import ThreeTakeaways, { storyAnchor } from './ThreeTakeaways'

// Instagram-style home feed for today's paper — but finite: 10 posts, then
// "You're all caught up". No like counts, no autoplay, nothing loads after the end.

const DOUBLE_TAP_MS = 300
const SWIPE_PX = 80

const sectionId = (name) => `feed-section-${name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`

function jumpTo(id) {
  const el = document.getElementById(id)
  if (!el) return
  el.scrollIntoView({ block: 'start' })
  el.focus({ preventScroll: true })
}

// ---------- story circles ----------

function StoryCircles({ circles, seenSections }) {
  return (
    <nav aria-label="Sections" className="flex gap-4 overflow-x-auto px-1 pb-3 pt-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {circles.map((c) => {
        const seen = seenSections.has(c.name)
        return (
          <button
            key={c.name}
            type="button"
            onClick={() => jumpTo(sectionId(c.name))}
            aria-label={`${c.name}${seen ? ' (read)' : ''}`}
            className="flex w-16 shrink-0 flex-col items-center gap-1"
          >
            <span className={`block size-16 rounded-full p-[3px] ${seen ? 'bg-rule' : 'bg-gradient-to-tr from-accent to-sky-400'}`}>
              {c.image ? (
                <img src={c.image} alt="" referrerPolicy="no-referrer" className="size-full rounded-full border-2 border-card object-cover" />
              ) : (
                <span className="flex size-full items-center justify-center rounded-full bg-rule font-headline text-xl font-black">
                  {c.name[0]}
                </span>
              )}
            </span>
            <span className={`w-full truncate text-center text-[11px] ${seen ? 'text-ink-muted' : ''}`}>{c.name}</span>
          </button>
        )
      })}
    </nav>
  )
}

// ---------- one post ----------

function FeedPost({ article, weight, sectionStart, skipState, onSkip, onUndo, onReadOriginal, onLike, observe }) {
  const [showWhy, setShowWhy] = useState(false)
  const [heart, setHeart] = useState(false)
  const lastTap = useRef(0)
  const startX = useRef(null)
  const ref = useRef(null)

  useEffect(() => observe(ref.current, article), [observe, article])

  if (skipState === 'notice') return <SkippedNotice article={article} onUndo={onUndo} />

  const fading = skipState === 'fading'
  const like = () => {
    if (!article.liked) onLike(article)
    setHeart(true)
    setTimeout(() => setHeart(false), 700)
  }
  // Double-tap the photo to like (works with mouse and touch), swipe left to skip.
  const onPhotoClick = () => {
    const now = Date.now()
    if (now - lastTap.current < DOUBLE_TAP_MS) like()
    lastTap.current = now
  }

  return (
    <article
      ref={ref}
      id={storyAnchor(article.id)}
      data-article-id={article.id}
      tabIndex={-1}
      aria-label={article.headline}
      aria-hidden={fading || undefined}
      className={`my-4 scroll-mt-28 overflow-hidden rounded-2xl border border-rule bg-card pb-4 outline-none transition-opacity duration-[250ms] motion-reduce:transition-none ${
        fading ? 'opacity-0' : 'opacity-100'
      }`}
    >
      {sectionStart && (
        <h2 id={sectionId(article.topic)} tabIndex={-1} className="scroll-mt-28 border-b border-rule bg-paper/60 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-accent outline-none">
          {article.topic}
        </h2>
      )}
      <header className="flex items-center gap-2 px-4 py-3">
        <span className="flex size-9 items-center justify-center rounded-full bg-gradient-to-br from-accent to-ink p-[2px]" aria-hidden="true">
          <span className="flex size-full items-center justify-center rounded-full bg-card font-headline text-sm font-black">
          {(article.source_name || '?')[0]}
          </span>
        </span>
        <span className="min-w-0 flex-1 truncate text-sm">
          <span className="font-semibold">{article.source_name}</span>
          <span className="text-xs text-ink-muted"> · {article.topic}</span>
        </span>
        {article.is_explore && <span className="rounded-full bg-accent px-2 py-0.5 text-[10px] font-semibold uppercase text-white">{article.label || 'Something new'}</span>}
        {article.is_lead && !article.is_explore && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold uppercase text-accent">Lead</span>}
      </header>

      <div
        className="relative select-none"
        onClick={onPhotoClick}
        onPointerDown={(e) => (startX.current = e.clientX)}
        onPointerUp={(e) => {
          if (startX.current !== null && e.clientX - startX.current < -SWIPE_PX) onSkip(article)
          startX.current = null
        }}
      >
        {article.image_url && (
          <img
            src={article.image_url}
            alt=""
            referrerPolicy="no-referrer"
            draggable={false}
            className="aspect-[4/5] w-full bg-rule object-cover sm:aspect-square"
          />
        )}
        {heart && (
          <Heart
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-1/2 size-24 -translate-x-1/2 -translate-y-1/2 fill-paper text-paper drop-shadow-lg"
          />
        )}
      </div>
      {article.image_credit && <p className="mt-1 px-4 text-[10px] uppercase tracking-wider text-ink-muted">{article.image_credit}</p>}

      <div className="mt-2 flex items-center gap-4 px-3">
        <button
          type="button"
          onClick={() => (article.liked ? onLike(article) : like())}
          aria-pressed={Boolean(article.liked)}
          aria-label={article.liked ? 'Liked: more like this' : 'More like this'}
          className="p-1"
        >
          <Heart className={`size-6 ${article.liked ? 'fill-accent text-accent' : ''}`} aria-hidden="true" />
        </button>
        <button type="button" onClick={() => onSkip(article)} disabled={fading} aria-label="Skip" className="p-1 disabled:opacity-40">
          <X className="size-6" aria-hidden="true" />
        </button>
        <a
          href={articleLink(article)}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => onReadOriginal(article)}
          aria-label={`Read original at ${article.source_name}`}
          className="p-1"
        >
          <ArrowUpRight className="size-6" aria-hidden="true" />
        </a>
        <button
          type="button"
          aria-expanded={showWhy}
          onClick={() => setShowWhy((v) => !v)}
          className="ml-auto flex items-center gap-1 text-xs text-ink-muted"
        >
          <HelpCircle className="size-4" aria-hidden="true" /> Why?
        </button>
      </div>

      <div className="mt-1 px-4 text-[15px] leading-relaxed">
        <h3 className="font-headline text-xl font-bold leading-snug">{article.headline}</h3>
        <p className="mt-1">{article.summary}</p>
        {article.why_it_matters && <p className="mt-1 italic text-ink-muted">{article.why_it_matters}</p>}
        {showWhy && <WhyThisStory article={article} weight={weight} />}
      </div>
    </article>
  )
}

// ---------- the feed ----------

// Questions belong to the part of the story they ask about.
const quizFor = (quiz, stories, part) => {
  const ids = new Set(stories.filter((a) => (a.part ?? 1) === part).map((a) => a.id))
  return quiz.filter((q) => ids.has(q.article_id))
}

function FeedView({ stories, sections, takeaways, quiz, articles, weights = {}, cardProps, onAnswer, quizResults = {} }) {
  const [seen, setSeen] = useState(() => new Set())
  const live = stories.filter((a) => !a.skipped)
  const observer = useRef(null)

  // A post counts as read once most of it has been on screen. The observer is created on
  // first use: posts (children) register in their effects, which run before this component's.
  const getObserver = () => {
    if (!observer.current && typeof IntersectionObserver !== 'undefined') {
      observer.current = new IntersectionObserver(
        (entries) => {
          const ids = entries.filter((e) => e.isIntersecting).map((e) => e.target.dataset.articleId)
          if (ids.length) setSeen((prev) => new Set([...prev, ...ids]))
        },
        { threshold: 0.6 },
      )
    }
    return observer.current
  }
  useEffect(() => () => observer.current?.disconnect(), [])
  const observe = useRef((el) => {
    const obs = el && getObserver()
    if (obs) obs.observe(el)
    return () => obs && obs.unobserve(el)
  }).current

  const seenCount = live.filter((a) => seen.has(a.id)).length
  const circles = sections
    .map((name) => ({ name, image: stories.find((a) => a.topic === name && a.image_url)?.image_url }))
    .filter((c) => stories.some((a) => a.topic === c.name))
  const seenSections = new Set(circles.filter((c) => live.filter((a) => a.topic === c.name).every((a) => seen.has(a.id))).map((c) => c.name))

  return (
    <div className="mx-auto max-w-[470px]">
      <StoryCircles circles={circles} seenSections={seenSections} />

      <div className="sticky top-14 z-10 bg-paper/95 py-2 backdrop-blur lg:top-0" role="status" aria-live="polite">
        <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-widest text-ink-muted">
          <span>Today&apos;s paper</span>
          <span>
            {seenCount} of {live.length}
          </span>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-rule" aria-hidden="true">
          <div className="h-full rounded-full bg-accent transition-[width] duration-[250ms]" style={{ width: `${live.length ? (seenCount / live.length) * 100 : 0}%` }} />
        </div>
      </div>

      {stories.map((a, i) => {
        const startsPartTwo = (a.part ?? 1) === 2 && (i === 0 || (stories[i - 1].part ?? 1) !== 2)
        return (
          <div key={a.id}>
            {startsPartTwo && (
              <>
                <section aria-label="Brain check, part 1" className="my-4 rounded-2xl border-2 border-accent/30 bg-card px-4 pb-6 text-center">
                  <RecallCheck
                    id="recall-check"
                    quiz={quizFor(quiz, stories, 1)}
                    articles={articles}
                    onAnswer={onAnswer}
                    title="🧠 Brain check · Part 1"
                    subtitle="Three questions on what you just read. Then 10 more stories."
                  />
                </section>
                <h2 className="pt-6 text-center font-headline text-2xl font-black">More for you · Part 2</h2>
              </>
            )}
            <FeedPost
              article={a}
              weight={weights[a.topic]}
              sectionStart={i === 0 || stories[i - 1].topic !== a.topic || startsPartTwo}
              observe={observe}
              {...cardProps(a)}
            />
          </div>
        )
      })}

      <section aria-label="End of paper" className="my-4 rounded-2xl border border-rule bg-card px-4 py-10 text-center">
        <p className="mx-auto flex size-16 items-center justify-center rounded-full border-2 border-accent font-headline text-3xl text-accent">✓</p>
        <h2 className="mt-3 font-headline text-3xl font-black">You&apos;re all caught up.</h2>
        <p className="mt-1 text-sm text-ink-muted">{live.length} stories, finished. Nothing more loads today — that&apos;s the point.</p>
        {stories.some((a) => a.part === 2) ? (
          <RecallCheck
            id="recall-check-2"
            quiz={quizFor(quiz, stories, 2)}
            articles={articles}
            onAnswer={onAnswer}
            title="🧠 Brain check · Part 2"
            subtitle="Last three questions. Then you're done for today."
          />
        ) : (
          <RecallCheck quiz={quiz} articles={articles} onAnswer={onAnswer} />
        )}
        <ThreeTakeaways takeaways={takeaways} articles={articles} results={quizResults} />
      </section>
    </div>
  )
}

export default FeedView
