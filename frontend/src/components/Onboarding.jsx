import { MessagesSquare, ListChecks } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { hasCopilot } from '../copilot/config'
import { BRAND, TAGLINE } from '../brand'
import QuickSetup from './QuickSetup'

// CopilotKit is large; load the Editor chat only when the reader picks it.
const EditorInterview = lazy(() => import('./EditorInterview'))

function Welcome({ onPick }) {
  const copilotReady = hasCopilot()
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center px-4 text-center">
      <p className="font-headline text-3xl font-black tracking-tight">{BRAND}</p>
      <p className="font-meta text-xs uppercase tracking-widest text-ink-muted">{TAGLINE}</p>
      <h1 className="mt-4 border-y-4 border-double border-ink py-6 font-headline text-4xl font-black sm:text-5xl">
        Every great paper starts with its reader.
      </h1>
      <p className="mt-6 text-ink-muted">Tell us who you are and what you care about. We will name your paper after you and print it fresh every morning. It takes about a minute.</p>
      <div className="mt-8 flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
        <button
          type="button"
          onClick={() => onPick('editor')}
          disabled={!copilotReady}
          className="flex items-center justify-center gap-2 bg-ink px-6 py-3 font-medium text-paper disabled:opacity-40"
        >
          <MessagesSquare className="size-4" aria-hidden="true" />
          Talk to the Editor
        </button>
        <button
          type="button"
          onClick={() => onPick('quick')}
          className="flex items-center justify-center gap-2 border border-ink px-6 py-3 font-medium hover:bg-ink hover:text-paper"
        >
          <ListChecks className="size-4" aria-hidden="true" />
          Quick setup
        </button>
      </div>
      {!copilotReady && (
        <p className="mt-4 font-meta text-xs text-ink-muted">
          The Editor chat needs VITE_COPILOTKIT_PUBLIC_API_KEY in frontend/.env.
        </p>
      )}
    </main>
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
    <>
      <Welcome onPick={setMode} />
      {account && (
        <p className="pb-6 text-center font-meta text-xs text-ink-muted">
          Signed in as {account.email} ·{' '}
          <button type="button" onClick={account.signOut} className="underline">
            Sign out
          </button>
        </p>
      )}
    </>
  )
}

export default Onboarding
