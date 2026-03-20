import { useState, useRef } from 'react'
import SecurityBadge from '../components/SecurityBadge.jsx'
import CitationPanel from '../components/CitationPanel.jsx'
import MetaPanel from '../components/MetaPanel.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import AgentTracePanel from '../components/AgentTracePanel.jsx'

const FIELDS = ['air', 'weapon', 'ground', 'sensor', 'comm']

const EXAMPLE_QUERIES = [
  'KF-21 항공기 최대 순항 고도는?',
  '무기 적재 중량 제한 규정 문서를 검색하세요.',
  'F-15K 플랫폼 성능 제원을 조회하세요.',
  '정비 절차 매뉴얼에서 엔진 관련 항목을 찾아주세요.',
  'KF-21 탑재중량 6000kg의 30%를 계산해줘.',
  'sin(45도)를 라디안으로 계산해줘.',
]

const EXAMPLE_BRIEFING_DATA = `unit_id,type,location_lat,location_lon,activity,equipment,time
E-001,기갑,37.52,127.01,북동방향 기동,T-80 전차,2026-03-20T14:00
E-002,기계화보병,37.54,127.03,진지 점령 중,BMP-3,2026-03-20T14:10
E-003,포병,37.48,126.95,사격 준비,2S19 자주포,2026-03-20T14:15
F-001,아군기갑,37.50,127.05,방어진지 구축,K2 전차,2026-03-20T14:05
F-002,아군보병,37.51,127.08,경계 중,K21 IFV,2026-03-20T14:12`

export default function QueryPage({ userContext, health }) {
  const [question, setQuestion] = useState('')
  const [fieldFilters, setFieldFilters] = useState([])
  const [topK, setTopK] = useState(5)
  const [onlineMode, setOnlineMode] = useState(false)
  const [agentMode, setAgentMode] = useState(false)
  const [maxAgentTurns, setMaxAgentTurns] = useState(10)
  // Briefing mode
  const [briefingMode, setBriefingMode] = useState(false)
  const [briefingData, setBriefingData] = useState('')
  const [includeCoa, setIncludeCoa] = useState(true)
  const [searchDoctrine, setSearchDoctrine] = useState(false)
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState(null)
  const [fetchError, setFetchError] = useState(null)
  const [submittedQuery, setSubmittedQuery] = useState('')
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
    const isReady = briefingMode ? briefingData.trim() : question.trim()
    if (!isReady || loading) return
    setLoading(true)
    setResponse(null)
    setFetchError(null)
    setSubmittedQuery(briefingMode ? '전장 브리핑 요청' : question)

    try {
      let res
      if (briefingMode) {
        res = await fetch('/api/briefing', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            raw_data: briefingData,
            format_hint: 'auto',
            question: question.trim() || '전장 상황을 브리핑해주세요.',
            search_doctrine: searchDoctrine,
            include_coa: includeCoa,
            user: userContext,
          }),
        })
      } else {
        res = await fetch('/api/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question,
            user: userContext,
            field_filters: fieldFilters,
            top_k: topK,
            show_citations: true,
            online_mode: onlineMode,
            agent_mode: agentMode,
            max_agent_turns: maxAgentTurns,
          }),
        })
      }
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

        {/* Mode toggle */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
          <button
            className={`btn ${!briefingMode ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '4px 14px', fontSize: 12 }}
            onClick={() => setBriefingMode(false)}
          >
            🔍 Q&A / Tool
          </button>
          <button
            className={`btn ${briefingMode ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '4px 14px', fontSize: 12 }}
            onClick={() => setBriefingMode(true)}
          >
            📋 Briefing
          </button>
        </div>

        {/* Composer */}
        <div className="composer">
          <textarea
            ref={textareaRef}
            className="composer__textarea"
            placeholder={briefingMode
              ? '브리핑 요청 / 특정 질문 (선택, 생략 시 기본 브리핑)'
              : '질문을 입력하세요… (Ctrl+Enter로 전송)'}
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={handleKey}
            rows={briefingMode ? 2 : 3}
          />

          {/* Briefing data input */}
          {briefingMode && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="composer__label">전장 데이터 (CSV / JSON)</span>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '2px 8px', fontSize: 10 }}
                  onClick={() => setBriefingData(EXAMPLE_BRIEFING_DATA)}
                >
                  예시 데이터 삽입
                </button>
              </div>
              <textarea
                className="composer__textarea"
                placeholder="CSV 또는 JSON 형식의 전장 상황 데이터를 붙여넣으세요…"
                value={briefingData}
                onChange={e => setBriefingData(e.target.value)}
                rows={6}
                style={{ fontFamily: 'monospace', fontSize: 11 }}
              />
            </div>
          )}

          {/* Field filter chips */}
          <div className="composer__controls">
            {briefingMode ? (
              <>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: includeCoa ? 'var(--cyan)' : '#aaa' }}>
                  <input type="checkbox" checked={includeCoa} onChange={e => setIncludeCoa(e.target.checked)} />
                  COA 권고 포함
                </label>
                <div className="topbar__divider" />
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#aaa' }}>
                  <input type="checkbox" checked={searchDoctrine} onChange={e => setSearchDoctrine(e.target.checked)} />
                  교범 검색
                </label>
              </>
            ) : (
              <>
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

                <div className="topbar__divider" />
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: '#aaa' }}>
                  <input type="checkbox" checked={onlineMode} onChange={e => setOnlineMode(e.target.checked)} />
                  Online Fallback
                </label>
                <div className="topbar__divider" />
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: agentMode ? 'var(--cyan)' : '#aaa' }}>
                  <input type="checkbox" checked={agentMode} onChange={e => setAgentMode(e.target.checked)} />
                  Agent Mode
                </label>
                {agentMode && (
                  <>
                    <span className="composer__label">Turns</span>
                    <input type="number" className="composer__input-sm" value={maxAgentTurns} min={1} max={30}
                      onChange={e => setMaxAgentTurns(Number(e.target.value))} />
                  </>
                )}
              </>
            )}

            <div className="composer__spacer" />

            <button
              className="btn btn-primary"
              onClick={submit}
              disabled={loading || (briefingMode ? !briefingData.trim() : !question.trim())}
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

              <div className="answer-card__body" style={{ whiteSpace: 'pre-wrap' }}>
                {response.data?.briefing
                  ? response.data.briefing
                  : (response.data?.answer || '(응답 없음)')}
              </div>

              {/* COA 결과 (briefing mode) */}
              {response.data?.coa && (
                <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(57,208,208,0.06)', borderRadius: 6, borderLeft: '3px solid var(--cyan)' }}>
                  <div style={{ fontSize: 11, color: 'var(--cyan)', marginBottom: 6, fontWeight: 600 }}>COA 권고안</div>
                  <div style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{response.data.coa}</div>
                </div>
              )}

              {/* Briefing metadata */}
              {response.data?.row_count != null && (
                <div style={{ marginTop: 8, fontSize: 11, color: '#888' }}>
                  데이터: {response.data.row_count}개 레코드 | 필드: {(response.data.columns || []).join(', ')}
                </div>
              )}

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
            <CitationPanel citations={response.citations || []} query={submittedQuery} answer={response?.data?.answer} />
            <AgentTracePanel toolCallLog={response.tool_call_log} />
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
