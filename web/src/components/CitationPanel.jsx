import { useState } from 'react'

function CitationRow({ citation, index }) {
  const [expanded, setExpanded] = useState(false)

  const copy = (text) => navigator.clipboard?.writeText(text)

  return (
    <div className="citation-row">
      <div className="citation-row__header">
        <span className="badge badge-info">{index + 1}</span>
        <span className="citation-row__doc-id">{citation.doc_id}</span>
        <span className="citation-row__rev">rev:{citation.doc_rev}</span>
      </div>

      <div className="citation-row__meta">
        {citation.page != null && <span>p.{citation.page}</span>}
        {citation.section_id && <span> · §{citation.section_id}</span>}
      </div>

      {citation.snippet && (
        <>
          {expanded ? (
            <div className="citation-row__snippet">{citation.snippet}</div>
          ) : (
            <div
              className="citation-row__snippet"
              style={{ cursor: 'pointer', WebkitLineClamp: 3, overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical' }}
              onClick={() => setExpanded(true)}
            >
              {citation.snippet}
            </div>
          )}
        </>
      )}

      {citation.snippet_hash && (
        <div className="citation-row__hash">hash:{citation.snippet_hash}</div>
      )}

      <div className="citation-row__actions">
        <button className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: 10 }}
          onClick={() => copy(citation.doc_id)}>
          Copy ID
        </button>
        {citation.snippet_hash && (
          <button className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: 10 }}
            onClick={() => copy(citation.snippet_hash)}>
            Copy Hash
          </button>
        )}
        {expanded && (
          <button className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: 10 }}
            onClick={() => setExpanded(false)}>
            Collapse
          </button>
        )}
      </div>
    </div>
  )
}

export default function CitationPanel({ citations = [] }) {
  const [open, setOpen] = useState(true)

  if (!citations.length) {
    return (
      <div className="inspector-section">
        <div className="inspector-section__header" onClick={() => setOpen(!open)}>
          <span className="inspector-section__title">Citations</span>
          <span className="inspector-section__count">0</span>
        </div>
        {open && (
          <div className="inspector-section__body">
            <div className="text-muted text-small">No citations in this response.</div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="inspector-section">
      <div className="inspector-section__header" onClick={() => setOpen(!open)}>
        <span className="inspector-section__title">Citations</span>
        <span className="inspector-section__count">{citations.length}</span>
      </div>
      {open && (
        <div className="inspector-section__body">
          {citations.map((c, i) => (
            <CitationRow key={i} citation={c} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}
