import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { StrictMode } from 'react'
import { getEdition, getGenerationStatus, getState, getTodayEdition, listEditions, printNextEdition } from '../api'
import App from '../App'
import { sampleEdition } from '../test/edition'
import ArchiveDrawer from './ArchiveDrawer'

vi.mock('../api', () => ({
  getState: vi.fn(),
  getTodayEdition: vi.fn(),
  getGenerationStatus: vi.fn(),
  printNextEdition: vi.fn(),
  listEditions: vi.fn(),
  getEdition: vi.fn(),
  sendSignal: vi.fn(),
  swapStory: vi.fn(),
  getBrain: vi.fn(),
  pdfUrl: (id) => `/api/edition/${id}/pdf`,
  downloadPdf: vi.fn(),
}))
vi.mock('../copilot/config', () => ({ hasCopilot: () => false, copilotApiKey: '' }))

const rows = [
  { id: 'ed-2026-10-17-2', edition_number: 2, date: '2026-10-17', reading_minutes: 3, lead_headline: 'Quantum chip record' },
  { id: 'ed-2026-10-17-1', edition_number: 1, date: '2026-10-17', reading_minutes: 4, lead_headline: 'Rogue AI agents broke into live systems' },
]
const edition2 = {
  ...sampleEdition,
  id: 'ed-2026-10-17-2',
  edition_number: 2,
  articles: [{ ...sampleEdition.articles[0], id: 'a1', headline: 'Quantum chip record', topic: 'Quantum Computing' }, ...sampleEdition.articles.slice(1)],
}
const profile = { onboarded: true, name: 'Ayesha', paper_title: 'THE AYESHA CHRONICLE', bio: '', topic_weights: {}, source_weights: {} }

describe('ArchiveDrawer', () => {
  afterEach(() => vi.resetAllMocks())

  it('lists editions newest first and marks the one being read', async () => {
    listEditions.mockResolvedValue(rows)
    render(<ArchiveDrawer open onClose={() => {}} currentId="ed-2026-10-17-2" onOpen={() => {}} />)
    const items = within(await screen.findByRole('list', { name: 'Editions' })).getAllByRole('button', { name: /^edition no\./i })
    expect(items.map((b) => b.textContent)).toEqual([
      expect.stringContaining('Edition No. 2'),
      expect.stringContaining('Edition No. 1'),
    ])
    expect(items[0]).toHaveAttribute('aria-current', 'page')
    expect(items[0]).toHaveTextContent(/reading now/i)
    // Every entry has its own PDF download.
    expect(screen.getByRole('button', { name: 'Download Edition No. 1 as PDF' })).toBeInTheDocument()
  })

  it('selecting an edition loads it and hands it over', async () => {
    listEditions.mockResolvedValue(rows)
    getEdition.mockResolvedValue(sampleEdition)
    const onOpen = vi.fn()
    const onClose = vi.fn()
    render(<ArchiveDrawer open onClose={onClose} currentId="ed-2026-10-17-2" onOpen={onOpen} />)
    await screen.findByRole('list', { name: 'Editions' })
    await act(async () => fireEvent.click(screen.getByRole('button', { name: /^edition no\. 1/i })))
    expect(getEdition).toHaveBeenCalledWith('ed-2026-10-17-1')
    expect(onOpen).toHaveBeenCalledWith(sampleEdition)
    expect(onClose).toHaveBeenCalled()
  })
})

describe('Print next edition and reopen from the archive', () => {
  beforeEach(() => {
    getState.mockResolvedValue({ onboarded: true, profile, today_edition_id: sampleEdition.id })
    getTodayEdition.mockResolvedValue(sampleEdition)
    getGenerationStatus.mockResolvedValue({ state: 'running', step: 'writing', step_index: 2 })
    printNextEdition.mockResolvedValue(edition2)
    listEditions.mockResolvedValue(rows)
    getEdition.mockResolvedValue(sampleEdition)
  })
  afterEach(() => vi.resetAllMocks())

  it('prints exactly one new edition, even under StrictMode, and the masthead updates', async () => {
    render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
    expect(await screen.findByText(/edition no\. 1/i)).toBeInTheDocument()

    await act(async () => fireEvent.click(screen.getByRole('button', { name: /print next edition/i })))
    expect(await screen.findByText(/edition no\. 2/i)).toBeInTheDocument()
    expect(printNextEdition).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('heading', { level: 2, name: 'Quantum chip record' })).toBeInTheDocument()

    // Reopen Edition 1 from Past Editions.
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Past Editions' })))
    await screen.findByRole('list', { name: 'Editions' })
    await act(async () => fireEvent.click(screen.getByRole('button', { name: /^edition no\. 1/i })))
    const masthead = await screen.findByRole('banner')
    await vi.waitFor(() => expect(within(masthead).getByText('Edition No. 1')).toBeInTheDocument())
    expect(screen.getByRole('heading', { level: 2, name: 'Rogue AI agents broke into live systems' })).toBeInTheDocument()
  })
})
