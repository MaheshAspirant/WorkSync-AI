import { Loader2 } from 'lucide-react'

export function LoadingSpinner({ label = 'Loading…', className = '' }) {
  return (
    <div className={`flex items-center justify-center gap-2 py-12 text-sm text-slate-500 ${className}`}>
      <Loader2 size={18} className="animate-spin" />
      {label}
    </div>
  )
}

export function PageLoader() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <LoadingSpinner label="Loading WorkSync AI…" />
    </div>
  )
}

export function EmptyState({ title = 'Nothing here yet', description, action, icon: Icon }) {
  return (
    <div className="card flex flex-col items-center justify-center px-6 py-14 text-center">
      {Icon && (
        <span className="mb-3 rounded-full bg-slate-100 p-3 text-slate-500">
          <Icon size={22} />
        </span>
      )}
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
