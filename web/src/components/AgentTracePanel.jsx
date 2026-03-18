import { useState } from 'react'

function TraceRow({ entry }) {
  const [expanded, setExpanded] = useState(false)
  const hasError = Boolean(entry.error)

  const argsFull = entry.args_summary || ''
  const argsShort = argsFull.length > 90 ? argsFull.slice(0, 90) + '…' : argsFull

  return (
    <div className={`trace-row${hasError ? ' trace-row--error' : ''}`}>
      <div className="trace-row__header">
        <span className="badge badge-mono">Turn {entry.turn + 1}</span>
        <span className={`badge ${hasError ? 'badge-error' : 'badge-info'}`}>
          {entry.tool_name}
        </span>
        {hasError && <span className="badge badge-error">ERR</span>}
      </div>

      <div
        className="trace-row__args"
        style={{ cursor: argsFull.length > 90 ? 'pointer' : 'default' }}
        onClick={() => argsFull.length > 90 && setExpanded(v => !v)}
      >
        <span className="trace-row__label">args</span>
        <span className="trace-row__value">
          {expanded ? argsFull : argsShort}
        </span>
      </div>

      <div className="trace-row__result">
        <span className="trace-row__label">result</span>
        <span className={`trace-row__value${hasError ? ' text-error' : ''}`}>
          {entry.error || entry.result_summary}
        </span>
      </div>
    </div>
  )
}

export default function AgentTracePanel({ toolCallLog }) {
  const [open, setOpen] = useState(true)

  if (!toolCallLog || toolCallLog.length === 0) return null

  return (
    <div className="inspector-section">
      <div className="inspector-section__header" onClick={() => setOpen(!open)} style={{ cursor: 'pointer' }}>
        <span className="inspector-section__title">Agent Trace</span>
        <span className="inspector-section__count">{toolCallLog.length} turns {open ? '▲' : '▼'}</span>
      </div>
      {open && (
        <div className="inspector-section__body">
          {toolCallLog.map((entry, i) => (
            <TraceRow key={i} entry={entry} />
          ))}
        </div>
      )}
    </div>
  )
}
