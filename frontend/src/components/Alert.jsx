import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import { cn } from '../lib/format'

const STYLES = {
  error: { wrap: 'border-rose-200 bg-rose-50 text-rose-800', icon: XCircle },
  success: { wrap: 'border-emerald-200 bg-emerald-50 text-emerald-800', icon: CheckCircle2 },
  warning: { wrap: 'border-amber-200 bg-amber-50 text-amber-800', icon: AlertTriangle },
  info: { wrap: 'border-sky-200 bg-sky-50 text-sky-800', icon: Info },
}

export default function Alert({ tone = 'info', title, children, className = '' }) {
  const style = STYLES[tone] || STYLES.info
  const Icon = style.icon
  return (
    <div className={cn('flex items-start gap-3 rounded-lg border px-4 py-3 text-sm', style.wrap, className)}>
      <Icon size={18} className="mt-0.5 shrink-0" />
      <div>
        {title && <p className="font-semibold">{title}</p>}
        <div className={title ? 'mt-0.5' : ''}>{children}</div>
      </div>
    </div>
  )
}
