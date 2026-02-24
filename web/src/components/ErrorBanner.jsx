const ERROR_CONFIG = {
  E_AUTH: {
    cls: 'banner-error',
    icon: '🔒',
    title: '접근 거부 (E_AUTH)',
    hint: '요청한 리소스에 대한 접근 권한이 없습니다. 보안 등급 또는 역할을 확인하세요.',
  },
  E_VALIDATION: {
    cls: 'banner-warn',
    icon: '⚠️',
    title: '검증 오류 (E_VALIDATION)',
    hint: '요청 파라미터 또는 도구 스키마에 오류가 있습니다. 입력을 수정하거나 관리자에게 문의하세요.',
  },
  E_INTERNAL: {
    cls: 'banner-error',
    icon: '💥',
    title: '내부 오류 (E_INTERNAL)',
    hint: '시스템 내부 오류가 발생했습니다. request_id를 기록하고 관리자에게 지원을 요청하세요.',
  },
}

export default function ErrorBanner({ errorCode, requestId }) {
  if (!errorCode) return null

  const cfg = ERROR_CONFIG[errorCode] || {
    cls: 'banner-warn',
    icon: '❓',
    title: `오류: ${errorCode}`,
    hint: '알 수 없는 오류입니다.',
  }

  return (
    <div className={`banner ${cfg.cls}`}>
      <span className="banner__icon">{cfg.icon}</span>
      <div>
        <div className="banner__title">{cfg.title}</div>
        <div className="banner__body">{cfg.hint}</div>
        {requestId && (
          <div className="banner__body" style={{ marginTop: 4 }}>
            request_id: {requestId}
          </div>
        )}
      </div>
    </div>
  )
}
