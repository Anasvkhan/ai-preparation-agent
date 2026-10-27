import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api, { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import StatusChip from '../components/StatusChip'
import { Alert, Button, Card } from '../components/ui'

const KINDS = [
  { kind: 'report', label: 'Report', hint: 'Text-readable PDF, up to 25 MB', accept: '.pdf' },
  { kind: 'presentation', label: 'Presentation', hint: 'PPTX or text-readable PDF, up to 25 MB', accept: '.pptx,.pdf' },
  {
    kind: 'code',
    label: 'Code (optional)',
    hint: 'Up to 5 UTF-8 files, 1 MB each: .py .js .jsx .ts .tsx .html .css .json .sql',
    accept: '.py,.js,.jsx,.ts,.tsx,.html,.css,.json,.sql',
  },
]

function formatSize(bytes) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function UploadButton({ kind, accept, onUploaded, onError, artifactId, label = 'Upload' }) {
  const input = useRef(null)
  const [busy, setBusy] = useState(false)

  const choose = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    onError('')
    const form = new FormData()
    form.append('file', file)
    try {
      if (artifactId) {
        await api.put(`${kind.base}/${artifactId}`, form)
      } else {
        form.append('kind', kind.kind)
        await api.post(kind.base, form)
      }
      onUploaded()
    } catch (err) {
      onError(`${file.name}: ${errorMessage(err, 'Upload failed')}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <input ref={input} type="file" accept={accept} className="hidden" onChange={choose} />
      <Button variant={artifactId ? 'secondary' : 'primary'} disabled={busy} onClick={() => input.current.click()}>
        {busy ? 'Uploading…' : label}
      </Button>
    </>
  )
}

export default function ProjectPage() {
  const { projectId } = useParams()
  const { setUser } = useAuth()
  const [project, setProject] = useState(null)
  const [artifacts, setArtifacts] = useState([])
  const [sessions, setSessions] = useState([])
  const [error, setError] = useState('')
  const base = `/projects/${projectId}/artifacts`

  const loadArtifacts = useCallback(
    () =>
      api
        .get(base)
        .then(({ data }) => setArtifacts(data))
        .catch((err) => setError(errorMessage(err))),
    [base],
  )

  const refreshAll = useCallback(() => {
    loadArtifacts()
    api.get('/users/me').then(({ data }) => setUser(data))
  }, [loadArtifacts, setUser])

  useEffect(() => {
    api
      .get(`/projects/${projectId}`)
      .then(({ data }) => setProject(data))
      .catch((err) => setError(errorMessage(err, 'Project not found')))
    loadArtifacts()
    api.get(`/projects/${projectId}/sessions`).then(({ data }) => setSessions(data)).catch(() => {})
  }, [projectId, loadArtifacts])

  // Poll while files are being processed by the worker.
  const busy = artifacts.some((a) => a.status === 'queued' || a.status === 'processing')
  useEffect(() => {
    if (!busy) return
    const timer = setInterval(loadArtifacts, 3000)
    return () => clearInterval(timer)
  }, [busy, loadArtifacts])

  const act = async (fn) => {
    setError('')
    try {
      await fn()
      refreshAll()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const remove = (a) => {
    if (!window.confirm(`Delete ${a.filename}? Questions that cite it will show "Source no longer available".`)) return
    act(() => api.delete(`${base}/${a.id}`))
  }

  const download = async (a) => {
    try {
      const { data } = await api.get(`${base}/${a.id}/download`)
      window.open(data.url, '_blank', 'noopener')
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const ready = artifacts.some((a) => a.status === 'ready')

  if (!project) return error ? <Alert>{error}</Alert> : <p className="text-slate-500">Loading…</p>

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to="/" className="text-sm text-indigo-600 hover:underline">
            ← Projects
          </Link>
          <h1 className="text-2xl font-semibold text-slate-900">{project.name}</h1>
          <p className="text-sm text-slate-500">Upload your FYP evidence. At least one file must be Ready to start a viva.</p>
        </div>
        {ready ? (
          <Link to={`/projects/${projectId}/practice`}>
            <Button>Start viva practice</Button>
          </Link>
        ) : (
          <Button disabled title="Upload a file and wait until it is Ready">
            Start viva practice
          </Button>
        )}
      </div>

      <Alert>{error}</Alert>

      <div className="grid gap-4 md:grid-cols-3">
        {KINDS.map((k) => (
          <Card key={k.kind} className="flex flex-col justify-between gap-3">
            <div>
              <h2 className="font-medium text-slate-900">{k.label}</h2>
              <p className="text-xs text-slate-500">{k.hint}</p>
            </div>
            <UploadButton kind={{ ...k, base }} accept={k.accept} onUploaded={refreshAll} onError={setError} />
          </Card>
        ))}
      </div>

      <Card>
        <h2 className="mb-3 font-medium text-slate-900">Files</h2>
        {artifacts.length === 0 ? (
          <p className="text-sm text-slate-500">No files uploaded yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {artifacts.map((a) => (
              <li key={a.id} className="flex flex-col gap-2 py-3 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate font-medium text-slate-800">{a.filename}</span>
                    <StatusChip status={a.status} />
                  </div>
                  <p className="text-xs text-slate-500">
                    {a.kind} · {formatSize(a.size_bytes)} · v{a.version}
                    {a.status === 'ready' && ` · ${a.chunk_count} chunks`}
                    {a.page_count ? ` · ${a.page_count} ${a.file_format === 'pptx' ? 'slides' : 'pages'}` : ''}
                  </p>
                  {a.error && <p className="text-xs text-red-600">{a.error}</p>}
                </div>
                <div className="flex flex-wrap gap-2">
                  {(a.status === 'queued' || a.status === 'processing') && (
                    <Button variant="ghost" onClick={() => act(() => api.post(`${base}/${a.id}/cancel`))}>
                      Cancel
                    </Button>
                  )}
                  {(a.status === 'failed' || a.status === 'canceled') && (
                    <Button variant="secondary" onClick={() => act(() => api.post(`${base}/${a.id}/retry`))}>
                      Retry
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => download(a)}>
                    Download
                  </Button>
                  <UploadButton
                    kind={{ ...KINDS.find((k) => k.kind === a.kind), base }}
                    accept={KINDS.find((k) => k.kind === a.kind).accept}
                    artifactId={a.id}
                    label="Replace"
                    onUploaded={refreshAll}
                    onError={setError}
                  />
                  <Button variant="danger" onClick={() => remove(a)}>
                    Delete
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {sessions.length > 0 && (
        <Card>
          <h2 className="mb-3 font-medium text-slate-900">Practice sessions</h2>
          <ul className="divide-y divide-slate-100">
            {sessions.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <Link to={`/projects/${projectId}/sessions/${s.id}`} className="text-sm font-medium text-indigo-700 hover:underline">
                  {s.scope === 'full' ? 'Full project viva' : 'Focused practice'} · {s.question_count} questions
                </Link>
                <span className="flex items-center gap-2 text-xs text-slate-500">
                  <StatusChip status={s.status} />
                  {new Date(s.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
