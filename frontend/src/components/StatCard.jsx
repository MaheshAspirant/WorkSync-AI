import { cn } from '../lib/format'

const TONES = {
  brand: 'bg-brand-50 text-brand-700',
  green: 'bg-emerald-50 text-emerald-700',
  amber: 'bg-amber-50 text-amber-700',
  red: 'bg-rose-50 text-rose-700',
  sky: 'bg-sky-50 text-sky-700',
  violet: 'bg-violet-50 text-violet-700',
}

export default function StatCard({ label, value, hint, icon: Icon, tone = 'brand', suffix }) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 truncate text-2xl font-bold tracking-tight text-slate-900">
            {value}
            {suffix && <span className="ml-1 text-sm font-semibold text-slate-500">{suffix}</span>}
          </p>
          {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
        </div>
        {Icon && (
          <span className={cn('rounded-lg p-2.5', TONES[tone] || TONES.brand)}>
            <Icon size={20} />
          </span>
        )}
      </div>
    </div>
  )
}
