// Reader profile draft used by both onboarding paths (Editor chat and Quick setup).
// Weights follow BLUEPRINT.md: core interest 10, casual 5, blocked -10, clamped to [-15, 25].

export const WEIGHTS = { core: 10, casual: 5, blocked: -10 }
export const MIN_WEIGHT = -15
export const MAX_WEIGHT = 25

export const initialProfile = {
  name: '',
  paper_title: '',
  title_custom: false, // true once the reader picks or types their own paper name
  bio: '',
  topics: {}, // { "AI Agents": 10, "Celebrity Gossip": -10 }
}

export const clampWeight = (w) => Math.max(MIN_WEIGHT, Math.min(MAX_WEIGHT, Math.round(w)))

export const paperTitleFor = (name) => (name.trim() ? `THE ${name.trim().toUpperCase()} CHRONICLE` : '')

// Ready-made paper names offered at onboarding; the reader can also type their own.
export const paperTitleSuggestions = (name) => {
  const n = name.trim().toUpperCase()
  if (!n) return []
  return [`THE ${n} CHRONICLE`, `THE ${n} TIMES`, `THE ${n} DAILY`, `${n}'S MORNING EDITION`]
}

const tidy = (topic) => topic.trim().replace(/\s+/g, ' ')

// Find an existing key case-insensitively so "ai agents" and "AI Agents" are one pill.
const existingKey = (topics, topic) =>
  Object.keys(topics).find((k) => k.toLowerCase() === topic.toLowerCase())

function setTopic(topics, rawTopic, weight) {
  const topic = tidy(rawTopic)
  if (!topic) return topics
  const key = existingKey(topics, topic) ?? topic
  return { ...topics, [key]: clampWeight(weight) }
}

export function profileReducer(state, action) {
  switch (action.type) {
    // Text is kept as typed (inputs need spaces mid-word); toOnboardPayload trims.
    case 'SET_NAME':
      // The paper name follows the reader's name until they choose their own.
      return { ...state, name: action.name, paper_title: state.title_custom ? state.paper_title : paperTitleFor(action.name) }
    case 'SET_PAPER_TITLE':
      // Clearing the field hands the name back to the automatic one.
      return action.title.trim()
        ? { ...state, paper_title: action.title, title_custom: true }
        : { ...state, paper_title: paperTitleFor(state.name), title_custom: false }
    case 'SET_BIO':
      return { ...state, bio: action.bio }
    case 'ADD_TOPICS': {
      // topics: [{ name, level: 'core' | 'casual' }] or plain strings (treated as core)
      let topics = state.topics
      for (const t of action.topics) {
        const name = typeof t === 'string' ? t : t.name
        const level = typeof t === 'string' ? 'core' : (t.level ?? 'core')
        topics = setTopic(topics, name, WEIGHTS[level] ?? WEIGHTS.core)
      }
      return { ...state, topics }
    }
    case 'BLOCK_TOPICS': {
      let topics = state.topics
      for (const name of action.topics) topics = setTopic(topics, name, WEIGHTS.blocked)
      return { ...state, topics }
    }
    case 'SET_WEIGHT': {
      const key = existingKey(state.topics, tidy(action.topic))
      if (!key) return state
      return { ...state, topics: { ...state.topics, [key]: clampWeight(action.weight) } }
    }
    case 'REMOVE_TOPIC': {
      const key = existingKey(state.topics, tidy(action.topic))
      if (!key) return state
      const { [key]: _removed, ...topics } = state.topics
      return { ...state, topics }
    }
    default:
      return state
  }
}

export const isBlocked = (weight) => weight < 0

export const isReady = (profile) => profile.name.trim() !== '' && Object.values(profile.topics).some((w) => w > 0)

// Shape expected by POST /api/onboard.
export const toOnboardPayload = (profile) => ({
  name: profile.name.trim(),
  paper_title: profile.paper_title.trim() || paperTitleFor(profile.name),
  bio: profile.bio.trim(),
  topic_weights: profile.topics,
})
