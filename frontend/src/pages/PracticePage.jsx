import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api, { errorMessage } from '../api/client'
import { Alert, Button, Card } from '../components/ui'

export default function PracticePage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [outline, setOutline] = useState(null)
  const [scope, setScope] = useState('full')
  const [artifactIds, setArtifactIds] = useState([])
  const [topics, setTopics] = useState([])
  const [query, setQuery] = useState('')
  const [count, setCount] = useState(10)
  const [error, setError] = useState('')
  const [maxSupported, setMaxSupported] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api
      .get(`/projects/${projectId}/outline`)
      .then(({ data }) => setOutline(data))
      .catch((err) => setError(errorMessage(err)))
  }, [projectId])

  const toggle = (list, setList, value) =>
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    setMaxSupported(null)
    try {
      const body =
        scope === 'full'
          ? { scope, question_count: count }
          : { scope, artifact_ids: artifactIds, topics, query: query || null, question_count: count }
      const { data } = await api.post(`/projects/${projectId}/sessions`, body)
      navigate(`/projects/${projectId}/sessions/${data.id}`)
    } catch (err) {
      setError(errorMessage(err, 'Could not start the session'))
      setMaxSupported(err?.response?.data?.detail?.max_supported ?? null)
    } finally {
      setBusy(false)
    }
  }

  if (!outline) return error ? <Alert>{error}</Alert> : <p className="text-slate-500">Loading…</p>

  return (
    <form onSubmit={submit} className="space-y-6">
      <div>
        <Link to={`/projects/${projectId}`} className="text-sm text-indigo-600 hover:underline">
          ← Back to project
        </Link>
        <h1 className="text-2xl font-semibold text-slate-900">Set up viva practice</h1>
        <p className="text-sm text-slate-500">Questions are generated only from your Ready files, with a source for each one.</p>
      </div>

      {!outline.ready && <Alert>No file is Ready yet. Upload a file and wait for processing to finish.</Alert>}

      <Card className="space-y-3">
        <h2 className="font-medium text-slate-900">Practice mode</h2>
        <label className="flex items-start gap-3">
          <input type="radio" name="scope" checked={scope === 'full'} onChange={() => setScope('full')} className="mt-1" />
          <span>
            <span className="font-medium text-slate-800">Full project viva</span>
            <span className="block text-sm text-slate-500">Questions across all Ready files.</span>
          </span>
        </label>
        <label className="flex items-start gap-3">
          <input type="radio" name="scope" checked={scope === 'focused'} onChange={() => setScope('focused')} className="mt-1" />
          <span>
            <span className="font-medium text-slate-800">Focused practice</span>
            <span className="block text-sm text-slate-500">Pick files, sections or a topic to drill.</span>
          </span>
        </label>
      </Card>

      {scope === 'focused' && (
        <Card className="space-y-4">
          <div>
            <h2 className="font-medium text-slate-900">Files</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              {outline.files.map((f) => (
                <label key={f.id} className="flex items-center gap-2 rounded-md border border-slate-200 px-3 py-1.5 text-sm">
                  <input type="checkbox" checked={artifactIds.includes(f.id)} onChange={() => toggle(artifactIds, setArtifactIds, f.id)} />
                  {f.filename}
                </label>
              ))}
            </div>
          </div>
          <div>
            <h2 className="font-medium text-slate-900">Sections / topics</h2>
            <div className="mt-2 space-y-3">
              {outline.files.map((f) => (
                <div key={f.id}>
                  <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">{f.filename}</p>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {f.topics.map((t) => (
                      <button
                        type="button"
                        key={t.topic}
                        onClick={() => toggle(topics, setTopics, t.topic)}
                        className={`rounded-full border px-3 py-1 text-xs ${
                          topics.includes(t.topic)
                            ? 'border-indigo-600 bg-indigo-600 text-white'
                            : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        {t.topic}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <label className="block">
            <span className="font-medium text-slate-900">Or describe a topic</span>
            <input
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="e.g. security and privacy of student data"
              value={query}
              maxLength={200}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </Card>
      )}

      <Card className="space-y-2">
        <label htmlFor="count" className="flex items-center justify-between">
          <span className="font-medium text-slate-900">Number of questions</span>
          <span className="text-lg font-semibold text-indigo-700">{count}</span>
        </label>
        <input id="count" type="range" min={10} max={20} step={1} value={count}
          onChange={(e) => setCount(Number(e.target.value))} className="w-full accent-indigo-600" />
        <div className="flex justify-between text-xs text-slate-500">
          <span>10</span>
          <span>20</span>
        </div>
      </Card>

      <Alert>{error}</Alert>

      <div className="flex flex-wrap gap-3">
        {maxSupported >= 10 && maxSupported < count && (
          <Button type="button" variant="secondary" onClick={() => setCount(maxSupported)}>
            Use {maxSupported} questions instead
          </Button>
        )}
        <Button type="submit" disabled={busy || !outline.ready} className="w-full sm:w-auto">
          {busy ? 'Starting…' : 'Generate questions'}
        </Button>
      </div>
    </form>
  )
}
