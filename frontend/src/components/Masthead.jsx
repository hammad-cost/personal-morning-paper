import { GalleryVertical, Newspaper } from 'lucide-react'

// The reader's own paper name, the edition line and the Feed / Broadsheet switch.
// The paper's tools live in the app's sidebar (AppShell). The feed gets a compact card;
// the broadsheet keeps the double-ruled newspaper masthead.

const formatDate = (date) =>
  date.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

const isoDate = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`

function ViewToggle({ view, onChange }) {
  const option = (value, Icon, label) => (
    <button
      type="button"
      onClick={() => onChange(value)}
      aria-pressed={view === value}
      className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
        view === value ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'
      }`}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </button>
  )
  return (
    <div role="group" aria-label="How to read" className="inline-flex rounded-full border border-rule bg-card p-0.5">
      {option('feed', GalleryVertical, 'Feed')}
      {option('broadsheet', Newspaper, 'Broadsheet')}
    </div>
  )
}

function Masthead({ title, date = new Date(), volume = 1, edition = null, readingMinutes = null, view, onViewChange }) {
  const compact = view === 'feed'
  const meta = (
    <>
      <span>Vol. {volume}</span>
      <span aria-hidden="true"> · </span>
      <span>{edition ? `Edition No. ${edition}` : 'First edition coming soon'}</span>
      <span aria-hidden="true"> · </span>
      <time dateTime={isoDate(date)}>{formatDate(date)}</time>
      {readingMinutes && (
        <>
          <span aria-hidden="true"> · </span>
          <span>Today&apos;s paper: {readingMinutes} min</span>
        </>
      )}
    </>
  )
  const toggle = edition && onViewChange && <ViewToggle view={view} onChange={onViewChange} />

  if (compact) {
    return (
      <header className="mx-auto max-w-[470px] pt-2 text-center">
        <h1 className="font-headline text-3xl font-black leading-tight tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-1 text-xs text-ink-muted">{meta}</p>
        {toggle && <div className="mt-3 flex justify-center">{toggle}</div>}
      </header>
    )
  }
  return (
    <header className="border-y-4 border-double border-ink pt-4 text-center">
      <h1 className="font-headline text-4xl font-black uppercase leading-none tracking-tight sm:text-6xl lg:text-7xl">{title}</h1>
      <p className="mt-3 border-t border-ink py-1.5 font-meta text-xs uppercase tracking-widest text-ink-muted">{meta}</p>
      {toggle && <div className="flex justify-center border-t border-rule py-2">{toggle}</div>}
    </header>
  )
}

export default Masthead
