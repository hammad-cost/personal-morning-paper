import { Brain, Heart, Newspaper, QrCode, X } from 'lucide-react'
import { TAGLINE } from '../brand'
import Logo, { ValeMark } from './Logo'

// Shared layout for sign-in and the welcome screen: the brand and the form on the left,
// a picture of what the paper looks like on the right (decoration only).

const FEATURES = [
  { icon: Newspaper, text: '20 stories a day, picked for you. Then it ends.' },
  { icon: Brain, text: 'Two quick brain checks so the news actually sticks.' },
  { icon: QrCode, text: 'A printable PDF with a QR code to every source.' },
]

function PhonePreview() {
  return (
    <div aria-hidden="true" className="relative mx-auto w-72 rotate-2 rounded-[2.5rem] border-8 border-ink bg-paper p-3 shadow-2xl">
      <div className="flex items-center justify-between px-1 pb-2">
        <span className="flex items-center gap-1.5 font-headline text-sm font-black">
          <ValeMark className="size-5" /> Your paper
        </span>
        <span className="text-[10px] text-ink-muted">3 of 20</span>
      </div>
      <div className="mb-2 h-1 rounded-full bg-rule">
        <div className="h-full w-[15%] rounded-full bg-accent" />
      </div>
      <div className="overflow-hidden rounded-2xl border border-rule bg-card">
        <div className="flex items-center gap-2 px-3 py-2 text-[11px]">
          <span className="size-6 rounded-full bg-gradient-to-br from-accent to-ink" />
          <span className="font-semibold">Reuters</span>
          <span className="text-ink-muted">· AI Agents</span>
        </div>
        <div className="flex aspect-square items-end bg-gradient-to-br from-sky-200 via-blue-300 to-accent p-3">
          <span className="rounded-full bg-card/90 px-2 py-0.5 text-[10px] font-semibold text-accent">Lead story</span>
        </div>
        <div className="flex gap-3 px-3 pt-2 text-ink">
          <Heart className="size-4 fill-accent text-accent" />
          <X className="size-4" />
        </div>
        <p className="px-3 pb-3 pt-1 font-headline text-sm font-bold leading-snug">AI agents get a seat at the newsroom table</p>
      </div>
      <div className="mt-2 rounded-2xl border-2 border-accent/30 bg-card p-3 text-center">
        <p className="text-[11px] font-semibold">🧠 Brain check · Part 1</p>
        <div className="mt-2 grid grid-cols-3 gap-1">
          <span className="h-5 rounded-md bg-accent" />
          <span className="h-5 rounded-md bg-rule" />
          <span className="h-5 rounded-md bg-rule" />
        </div>
      </div>
    </div>
  )
}

function Splash({ title, intro, children, footer }) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-card to-paper">
      <main className="mx-auto grid min-h-screen max-w-6xl items-center gap-12 px-4 py-10 md:grid-cols-2 md:px-8">
        <div className="mx-auto w-full max-w-md md:mx-0">
          <Logo size="lg" />
          <p className="mt-2 text-sm text-ink-muted">{TAGLINE}</p>
          <h1 className="mt-8 font-headline text-4xl font-black leading-tight tracking-tight sm:text-5xl">{title}</h1>
          {intro && <p className="mt-4 text-lg leading-relaxed text-ink-muted">{intro}</p>}
          <ul className="mt-6 space-y-3">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 text-[15px]">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                {text}
              </li>
            ))}
          </ul>
          <div className="mt-8">{children}</div>
          {footer}
        </div>
        <div className="hidden md:block">
          <PhonePreview />
        </div>
      </main>
    </div>
  )
}

export default Splash
