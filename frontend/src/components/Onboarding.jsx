// Placeholder welcome screen. Step 2 adds "Talk to the Editor" and "Quick setup".

function Onboarding() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center px-4 text-center">
      <p className="font-meta text-xs uppercase tracking-widest text-ink-muted">
        The Personal Morning Paper
      </p>
      <h1 className="mt-4 border-y-4 border-double border-ink py-6 font-headline text-4xl font-black sm:text-5xl">
        Every great paper starts with its reader.
      </h1>
      <p className="mt-6 text-ink-muted">Onboarding arrives in Step 2.</p>
    </main>
  )
}

export default Onboarding
