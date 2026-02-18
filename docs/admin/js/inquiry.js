
/**
 * inquiry.js
 * 견적문의 관리
 */

var currentAdminInquiryId = null;
var allInquiries = []; // 전체 문의 저장
var filteredInquiries = []; // 필터링된 문의

/**
 * 견적문의 목록 로드
 */
async function loadAdminInquiries() {
    try {
        const res = await api('/admin/inquiries');
        const data = await res.json();
        allInquiries = data;
        filteredInquiries = data;
        updateInquiryStats(data);
        renderAdminInquiries(data);
    } catch (e) {
        console.warn('견적문의 로드 실패:', e);
    }
}

/**
 * 견적문의 새로고침
 */
async function refreshInquiries() {
    await loadAdminInquiries();
}

/**
 * 통계 업데이트
 */
function updateInquiryStats(items) {
    const total = items.length;
    const pending = items.filter(i => i.status !== 'answered').length;
    const replied = items.filter(i => i.status === 'answered').length;

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayCount = items.filter(i => {
        const d = i.created_at ? new Date(i.created_at) : null;
        if (!d) return false;
        d.setHours(0, 0, 0, 0);
        return d.getTime() === today.getTime();
    }).length;

    document.getElementById('statTotal').textContent = total;
    document.getElementById('statPending').textContent = pending;
    document.getElementById('statReplied').textContent = replied;
    document.getElementById('statToday').textContent = todayCount;
}

/**
 * 견적문의 목록 렌더링 (카드 형태)
 */
function renderAdminInquiries(items) {
    const container = document.getElementById('adminInquiryList');
    if (!items || items.length === 0) {
        container.innerHTML = `
            <div class="empty-state-lg">
                <div class="empty-state-icon">📭</div>
                <div class="empty-state-title">견적문의가 없습니다</div>
                <div class="empty-state-text">고객으로부터 새로운 문의가 도착하면 여기에 표시됩니다</div>
            </div>
        `;
        return;
    }

    container.innerHTML = items.map(item => {
        const statusClass = item.status === 'answered' ? 'replied' : 'pending';
        const statusText = item.status === 'answered' ? '답변완료' : '답변대기';
        const d = item.created_at ? new Date(item.created_at) : null;
        const dateStr = d ? formatDate(d) : '';
        const timeStr = d ? formatTime(d) : '';

        return `
            <div class="inquiry-card" onclick="openInquiryDetail(${item.id})">
                <div class="inquiry-card-header">
                    <div style="flex:1;">
                        <div class="inquiry-card-title">${escapeHtmlAdmin(item.title)}</div>
                        <div class="inquiry-card-meta">
                            <span class="inquiry-card-meta-item">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                                ${escapeHtmlAdmin(item.author_name)}
                            </span>
                            <span class="inquiry-card-meta-item">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                                ${dateStr} ${timeStr}
                            </span>
                            <span class="inquiry-id-badge">#${item.id}</span>
                        </div>
                    </div>
                    <span class="inquiry-status-badge ${statusClass}">${statusText}</span>
                </div>
                <div class="inquiry-card-content">${escapeHtmlAdmin(item.content)}</div>
                <div class="inquiry-card-footer">
                    <div style="font-size:0.8rem;color:var(--text-muted);">
                        ${item.replies && item.replies.length > 0 ? `💬 답변 ${item.replies.length}개` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * 날짜 포맷팅
 */
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

/**
 * 시간 포맷팅
 */
function formatTime(date) {
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
}

/**
 * HTML 이스케이프 (견적문의용)
 */
function escapeHtmlAdmin(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/**
 * 문의 상세 모달 열기 (개선)
 */
async function openInquiryDetail(id) {
    currentAdminInquiryId = id;
    try {
        const res = await api('/admin/inquiries/' + id);
        const data = await res.json();

        // 모달 타이틀
        document.getElementById('inquiryDetailTitle').textContent = data.title;

        // 메타 정보
        document.getElementById('inquiryDetailAuthor').textContent = data.author_name;
        document.getElementById('inquiryDetailEmail').textContent = data.author_email || '-';
        const d = data.created_at ? new Date(data.created_at) : null;
        document.getElementById('inquiryDetailDate').textContent = d ? `${formatDate(d)} ${formatTime(d)}` : '-';

        // 상태 배지
        const statusBadge = document.getElementById('inquiryDetailStatus');
        if (data.status === 'answered') {
            statusBadge.className = 'inquiry-status-badge replied';
            statusBadge.textContent = '답변완료';
        } else {
            statusBadge.className = 'inquiry-status-badge pending';
            statusBadge.textContent = '답변대기';
        }

        // 문의 내용
        document.getElementById('inquiryDetailContent').textContent = data.content;

        // 기존 답변
        const repliesEl = document.getElementById('adminExistingReplies');
        const repliesSection = document.getElementById('existingRepliesSection');
        if (data.replies && data.replies.length > 0) {
            repliesSection.style.display = 'block';
            repliesEl.innerHTML = data.replies.map(rp => {
                const rd = rp.created_at ? new Date(rp.created_at) : null;
                const rdStr = rd ? `${formatDate(rd)} ${formatTime(rd)}` : '';
                return `
                    <div class="existing-reply-item">
                        <div class="existing-reply-header">
                            <strong>관리자 답변</strong>
                            <span>${rdStr}</span>
                        </div>
                        <div class="existing-reply-content">${escapeHtmlAdmin(rp.content)}</div>
                    </div>
                `;
            }).join('');
        } else {
            repliesSection.style.display = 'none';
            repliesEl.innerHTML = '';
        }

        // 답변 입력창 초기화
        document.getElementById('adminReplyText').value = '';

        // 모달 표시
        document.getElementById('inquiryDetailModal').style.display = 'flex';
    } catch (e) {
        alert('문의 상세 로드 실패: ' + e.message);
    }
}

/**
 * 상세 모달 닫기
 */
function closeInquiryDetail() {
    document.getElementById('inquiryDetailModal').style.display = 'none';
    currentAdminInquiryId = null;
}

/**
 * 기존 함수 호환성 유지
 */
async function openAdminReply(id) {
    return openInquiryDetail(id);
}

function closeAdminReply() {
    return closeInquiryDetail();
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
        closeInquiryDetail();
        loadAdminInquiries();
    } catch (e) {
        alert('오류: ' + e.message);
    }
}

/**
 * 답변 템플릿 삽입
 */
function insertReplyTemplate() {
    const textarea = document.getElementById('adminReplyText');
    const template = `안녕하세요, 영마린테크입니다.

문의 주신 내용에 대해 답변드립니다.

[여기에 답변 내용을 작성하세요]

추가 문의사항이 있으시면 언제든지 연락 주시기 바랍니다.

감사합니다.
영마린테크 드림`;

    textarea.value = template;
    textarea.focus();
}

/**
 * 상태별 필터링
 */
function filterInquiries(status) {
    // 필터 버튼 활성화 상태 변경
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-status') === status) {
            btn.classList.add('active');
        }
    });

    // 필터링
    if (status === 'all') {
        filteredInquiries = allInquiries;
    } else if (status === 'pending') {
        filteredInquiries = allInquiries.filter(i => i.status !== 'answered');
    } else if (status === 'replied') {
        filteredInquiries = allInquiries.filter(i => i.status === 'answered');
    }

    // 검색어가 있으면 검색도 적용
    const searchInput = document.getElementById('inquirySearchInput');
    if (searchInput && searchInput.value.trim()) {
        searchInquiries();
    } else {
        renderAdminInquiries(filteredInquiries);
    }
}

/**
 * 검색
 */
function searchInquiries() {
    const searchInput = document.getElementById('inquirySearchInput');
    const query = searchInput ? searchInput.value.trim().toLowerCase() : '';

    if (!query) {
        renderAdminInquiries(filteredInquiries);
        return;
    }

    const results = filteredInquiries.filter(item => {
        const title = (item.title || '').toLowerCase();
        const author = (item.author_name || '').toLowerCase();
        const content = (item.content || '').toLowerCase();
        return title.includes(query) || author.includes(query) || content.includes(query);
    });

    renderAdminInquiries(results);
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
