import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { AuthPage } from '../components/Layout'
import { Alert, Button, Card, Input } from '../components/ui'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(form.email, form.password)
      navigate('/')
    } catch (err) {
      setError(errorMessage(err, 'Login failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthPage title="Log in to practise your viva">
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <Alert>{error}</Alert>
          <Input id="email" label="Email" type="email" required autoComplete="email"
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <Input id="password" label="Password" type="password" required autoComplete="current-password"
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? 'Logging in…' : 'Log in'}
          </Button>
        </form>
      </Card>
      <p className="mt-4 text-center text-sm text-slate-600">
        No account?{' '}
        <Link to="/register" className="font-medium text-indigo-600 hover:underline">
          Register
        </Link>
      </p>
    </AuthPage>
  )
}
