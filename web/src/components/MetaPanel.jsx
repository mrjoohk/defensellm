import { useState } from 'react'
import SecurityBadge from './SecurityBadge.jsx'

export default function MetaPanel({ response }) {
  const [open, setOpen] = useState(true)
  const [showJson, setShowJson] = useState(false)

  if (!response) return null

  const { request_id, security_label, version, hash, error } = response

  return (
    <>
      <div className="inspector-section">
        <div className="inspector-section__header" onClick={() => setOpen(!open)}>
          <span className="inspector-section__title">Request Metadata</span>
          <span className="inspector-section__count">{open ? '▲' : '▼'}</span>
        </div>
        {open && (
          <div className="inspector-section__body">
            <div className="meta-row">
              <span className="meta-row__key">request_id</span>
              <span className="meta-row__val">{request_id}</span>
            </div>
            <div className="meta-row">
              <span className="meta-row__key">security_label</span>
              <span className="meta-row__val"><SecurityBadge label={security_label} /></span>
            </div>
            {error && (
              <div className="meta-row">
                <span className="meta-row__key">error</span>
                <span className="meta-row__val"><span className="badge badge-error">{error}</span></span>
              </div>
            )}
            {version && (
              <>
                <div className="meta-row">
                  <span className="meta-row__key">model</span>
                  <span className="meta-row__val">{version.model}</span>
                </div>
                <div className="meta-row">
                  <span className="meta-row__key">index</span>
                  <span className="meta-row__val">{version.index}</span>
                </div>
                <div className="meta-row">
                  <span className="meta-row__key">db</span>
                  <span className="meta-row__val">{version.db}</span>
                </div>
              </>
            )}
            {hash && (
              <div className="meta-row">
                <span className="meta-row__key">hash</span>
                <span className="meta-row__val" style={{ wordBreak: 'break-all', fontSize: 10 }}>
                  {hash}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="inspector-section">
        <div
          className="inspector-section__header"
          onClick={() => setShowJson(!showJson)}
          style={{ cursor: 'pointer' }}
        >
          <span className="inspector-section__title">Raw JSON</span>
          <span className="inspector-section__count">{showJson ? 'hide' : 'show'}</span>
        </div>
        {showJson && (
          <div className="inspector-section__body">
            <pre className="json-block">
              {JSON.stringify(response, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </>
  )
}
