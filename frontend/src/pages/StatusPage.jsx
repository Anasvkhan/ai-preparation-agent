import { useEffect, useState } from 'react'
import api from '../api/client'

export default function StatusPage() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .get('/health')
      .then((res) => setHealth(res.data))
      .catch((err) => setError(err.message))
  }, [])

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-2xl font-semibold text-slate-900">FYP Viva Preparation Agent</h1>
      <p className="mt-1 text-slate-500">System status</p>

      <div className="mt-6 rounded-lg border border-slate-200 bg-white p-4">
        {error && <p className="text-red-600">Backend not reachable: {error}</p>}
        {!error && !health && <p className="text-slate-500">Checking…</p>}
        {health && (
          <ul className="space-y-2">
            {Object.entries(health.checks).map(([name, value]) => (
              <li key={name} className="flex justify-between gap-4 text-sm">
                <span className="font-medium text-slate-700">{name}</span>
                <span className={String(value).startsWith('error') ? 'text-red-600' : 'text-emerald-600'}>
                  {String(value)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  )
}
