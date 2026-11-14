import { cn, statusTone } from '../lib/format'

const TONES = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-700 ring-amber-200',
  red: 'bg-rose-50 text-rose-700 ring-rose-200',
  orange: 'bg-orange-50 text-orange-700 ring-orange-200',
  blue: 'bg-sky-50 text-sky-700 ring-sky-200',
  slate: 'bg-slate-100 text-slate-600 ring-slate-200',
  purple: 'bg-violet-50 text-violet-700 ring-violet-200',
}

export default function Badge({ children, tone, status, className = '' }) {
  const finalTone = tone || statusTone(status ?? children)
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset',
        TONES[finalTone] || TONES.slate,
        className,
      )}
    >
      {children}
    </span>
  )
}
