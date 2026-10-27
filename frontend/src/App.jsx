import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { RequireAuth } from './components/Layout'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'
import PracticePage from './pages/PracticePage'
import ProjectPage from './pages/ProjectPage'
import ProjectsPage from './pages/ProjectsPage'
import RegisterPage from './pages/RegisterPage'
import SessionPage from './pages/SessionPage'
import StatusPage from './pages/StatusPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/status" element={<StatusPage />} />
          <Route element={<RequireAuth />}>
            <Route path="/" element={<ProjectsPage />} />
            <Route path="/projects/:projectId" element={<ProjectPage />} />
            <Route path="/projects/:projectId/practice" element={<PracticePage />} />
            <Route path="/projects/:projectId/sessions/:sessionId" element={<SessionPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
