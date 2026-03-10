/**
 * HTML 살균 유틸리티.
 * 백엔드 ReAct Agent가 생성하는 HTML은 신뢰할 수 있으므로
 * 데모 환경에서는 그대로 렌더링한다.
 */

export function sanitizeHtml(dirty: string): string {
  // 백엔드 생성 콘텐츠이므로 그대로 반환 (데모용)
  return dirty
}
