import { render, screen } from '@testing-library/react'
import { makeInterviewTools } from './interviewTools'

const setup = () => {
  const dispatch = vi.fn()
  const finish = vi.fn().mockResolvedValue('done')
  const tools = Object.fromEntries(makeInterviewTools({ dispatch, finish }).map((t) => [t.name, t]))
  return { dispatch, finish, tools }
}

describe('interview tools', () => {
  it('defines the blueprint actions plus setPaperTitle, with schemas', () => {
    const { tools } = setup()
    expect(Object.keys(tools)).toEqual(['setReaderName', 'setPaperTitle', 'addTopics', 'blockTopics', 'setBio', 'finishOnboarding'])
    for (const tool of Object.values(tools)) {
      expect(tool.description).toBeTruthy()
      expect(tool.parameters['~standard']).toBeDefined()
    }
  })

  it('handlers dispatch the matching reducer actions', async () => {
    const { tools, dispatch } = setup()
    await tools.setReaderName.handler({ name: 'Ayesha' })
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'SET_NAME', name: 'Ayesha' })

    const topics = [{ name: 'AI Agents', level: 'core' }]
    await tools.addTopics.handler({ topics })
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'ADD_TOPICS', topics })

    await tools.blockTopics.handler({ topics: ['Celebrity Gossip'] })
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'BLOCK_TOPICS', topics: ['Celebrity Gossip'] })

    await tools.setPaperTitle.handler({ title: 'The Iqra Times' })
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'SET_PAPER_TITLE', title: 'The Iqra Times' })

    await tools.setBio.handler({ bio: 'CS student' })
    expect(dispatch).toHaveBeenLastCalledWith({ type: 'SET_BIO', bio: 'CS student' })
  })

  it('finishOnboarding delegates to finish', async () => {
    const { tools, finish } = setup()
    expect(await tools.finishOnboarding.handler({})).toBe('done')
    expect(finish).toHaveBeenCalled()
  })

  it('validates tool arguments with the schema', async () => {
    const { tools } = setup()
    const ok = await tools.addTopics.parameters['~standard'].validate({ topics: [{ name: 'Space', level: 'casual' }] })
    expect(ok.issues).toBeUndefined()
    const bad = await tools.addTopics.parameters['~standard'].validate({ topics: [{ name: 'Space', level: 'huge' }] })
    expect(bad.issues?.length).toBeGreaterThan(0)
  })

  it('renders added and blocked pills inside the chat', () => {
    const { tools } = setup()
    const Added = tools.addTopics.render
    const Blocked = tools.blockTopics.render
    render(
      <>
        <Added args={{ topics: [{ name: 'AI Agents', level: 'core' }, { name: 'Space', level: 'casual' }] }} />
        <Blocked args={{ topics: ['Celebrity Gossip'] }} />
      </>,
    )
    expect(screen.getByText('AI Agents · 10')).toBeInTheDocument()
    expect(screen.getByText('Space · 5')).toBeInTheDocument()
    expect(screen.getByText('Celebrity Gossip · -10')).toBeInTheDocument()
  })
})
