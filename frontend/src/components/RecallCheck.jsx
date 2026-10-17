import { Check, X } from 'lucide-react'
import { useState } from 'react'
import { scrollToStory, storyAnchor } from './ThreeTakeaways'

// "Can you name 3 things?" — 3 quick questions after the paper ends.
// Instant feedback, a score at the end, and a QUIZ_RIGHT / QUIZ_WRONG signal per answer.

export const RECALL_ID = 'recall-check'

const VERDICTS = ['Time for a second coffee.', 'A start. Tomorrow will stick better.', 'Nearly there.', 'Three for three. You read the paper.']

function Question({ q, index, answer, onPick }) {
  const answered = answer !== undefined
  return (
    <li className="border-t border-rule py-4">
      <p className="font-meta text-[11px] uppercase tracking-widest text-ink-muted">Question {index + 1}</p>
      <p className="mt-1 font-headline text-lg font-bold leading-snug">{q.question}</p>
      <div role="group" aria-label={`Answers for question ${index + 1}`} className="mt-3 grid gap-2 sm:grid-cols-3">
        {q.options.map((option, i) => {
          const isRight = i === q.answer_index
          const picked = answer === i
          const state = !answered ? 'open' : isRight ? 'right' : picked ? 'wrong' : 'muted'
          return (
            <button
              key={i}
              type="button"
              disabled={answered}
              aria-pressed={picked}
              onClick={() => onPick(i)}
              className={`flex items-center justify-between gap-2 border px-3 py-2 text-left text-sm ${
                {
                  open: 'border-ink hover:bg-ink hover:text-paper',
                  right: 'border-ink bg-ink text-paper',
                  wrong: 'border-accent text-accent line-through',
                  muted: 'border-rule text-ink-muted',
                }[state]
              }`}
            >
              <span>{option}</span>
              {state === 'right' && <Check className="size-4 shrink-0" aria-label="correct answer" />}
              {state === 'wrong' && <X className="size-4 shrink-0" aria-label="your answer, wrong" />}
            </button>
          )
        })}
      </div>
      {answered && (
        <p role="status" className="mt-2 text-sm">
          {answer === q.answer_index ? (
            <span>Right. </span>
          ) : (
            <span className="text-accent">Not quite: it was “{q.options[q.answer_index]}”. </span>
          )}
          <a
            href={`#${storyAnchor(q.article_id)}`}
            onClick={(e) => {
              if (scrollToStory(q.article_id)) e.preventDefault()
            }}
            className="font-meta text-xs uppercase tracking-wider underline underline-offset-4"
          >
            Back to the story
          </a>
        </p>
      )}
    </li>
  )
}

function RecallCheck({ quiz = [], articles = [], onAnswer }) {
  const [answers, setAnswers] = useState({})
  // Only ask about stories the reader still has in their paper.
  const live = new Set(articles.filter((a) => !a.skipped).map((a) => a.id))
  const questions = quiz.filter((q) => live.has(q.article_id) && q.options?.length === 3).slice(0, 3)
  if (!questions.length) return null

  const done = questions.every((_, i) => answers[i] !== undefined)
  const score = questions.filter((q, i) => answers[i] === q.answer_index).length

  const pick = (i, option) => {
    if (answers[i] !== undefined) return
    setAnswers((prev) => ({ ...prev, [i]: option }))
    onAnswer?.(questions[i], option === questions[i].answer_index)
  }

  return (
    <section id={RECALL_ID} tabIndex={-1} aria-labelledby="recall-title" className="mx-auto mt-8 max-w-3xl scroll-mt-4 text-left outline-none">
      <h2 id="recall-title" className="text-center font-headline text-2xl font-black">
        Can you name 3 things?
      </h2>
      <p className="mt-1 text-center text-sm text-ink-muted">Three quick questions from today&apos;s paper.</p>
      <ol className="mt-4">
        {questions.map((q, i) => (
          <Question key={`${q.article_id}-${i}`} q={q} index={i} answer={answers[i]} onPick={(o) => pick(i, o)} />
        ))}
      </ol>
      {done && (
        <p role="status" aria-live="polite" className="border-t-4 border-double border-ink pt-4 text-center">
          <span className="font-headline text-3xl font-black">
            {score} of {questions.length}
          </span>
          <span className="mt-1 block text-sm text-ink-muted">{VERDICTS[Math.min(score, 3)]}</span>
        </p>
      )}
    </section>
  )
}

export default RecallCheck
