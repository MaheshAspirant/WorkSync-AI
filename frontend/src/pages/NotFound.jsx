import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <span className="rounded-full bg-slate-100 p-4 text-slate-500"><Compass size={28} /></span>
      <h1 className="mt-4 text-2xl font-bold text-slate-900">Page not found</h1>
      <p className="mt-1 text-sm text-slate-500">The page you requested does not exist in this workspace.</p>
      <Link to="/" className="btn-primary mt-5">Back to dashboard</Link>
    </div>
  )
}
