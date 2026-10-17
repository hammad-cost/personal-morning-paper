import Masthead from './Masthead'

// Plain edition view for Step 4 so the AI's writing can be checked.
// Step 5 replaces the body with the real broadsheet.

function Paper({ profile, edition }) {
  const [lead, ...rest] = edition.articles
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Masthead
        title={profile.paper_title}
        date={new Date(`${edition.date}T12:00:00`)}
        edition={edition.edition_number}
        readingMinutes={edition.reading_minutes}
      />
      {edition.writer === 'fallback' && (
        <p className="mt-2 text-center font-meta text-xs text-ink-muted">
          Printed without the AI editor today: summaries are the publishers&apos; own text.
        </p>
      )}

      <section aria-label="3 Things You Learned Today" className="mt-6 border border-ink p-4">
        <h2 className="font-meta text-xs uppercase tracking-widest">3 Things You Learned Today</h2>
        <ol className="mt-2 list-decimal pl-5">
          {edition.three_takeaways.map((t) => (
            <li key={t.article_id + t.text}>{t.text}</li>
          ))}
        </ol>
      </section>

      <article className="mt-8 border-b border-ink pb-6">
        <p className="font-meta text-xs uppercase text-accent">{lead.topic} · Lead story</p>
        <h2 className="mt-1 font-headline text-3xl font-black">{lead.headline}</h2>
        <p className="mt-2">{lead.summary}</p>
        <p className="mt-1 text-sm text-ink-muted">{lead.why_it_matters}</p>
        <p className="mt-1 font-meta text-xs text-ink-muted">{lead.source_name}</p>
      </article>

      <ul className="mt-4">
        {rest.map((a) => (
          <li key={a.id} className="border-b border-rule py-4">
            <p className="font-meta text-xs uppercase text-ink-muted">
              {a.is_explore ? <span className="text-accent">{a.label} · </span> : null}
              {a.topic} · {a.source_name}
            </p>
            <h3 className="font-headline text-xl font-bold">{a.headline}</h3>
            <p className="mt-1 text-sm">{a.summary}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default Paper
