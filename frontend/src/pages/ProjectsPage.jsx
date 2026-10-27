import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Alert, Button, Card } from '../components/ui'

function formatMB(bytes) {
  return (bytes / (1024 * 1024)).toFixed(1)
}

function QuotaBar({ used, total }) {
  const pct = Math.min(100, (used / total) * 100)
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-500">
        <span>Storage</span>
        <span>
          {formatMB(used)} / {formatMB(total)} MB
        </span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-slate-200">
        <div className={`h-2 rounded-full ${pct > 90 ? 'bg-red-500' : 'bg-indigo-500'}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function ProjectsPage() {
  const { user } = useAuth()
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [newName, setNewName] = useState('')
  const [editing, setEditing] = useState(null) // { id, name }

  const load = () =>
    api
      .get('/projects')
      .then(({ data }) => setProjects(data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))

  useEffect(() => {
    load()
  }, [])

  const create = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.post('/projects', { name: newName })
      setNewName('')
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const rename = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.patch(`/projects/${editing.id}`, { name: editing.name })
      setEditing(null)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const remove = async (project) => {
    if (!window.confirm(`Delete "${project.name}"? All its files and practice sessions will be removed.`)) return
    setError('')
    try {
      await api.delete(`/projects/${project.id}`)
      load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Your projects</h1>
          <p className="text-sm text-slate-500">Each project holds the report, slides and code for one FYP.</p>
        </div>
        <div className="w-full sm:w-64">
          <QuotaBar used={user.storage_used_bytes} total={user.quota_bytes} />
        </div>
      </div>

      <Alert>{error}</Alert>

      <Card>
        <form onSubmit={create} className="flex flex-col gap-2 sm:flex-row">
          <input
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            placeholder="New project name, e.g. Smart Attendance System"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            required
            maxLength={120}
          />
          <Button type="submit">Create project</Button>
        </form>
      </Card>

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : projects.length === 0 ? (
        <p className="text-center text-slate-500">No projects yet. Create one to start uploading your FYP files.</p>
      ) : (
        <ul className="space-y-3">
          {projects.map((p) => (
            <li key={p.id}>
              <Card className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                {editing?.id === p.id ? (
                  <form onSubmit={rename} className="flex flex-1 gap-2">
                    <input
                      autoFocus
                      className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
                      value={editing.name}
                      onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                      required
                      maxLength={120}
                    />
                    <Button type="submit">Save</Button>
                    <Button type="button" variant="ghost" onClick={() => setEditing(null)}>
                      Cancel
                    </Button>
                  </form>
                ) : (
                  <>
                    <div>
                      <Link to={`/projects/${p.id}`} className="font-medium text-indigo-700 hover:underline">
                        {p.name}
                      </Link>
                      <p className="text-xs text-slate-500">Updated {new Date(p.updated_at).toLocaleString()}</p>
                    </div>
                    <div className="flex gap-2">
                      <Button variant="secondary" onClick={() => setEditing({ id: p.id, name: p.name })}>
                        Rename
                      </Button>
                      <Button variant="danger" onClick={() => remove(p)}>
                        Delete
                      </Button>
                    </div>
                  </>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
