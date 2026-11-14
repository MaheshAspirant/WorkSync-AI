import { useState } from 'react'
import { AlertOctagon, CheckCircle2, RefreshCw, ShieldAlert } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import PageHeader from '../components/PageHeader'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import Alert from '../components/Alert'
import StatCard from '../components/StatCard'
import Modal from '../components/Modal'
import { buildQuery, formatDate, formatDateTime, humanize } from '../lib/format'

export default function Exceptions() {
  const { role } = useAuth()
  const [issueType, setIssueType] = useState('')
  const [resolution, setResolution] = useState('')
  const [severity, setSeverity] = useState('')
  const [page, setPage] = useState(1)
  const [detecting, setDetecting] = useState(false)
  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState('')
  const [resolving, setResolving] = useState(null)
  const [resolveForm, setResolveForm] = useState({ resolution_status: 'RESOLVED', note: '' })

  const query = buildQuery({ page, page_size: 20, issue_type: issueType, resolution_status: resolution, severity })
  const { data, loading, error, reload } = useApi(`/exceptions${query}`)
  const canAct = ['ADMIN', 'HR', 'MANAGER'].includes(role)
  const summary = useApi(canAct ? '/exceptions/summary' : null)

  async function detect() {
    setDetecting(true)
    setActionError('')
    setNotice('')
    try {
      const response = await api.post('/exceptions/detect')
      setNotice(`Detection complete: ${response.data.detected} findings (${response.data.new} new, ${response.data.updated} refreshed).`)
      reload()
      summary.reload()
    } catch (err) {
      setActionError(apiErrorMessage(err))
    } finally {
      setDetecting(false)
    }
  }

  async function resolve() {
    if (!resolving) return
    try {
      await api.put(`/exceptions/${resolving.issue_id}/resolve`, resolveForm)
      setResolving(null)
      setResolveForm({ resolution_status: 'RESOLVED', note: '' })
      setNotice('Exception updated and audit-logged.')
      reload()
      summary.reload()
    } catch (err) {
      setActionError(apiErrorMessage(err))
    }
  }

  const counts = Object.fromEntries((summary.data?.by_type || []).map((row) => [row.issue_type, row.count]))
  const openCount = (summary.data?.by_status || []).find((row) => row.resolution_status === 'OPEN')?.count || 0

  const columns = [
    { key: 'issue_id', label: 'Issue', render: (row) => <span className="font-mono text-[11px] font-semibold text-slate-700">{row.issue_id}</span> },
    { key: 'issue_type', label: 'Type', render: (row) => <Badge tone="red">{humanize(row.issue_type)}</Badge> },
    {
      key: 'affected',
      label: 'Affected record',
      render: (row) => (
        <div className="text-xs">
          <p className="font-semibold text-slate-700">{row.employee_name || row.shift_id || row.transaction_id || '—'}</p>
          <p className="text-slate-500">{row.employee_id || row.shift_id || ''} {row.transaction_id ? `· ${row.transaction_id}` : ''}</p>
        </div>
      ),
    },
    { key: 'description', label: 'Description', render: (row) => <span className="block max-w-md text-xs leading-relaxed text-slate-600">{row.description}</span> },
    { key: 'severity', label: 'Severity', render: (row) => <Badge status={row.severity}>{row.severity}</Badge> },
    { key: 'resolution_status', label: 'Status', render: (row) => <Badge status={row.resolution_status}>{humanize(row.resolution_status)}</Badge> },
    { key: 'detected_at', label: 'Detected', render: (row) => <span className="text-[11px] text-slate-500">{formatDateTime(row.detected_at)}</span> },
    {
      key: 'actions',
      label: 'Actions',
      render: (row) => canAct ? (
        <button className="btn-ghost px-2 py-1 text-xs text-brand-700" onClick={() => { setResolving(row); setResolveForm({ resolution_status: row.resolution_status === 'OPEN' ? 'RESOLVED' : 'ACKNOWLEDGED', note: row.resolution_note || '' }) }}>
          Review
        </button>
      ) : <span className="text-xs text-slate-400">—</span>,
    },
  ]

  return (
    <div>
      <PageHeader
        title="Conflicts & exceptions"
        subtitle="Detected rule violations with affected entities, severity, detection timestamp and resolution trail."
        actions={canAct && (
          <button className="btn-primary" onClick={detect} disabled={detecting}>
            <RefreshCw size={16} className={detecting ? 'animate-spin' : ''} /> {detecting ? 'Detecting…' : 'Run detection'}
          </button>
        )}
      />
      {notice && <Alert tone="success" className="mb-4">{notice}</Alert>}
      {(actionError || error) && <Alert tone="error" className="mb-4">{actionError || error}</Alert>}

      <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Open exceptions" value={openCount} icon={ShieldAlert} tone="red" />
        <StatCard label="Double bookings" value={counts.DOUBLE_BOOKING || 0} icon={AlertOctagon} tone="orange" />
        <StatCard label="Missing skills" value={counts.MISSING_SKILL || 0} icon={AlertOctagon} tone="amber" />
        <StatCard label="Overtime caps" value={counts.OVERTIME_CAP || 0} icon={CheckCircle2} tone="brand" />
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <select className="input w-auto min-w-44" value={issueType} onChange={(e) => { setIssueType(e.target.value); setPage(1) }}>
          <option value="">All issue types</option>
          {['DOUBLE_BOOKING', 'LEAVE_OVERLAP', 'MISSING_SKILL', 'OVERTIME_CAP', 'UNAPPROVED_SWAP', 'COVERAGE_GAP', 'REST_VIOLATION', 'HOURS_CAP'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
        <select className="input w-auto min-w-40" value={resolution} onChange={(e) => { setResolution(e.target.value); setPage(1) }}>
          <option value="">All statuses</option>
          {['OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'IGNORED'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
        <select className="input w-auto min-w-40" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1) }}>
          <option value="">All severities</option>
          {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
      </div>

      <DataTable columns={columns} rows={data?.items || []} loading={loading} page={data?.page || page} pages={data?.pages || 1} total={data?.total || 0} onPage={setPage} rowKey={(row) => row.issue_id} emptyMessage="No exceptions match these filters." />

      <Modal
        open={Boolean(resolving)}
        onClose={() => setResolving(null)}
        title="Review exception"
        subtitle={resolving ? `${resolving.issue_id} · ${humanize(resolving.issue_type)}` : ''}
        footer={
          <div className="flex justify-end gap-2">
            <button className="btn-secondary" onClick={() => setResolving(null)}>Cancel</button>
            <button className="btn-primary" onClick={resolve}>Save resolution</button>
          </div>
        }
      >
        {resolving && (
          <div className="space-y-4">
            <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{resolving.description}</div>
            <div className="grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
              <p>Detected: <strong>{formatDateTime(resolving.detected_at)}</strong></p>
              <p>Severity: <strong>{resolving.severity}</strong></p>
              <p>Employee: <strong>{resolving.employee_id || '—'}</strong></p>
              <p>Shift: <strong>{resolving.shift_id || '—'}</strong></p>
            </div>
            <div>
              <label className="label">Resolution status</label>
              <select className="input" value={resolveForm.resolution_status} onChange={(e) => setResolveForm({ ...resolveForm, resolution_status: e.target.value })}>
                {['ACKNOWLEDGED', 'RESOLVED', 'IGNORED'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
              </select>
            </div>
            <div><label className="label">Resolution note</label><textarea className="input min-h-24" value={resolveForm.note} onChange={(e) => setResolveForm({ ...resolveForm, note: e.target.value })} placeholder="What action was taken?" /></div>
          </div>
        )}
      </Modal>
    </div>
  )
}
