const STYLES = {
  queued: 'bg-slate-100 text-slate-700',
  processing: 'bg-amber-100 text-amber-800',
  ready: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-red-100 text-red-700',
  canceled: 'bg-slate-200 text-slate-600',
  generating: 'bg-amber-100 text-amber-800',
}

export default function StatusChip({ status }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status] || STYLES.queued}`}>
      {(status === 'processing' || status === 'generating') && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
      )}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}
