import { scrollToStory, storyAnchor } from './ThreeTakeaways'

// Side column beside the lead: Connect the Dots editor's note and the Morning Mind Vitamin.

function Box({ kicker, title, children }) {
  return (
    <section className="border-t-4 border-double border-ink py-4">
      <p className="font-meta text-[11px] uppercase tracking-widest text-ink-muted">{kicker}</p>
      {title && <h2 className="mt-1 font-headline text-xl font-black">{title}</h2>}
      <div className="mt-2 text-sm">{children}</div>
    </section>
  )
}

function SideColumn({ edition }) {
  const titles = Object.fromEntries(edition.articles.map((a) => [a.id, a.headline]))
  const dots = edition.connect_the_dots
  const vitamin = edition.mind_vitamin

  return (
    <aside aria-label="Side column" className="flex flex-col">
      {dots?.text && (
        <Box kicker="Editor's note" title="Connect the Dots">
          <p>{dots.text}</p>
          <ul className="mt-2 space-y-1">
            {dots.article_ids.filter((id) => titles[id]).map((id) => (
              <li key={id}>
                <a
                  href={`#${storyAnchor(id)}`}
                  onClick={(e) => {
                    if (scrollToStory(id)) e.preventDefault()
                  }}
                  className="font-meta text-xs underline decoration-rule underline-offset-4 hover:decoration-ink"
                >
                  → {titles[id]}
                </a>
              </li>
            ))}
          </ul>
        </Box>
      )}
      {vitamin?.content && (
        <Box kicker="Morning Mind Vitamin" title={vitamin.title}>
          <p className="italic">{vitamin.content}</p>
        </Box>
      )}
    </aside>
  )
}

export default SideColumn
