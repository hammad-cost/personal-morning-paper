import { CopilotSidebar, useAgentContext, useFrontendTools } from '@copilotkit/react-core/v2'
import { useMemo, useRef } from 'react'
import CopilotProvider from '../copilot/CopilotProvider'
import { DESK_INSTRUCTIONS, makeDeskTools } from '../copilot/deskTools'

// AI Editor Desk: a CopilotKit sidebar that reads the open edition and edits the paper by chat.
// Paper owns all state; the desk only calls the handlers it is given.

function Desk({ open, onOpenChange, stories, weights, edition, onAdjust, onSwap, onPrintNext, onQuiz }) {
  // Tools are registered once; refs let their handlers see the latest paper.
  const latest = useRef({})
  latest.current = { stories, weights, onAdjust, onSwap, onPrintNext, onQuiz }

  const tools = useMemo(
    () =>
      makeDeskTools({
        stories: () => latest.current.stories,
        adjust: (topic, delta, words) => latest.current.onAdjust(topic, delta, words),
        swap: (story, topic) => latest.current.onSwap(story, topic),
        explain: (story) => ({
          number: story.number,
          headline: story.headline,
          topic: story.topic,
          source: story.source,
          summary: story.summary,
          why_it_matters: story.why_it_matters,
          reader_weight_for_topic: latest.current.weights[story.topic] ?? 0,
          placement: story.is_lead ? 'lead story (highest score today)' : story.is_explore ? 'Something new (explore pick)' : 'regular',
        }),
        printNext: onPrintNext ? () => latest.current.onPrintNext() : undefined,
        quiz: onQuiz ? () => latest.current.onQuiz() : undefined,
      }),
    [onPrintNext, onQuiz],
  )
  useFrontendTools(tools, [tools])

  useAgentContext({ description: 'Your instructions as the Editor Desk. Follow them exactly.', value: DESK_INSTRUCTIONS })
  useAgentContext({
    description: 'currentEdition: the open paper. stories are numbered in reading order; story 1 is the lead.',
    value: {
      edition_number: edition.edition_number,
      date: edition.date,
      sections: edition.sections,
      stories: stories.map(({ number, topic, headline, summary, source, is_lead, is_explore }) => ({
        number, topic, headline, summary, source, is_lead, is_explore,
      })),
      skipped_headlines: edition.articles.filter((a) => a.skipped).map((a) => a.headline),
    },
  })
  useAgentContext({ description: "topicWeights: the reader's current topic weights (-15 to 25; negative = blocked)", value: weights })

  return (
    <CopilotSidebar
      open={open}
      onOpenChange={onOpenChange}
      position="right"
      width={420}
      labels={{
        modalHeaderTitle: 'The Editor Desk',
        welcomeMessageText: 'Good morning. Tell me what to change: "less politics, more quantum computing", "swap the lead for climate tech", or "why does story 3 matter to me?"',
        chatInputPlaceholder: 'Tell the Editor…',
      }}
    />
  )
}

function EditorDesk(props) {
  return (
    <CopilotProvider>
      <Desk {...props} />
    </CopilotProvider>
  )
}

export default EditorDesk
