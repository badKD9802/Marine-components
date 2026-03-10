/**
 * HTML 살균 유틸리티 (DOMPurify wrapper).
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
    ADD_ATTR: ['class', 'style', 'target'],
  })
}
