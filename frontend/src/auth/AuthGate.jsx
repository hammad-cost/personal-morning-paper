import { useEffect, useState } from 'react'
import SignIn from './SignIn'
import { authEnabled, supabase } from './supabase'

// Shows the sign-in screen until there is a session, then the app for that reader.
// In local mode (no Supabase settings) it renders the app straight away.

function AuthGate({ children, client = supabase, enabled = authEnabled() }) {
  const [session, setSession] = useState(undefined) // undefined = still checking

  useEffect(() => {
    if (!enabled) return undefined
    client.auth.getSession().then(({ data }) => setSession(data.session ?? null))
    const { data } = client.auth.onAuthStateChange((_event, next) => setSession(next ?? null))
    return () => data.subscription.unsubscribe()
  }, [client, enabled])

  if (!enabled) return children({ account: null })
  if (session === undefined) {
    return <main className="flex min-h-screen items-center justify-center font-meta text-sm text-ink-muted">Opening your paper…</main>
  }
  if (!session) return <SignIn client={client} />
  const account = {
    id: session.user.id,
    email: session.user.email,
    signOut: () => client.auth.signOut(),
  }
  return children({ account })
}

export default AuthGate
