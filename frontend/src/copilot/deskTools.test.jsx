import { makeDeskTools } from './deskTools'

const stories = [
  { number: 1, id: 'a1', topic: 'AI Agents', headline: 'Lead story', source: 'Reuters', is_lead: true },
  { number: 2, id: 'a4', topic: 'Politics', headline: 'Election news', source: 'BBC News' },
]

const setup = (extra = {}) => {
  const deps = {
    stories: () => stories,
    adjust: vi.fn().mockResolvedValue(15),
    swap: vi.fn().mockResolvedValue({ headline: 'Solar boom', source_name: 'The Verge' }),
    explain: vi.fn((s) => ({ headline: s.headline, summary: 'Facts.' })),
    ...extra,
  }
  const tools = Object.fromEntries(makeDeskTools(deps).map((t) => [t.name, t]))
  return { deps, tools }
}

describe('Editor Desk tools', () => {
  it('defines the five blueprint actions', () => {
    const { tools } = setup()
    expect(Object.keys(tools)).toEqual(['adjustInterest', 'swapStory', 'explainStory', 'printNextEdition', 'quizMe'])
  })

  it('adjustInterest maps more/less to +5/-5 and passes the reader words', async () => {
    const { tools, deps } = setup()
    await tools.adjustInterest.handler({ topic: 'Quantum Computing', direction: 'more', readerWords: 'more quantum' })
    expect(deps.adjust).toHaveBeenLastCalledWith('Quantum Computing', 5, 'more quantum')
    await tools.adjustInterest.handler({ topic: 'Politics', direction: 'less' })
    expect(deps.adjust).toHaveBeenLastCalledWith('Politics', -5, '')
  })

  it('swapStory finds the story by number (1 = lead)', async () => {
    const { tools, deps } = setup()
    const reply = await tools.swapStory.handler({ storyNumber: 1, topic: 'Climate Tech' })
    expect(deps.swap).toHaveBeenCalledWith(stories[0], 'Climate Tech')
    expect(reply).toMatch(/"Solar boom" from The Verge/)
    expect(await tools.swapStory.handler({ storyNumber: 9, topic: 'X' })).toMatch(/no story 9/)
  })

  it('explainStory returns only the story fields, with a no-new-facts rule', async () => {
    const { tools } = setup()
    const reply = JSON.parse(await tools.explainStory.handler({ storyNumber: 2 }))
    expect(reply).toEqual({ headline: 'Election news', summary: 'Facts.', rule: 'Answer only from these fields.' })
  })

  it('printNextEdition and quizMe stay hidden until their steps provide handlers', () => {
    const { tools } = setup()
    expect(tools.printNextEdition.available).toBe(false)
    expect(tools.quizMe.available).toBe(false)
    const withThem = setup({ printNext: vi.fn(), quiz: vi.fn() }).tools
    expect(withThem.printNextEdition.available).toBe(true)
  })

  it('adjustInterest validates its arguments', async () => {
    const { tools } = setup()
    const bad = await tools.adjustInterest.parameters['~standard'].validate({ topic: 'X', direction: 'lots' })
    expect(bad.issues?.length).toBeGreaterThan(0)
  })
})
