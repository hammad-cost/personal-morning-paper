import BroadsheetGrid from './BroadsheetGrid'
import CaughtUp from './CaughtUp'
import Masthead from './Masthead'
import SideColumn from './SideColumn'
import ThreeTakeaways from './ThreeTakeaways'

// The broadsheet reading page for one edition.

function Paper({ profile, edition }) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:py-8">
      <Masthead
        title={profile.paper_title}
        date={new Date(`${edition.date}T12:00:00`)}
        edition={edition.edition_number}
        readingMinutes={edition.reading_minutes}
      />
      {edition.writer === 'fallback' && (
        <p className="mt-2 text-center font-meta text-xs text-ink-muted">
          Printed without the AI editor today: summaries are the publishers&apos; own text.
        </p>
      )}

      <ThreeTakeaways takeaways={edition.three_takeaways} />

      <main className="mt-6">
        <BroadsheetGrid
          articles={edition.articles}
          sections={edition.sections}
          weights={profile.topic_weights}
          side={<SideColumn edition={edition} />}
        />
        <CaughtUp storyCount={edition.articles.length} />
      </main>
    </div>
  )
}

export default Paper
