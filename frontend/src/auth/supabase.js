import { createClient } from '@supabase/supabase-js'

// Supabase Auth in the browser. Without these two variables Vale runs in local mode:
// one reader, no sign-in (the original single-reader app).
const url = import.meta.env.VITE_SUPABASE_URL ?? ''
// The publishable (anon) key is meant for browsers; table access is locked by RLS.
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? ''

export const authEnabled = () => Boolean(url && publishableKey)
export const googleEnabled = () => import.meta.env.VITE_AUTH_GOOGLE === 'true'

export const supabase = authEnabled() ? createClient(url, publishableKey) : null

// The current access token for API calls, or null (local mode or signed out).
export async function accessToken() {
  if (!supabase) return null
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}
