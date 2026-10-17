import { useEffect, useState } from 'react'
import { getState } from './api'
import Onboarding from './components/Onboarding'
import Paper from './components/Paper'

function App() {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getState().then(setState).catch(setError)
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

  return state.onboarded ? <Paper profile={state.profile} /> : <Onboarding />
}

export default App
