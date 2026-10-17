import { Archive, Download, LogOut, Mail, Printer } from 'lucide-react'

// The reader's own page: who they are, how today went, what Vale has learned, and the
// actions that don't fit in the phone's bottom bar.

function Stat({ value, label }) {
  return (
    <div className="text-center">
      <p className="font-headline text-2xl font-black">{value}</p>
      <p className="text-xs text-ink-muted">{label}</p>
    </div>
  )
}

function Action({ icon: Icon, label, onClick, note }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      title={onClick ? label : note}
      className="flex w-full items-center gap-3 rounded-xl border border-rule bg-card px-4 py-3 text-left font-medium hover:border-accent disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-rule"
    >
      <Icon className="size-5 text-accent" aria-hidden="true" />
      <span className="flex-1">{label}</span>
      {!onClick && note && <span className="text-xs font-normal text-ink-muted">{note}</span>}
    </button>
  )
}

function YouPage({ profile, account, paper, weights, dailyEmail, onDailyEmail, actions = {}, printNote }) {
  const name = profile.name || 'Reader'
  const articles = paper.articles
  const interests = Object.entries(weights ?? {})
    .filter(([, w]) => w > 0)
    .sort((a, b) => b[1] - a[1])
  const top = interests[0]?.[1] || 1

  return (
    <main aria-labelledby="you-title" className="mx-auto max-w-xl px-4 py-8">
      <section className="flex items-center gap-5">
        <span className="flex size-20 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-ink p-[3px]">
          <span className="flex size-full items-center justify-center rounded-full bg-card font-headline text-3xl font-black">{name[0]}</span>
        </span>
        <div className="min-w-0">
          <h1 id="you-title" className="font-headline text-2xl font-black">
            {name}
          </h1>
          <p className="truncate text-sm text-ink-muted">{profile.paper_title}</p>
          {account?.email && <p className="truncate text-sm text-ink-muted">{account.email}</p>}
        </div>
      </section>

      <section aria-label="Today in numbers" className="mt-6 grid grid-cols-4 gap-2 rounded-2xl border border-rule bg-card py-4">
        <Stat value={articles.length} label="stories" />
        <Stat value={articles.filter((a) => a.liked).length} label="liked" />
        <Stat value={articles.filter((a) => a.skipped).length} label="skipped" />
        <Stat value={interests.length} label="interests" />
      </section>

      {interests.length > 0 && (
        <section aria-labelledby="interests-title" className="mt-6 rounded-2xl border border-rule bg-card p-5">
          <h2 id="interests-title" className="text-xs font-semibold uppercase tracking-widest text-ink-muted">
            What Vale has learned you like
          </h2>
          <ul className="mt-3 space-y-2">
            {interests.slice(0, 6).map(([topic, w]) => (
              <li key={topic} className="text-sm">
                <div className="flex justify-between">
                  <span>{topic}</span>
                  <span className="text-ink-muted">{w}</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-paper" aria-hidden="true">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(8, (w / top) * 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {onDailyEmail && (
        <label className="mt-6 flex items-center justify-between gap-3 rounded-2xl border border-rule bg-card p-5">
          <span>
            <span className="block font-medium">Morning email</span>
            <span className="block text-sm text-ink-muted">Your paper and its PDF, every day at 7:00.</span>
          </span>
          <input type="checkbox" checked={dailyEmail} onChange={(e) => onDailyEmail(e.target.checked)} className="size-5 accent-[var(--accent)]" />
        </label>
      )}

      <section aria-label="Your paper" className="mt-6 space-y-2">
        <Action icon={Download} label="Save today's PDF" onClick={actions.onDownload} />
        {actions.onEmail && <Action icon={Mail} label="Send this paper to my email" onClick={actions.onEmail} />}
        <Action icon={Printer} label="Print the next edition" onClick={actions.onPrintNext} note={printNote} />
        {actions.onArchive && <Action icon={Archive} label="Open past editions" onClick={actions.onArchive} />}
        {actions.onSignOut && <Action icon={LogOut} label="Sign out of Vale" onClick={actions.onSignOut} />}
      </section>
    </main>
  )
}

export default YouPage
