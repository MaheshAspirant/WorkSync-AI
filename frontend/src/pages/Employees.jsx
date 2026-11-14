import { useState } from 'react'
import { Plus, Search, UserRound } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi, useDebounced } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import Badge from '../components/Badge'
import Modal from '../components/Modal'
import Alert from '../components/Alert'
import { buildQuery, formatDate, humanize, initials } from '../lib/format'

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  team_id: '',
  job_title: '',
  employment_type: 'FULL_TIME',
  hire_date: new Date().toISOString().slice(0, 10),
  weekly_hours_cap: 40,
  daily_hours_cap: 8,
  overtime_cap_weekly: 10,
  min_rest_hours: 11,
  preferred_shift: 'NONE',
}

export default function Employees() {
  const { role } = useAuth()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [teamId, setTeamId] = useState('')
  const [status, setStatus] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const debouncedSearch = useDebounced(search)

  const teams = useApi('/teams?page_size=200')
  const query = buildQuery({
    page,
    page_size: 20,
    q: debouncedSearch,
    team_id: teamId,
    status,
  })
  const { data, loading, error, reload } = useApi(`/employees${query}`)

  const canCreate = ['ADMIN', 'HR'].includes(role)

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post('/employees', {
        ...form,
        weekly_hours_cap: Number(form.weekly_hours_cap),
        daily_hours_cap: Number(form.daily_hours_cap),
        overtime_cap_weekly: Number(form.overtime_cap_weekly),
        min_rest_hours: Number(form.min_rest_hours),
        phone: form.phone || null,
      })
      setModalOpen(false)
      setForm(EMPTY_FORM)
      reload()
    } catch (err) {
      setFormError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  function openCreate() {
    setForm({ ...EMPTY_FORM, team_id: teams.data?.items?.[0]?.team_id || '' })
    setFormError('')
    setModalOpen(true)
  }

  const columns = [
    {
      key: 'employee',
      label: 'Employee',
      render: (row) => (
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-50 text-xs font-bold text-brand-700">
            {initials(row.first_name, row.last_name)}
          </span>
          <div>
            <p className="font-semibold text-slate-800">{row.full_name}</p>
            <p className="text-xs text-slate-500">{row.employee_id} · {row.email}</p>
          </div>
        </div>
      ),
    },
    { key: 'team', label: 'Team', render: (row) => <span className="text-sm">{row.team_name}</span> },
    { key: 'job_title', label: 'Role', render: (row) => <span className="text-sm">{row.job_title}</span> },
    { key: 'employment_type', label: 'Type', render: (row) => <Badge tone="slate">{humanize(row.employment_type)}</Badge> },
    { key: 'preferred_shift', label: 'Preference', render: (row) => <span className="text-xs text-slate-600">{humanize(row.preferred_shift)}</span> },
    { key: 'weekly_hours_cap', label: 'Hours cap', render: (row) => <span className="text-sm">{row.weekly_hours_cap}h</span> },
    { key: 'hire_date', label: 'Hired', render: (row) => <span className="text-xs text-slate-500">{formatDate(row.hire_date)}</span> },
    { key: 'status', label: 'Status', render: (row) => <Badge status={row.status}>{humanize(row.status)}</Badge> },
  ]

  return (
    <div>
      <PageHeader
        title="Employees"
        subtitle="Master employee records, team assignment, working-hour caps and shift preferences."
        actions={
          canCreate && (
            <button type="button" className="btn-primary" onClick={openCreate}>
              <Plus size={16} /> Add employee
            </button>
          )
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_220px_180px]">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="input pl-9"
            placeholder="Search name, email or employee ID…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
          />
        </div>
        <select
          className="input"
          value={teamId}
          onChange={(event) => {
            setTeamId(event.target.value)
            setPage(1)
          }}
        >
          <option value="">All teams</option>
          {(teams.data?.items || []).map((team) => (
            <option key={team.team_id} value={team.team_id}>{team.name}</option>
          ))}
        </select>
        <select
          className="input"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value)
            setPage(1)
          }}
        >
          <option value="">All statuses</option>
          {['ACTIVE', 'ON_LEAVE', 'INACTIVE', 'TERMINATED'].map((value) => (
            <option key={value} value={value}>{humanize(value)}</option>
          ))}
        </select>
      </div>

      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <DataTable
        columns={columns}
        rows={data?.items || []}
        loading={loading}
        page={data?.page || page}
        pages={data?.pages || 1}
        total={data?.total || 0}
        onPage={setPage}
        rowKey={(row) => row.employee_id}
        emptyMessage="No employees match these filters."
      />

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Add employee"
        subtitle="Creates a master record and immutable employee ID."
        size="lg"
        footer={
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
            <button type="submit" form="employee-form" className="btn-primary" disabled={saving}>
              {saving ? 'Saving…' : 'Create employee'}
            </button>
          </div>
        }
      >
        <form id="employee-form" onSubmit={submit} className="space-y-4">
          {formError && <Alert tone="error">{formError}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className="label">First name</label><input className="input" required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></div>
            <div><label className="label">Last name</label><input className="input" required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></div>
            <div><label className="label">Email</label><input type="email" className="input" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
            <div>
              <label className="label">Team</label>
              <select className="input" required value={form.team_id} onChange={(e) => setForm({ ...form, team_id: e.target.value })}>
                <option value="">Select a team</option>
                {(teams.data?.items || []).map((team) => <option key={team.team_id} value={team.team_id}>{team.name}</option>)}
              </select>
            </div>
            <div><label className="label">Job title</label><input className="input" required value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} /></div>
            <div>
              <label className="label">Employment type</label>
              <select className="input" value={form.employment_type} onChange={(e) => setForm({ ...form, employment_type: e.target.value })}>
                {['FULL_TIME', 'PART_TIME', 'CONTRACT', 'INTERN'].map((v) => <option key={v} value={v}>{humanize(v)}</option>)}
              </select>
            </div>
            <div><label className="label">Hire date</label><input type="date" className="input" required value={form.hire_date} onChange={(e) => setForm({ ...form, hire_date: e.target.value })} /></div>
            <div><label className="label">Weekly hours cap</label><input type="number" min="1" max="60" className="input" value={form.weekly_hours_cap} onChange={(e) => setForm({ ...form, weekly_hours_cap: e.target.value })} /></div>
            <div><label className="label">Overtime cap / week</label><input type="number" min="0" max="30" className="input" value={form.overtime_cap_weekly} onChange={(e) => setForm({ ...form, overtime_cap_weekly: e.target.value })} /></div>
            <div><label className="label">Daily hours cap</label><input type="number" min="1" max="16" className="input" value={form.daily_hours_cap} onChange={(e) => setForm({ ...form, daily_hours_cap: e.target.value })} /></div>
            <div><label className="label">Minimum rest (hours)</label><input type="number" min="0" max="24" className="input" value={form.min_rest_hours} onChange={(e) => setForm({ ...form, min_rest_hours: e.target.value })} /></div>
            <div>
              <label className="label">Preferred shift</label>
              <select className="input" value={form.preferred_shift} onChange={(e) => setForm({ ...form, preferred_shift: e.target.value })}>
                {['MORNING', 'EVENING', 'NIGHT', 'NONE'].map((v) => <option key={v} value={v}>{humanize(v)}</option>)}
              </select>
            </div>
          </div>
          <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
            <UserRound size={13} className="mr-1 inline" /> Skills and availability can be added from the employee detail or HR admin workflow.
          </p>
        </form>
      </Modal>
    </div>
  )
}
