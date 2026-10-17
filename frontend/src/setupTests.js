import '@testing-library/jest-dom/vitest'

// The app opens on the feed; most component tests read the broadsheet, so start there.
// Tests that need the feed clear storage or click "Feed".
beforeEach(() => {
  try {
    window.localStorage.setItem('vale.view', 'broadsheet')
  } catch {
    // no storage in this environment
  }
})
