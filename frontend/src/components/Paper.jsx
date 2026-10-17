import Masthead from './Masthead'

// Placeholder paper page. The broadsheet itself arrives in Step 5.

function Paper({ profile }) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Masthead title={profile.paper_title} />
      <main className="py-12 text-center">
        <p className="font-headline text-2xl">Good morning, {profile.name}.</p>
        <p className="mt-2 text-ink-muted">Your first edition is being set in type. (Step 4)</p>
      </main>
    </div>
  )
}

export default Paper
