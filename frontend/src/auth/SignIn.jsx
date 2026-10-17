import { Mail } from 'lucide-react'
import { useState } from 'react'
import Splash from '../components/Splash'
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
    <Splash title="Sign in to your paper" intro="Your own morning paper: finite, calm, and getting smarter with every story you read or skip.">

      {state === 'sent' ? (
        <div role="status" className="rounded-2xl border border-rule bg-card p-5 text-left shadow-sm">
          <Mail className="size-6 text-accent" aria-hidden="true" />
          <p className="mt-2 font-headline text-xl font-bold">Check your inbox</p>
          <p className="mt-1 text-sm text-ink-muted">
            We sent a sign-in link to <strong className="text-ink">{email.trim()}</strong>. Open it on this device to read your paper.
          </p>
          <button type="button" onClick={() => setState('idle')} className="mt-3 text-sm underline">
            Use a different email
          </button>
        </div>
      ) : (
        <form onSubmit={sendLink} className="flex w-full flex-col gap-3 rounded-2xl border border-rule bg-card p-5 text-left shadow-sm" aria-label="Sign in">
          <label className="flex flex-col gap-1 text-sm font-medium">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@university.edu"
              className="rounded-xl border border-rule bg-paper px-3 py-2.5 font-normal focus:border-accent"
            />
          </label>
          <button type="submit" disabled={state === 'sending'} className="rounded-xl bg-accent px-5 py-3 font-semibold text-white hover:bg-blue-800 disabled:opacity-50">
            {state === 'sending' ? 'Sending…' : 'Email me a sign-in link'}
          </button>
          {googleEnabled() && (
            <button type="button" onClick={google} className="rounded-xl border border-rule px-5 py-3 font-semibold hover:border-accent">
              Continue with Google
            </button>
          )}
          <p className="text-xs text-ink-muted">No password needed. Each student gets their own paper, named after them.</p>
        </form>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}
    </Splash>
  )
}

export default SignIn
