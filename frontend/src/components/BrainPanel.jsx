import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getBrain } from '../api'

// Drawer showing what the paper has learned: topic weights as bars and the last 10 signals.

const formatTime = (ts) =>
  new Date(ts).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })

function WeightBar({ topic, weight, min, max }) {
  // Zero sits where 0 falls on the [min, max] scale; bars grow right (positive) or left (negative).
  const zero = (-min / (max - min)) * 100
  const size = (Math.abs(weight) / (max - min)) * 100
  const negative = weight < 0
  return (
    <li className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-3 py-1.5">
      <span className="truncate text-sm" title={topic}>
        {topic}
      </span>
      <span className="relative h-3 bg-paper" aria-hidden="true">
        <span className="absolute inset-y-0 w-px bg-ink-muted" style={{ left: `${zero}%` }} />
        <span
          className={`absolute inset-y-0.5 ${negative ? 'bg-accent' : 'bg-ink'}`}
          style={negative ? { right: `${100 - zero}%`, width: `${size}%` } : { left: `${zero}%`, width: `${size}%` }}
        />
      </span>
      <span className={`text-right font-meta text-xs ${negative ? 'text-accent' : ''}`}>
        {weight > 0 ? `+${weight}` : weight}
      </span>
    </li>
  )
}

function BrainPanel({ open, onClose, refreshKey }) {
  const [brain, setBrain] = useState(null)
  const [error, setError] = useState(null)
  const closeRef = useRef(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    getBrain().then(setBrain).catch((e) => setError(e.message))
  }, [open, refreshKey])

  useEffect(() => {
    if (!open) return
    closeRef.current?.focus()
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-ink/20 transition-opacity duration-200 motion-reduce:transition-none ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="brain-title"
        aria-hidden={!open}
        inert={!open || undefined}
        className={`fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l-2 border-ink bg-card transition-transform duration-200 motion-reduce:transition-none ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <header className="flex items-start justify-between border-b-4 border-double border-ink px-5 py-4">
          <div>
            <p className="font-meta text-[11px] uppercase tracking-widest text-ink-muted">What your paper has learned</p>
            <h2 id="brain-title" className="font-headline text-3xl font-black">
              The Brain
            </h2>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Close the Brain" className="p-1 hover:bg-rule">
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error && (
            <p role="alert" className="text-sm text-accent">
              {error}
            </p>
          )}
          {!brain && !error && <p className="font-meta text-sm text-ink-muted">Reading your habits…</p>}
          {brain && (
            <>
              <h3 className="font-meta text-xs uppercase tracking-widest">Topic weights</h3>
              <p className="mt-1 text-xs text-ink-muted">
                Higher weights win more space and lead stories. Range {brain.min_weight} to +{brain.max_weight}.
              </p>
              <ul aria-label="Topic weights" className="mt-2">
                {Object.entries(brain.topic_weights).map(([topic, weight]) => (
                  <WeightBar key={topic} topic={topic} weight={weight} min={brain.min_weight} max={brain.max_weight} />
                ))}
              </ul>

              <h3 className="mt-6 font-meta text-xs uppercase tracking-widest">Last 10 signals</h3>
              {brain.signals.length ? (
                <ol aria-label="Recent signals" className="mt-2 divide-y divide-rule">
                  {brain.signals.map((s, i) => (
                    <li key={`${s.ts}-${i}`} className="flex justify-between gap-3 py-2 text-sm">
                      <span>{s.text}</span>
                      <time dateTime={s.ts} className="shrink-0 font-meta text-xs text-ink-muted">
                        {formatTime(s.ts)}
                      </time>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="mt-2 text-sm text-ink-muted">Nothing yet. Read or skip a story and watch this change.</p>
              )}
            </>
          )}
        </div>
      </aside>
    </>
  )
}

export default BrainPanel
