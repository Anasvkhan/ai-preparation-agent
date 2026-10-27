import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { AuthPage } from '../components/Layout'
import { Alert, Button, Card, Input } from '../components/ui'

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await register(form.name, form.email, form.password)
      navigate('/')
    } catch (err) {
      setError(errorMessage(err, 'Registration failed'))
    } finally {
      setBusy(false)
    }
  }

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  return (
    <AuthPage title="Create your student account">
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <Alert>{error}</Alert>
          <Input id="name" label="Full name" required minLength={2} value={form.name} onChange={set('name')} />
          <Input id="email" label="Email" type="email" required autoComplete="email" value={form.email} onChange={set('email')} />
          <Input id="password" label="Password" type="password" required minLength={8} autoComplete="new-password"
            value={form.password} onChange={set('password')} />
          <p className="text-xs text-slate-500">At least 8 characters, with letters and numbers.</p>
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? 'Creating account…' : 'Create account'}
          </Button>
        </form>
      </Card>
      <p className="mt-4 text-center text-sm text-slate-600">
        Already registered?{' '}
        <Link to="/login" className="font-medium text-indigo-600 hover:underline">
          Log in
        </Link>
      </p>
    </AuthPage>
  )
}
