import { useState, useEffect } from 'react'
import SecurityBadge from '../components/SecurityBadge.jsx'

function truncate(str, n) {
  if (!str) return '—'
  return str.length > n ? str.slice(0, n) + '…' : str
}

function formatTs(ts) {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString('ko-KR', { hour12: false })
  } catch {
    return ts
  }
}

function DetailDrawer({ record, onClose }) {
  if (!record) return null

  const citations = Array.isArray(record.citations) ? record.citations : []

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0, width: 440,
      background: 'var(--bg-surface)', borderLeft: '1px solid var(--border)',
      overflow: 'auto', zIndex: 200, padding: 20,
      boxShadow: '-4px 0 24px rgba(0,0,0,.4)',
      animation: 'slideIn 200ms ease',
    }}>
      <div className="flex-between" style={{ marginBottom: 16 }}>
        <span className="card__title" style={{ margin: 0 }}>Audit Detail</span>
        <button className="btn btn-secondary" style={{ padding: '3px 10px' }} onClick={onClose}>
          ✕ Close
        </button>
      </div>

      <div className="meta-row">
        <span className="meta-row__key">request_id</span>
        <span className="meta-row__val" style={{ wordBreak: 'break-all' }}>{record.request_id}</span>
      </div>
      <div className="meta-row">
        <span className="meta-row__key">audit_id</span>
        <span className="meta-row__val" style={{ wordBreak: 'break-all', fontSize: 10 }}>{record.audit_id}</span>
      </div>
      <div className="meta-row">
        <span className="meta-row__key">user_id</span>
        <span className="meta-row__val">{record.user_id || '—'}</span>
      </div>
      <div className="meta-row">
        <span className="meta-row__key">timestamp</span>
        <span className="meta-row__val">{formatTs(record.timestamp)}</span>
      </div>
      <div className="meta-row">
        <span className="meta-row__key">model</span>
        <span className="meta-row__val">{record.model_version || '—'}</span>
      </div>
      <div className="meta-row">
        <span className="meta-row__key">index</span>
        <span className="meta-row__val">{record.index_version || '—'}</span>
      </div>
      <div className="meta-row">
        <span className="meta-row__key">error_code</span>
        <span className="meta-row__val">
          {record.error_code
            ? <span className="badge badge-error">{record.error_code}</span>
            : <span className="badge badge-ok">none</span>
          }
        </span>
      </div>
      <div className="meta-row">
        <span className="meta-row__key">response_hash</span>
        <span className="meta-row__val" style={{ fontSize: 10, wordBreak: 'break-all' }}>
          {record.response_hash || '—'}
        </span>
      </div>

      <div style={{ marginTop: 16 }}>
        <div className="card__title">Query</div>
        <pre className="json-block" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {record.query || '—'}
        </pre>
      </div>

      {citations.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div className="card__title">Citations ({citations.length})</div>
          {citations.map((c, i) => (
            <div key={i} className="meta-row" style={{ flexDirection: 'column', gap: 4 }}>
              <span className="meta-row__val">
                <span className="text-cyan">{c.doc_id}</span> rev:{c.doc_rev}
                {c.page != null && ` p.${c.page}`}
              </span>
              {c.snippet && (
                <span className="meta-row__val" style={{ fontSize: 10, opacity: 0.7 }}>
                  {truncate(c.snippet, 120)}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AuditPage() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [searchResult, setSearchResult] = useState(null)
  const [searchError, setSearchError] = useState(null)
  const [searching, setSearching] = useState(false)
  const [selected, setSelected] = useState(null)

  const fetchRecent = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/audit/recent?limit=50')
      const data = await res.json()
      if (res.ok) setRecords(data.records || [])
      else setError(data.detail || `HTTP ${res.status}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const searchById = async () => {
    if (!search.trim()) return
    setSearching(true)
    setSearchError(null)
    setSearchResult(null)
    try {
      const res = await fetch(`/api/audit/${encodeURIComponent(search.trim())}`)
      const data = await res.json()
      if (res.ok) {
        setSearchResult(data)
        setSelected(data)
      } else {
        setSearchError(data.detail || `HTTP ${res.status}`)
      }
    } catch (e) {
      setSearchError(e.message)
    } finally {
      setSearching(false)
    }
  }

  useEffect(() => {
    fetchRecent()
    const handler = (e) => {
      setSearch(e.detail)
    }
    window.addEventListener('openAudit', handler)
    return () => window.removeEventListener('openAudit', handler)
  }, [])

  // Auto-search when arriving via openAudit event
  useEffect(() => {
    if (search && !selected) {
      searchById()
    }
  }, [search])

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Search by request_id */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card__title">Request ID 조회</div>
        <div className="flex-center" style={{ gap: 10 }}>
          <input
            className="form-input"
            style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 12 }}
            placeholder="request_id를 입력하세요…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && searchById()}
          />
          <button
            className="btn btn-primary"
            onClick={searchById}
            disabled={searching || !search.trim()}
          >
            {searching ? <span className="spinner" /> : '조회'}
          </button>
        </div>

        {searchError && (
          <div className="banner banner-warn" style={{ marginTop: 10 }}>
            <span className="banner__icon">⚠️</span>
            <div>
              <div className="banner__title">조회 실패</div>
              <div className="banner__body">{searchError}</div>
            </div>
          </div>
        )}
      </div>

      {/* Recent records */}
      <div className="card">
        <div className="flex-between" style={{ marginBottom: 14 }}>
          <div className="card__title" style={{ margin: 0 }}>
            최근 요청 {records.length > 0 && `(${records.length})`}
          </div>
          <button
            className="btn btn-secondary"
            style={{ fontSize: 11, padding: '3px 10px' }}
            onClick={fetchRecent}
            disabled={loading}
          >
            {loading ? <span className="spinner" style={{ width: 12, height: 12 }} /> : '↻ 새로고침'}
          </button>
        </div>

        {error && (
          <div className="banner banner-error">
            <span className="banner__icon">❌</span>
            <div><div className="banner__body">{error}</div></div>
          </div>
        )}

        {records.length === 0 && !loading && !error && (
          <div className="empty-state">
            <div className="empty-state__icon">📋</div>
            <div className="empty-state__text">아직 기록된 요청이 없습니다.</div>
          </div>
        )}

        {records.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table className="audit-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>timestamp</th>
                  <th>request_id</th>
                  <th>user_id</th>
                  <th>query</th>
                  <th>error</th>
                  <th>citations</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, i) => (
                  <tr key={r.audit_id || i} style={{ cursor: 'pointer' }}>
                    <td style={{ color: 'var(--text-muted)', fontSize: 11 }}>{i + 1}</td>
                    <td style={{ whiteSpace: 'nowrap', fontSize: 11 }}>{formatTs(r.timestamp)}</td>
                    <td className="truncate" style={{ maxWidth: 160, color: 'var(--cyan)' }}>
                      {r.request_id}
                    </td>
                    <td>{r.user_id || '—'}</td>
                    <td className="truncate">{truncate(r.query, 50)}</td>
                    <td>
                      {r.error_code
                        ? <span className="badge badge-error">{r.error_code}</span>
                        : <span className="badge badge-ok">ok</span>
                      }
                    </td>
                    <td style={{ color: 'var(--cyan)' }}>
                      {(r.citations || []).length}
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '2px 8px', fontSize: 10 }}
                        onClick={() => setSelected(r)}
                      >
                        Detail
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {selected && (
        <DetailDrawer record={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
