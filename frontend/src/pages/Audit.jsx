import { useState } from 'react'
import { FileSearch, ShieldCheck } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import PageHeader from '../components/PageHeader'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import Alert from '../components/Alert'
import { buildQuery, formatDateTime, humanize } from '../lib/format'

export default function Audit() {
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')
  const [entityType, setEntityType] = useState('')

  const query = buildQuery({ page, page_size: 30, action, entity_type: entityType })
  const { data, loading, error } = useApi(`/audit${query}`)

  const columns = [
    { key: 'audit_id', label: 'ID', render: (row) => <span className="font-mono text-[11px] text-slate-500">#{row.audit_id}</span> },
    { key: 'actor', label: 'Actor', render: (row) => <div><p className="text-xs font-semibold text-slate-700">{row.actor_user_id || 'system'}</p><p className="text-[11px] text-slate-500">{row.actor_role || 'seed'}</p></div> },
    { key: 'action', label: 'Action', render: (row) => <Badge tone="slate">{humanize(row.action)}</Badge> },
    { key: 'entity', label: 'Entity', render: (row) => <div><p className="text-xs font-medium text-slate-700">{humanize(row.entity_type)}</p><p className="font-mono text-[11px] text-slate-500">{row.entity_id || '—'}</p></div> },
    {
      key: 'change',
      label: 'Change',
      render: (row) => (
        <span className="block max-w-md truncate text-[11px] text-slate-500" title={JSON.stringify(row.new_state || {})}>
          {row.previous_state ? 'Previous → ' : ''}{row.new_state ? JSON.stringify(row.new_state) : row.reason || '—'}
        </span>
      ),
    },
    { key: 'reason', label: 'Reason', render: (row) => <span className="block max-w-xs truncate text-xs text-slate-500">{row.reason || '—'}</span> },
    { key: 'created_at', label: 'Timestamp', render: (row) => <span className="text-[11px] text-slate-500">{formatDateTime(row.created_at)}</span> },
  ]

  return (
    <div>
      <PageHeader title="Audit trail" subtitle="Append-only log of state changes across employees, leave, scheduling, swaps, attendance and configuration." />
      {error && <Alert tone="error" className="mb-4">{error}</Alert>}
      <div className="mb-4 flex flex-wrap gap-3">
        <select className="input w-auto min-w-44" value={action} onChange={(e) => { setAction(e.target.value); setPage(1) }}>
          <option value="">All actions</option>
          {['LOGIN', 'CREATE_EMPLOYEE', 'UPDATE_EMPLOYEE', 'SUBMIT_LEAVE', 'APPROVED', 'REJECTED', 'REQUEST_SWAP', 'APPROVE_SWAP', 'APPLY_SWAP', 'GENERATE_SCHEDULE', 'RECORD_ATTENDANCE', 'RUN_EXCEPTION_DETECTION', 'RESOLVE_EXCEPTION', 'UPDATE_CONFIG'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
        </select>
        <select className="input w-auto min-w-44" value={entityType} onChange={(e) => { setEntityType(e.target.value); setPage(1) }}>
          <option value="">All entities</option>
          {['Employee', 'LeaveRequest', 'SwapRequest', 'ShiftAssignment', 'SchedulingRun', 'SchedulingException', 'AttendanceEvent', 'User', 'SystemConfig'].map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
        <span className="ml-auto inline-flex items-center gap-1 text-xs text-slate-500"><ShieldCheck size={14} /> Immutable event history</span>
      </div>
      <DataTable columns={columns} rows={data?.items || []} loading={loading} page={data?.page || page} pages={data?.pages || 1} total={data?.total || 0} onPage={setPage} rowKey={(row) => row.audit_id} emptyMessage="No audit entries match these filters." />
      <div className="mt-4 card flex items-start gap-3 p-4 text-xs text-slate-500">
        <FileSearch size={16} className="mt-0.5 shrink-0 text-brand-500" />
        <p>Audit records capture actor, action, entity, previous/new state, reason and timestamp. Historical records are never overwritten when lifecycle states change.</p>
      </div>
    </div>
  )
}
