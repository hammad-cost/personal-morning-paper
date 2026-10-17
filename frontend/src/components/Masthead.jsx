// Placeholder masthead for Step 1. Edition number, reading time and the
// buttons arrive with the real edition in Steps 4 and 5.

const formatDate = (date) =>
  date.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

function Masthead({ title, date = new Date(), volume = 1, edition = null, readingMinutes = null }) {
  return (
    <header className="border-y-4 border-double border-ink py-4 text-center">
      <h1 className="font-headline text-4xl font-black uppercase tracking-tight sm:text-6xl">
        {title}
      </h1>
      <p className="mt-2 font-meta text-xs uppercase tracking-widest text-ink-muted">
        <span>Vol. {volume}</span>
        <span aria-hidden="true"> · </span>
        <span>{edition ? `Edition No. ${edition}` : 'First edition coming soon'}</span>
        <span aria-hidden="true"> · </span>
        <time dateTime={date.toISOString().slice(0, 10)}>{formatDate(date)}</time>
        {readingMinutes && (
          <>
            <span aria-hidden="true"> · </span>
            <span>Today&apos;s paper: {readingMinutes} min</span>
          </>
        )}
      </p>
    </header>
  )
}

export default Masthead
