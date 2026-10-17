import { BRAND } from '../brand'

// The Vale mark: a white V with a blue line under it, on a slate tile.
export function ValeMark({ className = 'size-8' }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className={className}>
      <rect width="64" height="64" rx="14" fill="var(--ink)" />
      <path d="M18 15 L32 45 L46 15" fill="none" stroke="#fff" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="17" y="50" width="30" height="4" rx="2" fill="#3b82f6" />
    </svg>
  )
}

// Wordmark: "Vale" with the blue line under the V. Screen readers hear just "Vale".
function Logo({ size = 'md', mark = true }) {
  const text = { sm: 'text-xl', md: 'text-2xl', lg: 'text-4xl', xl: 'text-5xl' }[size]
  const tile = { sm: 'size-6', md: 'size-8', lg: 'size-10', xl: 'size-14' }[size]
  return (
    <span className="inline-flex items-center gap-2">
      {mark && <ValeMark className={tile} />}
      <span className={`font-headline font-black leading-none tracking-tight ${text}`}>
        <span className="sr-only">{BRAND}</span>
        <span aria-hidden="true">
          <span className="relative inline-block">
            V
            <span className="absolute inset-x-0 -bottom-[0.12em] h-[0.09em] min-h-[2px] rounded-full bg-accent" />
          </span>
          ale
        </span>
      </span>
    </span>
  )
}

export default Logo
