export function Button({ variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300',
    secondary: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
    danger: 'bg-red-600 text-white hover:bg-red-700',
    ghost: 'text-slate-600 hover:bg-slate-100',
  }
  return (
    <button
      className={`rounded-md px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...props}
    />
  )
}

export function Input({ label, id, ...props }) {
  return (
    <label htmlFor={id} className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        id={id}
        className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 focus:outline-none"
        {...props}
      />
    </label>
  )
}

export function Alert({ kind = 'error', children }) {
  if (!children) return null
  const styles = kind === 'error' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'
  return <p className={`rounded-md border px-3 py-2 text-sm ${styles}`}>{children}</p>
}

export function Card({ className = '', ...props }) {
  return <div className={`rounded-lg border border-slate-200 bg-white p-5 shadow-sm ${className}`} {...props} />
}
