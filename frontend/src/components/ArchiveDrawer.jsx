import { Download, Printer, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { downloadPdf, getEdition, listEditions } from '../api'

// Past Editions: every edition newest first; picking one reopens it.

const formatDate = (iso) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })

function ArchiveDrawer({ open, onClose, currentId, onOpen, onPrintNext }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)
  const [opening, setOpening] = useState(null)
  const closeRef = useRef(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    listEditions().then(setRows).catch((e) => setError(e.message))
  }, [open])

  useEffect(() => {
    if (!open) return
    closeRef.current?.focus()
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const pick = async (id) => {
    if (id === currentId) return onClose()
    setOpening(id)
    try {
      onOpen(await getEdition(id))
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setOpening(null)
    }
  }

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-ink/20 transition-opacity duration-200 motion-reduce:transition-none ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="archive-title"
        aria-hidden={!open}
        inert={!open || undefined}
        className={`fixed inset-y-0 left-0 z-50 flex w-full max-w-md flex-col border-r-2 border-ink bg-card transition-transform duration-200 motion-reduce:transition-none ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <header className="flex items-start justify-between border-b-4 border-double border-ink px-5 py-4">
          <div>
            <p className="font-meta text-[11px] uppercase tracking-widest text-ink-muted">The morgue</p>
            <h2 id="archive-title" className="font-headline text-3xl font-black">
              Past Editions
            </h2>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Close Past Editions" className="p-1 hover:bg-rule">
            <X className="size-5" aria-hidden="true" />
          </button>
        </header>

        {onPrintNext && (
          <div className="border-b border-rule px-5 py-3">
            <button
              type="button"
              onClick={() => {
                onClose()
                onPrintNext()
              }}
              className="flex w-full items-center justify-center gap-2 bg-ink px-4 py-2 font-medium text-paper"
            >
              <Printer className="size-4" aria-hidden="true" /> Print next edition
            </button>
            <p className="mt-1 text-center text-xs text-ink-muted">Uses everything your paper has learned so far.</p>
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-5 py-2">
          {error && (
            <p role="alert" className="py-2 text-sm text-accent">
              {error}
            </p>
          )}
          {!rows && !error && <p className="py-2 font-meta text-sm text-ink-muted">Pulling the files…</p>}
          {rows && (
            <ol aria-label="Editions" className="divide-y divide-rule">
              {rows.map((r) => {
                const current = r.id === currentId
                return (
                  <li key={r.id} className="flex items-start gap-2">
                    <button
                      type="button"
                      onClick={() => pick(r.id)}
                      aria-current={current ? 'page' : undefined}
                      className={`min-w-0 flex-1 py-3 text-left hover:bg-paper ${current ? 'border-l-4 border-accent pl-3' : ''}`}
                    >
                      <span className="block font-meta text-[11px] uppercase tracking-widest text-ink-muted">
                        Edition No. {r.edition_number} · {formatDate(r.date)} · {r.reading_minutes} min
                        {current && <span className="text-accent"> · Reading now</span>}
                        {opening === r.id && ' · Opening…'}
                      </span>
                      <span className="mt-1 block font-headline text-lg font-bold leading-snug">{r.lead_headline}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => downloadPdf(r.id).catch((e) => setError(e.message))}
                      aria-label={`Download Edition No. ${r.edition_number} as PDF`}
                      className="mt-3 flex shrink-0 items-center gap-1 border border-ink px-2 py-1 font-meta text-[11px] uppercase tracking-wider hover:bg-ink hover:text-paper"
                    >
                      <Download className="size-3.5" aria-hidden="true" /> PDF
                    </button>
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      </aside>
    </>
  )
}

export default ArchiveDrawer
