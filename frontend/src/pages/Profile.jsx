import { useState } from 'react'
import { KeyRound, Mail, ShieldCheck, UserRound } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import api, { apiErrorMessage } from '../services/api'
import PageHeader from '../components/PageHeader'
import Alert from '../components/Alert'
import Badge from '../components/Badge'
import { formatDate, humanize, initials } from '../lib/format'

export default function Profile() {
  const { user, role } = useAuth()
  const employee = useApi(user?.employee_id ? `/employees/${user.employee_id}` : null)
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '', confirm: '' })
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function changePassword(event) {
    event.preventDefault()
    setError('')
    setNotice('')
    if (passwords.new_password !== passwords.confirm) {
      setError('New password and confirmation do not match.')
      return
    }
    setSaving(true)
    try {
      await api.post('/auth/change-password', {
        current_password: passwords.current_password,
        new_password: passwords.new_password,
      })
      setPasswords({ current_password: '', new_password: '', confirm: '' })
      setNotice('Password changed successfully.')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const person = employee.data

  return (
    <div>
      <PageHeader title="My profile" subtitle="Account, employment record, skills and security settings." />
      {notice && <Alert tone="success" className="mb-4">{notice}</Alert>}
      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <div className="card overflow-hidden">
            <div className="h-24 bg-gradient-to-r from-slate-900 to-brand-800" />
            <div className="px-6 pb-6">
              <div className="-mt-9 flex flex-wrap items-end justify-between gap-4">
                <div className="flex items-end gap-4">
                  <span className="flex h-20 w-20 items-center justify-center rounded-2xl border-4 border-white bg-brand-600 text-2xl font-bold text-white shadow-lg">
                    {initials(user?.username?.slice(0, 1), user?.username?.slice(1, 2))}
                  </span>
                  <div className="pb-1">
                    <h2 className="text-xl font-bold text-slate-900">{person?.full_name || user?.username}</h2>
                    <p className="text-sm text-slate-500">{person?.job_title || humanize(role)} · {person?.team_name || 'No team link'}</p>
                  </div>
                </div>
                <Badge tone="purple">{humanize(role)}</Badge>
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <Info label="Username" value={user?.username} icon={UserRound} />
                <Info label="Email" value={user?.email} icon={Mail} />
                <Info label="Employee ID" value={person?.employee_id || '—'} />
                <Info label="Team" value={person?.team_name || '—'} />
                <Info label="Employment" value={person ? humanize(person.employment_type) : '—'} />
                <Info label="Hire date" value={person ? formatDate(person.hire_date) : '—'} />
                <Info label="Weekly hours cap" value={person ? `${person.weekly_hours_cap}h` : '—'} />
                <Info label="Preferred shift" value={person ? humanize(person.preferred_shift) : '—'} />
                <Info label="Overtime cap" value={person ? `${person.overtime_cap_weekly}h / week` : '—'} />
                <Info label="Minimum rest" value={person ? `${person.min_rest_hours}h` : '—'} />
              </div>
            </div>
          </div>

          {person && (
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-slate-800">Skills & qualifications</h3>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {(person.skills || []).map((skill) => (
                  <div key={skill.skill_id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
                    <div>
                      <p className="text-sm font-medium text-slate-800">{skill.skill_name || skill.skill_id}</p>
                      <p className="text-[11px] text-slate-500">{skill.category} · {skill.years_experience} yrs</p>
                    </div>
                    <Badge tone={skill.certified ? 'green' : 'slate'}>{skill.certified ? 'Certified' : `Level ${skill.proficiency}`}</Badge>
                  </div>
                ))}
                {(person.skills || []).length === 0 && <p className="text-sm text-slate-500">No skills recorded.</p>}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="card p-5">
            <div className="flex items-center gap-2">
              <KeyRound size={16} className="text-brand-600" />
              <h3 className="text-sm font-semibold text-slate-800">Change password</h3>
            </div>
            <form onSubmit={changePassword} className="mt-4 space-y-3">
              <div><label className="label">Current password</label><input type="password" className="input" required value={passwords.current_password} onChange={(e) => setPasswords({ ...passwords, current_password: e.target.value })} /></div>
              <div><label className="label">New password</label><input type="password" className="input" required minLength={8} value={passwords.new_password} onChange={(e) => setPasswords({ ...passwords, new_password: e.target.value })} /></div>
              <div><label className="label">Confirm new password</label><input type="password" className="input" required minLength={8} value={passwords.confirm} onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })} /></div>
              <button className="btn-primary w-full" disabled={saving}>{saving ? 'Updating…' : 'Update password'}</button>
            </form>
          </div>

          <div className="card p-5">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-emerald-600" />
              <h3 className="text-sm font-semibold text-slate-800">Security</h3>
            </div>
            <ul className="mt-3 space-y-2 text-xs text-slate-600">
              <li>• JWT bearer authentication with role-based access control.</li>
              <li>• Passwords hashed with bcrypt; never returned by the API.</li>
              <li>• All sensitive mutations are audit-logged.</li>
              <li>• Ground-truth labels are isolated from operational inputs.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

function Info({ label, value, icon: Icon }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-2.5">
      <p className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {Icon && <Icon size={11} />} {label}
      </p>
      <p className="mt-0.5 truncate text-sm font-medium text-slate-800">{value || '—'}</p>
    </div>
  )
}
