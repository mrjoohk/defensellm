import { useState, useRef } from 'react'
import SecurityBadge from '../components/SecurityBadge.jsx'
import CitationPanel from '../components/CitationPanel.jsx'
import MetaPanel from '../components/MetaPanel.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'

const FIELDS = ['air', 'weapon', 'ground', 'sensor', 'comm']

const EXAMPLE_QUERIES = [
  'KF-21 항공기 최대 순항 고도는?',
  '무기 적재 중량 제한 규정 문서를 검색하세요.',
  'F-15K 플랫폼 성능 제원을 조회하세요.',
  '정비 절차 매뉴얼에서 엔진 관련 항목을 찾아주세요.',
]

export default function QueryPage({ userContext, health }) {
  const [question, setQuestion] = useState('')
  const [fieldFilters, setFieldFilters] = useState([])
  const [topK, setTopK] = useState(5)
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState(null)
  const [fetchError, setFetchError] = useState(null)
  const textareaRef = useRef(null)

  const toggleField = (f) => {
    setFieldFilters(prev =>
      prev.includes(f) ? prev.filter(x => x !== f) : [...prev, f]
    )
  }

  const copyBundle = () => {
    if (!response) return
    const bundle = {
      request_id: response.request_id,
      hash: response.hash,
      version: response.version,
      citations: response.citations,
    }
    navigator.clipboard?.writeText(JSON.stringify(bundle, null, 2))
  }

  const openAudit = () => {
    if (!response) return
    // Switch to audit page with this request_id via a custom event
    window.dispatchEvent(new CustomEvent('openAudit', { detail: response.request_id }))
  }

  const submit = async () => {
    if (!question.trim() || loading) return
    setLoading(true)
    setResponse(null)
    setFetchError(null)

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          user: userContext,
          field_filters: fieldFilters,
          top_k: topK,
          show_citations: true,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setFetchError(data.detail || `HTTP ${res.status}`)
      } else {
        setResponse(data)
      }
    } catch (e) {
      setFetchError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit()
  }

  return (
    <div className="query-layout">
      {/* ── Left: Composer + Answer ── */}
      <div className="query-layout__main">
        {/* Status strip */}
        <div className="flex-center gap-8 mb" style={{ marginBottom: 12, gap: 10, flexWrap: 'wrap' }}>
          <span className="badge badge-mono">
            {userContext.role}
          </span>
          <SecurityBadge label={userContext.clearance} />
          {health && (
            <>
              <span className="badge badge-mono">{health.model}</span>
              <span className="badge badge-mono">{health.index_version}</span>
              <span className="badge badge-mono">{health.chunks_indexed} chunks</span>
            </>
          )}
        </div>

        {/* Composer */}
        <div className="composer">
          <textarea
            ref={textareaRef}
            className="composer__textarea"
            placeholder="질문을 입력하세요… (Ctrl+Enter로 전송)"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={handleKey}
            rows={3}
          />

          {/* Field filter chips */}
          <div className="composer__controls">
            <span className="composer__label">Field</span>
            {FIELDS.map(f => (
              <button
                key={f}
                className={`btn ${fieldFilters.includes(f) ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '3px 10px', fontSize: 11 }}
                onClick={() => toggleField(f)}
              >
                {f}
              </button>
            ))}

            <div className="topbar__divider" />

            <span className="composer__label">top_k</span>
            <input
              type="number"
              className="composer__input-sm"
              value={topK}
              min={1} max={20}
              onChange={e => setTopK(Number(e.target.value))}
            />

            <div className="composer__spacer" />

            <button
              className="btn btn-primary"
              onClick={submit}
              disabled={loading || !question.trim()}
            >
              {loading ? <span className="spinner" /> : '▶ Run'}
            </button>
          </div>

          {/* Example queries */}
          <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span className="composer__label" style={{ alignSelf: 'center' }}>예시</span>
            {EXAMPLE_QUERIES.map((q, i) => (
              <button
                key={i}
                className="btn btn-secondary"
                style={{ padding: '2px 8px', fontSize: 11 }}
                onClick={() => setQuestion(q)}
              >
                {q.length > 28 ? q.slice(0, 28) + '…' : q}
              </button>
            ))}
          </div>
        </div>

        {/* Fetch-level error (network / server) */}
        {fetchError && (
          <div className="banner banner-error">
            <span className="banner__icon">🌐</span>
            <div>
              <div className="banner__title">요청 실패</div>
              <div className="banner__body">{fetchError}</div>
            </div>
          </div>
        )}

        {/* Response */}
        {response && (
          <>
            {/* Error from backend */}
            <ErrorBanner errorCode={response.error} requestId={response.request_id} />

            {/* Answer card */}
            <div className="answer-card">
              <div className="answer-card__header">
                <SecurityBadge label={response.security_label} />
                {response.error && (
                  <span className="badge badge-error">{response.error}</span>
                )}
                <span className="answer-card__request-id">{response.request_id}</span>
              </div>

              <div className="answer-card__body">
                {response.data?.answer || '(응답 없음)'}
              </div>

              <div className="answer-card__footer">
                <span className="text-mono text-small text-muted">
                  citations: {response.citations?.length ?? 0}
                </span>
                <div style={{ flex: 1 }} />
                <button className="btn btn-secondary" style={{ padding: '3px 10px', fontSize: 11 }}
                  onClick={copyBundle}>
                  Copy Bundle
                </button>
                <button className="btn btn-secondary" style={{ padding: '3px 10px', fontSize: 11 }}
                  onClick={openAudit}>
                  View Audit
                </button>
              </div>
            </div>
          </>
        )}

        {/* Empty state */}
        {!response && !loading && !fetchError && (
          <div className="empty-state">
            <div className="empty-state__icon">🔍</div>
            <div className="empty-state__text">질문을 입력하고 Run을 눌러 쿼리를 실행하세요.</div>
          </div>
        )}
      </div>

      {/* ── Right: Inspector ── */}
      <div className="query-layout__inspector">
        {response ? (
          <>
            <CitationPanel citations={response.citations || []} />
            <MetaPanel response={response} />
          </>
        ) : (
          <div className="inspector-section">
            <div className="inspector-section__header">
              <span className="inspector-section__title">Inspector</span>
            </div>
            <div className="inspector-section__body">
              <div className="empty-state" style={{ padding: '24px 0' }}>
                <div className="empty-state__icon" style={{ fontSize: 20 }}>📋</div>
                <div className="empty-state__text">쿼리 실행 후 Citations 및 메타데이터가 여기 표시됩니다.</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
