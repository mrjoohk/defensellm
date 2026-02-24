import { useState, useRef } from 'react'

const FIELD_OPTIONS = ['air', 'weapon', 'ground', 'sensor', 'comm']
const LABEL_OPTIONS = ['PUBLIC', 'INTERNAL', 'RESTRICTED', 'SECRET']

export default function IndexPage() {
  const [file, setFile] = useState(null)
  const [docId, setDocId] = useState('')
  const [docRev, setDocRev] = useState('v1')
  const [title, setTitle] = useState('')
  const [field, setField] = useState('air')
  const [securityLabel, setSecurityLabel] = useState('INTERNAL')
  const [maxTokens, setMaxTokens] = useState(256)
  const [overlap, setOverlap] = useState(32)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) {
      setFile(f)
      if (!title) setTitle(f.name.replace(/\.[^.]+$/, ''))
    }
  }

  const handleFileChange = (e) => {
    const f = e.target.files[0]
    if (f) {
      setFile(f)
      if (!title) setTitle(f.name.replace(/\.[^.]+$/, ''))
    }
  }

  const submit = async () => {
    if (!file || !docId || !title) return
    setLoading(true)
    setResult(null)
    setError(null)

    const form = new FormData()
    form.append('file', file)
    form.append('doc_id', docId)
    form.append('doc_rev', docRev)
    form.append('title', title)
    form.append('field', field)
    form.append('security_label', securityLabel)
    form.append('max_tokens', maxTokens)
    form.append('overlap', overlap)

    try {
      const res = await fetch('/api/index', { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || `HTTP ${res.status}`)
      } else {
        setResult(data)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const isReady = file && docId.trim() && title.trim()

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <div className="card">
        <div className="card__title">Document Ingestion</div>

        {/* Drop zone */}
        <div
          className={`dropzone ${dragOver ? 'active' : ''}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{ marginBottom: 16 }}
        >
          <div className="dropzone__icon">📄</div>
          <div className="dropzone__text">
            파일을 드래그하거나 클릭하여 업로드
          </div>
          <div className="dropzone__sub">.txt, .md 파일 (UTF-8 / CP949)</div>
          {file && (
            <div className="dropzone__file">✓ {file.name} ({(file.size / 1024).toFixed(1)} KB)</div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.text"
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
        </div>

        {/* Metadata form */}
        <div className="form-grid">
          <div className="form-field">
            <label className="form-label">doc_id *</label>
            <input
              className="form-input"
              placeholder="e.g. KF21-MANUAL-001"
              value={docId}
              onChange={e => setDocId(e.target.value)}
            />
          </div>

          <div className="form-field">
            <label className="form-label">doc_rev *</label>
            <input
              className="form-input"
              placeholder="e.g. v1"
              value={docRev}
              onChange={e => setDocRev(e.target.value)}
            />
          </div>

          <div className="form-field form-field--full">
            <label className="form-label">title *</label>
            <input
              className="form-input"
              placeholder="문서 제목"
              value={title}
              onChange={e => setTitle(e.target.value)}
            />
          </div>

          <div className="form-field">
            <label className="form-label">field *</label>
            <select
              className="form-select"
              value={field}
              onChange={e => setField(e.target.value)}
            >
              {FIELD_OPTIONS.map(f => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label className="form-label">security_label *</label>
            <select
              className="form-select"
              value={securityLabel}
              onChange={e => setSecurityLabel(e.target.value)}
            >
              {LABEL_OPTIONS.map(l => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Advanced settings */}
        <div style={{ marginTop: 14 }}>
          <button
            className="btn btn-secondary"
            style={{ fontSize: 11, padding: '3px 10px' }}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? '▲ Advanced' : '▼ Advanced (chunk settings)'}
          </button>

          {showAdvanced && (
            <div className="form-grid" style={{ marginTop: 12 }}>
              <div className="form-field">
                <label className="form-label">max_tokens</label>
                <input
                  type="number"
                  className="form-input"
                  value={maxTokens}
                  min={64} max={1024}
                  onChange={e => setMaxTokens(Number(e.target.value))}
                />
              </div>
              <div className="form-field">
                <label className="form-label">overlap</label>
                <input
                  type="number"
                  className="form-input"
                  value={overlap}
                  min={0} max={128}
                  onChange={e => setOverlap(Number(e.target.value))}
                />
              </div>
            </div>
          )}
        </div>

        <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
          <button
            className="btn btn-primary"
            onClick={submit}
            disabled={!isReady || loading}
          >
            {loading ? <><span className="spinner" /> Indexing…</> : '▶ Index Document'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="banner banner-error">
          <span className="banner__icon">❌</span>
          <div>
            <div className="banner__title">색인 실패</div>
            <div className="banner__body">{error}</div>
          </div>
        </div>
      )}

      {/* Success result */}
      {result && (
        <div className="card">
          <div className="card__title">색인 결과</div>
          <div className="banner banner-success" style={{ marginBottom: 12 }}>
            <span className="banner__icon">✓</span>
            <div>
              <div className="banner__title">색인 완료</div>
              <div className="banner__body">{result.chunks_indexed}개 청크가 색인되었습니다.</div>
            </div>
          </div>

          <div className="meta-row">
            <span className="meta-row__key">doc_id</span>
            <span className="meta-row__val">{result.doc_id}</span>
          </div>
          <div className="meta-row">
            <span className="meta-row__key">doc_rev</span>
            <span className="meta-row__val">{result.doc_rev}</span>
          </div>
          <div className="meta-row">
            <span className="meta-row__key">chunks_indexed</span>
            <span className="meta-row__val text-cyan">{result.chunks_indexed}</span>
          </div>
          <div className="meta-row">
            <span className="meta-row__key">index_version</span>
            <span className="meta-row__val">{result.index_version}</span>
          </div>
          <div className="meta-row">
            <span className="meta-row__key">file_hash</span>
            <span className="meta-row__val" style={{ fontSize: 10, wordBreak: 'break-all' }}>
              {result.file_hash}
            </span>
          </div>
          <div className="meta-row">
            <span className="meta-row__key">status</span>
            <span className="meta-row__val">
              <span className="badge badge-ok">{result.status}</span>
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
