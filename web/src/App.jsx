import { useState, useEffect } from 'react'
import QueryPage from './pages/QueryPage.jsx'
import IndexPage from './pages/IndexPage.jsx'
import AuditPage from './pages/AuditPage.jsx'

const PAGES = [
  { id: 'query', label: 'Query' },
  { id: 'index', label: 'Document Index' },
  { id: 'audit', label: 'Audit Console' },
]

function SecurityBadge({ label }) {
  const cls = {
    PUBLIC: 'badge-public',
    INTERNAL: 'badge-internal',
    RESTRICTED: 'badge-restricted',
    SECRET: 'badge-secret',
  }[label] || 'badge-public'
  return <span className={`badge ${cls}`}>{label}</span>
}

export default function App() {
  const [page, setPage] = useState('query')
  const [health, setHealth] = useState(null)
  const [role, setRole] = useState('analyst')
  const [clearance, setClearance] = useState('INTERNAL')

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.ok ? r.json() : null)
      .then(d => setHealth(d))
      .catch(() => setHealth(null))
  }, [])

  const userContext = { role, clearance, user_id: 'u-demo' }

  return (
    <div className="app">
      {/* ── Top bar ── */}
      <header className="topbar">
        <div className="topbar__logo">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <rect x="1" y="1" width="7" height="7" rx="1" stroke="#39d0d0" strokeWidth="1.5"/>
            <rect x="10" y="1" width="7" height="7" rx="1" stroke="#39d0d0" strokeWidth="1.5" opacity=".5"/>
            <rect x="1" y="10" width="7" height="7" rx="1" stroke="#39d0d0" strokeWidth="1.5" opacity=".5"/>
            <rect x="10" y="10" width="7" height="7" rx="1" stroke="#39d0d0" strokeWidth="1.5" opacity=".8"/>
          </svg>
          Defense LLM
        </div>

        <div className="topbar__divider" />

        <nav className="topbar__nav">
          {PAGES.map(p => (
            <button
              key={p.id}
              className={`topbar__nav-btn ${page === p.id ? 'active' : ''}`}
              onClick={() => setPage(p.id)}
            >
              {p.label}
            </button>
          ))}
        </nav>

        <div className="topbar__spacer" />

        <div className="topbar__status">
          {/* Role selector */}
          <span className="text-muted text-small">Role</span>
          <select
            className="composer__select"
            value={role}
            onChange={e => setRole(e.target.value)}
          >
            <option value="admin">admin</option>
            <option value="analyst">analyst</option>
            <option value="air_analyst">air_analyst</option>
            <option value="weapon_analyst">weapon_analyst</option>
            <option value="viewer">viewer</option>
          </select>

          <span className="text-muted text-small">Clearance</span>
          <select
            className="composer__select"
            value={clearance}
            onChange={e => setClearance(e.target.value)}
          >
            <option value="PUBLIC">PUBLIC</option>
            <option value="INTERNAL">INTERNAL</option>
            <option value="RESTRICTED">RESTRICTED</option>
            <option value="SECRET">SECRET</option>
          </select>

          <SecurityBadge label={clearance} />

          <div className="topbar__divider" />

          {health ? (
            <span className="badge badge-ok">API OK</span>
          ) : (
            <span className="badge badge-error">API DOWN</span>
          )}

          {health && (
            <>
              <span className="badge badge-mono" style={{ textTransform: 'uppercase' }}>
                {health.llm_adapter || 'qwen'}
              </span>
              <span className="text-mono text-small text-muted">
                {health.model}
              </span>
            </>
          )}
        </div>
      </header>

      {/* ── Page content ── */}
      <main className="main-content">
        {page === 'query' && (
          <QueryPage userContext={userContext} health={health} />
        )}
        {page === 'index' && (
          <IndexPage userContext={userContext} />
        )}
        {page === 'audit' && (
          <AuditPage />
        )}
      </main>
    </div>
  )
}
