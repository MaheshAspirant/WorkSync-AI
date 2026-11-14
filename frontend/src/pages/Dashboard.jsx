import { Link, useNavigate } from 'react-router-dom'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  ArrowUpRight,
  CalendarCheck2,
  CalendarDays,
  ClipboardList,
  Clock3,
  Gauge,
  Repeat2,
  ShieldAlert,
  Sparkles,
  Users,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks/useApi'
import { formatDate, formatNumber, formatShortDate, percent } from '../lib/format'
import StatCard from '../components/StatCard'
import ChartCard from '../components/ChartCard'
import Alert from '../components/Alert'
import Badge from '../components/Badge'
import { LoadingSpinner } from '../components/Loading'

const COLORS = ['#6366f1', '#0ea5e9', '#f59e0b', '#10b981', '#f43f5e', '#8b5cf6']

const tooltipStyle = {
  borderRadius: 10,
  border: '1px solid #e2e8f0',
  fontSize: 12,
  boxShadow: '0 8px 24px rgba(15,23,42,0.08)',
}

export default function Dashboard() {
  const { user, role } = useAuth()
  return role === 'EMPLOYEE' ? <EmployeeDashboard user={user} /> : <ManagerDashboard role={role} />
}

function EmployeeDashboard({ user }) {
  const navigate = useNavigate()
  const { data, loading, error } = useApi('/analytics/me')

  if (loading) return <LoadingSpinner label="Loading your workspace…" />
  if (error) return <Alert tone="error" title="Could not load your dashboard">{error}</Alert>
  if (!data) return null

  const upcoming = data.upcoming_assignments || []
  const summary = data.attendance_summary || {}
  const annual = (data.leave_balances || []).find((row) => row.leave_type === 'ANNUAL')
  const overtimeWeeks = (data.overtime_weeks || []).map((row) => ({
    week: formatShortDate(row.week_start),
    overtime: row.overtime_hours,
  }))

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-brand-900 p-6 text-white shadow-xl">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-300">Employee workspace</p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">Hello, {data.employee_name?.split(' ')[0]}</h1>
            <p className="mt-1 text-sm text-slate-300">
              {data.team_name} · Preferred {data.preferred_shift?.toLowerCase()} shift ·{' '}
              {data.weekly_hours_cap}h weekly cap
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn bg-white text-slate-900 hover:bg-slate-100" onClick={() => navigate('/leave?new=1')}>
              <ClipboardList size={16} /> Request leave
            </button>
            <button type="button" className="btn border border-white/20 bg-white/10 text-white hover:bg-white/20" onClick={() => navigate('/swaps?new=1')}>
              <Repeat2 size={16} /> Request swap
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Upcoming shifts" value={upcoming.length} hint="Next 30 days" icon={CalendarCheck2} tone="brand" />
        <StatCard label="Scheduled hours" value={formatNumber(summary.total_scheduled_hours, 1)} suffix="h" hint="Last 30-day period" icon={Clock3} tone="sky" />
        <StatCard label="Overtime recorded" value={formatNumber(summary.total_overtime_hours, 1)} suffix="h" hint={`Absence rate ${percent(summary.absence_rate)}`} icon={Gauge} tone="amber" />
        <StatCard label="Annual leave left" value={formatNumber(annual?.remaining_days ?? 0, 1)} suffix="days" hint={`${formatNumber(annual?.approved_days ?? 0, 1)} approved this year`} icon={Sparkles} tone="green" />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="card xl:col-span-2">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">My upcoming shifts</h2>
              <p className="text-xs text-slate-500">Published roster for the next 30 days</p>
            </div>
            <Link to="/schedule" className="link text-xs">Open calendar</Link>
          </div>
          <div className="divide-y divide-slate-100">
            {upcoming.length === 0 && (
              <p className="px-5 py-10 text-center text-sm text-slate-500">No upcoming shifts published yet.</p>
            )}
            {upcoming.slice(0, 6).map((shift) => (
              <div key={shift.assignment_id} className="flex items-center gap-4 px-5 py-3.5">
                <span className="flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                  <span className="text-[10px] font-semibold uppercase">{formatDate(shift.shift_date).split(' ')[1]}</span>
                  <span className="text-sm font-bold leading-none">{formatDate(shift.shift_date).split(' ')[0]}</span>
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-800">
                    {shift.template_code} · {formatDate(shift.shift_date)}
                  </p>
                  <p className="text-xs text-slate-500">
                    {new Date(shift.start_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })} –{' '}
                    {new Date(shift.end_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
                <Badge status="SCHEDULED">{shift.scheduled_hours}h</Badge>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-6">
          <ChartCard title="My overtime by week" subtitle="Derived from attendance records" height="h-48">
            {overtimeWeeks.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={overtimeWeeks}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="week" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={28} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="overtime" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="flex h-full items-center justify-center text-sm text-slate-500">No attendance-derived overtime.</p>
            )}
          </ChartCard>

          <div className="card p-5">
            <h3 className="text-sm font-semibold text-slate-800">Leave balances</h3>
            <div className="mt-3 space-y-2.5">
              {(data.leave_balances || []).map((balance) => (
                <div key={balance.leave_type}>
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-600">{balance.leave_type}</span>
                    <span className="text-slate-500">{formatNumber(balance.remaining_days, 1)} / {formatNumber(balance.entitlement_days, 0)}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-brand-500"
                      style={{ width: `${Math.min(100, (balance.approved_days / Math.max(balance.entitlement_days, 1)) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ManagerDashboard({ role }) {
  const navigate = useNavigate()
  const dashboard = useApi('/analytics/dashboard')
  const trends = useApi('/analytics/trends')
  const leave = useApi('/analytics/leave')
  const coverage = useApi('/analytics/coverage')

  if (dashboard.loading && !dashboard.data) return <LoadingSpinner label="Calculating workforce metrics…" />
  if (dashboard.error) return <Alert tone="error" title="Dashboard unavailable">{dashboard.error}</Alert>

  const m = dashboard.data || {}
  const coverageTrend = (trends.data?.coverage || []).map((row) => ({
    week: formatShortDate(row.week_start),
    coverage: row.coverage_pct,
    required: row.required,
    filled: row.filled,
  }))
  const overtimeTrend = (trends.data?.overtime || []).map((row) => ({
    week: formatShortDate(row.week_start),
    overtime: row.overtime_hours,
  }))
  const leavePie = (leave.data?.by_status || []).map((row) => ({ name: row.status, value: row.count }))
  const teamCoverage = (coverage.data?.by_team || [])
    .slice()
    .sort((a, b) => a.coverage_pct - b.coverage_pct)
    .slice(0, 8)
    .map((row) => ({ name: row.team_name?.replace(/ (Operations|Customer Care|Logistics|Retail|Fulfilment|Technical Support|Quality|Finance Operations).*/, '') || row.team_id, coverage: row.coverage_pct }))

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-card sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-600">{role} control centre</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Workforce overview</h1>
          <p className="mt-1 text-sm text-slate-500">
            Reporting period {formatDate(m.period_start)} – {formatDate(m.period_end)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-primary" onClick={() => navigate('/schedule')}>
            <CalendarDays size={16} /> Generate schedule
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate('/exceptions')}>
            <ShieldAlert size={16} /> Review exceptions
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active employees" value={formatNumber(m.active_employees)} hint={`${formatNumber(m.total_teams)} teams`} icon={Users} tone="brand" />
        <StatCard label="Staffing coverage" value={percent(m.coverage_pct)} hint={`Skill coverage ${percent(m.skill_coverage_pct)}`} icon={Gauge} tone="green" />
        <StatCard label="Open conflicts" value={formatNumber(m.open_conflict_count)} hint={`${formatNumber(m.conflict_count)} detected in total`} icon={ShieldAlert} tone="red" />
        <StatCard label="Fairness score" value={percent(m.fairness_score)} hint={`Validity ${percent(m.schedule_validity_pct)}`} icon={Sparkles} tone="violet" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total shifts" value={formatNumber(m.total_shifts)} hint={`${formatNumber(m.total_assignments)} active assignments`} icon={CalendarCheck2} tone="sky" />
        <StatCard label="Leave requests" value={formatNumber(m.total_leave_requests)} hint={`${formatNumber(m.pending_leave_requests)} pending · ${formatNumber(m.approved_leave_requests)} approved`} icon={ClipboardList} tone="amber" />
        <StatCard label="Overtime hours" value={formatNumber(m.total_overtime_hours, 1)} suffix="h" hint={`${formatNumber(m.avg_overtime_per_employee, 2)}h average / employee`} icon={Clock3} tone="orange" />
        <StatCard label="Absence rate" value={percent(m.absence_rate)} hint="Attendance-derived, current period" icon={Users} tone="slate" />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ChartCard title="Coverage trend" subtitle="Filled required positions as a percentage of demand" height="h-72">
            {coverageTrend.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={coverageTrend} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="coverageFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="week" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}%`, 'Coverage']} />
                  <Area type="monotone" dataKey="coverage" stroke="#6366f1" strokeWidth={2.5} fill="url(#coverageFill)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="flex h-full items-center justify-center text-sm text-slate-500">No coverage history in this period.</p>
            )}
          </ChartCard>
        </div>

        <ChartCard title="Leave by status" subtitle="All seeded requests" height="h-72">
          {leavePie.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={leavePie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3}>
                  {leavePie.map((entry, index) => (
                    <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="flex h-full items-center justify-center text-sm text-slate-500">No leave data.</p>
          )}
        </ChartCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <ChartCard title="Overtime by week" subtitle="Actual hours above the 40-hour standard" height="h-64">
          {overtimeTrend.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={overtimeTrend} margin={{ left: -18, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}h`, 'Overtime']} />
                <Bar dataKey="overtime" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="flex h-full items-center justify-center text-sm text-slate-500">No overtime recorded.</p>
          )}
        </ChartCard>

        <ChartCard title="Lowest team coverage" subtitle="Teams needing attention first" height="h-64">
          {teamCoverage.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={teamCoverage} layout="vertical" margin={{ left: 6, right: 12 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}%`, 'Coverage']} />
                <Bar dataKey="coverage" fill="#0ea5e9" radius={[0, 4, 4, 0]} barSize={10} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="flex h-full items-center justify-center text-sm text-slate-500">No coverage data.</p>
          )}
        </ChartCard>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { title: 'Approve leave', body: 'Review pending requests against coverage.', to: '/leave?status=PENDING', icon: ClipboardList },
          { title: 'Resolve swaps', body: 'Check target agreement and skill compatibility.', to: '/swaps?status=REQUESTED', icon: Repeat2 },
          { title: 'Detect conflicts', body: 'Run the detector and resolve exceptions.', to: '/exceptions', icon: ShieldAlert },
        ].map((action) => {
          const Icon = action.icon
          return (
            <Link key={action.title} to={action.to} className="card group flex items-start gap-3 p-4 transition hover:border-brand-300">
              <span className="rounded-lg bg-slate-100 p-2 text-slate-600 group-hover:bg-brand-50 group-hover:text-brand-700">
                <Icon size={18} />
              </span>
              <span className="min-w-0">
                <span className="flex items-center gap-1 text-sm font-semibold text-slate-800">
                  {action.title} <ArrowUpRight size={13} className="text-slate-400" />
                </span>
                <span className="mt-0.5 block text-xs text-slate-500">{action.body}</span>
              </span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
