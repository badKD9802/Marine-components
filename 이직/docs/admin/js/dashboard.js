
/**
 * dashboard.js
 * 대시보드 통계 표시
 */

/**
 * 대시보드 통계 로드
 */
async function loadDashboardStats() {
    try {
        const data = await (await api('/admin/stats')).json();

        // 메일 통계
        document.getElementById('statMailTotal').textContent = data.mails.total || 0;
        document.getElementById('statMailToday').textContent = data.mails.today || 0;
        document.getElementById('statMailWeek').textContent = data.mails.this_week || 0;

        // 문서 통계
        document.getElementById('statDocTotal').textContent = data.documents.total || 0;
        document.getElementById('statDocConsultant').textContent = data.documents.by_purpose.consultant || 0;
        document.getElementById('statDocRag').textContent = data.documents.by_purpose.rag_session || 0;

        // RAG 대화 통계
        document.getElementById('statConvTotal').textContent = data.conversations.total || 0;
        document.getElementById('statConvToday').textContent = data.conversations.today || 0;

        // 견적문의 통계
        document.getElementById('statInqTotal').textContent = data.inquiries.total || 0;
        document.getElementById('statInqToday').textContent = data.inquiries.today || 0;

    } catch (e) {
        console.error('통계 로드 실패:', e);
    }
}
