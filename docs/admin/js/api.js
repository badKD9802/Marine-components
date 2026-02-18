
/**
 * api.js
 * API 통신 및 인증 관련 유틸리티
 */

// API 기본 설정
var API_BASE = 'https://adminmarine-component-production.up.railway.app';
var authToken = sessionStorage.getItem('admin_token') || '';

// 전역 상태 변수들
var siteLogoUrl = null;

/**
 * 인증된 API 요청 함수
 * @param {string} path - API 경로
 * @param {object} options - fetch 옵션
 * @returns {Promise<Response>}
 */
async function api(path, options = {}) {
    const res = await fetch(API_BASE + path, {
        ...options,
        headers: { ...(options.headers || {}), 'Authorization': 'Bearer ' + authToken },
    });
    if (res.status === 401) { handleLogout(); throw new Error('인증 만료'); }
    return res;
}

/**
 * HTML 특수문자 이스케이프
 * @param {string} str - 이스케이프할 문자열
 * @returns {string}
 */
function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
