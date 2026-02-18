
/**
 * inquiry.js
 * 견적문의 관리
 */

var currentAdminInquiryId = null;

/**
 * 견적문의 목록 로드
 */
async function loadAdminInquiries() {
    try {
        const res = await api('/admin/inquiries');
        const data = await res.json();
        renderAdminInquiries(data);
    } catch (e) {
        console.warn('견적문의 로드 실패:', e);
    }
}

/**
 * 견적문의 목록 렌더링
 */
function renderAdminInquiries(items) {
    const tbody = document.getElementById('adminInquiryList');
    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:24px;color:#94a3b8;">등록된 문의가 없습니다.</td></tr>';
        return;
    }
    tbody.innerHTML = items.map(item => {
        const statusBadge = item.status === 'answered'
            ? '<span style="background:#e8f5e9;color:#2e7d32;padding:2px 10px;border-radius:10px;font-size:0.82rem;font-weight:600;">답변완료</span>'
            : '<span style="background:#fff3e0;color:#e65100;padding:2px 10px;border-radius:10px;font-size:0.82rem;font-weight:600;">대기중</span>';
        const d = item.created_at ? new Date(item.created_at) : null;
        const dateStr = d ? (d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')) : '';
        return `<tr>
            <td>${item.id}</td>
            <td>${escapeHtmlAdmin(item.title)}</td>
            <td>${escapeHtmlAdmin(item.author_name)}</td>
            <td>${statusBadge}</td>
            <td>${dateStr}</td>
            <td>
                <button onclick="openAdminReply(${item.id})" style="padding:4px 12px;background:#0a2647;color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.82rem;margin-right:4px;">보기</button>
                <button onclick="deleteAdminInquiry(${item.id})" style="padding:4px 12px;background:#ef4444;color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.82rem;">삭제</button>
            </td>
        </tr>`;
    }).join('');
}

/**
 * HTML 이스케이프 (견적문의용)
 */
function escapeHtmlAdmin(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/**
 * 견적문의 상세 및 답변 패널 열기
 */
async function openAdminReply(id) {
    currentAdminInquiryId = id;
    try {
        const res = await api('/admin/inquiries/' + id);
        const data = await res.json();
        document.getElementById('adminReplyTitle').textContent = data.title;
        const d = data.created_at ? new Date(data.created_at) : null;
        const dateStr = d ? (d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')) : '';
        document.getElementById('adminReplyMeta').textContent = data.author_name + ' | ' + dateStr + ' | ' + (data.status === 'answered' ? '답변완료' : '대기중');
        document.getElementById('adminReplyContent').textContent = data.content;
        const repliesEl = document.getElementById('adminExistingReplies');
        if (data.replies && data.replies.length > 0) {
            repliesEl.innerHTML = data.replies.map(rp => {
                const rd = rp.created_at ? new Date(rp.created_at) : null;
                const rdStr = rd ? (rd.getFullYear()+'-'+String(rd.getMonth()+1).padStart(2,'0')+'-'+String(rd.getDate()).padStart(2,'0')) : '';
                return '<div style="background:#fffbf0;border-top:3px solid:#f0a500;border-radius:8px;padding:14px;margin-bottom:8px;">'
                    + '<strong style="color:#f0a500;">관리자 답변</strong><br>'
                    + '<div style="margin-top:6px;white-space:pre-wrap;">' + escapeHtmlAdmin(rp.content) + '</div>'
                    + '<div style="font-size:0.82rem;color:#94a3b8;margin-top:6px;">' + rdStr + '</div>'
                    + '</div>';
            }).join('');
        } else {
            repliesEl.innerHTML = '';
        }
        document.getElementById('adminReplyText').value = '';
        document.getElementById('adminReplyPanel').style.display = '';
    } catch (e) {
        alert('문의 상세 로드 실패: ' + e.message);
    }
}

/**
 * 답변 패널 닫기
 */
function closeAdminReply() {
    document.getElementById('adminReplyPanel').style.display = 'none';
    currentAdminInquiryId = null;
}

/**
 * 답변 등록
 */
async function submitAdminReply() {
    const content = document.getElementById('adminReplyText').value.trim();
    if (!content) { alert('답변 내용을 입력해주세요.'); return; }
    try {
        const res = await api('/admin/inquiries/' + currentAdminInquiryId + '/reply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content })
        });
        if (!res.ok) { const err = await res.json(); alert(err.detail || '답변 등록 실패'); return; }
        alert('답변이 등록되었습니다.');
        closeAdminReply();
        loadAdminInquiries();
    } catch (e) {
        alert('오류: ' + e.message);
    }
}

/**
 * 견적문의 삭제
 */
async function deleteAdminInquiry(id) {
    if (!confirm('이 문의를 삭제하시겠습니까?')) return;
    try {
        const res = await api('/admin/inquiries/' + id, { method: 'DELETE' });
        if (!res.ok) { const err = await res.json(); alert(err.detail || '삭제 실패'); return; }
        closeAdminReply();
        loadAdminInquiries();
    } catch (e) {
        alert('오류: ' + e.message);
    }
}

/**
 * 문의 상세 로드 (backward compatibility)
 */
async function loadInquiryDetail(id) {
    return openAdminReply(id);
}

/**
 * 답변 제출 (backward compatibility)
 */
async function replyInquiry() {
    return submitAdminReply();
}
