import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Activity, BadgeCheck, Clock3, Scale, Users } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import ChartCard from '../components/ChartCard'
import Alert from '../components/Alert'
import Badge from '../components/Badge'
import { LoadingSpinner } from '../components/Loading'
import { formatDate, formatNumber, formatShortDate, humanize, percent } from '../lib/format'

const COLORS = ['#6366f1', '#0ea5e9', '#f59e0b', '#10b981', '#f43f5e', '#8b5cf6']
const tooltipStyle = { borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 12 }

export default function Analytics() {
  const dashboard = useApi('/analytics/dashboard')
  const coverage = useApi('/analytics/coverage')
  const overtime = useApi('/analytics/overtime')
  const fairness = useApi('/analytics/fairness')
  const leave = useApi('/analytics/leave')
  const trends = useApi('/analytics/trends')

  if (dashboard.loading && !dashboard.data) return <LoadingSpinner label="Aggregating analytics…" />
  if (dashboard.error) return <Alert tone="error" title="Analytics unavailable">{dashboard.error}</Alert>

  const m = dashboard.data || {}
  const cover = coverage.data || {}
  const over = overtime.data || {}
  const fair = fairness.data || {}
  const leaveData = leave.data || {}
  const trend = trends.data || {}

  const coverageByDay = (cover.by_day || []).map((row) => ({
    date: formatShortDate(row.date),
    coverage: row.coverage_pct,
    required: row.required,
    filled: row.filled,
  }))
  const coverageByTeam = (cover.by_team || []).map((row) => ({
    name: row.team_name?.replace(/\s(Operations|Customer Care|Logistics|Retail|Fulfilment|Technical Support|Quality|Finance Operations).*/, '') || row.team_id,
    coverage: row.coverage_pct,
  }))
  const overtimeWeekly = (over.by_week || []).map((row) => ({ week: formatShortDate(row.week_start), overtime: row.overtime_hours }))
  const leavePie = (leaveData.by_status || []).map((row) => ({ name: humanize(row.status), value: row.count }))
  const leaveTypes = (leaveData.by_type || []).map((row) => ({ name: humanize(row.leave_type), value: row.count }))
  const fairnessRows = (fair.by_employee || []).slice(0, 10)
  const topOvertime = (over.top_employees || []).slice(0, 8)
  const trendCoverage = (trend.coverage || []).map((row) => ({ week: formatShortDate(row.week_start), coverage: row.coverage_pct }))
  const trendAbsence = (trend.absences || []).map((row) => ({ week: formatShortDate(row.week_start), absence: row.absence_rate }))

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics & reports"
        subtitle={`All metrics calculated from operational records · ${formatDate(m.period_start)} – ${formatDate(m.period_end)}`}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Coverage" value={percent(m.coverage_pct)} hint={`${formatNumber(cover.filled_positions)} of ${formatNumber(cover.required_positions)} positions`} icon={BadgeCheck} tone="green" />
        <StatCard label="Skill coverage" value={percent(m.skill_coverage_pct)} hint={`${formatNumber(cover.skill_filled_positions)} qualified fills`} icon={Users} tone="brand" />
        <StatCard label="Overtime" value={formatNumber(m.total_overtime_hours, 1)} suffix="h" hint={`${m.employees_over_cap || 0} employees over cap`} icon={Clock3} tone="amber" />
        <StatCard label="Fairness score" value={percent(m.fairness_score)} hint={`Schedule validity ${percent(m.schedule_validity_pct)}`} icon={Scale} tone="violet" />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <ChartCard title="Daily coverage" subtitle="Filled positions ÷ required positions × 100" height="h-72">
          {coverageByDay.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={coverageByDay} margin={{ left: -18, right: 8 }}>
                <defs>
                  <linearGradient id="dailyCoverage" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}%`, 'Coverage']} />
                <Area type="monotone" dataKey="coverage" stroke="#10b981" strokeWidth={2.5} fill="url(#dailyCoverage)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : <p className="flex h-full items-center justify-center text-sm text-slate-500">No coverage data.</p>}
        </ChartCard>

        <ChartCard title="Coverage by team" subtitle="Lowest teams first" height="h-72">
          {coverageByTeam.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={[...coverageByTeam].sort((a, b) => a.coverage - b.coverage).slice(0, 12)} layout="vertical" margin={{ left: 8, right: 12 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}%`, 'Coverage']} />
                <Bar dataKey="coverage" fill="#6366f1" radius={[0, 4, 4, 0]} barSize={9} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="flex h-full items-center justify-center text-sm text-slate-500">No team coverage data.</p>}
        </ChartCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <ChartCard title="Overtime by week" subtitle="Attendance-derived" height="h-64">
          {overtimeWeekly.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={overtimeWeekly} margin={{ left: -18, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="week" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}h`, 'Overtime']} />
                <Bar dataKey="overtime" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="flex h-full items-center justify-center text-sm text-slate-500">No overtime.</p>}
        </ChartCard>

        <ChartCard title="Leave by status" subtitle={`Approval rate ${percent(leaveData.approval_rate)}`} height="h-64">
          {leavePie.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={leavePie} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={3}>
                  {leavePie.map((entry, index) => <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="flex h-full items-center justify-center text-sm text-slate-500">No leave data.</p>}
        </ChartCard>

        <ChartCard title="Leave by type" subtitle="Request mix" height="h-64">
          {leaveTypes.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={leaveTypes} layout="vertical" margin={{ left: 10, right: 10 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="value" fill="#8b5cf6" radius={[0, 4, 4, 0]} barSize={10} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="flex h-full items-center justify-center text-sm text-slate-500">No leave types.</p>}
        </ChartCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <ChartCard title="Coverage trend" subtitle="Weekly rollup" height="h-64">
          {trendCoverage.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendCoverage} margin={{ left: -18, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="week" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}%`, 'Coverage']} />
                <Line type="monotone" dataKey="coverage" stroke="#6366f1" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : <p className="flex h-full items-center justify-center text-sm text-slate-500">No trend data.</p>}
        </ChartCard>

        <ChartCard title="Absence rate trend" subtitle="Absent + no-show ÷ attendance events" height="h-64">
          {trendAbsence.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendAbsence} margin={{ left: -18, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="week" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 'auto']} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} formatter={(value) => [`${value}%`, 'Absence rate']} />
                <Line type="monotone" dataKey="absence" stroke="#f43f5e" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : <p className="flex h-full items-center justify-center text-sm text-slate-500">No absence data.</p>}
        </ChartCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div><h3 className="text-sm font-semibold text-slate-800">Fairness detail</h3><p className="text-xs text-slate-500">{fair.explanation}</p></div>
            <Badge tone="violet">{percent(fair.fairness_score)}</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100">
              <thead className="table-head"><tr><th className="px-4 py-2">Employee</th><th className="px-4 py-2">Nights</th><th className="px-4 py-2">Weekends</th><th className="px-4 py-2">OT</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {fairnessRows.map((row) => (
                  <tr key={row.employee_id}>
                    <td className="px-4 py-2 text-sm"><p className="font-medium text-slate-800">{row.employee_name}</p><p className="text-[11px] text-slate-500">{row.employee_id}</p></td>
                    <td className="px-4 py-2 text-sm">{row.night}</td>
                    <td className="px-4 py-2 text-sm">{row.weekend}</td>
                    <td className="px-4 py-2 text-sm">{formatNumber(row.overtime_hours, 1)}h</td>
                  </tr>
                ))}
                {fairnessRows.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-slate-500">No assignment data.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div><h3 className="text-sm font-semibold text-slate-800">Top overtime employees</h3><p className="text-xs text-slate-500">Highest actual hours above the weekly cap</p></div>
            <Badge tone="amber">{formatNumber(over.total_overtime_hours, 1)}h</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100">
              <thead className="table-head"><tr><th className="px-4 py-2">Employee</th><th className="px-4 py-2">Week</th><th className="px-4 py-2">Overtime</th><th className="px-4 py-2">Cap</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {topOvertime.map((row) => (
                  <tr key={`${row.employee_id}-${row.week_start}`}>
                    <td className="px-4 py-2 text-sm"><p className="font-medium text-slate-800">{row.employee_name}</p><p className="text-[11px] text-slate-500">{row.team_id}</p></td>
                    <td className="px-4 py-2 text-xs text-slate-500">{formatDate(row.week_start)}</td>
                    <td className="px-4 py-2 text-sm font-semibold text-amber-700">{formatNumber(row.overtime_hours, 1)}h</td>
                    <td className="px-4 py-2"><Badge tone={row.cap_exceeded ? 'red' : 'green'}>{row.cap_exceeded ? 'Exceeded' : 'Within'}</Badge></td>
                  </tr>
                ))}
                {topOvertime.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-sm text-slate-500">No overtime records.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="card flex items-start gap-3 p-4 text-xs text-slate-500">
        <Activity size={16} className="mt-0.5 shrink-0 text-brand-500" />
        <p>
          Metrics are computed from database records on request: coverage from required vs active assignments, skill coverage
          from qualified assignees, overtime from attendance actual hours, and fairness from normalised distributions of
          night, weekend and overtime loads. Hard-constraint validity is reported separately from the soft-constraint score.
        </p>
      </div>
    </div>
  )
}
