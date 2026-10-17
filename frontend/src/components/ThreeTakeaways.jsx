import { Check, RotateCcw } from 'lucide-react'

// "3 Things You Learned Today", shown at the very end, after the Brain checks.
// It follows the reader: stories they skipped drop out, questions they got right move
// to the top ("Remembered"), and missed ones point back to the story ("Worth another look").

export const storyAnchor = (articleId) => `story-${articleId}`

export function scrollToStory(articleId) {
  const el = document.getElementById(storyAnchor(articleId))
  if (!el) return false
  // Instant jump: the design allows no motion besides skip and drawers.
  el.scrollIntoView({ block: 'start' })
  el.focus({ preventScroll: true })
  return true
}

// results: { [article_id]: true | false } from the Brain check answers.
export function pickThreeThings(takeaways = [], articles = [], results = {}) {
  const byId = Object.fromEntries(articles.map((a) => [a.id, a]))
  const live = (id) => !articles.length || (byId[id] && !byId[id].skipped)
  const items = takeaways.filter((t) => live(t.article_id)).map((t) => ({ text: t.text, article_id: t.article_id }))
  // A story you answered right is something you learned, even if the editor didn't pick it.
  for (const [id, right] of Object.entries(results)) {
    if (right && live(id) && byId[id] && !items.some((i) => i.article_id === id)) {
      items.push({ text: byId[id].headline, article_id: id })
    }
  }
  const rank = (i) => (results[i.article_id] === true ? 0 : results[i.article_id] === false ? 2 : 1)
  return items
    .map((item, order) => ({ ...item, order, status: results[item.article_id] === true ? 'right' : results[item.article_id] === false ? 'wrong' : null }))
    .sort((a, b) => rank(a) - rank(b) || a.order - b.order)
    .slice(0, 3)
}

function ThreeTakeaways({ takeaways, articles = [], results = {} }) {
  const things = pickThreeThings(takeaways, articles, results)
  if (!things.length) return null
  const answered = Object.keys(results).length
  const right = Object.values(results).filter(Boolean).length

  return (
    <section aria-labelledby="takeaways-title" className="mx-auto mt-8 max-w-3xl rounded-2xl border border-rule bg-card p-5 text-left shadow-sm">
      <h2 id="takeaways-title" className="text-center font-headline text-2xl font-black">
        3 Things You Learned Today
      </h2>
      <p className="mt-1 text-center text-sm text-ink-muted">
        {answered
          ? `You got ${right} of ${answered} brain-check question${answered === 1 ? '' : 's'} right. Here's what stuck.`
          : 'Answer the brain checks to lock these in.'}
      </p>
      <ol className="mt-4 space-y-3">
        {things.map((t, i) => (
          <li key={t.article_id} className="flex gap-4 rounded-xl bg-paper p-4">
            <span className="font-headline text-3xl font-black leading-none text-accent" aria-hidden="true">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <a
                href={`#${storyAnchor(t.article_id)}`}
                onClick={(e) => {
                  if (scrollToStory(t.article_id)) e.preventDefault()
                }}
                className="leading-snug underline decoration-rule underline-offset-4 hover:decoration-accent"
              >
                {t.text}
              </a>
              {t.status === 'right' && (
                <p className="mt-1 flex items-center gap-1 text-xs font-semibold text-accent">
                  <Check className="size-3.5" aria-hidden="true" /> Remembered
                </p>
              )}
              {t.status === 'wrong' && (
                <p className="mt-1 flex items-center gap-1 text-xs font-semibold text-ink-muted">
                  <RotateCcw className="size-3.5" aria-hidden="true" /> Worth another look
                </p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

export default ThreeTakeaways
