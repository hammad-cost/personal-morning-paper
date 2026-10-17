import { useCallback, useEffect, useRef, useState } from 'react'
import { getState, printNextEdition } from './api'
import Onboarding from './components/Onboarding'
import Paper from './components/Paper'
import PrintingPress from './components/PrintingPress'

function App({ account = null }) {
  const [state, setState] = useState(null)
  const [edition, setEdition] = useState(null)
  const [printingNext, setPrintingNext] = useState(false)
  const [error, setError] = useState(null)
  // One request per "Print next edition", even if the press effect runs twice (React StrictMode).
  const nextRequest = useRef(null)

  useEffect(() => {
    getState().then(setState).catch(setError)
  }, [])

  const loadNext = useCallback(() => {
    if (!nextRequest.current) {
      nextRequest.current = printNextEdition().catch((e) => {
        nextRequest.current = null // let "Try again" make a fresh request
        throw e
      })
    }
    return nextRequest.current
  }, [])

  const startNext = useCallback(() => {
    nextRequest.current = null
    setPrintingNext(true)
  }, [])

  const finishNext = useCallback((next) => {
    nextRequest.current = null
    setPrintingNext(false)
    setEdition(next)
    // Weights changed since the last paper; refresh the profile the new paper reads.
    getState().then(setState).catch(() => {})
  }, [])

  if (error) {
    return (
      <main role="alert" className="flex min-h-screen items-center justify-center px-4 text-center">
        <p>
          Could not reach the newsroom. Is the backend running on port 8000?
        </p>
      </main>
    )
  }

  if (!state) {
    return (
      <main className="flex min-h-screen items-center justify-center font-meta text-sm text-ink-muted">
        Loading…
      </main>
    )
  }

  if (!state.onboarded) return <Onboarding onOnboarded={setState} account={account} />
  if (printingNext) return <PrintingPress load={loadNext} onReady={finishNext} title="Printing your next edition" />
  // Today's edition loads instantly if it exists; otherwise the press makes it once.
  if (!edition) return <PrintingPress onReady={setEdition} />
  return (
    <Paper
      key={edition.id}
      profile={state.profile}
      edition={edition}
      onPrintNext={startNext}
      onOpenEdition={setEdition}
      extraEditionsLeft={state.extra_editions_left}
      account={account}
      emailReady={state.email_ready}
    />
  )
}

export default App
