import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { CalendarPlus, Check, Plus, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import PageHeader from '../components/PageHeader'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import Alert from '../components/Alert'
import { buildQuery, formatDate, formatDateTime, humanize } from '../lib/format'

const EMPTY = {
  leave_type: 'ANNUAL',
  start_date: new Date().toISOString().slice(0, 10),
  end_date: new Date().toISOString().slice(0, 10),
  reason: '',
}

export default function Leave() {
  const { role, user } = useAuth()
  const location = useLocation()
  const params = useMemo(() => new URLSearchParams(location.search), [location.search])
  const [status, setStatus] = useState(params.get('status') || '')
  const [leaveType, setLeaveType] = useState('')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(params.get('new') === '1')
  const [form, setForm] = useState(EMPTY)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [decision, setDecision] = useState(null)
  const [comment, setComment] = useState('')
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')

  const query = buildQuery({ page, page_size: 20, status, leave_type: leaveType })
  const { data, loading, error, reload } = useApi(`/leaves${query}`)

  useEffect(() => {
    if (params.get('new') === '1') setOpen(true)
  }, [params])

  const canDecide = ['ADMIN', 'HR', 'MANAGER'].includes(role)

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post('/leaves', { ...form, employee_id: null })
      setOpen(false)
      setForm(EMPTY)
      setNotice('Leave request submitted for approval.')
      reload()
    } catch (err) {
      setFormError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function decide() {
    if (!decision) return
    setActionError('')
    try {
      const path = `/leaves/${decision.leave.leave_id}/${decision.action}`
      await api.put(path, { comment: comment || null })
      setDecision(null)
      setComment('')
      setNotice(`Leave ${decision.action === 'approve' ? 'approved' : 'rejected'} successfully.`)
      reload()
    } catch (err) {
      setActionError(apiErrorMessage(err))
    }
  }

  async function cancel(leave) {
    if (!window.confirm(`Cancel leave request ${leave.leave_id}?`)) return
    try {
      await api.put(`/leaves/${leave.leave_id}/cancel`, { comment: 'Cancelled from UI' })
      setNotice('Leave request cancelled.')
      reload()
    } catch (err) {
      setActionError(apiErrorMessage(err))
    }
  }

  const columns = [
    {
      key: 'employee',
      label: 'Employee',
      render: (row) => (
        <div>
          <p className="font-semibold text-slate-800">{row.employee_name}</p>
          <p className="text-xs text-slate-500">{row.employee_id} · {row.team_id}</p>
        </div>
      ),
    },
    { key: 'leave_type', label: 'Type', render: (row) => <Badge tone="slate">{humanize(row.leave_type)}</Badge> },
    {
      key: 'dates',
      label: 'Dates',
      render: (row) => (
        <span className="text-xs text-slate-600">
          {formatDate(row.start_date)} → {formatDate(row.end_date)}
          <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 font-semibold text-slate-600">{row.total_days}d</span>
        </span>
      ),
    },
    { key: 'reason', label: 'Reason', render: (row) => <span className="block max-w-[220px] truncate text-xs text-slate-500">{row.reason}</span> },
    { key: 'submitted_at', label: 'Submitted', render: (row) => <span className="text-xs text-slate-500">{formatDateTime(row.submitted_at)}</span> },
    { key: 'status', label: 'Status', render: (row) => <Badge status={row.status}>{humanize(row.status)}</Badge> },
    {
      key: 'actions',
      label: 'Actions',
      render: (row) => {
        const isOwn = row.employee_id === user?.employee_id
        const canApprove = canDecide && row.status === 'PENDING'
        return (
          <div className="flex flex-wrap gap-1.5">
            {canApprove && (
              <>
                <button className="btn-ghost px-2 py-1 text-xs text-emerald-700" onClick={() => { setDecision({ leave: row, action: 'approve' }); setComment(''); setActionError('') }}>
                  <Check size={13} /> Approve
                </button>
                <button className="btn-ghost px-2 py-1 text-xs text-rose-700" onClick={() => { setDecision({ leave: row, action: 'reject' }); setComment(''); setActionError('') }}>
                  <X size={13} /> Reject
                </button>
              </>
            )}
            {isOwn && ['PENDING', 'APPROVED'].includes(row.status) && (
              <button className="btn-ghost px-2 py-1 text-xs text-slate-500" onClick={() => cancel(row)}>Cancel</button>
            )}
            {!canApprove && !isOwn && <span className="text-xs text-slate-400">—</span>}
          </div>
        )
      },
    },
  ]

  return (
    <div>
      <PageHeader
        title="Leave management"
        subtitle="Submit, review and decide leave with approval history and assignment-impact checks."
        actions={
          <button className="btn-primary" onClick={() => { setForm(EMPTY); setFormError(''); setOpen(true) }}>
            <Plus size={16} /> Request leave
          </button>
        }
      />

      {notice && <Alert tone="success" className="mb-4">{notice}</Alert>}
      {actionError && <Alert tone="error" className="mb-4">{actionError}</Alert>}
      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <div className="mb-4 flex flex-wrap gap-3">
        <select className="input w-auto min-w-40" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
          <option value="">All statuses</option>
          {['PENDING', 'APPROVED', 'REJECTED', 'CANCELLED'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
        <select className="input w-auto min-w-40" value={leaveType} onChange={(e) => { setLeaveType(e.target.value); setPage(1) }}>
          <option value="">All leave types</option>
          {['ANNUAL', 'SICK', 'UNPAID', 'PARENTAL', 'BEREAVEMENT'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          <CalendarPlus size={14} /> {data?.total ?? 0} requests
        </div>
      </div>

      <DataTable columns={columns} rows={data?.items || []} loading={loading} page={data?.page || page} pages={data?.pages || 1} total={data?.total || 0} onPage={setPage} rowKey={(row) => row.leave_id} emptyMessage="No leave requests match these filters." />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Request leave"
        subtitle="Working days are calculated automatically, excluding weekends and public holidays."
        footer={
          <div className="flex justify-end gap-2">
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" type="submit" form="leave-form" disabled={saving}>{saving ? 'Submitting…' : 'Submit request'}</button>
          </div>
        }
      >
        <form id="leave-form" onSubmit={submit} className="space-y-4">
          {formError && <Alert tone="error">{formError}</Alert>}
          <div>
            <label className="label">Leave type</label>
            <select className="input" value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })}>
              {['ANNUAL', 'SICK', 'UNPAID', 'PARENTAL', 'BEREAVEMENT'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
            </select>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className="label">Start date</label><input type="date" className="input" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value, end_date: e.target.value > form.end_date ? e.target.value : form.end_date })} /></div>
            <div><label className="label">End date</label><input type="date" className="input" required min={form.start_date} value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></div>
          </div>
          <div><label className="label">Reason</label><textarea className="input min-h-28" required minLength={3} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="Add context for your manager…" /></div>
          <p className="text-xs text-slate-500">Annual leave is checked against your balance; overlapping requests and policy limits are enforced by the API.</p>
        </form>
      </Modal>

      <Modal
        open={Boolean(decision)}
        onClose={() => setDecision(null)}
        title={decision?.action === 'approve' ? 'Approve leave' : 'Reject leave'}
        subtitle={decision ? `${decision.leave.employee_name} · ${formatDate(decision.leave.start_date)} to ${formatDate(decision.leave.end_date)}` : ''}
        footer={
          <div className="flex justify-end gap-2">
            <button className="btn-secondary" onClick={() => setDecision(null)}>Cancel</button>
            <button className={decision?.action === 'approve' ? 'btn-primary' : 'btn-danger'} onClick={decide}>
              {decision?.action === 'approve' ? 'Approve request' : 'Reject request'}
            </button>
          </div>
        }
      >
        {actionError && <Alert tone="error" className="mb-3">{actionError}</Alert>}
        <label className="label">Manager comment {decision?.action === 'reject' ? '(required)' : '(optional)'}</label>
        <textarea className="input min-h-24" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Explain the decision…" />
        {decision?.action === 'approve' && (
          <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Approved leave blocks future assignments. Existing overlapping shifts are surfaced as a LEAVE_OVERLAP exception.
          </p>
        )}
      </Modal>
    </div>
  )
}
