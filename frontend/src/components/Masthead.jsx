import { Archive, Brain, Download, GalleryVertical, LogOut, Mail, MessagesSquare, Newspaper, Printer } from 'lucide-react'

// Broadsheet masthead: double rules, centered title, meta row, and the paper's tools.
// Tools without an onClick are not built yet and render disabled.

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
      className={`flex items-center gap-1.5 px-2.5 py-1 font-meta text-xs uppercase tracking-wider ${
        view === value ? 'bg-ink text-paper' : 'hover:bg-rule'
      }`}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </button>
  )
  return (
    <div role="group" aria-label="How to read" className="inline-flex border border-ink">
      {option('feed', GalleryVertical, 'Feed')}
      {option('broadsheet', Newspaper, 'Broadsheet')}
    </div>
  )
}

function ToolButton({ icon: Icon, label, onClick, comingIn, note }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      title={onClick ? label : note || `${label} arrives in ${comingIn}`}
      className="flex items-center gap-1.5 px-2 py-1 font-meta text-xs uppercase tracking-wider hover:bg-ink hover:text-paper disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-ink"
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </button>
  )
}

function Masthead({ title, date = new Date(), volume = 1, edition = null, readingMinutes = null, tools = {}, printNote = null, view, onViewChange }) {
  return (
    <header className="border-y-4 border-double border-ink pt-4 text-center">
      <h1 className="font-headline text-4xl font-black uppercase leading-none tracking-tight sm:text-6xl lg:text-7xl">
        {title}
      </h1>
      <p className="mt-3 border-t border-ink py-1.5 font-meta text-xs uppercase tracking-widest text-ink-muted">
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
      </p>
      {edition && (
        <nav aria-label="Paper tools" className="flex flex-wrap justify-center gap-1 border-t border-rule py-1">
          <ToolButton icon={Download} label="Download PDF" onClick={tools.onDownload} comingIn="Step 9" />
          {tools.onEmail && <ToolButton icon={Mail} label="Email me this paper" onClick={tools.onEmail} />}
          <ToolButton icon={Archive} label="Past Editions" onClick={tools.onArchive} comingIn="Step 8" />
          <ToolButton icon={Brain} label="Brain" onClick={tools.onBrain} comingIn="Step 6" />
          <ToolButton icon={MessagesSquare} label="Editor Desk" onClick={tools.onEditorDesk} comingIn="Step 7" />
          <ToolButton icon={Printer} label="Print next edition" onClick={tools.onPrintNext} comingIn="Step 8" note={printNote} />
          {tools.onSignOut && <ToolButton icon={LogOut} label="Sign out" onClick={tools.onSignOut} />}
        </nav>
      )}
      {printNote && <p className="pb-1 font-meta text-[11px] text-ink-muted">{printNote}</p>}
      {edition && onViewChange && (
        <div className="flex justify-center border-t border-rule py-2">
          <ViewToggle view={view} onChange={onViewChange} />
        </div>
      )}
    </header>
  )
}

export default Masthead
