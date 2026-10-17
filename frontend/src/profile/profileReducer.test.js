import { initialProfile, isReady, profileReducer, toOnboardPayload } from './profileReducer'

const run = (...actions) => actions.reduce(profileReducer, initialProfile)

describe('profileReducer', () => {
  it('SET_NAME sets the name and masthead', () => {
    const p = run({ type: 'SET_NAME', name: 'Ayesha ' })
    expect(p.name).toBe('Ayesha ') // kept as typed so the next keystroke can add a space
    expect(p.paper_title).toBe('THE AYESHA CHRONICLE')
  })

  it('keeps spaces while typing and trims in the payload', () => {
    const p = run(
      { type: 'SET_NAME', name: ' Mary Ann ' },
      { type: 'SET_BIO', bio: 'CS student ' },
      { type: 'ADD_TOPICS', topics: ['Space'] },
    )
    expect(p.bio).toBe('CS student ')
    expect(toOnboardPayload(p)).toMatchObject({ name: 'Mary Ann', paper_title: 'THE MARY ANN CHRONICLE', bio: 'CS student' })
  })

  it('ADD_TOPICS uses 10 for core and 5 for casual', () => {
    const p = run({
      type: 'ADD_TOPICS',
      topics: [{ name: 'AI Agents', level: 'core' }, { name: 'Space', level: 'casual' }, 'Cybersecurity'],
    })
    expect(p.topics).toEqual({ 'AI Agents': 10, Space: 5, Cybersecurity: 10 })
  })

  it('treats topics case-insensitively and ignores blanks', () => {
    const p = run(
      { type: 'ADD_TOPICS', topics: ['AI Agents'] },
      { type: 'ADD_TOPICS', topics: [{ name: 'ai agents', level: 'casual' }, '   '] },
    )
    expect(p.topics).toEqual({ 'AI Agents': 5 })
  })

  it('BLOCK_TOPICS sets -10, including on an existing interest', () => {
    const p = run(
      { type: 'ADD_TOPICS', topics: ['Crypto'] },
      { type: 'BLOCK_TOPICS', topics: ['crypto', 'Celebrity Gossip'] },
    )
    expect(p.topics).toEqual({ Crypto: -10, 'Celebrity Gossip': -10 })
  })

  it('REMOVE_TOPIC removes a pill', () => {
    const p = run(
      { type: 'ADD_TOPICS', topics: ['AI Agents', 'Space'] },
      { type: 'REMOVE_TOPIC', topic: 'space' },
    )
    expect(p.topics).toEqual({ 'AI Agents': 10 })
  })

  it('SET_WEIGHT clamps between -15 and 25 and ignores unknown topics', () => {
    let p = run({ type: 'ADD_TOPICS', topics: ['AI Agents'] }, { type: 'SET_WEIGHT', topic: 'AI Agents', weight: 99 })
    expect(p.topics['AI Agents']).toBe(25)
    p = profileReducer(p, { type: 'SET_WEIGHT', topic: 'AI Agents', weight: -99 })
    expect(p.topics['AI Agents']).toBe(-15)
    expect(profileReducer(p, { type: 'SET_WEIGHT', topic: 'Nope', weight: 3 })).toBe(p)
  })

  it('isReady needs a name and at least one positive topic', () => {
    expect(isReady(run({ type: 'SET_NAME', name: 'A' }))).toBe(false)
    expect(isReady(run({ type: 'SET_NAME', name: 'A' }, { type: 'BLOCK_TOPICS', topics: ['X'] }))).toBe(false)
    expect(isReady(run({ type: 'SET_NAME', name: 'A' }, { type: 'ADD_TOPICS', topics: ['X'] }))).toBe(true)
  })

  it('toOnboardPayload matches the /api/onboard shape', () => {
    const p = run(
      { type: 'SET_NAME', name: 'Ayesha' },
      { type: 'SET_BIO', bio: 'CS student' },
      { type: 'ADD_TOPICS', topics: ['AI Agents'] },
      { type: 'BLOCK_TOPICS', topics: ['Celebrity Gossip'] },
    )
    expect(toOnboardPayload(p)).toEqual({
      name: 'Ayesha',
      paper_title: 'THE AYESHA CHRONICLE',
      bio: 'CS student',
      topic_weights: { 'AI Agents': 10, 'Celebrity Gossip': -10 },
    })
  })
})
