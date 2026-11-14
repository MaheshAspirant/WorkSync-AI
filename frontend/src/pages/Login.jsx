import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, CalendarDays, Lock, ShieldCheck, Sparkles, User } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { apiErrorMessage } from '../services/api'

const DEMOS = [
  { label: 'Administrator', username: 'admin', password: 'Admin@123' },
  { label: 'Manager', username: 'manager', password: 'Manager@123' },
  { label: 'HR Partner', username: 'hr', password: 'Hr@12345' },
  { label: 'Employee', username: 'employee', password: 'Employee@123' },
]

export default function Login() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isAuthenticated) navigate('/', { replace: true })
  }, [isAuthenticated, navigate])

  async function submit(event) {
    event?.preventDefault()
    setLoading(true)
    setError('')
    try {
      await login(form.username.trim(), form.password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  function quickLogin(demo) {
    setForm({ username: demo.username, password: demo.password })
    setError('')
  }

  return (
    <div className="grid min-h-screen bg-slate-950 lg:grid-cols-2">
      <div className="relative hidden overflow-hidden p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(99,102,241,0.35),transparent_45%),radial-gradient(circle_at_80%_80%,rgba(14,165,233,0.25),transparent_45%)]" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500 text-white shadow-xl shadow-brand-900/40">
              <CalendarDays size={22} />
            </span>
            <div>
              <p className="text-lg font-bold text-white">WorkSync AI</p>
              <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Workforce OS</p>
            </div>
          </div>
          <h1 className="mt-16 max-w-lg text-4xl font-bold leading-tight tracking-tight text-white">
            Fair, feasible schedules. Every shift, every team.
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-400">
            Combine leave, skills, availability and labour rules into one explainable schedule —
            then track coverage, overtime and exceptions with a complete audit trail.
          </p>
          <div className="mt-10 grid max-w-md gap-3">
            {[
              ['OR-Tools optimization', 'Hard constraints never silently violated'],
              ['Explainable decisions', 'Every assignment has a recorded reason'],
              ['Auditable workflows', 'Leave, swaps and changes preserve history'],
            ].map(([title, body]) => (
              <div key={title} className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3">
                <Sparkles size={16} className="mt-0.5 text-brand-300" />
                <div>
                  <p className="text-sm font-semibold text-white">{title}</p>
                  <p className="text-xs text-slate-400">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-slate-600">
          Synthetic data only · Fixed seed 20261022 · Three-tier architecture
        </p>
      </div>

      <div className="flex items-center justify-center bg-slate-50 px-5 py-12 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white">
              <CalendarDays size={20} />
            </span>
            <div>
              <p className="text-lg font-bold text-slate-900">WorkSync AI</p>
              <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Workforce OS</p>
            </div>
          </div>

          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Sign in to your workspace</h2>
          <p className="mt-1 text-sm text-slate-500">Use your role-based account to continue.</p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            <div>
              <label className="label" htmlFor="username">Username</label>
              <div className="relative">
                <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  id="username"
                  className="input pl-9"
                  value={form.username}
                  onChange={(event) => setForm({ ...form, username: event.target.value })}
                  placeholder="admin"
                  autoComplete="username"
                  required
                />
              </div>
            </div>
            <div>
              <label className="label" htmlFor="password">Password</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  id="password"
                  type="password"
                  className="input pl-9"
                  value={form.password}
                  onChange={(event) => setForm({ ...form, password: event.target.value })}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                />
              </div>
            </div>
            {error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            )}
            <button type="submit" className="btn-primary w-full py-2.5" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
              {!loading && <ArrowRight size={16} />}
            </button>
          </form>

          <div className="mt-7 rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <ShieldCheck size={14} /> Demo accounts
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {DEMOS.map((demo) => (
                <button
                  key={demo.username}
                  type="button"
                  onClick={() => quickLogin(demo)}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-left text-xs transition hover:border-brand-300 hover:bg-brand-50/50"
                >
                  <span className="block font-semibold text-slate-800">{demo.label}</span>
                  <span className="text-slate-500">{demo.username}</span>
                </button>
              ))}
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-slate-400">
              Demo passwords are documented in the README. Accounts are seeded on first startup.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
