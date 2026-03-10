/**
 * HTML 살균 유틸리티 (DOMPurify wrapper).
 * 백엔드 ReAct Agent가 생성하는 HTML (테이블, 카드, 스타일 등)을 안전하게 렌더링.
 */

let DOMPurifyInstance: any = null

export function sanitizeHtml(dirty: string): string {
  if (typeof window === 'undefined') return dirty

  if (!DOMPurifyInstance) {
    try {
      const DOMPurify = require('dompurify')
      DOMPurifyInstance = DOMPurify
    } catch {
      return dirty
    }
  }

  return DOMPurifyInstance.sanitize(dirty, {
    ADD_TAGS: ['style'],
    ADD_ATTR: ['class', 'style', 'target', 'colspan', 'rowspan', 'align', 'valign', 'width', 'height', 'border'],
    ALLOW_DATA_ATTR: false,
  })
}
