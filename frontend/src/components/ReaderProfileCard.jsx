import { Minus, Plus, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { isBlocked, paperTitleSuggestions } from '../profile/profileReducer'

// Live profile card: masthead, bio and editable topic pills.
// Used beside the Editor chat and inside Quick setup.

const STEP = 1

function TopicPill({ topic, weight, dispatch }) {
  const blocked = isBlocked(weight)
  return (
    <li
      className={`flex items-center gap-1 border px-2 py-1 font-meta text-xs ${
        blocked ? 'border-accent text-accent line-through decoration-1' : 'border-ink'
      }`}
      aria-label={`${topic}, weight ${weight}${blocked ? ', blocked' : ''}`}
    >
      <span className="font-body text-sm no-underline">{topic}</span>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_WEIGHT', topic, weight: weight - STEP })}
        aria-label={`Lower ${topic}`}
        className="p-0.5 hover:bg-rule"
      >
        <Minus className="size-3" aria-hidden="true" />
      </button>
      <span className="min-w-6 text-center">{weight}</span>
      <button
        type="button"
        onClick={() => dispatch({ type: 'SET_WEIGHT', topic, weight: weight + STEP })}
        aria-label={`Raise ${topic}`}
        className="p-0.5 hover:bg-rule"
      >
        <Plus className="size-3" aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={() => dispatch({ type: 'REMOVE_TOPIC', topic })}
        aria-label={`Remove ${topic}`}
        className="p-0.5 hover:bg-rule"
      >
        <X className="size-3" aria-hidden="true" />
      </button>
    </li>
  )
}

// "Name your paper": type a name or pick a suggestion. The draft is local so the field can be
// cleared and retyped; it is committed on Enter or when the field loses focus.
function PaperName({ profile, dispatch }) {
  const [draft, setDraft] = useState(profile.paper_title)
  const [editing, setEditing] = useState(false)
  useEffect(() => {
    if (!editing) setDraft(profile.paper_title)
  }, [profile.paper_title, editing])

  const commit = () => {
    setEditing(false)
    dispatch({ type: 'SET_PAPER_TITLE', title: draft })
  }

  return (
    <div className="mt-5">
      <label htmlFor="paper-name" className="font-meta text-xs uppercase tracking-widest text-ink-muted">
        Name your paper
      </label>
      <input
        id="paper-name"
        value={draft}
        onFocus={() => setEditing(true)}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            e.currentTarget.blur()
          }
        }}
        maxLength={60}
        className="mt-1 w-full border border-rule bg-paper px-3 py-1.5 font-headline text-sm font-bold uppercase"
      />
      <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Paper name ideas">
        {paperTitleSuggestions(profile.name).map((title) => (
          <button
            key={title}
            type="button"
            aria-pressed={profile.paper_title === title}
            onClick={() => dispatch({ type: 'SET_PAPER_TITLE', title })}
            className={`border px-2 py-0.5 font-meta text-[11px] ${
              profile.paper_title === title ? 'border-ink bg-ink text-paper' : 'border-rule hover:border-ink'
            }`}
          >
            {title}
          </button>
        ))}
      </div>
    </div>
  )
}

function ReaderProfileCard({ profile, dispatch }) {
  const [newTopic, setNewTopic] = useState('')
  const entries = Object.entries(profile.topics).sort((a, b) => b[1] - a[1])
  const interests = entries.filter(([, w]) => !isBlocked(w))
  const blocked = entries.filter(([, w]) => isBlocked(w))

  const addTopic = (e) => {
    e.preventDefault()
    if (!newTopic.trim()) return
    dispatch({ type: 'ADD_TOPICS', topics: [{ name: newTopic, level: 'core' }] })
    setNewTopic('')
  }

  return (
    <section aria-label="Reader profile" className="border border-ink bg-card p-6">
      <p className="font-meta text-xs uppercase tracking-widest text-ink-muted">Reader profile</p>
      <h2 className="mt-2 border-y-4 border-double border-ink py-3 text-center font-headline text-2xl font-black uppercase sm:text-3xl">
        {profile.paper_title || 'Your paper, unnamed'}
      </h2>
      <p className="mt-3 text-center text-sm text-ink-muted">
        {profile.name ? `Edited for ${profile.name}` : 'Who is this paper for?'}
        {profile.bio && <> · {profile.bio}</>}
      </p>

      {profile.name.trim() && <PaperName profile={profile} dispatch={dispatch} />}

      <h3 className="mt-6 font-meta text-xs uppercase tracking-widest text-ink-muted">Interests</h3>
      {interests.length ? (
        <ul className="mt-2 flex flex-wrap gap-2">
          {interests.map(([t, w]) => (
            <TopicPill key={t} topic={t} weight={w} dispatch={dispatch} />
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-ink-muted">No topics yet.</p>
      )}

      {blocked.length > 0 && (
        <>
          <h3 className="mt-4 font-meta text-xs uppercase tracking-widest text-accent">Never show</h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {blocked.map(([t, w]) => (
              <TopicPill key={t} topic={t} weight={w} dispatch={dispatch} />
            ))}
          </ul>
        </>
      )}

      <form onSubmit={addTopic} className="mt-6 flex gap-2">
        <label htmlFor="add-topic" className="sr-only">
          Add a topic
        </label>
        <input
          id="add-topic"
          value={newTopic}
          onChange={(e) => setNewTopic(e.target.value)}
          placeholder="Add a topic"
          className="min-w-0 flex-1 border border-rule bg-paper px-3 py-1.5 text-sm"
        />
        <button type="submit" className="border border-ink px-3 py-1.5 text-sm hover:bg-ink hover:text-paper">
          Add
        </button>
      </form>
    </section>
  )
}

export default ReaderProfileCard
