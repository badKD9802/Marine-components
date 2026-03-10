
/**
 * docs.js
 * 문서 업로드 및 관리
 */

/**
 * 문서 목록 로드
 */
async function loadDocuments() {
    try { const res = await api('/admin/documents'); renderDocuments(await res.json()); }
    catch (e) { console.error('문서 목록 로드 실패:', e); }
}

/**
 * 문서 목록 렌더링
 */
function renderDocuments(docs) {
    const c = document.getElementById('docsTable');
    if (!docs.length) { c.innerHTML = '<div class="empty-state"><div class="icon">&#128196;</div><div>아직 업로드된 문서가 없습니다</div></div>'; return; }

    const statusBadge = s => {
        const m = { done: ['badge-done','완료'], processing: ['badge-processing','처리중'], error: ['badge-error','오류'], pending: ['badge-pending','대기'] };
        const [cls, label] = m[s] || ['badge-pending', s];
        return `<span class="badge ${cls}">${label}</span>`;
    };
    const purposeBadge = p => p === 'rag_session'
        ? '<span class="badge purpose-rag" style="margin-left:4px">RAG / 메일</span>'
        : '<span class="badge purpose-consultant" style="margin-left:4px">AI 상담</span>';

    let html = '<div class="docs-table-wrapper">';
    for (const d of docs) {
        const date = d.created_at ? new Date(d.created_at).toLocaleString('ko-KR') : '-';
        const category = d.category || '미분류';
        html += `
        <div class="doc-row" data-doc-id="${d.id}">
            <div class="doc-row-content" onclick="viewDocument(${d.id})">
                <div class="doc-main">
                    <div class="doc-icon">${d.file_type==='pdf'?'📄':'🖼️'}</div>
                    <div class="doc-info">
                        <div class="doc-name">${esc(d.filename)}</div>
                        <div class="doc-meta">
                            <span>${d.file_type.toUpperCase()}</span>
                            <span>•</span>
                            <span>${purposeBadge(d.purpose)}</span>
                            <span>•</span>
                            <span class="doc-category-display" onclick="event.stopPropagation(); editCategory(${d.id}, '${esc(category)}')">${esc(category)}</span>
                        </div>
                    </div>
                </div>
                <div class="doc-status">
                    ${statusBadge(d.status)}
                    ${d.error_msg?'<br><small style="color:var(--error)">'+esc(d.error_msg)+'</small>':''}
                </div>
                <div class="doc-date">${date}</div>
            </div>
            <button class="doc-delete-btn" onclick="event.stopPropagation(); deleteDocument(${d.id})" title="삭제">×</button>
        </div>`;
    }
    c.innerHTML = html + '</div>';
}

/**
 * 파일 업로드 처리
 */
async function handleFiles(fileList, purpose) {
    for (const f of fileList) await uploadFile(f, purpose);
}

/**
 * 개별 파일 업로드
 */
async function uploadFile(file, purpose) {
    const prog = document.getElementById('uploadProgress');
    const fname = document.getElementById('uploadFileName');
    prog.style.display = 'block';
    fname.textContent = `처리 중: ${file.name}`;

    // 선택된 카테고리 가져오기
    const categorySelect = document.getElementById('uploadCategorySelect');
    const category = categorySelect ? categorySelect.value : '미분류';

    const fd = new FormData();
    fd.append('file', file);
    fd.append('purpose', purpose);
    fd.append('category', category);

    try {
        const res = await api('/admin/upload', { method: 'POST', body: fd });
        const d = await res.json();
        if (d.status === 'error') { fname.textContent = `오류: ${file.name} — ${d.error_msg}`; setTimeout(() => prog.style.display='none', 4000); }
        else { fname.textContent = `완료: ${file.name} (${d.chunks_count}개 청크)`; setTimeout(() => prog.style.display='none', 2000); }
    } catch { fname.textContent = `업로드 실패: ${file.name}`; setTimeout(() => prog.style.display='none', 4000); }
    loadDocuments();
}

/**
 * 문서 상세 조회
 */
async function viewDocument(docId) {
    try {
        const doc = await (await api(`/admin/documents/${docId}`)).json();
        document.getElementById('modalTitle').textContent = doc.filename;
        let html = `<p style="margin-bottom:12px;color:var(--text-light);font-size:0.85rem">상태: ${doc.status} | 청크: ${doc.chunks.length}개</p>`;
        if (doc.chunks.length) {
            for (const c of doc.chunks) {
                html += `<div class="chunk-label">청크 #${c.chunk_index+1} <button class="chunk-edit-btn" onclick="startChunkEdit(${docId},${c.id},this)">수정</button></div>`;
                html += `<div class="chunk" id="chunk-${c.id}">${esc(c.chunk_text)}</div>`;
            }
        } else html += '<p style="color:var(--text-muted)">청크가 없습니다</p>';
        document.getElementById('modalContent').innerHTML = html;
        document.getElementById('docModal').classList.add('active');
    } catch (e) { console.error('문서 상세 조회 실패:', e); }
}

/**
 * 청크 수정 시작
 */
function startChunkEdit(docId, chunkId, btn) {
    const chunkDiv = document.getElementById('chunk-' + chunkId);
    if (!chunkDiv) return;
    const originalText = chunkDiv.textContent;
    chunkDiv.innerHTML = `<textarea class="chunk-textarea">${esc(originalText)}</textarea>
        <div class="chunk-save-actions">
            <button class="cancel-btn" onclick="cancelChunkEdit(${docId})">취소</button>
            <button class="save-btn" onclick="saveChunkEdit(${docId},${chunkId},this)">저장</button>
        </div>`;
    btn.style.display = 'none';
}

/**
 * 청크 수정 취소
 */
function cancelChunkEdit(docId) {
    viewDocument(docId);
}

/**
 * 청크 수정 저장
 */
async function saveChunkEdit(docId, chunkId, btn) {
    const chunkDiv = document.getElementById('chunk-' + chunkId);
    const textarea = chunkDiv.querySelector('.chunk-textarea');
    const newText = textarea.value.trim();
    if (!newText) { alert('텍스트를 입력하세요'); return; }
    btn.disabled = true;
    btn.textContent = '저장 중...';
    try {
        const res = await api(`/admin/documents/${docId}/chunks/${chunkId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chunk_text: newText }),
        });
        if (!res.ok) { const d = await res.json(); alert('수정 실패: ' + d.detail); btn.disabled = false; btn.textContent = '저장'; return; }
        viewDocument(docId);
    } catch (e) { console.error('청크 수정 실패:', e); alert('수정 실패'); btn.disabled = false; btn.textContent = '저장'; }
}

/**
 * 모달 닫기
 */
function closeModal() { document.getElementById('docModal').classList.remove('active'); }

/**
 * 문서 삭제
 */
async function deleteDocument(docId) {
    if (!confirm('이 문서를 삭제하시겠습니까?')) return;
    try { await api(`/admin/documents/${docId}`, { method: 'DELETE' }); loadDocuments(); }
    catch (e) { console.error('삭제 실패:', e); }
}

/**
 * RAG용 문서 목록 로드
 */
async function loadRagDocuments() {
    try {
        const docs = await (await api('/admin/documents?purpose=rag_session')).json();
        ragDocuments = docs;
        renderRagDocuments(docs);
        renderWelcomeDocs(docs);
    } catch (e) { console.error('RAG 문서 로드 실패:', e); }
}

/**
 * RAG 문서 목록 렌더링
 */
function renderRagDocuments(docs) {
    const c = document.getElementById('ragDocs');
    if (!docs.length) { c.innerHTML = '<div class="empty-state" style="padding:20px 12px;font-size:0.78rem">참조할 문서를 업로드하세요</div>'; return; }
    let html = '<label style="font-weight:600;margin-bottom:4px;display:block;font-size:0.75rem"><input type="checkbox" onclick="toggleAllDocs(this.checked)" checked> 전체 선택</label>';
    for (const d of docs) html += `<label class="doc-chip" data-doc-id="${d.id}"><input type="checkbox" value="${d.id}" checked> ${d.filename}</label>`;
    c.innerHTML = html;
}

/**
 * Welcome 화면 문서 렌더링
 */
function renderWelcomeDocs(docs) {
    const c = document.getElementById('welcomeDocs');
    if (!docs.length) { c.innerHTML = '<div class="welcome-no-docs">아직 업로드된 문서가 없습니다</div>'; return; }
    let html = '';
    for (const d of docs) html += `<div class="welcome-doc-chip" data-doc-id="${d.id}" onclick="toggleWelcomeDoc(this)">${d.filename}</div>`;
    c.innerHTML = html;
}

/**
 * Welcome 문서 토글
 */
function toggleWelcomeDoc(chip) {
    chip.classList.toggle('selected');
}

/**
 * 전체 문서 선택/해제
 */
function toggleAllDocs(checked) {
    document.querySelectorAll('#ragDocs input[type="checkbox"]').forEach(cb => cb.checked = checked);
}

/**
 * 선택된 문서 ID 배열 반환
 */
function getSelectedDocIds() {
    if (document.getElementById('chatMessages').innerHTML.includes('chat-welcome')) {
        return Array.from(document.querySelectorAll('#welcomeDocs .welcome-doc-chip.selected')).map(el => parseInt(el.dataset.docId));
    }
    return Array.from(document.querySelectorAll('#ragDocs input[type="checkbox"]:checked')).map(cb => parseInt(cb.value));
}

/**
 * 메일용 문서 목록 로드
 */
async function loadMailDocuments() {
    try { renderMailDocuments(await (await api('/admin/documents?purpose=rag_session')).json()); }
    catch (e) { console.error('메일 문서 로드 실패:', e); }
}

/**
 * 메일 문서 목록 렌더링
 */
function renderMailDocuments(docs) {
    const c = document.getElementById('mailDocs');
    if (!docs.length) { c.innerHTML = '<div class="empty-state" style="padding:20px 12px;font-size:0.78rem">참조할 문서를 업로드하세요</div>'; return; }
    let html = '<label style="font-weight:600;margin-bottom:4px;display:block;font-size:0.75rem"><input type="checkbox" onclick="toggleAllMailDocs(this.checked)" checked> 전체 선택</label>';
    for (const d of docs) html += `<label class="doc-chip"><input type="checkbox" value="${d.id}" checked> ${d.filename}</label>`;
    c.innerHTML = html;
}

/**
 * 전체 메일 문서 선택/해제
 */
function toggleAllMailDocs(checked) {
    document.querySelectorAll('#mailDocs input[type="checkbox"]').forEach(cb => cb.checked = checked);
}

/**
 * 선택된 메일 문서 ID 배열 반환
 */
function getMailSelectedDocIds() {
    return Array.from(document.querySelectorAll('#mailDocs input[type="checkbox"]:checked')).map(cb => parseInt(cb.value));
}

/**
 * 카테고리 프리셋 목록
 */
const CATEGORY_PRESETS = [
    '엔진',
    '펌프',
    '프로펠러',
    '배터리',
    '항해장비',
    '안전장비',
    '전기/전자',
    '배관/호스',
    '매뉴얼',
    '기타'
];

/**
 * 카테고리 편집
 */
function editCategory(docId, currentCategory) {
    // 모달 생성
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-container" style="max-width: 400px;">
            <div class="modal-header">
                <h3>카테고리 선택</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
            </div>
            <div class="modal-body">
                <label style="display:block;margin-bottom:8px;font-weight:600;">카테고리 선택</label>
                <select id="categorySelect" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;margin-bottom:12px;font-size:0.9rem;">
                    <option value="">-- 선택하세요 --</option>
                    ${CATEGORY_PRESETS.map(cat => `<option value="${cat}" ${cat === currentCategory ? 'selected' : ''}>${cat}</option>`).join('')}
                    <option value="__custom__">직접 입력...</option>
                </select>
                <div id="customCategoryInput" style="display:none;">
                    <label style="display:block;margin-bottom:8px;font-weight:600;">직접 입력</label>
                    <input type="text" id="customCategory" placeholder="카테고리 입력" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;font-size:0.9rem;">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">취소</button>
                <button class="btn btn-primary" onclick="saveCategoryFromModal(${docId})">저장</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // 선택 변경 이벤트
    const select = document.getElementById('categorySelect');
    const customInput = document.getElementById('customCategoryInput');
    select.addEventListener('change', (e) => {
        if (e.target.value === '__custom__') {
            customInput.style.display = 'block';
        } else {
            customInput.style.display = 'none';
        }
    });

    // 현재 카테고리가 프리셋에 없으면 직접 입력으로 설정
    if (currentCategory && !CATEGORY_PRESETS.includes(currentCategory)) {
        select.value = '__custom__';
        customInput.style.display = 'block';
        document.getElementById('customCategory').value = currentCategory;
    }
}

/**
 * 모달에서 카테고리 저장
 */
function saveCategoryFromModal(docId) {
    const select = document.getElementById('categorySelect');
    let category = select.value;

    if (category === '__custom__') {
        category = document.getElementById('customCategory').value.trim();
    }

    if (!category || category === '') {
        alert('카테고리를 선택하거나 입력하세요.');
        return;
    }

    updateDocumentCategory(docId, category);
    document.querySelector('.modal-overlay').remove();
}

/**
 * 문서 카테고리 업데이트 (백엔드 API 호출)
 */
async function updateDocumentCategory(docId, category) {
    try {
        const res = await api(`/admin/documents/${docId}/category`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: category })
        });

        if (!res.ok) {
            const err = await res.json();
            alert(err.detail || '카테고리 업데이트 실패');
            return;
        }

        // 성공 시 목록 새로고침
        loadDocuments();

    } catch (e) {
        console.error('카테고리 업데이트 실패:', e);
        alert('카테고리 업데이트 중 오류가 발생했습니다.');
    }
}
