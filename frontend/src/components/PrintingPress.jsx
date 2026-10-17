import { Check } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { getGenerationStatus, getTodayEdition } from '../api'

// Loading screen while today's edition is made. Shows the backend's real step.

export const PRESS_STEPS = [
  { key: 'gathering', label: 'Gathering articles' },
  { key: 'choosing', label: 'Choosing your stories' },
  { key: 'writing', label: 'Writing your summaries' },
  { key: 'setting', label: 'Setting the type' },
]

function PrintingPress({ onReady, pollMs = 700 }) {
  const [stepIndex, setStepIndex] = useState(-1)
  const [error, setError] = useState(null)
  const [attempt, setAttempt] = useState(0)
  const onReadyRef = useRef(onReady)
  onReadyRef.current = onReady

  useEffect(() => {
    let alive = true
    setError(null)
    setStepIndex(-1)

    const timer = setInterval(async () => {
      try {
        const status = await getGenerationStatus()
        if (alive && status.state === 'running') setStepIndex(status.step_index)
      } catch {
        // polling is best-effort; the edition request decides success or failure
      }
    }, pollMs)

    getTodayEdition()
      .then((edition) => alive && onReadyRef.current(edition))
      .catch((e) => alive && setError(e.message))
      .finally(() => clearInterval(timer))

    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [attempt, pollMs])

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <p className="text-center font-meta text-xs uppercase tracking-widest text-ink-muted">The Printing Press</p>
      <h1 className="mt-2 border-y-4 border-double border-ink py-4 text-center font-headline text-3xl font-black">
        Your paper is on the press
      </h1>
      <ol className="mt-8 flex flex-col gap-3" aria-label="Printing progress">
        {PRESS_STEPS.map((step, i) => {
          const state = i < stepIndex ? 'done' : i === stepIndex ? 'current' : 'pending'
          return (
            <li
              key={step.key}
              aria-current={state === 'current' ? 'step' : undefined}
              className={`flex items-center gap-3 border-b border-rule pb-3 ${
                state === 'pending' ? 'text-ink-muted' : 'text-ink'
              } ${state === 'current' ? 'font-semibold' : ''}`}
            >
              <span className="flex size-5 items-center justify-center font-meta text-xs" aria-hidden="true">
                {state === 'done' ? <Check className="size-4" /> : state === 'current' ? <span className="text-accent">●</span> : i + 1}
              </span>
              <span>{step.label}</span>
              {state === 'done' && <span className="sr-only">(done)</span>}
            </li>
          )
        })}
      </ol>
      {error && (
        <div role="alert" className="mt-8 border border-accent p-4 text-sm">
          <p className="text-accent">The press jammed: {error}</p>
          <button type="button" onClick={() => setAttempt((n) => n + 1)} className="mt-3 bg-ink px-4 py-1.5 text-paper">
            Try again
          </button>
        </div>
      )}
    </main>
  )
}

export default PrintingPress
