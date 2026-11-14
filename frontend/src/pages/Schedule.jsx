import { useEffect, useMemo, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight, Play, Users, Wand2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import PageHeader from '../components/PageHeader'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import Alert from '../components/Alert'
import { LoadingSpinner } from '../components/Loading'
import { addDays, buildQuery, formatDate, formatShortDate, startOfWeek, toISODate } from '../lib/format'

const CODES = ['A', 'B', 'C']
const CODE_STYLE = {
  A: 'border-amber-200 bg-amber-50/70 text-amber-900',
  B: 'border-sky-200 bg-sky-50/70 text-sky-900',
  C: 'border-violet-200 bg-violet-50/70 text-violet-900',
}

export default function Schedule() {
  const { role } = useAuth()
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()))
  const [teamId, setTeamId] = useState('')
  const [generateOpen, setGenerateOpen] = useState(false)
  const [run, setRun] = useState(null)
  const [form, setForm] = useState({ replace_existing: false, use_preferences: true, use_fairness: true, time_limit_seconds: 8 })
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState('')
  const [selected, setSelected] = useState(null)

  const teams = useApi('/teams?page_size=200')
  const weekEnd = addDays(weekStart, 6)
  const start = toISODate(weekStart)
  const end = toISODate(weekEnd)

  useEffect(() => {
    if (!teamId && teams.data?.items?.length) setTeamId(teams.data.items[0].team_id)
  }, [teams.data, teamId])

  const query = buildQuery({ start, end, team_id: teamId || undefined, page_size: 200 })
  const shifts = useApi(teamId || role === 'EMPLOYEE' ? `/scheduling/shifts${query}` : null)
  const assignments = useApi(teamId || role === 'EMPLOYEE' ? `/scheduling/assignments${query}` : null)

  const byShift = useMemo(() => {
    const map = {}
    for (const assignment of assignments.data?.items || []) {
      if (!map[assignment.shift_id]) map[assignment.shift_id] = []
      map[assignment.shift_id].push(assignment)
    }
    return map
  }, [assignments.data])

  const days = useMemo(
    () => Array.from({ length: 7 }).map((_, index) => addDays(weekStart, index)),
    [weekStart],
  )
  const shiftsByDate = useMemo(() => {
    const map = {}
    for (const shift of shifts.data?.items || []) {
      if (!map[shift.shift_date]) map[shift.shift_date] = []
      map[shift.shift_date].push(shift)
    }
    Object.values(map).forEach((rows) => rows.sort((a, b) => a.template_code.localeCompare(b.template_code)))
    return map
  }, [shifts.data])

  const teamName = teams.data?.items?.find((team) => team.team_id === teamId)?.name
  const isManager = ['ADMIN', 'HR', 'MANAGER'].includes(role)

  function openGenerate() {
    setForm({
      replace_existing: false,
      use_preferences: true,
      use_fairness: true,
      time_limit_seconds: 8,
    })
    setGenerateError('')
    setGenerateOpen(true)
  }

  async function generate() {
    setGenerating(true)
    setGenerateError('')
    try {
      const response = await api.post('/scheduling/generate', {
        team_id: teamId,
        start_date: start,
        end_date: end,
        replace_existing: form.replace_existing,
        use_preferences: form.use_preferences,
        use_fairness: form.use_fairness,
        time_limit_seconds: Number(form.time_limit_seconds),
      })
      setRun(response.data)
      setGenerateOpen(false)
      shifts.reload()
      assignments.reload()
    } catch (err) {
      setGenerateError(apiErrorMessage(err))
    } finally {
      setGenerating(false)
    }
  }

  const loading = shifts.loading || assignments.loading
  const error = shifts.error || assignments.error

  return (
    <div>
      <PageHeader
        title="Shift schedule"
        subtitle="Weekly roster with coverage status. Generate an optimized plan or inspect assignment-level explanations."
        actions={
          <>
            {isManager && (
              <select className="input w-auto min-w-52" value={teamId} onChange={(event) => setTeamId(event.target.value)}>
                {(teams.data?.items || []).map((team) => (
                  <option key={team.team_id} value={team.team_id}>{team.name}</option>
                ))}
              </select>
            )}
            {isManager && (
              <button className="btn-primary" onClick={openGenerate} disabled={!teamId}>
                <Wand2 size={16} /> Generate schedule
              </button>
            )}
          </>
        }
      />

      {run && (
        <div className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
          <div className="flex flex-wrap items-center gap-3">
            <Badge tone={run.coverage_gaps ? 'amber' : 'green'}>{run.status}</Badge>
            <p className="text-sm font-semibold text-slate-800">{run.run_id} · {run.message}</p>
            <button className="btn-ghost ml-auto px-2 py-1 text-xs" onClick={() => setRun(null)}>Dismiss</button>
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-600">
            <span><strong>{run.assignments_created}</strong> assignments</span>
            <span><strong>{run.coverage_gaps}</strong> coverage gaps</span>
            <span>Solver: <strong>{run.solver_status}</strong></span>
            <span>Duration: <strong>{run.duration_seconds}s</strong></span>
            <span>Soft score: <strong>{run.soft_score ?? '—'}</strong></span>
          </div>
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button className="btn-secondary px-2.5" onClick={() => setWeekStart(addDays(weekStart, -7))} aria-label="Previous week"><ChevronLeft size={16} /></button>
        <button className="btn-secondary px-2.5" onClick={() => setWeekStart(startOfWeek(new Date()))}>Today</button>
        <button className="btn-secondary px-2.5" onClick={() => setWeekStart(addDays(weekStart, 7))} aria-label="Next week"><ChevronRight size={16} /></button>
        <div className="ml-1">
          <p className="text-sm font-semibold text-slate-800">{formatDate(start)} – {formatDate(end)}</p>
          <p className="text-xs text-slate-500">{teamName || 'My team'} · {shifts.data?.total ?? 0} shifts</p>
        </div>
        <div className="ml-auto flex items-center gap-3 text-[11px] text-slate-500">
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Covered</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> Understaffed</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-500" /> Unfilled</span>
        </div>
      </div>

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}
      {loading && !shifts.data ? (
        <LoadingSpinner label="Loading roster…" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-7">
          {days.map((day) => {
            const iso = toISODate(day)
            const isToday = iso === toISODate(new Date())
            const rows = shiftsByDate[iso] || []
            return (
              <div key={iso} className={`rounded-xl border bg-white shadow-card ${isToday ? 'border-brand-300 ring-1 ring-brand-200' : 'border-slate-200'}`}>
                <div className={`border-b px-3 py-2.5 ${isToday ? 'bg-brand-50/70' : 'bg-slate-50'}`}>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    {day.toLocaleDateString('en-IN', { weekday: 'short' })}
                  </p>
                  <p className="text-sm font-bold text-slate-800">{day.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</p>
                </div>
                <div className="space-y-2 p-2">
                  {rows.length === 0 && <p className="py-6 text-center text-[11px] text-slate-400">No shifts</p>}
                  {rows.map((shift) => {
                    const count = shift.assigned_count ?? 0
                    const tone = count >= shift.required_staff ? 'green' : count === 0 ? 'red' : 'amber'
                    return (
                      <button
                        type="button"
                        key={shift.shift_id}
                        onClick={() => setSelected(shift)}
                        className={`w-full rounded-lg border p-2 text-left transition hover:shadow-sm ${CODE_STYLE[shift.template_code] || 'border-slate-200 bg-white'}`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold uppercase tracking-wide">{shift.template_code} · {shift.template_name}</span>
                          <span className={`h-1.5 w-1.5 rounded-full ${tone === 'green' ? 'bg-emerald-500' : tone === 'red' ? 'bg-rose-500' : 'bg-amber-500'}`} />
                        </div>
                        <p className="mt-0.5 text-[10px] opacity-70">
                          {new Date(shift.start_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} –{' '}
                          {new Date(shift.end_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                        </p>
                        <p className="mt-1 inline-flex items-center gap-1 text-[10px] font-semibold">
                          <Users size={10} /> {count}/{shift.required_staff} staff
                        </p>
                      </button>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected ? `${selected.template_code} · ${selected.template_name}` : ''}
        subtitle={selected ? `${formatDate(selected.shift_date)} · ${selected.team_name}` : ''}
      >
        {selected && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg bg-slate-50 p-3"><p className="text-[10px] uppercase text-slate-500">Shift</p><p className="text-sm font-semibold">{selected.shift_id}</p></div>
              <div className="rounded-lg bg-slate-50 p-3"><p className="text-[10px] uppercase text-slate-500">Required</p><p className="text-sm font-semibold">{selected.required_staff}</p></div>
              <div className="rounded-lg bg-slate-50 p-3"><p className="text-[10px] uppercase text-slate-500">Assigned</p><p className="text-sm font-semibold">{selected.assigned_count}</p></div>
            </div>
            <div>
              <p className="label">Assigned employees</p>
              <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                {(byShift[selected.shift_id] || []).length === 0 && <p className="px-3 py-6 text-center text-xs text-slate-500">No active assignments.</p>}
                {(byShift[selected.shift_id] || []).map((assignment) => (
                  <div key={assignment.assignment_id} className="flex items-center justify-between px-3 py-2">
                    <div>
                      <p className="text-sm font-medium text-slate-800">{assignment.employee_name}</p>
                      <p className="text-[11px] text-slate-500">{assignment.employee_id} · {assignment.assignment_source}</p>
                    </div>
                    <Badge status={assignment.status}>{assignment.status}</Badge>
                  </div>
                ))}
              </div>
            </div>
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
              Coverage status: <strong>{selected.coverage_status}</strong>. Assignment reasons are recorded per scheduling run in the decision log.
            </p>
          </div>
        )}
      </Modal>

      <Modal
        open={generateOpen}
        onClose={() => setGenerateOpen(false)}
        title="Generate schedule"
        subtitle={`${formatDate(start)} – ${formatDate(end)} · ${teamName || ''}`}
        footer={
          <div className="flex justify-end gap-2">
            <button className="btn-secondary" onClick={() => setGenerateOpen(false)}>Cancel</button>
            <button className="btn-primary" onClick={generate} disabled={generating}>
              <Play size={15} /> {generating ? 'Solving…' : 'Run optimizer'}
            </button>
          </div>
        }
      >
        {generateError && <Alert tone="error" className="mb-3">{generateError}</Alert>}
        <div className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <p className="font-semibold text-slate-700">Hard constraints</p>
            <p className="mt-0.5">No overlaps, approved leave respected, skills held, rest and weekly-hour caps enforced. Coverage is reported as gaps when infeasible.</p>
          </div>
          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input type="checkbox" className="mt-0.5 h-4 w-4" checked={form.replace_existing} onChange={(e) => setForm({ ...form, replace_existing: e.target.checked })} />
            <span>Replace existing assignments in scope <span className="block text-xs text-slate-500">Old records are cancelled, never deleted.</span></span>
          </label>
          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input type="checkbox" className="mt-0.5 h-4 w-4" checked={form.use_preferences} onChange={(e) => setForm({ ...form, use_preferences: e.target.checked })} />
            <span>Respect shift preferences as a soft objective</span>
          </label>
          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input type="checkbox" className="mt-0.5 h-4 w-4" checked={form.use_fairness} onChange={(e) => setForm({ ...form, use_fairness: e.target.checked })} />
            <span>Balance morning / evening / night distribution</span>
          </label>
          <div>
            <label className="label">Solver time limit (seconds)</label>
            <input type="number" min="1" max="120" className="input max-w-40" value={form.time_limit_seconds} onChange={(e) => setForm({ ...form, time_limit_seconds: e.target.value })} />
          </div>
          <p className="flex items-center gap-2 text-xs text-slate-500"><CalendarDays size={13} /> The run, every assignment decision and any gap are persisted with audit trail.</p>
        </div>
      </Modal>
    </div>
  )
}
