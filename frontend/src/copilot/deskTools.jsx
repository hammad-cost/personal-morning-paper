import { z } from 'zod'

// Frontend tools (CopilotKit v2) for the AI Editor Desk sidebar on the paper.
// Plain data + handlers so they can be tested without CopilotKit.

export const DESK_INSTRUCTIONS = `You are the reader's editor, sitting at their desk beside today's paper.
You can change the paper with tools:
- "more X" / "less X" / "I'm bored of X": call adjustInterest once per topic (more = +5, less = -5). Pass the reader's own words. Use the reader's own topic name (e.g. "Politics"); reuse an existing topic from topicWeights only if it means exactly the same thing.
- "swap / replace story N for something on Y": call swapStory exactly ONCE per request. Story 1 is the lead story; numbers follow the stories list in currentEdition. When it returns, the swap is done: report it and do not call swapStory again unless the reader asks for another swap.
- "why does story N matter to me?" or "explain story N": call explainStory, then answer in 2-3 sentences using ONLY the fields it returns. Never add facts that are not there.
- printNextEdition and quizMe only when the reader asks for them.
Use short, calm newspaper-editor replies. Never invent news, numbers or sources. If a story number does not exist, say so.`

function DeltaChip({ topic, direction }) {
  if (!topic) return null
  const more = direction !== 'less'
  return (
    <span className={`my-1 inline-block border px-2 py-0.5 font-meta text-xs ${more ? 'border-ink' : 'border-accent text-accent'}`}>
      {topic} {more ? '+5' : '−5'}
    </span>
  )
}

export function makeDeskTools({ stories, adjust, swap, explain, printNext, quiz }) {
  const byNumber = (n) => stories().find((s) => s.number === Number(n))

  return [
    {
      name: 'adjustInterest',
      description: "Make the reader's paper show more or less of a topic (changes its weight by 5).",
      parameters: z.object({
        topic: z.string().describe('Short section-style topic name, e.g. "Quantum Computing"'),
        direction: z.enum(['more', 'less']),
        readerWords: z.string().describe("The reader's own words for this request").optional(),
      }),
      handler: async ({ topic, direction, readerWords }) => {
        const weight = await adjust(topic, direction === 'more' ? 5 : -5, readerWords ?? '')
        return `${topic} is now weighted ${weight}. Future papers will show ${direction} of it.`
      },
      render: ({ args }) => <DeltaChip topic={args?.topic} direction={args?.direction} />,
    },
    {
      name: 'swapStory',
      description: 'Replace one story in today\'s paper with a fresh one on a topic. Story 1 is the lead.',
      parameters: z.object({
        storyNumber: z.number().int().describe('Number from the stories list; 1 is the lead'),
        topic: z.string().describe('Topic for the replacement story'),
      }),
      handler: async ({ storyNumber, topic }) => {
        const story = byNumber(storyNumber)
        if (!story) return `There is no story ${storyNumber} in today's paper.`
        const fresh = await swap(story, topic)
        if (fresh.alreadySwapped) {
          return `Story ${storyNumber} was already swapped to ${topic} a moment ago ("${fresh.headline}"). Not swapping again.`
        }
        return `Swapped story ${storyNumber} ("${story.headline}") for "${fresh.headline}" from ${fresh.source_name}. Done.`
      },
    },
    {
      name: 'explainStory',
      description: 'Get the facts needed to explain why a story is in the paper and why it matters to the reader.',
      parameters: z.object({ storyNumber: z.number().int() }),
      handler: async ({ storyNumber }) => {
        const story = byNumber(storyNumber)
        if (!story) return `There is no story ${storyNumber} in today's paper.`
        return JSON.stringify({ ...explain(story), rule: 'Answer only from these fields.' })
      },
    },
    {
      name: 'printNextEdition',
      description: "Print a new edition now using the reader's updated interests.",
      parameters: z.object({}),
      available: Boolean(printNext),
      handler: async () => (printNext ? printNext() : 'Printing a new edition is not available yet.'),
    },
    {
      name: 'quizMe',
      description: "Open the 'Can you name 3 things?' recall check.",
      parameters: z.object({}),
      available: Boolean(quiz),
      handler: async () => (quiz ? quiz() : 'The recall check is not available yet.'),
    },
  ]
}
