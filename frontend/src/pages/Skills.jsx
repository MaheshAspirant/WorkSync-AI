import { useState } from 'react'
import { Plus, ShieldCheck, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import PageHeader from '../components/PageHeader'
import DataTable from '../components/DataTable'
import Modal from '../components/Modal'
import Alert from '../components/Alert'
import Badge from '../components/Badge'
import StatCard from '../components/StatCard'

const EMPTY = { name: '', category: '', description: '', is_critical: false }

export default function Skills() {
  const { role } = useAuth()
  const { data, loading, error, reload } = useApi('/skills?page_size=200')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const skills = data?.items || []
  const critical = skills.filter((skill) => skill.is_critical).length
  const categories = new Set(skills.map((skill) => skill.category)).size

  async function submit(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post('/skills', form)
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
      key: 'skill',
      label: 'Skill',
      render: (row) => (
        <div className="flex items-center gap-3">
          <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${row.is_critical ? 'bg-rose-50 text-rose-600' : 'bg-brand-50 text-brand-600'}`}>
            <Sparkles size={16} />
          </span>
          <div>
            <p className="font-semibold text-slate-800">{row.name}</p>
            <p className="text-xs text-slate-500">{row.skill_id}</p>
          </div>
        </div>
      ),
    },
    { key: 'category', label: 'Category', render: (row) => <Badge tone="slate">{row.category}</Badge> },
    { key: 'description', label: 'Description', render: (row) => <span className="block max-w-xl truncate text-xs text-slate-500">{row.description || '—'}</span> },
    { key: 'employee_count', label: 'Qualified employees', render: (row) => <span className="text-sm font-medium">{row.employee_count}</span> },
    { key: 'is_critical', label: 'Criticality', render: (row) => <Badge tone={row.is_critical ? 'red' : 'slate'}>{row.is_critical ? 'Critical' : 'Standard'}</Badge> },
  ]

  return (
    <div>
      <PageHeader
        title="Skills"
        subtitle="Skill catalogue used for coverage requirements, eligibility and swap validation."
        actions={['ADMIN', 'HR'].includes(role) && <button className="btn-primary" onClick={() => { setForm(EMPTY); setFormError(''); setOpen(true) }}><Plus size={16} /> Add skill</button>}
      />
      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Skills" value={skills.length} icon={Sparkles} tone="brand" />
        <StatCard label="Categories" value={categories} icon={ShieldCheck} tone="sky" />
        <StatCard label="Critical skills" value={critical} icon={ShieldCheck} tone="red" />
      </div>
      {error && <Alert tone="error" className="mb-4">{error}</Alert>}
      <DataTable columns={columns} rows={skills} loading={loading} rowKey={(row) => row.skill_id} emptyMessage="No skills configured." />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Add skill"
        footer={
          <div className="flex justify-end gap-2">
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" form="skill-form" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create skill'}</button>
          </div>
        }
      >
        <form id="skill-form" onSubmit={submit} className="space-y-4">
          {formError && <Alert tone="error">{formError}</Alert>}
          <div><label className="label">Name</label><input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div><label className="label">Category</label><input className="input" required value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></div>
          <div><label className="label">Description</label><textarea className="input min-h-24" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={form.is_critical} onChange={(e) => setForm({ ...form, is_critical: e.target.checked })} />
            Mark as critical skill
          </label>
        </form>
      </Modal>
    </div>
  )
}
