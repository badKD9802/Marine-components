
/**
 * auth.js
 * 사용자 인증 및 로그인/로그아웃 관리
 */

/**
 * 로그인 처리
 */
async function handleLogin() {
    const pw = document.getElementById('passwordInput').value;
    const errEl = document.getElementById('loginError');
    errEl.style.display = 'none';
    try {
        const res = await fetch(API_BASE + '/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: pw }),
        });
        if (!res.ok) { const d = await res.json(); errEl.textContent = d.detail || '로그인 실패'; errEl.style.display = 'block'; return; }
        const d = await res.json();
        authToken = d.token;
        sessionStorage.setItem('admin_token', authToken);
        showDashboard();
    } catch { errEl.textContent = '서버 연결 실패'; errEl.style.display = 'block'; }
}

/**
 * 로그아웃 처리
 */
function handleLogout() {
    authToken = '';
    sessionStorage.removeItem('admin_token');
    document.getElementById('loginView').style.display = 'flex';
    document.getElementById('dashboardView').style.display = 'none';
}

/**
 * 대시보드 표시
 */
function showDashboard() {
    document.getElementById('loginView').style.display = 'none';
    document.getElementById('dashboardView').style.display = 'block';
    loadDocuments();
}

/**
 * 로그아웃 별칭 (backward compatibility)
 */
function logout() {
    handleLogout();
}

/**
 * 로그인 화면 표시 (backward compatibility)
 */
function showLogin() {
    handleLogout();
}
