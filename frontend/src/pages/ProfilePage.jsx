import { useState } from 'react'
import api, { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Alert, Button, Card, Input } from '../components/ui'

export default function ProfilePage() {
  const { user, setUser, applySession } = useAuth()
  const [profile, setProfile] = useState({ name: user.name, email: user.email })
  const [profileMsg, setProfileMsg] = useState({})
  const [pw, setPw] = useState({ current_password: '', new_password: '' })
  const [pwMsg, setPwMsg] = useState({})

  const saveProfile = async (e) => {
    e.preventDefault()
    setProfileMsg({})
    try {
      const { data } = await api.patch('/users/me', profile)
      setUser(data)
      setProfileMsg({ ok: 'Profile updated' })
    } catch (err) {
      setProfileMsg({ error: errorMessage(err) })
    }
  }

  const changePassword = async (e) => {
    e.preventDefault()
    setPwMsg({})
    try {
      const { data } = await api.post('/users/me/password', pw)
      applySession(data)
      setPw({ current_password: '', new_password: '' })
      setPwMsg({ ok: 'Password changed. Other devices have been logged out.' })
    } catch (err) {
      setPwMsg({ error: errorMessage(err) })
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Profile</h2>
        <form onSubmit={saveProfile} className="space-y-4">
          <Alert>{profileMsg.error}</Alert>
          <Alert kind="success">{profileMsg.ok}</Alert>
          <Input id="name" label="Full name" required minLength={2} value={profile.name}
            onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
          <Input id="email" label="Email" type="email" required value={profile.email}
            onChange={(e) => setProfile({ ...profile, email: e.target.value })} />
          <Button type="submit">Save changes</Button>
        </form>
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-900">Change password</h2>
        <form onSubmit={changePassword} className="space-y-4">
          <Alert>{pwMsg.error}</Alert>
          <Alert kind="success">{pwMsg.ok}</Alert>
          <Input id="current" label="Current password" type="password" required autoComplete="current-password"
            value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
          <Input id="new" label="New password" type="password" required minLength={8} autoComplete="new-password"
            value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
          <Button type="submit">Change password</Button>
        </form>
      </Card>
    </div>
  )
}
