/**
 * rag.js
 * RAG (문서 내 Q&A) 챗봇 기능
 */

// 전역 변수
var currentConvId = null;
var ragDocuments = [];
var isLoadingConversation = false;  // 대화 로딩 중복 방지

async function loadConversations() {
    console.log('📋 [DEBUG] 대화 목록 로드 시작');
    try {
        console.log('📋 [DEBUG] API 호출 중: /admin/rag/conversations');
        var res = await api('/admin/rag/conversations');
        console.log('📋 [DEBUG] API 응답 받음:', res.status);

        var data = await res.json();
        console.log('📋 [DEBUG] 대화 개수:', data.length);

        renderConversations(data);
        console.log('📋 [DEBUG] 렌더링 완료');
    } catch (e) {
        console.error('❌ [ERROR] 대화 목록 로드 실패:', e);
        var c = document.getElementById('convList');
        if (c) {
            c.innerHTML = '<div class="empty-state" style="padding:32px 12px;font-size:0.82rem;color:var(--error);">대화 목록 로드 실패<br><small>' + e.message + '</small></div>';
        }
    }
}

function renderConversations(convs) {
    console.log('🎨 [DEBUG] renderConversations 시작, 대화 수:', convs.length);
    var c = document.getElementById('convList');

    if (!c) {
        console.error('❌ [ERROR] convList 엘리먼트를 찾을 수 없습니다!');
        return;
    }

    if (!convs.length) {
        console.log('🎨 [DEBUG] 대화 없음, 빈 상태 표시');
        c.innerHTML = '<div class="empty-state" style="padding:32px 12px;font-size:0.82rem"><div style="font-size:1.3rem;margin-bottom:6px;">&#128172;</div>새 대화를 시작하세요</div>';
        updateChatHeader(null);
        return;
    }

    console.log('🎨 [DEBUG] 대화 분류 시작');

    // 3그룹으로 분류: 저장된 대화, 오늘, 7일 이내
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    const saved = [];
    const today = [];
    const recent = [];

    for (const cv of convs) {
        if (cv.saved) {
            saved.push(cv);
        } else {
            const updated = cv.updated_at ? new Date(cv.updated_at) : new Date();
            if (updated >= todayStart) {
                today.push(cv);
            } else {
                recent.push(cv);
            }
        }
    }

    let html = '';

    const renderGroup = (label, items, showDaysLeft) => {
        if (!items.length) return '';
        let groupHtml = `<div class="conv-group-header">${label}</div>`;
        for (const cv of items) {
            const daysLeft = getDaysLeft(cv.updated_at);
            const savedIcon = cv.saved ? '<span class="conv-saved-badge">&#11088;</span> ' : '';
            const ageText = cv.saved ? '영구 보관' : `${daysLeft}일 후 삭제`;
            groupHtml += `<div class="conv-item ${cv.id===currentConvId?'active':''}" onclick="selectConversation(${cv.id})">
                <div class="conv-item-icon">&#128172;</div>
                <div style="flex:1;min-width:0">
                    <span class="conv-title">${savedIcon}${esc(cv.title)}</span>
                    <div class="conv-age">${ageText}</div>
                </div>
                <div class="conv-kebab" id="kebab-${cv.id}" onclick="event.stopPropagation()">
                    <button class="conv-kebab-btn" onclick="toggleKebab(event,${cv.id})">&#8943;</button>
                    <div class="conv-kebab-menu" id="kebab-menu-${cv.id}">
                        <button class="conv-kebab-menu-item" onclick="toggleSaveFromList(${cv.id});closeAllKebabs()">${cv.saved?'&#11088; 저장 해제':'&#9734; 저장'}</button>
                        <button class="conv-kebab-menu-item" onclick="closeAllKebabs();startRename(${cv.id},'${esc(cv.title).replace(/'/g,"\\&#39;")}')">&#9998; 이름 변경</button>
                        <button class="conv-kebab-menu-item danger" onclick="closeAllKebabs();deleteConversation(${cv.id})">&#128465; 삭제</button>
                    </div>
                </div>
            </div>`;
        }
        return groupHtml;
    };

    html += renderGroup('&#11088; 저장한 대화내역', saved, false);
    html += renderGroup('&#128197; 오늘', today, true);
    html += renderGroup('&#128336; 7일 이내', recent, true);

    console.log('🎨 [DEBUG] HTML 생성 완료, 길이:', html.length);
    c.innerHTML = html;
    console.log('🎨 [DEBUG] DOM 업데이트 완료');

    // 현재 대화 헤더 업데이트
    if (currentConvId) {
        var current = convs.find(cv => cv.id === currentConvId);
        updateChatHeader(current);
    }
    console.log('✅ [DEBUG] renderConversations 완료');
}

function getDaysLeft(updatedAt) {
    if (!updatedAt) return 7;
    const updated = new Date(updatedAt);
    const expiry = new Date(updated.getTime() + 7 * 24 * 60 * 60 * 1000);
    const now = new Date();
    const diff = Math.ceil((expiry - now) / (24 * 60 * 60 * 1000));
    return Math.max(0, diff);
}

function updateChatHeader(conv) {
    const bar = document.getElementById('chatHeaderBar');
    const title = document.getElementById('chatHeaderTitle');
    const saveBtn = document.getElementById('chatSaveBtn');
    if (conv) {
        bar.classList.add('visible');
        title.textContent = conv.title;
        if (conv.saved) {
            saveBtn.innerHTML = '&#11088; 저장됨';
            saveBtn.style.color = 'var(--warning)';
            saveBtn.style.borderColor = 'var(--warning)';
        } else {
            saveBtn.innerHTML = '&#9734; 저장';
            saveBtn.style.color = '';
            saveBtn.style.borderColor = '';
        }
    } else {
        bar.classList.remove('visible');
    }
}

async function createConversation() {
    try {
        const cv = await (await api('/admin/rag/conversations', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: '새 대화' }),
        })).json();
        currentConvId = cv.id;
        await loadConversations();
        renderEmptyChat();
        switchToChatMode();
        setChatEnabled(true);
    } catch (e) { console.error('대화 생성 실패:', e); }
}

async function selectConversation(convId) {
    console.log('💬 [DEBUG] selectConversation 호출, convId:', convId);

    // 이미 로딩 중이면 무시 (중복 호출 방지)
    if (isLoadingConversation) {
        console.log('⏸️ [DEBUG] 이미 대화 로딩 중입니다. 무시.');
        return;
    }

    // 같은 대화를 다시 클릭한 경우 무시
    if (currentConvId === convId) {
        console.log('⏸️ [DEBUG] 같은 대화 재클릭. 무시.');
        return;
    }

    console.log('💬 [DEBUG] 대화 로딩 시작');
    isLoadingConversation = true;
    currentConvId = convId;

    try {
        console.log('💬 [DEBUG] active 상태 업데이트 중...');
        // active 상태만 업데이트 (전체 재렌더링 제거)
        document.querySelectorAll('.conv-item').forEach(item => {
            item.classList.remove('active');
        });
        var activeItem = document.querySelector(`.conv-item[onclick*="${convId}"]`);
        if (activeItem) activeItem.classList.add('active');

        console.log('💬 [DEBUG] 로딩 표시 중...');
        // 로딩 표시
        var chatContainer = document.getElementById('chatMessages');
        chatContainer.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100%;"><div style="text-align:center;"><div style="font-size:2rem;margin-bottom:10px;">⏳</div><div style="color:var(--text-muted);">대화 로딩 중...</div></div></div>';

        console.log('💬 [DEBUG] loadConversation 호출 전...');
        await loadConversation(convId);
        console.log('💬 [DEBUG] loadConversation 완료!');

        console.log('💬 [DEBUG] switchToChatMode 호출...');
        switchToChatMode();
        console.log('💬 [DEBUG] setChatEnabled 호출...');
        setChatEnabled(true);

        // 실시간 polling 시작
        console.log('🔄 [DEBUG] 실시간 polling 시작 요청...');
        startRealtimePolling();

        console.log('✅ [DEBUG] selectConversation 완료!');
    } catch (e) {
        console.error('❌ [ERROR] 대화 선택 실패:', e);
        alert('대화를 불러오는데 실패했습니다: ' + e.message);
    } finally {
        console.log('💬 [DEBUG] finally 블록 - isLoadingConversation = false');
        isLoadingConversation = false;
    }
}

async function loadConversation(convId) {
    console.log('💬 [DEBUG] loadConversation 시작, convId:', convId);
    try {
        console.log('💬 [DEBUG] API_BASE:', API_BASE);
        console.log('💬 [DEBUG] authToken:', authToken ? '있음 (길이: ' + authToken.length + ')' : '없음');
        console.log('💬 [DEBUG] API 호출 중:', `/admin/rag/conversations/${convId}`);
        console.log('💬 [DEBUG] 전체 URL:', API_BASE + `/admin/rag/conversations/${convId}`);

        var res = await api(`/admin/rag/conversations/${convId}`);
        console.log('💬 [DEBUG] API 응답 받음, status:', res.status);

        if (!res.ok) {
            throw new Error('API 응답 실패: ' + res.status);
        }

        console.log('💬 [DEBUG] JSON 파싱 중...');
        var data = await res.json();
        console.log('💬 [DEBUG] JSON 파싱 완료');
        console.log('💬 [DEBUG] 메시지 개수:', data.messages?.length);
        console.log('💬 [DEBUG] 데이터 구조:', Object.keys(data));

        console.log('💬 [DEBUG] renderChatMessages 호출 전...');
        renderChatMessages(data.messages);
        console.log('✅ [DEBUG] renderChatMessages 완료');
        console.log('✅ [DEBUG] loadConversation 완료');
    } catch (e) {
        console.error('❌ [ERROR] 대화 로드 실패:', e);
        console.error('❌ [ERROR] 에러 스택:', e.stack);
        var chatContainer = document.getElementById('chatMessages');
        if (chatContainer) {
            chatContainer.innerHTML = '<div style="padding:40px;text-align:center;color:var(--error);">대화 로드 실패<br><small>' + e.message + '</small></div>';
        }
        throw e; // 상위로 전파
    }
}

function renderEmptyChat() {
    document.getElementById('chatMessages').innerHTML = `
        <div class="chat-welcome" id="chatWelcome">
            <div class="chat-welcome-icon">&#9875;</div>
            <h3>새 대화가 시작되었습니다</h3>
            <p>오른쪽 패널에서 참조할 문서를 선택하고<br>질문을 입력하세요</p>
        </div>`;
}

function renderMd(str) {
    if (!str) return '';

    try {
        // marked.parse()가 멈추는 문제로 인해 fallback만 사용
        console.log('📝 [DEBUG] Fallback 마크다운 렌더링 사용');
        var s = esc(str);

        // 코드 블록 (```)
        s = s.replace(/```([\s\S]*?)```/g, '<pre style="background:var(--bg-gray);padding:8px 10px;border-radius:6px;overflow-x:auto;font-size:0.82rem;margin:6px 0">$1</pre>');

        // 인라인 코드 (`)
        s = s.replace(/`([^`]+)`/g, '<code style="background:var(--bg-gray-100);padding:1px 5px;border-radius:4px;font-size:0.84em">$1</code>');

        // 굵게 (**)
        s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // 기울임 (*)
        s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');

        // 목록 (-, •)
        s = s.replace(/^[-•]\s+(.+)$/gm, '<li style="margin-left:16px;list-style:disc">$1</li>');

        // 번호 목록
        s = s.replace(/^\d+\.\s+(.+)$/gm, '<li style="margin-left:16px;list-style:decimal">$1</li>');

        // 줄바꿈을 <br>로
        s = s.replace(/\n/g, '<br>');

        return s;
    } catch (e) {
        console.error('❌ [ERROR] renderMd 실패:', e);
        // 에러 발생 시 안전하게 텍스트만 반환
        return esc(str);
    }
}

function renderChatMessages(messages) {
    console.log('🎨 [DEBUG] renderChatMessages 시작, messages:', messages?.length);
    var c = document.getElementById('chatMessages');
    if (!c) {
        console.error('❌ [ERROR] chatMessages 엘리먼트 없음!');
        return;
    }

    if (!messages || !messages.length) {
        console.log('🎨 [DEBUG] 메시지 없음, renderEmptyChat 호출');
        renderEmptyChat();
        return;
    }

    console.log('🎨 [DEBUG] HTML 생성 시작...');
    var html = '';
    for (var i = 0; i < messages.length; i++) {
        console.log('🎨 [DEBUG] 메시지 #' + i + ' 처리 중...');
        var m = messages[i];
        var refs = m.references || [];

        // AI 아바타: 로고 있으면 이미지, 없으면 "AI" 텍스트
        var avatar = m.role === 'user'
            ? 'U'
            : (siteLogoUrl ? '<img src="' + siteLogoUrl + '" alt="AI">' : 'AI');

        console.log('🎨 [DEBUG] 메시지 #' + i + ' 내용 렌더링 중... role:', m.role);
        var content = m.role === 'assistant' ? renderMd(m.content) : esc(m.content);
        console.log('🎨 [DEBUG] 메시지 #' + i + ' 내용 렌더링 완료');

        var time = m.created_at ? new Date(m.created_at).toLocaleTimeString('ko-KR', {hour:'2-digit',minute:'2-digit'}) : '';

        html += '<div class="msg-row ' + m.role + '">' +
            '<div class="msg-avatar">' + avatar + '</div>' +
            '<div class="msg-content">' +
                '<div class="msg-bubble">' + content + '</div>' +
                (time ? '<span class="msg-time">' + time + '</span>' : '') +
                (m.role === 'assistant' && refs.length ? '<span class="msg-refs-link" onclick=\'showRefChunks(' + JSON.stringify(refs).replace(/'/g,"&#39;") + ')\'>\&#128196; 참조 ' + refs.length + '건 보기</span>' : '') +
            '</div>' +
        '</div>';
    }
    console.log('🎨 [DEBUG] HTML 생성 완료, innerHTML 설정 중...');
    c.innerHTML = html;
    console.log('🎨 [DEBUG] innerHTML 설정 완료, 스크롤 조정 중...');
    c.scrollTop = c.scrollHeight;
    console.log('✅ [DEBUG] renderChatMessages 완료!');
}

async function deleteConversation(convId) {
    if (!confirm('이 대화를 삭제하시겠습니까?')) return;
    try {
        await api(`/admin/rag/conversations/${convId}`, { method: 'DELETE' });
        if (currentConvId === convId) {
            currentConvId = null;
            showWelcomeScreen();
            updateChatHeader(null);
        }
        loadConversations();
    } catch (e) { console.error('대화 삭제 실패:', e); }
}

// --- 대화 이름 변경 ---
function startRename(convId, currentTitle) {
    const item = document.querySelector(`.conv-item[onclick*="selectConversation(${convId})"]`);
    if (!item) return;
    const titleArea = item.querySelector('.conv-title');
    if (!titleArea) return;

    const input = document.createElement('input');
    input.className = 'conv-rename-input';
    input.value = currentTitle;
    input.onclick = e => e.stopPropagation();

    titleArea.replaceWith(input);
    input.focus();
    input.select();

    const doRename = async () => {
        const newTitle = input.value.trim();
        if (newTitle && newTitle !== currentTitle) {
            try {
                await api(`/admin/rag/conversations/${convId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle }),
                });
            } catch (e) { console.error('이름 변경 실패:', e); }
        }
        loadConversations();
    };

    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); doRename(); }
        if (e.key === 'Escape') loadConversations();
    });
    input.addEventListener('blur', doRename);
}

function startRenameFromHeader() {
    if (!currentConvId) return;
    const title = document.getElementById('chatHeaderTitle').textContent;
    const newTitle = prompt('대화 이름 변경', title);
    if (newTitle && newTitle.trim() && newTitle.trim() !== title) {
        api(`/admin/rag/conversations/${currentConvId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle.trim() }),
        }).then(() => loadConversations()).catch(e => console.error('이름 변경 실패:', e));
    }
}

// --- 대화 저장/해제 토글 ---
async function toggleSaveConversation() {
    if (!currentConvId) return;
    const saveBtn = document.getElementById('chatSaveBtn');
    const origText = saveBtn.innerHTML;
    saveBtn.innerHTML = '&#8987; 처리중...';
    saveBtn.disabled = true;
    try {
        const res = await api(`/admin/rag/conversations/${currentConvId}/save`, { method: 'POST' });
        if (!res.ok) { alert('저장 토글 실패: ' + (await res.json()).detail); return; }
        await loadConversations();
    } catch (e) {
        console.error('저장 토글 실패:', e);
        alert('저장 토글에 실패했습니다.');
        saveBtn.innerHTML = origText;
    } finally {
        saveBtn.disabled = false;
    }
}

// --- 케밥 메뉴 ---
function toggleKebab(event, convId) {
    event.stopPropagation();
    const menu = document.getElementById('kebab-menu-' + convId);
    const kebab = document.getElementById('kebab-' + convId);
    const isOpen = menu.classList.contains('open');
    closeAllKebabs();
    if (!isOpen) {
        menu.classList.add('open');
        kebab.classList.add('open');
    }
}

function closeAllKebabs() {
    document.querySelectorAll('.conv-kebab-menu.open').forEach(m => m.classList.remove('open'));
    document.querySelectorAll('.conv-kebab.open').forEach(k => k.classList.remove('open'));
}

document.addEventListener('click', closeAllKebabs);

async function toggleSaveFromList(convId) {
    try {
        const res = await api(`/admin/rag/conversations/${convId}/save`, { method: 'POST' });
        if (!res.ok) { console.error('저장 토글 실패:', await res.text()); }
        await loadConversations();
    } catch (e) { console.error('저장 토글 실패:', e); }
}

// --- RAG 문서 ---
async function loadRagDocuments() {
    try {
        ragDocuments = await (await api('/admin/rag/documents')).json();
        renderRagDocuments(ragDocuments);
        renderWelcomeDocs(ragDocuments);
    } catch (e) { console.error('RAG 문서 로드 실패:', e); }
}

function renderRagDocuments(docs) {
    const c = document.getElementById('refDocList');
    if (!docs.length) {
        c.innerHTML = '<div class="empty-state" style="padding:24px 12px;font-size:0.8rem"><div style="font-size:1.2rem;margin-bottom:6px;">&#128196;</div>RAG 세션용 문서가 없습니다<br><span style="font-size:0.72rem">문서 관리에서 업로드하세요</span></div>';
        return;
    }
    let html = `<div class="ref-doc-item ref-doc-all"><input type="checkbox" id="refDocAll" checked onchange="toggleAllDocs(this.checked)" /><label for="refDocAll">전체 문서</label></div>`;
    for (const d of docs) {
        html += `<div class="ref-doc-item"><input type="checkbox" class="ref-doc-check" id="refDoc${d.id}" value="${d.id}" checked /><label for="refDoc${d.id}">&#128196; ${esc(d.filename)}</label></div>`;
    }
    c.innerHTML = html;
}

function renderWelcomeDocs(docs) {
    const c = document.getElementById('welcomeDocs');
    if (!c) return;
    if (!docs.length) {
        c.innerHTML = '<div style="font-size:0.78rem;color:var(--text-muted);padding:8px 0;">문서 관리 탭에서 RAG 세션용 문서를 업로드하세요</div>';
        return;
    }
    let html = '';
    for (const d of docs) {
        html += `<div class="welcome-doc-chip selected" data-doc-id="${d.id}" onclick="toggleWelcomeDoc(this)">
            <span class="chip-check">&#10003;</span>
            <span>&#128196; ${esc(d.filename)}</span>
        </div>`;
    }
    c.innerHTML = html;
}

function toggleWelcomeDoc(chip) {
    chip.classList.toggle('selected');
    const check = chip.querySelector('.chip-check');
    check.textContent = chip.classList.contains('selected') ? '\u2713' : '';
    // 사이드바 체크박스도 동기화
    const docId = chip.dataset.docId;
    const sidebarCheck = document.getElementById('refDoc' + docId);
    if (sidebarCheck) sidebarCheck.checked = chip.classList.contains('selected');
    // 전체 체크박스 동기화
    const allCheck = document.getElementById('refDocAll');
    if (allCheck) allCheck.checked = document.querySelectorAll('.welcome-doc-chip.selected').length === ragDocuments.length;
}

function toggleAllDocs(checked) {
    document.querySelectorAll('.ref-doc-check').forEach(cb => cb.checked = checked);
    document.querySelectorAll('.welcome-doc-chip').forEach(chip => {
        if (checked) chip.classList.add('selected');
        else chip.classList.remove('selected');
        chip.querySelector('.chip-check').textContent = checked ? '\u2713' : '';
    });
}

function getSelectedDocIds() {
    // 웰컴 화면의 칩에서도 선택 상태 확인
    const welcomeChips = document.querySelectorAll('.welcome-doc-chip.selected');
    if (welcomeChips.length > 0 && !currentConvId) {
        const ids = Array.from(welcomeChips).map(c => parseInt(c.dataset.docId));
        return (ids.length === ragDocuments.length || ids.length === 0) ? null : ids;
    }
    const ids = Array.from(document.querySelectorAll('.ref-doc-check:checked')).map(cb => parseInt(cb.value));
    return (ids.length === ragDocuments.length || ids.length === 0) ? null : ids;
}

// --- 웰컴 화면 표시/복구 ---
function showWelcomeScreen() {
    document.getElementById('chatInputWrap').style.display = 'none';
    const c = document.getElementById('chatMessages');
    c.innerHTML = `
        <div class="chat-welcome" id="chatWelcome">
            <div class="chat-welcome-icon">&#9875;</div>
            <h3>문서 내 Q&A</h3>
            <p>업로드된 기술 문서를 기반으로<br>정확한 답변을 받아보세요</p>
            <div class="welcome-docs" id="welcomeDocs"></div>
            <div class="welcome-input-wrap">
                <div class="welcome-input-box">
                    <input type="text" id="welcomeInput" placeholder="문서에 대해 질문하세요..." />
                    <button class="chat-send-btn" id="welcomeSendBtn" onclick="sendRagMessage()">&#10148;</button>
                </div>
                <div class="welcome-hint">Enter로 전송 — 대화가 자동 생성됩니다</div>
            </div>
        </div>`;
    // 이벤트 리스너 재등록
    document.getElementById('welcomeInput').addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) sendRagMessage();
    });
    // 문서 칩 렌더링
    renderWelcomeDocs(ragDocuments);
}

// --- 메시지 전송 ---
async function sendRagMessage() {
    // 웰컴 입력 또는 하단 입력에서 메시지 가져오기
    const welcomeInput = document.getElementById('welcomeInput');
    const ragInput = document.getElementById('ragInput');
    const isFromWelcome = !currentConvId && welcomeInput && welcomeInput.value.trim();
    const input = isFromWelcome ? welcomeInput : ragInput;
    const msg = input.value.trim();
    if (!msg) return;

    input.value = '';

    // 대화가 없으면 자동 생성
    if (!currentConvId) {
        try {
            const cv = await (await api('/admin/rag/conversations', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: '새 대화' }),
            })).json();
            currentConvId = cv.id;
        } catch (e) {
            console.error('대화 자동 생성 실패:', e);
            alert('대화 생성에 실패했습니다.');
            return;
        }
    }

    // 웰컴 화면 → 채팅 모드로 전환
    switchToChatMode();
    setChatEnabled(false);

    // 1. 사용자 메시지 즉시 표시
    appendMsg('user', msg);

    // 2. 로딩 인디케이터 즉시 표시
    const loadingMsgId = appendLoadingMsg();

    // SSE 스트리밍으로 AI 답변 받기
    let fullResponse = '';
    let assistantMsgId = null;
    let references = [];
    let isFirstChunk = true;

    try {
        const res = await api('/admin/rag/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conversation_id: currentConvId, message: msg, document_ids: getSelectedDocIds() }),
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.substring(6);
                    try {
                        const data = JSON.parse(jsonStr);

                        if (data.chunk) {
                            fullResponse += data.chunk;

                            // 3. 첫 번째 청크가 도착하면 로딩 메시지를 실제 답변으로 교체
                            if (isFirstChunk) {
                                removeLoadingMsg(loadingMsgId);
                                assistantMsgId = appendMsg('assistant', fullResponse);
                                isFirstChunk = false;
                            } else {
                                updateMsg(assistantMsgId, fullResponse);
                            }
                        }

                        if (data.done) {
                            references = data.references || [];
                            // 참조 문서 표시
                            if (references.length > 0) {
                                addRefsToMsg(assistantMsgId, references);
                            }
                            showRefChunks(references);
                        }
                    } catch (e) {
                        console.error('SSE 파싱 오류:', e);
                    }
                }
            }
        }

        await loadConversations();
    } catch (e) {
        // 로딩 메시지 제거
        if (loadingMsgId && !assistantMsgId) {
            removeLoadingMsg(loadingMsgId);
        }

        // 에러 메시지 표시
        if (assistantMsgId) {
            updateMsg(assistantMsgId, fullResponse || '⚠️ 오류가 발생했습니다. 다시 시도해주세요.');
        } else {
            appendMsg('assistant', '⚠️ 오류가 발생했습니다. 다시 시도해주세요.');
        }
        console.error('스트리밍 오류:', e);
    } finally {
        setChatEnabled(true);
    }
}

// 웰컴 화면 → 채팅 모드 전환
function switchToChatMode() {
    const welcome = document.getElementById('chatWelcome');
    if (welcome) welcome.remove();
    document.getElementById('chatInputWrap').style.display = '';
}

let _mc = 0;
function appendMsg(role, content, refs) {
    const c = document.getElementById('chatMessages');
    const welcome = c.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const id = 'msg-' + (++_mc);
    // AI 아바타: 로고 있으면 이미지, 없으면 "AI" 텍스트
    const avatar = role === 'user'
        ? 'U'
        : (siteLogoUrl ? `<img src="${siteLogoUrl}" alt="AI">` : 'AI');
    const rendered = role === 'assistant' ? renderMd(content) : esc(content);
    const now = new Date();
    const timeStr = now.toLocaleTimeString('ko-KR', {hour:'2-digit',minute:'2-digit'});
    const refsHtml = (role === 'assistant' && refs && refs.length)
        ? `<span class="msg-refs-link" onclick='showRefChunks(${JSON.stringify(refs).replace(/'/g,"&#39;")})'>&#128196; 참조 ${refs.length}건 보기</span>` : '';

    const div = document.createElement('div');
    div.className = `msg-row ${role}`;
    div.id = id;
    div.innerHTML = `<div class="msg-avatar">${avatar}</div><div class="msg-content"><div class="msg-bubble">${rendered}</div><span class="msg-time">${timeStr}</span>${refsHtml}</div>`;
    c.appendChild(div);
    c.scrollTop = c.scrollHeight;
    return id;
}

function updateMsg(msgId, content) {
    const el = document.getElementById(msgId);
    if (!el) return;
    const bubble = el.querySelector('.msg-bubble');
    if (bubble) {
        bubble.innerHTML = renderMd(content);
    }
    const c = document.getElementById('chatMessages');
    c.scrollTop = c.scrollHeight;
}

function addRefsToMsg(msgId, refs) {
    const el = document.getElementById(msgId);
    if (!el || !refs || !refs.length) return;
    const msgContent = el.querySelector('.msg-content');
    if (!msgContent) return;

    // 이미 참조 링크가 있으면 제거
    const existingLink = msgContent.querySelector('.msg-refs-link');
    if (existingLink) existingLink.remove();

    // 새 참조 링크 추가
    const refsLink = document.createElement('span');
    refsLink.className = 'msg-refs-link';
    refsLink.textContent = `📄 참조 ${refs.length}건 보기`;
    refsLink.onclick = () => showRefChunks(refs);
    msgContent.appendChild(refsLink);
}

/**
 * 로딩 메시지 표시 (답변 생성 중...)
 */
function appendLoadingMsg() {
    const c = document.getElementById('chatMessages');
    const welcome = c.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const id = 'loading-' + Date.now();
    const avatar = siteLogoUrl ? `<img src="${siteLogoUrl}" alt="AI">` : 'AI';

    const div = document.createElement('div');
    div.className = 'msg-row assistant';
    div.id = id;
    div.innerHTML = `
        <div class="msg-avatar">${avatar}</div>
        <div class="msg-content">
            <div class="msg-bubble loading-bubble">
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
                <div class="loading-text">문서를 분석하여 답변을 생성하고 있습니다...</div>
            </div>
        </div>
    `;
    c.appendChild(div);
    c.scrollTop = c.scrollHeight;
    return id;
}

/**
 * 로딩 메시지 제거
 */
function removeLoadingMsg(msgId) {
    const el = document.getElementById(msgId);
    if (el) {
        el.remove();
    }
}

function showTyping() {
    const c = document.getElementById('chatMessages');
    const id = 'typing-' + (++_mc);
    const aiAvatar = siteLogoUrl ? `<img src="${siteLogoUrl}" alt="AI">` : 'AI';
    const div = document.createElement('div');
    div.className = 'msg-row assistant';
    div.id = id;
    div.innerHTML = `<div class="msg-avatar">${aiAvatar}</div><div class="msg-content"><div class="msg-bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div></div>`;
    c.appendChild(div);
    c.scrollTop = c.scrollHeight;
    return id;
}

function removeEl(id) { const el = document.getElementById(id); if (el) el.remove(); }

let _lastRefs = [];

function showRefChunks(refs) {
    _lastRefs = refs || [];
    const p = document.getElementById('refChunksPanel');
    if (!refs || !refs.length) {
        p.innerHTML = `<div class="ref-chunks-title">&#128269; 참조된 문서 내용</div><div style="font-size:0.76rem;color:var(--text-muted);text-align:center;padding:12px 0;">참조된 내용이 없습니다</div>`;
        return;
    }
    let html = `<div class="ref-chunks-title">&#128269; 참조된 문서 내용 (${refs.length}건)</div>`;
    refs.forEach((r, i) => {
        const pct = Math.round(r.similarity * 100);
        html += `<div class="ref-chunk-card" onclick="openRefPopup(${i})">
            <span class="chunk-file">&#128196; ${esc(r.filename)}</span>
            <span class="chunk-score">${pct}% <span class="score-bar"><span class="score-bar-fill" style="width:${pct}%"></span></span></span>
        </div>`;
    });
    p.innerHTML = html;
}

function openRefPopup(idx) {
    const r = _lastRefs[idx];
    if (!r) return;
    const pct = Math.round(r.similarity * 100);
    document.getElementById('refPopupFilename').textContent = r.filename;
    document.getElementById('refPopupScore').innerHTML = `유사도 ${pct}% <span class="score-bar"><span class="score-bar-fill" style="width:${pct}%"></span></span>`;
    document.getElementById('refPopupBody').textContent = r.chunk_text;
    document.getElementById('refPopup').classList.add('active');
}

function closeRefPopup() {
    document.getElementById('refPopup').classList.remove('active');
}

function setChatEnabled(enabled) {
    const ragInput = document.getElementById('ragInput');
    const ragSendBtn = document.getElementById('ragSendBtn');
    ragInput.disabled = !enabled;
    ragSendBtn.disabled = !enabled;
    if (enabled) ragInput.focus();
}

// ===== 실시간 채팅 업데이트 (Polling) =====

var pollingInterval = null;
var lastMessageCount = 0;
var isPolling = false;

/**
 * 실시간 polling 시작
 */
function startRealtimePolling() {
    // 이미 polling 중이면 중복 시작 방지
    if (pollingInterval) {
        console.log('🔄 [POLLING] 이미 polling 중입니다');
        return;
    }

    console.log('🔄 [POLLING] 실시간 polling 시작');

    // 3초마다 체크
    pollingInterval = setInterval(async () => {
        // 현재 열린 대화가 있고, 다른 작업 중이 아닐 때만 체크
        if (currentConvId && !isPolling && !isLoadingConversation) {
            await checkForNewMessages();
        }
    }, 3000);
}

/**
 * 실시간 polling 중지
 */
function stopRealtimePolling() {
    if (pollingInterval) {
        console.log('🛑 [POLLING] 실시간 polling 중지');
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

/**
 * 새 메시지 확인
 */
async function checkForNewMessages() {
    if (!currentConvId) return;

    isPolling = true;
    try {
        const res = await api(`/admin/rag/conversations/${currentConvId}`);
        if (!res.ok) {
            isPolling = false;
            return;
        }

        const data = await res.json();
        const newMessageCount = data.messages?.length || 0;

        // 새 메시지가 있으면
        if (newMessageCount > lastMessageCount) {
            console.log('✨ [POLLING] 새 메시지 감지:', newMessageCount - lastMessageCount, '개');

            // 현재 스크롤 위치 저장
            const chatContainer = document.getElementById('chatMessages');
            const wasAtBottom = chatContainer ?
                (chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 100) : false;

            // 메시지 렌더링
            renderChatMessages(data.messages);
            lastMessageCount = newMessageCount;

            // 하단에 있었다면 자동 스크롤
            if (wasAtBottom && chatContainer) {
                setTimeout(() => {
                    chatContainer.scrollTo({
                        top: chatContainer.scrollHeight,
                        behavior: 'smooth'
                    });
                }, 100);
            }

            // 새 메시지 알림 (선택적)
            showNewMessageIndicator();
        }
    } catch (e) {
        console.error('❌ [POLLING] 메시지 체크 실패:', e);
    } finally {
        isPolling = false;
    }
}

/**
 * 새 메시지 알림 표시
 */
function showNewMessageIndicator() {
    // 간단한 시각적 피드백
    const chatContainer = document.getElementById('chatMessages');
    if (!chatContainer) return;

    // 임시 배지 표시
    const badge = document.createElement('div');
    badge.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px 20px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        z-index: 9999;
        animation: slideInRight 0.3s ease;
    `;
    badge.textContent = '✨ 새 메시지가 도착했습니다';
    document.body.appendChild(badge);

    // 2초 후 제거
    setTimeout(() => {
        badge.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => badge.remove(), 300);
    }, 2000);
}

/**
 * 대화 로드 시 메시지 카운트 초기화
 */
var _originalLoadConversation = loadConversation;
loadConversation = async function(convId) {
    // 기존 함수 호출
    await _originalLoadConversation(convId);

    // 메시지 카운트 업데이트
    const res = await api(`/admin/rag/conversations/${convId}`);
    const data = await res.json();
    lastMessageCount = data.messages?.length || 0;

    console.log('📊 [POLLING] 초기 메시지 개수:', lastMessageCount);
};

/**
 * 메시지 전송 후 polling 재개
 */
var _originalSendRagMessage = sendRagMessage;
sendRagMessage = async function() {
    await _originalSendRagMessage();

    // 메시지 전송 후 즉시 체크
    setTimeout(() => {
        if (currentConvId) {
            checkForNewMessages();
        }
    }, 1000);
};

// 탭이 활성화되면 polling 시작
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('👁️ [POLLING] 탭 비활성화 - polling 계속 실행');
        // 백그라운드에서도 계속 polling (선택적)
    } else {
        console.log('👁️ [POLLING] 탭 활성화 - polling 확인');
        if (!pollingInterval && currentConvId) {
            startRealtimePolling();
        }
    }
});

// 페이지 로드 시 자동으로 polling 시작
if (typeof window !== 'undefined') {
    // DOM이 로드된 후 실행
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            console.log('🚀 [POLLING] 페이지 로드 완료, polling 준비');
            // Q&A 탭이 활성화되면 polling 시작
            const ragTab = document.getElementById('tabRag');
            if (ragTab) {
                const observer = new MutationObserver((mutations) => {
                    mutations.forEach((mutation) => {
                        if (mutation.target.style.display !== 'none' && currentConvId) {
                            startRealtimePolling();
                        } else if (mutation.target.style.display === 'none') {
                            stopRealtimePolling();
                        }
                    });
                });
                observer.observe(ragTab, { attributes: true, attributeFilter: ['style'] });
            }
        });
    } else {
        console.log('🚀 [POLLING] 페이지 이미 로드됨, polling 준비');
    }
}

// CSS 애니메이션 추가 (동적으로)
if (typeof document !== 'undefined') {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOutRight {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}

