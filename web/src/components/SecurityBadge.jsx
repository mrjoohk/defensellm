export default function SecurityBadge({ label, size = 'normal' }) {
  const cls = {
    PUBLIC: 'badge-public',
    INTERNAL: 'badge-internal',
    RESTRICTED: 'badge-restricted',
    SECRET: 'badge-secret',
  }[label] || 'badge-public'

  return <span className={`badge ${cls}`}>{label || 'UNKNOWN'}</span>
}
