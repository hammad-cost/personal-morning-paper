import { z } from 'zod'
import { WEIGHTS } from '../profile/profileReducer'

// Frontend tools (CopilotKit v2 `useFrontendTools`) for the onboarding interviewer.
// Kept as plain data + handlers so they can be unit-tested without CopilotKit.

export const INTERVIEW_INSTRUCTIONS = `You are the warm, witty editor-in-chief at Vale, about to launch a brand-new personal newspaper for one reader, and you are interviewing them.
Your job is to learn enough to print their first edition.
Rules:
- Ask ONE short question at a time. Ask at most 4 questions in total: their name, what they do, what they can't stop reading about, and what they never want to see.
- Call a tool as soon as you learn something: setReaderName for their name, setBio for a one-line plain-English bio, addTopics for interests (level "core" for strong interests, "casual" for mild ones), blockTopics for things they never want to see.
- After setReaderName, mention the paper's default name (e.g. THE IQRA CHRONICLE) in the same reply as your next question, and say they can rename it. If the reader asks for another name or style ("call it The Iqra Times"), call setPaperTitle. Do not spend a separate question on it.
- Use short, newspaper-section style topic names (e.g. "AI Agents", "Cybersecurity", "Climate Tech").
- Never invent interests the reader did not mention.
- The reader can edit their profile card by hand; always trust the latest readerProfileDraft.
- When you have a name and at least one interest, ask if they're ready, and when they agree call finishOnboarding.
Keep replies to one or two sentences.`

function PillsInChat({ topics, blocked }) {
  if (!topics?.length) return null
  return (
    <ul className="my-1 flex flex-wrap gap-1.5" aria-label={blocked ? 'Blocked topics' : 'Added topics'}>
      {topics.map((t) => {
        const name = typeof t === 'string' ? t : t?.name
        if (!name) return null
        const weight = blocked ? WEIGHTS.blocked : (WEIGHTS[t?.level] ?? WEIGHTS.core)
        return (
          <li
            key={name}
            className={`border px-2 py-0.5 font-meta text-xs ${blocked ? 'border-accent text-accent line-through' : 'border-ink'}`}
          >
            {name} · {weight}
          </li>
        )
      })}
    </ul>
  )
}

export function makeInterviewTools({ dispatch, finish }) {
  return [
    {
      name: 'setReaderName',
      description: "Set the reader's first name. Unless they already chose a paper name, the paper becomes THE <NAME> CHRONICLE.",
      parameters: z.object({ name: z.string().describe("The reader's first name") }),
      handler: async ({ name }) => {
        dispatch({ type: 'SET_NAME', name })
        return `Name set to ${name.trim()}. The default paper name is THE ${name.trim().toUpperCase()} CHRONICLE unless they pick another.`
      },
    },
    {
      name: 'setPaperTitle',
      description: "Rename the reader's newspaper, e.g. THE IQRA TIMES. Only when the reader asks for a different name or style.",
      parameters: z.object({ title: z.string().describe('The full paper name as it should print on the masthead') }),
      handler: async ({ title }) => {
        dispatch({ type: 'SET_PAPER_TITLE', title })
        return `The paper is now called ${title.trim().toUpperCase()}.`
      },
    },
    {
      name: 'addTopics',
      description: 'Add topics the reader wants to read about. core = strong interest (weight 10), casual = mild interest (weight 5).',
      parameters: z.object({
        topics: z.array(
          z.object({
            name: z.string().describe('Short section-style topic name'),
            level: z.enum(['core', 'casual']),
          }),
        ),
      }),
      handler: async ({ topics }) => {
        dispatch({ type: 'ADD_TOPICS', topics })
        return `Added ${topics.map((t) => t.name).join(', ')}.`
      },
      render: ({ args }) => <PillsInChat topics={args?.topics} />,
    },
    {
      name: 'blockTopics',
      description: 'Block topics the reader never wants to see (weight -10).',
      parameters: z.object({ topics: z.array(z.string()) }),
      handler: async ({ topics }) => {
        dispatch({ type: 'BLOCK_TOPICS', topics })
        return `Blocked ${topics.join(', ')}.`
      },
      render: ({ args }) => <PillsInChat topics={args?.topics} blocked />,
    },
    {
      name: 'setBio',
      description: 'Save a one-line plain-English bio of the reader, e.g. "CS student into AI agents and cybersecurity".',
      parameters: z.object({ bio: z.string() }),
      handler: async ({ bio }) => {
        dispatch({ type: 'SET_BIO', bio })
        return 'Bio saved.'
      },
    },
    {
      name: 'finishOnboarding',
      description: 'Save the profile and print the first edition. Only call when the reader has a name and at least one interest and has agreed.',
      parameters: z.object({}),
      handler: async () => finish(),
    },
  ]
}
