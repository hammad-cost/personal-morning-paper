import { ArrowUpRight, HelpCircle, Undo2, X } from 'lucide-react'
import { useId, useState } from 'react'
import { storyAnchor } from './ThreeTakeaways'

// One story. No shadows or rounded corners: print-style rules do the separating.
// skipState: undefined (normal) | 'fading' (250 ms fade-out) | 'notice' ("Skipped · Undo").

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

// News photo with a credit. Hotlinked from the publisher (no referrer sent); if it fails
// to load, the card quietly becomes text-only.
function StoryPhoto({ article, lead }) {
  const [failed, setFailed] = useState(false)
  if (!article.image_url || failed) return null
  return (
    <figure className="mb-3">
      <a href={articleLink(article)} target="_blank" rel="noopener noreferrer" tabIndex={-1} aria-hidden="true">
        <img
          src={article.image_url}
          alt=""
          loading={lead ? 'eager' : 'lazy'}
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className={`w-full border border-rule bg-rule object-cover ${lead ? 'aspect-[16/9]' : 'aspect-[3/2]'}`}
        />
      </a>
      <figcaption className="mt-1 font-meta text-[10px] uppercase tracking-wider text-ink-muted">
        {article.image_credit || `Photo: ${article.source_name}`}
      </figcaption>
    </figure>
  )
}

// Straight to the publisher when the backend decoded it, else the feed link.
export const articleLink = (article) => article.publisher_url || article.url

function SkippedNotice({ article, onUndo }) {
  return (
    <div
      role="status"
      className="my-3 flex items-center justify-between gap-3 border border-dashed border-rule px-3 py-2 font-meta text-xs text-ink-muted"
    >
      <span>
        Skipped · <span className="normal-case">{article.topic}</span>
      </span>
      <button
        type="button"
        onClick={() => onUndo(article)}
        className="flex items-center gap-1 uppercase tracking-wider text-ink underline underline-offset-4"
      >
        <Undo2 className="size-3.5" aria-hidden="true" /> Undo
      </button>
    </div>
  )
}

function StoryCard({ article, weight, lead = false, skipState, onSkip, onUndo, onReadOriginal }) {
  const [showWhy, setShowWhy] = useState(false)
  const whyId = useId()
  const Headline = lead ? 'h2' : 'h3'

  if (skipState === 'notice') return <SkippedNotice article={article} onUndo={onUndo} />

  const fading = skipState === 'fading'
  return (
    <article
      id={storyAnchor(article.id)}
      tabIndex={-1}
      aria-label={article.headline}
      aria-hidden={fading || undefined}
      className={`scroll-mt-4 overflow-hidden py-4 outline-none transition-[opacity,max-height] duration-[250ms] ease-out motion-reduce:transition-none ${
        fading ? 'max-h-0 py-0 opacity-0' : 'max-h-[80rem] opacity-100'
      }`}
    >
      <StoryPhoto article={article} lead={lead} />
      <p className="font-meta text-[11px] uppercase tracking-widest text-ink-muted">
        {article.is_explore && <span className="mr-2 bg-accent px-1.5 py-0.5 text-paper">{article.label || 'Something new'}</span>}
        {article.swapped && <span className="mr-2 border border-ink px-1.5 py-0.5 text-ink">Editor&apos;s swap</span>}
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
          href={articleLink(article)}
          target="_blank"
          rel="noopener noreferrer"
          onClick={onReadOriginal ? () => onReadOriginal(article) : undefined}
          className="flex items-center gap-1 underline underline-offset-4 hover:text-accent"
        >
          Read Original <ArrowUpRight className="size-3.5" aria-hidden="true" />
          <span className="sr-only">(opens {article.source_name} in a new tab)</span>
        </a>
        <button
          type="button"
          onClick={onSkip ? () => onSkip(article) : undefined}
          disabled={!onSkip || fading}
          title={onSkip ? 'Skip this story' : 'Skip is not available'}
          className="flex items-center gap-1 text-accent hover:underline disabled:cursor-not-allowed disabled:opacity-40"
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
