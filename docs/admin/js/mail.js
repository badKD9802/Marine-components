
/**
 * mail.js
 * 메일 작성, Gmail 연동, 템플릿, 서명, 프롬프트 관리
 * @version 2.0.0 - 2026-02-19 - DOM null 체크 완전 적용
 */

var mailDocuments = [];
var mailTemplates = [];
var mailSignatures = [];
var promptExamples = [];
var currentMailHistoryId = null;
var mailDetectedLang = 'en';  // 감지된 언어
var mailCurrentRefs = [];     // 현재 참조 문서

async function loadMailDocuments() {
    try {
        mailDocuments = await (await api('/admin/rag/documents')).json();
        renderMailDocuments(mailDocuments);
    } catch (e) { console.error('메일 문서 로드 실패:', e); }
}

function renderMailDocuments(docs) {
    const c = document.getElementById('mailDocList');
    if (!docs.length) {
        c.innerHTML = '<div class="empty-state" style="padding:20px 10px;font-size:0.8rem"><div style="font-size:1.2rem;margin-bottom:6px;">&#128196;</div>RAG 세션용 문서가 없습니다<br><span style="font-size:0.72rem">문서 관리에서 업로드하세요</span></div>';
        return;
    }
    let html = `<div class="ref-doc-item ref-doc-all"><input type="checkbox" id="mailDocAll" checked onchange="toggleAllMailDocs(this.checked)" /><label for="mailDocAll">전체 문서</label></div>`;
    for (const d of docs) {
        html += `<div class="ref-doc-item"><input type="checkbox" class="mail-doc-check" id="mailDoc${d.id}" value="${d.id}" checked /><label for="mailDoc${d.id}">&#128196; ${esc(d.filename)}</label></div>`;
    }
    c.innerHTML = html;
}

function toggleAllMailDocs(checked) {
    document.querySelectorAll('.mail-doc-check').forEach(cb => cb.checked = checked);
}

function getMailSelectedDocIds() {
    const ids = Array.from(document.querySelectorAll('.mail-doc-check:checked')).map(cb => parseInt(cb.value));
    return (ids.length === mailDocuments.length || ids.length === 0) ? null : ids;
}

// --- 이력 로드 ---
async function loadMailHistory() {
    try {
        const items = await (await api('/admin/mail/history')).json();
        renderMailHistory(items);
    } catch (e) { console.error('메일 이력 로드 실패:', e); }
}

function renderMailHistory(items) {
    const c = document.getElementById('mailHistoryList');
    if (!items.length) {
        c.innerHTML = '<div class="empty-state" style="padding:20px 10px;font-size:0.8rem">저장된 이력이 없습니다</div>';
        return;
    }
    const langMap = { en: 'EN', ja: 'JA', zh: 'ZH', ko: 'KO', de: 'DE', fr: 'FR', es: 'ES' };
    let html = '';
    for (const item of items) {
        const date = item.created_at ? new Date(item.created_at).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
        const lang = langMap[item.detected_lang] || item.detected_lang;
        html += `<div class="mail-history-item" onclick="loadMailHistoryItem(${item.id})">
            <div class="mail-history-title">${esc(item.incoming_email)}</div>
            <div class="mail-history-meta">
                <span class="mail-pane-badge badge-lang">${lang}</span>
                <span>${date}</span>
            </div>
            <button class="mail-history-del" onclick="event.stopPropagation();deleteMailHistory(${item.id})" title="삭제">&#10005;</button>
        </div>`;
    }
    c.innerHTML = html;
}

// --- 수신 메일 ↔ 초안 리사이즈 ---
(function() {
    const handle = document.getElementById('mailResizeHandle');
    const mailMain = document.querySelector('.mail-main');
    const incoming = document.querySelector('.mail-incoming');
    let dragging = false, startY = 0, startH = 0;

    handle.addEventListener('mousedown', function(e) {
        e.preventDefault();
        dragging = true;
        startY = e.clientY;
        startH = incoming.offsetHeight;
        handle.classList.add('active');
        document.body.style.cursor = 'row-resize';
        document.body.style.userSelect = 'none';
    });
    document.addEventListener('mousemove', function(e) {
        if (!dragging) return;
        const delta = e.clientY - startY;
        const newH = Math.max(100, Math.min(startH + delta, mailMain.offsetHeight - 150));
        incoming.style.height = newH + 'px';
    });
    document.addEventListener('mouseup', function() {
        if (!dragging) return;
        dragging = false;
        handle.classList.remove('active');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    });

    // 터치 지원
    handle.addEventListener('touchstart', function(e) {
        e.preventDefault();
        dragging = true;
        startY = e.touches[0].clientY;
        startH = incoming.offsetHeight;
        handle.classList.add('active');
    }, { passive: false });
    document.addEventListener('touchmove', function(e) {
        if (!dragging) return;
        const delta = e.touches[0].clientY - startY;
        const newH = Math.max(100, Math.min(startH + delta, mailMain.offsetHeight - 150));
        incoming.style.height = newH + 'px';
    });
    document.addEventListener('touchend', function() {
        if (!dragging) return;
        dragging = false;
        handle.classList.remove('active');
    });
})();

// --- 수신 메일 한국어 번역 ---
async function translateIncoming() {
    console.log('🌏 [translateIncoming] 함수 호출됨');

    const mailIncoming = document.getElementById('mailIncoming');
    console.log('🔍 [translateIncoming] mailIncoming 요소:', mailIncoming);

    if (!mailIncoming) {
        console.error('❌ [translateIncoming] mailIncoming 요소를 찾을 수 없음');
        alert('메일 입력 영역을 찾을 수 없습니다.');
        return;
    }

    const incoming = mailIncoming.value.trim();
    console.log('📧 [translateIncoming] 수신 메일 내용 길이:', incoming.length);

    if (!incoming) {
        console.warn('⚠️ [translateIncoming] 수신 메일 내용이 비어있음');
        alert('수신 메일 내용을 입력해주세요.');
        return;
    }

    showMailLoading('수신 메일을 한국어로 번역하고 있습니다...');
    console.log('⏳ [translateIncoming] 로딩 표시 시작');

    try {
        console.log('🌐 [translateIncoming] API 호출 시작');
        const response = await api('/admin/mail/translate-incoming', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ foreign_text: incoming, source_lang: 'auto' }),
        });
        console.log('📥 [translateIncoming] API 응답 받음:', response.status);

        const data = await response.json();
        console.log('✅ [translateIncoming] 응답 데이터:', data);

        const translated = data.translated_korean || '';
        console.log('🇰🇷 [translateIncoming] 번역 결과 길이:', translated.length);

        // 단일 textarea 숨기고 분할 뷰 표시
        const splitView = document.getElementById('mailIncomingSplit');
        const originalInput = document.getElementById('mailIncomingOriginal');
        const translatedInput = document.getElementById('mailIncomingTranslated');

        console.log('🔍 [translateIncoming] 분할 뷰 요소:', {
            splitView: !!splitView,
            originalInput: !!originalInput,
            translatedInput: !!translatedInput
        });

        // 번역 결과를 표시할 영역 찾기
        const koreanDraftArea = document.getElementById('mailKoreanDraft');
        console.log('📝 [translateIncoming] 한국어 초안 영역:', !!koreanDraftArea);

        if (splitView && originalInput && translatedInput) {
            console.log('✅ [translateIncoming] 분할 뷰에 표시');
            mailIncoming.style.display = 'none';
            splitView.classList.add('visible');

            // 원문 채우기
            originalInput.value = incoming;
            translatedInput.value = translated;

            // 원문 편집 시 단일 textarea도 동기화
            originalInput.oninput = function() {
                mailIncoming.value = this.value;
            };
        } else if (koreanDraftArea) {
            console.log('✅ [translateIncoming] 한국어 초안 영역에 표시');
            // 한국어 초안 영역에 번역 결과 표시
            koreanDraftArea.value = `📧 번역된 내용:\n\n${translated}\n\n---\n원문은 위의 수신 메일 영역에 있습니다.`;
            alert('✅ 번역이 완료되었습니다!\n아래 한국어 초안 영역에서 확인하세요.');
        } else {
            console.warn('⚠️ [translateIncoming] 표시할 영역을 찾을 수 없음');
            alert('번역 완료:\n\n' + translated.substring(0, 200) + '...');
        }

        // 소스 언어 배지 (감지된 언어가 있으면 표시)
        const srcBadge = document.getElementById('incomingSrcLangBadge');
        if (srcBadge && mailDetectedLang && mailDetectedLang !== 'ko') {
            srcBadge.textContent = mailDetectedLang.toUpperCase();
        }

        console.log('✨ [translateIncoming] 번역 완료');

    } catch (e) {
        console.error('수신 메일 번역 오류:', e);
        alert('번역에 실패했습니다. 다시 시도해주세요.');
    } finally {
        hideMailLoading();
    }
}

// --- 답장 생성 ---
async function composeMail() {
    console.log('🚀 [composeMail] 함수 호출됨');

    const mailIncoming = document.getElementById('mailIncoming');
    console.log('🔍 [composeMail] mailIncoming 요소:', mailIncoming);

    if (!mailIncoming) {
        console.error('❌ [composeMail] mailIncoming 요소를 찾을 수 없음');
        alert('메일 입력 영역을 찾을 수 없습니다.');
        return;
    }

    const incoming = mailIncoming.value.trim();
    console.log('📧 [composeMail] 수신 메일 내용 길이:', incoming.length);

    if (!incoming) {
        console.warn('⚠️ [composeMail] 수신 메일 내용이 비어있음');
        alert('수신 메일 내용을 입력해주세요.');
        return;
    }

    const toneInput = document.getElementById('mailTone');
    const tone = toneInput ? toneInput.value : 'formal';
    console.log('🎨 [composeMail] 톤:', tone);

    const docIds = getMailSelectedDocIds();
    console.log('📚 [composeMail] 선택된 문서 IDs:', docIds);

    showMailLoading('수신 메일을 분석하고 답장을 생성하고 있습니다...');
    console.log('⏳ [composeMail] 로딩 표시 시작');

    try {
        console.log('🌐 [composeMail] API 호출 시작');
        const response = await api('/admin/mail/compose', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ incoming_email: incoming, document_ids: docIds, tone: tone }),
        });
        console.log('📥 [composeMail] API 응답 받음:', response.status);

        const data = await response.json();
        console.log('✅ [composeMail] 응답 데이터:', data);

        mailDetectedLang = data.detected_lang || 'en';
        mailCurrentRefs = data.references || [];

        // 분석 결과 표시
        const analysisEl = document.getElementById('mailAnalysis');
        const analysisText = document.getElementById('mailAnalysisText');
        if (analysisEl && analysisText) {
            if (data.analysis) {
                analysisText.textContent = data.analysis;
                analysisEl.classList.add('visible');
            } else {
                analysisEl.classList.remove('visible');
            }
        }

        // 한국어 초안
        let koreanDraft = data.korean_draft || '';

        // 기본 서명 자동 추가
        const defaultSig = getDefaultSignature();
        if (defaultSig && koreanDraft) {
            koreanDraft = koreanDraft.trim() + '\n\n' + defaultSig.content;
        }

        const koreanDraftInput = document.getElementById('mailKoreanDraft');
        if (koreanDraftInput) koreanDraftInput.value = koreanDraft;

        // 번역 대상 언어 자동 설정
        const langSelect = document.getElementById('mailTargetLang');
        if (langSelect && mailDetectedLang && mailDetectedLang !== 'ko') {
            langSelect.value = mailDetectedLang;
        }
        updateTargetLangBadge();

        // 번역본 초기화
        const translatedInput = document.getElementById('mailTranslated');
        if (translatedInput) translatedInput.value = '';

        // 버튼 활성화
        const recomposeBtn = document.getElementById('mailRecomposeBtn');
        const translateBtn = document.getElementById('mailTranslateBtn');
        const saveBtn = document.getElementById('mailSaveBtn');
        if (recomposeBtn) recomposeBtn.disabled = false;
        if (translateBtn) translateBtn.disabled = false;
        if (saveBtn) saveBtn.disabled = false;

    } catch (e) {
        console.error('메일 생성 오류:', e);
        alert('메일 생성에 실패했습니다. 다시 시도해주세요.');
    } finally {
        hideMailLoading();
    }
}

// 한국어 초안 재작성
async function recomposeMail() {
    const mailIncoming = document.getElementById('mailIncoming');
    if (!mailIncoming) { alert('메일 입력 영역을 찾을 수 없습니다.'); return; }

    const incoming = mailIncoming.value.trim();
    if (!incoming) { alert('수신 메일 내용을 입력해주세요.'); return; }

    if (!confirm('한국어 초안을 다시 생성하시겠습니까? 기존 내용은 사라집니다.')) return;

    const toneInput = document.getElementById('mailTone');
    const tone = toneInput ? toneInput.value : 'formal';
    const docIds = getMailSelectedDocIds();

    showMailLoading('답장을 재작성하고 있습니다...');

    try {
        const data = await (await api('/admin/mail/compose', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ incoming_email: incoming, document_ids: docIds, tone: tone }),
        })).json();

        mailDetectedLang = data.detected_lang || 'en';
        mailCurrentRefs = data.references || [];

        // 분석 결과 표시
        const analysisEl = document.getElementById('mailAnalysis');
        const analysisText = document.getElementById('mailAnalysisText');
        if (analysisEl && analysisText) {
            if (data.analysis) {
                analysisText.textContent = data.analysis;
                analysisEl.classList.add('visible');
            } else {
                analysisEl.classList.remove('visible');
            }
        }

        // 한국어 초안
        let koreanDraft = data.korean_draft || '';

        // 기본 서명 자동 추가
        const defaultSig = getDefaultSignature();
        if (defaultSig && koreanDraft) {
            koreanDraft = koreanDraft.trim() + '\n\n' + defaultSig.content;
        }

        const koreanDraftInput = document.getElementById('mailKoreanDraft');
        if (koreanDraftInput) koreanDraftInput.value = koreanDraft;

        // 번역 대상 언어 자동 설정
        const langSelect = document.getElementById('mailTargetLang');
        if (langSelect && mailDetectedLang && mailDetectedLang !== 'ko') {
            langSelect.value = mailDetectedLang;
        }
        updateTargetLangBadge();

        // 번역본 초기화 (재작성하면 다시 번역해야 함)
        const translatedInput = document.getElementById('mailTranslated');
        const retranslateBtn = document.getElementById('mailRetranslateBtn');
        if (translatedInput) translatedInput.value = '';
        if (retranslateBtn) retranslateBtn.disabled = true;

        // 버튼 활성화
        const recomposeBtn = document.getElementById('mailRecomposeBtn');
        const translateBtn = document.getElementById('mailTranslateBtn');
        const saveBtn = document.getElementById('mailSaveBtn');
        if (recomposeBtn) recomposeBtn.disabled = false;
        if (translateBtn) translateBtn.disabled = false;
        if (saveBtn) saveBtn.disabled = false;

        alert('한국어 초안이 재작성되었습니다.');

    } catch (e) {
        console.error('재작성 오류:', e);
        alert('재작성에 실패했습니다. 다시 시도해주세요.');
    } finally {
        hideMailLoading();
    }
}

// --- 번역 ---
async function translateMail() {
    const koreanDraftInput = document.getElementById('mailKoreanDraft');
    if (!koreanDraftInput) { alert('한국어 초안 입력 영역을 찾을 수 없습니다.'); return; }

    const koreanText = koreanDraftInput.value.trim();
    if (!koreanText) { alert('번역할 한국어 초안이 없습니다.'); return; }

    const targetLangInput = document.getElementById('mailTargetLang');
    const targetLang = targetLangInput ? targetLangInput.value : 'en';

    showMailLoading('번역 중...');

    try {
        console.log('[DEBUG] 번역 시작, 대상 언어:', targetLang);
        const data = await (await api('/admin/mail/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ korean_text: koreanText, target_lang: targetLang }),
        })).json();

        console.log('[DEBUG] 번역 응답:', data);

        const translatedInput = document.getElementById('mailTranslated');
        const retranslateBtn = document.getElementById('mailRetranslateBtn');

        if (translatedInput) translatedInput.value = data.translated || '';
        if (retranslateBtn) retranslateBtn.disabled = false;
        updateTargetLangBadge();

        console.log('[DEBUG] 번역 완료');

    } catch (e) {
        console.error('[ERROR] 번역 오류:', e);
        alert('번역에 실패했습니다. 다시 시도해주세요.');
    } finally {
        hideMailLoading();
    }
}

// --- 저장 ---
async function saveMailComposition() {
    const incoming = document.getElementById('mailIncoming').value.trim();
    const korean = document.getElementById('mailKoreanDraft').value.trim();
    const translated = document.getElementById('mailTranslated').value.trim();

    if (!incoming || !korean) { alert('수신 메일과 한국어 초안이 필요합니다.'); return; }

    try {
        const saveResp = await (await api('/admin/mail/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                incoming_email: incoming,
                detected_lang: mailDetectedLang,
                tone: document.getElementById('mailTone').value,
                korean_draft: korean,
                translated_draft: translated,
                document_ids: getMailSelectedDocIds(),
                refs: mailCurrentRefs,
            }),
        })).json();

        // 수신 메일이 선택된 상태면 composition_id 연결
        if (currentInboxId && saveResp.id) {
            try {
                await api(`/admin/mail/gmail/inbox/${currentInboxId}/link?composition_id=${saveResp.id}`, { method: 'POST' });
                document.getElementById('mailSendBtn').disabled = false;
                loadInboxEmails();
            } catch (e) { console.error('초안 연결 실패:', e); }
        }

        alert('저장되었습니다.');
        loadMailHistory();
    } catch (e) {
        console.error('저장 오류:', e);
        alert('저장에 실패했습니다.');
    }
}

// --- 이력 불러오기 ---
async function loadMailHistoryItem(id) {
    try {
        const data = await (await api(`/admin/mail/history/${id}`)).json();

        document.getElementById('mailIncoming').value = data.incoming_email || '';
        document.getElementById('mailKoreanDraft').value = data.korean_draft || '';
        document.getElementById('mailTranslated').value = data.translated_draft || '';
        document.getElementById('mailTone').value = data.tone || 'formal';

        mailDetectedLang = data.detected_lang || 'en';
        mailCurrentRefs = data.refs || [];

        if (data.detected_lang && data.detected_lang !== 'ko') {
            document.getElementById('mailTargetLang').value = data.detected_lang;
        }
        updateTargetLangBadge();

        // 분석 숨기기 + 번역 분할 뷰 리셋 (이력에서는 분석 없음)
        document.getElementById('mailAnalysis').classList.remove('visible');
        document.getElementById('mailIncomingSplit').classList.remove('visible');
        document.getElementById('mailIncoming').style.display = '';

        // 버튼 활성화
        document.getElementById('mailTranslateBtn').disabled = false;
        document.getElementById('mailRetranslateBtn').disabled = !(data.translated_draft);
        document.getElementById('mailSaveBtn').disabled = false;

        // 활성 표시
        document.querySelectorAll('.mail-history-item').forEach(el => el.classList.remove('active'));
        const clicked = document.querySelector(`.mail-history-item[onclick*="loadMailHistoryItem(${id})"]`);
        if (clicked) clicked.classList.add('active');

    } catch (e) {
        console.error('이력 로드 실패:', e);
        alert('이력을 불러오는데 실패했습니다.');
    }
}

// --- 이력 삭제 ---
async function deleteMailHistory(id) {
    if (!confirm('이 이력을 삭제하시겠습니까?')) return;
    try {
        await api(`/admin/mail/history/${id}`, { method: 'DELETE' });
        loadMailHistory();
    } catch (e) { console.error('이력 삭제 실패:', e); }
}

// --- 복사 ---
function copyMailDraft(type) {
    const text = type === 'ko'
        ? document.getElementById('mailKoreanDraft').value
        : document.getElementById('mailTranslated').value;
    if (!text) { alert('복사할 내용이 없습니다.'); return; }
    navigator.clipboard.writeText(text).then(() => {
        const label = type === 'ko' ? '한국어 초안' : '번역본';
        alert(`${label}이 클립보드에 복사되었습니다.`);
    }).catch(() => {
        // fallback
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        alert('클립보드에 복사되었습니다.');
    });
}

// --- 언어 뱃지 업데이트 ---
function updateTargetLangBadge() {
    const langSelect = document.getElementById('mailTargetLang');
    const badge = document.getElementById('mailTargetLangBadge');
    const langMap = { en: 'EN', ja: 'JA', zh: 'ZH', ko: 'KO', de: 'DE', fr: 'FR', es: 'ES' };
    badge.textContent = langMap[langSelect.value] || langSelect.value.toUpperCase();
}

// 언어 선택 변경 시 뱃지 업데이트
document.getElementById('mailTargetLang').addEventListener('change', updateTargetLangBadge);

// --- 로딩 표시 ---
function showMailLoading(text) {
    const loadingText = document.getElementById('mailLoadingText');
    const loading = document.getElementById('mailLoading');
    const composeBtn = document.getElementById('mailComposeBtn');
    const recomposeBtn = document.getElementById('mailRecomposeBtn');
    const translateBtn = document.getElementById('mailTranslateBtn');

    if (loadingText) loadingText.textContent = text || '처리 중...';
    if (loading) loading.classList.add('active');
    if (composeBtn) composeBtn.disabled = true;
    if (recomposeBtn) recomposeBtn.disabled = true;
    if (translateBtn) translateBtn.disabled = true;
}

function hideMailLoading() {
    const loading = document.getElementById('mailLoading');
    const composeBtn = document.getElementById('mailComposeBtn');

    if (loading) loading.classList.remove('active');
    if (composeBtn) composeBtn.disabled = false;
}

// ============================================================
//  Gmail 연동
// ============================================================
var gmailConnected = false;
var currentInboxId = null;  // 현재 선택된 수신 메일 ID

// --- Gmail 상태 로드 ---
async function loadGmailStatus() {
    try {
        console.log('[DEBUG] Gmail 상태 API 호출 중...');
        const data = await (await api('/admin/mail/gmail/status')).json();
        console.log('[DEBUG] Gmail 상태 응답:', data);
        gmailConnected = data.connected;
        console.log('[DEBUG] gmailConnected 설정됨:', gmailConnected);
        updateGmailUI(data);
    } catch (e) {
        console.error('[ERROR] Gmail 상태 로드 실패:', e);
        gmailConnected = false;
        updateGmailUI({ connected: false });
    }
}

function updateGmailUI(data) {
    console.log('[DEBUG] updateGmailUI 호출됨, data:', data);

    const dot = document.getElementById('gmailDot');
    const statusText = document.getElementById('gmailStatusText');
    const disconnectBtn = document.getElementById('gmailDisconnectBtn');
    const fetchBtn = document.getElementById('gmailFetchBtn');
    const autoSettings = document.getElementById('gmailAutoSettings');
    const authSection = document.getElementById('gmailAuthSection');
    const sendBtn = document.getElementById('mailSendBtn');

    // 필수 요소가 없으면 경고만 출력하고 종료
    if (!dot || !statusText) {
        console.warn('[WARN] Gmail UI 요소를 찾을 수 없습니다. 메일 탭이 아닐 수 있습니다.');
        return;
    }

    if (data.connected) {
        console.log('[DEBUG] Gmail 연결됨, 수신함 로드 예정');

        dot.className = 'gmail-status-dot connected';
        statusText.textContent = data.email;
        if (disconnectBtn) disconnectBtn.style.display = '';
        if (fetchBtn) fetchBtn.style.display = '';
        if (autoSettings) autoSettings.style.display = '';
        if (authSection) authSection.style.display = 'none';  // 연결되면 입력란 숨김
        if (sendBtn) sendBtn.style.display = '';

        // 자동 체크 설정
        const checkTimeInput = document.getElementById('gmailCheckTime');
        if (checkTimeInput) checkTimeInput.value = data.check_time || '09:00';

        const toggle = document.getElementById('gmailAutoToggle');
        if (toggle) {
            if (data.auto_reply_enabled) {
                toggle.classList.add('active');
            } else {
                toggle.classList.remove('active');
            }
        }

        // 마지막 체크 시간
        if (data.last_checked_at) {
            const d = new Date(data.last_checked_at);
            const lastChecked = document.getElementById('gmailLastChecked');
            if (lastChecked) {
                lastChecked.textContent = '마지막: ' + d.toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            }
        }

        console.log('[DEBUG] 수신함 로드 함수 호출');
        loadInboxEmails();
    } else {
        console.log('[DEBUG] Gmail 연결 안됨');

        dot.className = 'gmail-status-dot disconnected';
        statusText.textContent = '연결 안됨';
        if (disconnectBtn) disconnectBtn.style.display = 'none';
        if (fetchBtn) fetchBtn.style.display = 'none';
        if (autoSettings) autoSettings.style.display = 'none';
        if (authSection) authSection.style.display = 'flex';  // 연결 해제되면 입력란 다시 표시
        if (sendBtn) sendBtn.style.display = 'none';

        // 입력란 초기화
        const emailInput = document.getElementById('gmailEmail');
        const pwInput = document.getElementById('gmailAppPassword');
        if (emailInput) emailInput.value = '';
        if (pwInput) pwInput.value = '';

        // 수신함도 비우기
        loadInboxEmails();
    }
}

// --- Gmail 연결 ---
async function gmailConnect() {
    const email = document.getElementById('gmailEmail').value.trim();
    const pw = document.getElementById('gmailAppPassword').value.trim();
    if (!email || !pw) { alert('이메일과 앱 비밀번호를 입력하세요.'); return; }

    try {
        const resp = await api('/admin/mail/gmail/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, app_password: pw }),
        });
        const data = await resp.json();
        if (!resp.ok) { alert(data.detail || '연결 실패'); return; }
        alert('Gmail 연결 성공!');
        loadGmailStatus();
    } catch (e) {
        alert('Gmail 연결 오류: ' + e.message);
    }
}

// --- Gmail 연결 해제 ---
async function gmailDisconnect() {
    if (!confirm('Gmail 연결을 해제하시겠습니까?')) return;
    try {
        await api('/admin/mail/gmail/disconnect', { method: 'POST' });
        gmailConnected = false;
        currentInboxId = null;
        loadGmailStatus();
    } catch (e) { alert('연결 해제 실패: ' + e.message); }
}

// --- 수동 메일 가져오기 ---
async function gmailFetch() {
    showMailLoading('메일을 가져오는 중...');
    try {
        const data = await (await api('/admin/mail/gmail/fetch', { method: 'POST' })).json();
        alert(data.message);
        loadInboxEmails();
        loadGmailStatus();
    } catch (e) {
        alert('메일 가져오기 실패: ' + e.message);
    } finally {
        hideMailLoading();
    }
}

// --- 자동 체크 토글 ---
async function toggleGmailAuto() {
    const toggle = document.getElementById('gmailAutoToggle');
    const newState = !toggle.classList.contains('active');
    const checkTime = document.getElementById('gmailCheckTime').value;

    try {
        await api('/admin/mail/gmail/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ check_time: checkTime, auto_reply_enabled: newState }),
        });
        toggle.classList.toggle('active', newState);
    } catch (e) { alert('설정 저장 실패: ' + e.message); }
}

// 체크 시간 변경 시 자동 저장
document.getElementById('gmailCheckTime').addEventListener('change', async function () {
    const toggle = document.getElementById('gmailAutoToggle');
    const autoEnabled = toggle.classList.contains('active');
    if (!gmailConnected) return;
    try {
        await api('/admin/mail/gmail/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ check_time: this.value, auto_reply_enabled: autoEnabled }),
        });
    } catch (e) { console.error('설정 저장 실패:', e); }
});

// --- 수신함 로드 ---
async function loadInboxEmails() {
    console.log('[DEBUG] loadInboxEmails 호출됨, gmailConnected:', gmailConnected);

    if (!gmailConnected) {
        console.warn('Gmail이 연결되지 않았습니다. 수신함을 로드할 수 없습니다.');
        const c = document.getElementById('inboxList');
        const empty = document.getElementById('inboxEmpty');
        if (c) c.innerHTML = '';
        if (empty) {
            empty.style.display = '';
            empty.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);"><div style="font-size:2rem;margin-bottom:8px;">📭</div><div>Gmail이 연결되지 않았습니다</div><div style="font-size:0.8rem;margin-top:4px;">메일 작성 도구에서 Gmail을 연결하세요</div></div>';
        }
        return;
    }

    try {
        console.log('[DEBUG] 수신함 API 호출 중...');
        const items = await (await api('/admin/mail/gmail/inbox')).json();
        console.log('[DEBUG] 수신함 메일 개수:', items.length);
        console.log('[DEBUG] 수신함 데이터:', items);
        renderInboxList(items);
    } catch (e) {
        console.error('[ERROR] 수신함 로드 실패:', e);
        const c = document.getElementById('inboxList');
        const empty = document.getElementById('inboxEmpty');
        if (c) c.innerHTML = '';
        if (empty) {
            empty.style.display = '';
            empty.innerHTML = '<div style="padding:20px;text-align:center;color:var(--error);"><div style="font-size:2rem;margin-bottom:8px;">⚠️</div><div>수신함 로드 실패</div><div style="font-size:0.8rem;margin-top:4px;">'+e.message+'</div></div>';
        }
    }
}

function renderInboxList(items) {
    const c = document.getElementById('inboxList');
    const empty = document.getElementById('inboxEmpty');
    const countBadge = document.getElementById('inboxCount');

    console.log('[DEBUG] renderInboxList 호출, items:', items.length);
    console.log('[DEBUG] inboxList 요소:', c, 'inboxEmpty 요소:', empty, 'inboxCount 요소:', countBadge);

    // 필수 요소가 없으면 경고하고 종료
    if (!c) {
        console.error('[ERROR] inboxList 요소를 찾을 수 없습니다');
        return;
    }

    if (!items.length) {
        c.innerHTML = '';
        if (empty) empty.style.display = '';
        if (countBadge) countBadge.style.display = 'none';
        return;
    }
    if (empty) empty.style.display = 'none';

    // new 카운트
    const newCount = items.filter(i => i.status === 'new').length;
    if (countBadge) {
        if (newCount > 0) {
            countBadge.textContent = newCount;
            countBadge.style.display = '';
        } else {
            countBadge.style.display = 'none';
        }
    }

    const statusMap = {
        'new': { label: 'NEW', cls: 'badge-new' },
        'draft_ready': { label: '초안', cls: 'badge-draft-ready' },
        'replied': { label: '답장', cls: 'badge-replied' },
        'ignored': { label: '무시', cls: 'badge-ignored' },
    };

    let html = '';
    for (const item of items) {
        const st = statusMap[item.status] || { label: item.status, cls: '' };
        const date = item.received_at ? new Date(item.received_at).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
        html += `<div class="inbox-item${currentInboxId === item.id ? ' active' : ''}" onclick="loadInboxItem(${item.id})">
            <div class="inbox-item-from">${esc(item.from_name || item.from_addr)}</div>
            <div class="inbox-item-subject">${esc(item.subject || '(제목 없음)')}</div>
            <div class="inbox-item-meta">
                <span class="badge-status ${st.cls}">${st.label}</span>
                <span>${date}</span>
            </div>
        </div>`;
    }
    c.innerHTML = html;
    console.log('[DEBUG] 수신함 렌더링 완료, HTML 길이:', html.length);
}

// --- 수신 메일 클릭 → 본문 채우기 ---
async function loadInboxItem(id) {
    try {
        console.log('[DEBUG] 수신 메일 로드:', id);
        const data = await (await api(`/admin/mail/gmail/inbox/${id}`)).json();
        currentInboxId = id;

        // 수신 메일 textarea에 채우기
        const bodyText = `From: ${data.from_name || ''} <${data.from_addr}>\nSubject: ${data.subject || ''}\n\n${data.body || ''}`;
        const mailIncoming = document.getElementById('mailIncoming');
        if (mailIncoming) mailIncoming.value = bodyText;

        // HTML 메일이 있으면 iframe에 표시
        const htmlDiv = document.getElementById('mailIncomingHtml');
        const htmlFrame = document.getElementById('mailHtmlFrame');
        if (htmlDiv && htmlFrame && data.body_html) {
            htmlFrame.srcdoc = data.body_html;
            htmlDiv.style.display = '';
            if (mailIncoming) mailIncoming.style.display = 'none';
        } else {
            if (htmlDiv) htmlDiv.style.display = 'none';
            if (mailIncoming) mailIncoming.style.display = '';
        }

        // 초안이 있으면 채우기
        const koreanDraft = document.getElementById('mailKoreanDraft');
        const translated = document.getElementById('mailTranslated');
        const targetLang = document.getElementById('mailTargetLang');
        const translateBtn = document.getElementById('mailTranslateBtn');
        const retranslateBtn = document.getElementById('mailRetranslateBtn');
        const saveBtn = document.getElementById('mailSaveBtn');

        if (data.draft) {
            if (koreanDraft) koreanDraft.value = data.draft.korean_draft || '';
            if (translated) translated.value = data.draft.translated_draft || '';
            mailDetectedLang = data.draft.detected_lang || 'en';
            if (data.draft.detected_lang && data.draft.detected_lang !== 'ko' && targetLang) {
                targetLang.value = data.draft.detected_lang;
            }
            updateTargetLangBadge();
            if (translateBtn) translateBtn.disabled = false;
            if (retranslateBtn) retranslateBtn.disabled = !(data.draft.translated_draft);
            if (saveBtn) saveBtn.disabled = false;
        } else {
            if (koreanDraft) koreanDraft.value = '';
            if (translated) translated.value = '';
        }

        // 분석 숨기기 + 번역 분할 뷰 리셋
        const mailAnalysis = document.getElementById('mailAnalysis');
        const mailIncomingSplit = document.getElementById('mailIncomingSplit');
        if (mailAnalysis) mailAnalysis.classList.remove('visible');
        if (mailIncomingSplit) mailIncomingSplit.classList.remove('visible');

        // 발송 버튼 활성화 (번역본이 있을 때)
        const sendBtn = document.getElementById('mailSendBtn');
        if (sendBtn) {
            if (data.draft && (data.draft.translated_draft || data.draft.korean_draft)) {
                sendBtn.disabled = false;
            } else {
                sendBtn.disabled = true;
            }
        }

        // 활성 표시
        document.querySelectorAll('.inbox-item').forEach(el => el.classList.remove('active'));
        const clicked = document.querySelector(`.inbox-item[onclick*="loadInboxItem(${id})"]`);
        if (clicked) clicked.classList.add('active');

        // 이력 탭이 열려있으면 자동으로 이력 업데이트
        const historyPanel = document.getElementById('mailSidePanelHistory');
        if (historyPanel && historyPanel.style.display === 'block') {
            loadMailHistoryForInbox();
        }

        console.log('[DEBUG] 수신 메일 로드 완료');

    } catch (e) {
        console.error('[ERROR] 수신 메일 로드 실패:', e);
        alert('수신 메일을 불러오는데 실패했습니다.');
    }
}

// HTML/텍스트 뷰 전환
function toggleMailHtmlView() {
    const htmlDiv = document.getElementById('mailIncomingHtml');
    const textarea = document.getElementById('mailIncoming');
    const btn = htmlDiv.querySelector('button');

    if (htmlDiv.style.display !== 'none') {
        htmlDiv.style.display = 'none';
        textarea.style.display = '';
        btn.textContent = 'HTML 보기';
    } else {
        htmlDiv.style.display = '';
        textarea.style.display = 'none';
        btn.textContent = '텍스트 보기';
    }
}

// --- 답장 발송 ---
async function sendMailReply() {
    if (!currentInboxId) { alert('발송할 수신 메일을 선택하세요.'); return; }

    const translated = document.getElementById('mailTranslated').value.trim();
    const korean = document.getElementById('mailKoreanDraft').value.trim();
    if (!translated && !korean) { alert('발송할 답장 내용이 없습니다.'); return; }

    if (!confirm('이 답장을 발송하시겠습니까?')) return;

    showMailLoading('메일을 저장·발송하는 중...');
    try {
        // 먼저 저장 (composition_id 연결을 위해)
        const incoming = document.getElementById('mailIncoming').value.trim();
        if (incoming && korean) {
            const saveResp = await (await api('/admin/mail/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    incoming_email: incoming,
                    detected_lang: mailDetectedLang,
                    tone: document.getElementById('mailTone').value,
                    korean_draft: korean,
                    translated_draft: translated,
                    document_ids: getMailSelectedDocIds(),
                    refs: mailCurrentRefs,
                }),
            })).json();

            // inbox_emails에 composition_id 연결
            await api(`/admin/mail/gmail/inbox/${currentInboxId}/link?composition_id=${saveResp.id}`, {
                method: 'POST',
            });
        }

        const resp = await api(`/admin/mail/gmail/send/${currentInboxId}`, { method: 'POST' });
        const data = await resp.json();
        if (!resp.ok) { alert(data.detail || '발송 실패'); return; }
        alert('메일이 발송되었습니다!');
        loadInboxEmails();
        loadMailHistory();
    } catch (e) {
        alert('메일 발송 오류: ' + e.message);
    } finally {
        hideMailLoading();
    }
}

// ============================================================
//  메일 템플릿 관리
// ============================================================

var mailTemplates = [];
var currentCategoryFilter = '';

async function loadTemplates() {
    try {
        const url = currentCategoryFilter ? `/admin/mail/templates?category=${currentCategoryFilter}` : '/admin/mail/templates';
        const res = await api(url);
        mailTemplates = await res.json();
        renderTemplates();
    } catch (e) {
        console.error('템플릿 로드 실패:', e);
        document.getElementById('templateList').innerHTML = '<div class="empty-state" style="padding:20px 10px;font-size:0.8rem;color:var(--error)">로드 실패</div>';
    }
}

function renderTemplates() {
    const container = document.getElementById('templateList');
    if (!mailTemplates.length) {
        container.innerHTML = '<div class="empty-state" style="padding:20px 10px;font-size:0.8rem"><div style="font-size:1.2rem;margin-bottom:6px;">&#128221;</div>등록된 템플릿이 없습니다</div>';
        return;
    }

    const categoryNames = {general: '일반', quotation: '견적', inquiry: '문의', 'follow-up': '후속'};

    container.innerHTML = mailTemplates.map(tpl => `
        <div style="background:white;border:1px solid var(--border);border-radius:8px;padding:10px;margin-bottom:8px;">
            <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:6px;">
                <div>
                    <div style="font-size:0.85rem;font-weight:600;color:var(--text-regular);">${tpl.name}</div>
                    <div style="font-size:0.7rem;color:var(--text-muted);margin-top:2px;">${categoryNames[tpl.category] || tpl.category}</div>
                </div>
                <div style="display:flex;gap:4px;">
                    <button onclick="useTemplate(${tpl.id})" style="font-size:0.7rem;padding:2px 6px;background:var(--accent);color:white;border:none;border-radius:4px;cursor:pointer;" title="사용">&#10004;</button>
                    <button onclick="editTemplate(${tpl.id})" style="font-size:0.7rem;padding:2px 6px;background:var(--primary);color:white;border:none;border-radius:4px;cursor:pointer;" title="수정">&#9998;</button>
                    <button onclick="deleteTemplate(${tpl.id})" style="font-size:0.7rem;padding:2px 6px;background:var(--error);color:white;border:none;border-radius:4px;cursor:pointer;" title="삭제">&#128465;</button>
                </div>
            </div>
            <div style="font-size:0.75rem;color:var(--text-regular);background:var(--bg-gray);padding:6px;border-radius:4px;white-space:pre-wrap;max-height:80px;overflow-y:auto;">${tpl.content}</div>
        </div>
    `).join('');
}

function filterTemplates() {
    currentCategoryFilter = document.getElementById('templateCategoryFilter').value;
    loadTemplates();
}

function showTemplateForm() {
    document.getElementById('templateForm').style.display = 'block';
    document.getElementById('templateId').value = '';
    document.getElementById('templateName').value = '';
    document.getElementById('templateCategory').value = 'general';
    document.getElementById('templateContent').value = '';
}

function hideTemplateForm() {
    document.getElementById('templateForm').style.display = 'none';
}

function editTemplate(id) {
    const tpl = mailTemplates.find(t => t.id === id);
    if (!tpl) return;

    document.getElementById('templateForm').style.display = 'block';
    document.getElementById('templateId').value = tpl.id;
    document.getElementById('templateName').value = tpl.name;
    document.getElementById('templateCategory').value = tpl.category;
    document.getElementById('templateContent').value = tpl.content;
    document.getElementById('templateForm').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function saveTemplate() {
    const id = document.getElementById('templateId').value;
    const name = document.getElementById('templateName').value.trim();
    const category = document.getElementById('templateCategory').value;
    const content = document.getElementById('templateContent').value.trim();

    if (!name || !content) {
        alert('템플릿 이름과 내용을 입력해주세요.');
        return;
    }

    // 변수 추출 ({{변수명}} 형식)
    const variables = [...new Set(content.match(/\{\{([^}]+)\}\}/g)?.map(v => v.replace(/[{}]/g, '')) || [])];

    const body = { name, category, content, variables };

    try {
        if (id) {
            await api(`/admin/mail/templates/${id}`, { method: 'PUT', body: JSON.stringify(body) });
            alert('템플릿이 수정되었습니다.');
        } else {
            await api('/admin/mail/templates', { method: 'POST', body: JSON.stringify(body) });
            alert('템플릿이 추가되었습니다.');
        }
        hideTemplateForm();
        loadTemplates();
    } catch (e) {
        console.error('저장 실패:', e);
        alert('저장에 실패했습니다: ' + e.message);
    }
}

async function deleteTemplate(id) {
    if (!confirm('이 템플릿을 삭제하시겠습니까?')) return;

    try {
        await api(`/admin/mail/templates/${id}`, { method: 'DELETE' });
        alert('템플릿이 삭제되었습니다.');
        loadTemplates();
    } catch (e) {
        console.error('삭제 실패:', e);
        alert('삭제에 실패했습니다: ' + e.message);
    }
}

function useTemplate(id) {
    const tpl = mailTemplates.find(t => t.id === id);
    if (!tpl) return;

    let content = tpl.content;

    // 변수가 있으면 치환
    if (tpl.variables && tpl.variables.length > 0) {
        const values = {};
        for (const varName of tpl.variables) {
            const value = prompt(`${varName} 값을 입력하세요:`, '');
            if (value !== null) {
                values[varName] = value;
            }
        }
        // 치환
        for (const [key, val] of Object.entries(values)) {
            content = content.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), val);
        }
    }

    // 한국어 초안에 삽입
    document.getElementById('mailKoreanDraft').value = content;
    alert(`템플릿 "${tpl.name}"이(가) 적용되었습니다.`);
}

// ============================================================
//  프롬프트 예시 관리
// ============================================================

var promptExamples = [];

async function loadPromptExamples() {
    try {
        const res = await api('/admin/mail/prompt-examples');
        promptExamples = await res.json();
        renderPromptExamples();
    } catch (e) {
        console.error('프롬프트 예시 로드 실패:', e);
        document.getElementById('promptExampleList').innerHTML = '<div class="empty-state" style="padding:20px 10px;font-size:0.8rem;color:var(--error)">로드 실패</div>';
    }
}

function renderPromptExamples() {
    const container = document.getElementById('promptExampleList');
    if (!promptExamples.length) {
        container.innerHTML = '<div class="empty-state" style="padding:20px 10px;font-size:0.8rem"><div style="font-size:1.2rem;margin-bottom:6px;">&#128172;</div>등록된 예시가 없습니다</div>';
        return;
    }

    container.innerHTML = promptExamples.map(ex => `
        <div style="background:white;border:1px solid var(--border);border-radius:8px;padding:10px;margin-bottom:8px;">
            <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:6px;">
                <span style="font-size:0.7rem;color:var(--text-muted);font-weight:500;">순서: ${ex.sort_order}</span>
                <div style="display:flex;gap:4px;">
                    <button onclick="editPromptExample(${ex.id})" style="font-size:0.7rem;padding:2px 6px;background:var(--primary);color:white;border:none;border-radius:4px;cursor:pointer;" title="수정">&#9998;</button>
                    <button onclick="deletePromptExample(${ex.id})" style="font-size:0.7rem;padding:2px 6px;background:var(--error);color:white;border:none;border-radius:4px;cursor:pointer;" title="삭제">&#128465;</button>
                </div>
            </div>
            <div style="margin-bottom:6px;">
                <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px;">📨 수신:</div>
                <div style="font-size:0.75rem;color:var(--text-regular);background:var(--bg-gray);padding:6px;border-radius:4px;white-space:pre-wrap;max-height:80px;overflow-y:auto;">${ex.incoming_text}</div>
            </div>
            <div>
                <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:2px;">📧 답장:</div>
                <div style="font-size:0.75rem;color:var(--text-regular);background:var(--bg-gray);padding:6px;border-radius:4px;white-space:pre-wrap;max-height:80px;overflow-y:auto;">${ex.reply_text}</div>
            </div>
        </div>
    `).join('');
}

function showPromptExampleForm() {
    document.getElementById('promptExampleForm').style.display = 'block';
    document.getElementById('promptExampleId').value = '';
    document.getElementById('promptIncomingText').value = '';
    document.getElementById('promptReplyText').value = '';
    document.getElementById('promptSortOrder').value = promptExamples.length;
}

function hidePromptExampleForm() {
    document.getElementById('promptExampleForm').style.display = 'none';
    document.getElementById('promptExampleId').value = '';
    document.getElementById('promptIncomingText').value = '';
    document.getElementById('promptReplyText').value = '';
}

function editPromptExample(id) {
    const ex = promptExamples.find(e => e.id === id);
    if (!ex) return;

    document.getElementById('promptExampleForm').style.display = 'block';
    document.getElementById('promptExampleId').value = ex.id;
    document.getElementById('promptIncomingText').value = ex.incoming_text;
    document.getElementById('promptReplyText').value = ex.reply_text;
    document.getElementById('promptSortOrder').value = ex.sort_order;

    // 폼이 보이도록 스크롤
    document.getElementById('promptExampleForm').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function savePromptExample() {
    const id = document.getElementById('promptExampleId').value;
    const incomingText = document.getElementById('promptIncomingText').value.trim();
    const replyText = document.getElementById('promptReplyText').value.trim();
    const sortOrder = parseInt(document.getElementById('promptSortOrder').value) || 0;

    if (!incomingText || !replyText) {
        alert('수신 메일과 답장 예시를 모두 입력해주세요.');
        return;
    }

    const body = {
        incoming_text: incomingText,
        reply_text: replyText,
        sort_order: sortOrder
    };

    try {
        if (id) {
            // 수정
            await api(`/admin/mail/prompt-examples/${id}`, {
                method: 'PUT',
                body: JSON.stringify(body)
            });
            alert('예시가 수정되었습니다.');
        } else {
            // 생성
            await api('/admin/mail/prompt-examples', {
                method: 'POST',
                body: JSON.stringify(body)
            });
            alert('예시가 추가되었습니다.');
        }

        hidePromptExampleForm();
        loadPromptExamples();
    } catch (e) {
        console.error('저장 실패:', e);
        alert('저장에 실패했습니다: ' + e.message);
    }
}

async function deletePromptExample(id) {
    if (!confirm('이 예시를 삭제하시겠습니까?')) return;

    try {
        await api(`/admin/mail/prompt-examples/${id}`, {
            method: 'DELETE'
        });
        alert('예시가 삭제되었습니다.');
        loadPromptExamples();
    } catch (e) {
        console.error('삭제 실패:', e);
        alert('삭제에 실패했습니다: ' + e.message);
    }
}

// ============================================================
//  서명 관리
// ============================================================

var signatures = [];

async function loadSignatures() {
    try {
        const res = await api('/admin/mail/signatures');
        signatures = await res.json();
        renderSignatures();
        updateSignatureDropdown();
    } catch (e) {
        console.error('서명 로드 실패:', e);
        document.getElementById('signatureList').innerHTML = '<div class="empty-state" style="padding:20px 10px;font-size:0.8rem;color:var(--error)">로드 실패</div>';
    }
}

function updateSignatureDropdown() {
    const select = document.getElementById('mailSignatureSelect');
    if (!select) return;

    select.innerHTML = '<option value="">서명 없음</option>';
    signatures.forEach(sig => {
        const option = document.createElement('option');
        option.value = sig.id;
        option.textContent = sig.name + (sig.is_default ? ' (기본)' : '');
        if (sig.is_default) {
            option.selected = true;
        }
        select.appendChild(option);
    });
}

function renderSignatures() {
    const container = document.getElementById('signatureList');
    if (!signatures.length) {
        container.innerHTML = '<div class="empty-state" style="padding:20px 10px;font-size:0.8rem"><div style="font-size:1.2rem;margin-bottom:6px;">&#9998;</div>등록된 서명이 없습니다</div>';
        return;
    }

    container.innerHTML = signatures.map(sig => `
        <div style="background:white;border:1px solid var(--border);border-radius:8px;padding:10px;margin-bottom:8px;${sig.is_default ? 'border-color:var(--primary);border-width:2px;' : ''}">
            <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:6px;">
                <div style="display:flex;align-items:center;gap:6px;">
                    <span style="font-size:0.85rem;font-weight:600;color:var(--text-regular);">${sig.name}</span>
                    ${sig.is_default ? '<span style="font-size:0.65rem;background:var(--primary);color:white;padding:2px 6px;border-radius:4px;">기본</span>' : ''}
                </div>
                <div style="display:flex;gap:4px;">
                    <button onclick="editSignature(${sig.id})" style="font-size:0.7rem;padding:2px 6px;background:var(--primary);color:white;border:none;border-radius:4px;cursor:pointer;" title="수정">&#9998;</button>
                    <button onclick="deleteSignature(${sig.id})" style="font-size:0.7rem;padding:2px 6px;background:var(--error);color:white;border:none;border-radius:4px;cursor:pointer;" title="삭제">&#128465;</button>
                </div>
            </div>
            <div style="font-size:0.75rem;color:var(--text-regular);background:var(--bg-gray);padding:8px;border-radius:4px;white-space:pre-wrap;max-height:120px;overflow-y:auto;font-family:monospace;">${sig.content}</div>
        </div>
    `).join('');
}

function showSignatureForm() {
    document.getElementById('signatureForm').style.display = 'block';
    document.getElementById('signatureId').value = '';
    document.getElementById('signatureName').value = '';
    document.getElementById('signatureContent').value = '';
    document.getElementById('signatureIsDefault').checked = false;
}

function hideSignatureForm() {
    document.getElementById('signatureForm').style.display = 'none';
    document.getElementById('signatureId').value = '';
    document.getElementById('signatureName').value = '';
    document.getElementById('signatureContent').value = '';
    document.getElementById('signatureIsDefault').checked = false;
}

function editSignature(id) {
    const sig = signatures.find(s => s.id === id);
    if (!sig) return;

    document.getElementById('signatureForm').style.display = 'block';
    document.getElementById('signatureId').value = sig.id;
    document.getElementById('signatureName').value = sig.name;
    document.getElementById('signatureContent').value = sig.content;
    document.getElementById('signatureIsDefault').checked = sig.is_default;

    // 폼이 보이도록 스크롤
    document.getElementById('signatureForm').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function saveSignature() {
    const id = document.getElementById('signatureId').value;
    const name = document.getElementById('signatureName').value.trim();
    const content = document.getElementById('signatureContent').value.trim();
    const isDefault = document.getElementById('signatureIsDefault').checked;

    if (!name || !content) {
        alert('서명 이름과 내용을 모두 입력해주세요.');
        return;
    }

    const body = {
        name: name,
        content: content,
        is_default: isDefault
    };

    try {
        if (id) {
            // 수정
            await api(`/admin/mail/signatures/${id}`, {
                method: 'PUT',
                body: JSON.stringify(body)
            });
            alert('서명이 수정되었습니다.');
        } else {
            // 생성
            await api('/admin/mail/signatures', {
                method: 'POST',
                body: JSON.stringify(body)
            });
            alert('서명이 추가되었습니다.');
        }

        hideSignatureForm();
        loadSignatures();
    } catch (e) {
        console.error('저장 실패:', e);
        alert('저장에 실패했습니다: ' + e.message);
    }
}

async function deleteSignature(id) {
    if (!confirm('이 서명을 삭제하시겠습니까?')) return;

    try {
        await api(`/admin/mail/signatures/${id}`, {
            method: 'DELETE'
        });
        alert('서명이 삭제되었습니다.');
        loadSignatures();
    } catch (e) {
        console.error('삭제 실패:', e);
        alert('삭제에 실패했습니다: ' + e.message);
    }
}

function insertSignature() {
    const select = document.getElementById('mailSignatureSelect');
    const sigId = parseInt(select.value);

    if (!sigId) {
        alert('서명을 선택해주세요.');
        return;
    }

    const sig = signatures.find(s => s.id === sigId);
    if (!sig) {
        alert('서명을 찾을 수 없습니다.');
        return;
    }

    const textarea = document.getElementById('mailKoreanDraft');
    const currentContent = textarea.value.trim();

    // 이미 서명이 있는지 확인 (간단히 마지막 부분 체크)
    if (currentContent && !currentContent.endsWith('\n\n')) {
        textarea.value = currentContent + '\n\n' + sig.content;
    } else if (currentContent) {
        textarea.value = currentContent + sig.content;
    } else {
        textarea.value = sig.content;
    }

    // 커서를 끝으로 이동
    textarea.scrollTop = textarea.scrollHeight;
}

function getDefaultSignature() {
    return signatures.find(s => s.is_default);
}

// 메일 탭용 서명 로드 (사이드바 UI는 업데이트하지 않음)
async function loadSignaturesForMail() {
    try {
        const res = await api('/admin/mail/signatures');
        signatures = await res.json();
        updateSignatureDropdown();
    } catch (e) {
        console.error('서명 로드 실패:', e);
    }
}

/**
 * 메일 패널 전환 (수신함/문서/템플릿 등)
 */
function showMailPanel(panel) {
    console.log('메일 패널 열기:', panel);

    // mailSettingsModal 표시
    const modal = document.getElementById('mailSettingsModal');
    if (!modal) {
        console.error('mailSettingsModal을 찾을 수 없습니다');
        return;
    }

    modal.style.display = 'flex';

    // switchMailSettingsTab 호출하여 적절한 탭 표시
    switchMailSettingsTab(panel);
}

function hideMailPanel() {
    showMailPanel('compose');
}

// ===== 개선된 UI 컨트롤 함수들 (3-Panel 레이아웃) =====

/**
 * 읽기 패널 탭 전환 (원문/번역)
 */
function switchMailReadTab(tabName) {
    const tabs = ['original', 'translated'];
    tabs.forEach(t => {
        const btn = document.getElementById(`tabRead${t.charAt(0).toUpperCase() + t.slice(1)}`);
        const content = document.getElementById(`mailRead${t.charAt(0).toUpperCase() + t.slice(1)}Content`);
        if (t === tabName) {
            btn?.classList.add('active');
            if (content) content.style.display = 'flex';
        } else {
            btn?.classList.remove('active');
            if (content) content.style.display = 'none';
        }
    });
}

/**
 * 읽기 패널 접기/펴기
 */
function toggleMailReadPanel() {
    const panel = document.getElementById('mailReadPanel');
    const expandBtn = document.getElementById('mailReadExpandBtn');

    if (panel && expandBtn) {
        if (panel.classList.contains('collapsed')) {
            panel.classList.remove('collapsed');
            expandBtn.style.display = 'none';
        } else {
            panel.classList.add('collapsed');
            expandBtn.style.display = 'block';
        }
    }
}

/**
 * 작성 패널 탭 전환 (초안/최종)
 */
function switchMailWriteTab(tabName) {
    const container = document.getElementById('mailEditorContainer');
    const mode = container?.classList.contains('split-mode') ? 'split' : 'tab';
    if (mode === 'split') return; // 비교 모드에서는 탭 전환 불가

    const tabs = ['draft', 'final'];
    tabs.forEach(t => {
        const btn = document.getElementById(`tabWrite${t.charAt(0).toUpperCase() + t.slice(1)}`);
        const area = document.getElementById(`mailEditor${t.charAt(0).toUpperCase() + t.slice(1)}`);
        if (t === tabName) {
            btn?.classList.add('active');
            if (area) area.style.display = 'flex';
        } else {
            btn?.classList.remove('active');
            if (area) area.style.display = 'none';
        }
    });
}

/**
 * 작성 뷰 모드 전환 (탭/비교)
 */
function setMailViewMode(mode) {
    const container = document.getElementById('mailEditorContainer');
    const draftArea = document.getElementById('mailEditorDraft');
    const finalArea = document.getElementById('mailEditorFinal');
    const divider = document.getElementById('mailEditorDivider');
    const tabs = document.getElementById('mailWriteTabs');
    const btnTab = document.getElementById('modeBtnTab');
    const btnSplit = document.getElementById('modeBtnSplit');

    if (!container) return;

    if (mode === 'split') {
        // 비교 모드
        btnSplit?.classList.add('active');
        btnTab?.classList.remove('active');
        container.classList.add('split-mode');
        if (draftArea) draftArea.style.display = 'flex';
        if (finalArea) finalArea.style.display = 'flex';
        if (divider) divider.style.display = 'flex';
        if (tabs) tabs.style.display = 'none';
    } else {
        // 탭 모드
        btnTab?.classList.add('active');
        btnSplit?.classList.remove('active');
        container.classList.remove('split-mode');
        if (divider) divider.style.display = 'none';
        if (tabs) tabs.style.display = 'flex';
        // 현재 활성 탭 유지
        const activeTab = document.querySelector('.mail-write-tabs .mail-tab.active')?.id;
        if (activeTab === 'tabWriteFinal') {
            switchMailWriteTab('final');
        } else {
            switchMailWriteTab('draft');
        }
    }
}

/**
 * 빠른 작업 모달 표시
 */
function showQuickActions() {
    const modal = document.getElementById('quickActionsModal');
    if (modal) modal.style.display = 'flex';
}

/**
 * 빠른 작업 모달 숨김
 */
function hideQuickActions() {
    const modal = document.getElementById('quickActionsModal');
    if (modal) modal.style.display = 'none';
}

/**
 * 설정 모달 표시 (템플릿, 서명 등)
 */
function showMailSettings() {
    const modal = document.getElementById('mailSettingsModal');
    if (modal) {
        modal.style.display = 'flex';
        switchMailSettingsTab('templates');
    }
}

/**
 * 설정 모달 숨김
 */
function hideMailSettings() {
    const modal = document.getElementById('mailSettingsModal');
    if (modal) modal.style.display = 'none';
}

/**
 * 설정 모달 탭 전환
 */
function switchMailSettingsTab(tabName) {
    const tabs = ['templates', 'signatures', 'docs', 'history', 'prompts'];
    tabs.forEach(t => {
        const btns = document.querySelectorAll('.modal-tabs .modal-tab');
        btns.forEach(btn => {
            if (btn.textContent.includes(getTabLabelByName(t))) {
                if (t === tabName) btn.classList.add('active');
                else btn.classList.remove('active');
            }
        });

        const content = document.getElementById(`mailSidePanel${t.charAt(0).toUpperCase() + t.slice(1)}`);
        if (content) {
            content.style.display = (t === tabName) ? 'block' : 'none';
        }
    });

    // 패널별로 데이터 로드
    if (tabName === 'templates') loadTemplates();
    else if (tabName === 'signatures') loadSignatures();
    else if (tabName === 'docs') loadMailDocuments();
    else if (tabName === 'history') loadMailHistoryForInbox();
    else if (tabName === 'prompts') loadPromptExamples();
}

function getTabLabelByName(name) {
    const labels = {
        'templates': '템플릿',
        'signatures': '서명',
        'docs': '참조 문서',
        'history': '이력',
        'prompts': '프롬프트'
    };
    return labels[name] || name;
}

/**
 * AI 프롬프트 실행
 */
async function executeAIPrompt() {
    const input = document.getElementById('aiPromptInput');
    const prompt = input?.value.trim();

    if (!prompt) {
        alert('프롬프트를 입력해주세요.');
        return;
    }

    console.log('AI Prompt:', prompt);
    updateMailStatus('AI 처리 중...', 'processing');

    // TODO: 실제 AI API 호출 구현
    setTimeout(() => {
        updateMailStatus('대기 중', 'default');
        alert('AI 프롬프트 기능은 추후 구현 예정입니다.');
    }, 2000);
}

/**
 * 메일 상태 업데이트
 */
function updateMailStatus(text, type = 'default') {
    const indicator = document.getElementById('mailStatusIndicator');
    if (!indicator) return;

    indicator.className = 'mail-status ' + type;
    indicator.innerHTML = `<span class="status-dot"></span>${text}`;
}

/**
 * 메일 분석 정보 표시
 */
function showMailAnalysis(analysisText) {
    const analysisDiv = document.getElementById('mailAnalysis');
    const textDiv = document.getElementById('mailAnalysisText');
    if (analysisDiv && textDiv) {
        textDiv.textContent = analysisText;
        analysisDiv.classList.add('active');
    }
}

/**
 * 메일 분석 정보 숨김
 */
function hideMailAnalysis() {
    const analysisDiv = document.getElementById('mailAnalysis');
    if (analysisDiv) {
        analysisDiv.classList.remove('active');
    }
}

/**
 * 선택된 수신 메일의 작성 이력 로드
 */
async function loadMailHistoryForInbox() {
    const historyList = document.getElementById('mailHistoryList');
    const emailInfo = document.getElementById('historyEmailInfo');
    const emailSubject = document.getElementById('historyEmailSubject');
    const emailFrom = document.getElementById('historyEmailFrom');

    if (!currentInboxId) {
        historyList.innerHTML = '<div class="empty-state-sm">왼쪽 수신함에서 메일을 선택하면<br/>해당 메일의 작성 이력이 표시됩니다</div>';
        emailInfo.style.display = 'none';
        return;
    }

    try {
        console.log('수신 메일 이력 로드:', currentInboxId);

        // 수신 메일 정보 가져오기
        const inboxData = await (await api(`/admin/mail/gmail/inbox/${currentInboxId}`)).json();

        // 메일 정보 표시
        emailSubject.textContent = inboxData.subject || '(제목 없음)';
        emailFrom.textContent = `${inboxData.from_name || ''} <${inboxData.from_addr}>`;
        emailInfo.style.display = 'block';

        // 해당 메일의 작성 이력 가져오기 (inbox_id로 필터링)
        const allHistory = await (await api('/admin/mail/history')).json();
        const filteredHistory = allHistory.filter(h => h.inbox_id === currentInboxId);

        if (!filteredHistory.length) {
            historyList.innerHTML = '<div class="empty-state-sm">이 메일에 대한 작성 이력이 없습니다</div>';
            return;
        }

        // 이력 렌더링
        let html = '';
        for (const item of filteredHistory) {
            const date = item.created_at ? new Date(item.created_at).toLocaleString('ko-KR', {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            }) : '';

            html += `
                <div class="history-item" onclick="loadHistoryItem(${item.id})">
                    <div class="history-item-header">
                        <span class="history-item-date">${date}</span>
                        ${item.is_sent ? '<span class="badge badge-done">발송완료</span>' : '<span class="badge badge-draft">임시저장</span>'}
                    </div>
                    <div class="history-item-preview">${esc(item.korean_draft ? item.korean_draft.substring(0, 100) : '')}</div>
                </div>
            `;
        }
        historyList.innerHTML = html;

    } catch (e) {
        console.error('이력 로드 실패:', e);
        historyList.innerHTML = '<div class="empty-state-sm">이력을 불러오는데 실패했습니다</div>';
    }
}

/**
 * 이력 항목 클릭 시 내용 불러오기
 */
async function loadHistoryItem(historyId) {
    try {
        const item = await (await api(`/admin/mail/history/${historyId}`)).json();

        // 수신 메일 표시
        document.getElementById('mailIncoming').value = item.incoming_email || '';

        // 초안 채우기
        document.getElementById('mailKoreanDraft').value = item.korean_draft || '';
        document.getElementById('mailTranslated').value = item.translated_draft || '';

        // 언어 설정
        if (item.detected_lang) {
            mailDetectedLang = item.detected_lang;
            if (item.detected_lang !== 'ko') {
                document.getElementById('mailTargetLang').value = item.detected_lang;
            }
            updateTargetLangBadge();
        }

        // 버튼 활성화
        document.getElementById('mailTranslateBtn').disabled = false;
        document.getElementById('mailSaveBtn').disabled = false;

        console.log('이력 항목 로드 완료:', historyId);

    } catch (e) {
        console.error('이력 항목 로드 실패:', e);
        alert('이력을 불러오는데 실패했습니다.');
    }
}
