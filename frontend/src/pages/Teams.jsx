import { useMemo, useState } from 'react'
import { Building2, Plus, Search, Users } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import DataTable from '../components/DataTable'
import Modal from '../components/Modal'
import Alert from '../components/Alert'
import Badge from '../components/Badge'
import { humanize } from '../lib/format'

const EMPTY = { name: '', department: '', site: '', cost_center: '', timezone: 'Asia/Kolkata', manager_employee_id: '' }

export default function Teams() {
  const { role } = useAuth()
  const { data, loading, error, reload } = useApi('/teams?page_size=200')
  const employees = useApi('/employees?page_size=200&status=ACTIVE')
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const teams = useMemo(() => {
    const items = data?.items || []
    if (!search) return items
    const q = search.toLowerCase()
    return items.filter((team) => `${team.name} ${team.department} ${team.site}`.toLowerCase().includes(q))
  }, [data, search])

  const departments = new Set((data?.items || []).map((team) => team.department)).size
  const headcount = (data?.items || []).reduce((sum, team) => sum + team.headcount, 0)

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post('/teams', { ...form, manager_employee_id: form.manager_employee_id || null })
      setOpen(false)
      setForm(EMPTY)
      reload()
    } catch (err) {
      setFormError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    {
      key: 'team',
      label: 'Team',
      render: (row) => (
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-600"><Building2 size={16} /></span>
          <div>
            <p className="font-semibold text-slate-800">{row.name}</p>
            <p className="text-xs text-slate-500">{row.team_id} · {row.site}</p>
          </div>
        </div>
      ),
    },
    { key: 'department', label: 'Department', render: (row) => <Badge tone="slate">{row.department}</Badge> },
    { key: 'manager_name', label: 'Manager', render: (row) => <span className="text-sm">{row.manager_name || 'Unassigned'}</span> },
    { key: 'headcount', label: 'Headcount', render: (row) => <span className="inline-flex items-center gap-1 text-sm"><Users size={13} className="text-slate-400" /> {row.headcount}</span> },
    { key: 'cost_center', label: 'Cost centre', render: (row) => <span className="text-xs text-slate-500">{row.cost_center || '—'}</span> },
    { key: 'is_active', label: 'Status', render: (row) => <Badge tone={row.is_active ? 'green' : 'slate'}>{row.is_active ? 'Active' : 'Inactive'}</Badge> },
  ]

  return (
    <div>
      <PageHeader
        title="Teams"
        subtitle="Organisational units, sites, headcount and active manager assignments."
        actions={['ADMIN', 'HR'].includes(role) && <button className="btn-primary" onClick={() => { setForm(EMPTY); setFormError(''); setOpen(true) }}><Plus size={16} /> Add team</button>}
      />
      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Teams" value={data?.total ?? 0} icon={Building2} tone="brand" />
        <StatCard label="Departments" value={departments} icon={Users} tone="sky" />
        <StatCard label="Employees covered" value={headcount} icon={Users} tone="green" />
      </div>

      <div className="mb-4 max-w-md">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="input pl-9" placeholder="Search teams…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}
      <DataTable columns={columns} rows={teams} loading={loading} rowKey={(row) => row.team_id} emptyMessage="No teams found." />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Create team"
        subtitle="A team groups employees under one operational unit."
        footer={
          <div className="flex justify-end gap-2">
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" form="team-form" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create team'}</button>
          </div>
        }
      >
        <form id="team-form" onSubmit={submit} className="space-y-4">
          {formError && <Alert tone="error">{formError}</Alert>}
          <div><label className="label">Team name</label><input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className="label">Department</label><input className="input" required value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} /></div>
            <div><label className="label">Site</label><input className="input" required value={form.site} onChange={(e) => setForm({ ...form, site: e.target.value })} /></div>
            <div><label className="label">Cost centre</label><input className="input" value={form.cost_center} onChange={(e) => setForm({ ...form, cost_center: e.target.value })} /></div>
            <div><label className="label">Timezone</label><input className="input" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} /></div>
          </div>
          <div>
            <label className="label">Manager (optional)</label>
            <select className="input" value={form.manager_employee_id} onChange={(e) => setForm({ ...form, manager_employee_id: e.target.value })}>
              <option value="">Unassigned</option>
              {(employees.data?.items || []).slice(0, 200).map((employee) => (
                <option key={employee.employee_id} value={employee.employee_id}>{employee.full_name} · {employee.employee_id}</option>
              ))}
            </select>
          </div>
        </form>
      </Modal>
    </div>
  )
}
