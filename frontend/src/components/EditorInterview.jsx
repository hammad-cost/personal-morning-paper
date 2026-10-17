import { CopilotChat, useAgentContext, useFrontendTools } from '@copilotkit/react-core/v2'
import { useMemo, useReducer, useRef, useState } from 'react'
import { onboard } from '../api'
import CopilotProvider from '../copilot/CopilotProvider'
import { INTERVIEW_INSTRUCTIONS, makeInterviewTools } from '../copilot/interviewTools'
import { initialProfile, isReady, profileReducer, toOnboardPayload } from '../profile/profileReducer'
import ReaderProfileCard from './ReaderProfileCard'

// "Talk to the Editor": chat on the left, live profile card on the right.

function Interview({ onDone, onFallback }) {
  const [profile, dispatch] = useReducer(profileReducer, initialProfile)
  const [chatError, setChatError] = useState(null)
  const [saving, setSaving] = useState(false)

  // Tool handlers read the latest draft through a ref so they never see stale state.
  const profileRef = useRef(profile)
  profileRef.current = profile

  const finish = async () => {
    const draft = profileRef.current
    if (!isReady(draft)) return 'Not ready: the reader needs a name and at least one interest.'
    setSaving(true)
    try {
      const state = await onboard(toOnboardPayload(draft))
      onDone(state)
      return 'Profile saved. The first edition is going to press.'
    } catch {
      setSaving(false)
      return 'Saving failed. Ask the reader to try again.'
    }
  }
  const finishRef = useRef(finish)
  finishRef.current = finish

  const tools = useMemo(() => makeInterviewTools({ dispatch, finish: () => finishRef.current() }), [])
  useFrontendTools(tools, [tools])

  useAgentContext({ description: 'Your instructions as the newspaper editor. Follow them exactly.', value: INTERVIEW_INSTRUCTIONS })
  useAgentContext({
    description: 'readerProfileDraft: the live reader profile card (name, paper title, bio, topic weights; negative = blocked)',
    value: profile,
  })

  return (
    <main className="mx-auto grid max-w-6xl gap-8 px-4 py-10 lg:grid-cols-2">
      <section aria-label="Talk to the Editor" className="flex min-h-[32rem] flex-col border border-ink bg-card">
        <header className="border-b border-rule px-4 py-3">
          <p className="font-meta text-xs uppercase tracking-widest text-ink-muted">The Editor&apos;s desk</p>
          <h1 className="font-headline text-2xl font-black">Talk to the Editor</h1>
        </header>
        {chatError && (
          <div role="alert" className="border-b border-accent px-4 py-2 text-sm text-accent">
            The Editor is unavailable right now.{' '}
            <button type="button" onClick={onFallback} className="underline">
              Use Quick setup instead
            </button>
          </div>
        )}
        <div className="editor-chat min-h-0 flex-1">
          <CopilotChat
            labels={{
              welcomeMessageText: "Good morning! I'm your editor. Every great paper starts with its reader. What's your name?",
              chatInputPlaceholder: 'Tell the Editor…',
            }}
            onError={({ error }) => setChatError(error)}
          />
        </div>
      </section>

      <div className="flex flex-col gap-4">
        <ReaderProfileCard profile={profile} dispatch={dispatch} />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={finish}
            disabled={!isReady(profile) || saving}
            className="bg-ink px-5 py-2 font-medium text-paper disabled:opacity-40"
          >
            {saving ? 'Printing…' : 'Print my first edition'}
          </button>
          <button type="button" onClick={onFallback} className="px-3 py-2 text-sm text-ink-muted underline">
            Switch to Quick setup
          </button>
        </div>
      </div>
    </main>
  )
}

function EditorInterview(props) {
  return (
    <CopilotProvider>
      <Interview {...props} />
    </CopilotProvider>
  )
}

export default EditorInterview
