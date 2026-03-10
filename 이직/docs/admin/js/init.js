
/**
 * init.js
 * 애플리케이션 초기화, 이벤트 리스너, 탭 전환
 */

/**
 * 업로드 카드 설정
 */
function setupUploadCard(cardId, inputId, purpose) {
    const card = document.getElementById(cardId);
    const input = document.getElementById(inputId);
    card.addEventListener('click', e => { if (e.target.tagName !== 'INPUT') input.click(); });
    card.addEventListener('dragover', e => { e.preventDefault(); card.classList.add('dragover'); });
    card.addEventListener('dragleave', () => card.classList.remove('dragover'));
    card.addEventListener('drop', e => { e.preventDefault(); card.classList.remove('dragover'); handleFiles(e.dataTransfer.files, purpose); });
    input.addEventListener('change', e => { handleFiles(e.target.files, purpose); e.target.value = ''; });
}

/**
 * 탭 전환
 */
function switchTab(tab) {
    const tabMap = { guide: 0, products: 1, inquiry: 2, mail: 3, rag: 4, docs: 5, homepage: 6, logs: 7 };
    document.querySelectorAll('.tab-nav button').forEach((btn, i) => {
        btn.classList.toggle('active', i === tabMap[tab]);
    });
    document.getElementById('tabGuide').classList.toggle('active', tab === 'guide');
    document.getElementById('tabProducts').classList.toggle('active', tab === 'products');
    document.getElementById('tabDocs').classList.toggle('active', tab === 'docs');
    document.getElementById('tabRag').classList.toggle('active', tab === 'rag');
    document.getElementById('tabMail').classList.toggle('active', tab === 'mail');
    document.getElementById('tabInquiry').classList.toggle('active', tab === 'inquiry');
    document.getElementById('tabHomepage').classList.toggle('active', tab === 'homepage');
    document.getElementById('tabLogs').classList.toggle('active', tab === 'logs');
    if (tab === 'guide') { loadDashboardStats(); }
    if (tab === 'products') { loadProducts(); }
    if (tab === 'rag') { loadConversations(); loadRagDocuments(); }
    if (tab === 'mail') { loadMailDocuments(); loadMailHistory(); loadGmailStatus(); loadSignaturesForMail(); }
    if (tab === 'inquiry') { loadAdminInquiries(); }
    if (tab === 'homepage') { loadSiteSettings(); }
    if (tab === 'logs') { loadMailLogs(); }
}

/**
 * DOM 준비 완료 이벤트 핸들러
 */
document.addEventListener('DOMContentLoaded', () => {
    loadSiteLogo();  // 로고 로드
    initLogoUpload(); // 로고 드래그앤드롭 초기화
    if (authToken) { showDashboard(); loadDashboardStats(); }

    document.getElementById('passwordInput').addEventListener('keydown', e => {
        if (e.key === 'Enter') handleLogin();
    });

    setupUploadCard('uploadConsultant', 'fileInputConsultant', 'consultant');
    setupUploadCard('uploadRag', 'fileInputRag', 'rag_session');

    document.getElementById('ragInput').addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) sendRagMessage();
    });
    document.getElementById('welcomeInput').addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) sendRagMessage();
    });

    // 케밥 메뉴 닫기
    document.addEventListener('click', closeAllKebabs);
});
