import { useEffect, useState } from 'react'
import { CheckCircle2, Clock3, Plus, UserX } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import PageHeader from '../components/PageHeader'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import Alert from '../components/Alert'
import StatCard from '../components/StatCard'
import { buildQuery, formatDate, formatDateTime, formatNumber, humanize, toISODate } from '../lib/format'

function localInput(value) {
  const date = new Date(value)
  const offset = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export default function Attendance() {
  const { role } = useAuth()
  const today = new Date()
  const [start, setStart] = useState(toISODate(new Date(today.getTime() - 14 * 86400000)))
  const [end, setEnd] = useState(toISODate(today))
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ assignment_id: '', check_in: '', check_out: '', source: 'MANUAL', notes: '' })
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')

  const query = buildQuery({ page, page_size: 20, start, end, status })
  const { data, loading, error, reload } = useApi(`/attendance${query}`)
  const assignments = useApi(open ? `/scheduling/assignments?start=${toISODate(new Date(today.getTime() - 21 * 86400000))}&end=${toISODate(new Date(today.getTime() + 7 * 86400000))}&page_size=200` : null)

  useEffect(() => {
    if (!open) return
    const first = assignments.data?.items?.[0]
    if (first) chooseAssignment(first.assignment_id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, assignments.data])

  function chooseAssignment(assignmentId) {
    const assignment = (assignments.data?.items || []).find((row) => row.assignment_id === assignmentId)
    setForm((current) => ({
      ...current,
      assignment_id: assignmentId,
      check_in: assignment ? localInput(assignment.start_at) : '',
      check_out: assignment ? localInput(assignment.end_at) : '',
    }))
  }

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post('/attendance', {
        assignment_id: form.assignment_id,
        check_in: form.check_in || null,
        check_out: form.check_out || null,
        source: form.source,
        notes: form.notes || null,
      })
      setOpen(false)
      setNotice('Attendance recorded and reconciled against the assignment.')
      reload()
    } catch (err) {
      setFormError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const rows = data?.items || []
  const absent = rows.filter((row) => ['ABSENT', 'NO_SHOW'].includes(row.status)).length
  const late = rows.filter((row) => row.status === 'LATE').length
  const overtime = rows.reduce((sum, row) => sum + Number(row.overtime_hours || 0), 0)

  const columns = [
    {
      key: 'employee',
      label: 'Employee',
      render: (row) => (
        <div>
          <p className="font-semibold text-slate-800">{row.employee_name}</p>
          <p className="text-xs text-slate-500">{row.employee_id}</p>
        </div>
      ),
    },
    { key: 'shift_date', label: 'Shift date', render: (row) => <span className="text-xs text-slate-600">{formatDate(row.shift_date)}</span> },
    {
      key: 'scheduled',
      label: 'Scheduled',
      render: (row) => (
        <span className="text-xs text-slate-600">
          {new Date(row.scheduled_start).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} –{' '}
          {new Date(row.scheduled_end).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
        </span>
      ),
    },
    {
      key: 'actual',
      label: 'Actual',
      render: (row) => (
        <span className="text-xs text-slate-600">
          {row.actual_check_in ? formatDateTime(row.actual_check_in) : '—'}
          <span className="block text-slate-400">{row.actual_check_out ? `→ ${formatDateTime(row.actual_check_out)}` : 'No checkout'}</span>
        </span>
      ),
    },
    { key: 'actual_hours', label: 'Hours', render: (row) => <span className="text-sm font-medium">{formatNumber(row.actual_hours, 2)}</span> },
    { key: 'overtime_hours', label: 'OT', render: (row) => <span className={`text-sm ${row.overtime_hours > 0 ? 'font-semibold text-amber-700' : 'text-slate-400'}`}>{formatNumber(row.overtime_hours, 2)}h</span> },
    { key: 'late_minutes', label: 'Late', render: (row) => <span className={`text-xs ${row.late_minutes > 5 ? 'font-semibold text-orange-600' : 'text-slate-400'}`}>{row.late_minutes ? `${row.late_minutes}m` : '—'}</span> },
    { key: 'status', label: 'Status', render: (row) => <Badge status={row.status}>{humanize(row.status)}</Badge> },
    { key: 'reconciliation_status', label: 'Reconciled', render: (row) => <Badge tone={row.reconciliation_status === 'MATCHED' ? 'green' : 'red'}>{humanize(row.reconciliation_status)}</Badge> },
  ]

  return (
    <div>
      <PageHeader
        title="Attendance"
        subtitle="Scheduled vs actual check-in/out, late arrivals, absences and derived overtime."
        actions={<button className="btn-primary" onClick={() => { setForm({ assignment_id: '', check_in: '', check_out: '', source: 'MANUAL', notes: '' }); setFormError(''); setOpen(true) }}><Plus size={16} /> Record attendance</button>}
      />
      {notice && <Alert tone="success" className="mb-4">{notice}</Alert>}
      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Events on page" value={rows.length} icon={CheckCircle2} tone="brand" />
        <StatCard label="Late arrivals" value={late} hint={`${absent} absences`} icon={Clock3} tone="orange" />
        <StatCard label="Overtime on page" value={formatNumber(overtime, 1)} suffix="h" icon={UserX} tone="amber" />
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div><label className="label">From</label><input type="date" className="input" value={start} onChange={(e) => { setStart(e.target.value); setPage(1) }} /></div>
        <div><label className="label">To</label><input type="date" className="input" value={end} onChange={(e) => { setEnd(e.target.value); setPage(1) }} /></div>
        <div>
          <label className="label">Status</label>
          <select className="input min-w-40" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
            <option value="">All statuses</option>
            {['PRESENT', 'LATE', 'ABSENT', 'EARLY_DEPARTURE', 'NO_SHOW'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
          </select>
        </div>
      </div>

      <DataTable columns={columns} rows={rows} loading={loading} page={data?.page || page} pages={data?.pages || 1} total={data?.total || 0} onPage={setPage} rowKey={(row) => row.attendance_id} emptyMessage="No attendance events in this period." />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Record attendance"
        subtitle="Attendance must reference an active shift assignment; hours and overtime are computed by the API."
        footer={
          <div className="flex justify-end gap-2">
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" form="attendance-form" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save attendance'}</button>
          </div>
        }
      >
        <form id="attendance-form" onSubmit={submit} className="space-y-4">
          {formError && <Alert tone="error">{formError}</Alert>}
          <div>
            <label className="label">Assignment</label>
            <select className="input" required value={form.assignment_id} onChange={(e) => chooseAssignment(e.target.value)}>
              <option value="">Select an assignment</option>
              {(assignments.data?.items || []).map((row) => (
                <option key={row.assignment_id} value={row.assignment_id}>
                  {formatDate(row.shift_date)} · {row.template_code} · {row.employee_name} ({row.assignment_id})
                </option>
              ))}
            </select>
            {assignments.data?.items?.length === 0 && <p className="mt-1 text-xs text-amber-700">No assignments available in the window.</p>}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className="label">Check-in</label><input type="datetime-local" className="input" value={form.check_in} onChange={(e) => setForm({ ...form, check_in: e.target.value })} /></div>
            <div><label className="label">Check-out</label><input type="datetime-local" className="input" value={form.check_out} onChange={(e) => setForm({ ...form, check_out: e.target.value })} /></div>
          </div>
          <div>
            <label className="label">Source</label>
            <select className="input" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}>
              {['MANUAL', 'BIOMETRIC', 'MOBILE'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
            </select>
          </div>
          <div><label className="label">Notes</label><textarea className="input min-h-20" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
        </form>
      </Modal>
    </div>
  )
}
