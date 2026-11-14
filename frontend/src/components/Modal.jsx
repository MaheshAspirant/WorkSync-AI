import { X } from 'lucide-react'
import { useEffect } from 'react'

export default function Modal({ open, title, subtitle, onClose, children, footer, size = 'md' }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => event.key === 'Escape' && onClose?.()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  if (!open) return null
  const widths = { sm: 'max-w-md', md: 'max-w-xl', lg: 'max-w-3xl', xl: 'max-w-5xl' }
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/50 p-0 backdrop-blur-sm sm:items-center sm:p-6">
      <div
        className={`w-full ${widths[size] || widths.md} max-h-[92vh] overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl`}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
            {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
          </div>
          <button type="button" onClick={onClose} className="btn-ghost -mr-2 p-1.5" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="max-h-[65vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="border-t border-slate-200 bg-slate-50 px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}
