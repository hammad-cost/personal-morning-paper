// The end of a finite paper, followed by the recall check.

function CaughtUp({ storyCount, children }) {
  return (
    <section aria-label="End of paper" className="mt-10 border-y-4 border-double border-ink py-10 text-center">
      <p className="font-meta text-xs uppercase tracking-widest text-ink-muted">— 30 —</p>
      <h2 className="mt-2 font-headline text-3xl font-black sm:text-4xl">You&apos;re all caught up.</h2>
      <p className="mt-2 text-ink-muted">
        {storyCount} stories, finished. Can you name three things you learned?
      </p>
      {children}
    </section>
  )
}

export default CaughtUp
