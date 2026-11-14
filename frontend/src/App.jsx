import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { PageLoader } from './components/Loading'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Employees from './pages/Employees'
import Teams from './pages/Teams'
import Skills from './pages/Skills'
import Leave from './pages/Leave'
import Schedule from './pages/Schedule'
import Swaps from './pages/Swaps'
import Attendance from './pages/Attendance'
import Overtime from './pages/Overtime'
import Exceptions from './pages/Exceptions'
import Analytics from './pages/Analytics'
import Audit from './pages/Audit'
import Admin from './pages/Admin'
import Profile from './pages/Profile'
import NotFound from './pages/NotFound'

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  if (loading) return <PageLoader />
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="employees" element={<Employees />} />
        <Route path="teams" element={<Teams />} />
        <Route path="skills" element={<Skills />} />
        <Route path="leave" element={<Leave />} />
        <Route path="schedule" element={<Schedule />} />
        <Route path="swaps" element={<Swaps />} />
        <Route path="attendance" element={<Attendance />} />
        <Route path="overtime" element={<Overtime />} />
        <Route path="exceptions" element={<Exceptions />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="audit" element={<Audit />} />
        <Route path="admin" element={<Admin />} />
        <Route path="profile" element={<Profile />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
