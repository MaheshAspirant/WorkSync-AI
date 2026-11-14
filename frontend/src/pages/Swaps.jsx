import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Check, Plus, Repeat2, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import PageHeader from '../components/PageHeader'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import Alert from '../components/Alert'
import { buildQuery, formatDate, humanize, toISODate } from '../lib/format'

const EMPTY = { requester_assignment_id: '', target_assignment_id: '', reason: '' }

export default function Swaps() {
  const { role, user } = useAuth()
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')

  const query = buildQuery({ page, page_size: 20, status })
  const swaps = useApi(`/swaps${query}`)
  const today = toISODate(new Date())
  const future = toISODate(new Date(Date.now() + 90 * 86400000))
  const candidates = useApi(open ? `/swaps/candidates?start=${today}&end=${future}` : null)

  useEffect(() => {
    if (!open) return
    const rows = candidates.data || []
    const own = rows.filter((row) => row.employee_id === user?.employee_id)
    setForm({
      requester_assignment_id: own[0]?.assignment_id || rows[0]?.assignment_id || '',
      target_assignment_id: '',
      reason: '',
    })
  }, [open, candidates.data, user?.employee_id])

  const allCandidates = candidates.data || []
  const ownCandidates = allCandidates.filter((row) => row.employee_id === user?.employee_id)
  const requesterPool = ownCandidates.length ? ownCandidates : allCandidates
  const selectedRequester = allCandidates.find((row) => row.assignment_id === form.requester_assignment_id)
  const targetPool = allCandidates.filter(
    (row) =>
      row.assignment_id !== form.requester_assignment_id &&
      row.employee_id !== selectedRequester?.employee_id &&
      row.shift_id !== selectedRequester?.shift_id,
  )

  const canDecide = ['ADMIN', 'HR', 'MANAGER'].includes(role)
  const isTarget = (swap) => swap.target_employee_id === user?.employee_id
  const isRequester = (swap) => swap.requester_employee_id === user?.employee_id

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post('/swaps', form)
      setOpen(false)
      setForm(EMPTY)
      setNotice('Swap request submitted. The target employee must agree before manager approval.')
      swaps.reload()
    } catch (err) {
      setFormError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function act(swap, action) {
    setActionError('')
    setNotice('')
    try {
      if (action === 'accept' || action === 'decline') {
        await api.put(`/swaps/${swap.swap_id}/target-response`, {
          agree: action === 'accept',
          comment: action === 'decline' ? window.prompt('Reason for declining (optional)') || null : null,
        })
        setNotice(action === 'accept' ? 'You agreed to the swap. Awaiting manager approval.' : 'Swap declined.')
      } else if (action === 'approve') {
        await api.put(`/swaps/${swap.swap_id}/approve?apply_immediately=true`, { comment: 'Approved from manager console' })
        setNotice('Swap approved and applied to the roster.')
      } else if (action === 'reject') {
        const comment = window.prompt('Rejection comment (required)')
        if (!comment) return
        await api.put(`/swaps/${swap.swap_id}/reject`, { comment })
        setNotice('Swap rejected.')
      } else if (action === 'apply') {
        await api.put(`/swaps/${swap.swap_id}/apply`, { comment: 'Applied from manager console' })
        setNotice('Swap applied.')
      } else if (action === 'cancel') {
        await api.put(`/swaps/${swap.swap_id}/cancel`, { comment: 'Withdrawn by requester' })
        setNotice('Swap request cancelled.')
      }
      swaps.reload()
    } catch (err) {
      setActionError(apiErrorMessage(err))
    }
  }

  const columns = [
    { key: 'swap_id', label: 'Swap', render: (row) => <span className="font-mono text-xs font-semibold text-slate-700">{row.swap_id}</span> },
    {
      key: 'people',
      label: 'Employees',
      render: (row) => (
        <div className="flex items-center gap-2 text-sm">
          <div><p className="font-semibold text-slate-800">{row.requester_name}</p><p className="text-[11px] text-slate-500">Requester</p></div>
          <ArrowRight size={14} className="text-slate-400" />
          <div><p className="font-semibold text-slate-800">{row.target_name}</p><p className="text-[11px] text-slate-500">Target</p></div>
        </div>
      ),
    },
    {
      key: 'shifts',
      label: 'Shifts',
      render: (row) => (
        <div className="text-xs text-slate-600">
          <p>{formatDate(row.requester_shift_date)} · {row.requester_shift_code}</p>
          <p className="text-slate-400">↔ {formatDate(row.target_shift_date)} · {row.target_shift_code}</p>
        </div>
      ),
    },
    {
      key: 'agreement',
      label: 'Agreement',
      render: (row) => (
        <div className="space-y-1">
          <Badge tone={row.requester_agreed ? 'green' : 'slate'}>Requester</Badge>
          <Badge tone={row.target_agreed ? 'green' : 'amber'}>{row.target_agreed ? 'Target agreed' : 'Awaiting target'}</Badge>
        </div>
      ),
    },
    { key: 'status', label: 'Status', render: (row) => <Badge status={row.status}>{humanize(row.status)}</Badge> },
    {
      key: 'actions',
      label: 'Actions',
      render: (row) => {
        const buttons = []
        if (row.status === 'REQUESTED' && isTarget(row)) {
          buttons.push(<button key="accept" className="btn-ghost px-2 py-1 text-xs text-emerald-700" onClick={() => act(row, 'accept')}><Check size={12} /> Agree</button>)
          buttons.push(<button key="decline" className="btn-ghost px-2 py-1 text-xs text-rose-700" onClick={() => act(row, 'decline')}><X size={12} /> Decline</button>)
        }
        if (canDecide && row.status === 'REQUESTED') {
          buttons.push(<button key="approve" className="btn-ghost px-2 py-1 text-xs text-emerald-700" onClick={() => act(row, 'approve')}><Check size={12} /> Approve</button>)
          buttons.push(<button key="reject" className="btn-ghost px-2 py-1 text-xs text-rose-700" onClick={() => act(row, 'reject')}><X size={12} /> Reject</button>)
        }
        if (canDecide && row.status === 'APPROVED') {
          buttons.push(<button key="apply" className="btn-ghost px-2 py-1 text-xs text-brand-700" onClick={() => act(row, 'apply')}>Apply</button>)
        }
        if (row.status === 'REQUESTED' && isRequester(row)) {
          buttons.push(<button key="cancel" className="btn-ghost px-2 py-1 text-xs text-slate-500" onClick={() => act(row, 'cancel')}>Cancel</button>)
        }
        return <div className="flex flex-wrap gap-1">{buttons.length ? buttons : <span className="text-xs text-slate-400">—</span>}</div>
      },
    },
  ]

  return (
    <div>
      <PageHeader
        title="Shift swaps"
        subtitle="Two-way agreement, skill and availability validation, manager approval, then an immutable applied-swap record."
        actions={<button className="btn-primary" onClick={() => { setForm(EMPTY); setFormError(''); setOpen(true) }}><Plus size={16} /> Request swap</button>}
      />
      {notice && <Alert tone="success" className="mb-4">{notice}</Alert>}
      {actionError && <Alert tone="error" className="mb-4">{actionError}</Alert>}
      {swaps.error && <Alert tone="error" className="mb-4">{swaps.error}</Alert>}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select className="input w-auto min-w-40" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
          <option value="">All statuses</option>
          {['REQUESTED', 'APPROVED', 'APPLIED', 'REJECTED', 'CANCELLED'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
        <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-slate-500"><Repeat2 size={14} /> {swaps.data?.total ?? 0} swap requests</span>
      </div>

      <DataTable columns={columns} rows={swaps.data?.items || []} loading={swaps.loading} page={swaps.data?.page || page} pages={swaps.data?.pages || 1} total={swaps.data?.total || 0} onPage={setPage} rowKey={(row) => row.swap_id} emptyMessage="No swap requests found." />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Request a shift swap"
        subtitle="Pick your assignment and a colleague's assignment. The target must agree; a manager approves before the roster changes."
        size="lg"
        footer={
          <div className="flex justify-end gap-2">
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" type="submit" form="swap-form" disabled={saving}>{saving ? 'Submitting…' : 'Submit request'}</button>
          </div>
        }
      >
        <form id="swap-form" onSubmit={submit} className="space-y-4">
          {formError && <Alert tone="error">{formError}</Alert>}
          <div>
            <label className="label">Your assignment</label>
            <select className="input" required value={form.requester_assignment_id} onChange={(e) => setForm({ ...form, requester_assignment_id: e.target.value, target_assignment_id: '' })}>
              <option value="">Select an assignment</option>
              {requesterPool.map((row) => (
                <option key={row.assignment_id} value={row.assignment_id}>
                  {formatDate(row.shift_date)} · {row.template_code} · {row.employee_name} ({row.assignment_id})
                </option>
              ))}
            </select>
            {requesterPool.length === 0 && <p className="mt-1 text-xs text-amber-700">No eligible assignments found in the next 90 days.</p>}
          </div>
          <div>
            <label className="label">Target assignment</label>
            <select className="input" required value={form.target_assignment_id} onChange={(e) => setForm({ ...form, target_assignment_id: e.target.value })}>
              <option value="">Select a colleague's assignment</option>
              {targetPool.map((row) => (
                <option key={row.assignment_id} value={row.assignment_id}>
                  {formatDate(row.shift_date)} · {row.template_code} · {row.employee_name} ({row.assignment_id})
                </option>
              ))}
            </select>
          </div>
          <div><label className="label">Reason</label><textarea className="input min-h-24" required value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="Why do you need this swap?" /></div>
          <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
            The API validates skill compatibility, availability, leave, weekly hours and rest for both employees before approval.
          </p>
        </form>
      </Modal>
    </div>
  )
}
