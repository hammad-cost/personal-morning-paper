import { ArrowUpRight, HelpCircle, X } from 'lucide-react'
import { useId, useState } from 'react'
import { storyAnchor } from './ThreeTakeaways'

// One story. No shadows or rounded corners: print-style rules do the separating.
// onSkip is wired up in Step 6; without it the Skip button is disabled.

function WhyThisStory({ article, weight }) {
  return (
    <p className="mt-2 border-l-2 border-accent pl-3 font-meta text-xs leading-relaxed text-ink-muted">
      {article.is_explore
        ? `Something new: ${article.topic} is outside your usual topics, picked to widen your view.`
        : `You follow ${article.topic} (weight ${weight ?? 0}).`}{' '}
      {article.is_lead && 'It scored highest today, so it leads. '}
      Score {article.score ?? '—'}.
    </p>
  )
}

function StoryCard({ article, weight, lead = false, onSkip }) {
  const [showWhy, setShowWhy] = useState(false)
  const whyId = useId()
  const Headline = lead ? 'h2' : 'h3'

  return (
    <article id={storyAnchor(article.id)} tabIndex={-1} aria-label={article.headline} className="scroll-mt-4 py-4 outline-none">
      <p className="font-meta text-[11px] uppercase tracking-widest text-ink-muted">
        {article.is_explore && <span className="mr-2 bg-accent px-1.5 py-0.5 text-paper">{article.label || 'Something new'}</span>}
        <span className={lead ? 'text-accent' : ''}>{article.topic}</span>
        <span aria-hidden="true"> · </span>
        <span>{article.source_name}</span>
      </p>
      <Headline
        className={`mt-1 font-headline font-black leading-tight ${lead ? 'text-3xl sm:text-4xl lg:text-5xl' : 'text-xl'}`}
      >
        {article.headline}
      </Headline>
      <p className={`mt-2 ${lead ? 'text-lg' : 'text-sm'}`}>{article.summary}</p>
      {article.why_it_matters && (
        <p className="mt-2 text-sm italic text-ink-muted">
          <span className="font-meta text-[11px] not-italic uppercase tracking-wider text-ink">Why it matters to you · </span>
          {article.why_it_matters}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 font-meta text-xs uppercase tracking-wider">
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 underline underline-offset-4 hover:text-accent"
        >
          Read Original <ArrowUpRight className="size-3.5" aria-hidden="true" />
          <span className="sr-only">(opens {article.source_name} in a new tab)</span>
        </a>
        <button
          type="button"
          onClick={onSkip ? () => onSkip(article) : undefined}
          disabled={!onSkip}
          title={onSkip ? 'Skip this story' : 'Skip arrives in Step 6'}
          className="flex items-center gap-1 text-accent disabled:cursor-not-allowed disabled:opacity-40"
        >
          Skip <X className="size-3.5" aria-hidden="true" />
        </button>
        <button
          type="button"
          aria-expanded={showWhy}
          aria-controls={whyId}
          onClick={() => setShowWhy((v) => !v)}
          className="flex items-center gap-1 text-ink-muted hover:text-ink"
        >
          <HelpCircle className="size-3.5" aria-hidden="true" /> Why this story?
        </button>
      </div>
      <div id={whyId}>{showWhy && <WhyThisStory article={article} weight={weight} />}</div>
    </article>
  )
}

export default StoryCard
