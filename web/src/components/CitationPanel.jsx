import { useState } from 'react'

// Utility to highlight snippets based on the query string
function highlightText(text, queryStr) {
  if (!text || !queryStr) return text;

  const stopWords = new Set(['is', 'it', 'in', 'on', 'at', 'to', 'of', 'and', 'or', 'for', 'the', 'a', 'an', '이', '그', '저', '은', '는', '이', '가', '을', '를', '에', '에게']);

  // Extract keywords (filter out very short words, punctuation, and stopwords)
  const tokens = queryStr
    .split(/[\s,.'"?()]+/)
    .map(t => t.trim())
    .filter(t => t.length > 2 || (t.length > 1 && !stopWords.has(t.toLowerCase())))
    .sort((a, b) => b.length - a.length); // match longer words first

  if (tokens.length === 0) return text;

  // Build a safe regex string
  const escapeRegExp = (str) => str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regexStr = tokens.map(escapeRegExp).join('|');
  const regex = new RegExp(`(${regexStr})`, 'gi');

  const parts = text.split(regex);
  const result = [];

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (!part) continue;

    // Check if part is a match
    const isMatch = tokens.some(t => t.toLowerCase() === part.toLowerCase());
    if (isMatch) {
      result.push(
        <mark key={i} style={{ backgroundColor: 'rgba(57, 208, 208, 0.3)', color: 'inherit', padding: '0 2px', borderRadius: '2px' }}>
          {part}
        </mark>
      );
    } else {
      result.push(part);
    }
  }
  return result;
}

function CitationRow({ citation, index, query }) {
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
            <div className="citation-row__snippet">{highlightText(citation.snippet, query)}</div>
          ) : (
            <div
              className="citation-row__snippet"
              style={{ cursor: 'pointer', WebkitLineClamp: 3, overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical' }}
              onClick={() => setExpanded(true)}
            >
              {highlightText(citation.snippet, query)}
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

export default function CitationPanel({ citations = [], query }) {
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
            <CitationRow key={i} citation={c} index={i} query={query} />
          ))}
        </div>
      )}
    </div>
  )
}
