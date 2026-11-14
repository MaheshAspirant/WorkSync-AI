import { useEffect, useState } from 'react'
import { CheckCircle2, Plus, RefreshCw, Settings, ShieldCheck, Users } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import PageHeader from '../components/PageHeader'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import Alert from '../components/Alert'
import Modal from '../components/Modal'
import StatCard from '../components/StatCard'
import { buildQuery, formatDateTime, humanize } from '../lib/format'

const EMPTY_USER = { username: '', email: '', password: '', role: 'EMPLOYEE', employee_id: '' }

export default function Admin() {
  const [tab, setTab] = useState('users')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_USER)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState('')
  const [configEdits, setConfigEdits] = useState({})

  const users = useApi(`/admin/users${buildQuery({ page, page_size: 20 })}`)
  const roles = useApi('/admin/roles')
  const config = useApi('/admin/config')
  const validation = useApi(tab === 'validation' ? '/admin/validation' : null)

  useEffect(() => {
    if (!config.data) return
    const edits = {}
    for (const row of config.data) edits[row.config_key] = JSON.stringify(row.config_value)
    setConfigEdits(edits)
  }, [config.data])

  async function createUser(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post('/admin/users', { ...form, employee_id: form.employee_id || null })
      setOpen(false)
      setForm(EMPTY_USER)
      setNotice('User account created.')
      users.reload()
    } catch (err) {
      setFormError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(user) {
    try {
      await api.put(`/admin/users/${user.user_id}`, { is_active: !user.is_active })
      users.reload()
    } catch (err) {
      setActionError(apiErrorMessage(err))
    }
  }

  async function saveConfig(row) {
    setActionError('')
    try {
      let parsed
      try {
        parsed = JSON.parse(configEdits[row.config_key])
      } catch {
        parsed = configEdits[row.config_key]
      }
      await api.put(`/admin/config/${row.config_key}`, { config_value: parsed, description: row.description })
      setNotice(`Configuration ${row.config_key} updated.`)
      config.reload()
    } catch (err) {
      setActionError(apiErrorMessage(err))
    }
  }

  const userColumns = [
    { key: 'user', label: 'User', render: (row) => <div><p className="font-semibold text-slate-800">{row.username}</p><p className="text-xs text-slate-500">{row.email}</p></div> },
    { key: 'role', label: 'Role', render: (row) => <Badge tone="purple">{humanize(row.role)}</Badge> },
    { key: 'employee_id', label: 'Employee link', render: (row) => <span className="font-mono text-xs text-slate-500">{row.employee_id || '—'}</span> },
    { key: 'is_active', label: 'Status', render: (row) => <Badge tone={row.is_active ? 'green' : 'red'}>{row.is_active ? 'Active' : 'Disabled'}</Badge> },
    { key: 'last_login_at', label: 'Last login', render: (row) => <span className="text-xs text-slate-500">{formatDateTime(row.last_login_at)}</span> },
    { key: 'actions', label: 'Actions', render: (row) => <button className="btn-ghost px-2 py-1 text-xs" onClick={() => toggleActive(row)}>{row.is_active ? 'Disable' : 'Enable'}</button> },
  ]

  return (
    <div>
      <PageHeader
        title="System administration"
        subtitle="Application users, roles, runtime configuration and database integrity validation."
        actions={tab === 'users' && <button className="btn-primary" onClick={() => { setForm(EMPTY_USER); setFormError(''); setOpen(true) }}><Plus size={16} /> Add user</button>}
      />
      {notice && <Alert tone="success" className="mb-4">{notice}</Alert>}
      {(actionError || users.error) && <Alert tone="error" className="mb-4">{actionError || users.error}</Alert>}

      <div className="mb-5 flex gap-2 rounded-xl border border-slate-200 bg-white p-1 shadow-card">
        {[
          ['users', 'Users', Users],
          ['config', 'Configuration', Settings],
          ['validation', 'Data validation', ShieldCheck],
        ].map(([key, label, Icon]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${tab === key ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-50'}`}
          >
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {tab === 'users' && (
        <>
          <div className="mb-5 grid gap-4 sm:grid-cols-3">
            <StatCard label="User accounts" value={users.data?.total ?? 0} icon={Users} tone="brand" />
            <StatCard label="Roles" value={roles.data?.length ?? 0} icon={ShieldCheck} tone="sky" />
            <StatCard label="Active sessions" value="—" hint="JWT stateless; tracked via last login" icon={CheckCircle2} tone="green" />
          </div>
          <DataTable columns={userColumns} rows={users.data?.items || []} loading={users.loading} page={users.data?.page || page} pages={users.data?.pages || 1} total={users.data?.total || 0} onPage={setPage} rowKey={(row) => row.user_id} emptyMessage="No users found." />
        </>
      )}

      {tab === 'config' && (
        <div className="card overflow-hidden">
          <div className="border-b border-slate-200 px-5 py-4">
            <h3 className="text-sm font-semibold text-slate-800">Runtime settings</h3>
            <p className="text-xs text-slate-500">Policy values are persisted and used by services and the scheduling engine.</p>
          </div>
          <div className="divide-y divide-slate-100">
            {(config.data || []).map((row) => (
              <div key={row.config_key} className="flex flex-col gap-3 px-5 py-3 sm:flex-row sm:items-center">
                <div className="min-w-0 sm:w-1/3">
                  <p className="text-sm font-semibold text-slate-800">{humanize(row.config_key)}</p>
                  <p className="text-[11px] text-slate-500">{row.description}</p>
                </div>
                <input
                  className="input font-mono text-xs sm:flex-1"
                  value={configEdits[row.config_key] ?? ''}
                  onChange={(e) => setConfigEdits({ ...configEdits, [row.config_key]: e.target.value })}
                />
                <button className="btn-secondary px-3 py-1.5 text-xs" onClick={() => saveConfig(row)}>Save</button>
              </div>
            ))}
            {!config.data && <p className="px-5 py-8 text-center text-sm text-slate-500">Loading configuration…</p>}
          </div>
        </div>
      )}

      {tab === 'validation' && (
        <div>
          <div className="mb-4 flex items-center gap-2">
            <button className="btn-secondary" onClick={validation.reload}><RefreshCw size={15} /> Re-run validation</button>
            {validation.data && <Badge tone={validation.data.status === 'PASS' ? 'green' : 'red'}>{validation.data.status}</Badge>}
            {validation.data && <span className="text-xs text-slate-500">{validation.data.failures} failures · checked {formatDateTime(validation.data.checked_at)}</span>}
          </div>
          {validation.error && <Alert tone="error" className="mb-4">{validation.error}</Alert>}
          <div className="card overflow-hidden">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="table-head"><tr><th className="px-4 py-3">Check</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Count</th><th className="px-4 py-3">Detail</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {(validation.data?.checks || []).map((check) => (
                  <tr key={check.name}>
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-700">{check.name}</td>
                    <td className="px-4 py-2.5"><Badge status={check.status}>{check.status}</Badge></td>
                    <td className="px-4 py-2.5 text-sm">{check.count}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">{check.detail}</td>
                  </tr>
                ))}
                {!validation.data && validation.loading && <tr><td colSpan={4} className="px-4 py-10 text-center text-sm text-slate-500">Running database checks…</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Create user account"
        footer={
          <div className="flex justify-end gap-2">
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" form="user-form" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create user'}</button>
          </div>
        }
      >
        <form id="user-form" onSubmit={createUser} className="space-y-4">
          {formError && <Alert tone="error">{formError}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className="label">Username</label><input className="input" required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></div>
            <div><label className="label">Email</label><input type="email" className="input" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div><label className="label">Password</label><input type="password" className="input" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
            <div>
              <label className="label">Role</label>
              <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {(roles.data || [{ name: 'EMPLOYEE' }]).map((role) => <option key={role.name} value={role.name}>{humanize(role.name)}</option>)}
              </select>
            </div>
            <div className="sm:col-span-2"><label className="label">Employee ID (optional)</label><input className="input" placeholder="EMP-000001" value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} /></div>
          </div>
        </form>
      </Modal>
    </div>
  )
}
