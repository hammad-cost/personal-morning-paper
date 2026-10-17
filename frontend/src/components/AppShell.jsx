import Logo from './Logo'

// Instagram-style web layout. One nav, two shapes: a left sidebar on computers and a
// bottom tab bar on phones (items marked desktopOnly live on the You page there).
// Items without an onClick render disabled with a note.

function NavItem({ item }) {
  const { icon: Icon, label, onClick, active, note, desktopOnly } = item
  return (
    <li className={desktopOnly ? 'hidden lg:block' : 'flex-1 lg:flex-none'}>
      <button
        type="button"
        onClick={onClick}
        disabled={!onClick}
        aria-current={active ? 'page' : undefined}
        title={onClick ? label : note || label}
        className={`flex w-full flex-col items-center gap-0.5 whitespace-nowrap rounded-xl px-1 py-1.5 text-[10px] transition-colors lg:flex-row lg:gap-4 lg:px-3 lg:py-3 lg:text-[15px] ${
          active ? 'font-bold text-ink' : 'text-ink'
        } hover:bg-paper disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent`}
      >
        <Icon className={`size-6 shrink-0 ${active ? 'text-accent' : ''}`} strokeWidth={active ? 2.5 : 2} aria-hidden="true" />
        <span>{label}</span>
      </button>
    </li>
  )
}

function AppShell({ items, note, topBar, aside, children }) {
  return (
    <div className="min-h-screen lg:flex">
      <div className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-rule bg-card/95 px-4 backdrop-blur lg:hidden">
        <Logo size="sm" />
        {topBar}
      </div>

      <nav
        aria-label="Paper tools"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-rule bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-60 lg:shrink-0 lg:flex-col lg:border-r lg:border-t-0 lg:bg-card lg:px-3 lg:py-7 xl:w-64"
      >
        <div className="hidden px-3 pb-8 lg:block">
          <Logo size="md" />
        </div>
        <ul className="flex items-stretch justify-around px-1 lg:flex-col lg:gap-1 lg:px-0">
          {items.map((item) => (
            <NavItem key={item.key} item={item} />
          ))}
        </ul>
        {note && <p className="mt-2 hidden px-3 text-xs text-ink-muted lg:block">{note}</p>}
      </nav>

      <div className="min-w-0 flex-1 pb-20 lg:pb-0">{children}</div>

      {aside && (
        <aside aria-label="Today at a glance" className="hidden w-80 shrink-0 xl:block">
          <div className="sticky top-0 max-h-screen overflow-y-auto px-6 py-8">{aside}</div>
        </aside>
      )}
    </div>
  )
}

export default AppShell
