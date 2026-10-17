import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AuthGate from './AuthGate'
import SignIn from './SignIn'
import { googleEnabled } from './supabase'

vi.mock('./supabase', () => ({ supabase: null, authEnabled: () => false, googleEnabled: vi.fn(() => false), accessToken: async () => null }))

function fakeClient({ session = null, otpError = null } = {}) {
  let listener = () => {}
  return {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session } }),
      onAuthStateChange: vi.fn((cb) => {
        listener = cb
        return { data: { subscription: { unsubscribe: vi.fn() } } }
      }),
      signInWithOtp: vi.fn().mockResolvedValue({ error: otpError }),
      signInWithOAuth: vi.fn().mockResolvedValue({ error: null }),
      signOut: vi.fn().mockResolvedValue({}),
    },
    emit: (next) => listener('SIGNED_IN', next),
  }
}

const session = { access_token: 't', user: { id: 'user-1', email: 'iqra@uni.edu' } }

describe('SignIn', () => {
  it('emails a one-time sign-in link and says to check the inbox', async () => {
    const client = fakeClient()
    const user = userEvent.setup()
    render(<SignIn client={client} />)
    expect(screen.getByText('Vale')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Email'), 'iqra@uni.edu ')
    await user.click(screen.getByRole('button', { name: /email me a sign-in link/i }))
    expect(client.auth.signInWithOtp).toHaveBeenCalledWith({
      email: 'iqra@uni.edu',
      options: { emailRedirectTo: window.location.origin },
    })
    expect(screen.getByRole('status')).toHaveTextContent(/check your inbox/i)
    expect(screen.getByRole('status')).toHaveTextContent('iqra@uni.edu')
  })

  it('shows Supabase errors', async () => {
    const client = fakeClient({ otpError: { message: 'Email rate limit exceeded' } })
    const user = userEvent.setup()
    render(<SignIn client={client} />)
    await user.type(screen.getByLabelText('Email'), 'a@b.co')
    await user.click(screen.getByRole('button', { name: /email me a sign-in link/i }))
    expect(screen.getByRole('alert')).toHaveTextContent('Email rate limit exceeded')
  })

  it('offers Google only when it is switched on', async () => {
    const { unmount } = render(<SignIn client={fakeClient()} />)
    expect(screen.queryByRole('button', { name: /google/i })).toBeNull()
    unmount()
    googleEnabled.mockReturnValue(true)
    const client = fakeClient()
    render(<SignIn client={client} />)
    await userEvent.setup().click(screen.getByRole('button', { name: /continue with google/i }))
    expect(client.auth.signInWithOAuth).toHaveBeenCalledWith({ provider: 'google', options: { redirectTo: window.location.origin } })
  })
})

describe('AuthGate', () => {
  const app = ({ account }) => <p>App for {account ? account.email : 'local reader'}</p>

  it('renders the app straight away in local mode', () => {
    render(<AuthGate enabled={false}>{app}</AuthGate>)
    expect(screen.getByText('App for local reader')).toBeInTheDocument()
  })

  it('asks to sign in when there is no session, then opens the app after sign-in', async () => {
    const client = fakeClient()
    render(<AuthGate enabled client={client}>{app}</AuthGate>)
    expect(await screen.findByRole('heading', { name: /sign in to your paper/i })).toBeInTheDocument()
    act(() => client.emit(session))
    expect(screen.getByText('App for iqra@uni.edu')).toBeInTheDocument()
  })

  it('gives the app a sign-out that ends the Supabase session', async () => {
    const client = fakeClient({ session })
    render(
      <AuthGate enabled client={client}>
        {({ account }) => (
          <button type="button" onClick={account.signOut}>
            Sign out {account.email}
          </button>
        )}
      </AuthGate>,
    )
    fireEvent.click(await screen.findByRole('button', { name: /sign out iqra@uni.edu/i }))
    expect(client.auth.signOut).toHaveBeenCalled()
  })
})
