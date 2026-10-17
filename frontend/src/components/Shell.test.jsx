import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { downloadPdf, updateSettings } from '../api'
import { sampleEdition } from '../test/edition'
import Logo from './Logo'
import Paper, { VIEW_KEY } from './Paper'

vi.mock('../api', () => ({
  sendSignal: vi.fn(), swapStory: vi.fn(), getBrain: vi.fn(), downloadPdf: vi.fn(),
  emailEdition: vi.fn(), updateSettings: vi.fn(),
}))
vi.mock('../copilot/config', () => ({ hasCopilot: () => false, copilotApiKey: '' }))

const profile = { name: 'Iqra', paper_title: 'THE IQRA TIMES', topic_weights: { 'AI Agents': 10, Cybersecurity: 4, Sport: -3 }, daily_email: true }
const account = { id: 'u1', email: 'iqra@uni.edu', signOut: vi.fn() }

beforeEach(() => {
  window.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})
afterEach(() => vi.resetAllMocks())

describe('Instagram-style shell', () => {
  it('opens on the feed when the reader has not picked a view', () => {
    window.localStorage.removeItem(VIEW_KEY)
    render(<Paper profile={profile} edition={sampleEdition} />)
    expect(screen.getByRole('button', { name: 'Feed' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('navigation', { name: 'Sections' })).toBeInTheDocument()
  })

  it('has one nav with Home, Past Editions, Editor Desk, Brain and You', () => {
    render(<Paper profile={profile} edition={sampleEdition} onOpenEdition={vi.fn()} account={account} emailReady />)
    const nav = screen.getByRole('navigation', { name: 'Paper tools' })
    const labels = within(nav).getAllByRole('button').map((b) => b.textContent)
    expect(labels).toEqual(['Home', 'Past Editions', 'Editor Desk', 'Brain', 'Download PDF', 'Email me this paper', 'Print next edition', 'You', 'Sign out'])
    expect(within(nav).getByRole('button', { name: 'Home' })).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('button', { name: 'Editor Desk' })).toBeDisabled()
  })

  it('You page shows the reader, what Vale learned, and the paper actions; Home goes back', async () => {
    updateSettings.mockResolvedValue({})
    downloadPdf.mockResolvedValue()
    render(<Paper profile={profile} edition={sampleEdition} onOpenEdition={vi.fn()} account={account} emailReady />)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'You' })))

    expect(screen.getByRole('heading', { level: 1, name: 'Iqra' })).toBeInTheDocument()
    expect(screen.getByText('iqra@uni.edu')).toBeInTheDocument()
    const learned = screen.getByRole('heading', { name: /what vale has learned/i }).parentElement
    expect(within(learned).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['AI Agents10', 'Cybersecurity4'])

    await act(async () => fireEvent.click(screen.getByRole('button', { name: "Save today's PDF" })))
    expect(downloadPdf).toHaveBeenCalledWith(sampleEdition.id)
    await act(async () => fireEvent.click(screen.getByRole('checkbox', { name: /morning email/i })))
    expect(updateSettings).toHaveBeenCalledWith({ daily_email: false })

    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Home' })))
    expect(screen.getByRole('heading', { level: 1, name: 'THE IQRA TIMES' })).toBeInTheDocument()
  })
})

describe('Brand', () => {
  it('reads as "Vale" with the blue line under the V', () => {
    const { container } = render(<Logo />)
    expect(screen.getByText('Vale')).toHaveClass('sr-only')
    expect(container.querySelector('.bg-accent')).not.toBeNull()
  })

  it('ships an installable manifest and a blue-line icon', () => {
    const manifest = JSON.parse(readFileSync('public/manifest.webmanifest', 'utf-8'))
    expect(manifest.display).toBe('standalone')
    expect(manifest.icons.map((i) => i.sizes)).toEqual(expect.arrayContaining(['192x192', '512x512']))
    expect(readFileSync('public/vale.svg', 'utf-8')).toContain('#3B82F6')
    expect(readFileSync('index.html', 'utf-8')).toContain('manifest.webmanifest')
  })
})
