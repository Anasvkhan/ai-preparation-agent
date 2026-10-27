import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api, { errorMessage } from '../api/client'
import StatusChip from '../components/StatusChip'
import { Alert, Card } from '../components/ui'

const DIFFICULTY = {
  easy: 'bg-sky-100 text-sky-800',
  medium: 'bg-violet-100 text-violet-800',
  hard: 'bg-rose-100 text-rose-800',
}

function Citation({ c, open, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      title={c.note || 'Show the cited text'}
      className={`rounded-md border px-2 py-1 text-xs ${
        !c.available
          ? 'border-slate-200 bg-slate-100 text-slate-500 line-through'
          : open
            ? 'border-indigo-600 bg-indigo-600 text-white'
            : 'border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
      }`}
    >
      {c.label}
    </button>
  )
}

function Question({ q }) {
  const [showPoints, setShowPoints] = useState(false)
  const [openCitation, setOpenCitation] = useState(null)
  const cited = openCitation === null ? null : q.citations[openCitation]
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold text-slate-500">Q{q.order}</span>
        <span className={`rounded-full px-2 py-0.5 font-medium ${DIFFICULTY[q.difficulty]}`}>{q.difficulty}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">{q.topic}</span>
      </div>
      <p className="mt-2 font-medium text-slate-900">{q.text}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {q.citations.map((c, i) => (
          <Citation key={i} c={c} open={openCitation === i} onToggle={() => setOpenCitation(openCitation === i ? null : i)} />
        ))}
      </div>
      {cited && (
        <div className="mt-2 rounded-md bg-slate-50 p-3 text-xs text-slate-600">
          {!cited.available && <p className="mb-1 font-medium text-slate-500">{cited.note} (saved excerpt shown)</p>}
          <blockquote className="border-l-2 border-indigo-200 pl-3 font-[inherit] whitespace-pre-wrap">{cited.quote}</blockquote>
        </div>
      )}
      <button type="button" onClick={() => setShowPoints(!showPoints)} className="mt-3 text-xs font-medium text-indigo-600 hover:underline">
        {showPoints ? 'Hide' : 'Show'} expected points
      </button>
      {showPoints && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
          {q.expected_points.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export default function SessionPage() {
  const { projectId, sessionId } = useParams()
  const [session, setSession] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(
    () =>
      api
        .get(`/projects/${projectId}/sessions/${sessionId}`)
        .then(({ data }) => setSession(data))
        .catch((err) => setError(errorMessage(err))),
    [projectId, sessionId],
  )

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (session?.status !== 'generating') return
    const timer = setInterval(load, 3000)
    return () => clearInterval(timer)
  }, [session?.status, load])

  if (!session) return error ? <Alert>{error}</Alert> : <p className="text-slate-500">Loading…</p>

  const focus = session.focus
  const focusText =
    session.scope === 'full'
      ? 'Full project viva'
      : `Focused: ${[...focus.topics, focus.query].filter(Boolean).join(', ') || `${focus.artifact_ids.length} file(s)`}`

  return (
    <div className="space-y-6">
      <div>
        <Link to={`/projects/${projectId}`} className="text-sm text-indigo-600 hover:underline">
          ← Back to project
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900">Viva questions</h1>
          <StatusChip status={session.status} />
        </div>
        <p className="text-sm text-slate-500">
          {focusText} · {session.question_count} questions · {new Date(session.created_at).toLocaleString()}
        </p>
      </div>

      {session.status === 'generating' && (
        <Card>
          <p className="text-slate-700">Generating questions from your evidence… this usually takes under a minute.</p>
        </Card>
      )}
      {session.status === 'failed' && (
        <Alert>
          {session.error || 'Question generation failed.'}{' '}
          <Link to={`/projects/${projectId}/practice`} className="underline">
            Try different settings
          </Link>
        </Alert>
      )}
      {session.status === 'ready' && (
        <div className="space-y-4">
          {session.questions.map((q) => (
            <Question key={q.id} q={q} />
          ))}
        </div>
      )}
    </div>
  )
}
