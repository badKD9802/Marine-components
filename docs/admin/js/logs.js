
/**
 * logs.js
 * 시스템 로그 관리
 */

/**
 * 메일 로그 로드
 */
async function loadMailLogs() {
    try {
        const data = await (await api('/admin/logs/mail')).json();
        const container = document.getElementById('mailLogsList');

        if (!data.length) {
            container.innerHTML = '<div class="empty-state" style="padding:40px 20px;">메일 작성 이력이 없습니다.</div>';
            return;
        }

        const toneNames = {formal: '격식체', friendly: '친근체', concise: '간결체'};
        const langNames = {en: '영어', ja: '일본어', zh: '중국어', ko: '한국어'};

        container.innerHTML = data.map(log => `
            <div style="border-bottom:1px solid var(--border-light);padding:12px 0;">
                <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:6px;">
                    <div style="flex:1;">
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;">
                            ${new Date(log.created_at).toLocaleString('ko-KR')} · ${langNames[log.detected_lang] || log.detected_lang} · ${toneNames[log.tone] || log.tone}
                        </div>
                        <div style="font-size:0.85rem;color:var(--text-regular);margin-bottom:6px;"><strong>수신:</strong> ${log.incoming_preview}</div>
                        <div style="font-size:0.85rem;color:var(--text-regular);"><strong>답장:</strong> ${log.draft_preview}</div>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (e) {
        console.error('로그 로드 실패:', e);
        document.getElementById('mailLogsList').innerHTML = '<div class="empty-state" style="padding:40px 20px;color:var(--error);">로그 로드 실패</div>';
    }
}
