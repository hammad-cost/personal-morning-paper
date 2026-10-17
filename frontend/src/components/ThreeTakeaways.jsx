// "3 Things You Learned Today": each item jumps to the story it came from.

export const storyAnchor = (articleId) => `story-${articleId}`

export function scrollToStory(articleId) {
  const el = document.getElementById(storyAnchor(articleId))
  if (!el) return false
  // Instant jump: the design allows no motion besides skip and drawers.
  el.scrollIntoView({ block: 'start' })
  el.focus({ preventScroll: true })
  return true
}

function ThreeTakeaways({ takeaways }) {
  return (
    <section aria-labelledby="takeaways-title" className="mt-6 border-2 border-ink bg-card px-5 py-4">
      <h2 id="takeaways-title" className="font-meta text-xs uppercase tracking-widest">
        3 Things You Learned Today
      </h2>
      <ol className="mt-3 grid gap-3 md:grid-cols-3 md:gap-0 md:divide-x md:divide-rule">
        {takeaways.map((t, i) => (
          <li key={`${t.article_id}-${i}`} className="flex gap-3 md:px-4 md:first:pl-0 md:last:pr-0">
            <span className="font-headline text-3xl font-black leading-none text-accent" aria-hidden="true">
              {i + 1}
            </span>
            <a
              href={`#${storyAnchor(t.article_id)}`}
              onClick={(e) => {
                if (scrollToStory(t.article_id)) e.preventDefault()
              }}
              className="text-sm leading-snug underline decoration-rule underline-offset-4 hover:decoration-ink"
            >
              {t.text}
            </a>
          </li>
        ))}
      </ol>
    </section>
  )
}

export default ThreeTakeaways
