import { Mail } from 'lucide-react'
import { useState } from 'react'
import { BRAND, TAGLINE } from '../brand'
import { googleEnabled, supabase } from './supabase'

// Sign in with a one-time email link (and Google, when it is switched on in Supabase).

function SignIn({ client = supabase }) {
  const [email, setEmail] = useState('')
  const [state, setState] = useState('idle') // idle | sending | sent
  const [error, setError] = useState(null)

  const sendLink = async (e) => {
    e.preventDefault()
    setError(null)
    setState('sending')
    const { error: err } = await client.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: window.location.origin },
    })
    if (err) {
      setError(err.message)
      setState('idle')
    } else {
      setState('sent')
    }
  }

  const google = async () => {
    setError(null)
    const { error: err } = await client.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } })
    if (err) setError(err.message)
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-4 text-center">
      <p className="font-headline text-4xl font-black tracking-tight">{BRAND}</p>
      <p className="font-meta text-xs uppercase tracking-widest text-ink-muted">{TAGLINE}</p>
      <h1 className="mt-6 w-full border-y-4 border-double border-ink py-5 font-headline text-3xl font-black">
        Sign in to your paper
      </h1>

      {state === 'sent' ? (
        <div role="status" className="mt-6 border border-ink bg-card p-5 text-left">
          <Mail className="size-6" aria-hidden="true" />
          <p className="mt-2 font-headline text-xl font-bold">Check your inbox</p>
          <p className="mt-1 text-sm text-ink-muted">
            We sent a sign-in link to <strong className="text-ink">{email.trim()}</strong>. Open it on this device to read your paper.
          </p>
          <button type="button" onClick={() => setState('idle')} className="mt-3 text-sm underline">
            Use a different email
          </button>
        </div>
      ) : (
        <form onSubmit={sendLink} className="mt-6 flex w-full flex-col gap-3 text-left" aria-label="Sign in">
          <label className="flex flex-col gap-1 text-sm">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@university.edu"
              className="border border-rule bg-card px-3 py-2"
            />
          </label>
          <button type="submit" disabled={state === 'sending'} className="bg-ink px-5 py-2.5 font-medium text-paper disabled:opacity-50">
            {state === 'sending' ? 'Sending…' : 'Email me a sign-in link'}
          </button>
          {googleEnabled() && (
            <button type="button" onClick={google} className="border border-ink px-5 py-2.5 font-medium hover:bg-ink hover:text-paper">
              Continue with Google
            </button>
          )}
          <p className="text-xs text-ink-muted">No password needed. Each student gets their own paper, named after them.</p>
        </form>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-accent">
          {error}
        </p>
      )}
    </main>
  )
}

export default SignIn
