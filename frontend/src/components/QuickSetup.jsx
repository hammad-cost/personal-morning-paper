import { useReducer, useState } from 'react'
import { onboard } from '../api'
import { initialProfile, isReady, profileReducer, toOnboardPayload } from '../profile/profileReducer'
import ReaderProfileCard from './ReaderProfileCard'

// 30-second manual onboarding. Also the fallback when CopilotKit is unavailable.

const SUGGESTED = ['AI Agents', 'Cybersecurity', 'Climate Tech', 'Startups', 'Space', 'Health', 'World News', 'Football']

function QuickSetup({ onDone, onBack }) {
  const [profile, dispatch] = useReducer(profileReducer, initialProfile)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!isReady(profile)) return
    setSubmitting(true)
    setError(null)
    try {
      onDone(await onboard(toOnboardPayload(profile)))
    } catch {
      setError('Could not save your profile. Is the backend running?')
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-4 py-10 lg:grid-cols-2">
      <form onSubmit={submit} className="flex flex-col gap-5" aria-label="Quick setup">
        <div>
          <p className="font-meta text-xs uppercase tracking-widest text-ink-muted">Quick setup</p>
          <h1 className="mt-1 font-headline text-3xl font-black">Set up your paper</h1>
        </div>

        <label className="flex flex-col gap-1 text-sm">
          Your name
          <input
            required
            value={profile.name}
            onChange={(e) => dispatch({ type: 'SET_NAME', name: e.target.value })}
            className="border border-rule bg-card px-3 py-2"
          />
        </label>

        <fieldset>
          <legend className="text-sm">Pick topics you care about</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {SUGGESTED.map((topic) => {
              const selected = topic in profile.topics
              return (
                <button
                  key={topic}
                  type="button"
                  aria-pressed={selected}
                  onClick={() =>
                    dispatch(selected ? { type: 'REMOVE_TOPIC', topic } : { type: 'ADD_TOPICS', topics: [topic] })
                  }
                  className={`border px-3 py-1 text-sm ${selected ? 'border-ink bg-ink text-paper' : 'border-rule hover:border-ink'}`}
                >
                  {topic}
                </button>
              )
            })}
          </div>
        </fieldset>

        <label className="flex flex-col gap-1 text-sm">
          One line about you (optional)
          <input
            value={profile.bio}
            onChange={(e) => dispatch({ type: 'SET_BIO', bio: e.target.value })}
            placeholder="CS student into AI agents and cybersecurity"
            className="border border-rule bg-card px-3 py-2"
          />
        </label>

        {error && (
          <p role="alert" className="text-sm text-accent">
            {error}
          </p>
        )}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={!isReady(profile) || submitting}
            className="bg-ink px-5 py-2 font-medium text-paper disabled:opacity-40"
          >
            {submitting ? 'Printing…' : 'Print my first edition'}
          </button>
          {onBack && (
            <button type="button" onClick={onBack} className="px-3 py-2 text-sm text-ink-muted underline">
              Back
            </button>
          )}
        </div>
      </form>

      <ReaderProfileCard profile={profile} dispatch={dispatch} />
    </main>
  )
}

export default QuickSetup
