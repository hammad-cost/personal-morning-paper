import { MessagesSquare, ListChecks } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { hasCopilot } from '../copilot/config'
import QuickSetup from './QuickSetup'
import Splash from './Splash'

// CopilotKit is large; load the Editor chat only when the reader picks it.
const EditorInterview = lazy(() => import('./EditorInterview'))

function Welcome({ onPick, footer }) {
  const copilotReady = hasCopilot()
  return (
    <Splash
      title="Every great paper starts with its reader."
      intro="Tell us who you are and what you care about. We will name your paper after you and print it fresh every morning. It takes about a minute."
      footer={footer}
    >
      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={() => onPick('editor')}
          disabled={!copilotReady}
          className="flex items-center justify-center gap-2 rounded-xl bg-accent px-6 py-3 font-semibold text-white shadow-sm hover:bg-blue-800 disabled:opacity-40"
        >
          <MessagesSquare className="size-4" aria-hidden="true" />
          Talk to the Editor
        </button>
        <button
          type="button"
          onClick={() => onPick('quick')}
          className="flex items-center justify-center gap-2 rounded-xl border border-rule bg-card px-6 py-3 font-semibold hover:border-accent"
        >
          <ListChecks className="size-4" aria-hidden="true" />
          Quick setup
        </button>
      </div>
      {!copilotReady && (
        <p className="mt-4 text-xs text-ink-muted">
          The Editor chat needs VITE_COPILOTKIT_PUBLIC_API_KEY in frontend/.env.
        </p>
      )}
    </Splash>
  )
}

function Onboarding({ onOnboarded, account = null }) {
  const [mode, setMode] = useState('welcome')
  const back = () => setMode('welcome')

  if (mode === 'quick') return <QuickSetup onDone={onOnboarded} onBack={back} />
  if (mode === 'editor') {
    return (
      <Suspense fallback={<p className="p-10 text-center font-meta text-sm text-ink-muted">Calling the Editor…</p>}>
        <EditorInterview onDone={onOnboarded} onFallback={() => setMode('quick')} />
      </Suspense>
    )
  }
  return (
    <Welcome
      onPick={setMode}
      footer={
        account && (
        <p className="mt-6 text-xs text-ink-muted">
          Signed in as {account.email} ·{' '}
          <button type="button" onClick={account.signOut} className="underline">
            Sign out
          </button>
        </p>
        )
      }
    />
  )
}

export default Onboarding
