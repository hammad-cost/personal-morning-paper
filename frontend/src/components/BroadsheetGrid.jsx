import StoryCard from './StoryCard'

// 12-column broadsheet: lead spans 8 with the side column in 4, then sections in the
// order the ranker gave (topic weight). Collapses to one column on phones.

export function groupBySection(articles, sections, { noLead = false } = {}) {
  const lead = noLead ? null : (articles.find((a) => a.is_lead) ?? articles[0])
  const rest = articles.filter((a) => a !== lead)
  const known = sections.filter((s) => rest.some((a) => a.topic === s))
  // Any topic missing from `sections` still gets printed, after the known ones.
  const extra = [...new Set(rest.map((a) => a.topic))].filter((t) => !sections.includes(t))
  return {
    lead,
    sections: [...known, ...extra].map((name) => ({ name, articles: rest.filter((a) => a.topic === name) })),
  }
}

// Stories in the order a reader meets them: lead first, then each section of part 1,
// then each section of part 2. Used to number them.
export function readingOrder(articles, sections) {
  const partOne = articles.filter((a) => (a.part ?? 1) !== 2)
  const { lead, sections: grouped } = groupBySection(partOne.length ? partOne : articles, sections)
  if (!lead) return []
  const partTwo = partOne.length ? groupBySection(articles.filter((a) => a.part === 2), sections, { noLead: true }).sections : []
  return [lead, ...grouped.flatMap((s) => s.articles), ...partTwo.flatMap((s) => s.articles)]
}

// Vertical rule after a card only when another card sits to its right (2 columns md, 3 lg).
export function columnRule(index, count) {
  const isLast = index === count - 1
  const md = index % 2 === 0 && !isLast ? 'md:border-r' : 'md:border-r-0'
  const lg = index % 3 !== 2 && !isLast ? 'lg:border-r' : 'lg:border-r-0'
  return `${md} ${lg}`
}

function BroadsheetGrid({ articles, sections, weights = {}, side, cardProps = () => ({}), noLead = false }) {
  const { lead, sections: grouped } = groupBySection(articles, sections, { noLead })

  return (
    <div>
      {!noLead && (
      <div className="grid border-b-2 border-ink lg:grid-cols-12">
        <div className="lg:col-span-8 lg:border-r lg:border-rule lg:pr-6">
          {lead && <StoryCard article={lead} weight={weights[lead.topic]} lead {...cardProps(lead)} />}
        </div>
        <div className="border-t border-rule lg:col-span-4 lg:border-t-0 lg:pl-6">{side}</div>
      </div>
      )}

      {grouped.map((section) => (
        <section key={section.name} aria-labelledby={`section-${section.name}`} className="mt-6">
          <h2
            id={`section-${section.name}`}
            className="border-b border-ink pb-1 font-meta text-xs font-medium uppercase tracking-[0.2em]"
          >
            {section.name}
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3">
            {section.articles.map((a, i) => (
              <div key={a.id} className={`border-b border-rule md:px-4 ${columnRule(i, section.articles.length)}`}>
                <StoryCard article={a} weight={weights[a.topic]} {...cardProps(a)} />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

export default BroadsheetGrid
