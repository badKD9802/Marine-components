
/**
 * products.js
 * 상품 및 카테고리 관리
 */

var allProducts = [];
var allCategories = [];

/**
 * 카테고리 로드
 */
async function loadCategories() {
    try {
        const res = await api('/admin/categories');
        allCategories = await res.json();

        // 필터 드롭다운 업데이트
        const filter = document.getElementById('productCategoryFilter');
        if (filter) {
            filter.innerHTML = '<option value="">전체 카테고리</option>';
            allCategories.forEach(cat => {
                filter.innerHTML += `<option value="${cat.code}">${cat.name_ko}</option>`;
            });
        }

        // 상품 모달 카테고리 드롭다운 업데이트
        const modalCat = document.getElementById('productCategory');
        if (modalCat) {
            modalCat.innerHTML = '';
            allCategories.forEach(cat => {
                modalCat.innerHTML += `<option value="${cat.code}">${cat.name_ko}</option>`;
            });
        }

        // 카테고리 목록 렌더링
        renderCategoryList();
    } catch (e) {
        console.error('카테고리 로드 실패:', e);
    }
}

/**
 * 카테고리 목록 렌더링
 */
function renderCategoryList() {
    const container = document.getElementById('categoryList');
    if (!container) return;
    
    if (!allCategories.length) {
        container.innerHTML = '<div style="color:var(--text-muted);font-size:0.85rem;">등록된 카테고리가 없습니다</div>';
        return;
    }

    container.innerHTML = allCategories.map(cat => `
        <div style="display:inline-flex;align-items:center;gap:6px;background:white;padding:8px 12px;border-radius:6px;border:1px solid var(--border);">
            <span style="font-size:0.85rem;font-weight:500;">${cat.name_ko}</span>
            <span style="font-size:0.75rem;color:var(--text-muted);">(${cat.code})</span>
            <button onclick="deleteCategory(${cat.id})" style="background:none;border:none;color:var(--error);cursor:pointer;font-size:0.9rem;padding:0 4px;" title="삭제">×</button>
        </div>
    `).join('');
}

/**
 * 카테고리 관리 패널 토글
 */
function toggleCategoryManage() {
    const panel = document.getElementById('categoryManagePanel');
    if (!panel) return;
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    if (panel.style.display === 'block') {
        loadCategories();
    }
}

/**
 * 카테고리 추가
 */
async function addCategory() {
    console.log('📁 [DEBUG] addCategory 시작');
    const code = document.getElementById('newCategoryCode').value.trim();
    const nameKo = document.getElementById('newCategoryNameKo').value.trim();
    const nameEn = document.getElementById('newCategoryNameEn').value.trim();

    console.log('📁 [DEBUG] 입력값 - code:', code, 'nameKo:', nameKo, 'nameEn:', nameEn);

    if (!code || !nameKo) {
        alert('코드와 한글명은 필수입니다.');
        return;
    }

    try {
        console.log('📁 [DEBUG] API 요청:', '/admin/categories');
        const res = await api('/admin/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, name_ko: nameKo, name_en: nameEn })
        });
        console.log('📁 [DEBUG] 응답 status:', res.status);

        if (!res.ok) {
            const errorText = await res.text();
            console.error('❌ [ERROR] 카테고리 추가 실패:', errorText);
            throw new Error('추가 실패: ' + res.status + ' - ' + errorText);
        }

        alert('카테고리가 추가되었습니다.');
        document.getElementById('newCategoryCode').value = '';
        document.getElementById('newCategoryNameKo').value = '';
        document.getElementById('newCategoryNameEn').value = '';
        loadCategories();
        console.log('✅ [DEBUG] addCategory 완료');
    } catch (e) {
        console.error('❌ [ERROR] 카테고리 추가 실패:', e);
        console.error('❌ [ERROR] 에러 스택:', e.stack);
        alert('카테고리 추가 실패: ' + e.message);
    }
}

/**
 * 카테고리 삭제
 */
async function deleteCategory(id) {
    if (!confirm('이 카테고리를 삭제하시겠습니까?')) return;

    try {
        await api(`/admin/categories/${id}`, { method: 'DELETE' });
        alert('카테고리가 삭제되었습니다.');
        loadCategories();
    } catch (e) {
        console.error('삭제 실패:', e);
        alert('삭제 실패: ' + e.message);
    }
}

/**
 * 이미지 드롭존 설정
 */
function setupImageDropZone() {
    const dropZone = document.getElementById('imageDropZone');
    if (!dropZone) return;

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--primary)';
        dropZone.style.background = 'var(--primary-light)';
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'var(--bg-gray)';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'var(--bg-gray)';

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleImageFile(files[0]);
        }
    });
}

/**
 * 이미지 업로드 처리 (input)
 */
function handleImageUpload(event) {
    const file = event.target.files[0];
    if (file) {
        handleImageFile(file);
    }
}

/**
 * 이미지 파일 처리
 */
function handleImageFile(file) {
    if (!file.type.startsWith('image/')) {
        alert('이미지 파일만 업로드 가능합니다.');
        return;
    }

    if (file.size > 5 * 1024 * 1024) {
        alert('파일 크기는 5MB 이하여야 합니다.');
        return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
        const imageData = e.target.result;

        // 미리보기 표시
        document.getElementById('previewImg').src = imageData;
        document.getElementById('imagePreview').style.display = 'block';
        document.getElementById('dropZonePlaceholder').style.display = 'none';

        // 이미지 데이터 저장
        document.getElementById('productImage').value = imageData;

        // 서버 업로드 (선택사항)
        try {
            const res = await api('/admin/upload-image', {
                method: 'POST',
                body: JSON.stringify({ image: imageData })
            });
            const data = await res.json();
            console.log('이미지 업로드 완료:', data.url);
        } catch (e) {
            console.error('이미지 업로드 실패:', e);
        }
    };
    reader.readAsDataURL(file);
}

/**
 * 상품 목록 로드
 */
async function loadProducts() {
    try {
        // 카테고리 먼저 로드
        await loadCategories();

        var category = document.getElementById('productCategoryFilter')?.value || '';
        var search = document.getElementById('productSearchInput')?.value.trim() || '';

        var url = '/admin/products';
        var params = new URLSearchParams();
        if (category) params.append('category', category);
        if (search) params.append('search', search);
        if (params.toString()) url += '?' + params.toString();

        console.log('상품 로드 중:', url);
        var res = await api(url);
        allProducts = await res.json();
        console.log('상품 로드 완료:', allProducts.length, '개');
        renderProducts();
    } catch (e) {
        console.error('상품 로드 실패:', e);
        var container = document.getElementById('productList');
        if (container) {
            container.innerHTML = '<div class="empty-state" style="grid-column:1/-1;padding:60px 20px;color:var(--error);">상품 로드 실패: ' + e.message + '</div>';
        }
    }
}

/**
 * 상품 목록 렌더링
 */
function renderProducts() {
    const container = document.getElementById('productList');
    if (!container) return;

    if (!allProducts.length) {
        container.innerHTML = '<div class="empty-state" style="grid-column:1/-1;padding:60px 20px;">등록된 상품이 없습니다</div>';
        return;
    }

    container.innerHTML = allProducts.map(p => `
        <div style="background:white;border:1px solid var(--border);border-radius:8px;overflow:hidden;transition:box-shadow 0.2s;position:relative;" onmouseenter="this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)'" onmouseleave="this.style.boxShadow='none'">
            <div style="aspect-ratio:1;background:var(--bg-gray);overflow:hidden;cursor:pointer;" onclick="editProduct(${p.id})">
                <img src="${p.image}" alt="${p.name?.ko || p.part_no}" style="width:100%;height:100%;object-fit:cover;" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22%3E%3Crect fill=%22%23f0f0f0%22 width=%22100%22 height=%22100%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%23999%22%3ENo Image%3C/text%3E%3C/svg%3E'">
            </div>
            <div style="padding:12px;">
                <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:4px;">${p.part_no}</div>
                <div style="font-size:0.9rem;font-weight:600;color:var(--text-dark);margin-bottom:6px;line-height:1.3;">${p.name?.ko || 'N/A'}</div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <span style="font-size:0.75rem;color:var(--text-muted);">${p.brand}</span>
                    <span style="font-size:0.85rem;font-weight:600;color:var(--primary);">${p.price}</span>
                </div>
                <div style="display:flex;gap:6px;">
                    <button onclick="event.stopPropagation(); editProduct(${p.id})" style="flex:1;padding:6px;background:var(--primary);color:white;border:none;border-radius:4px;cursor:pointer;font-size:0.8rem;font-weight:500;transition:background 0.2s;" onmouseover="this.style.background='var(--primary-dark)'" onmouseout="this.style.background='var(--primary)'">수정</button>
                    <button onclick="event.stopPropagation(); deleteProduct(${p.id})" style="flex:1;padding:6px;background:var(--error);color:white;border:none;border-radius:4px;cursor:pointer;font-size:0.8rem;font-weight:500;transition:background 0.2s;" onmouseover="this.style.background='#c0392b'" onmouseout="this.style.background='var(--error)'">삭제</button>
                </div>
            </div>
        </div>
    `).join('');
}

/**
 * 상품 추가 폼 표시
 */
async function showProductForm() {
    // 카테고리 로드
    await loadCategories();

    document.getElementById('productModalTitle').textContent = '상품 추가';
    document.getElementById('productId').value = '';
    document.getElementById('productImage').value = '';
    document.getElementById('productPartNo').value = '';
    document.getElementById('productPrice').value = '';
    document.getElementById('productBrand').value = '';
    document.getElementById('productCategory').value = allCategories[0]?.code || '';
    document.getElementById('productNameKo').value = '';
    document.getElementById('productNameEn').value = '';
    document.getElementById('productNameCn').value = '';
    document.getElementById('productDescKo').value = '';
    document.getElementById('productDescEn').value = '';
    document.getElementById('productDescCn').value = '';
    document.getElementById('productDetailInfoKo').value = '';
    document.getElementById('productDetailInfoEn').value = '';
    document.getElementById('productDetailInfoCn').value = '';
    document.getElementById('productDeleteBtn').style.display = 'none';

    // 언어별 스펙/호환정보 초기화
    populateSpecsByLang('ko', {});
    populateSpecsByLang('en', {});
    populateSpecsByLang('cn', {});
    populateCompatibilityByLang('ko', []);
    populateCompatibilityByLang('en', []);
    populateCompatibilityByLang('cn', []);

    // 한국어 탭으로 초기화
    switchProductLang('ko');

    // 이미지 미리보기 초기화
    document.getElementById('imagePreview').style.display = 'none';
    document.getElementById('dropZonePlaceholder').style.display = 'block';

    document.getElementById('productModal').style.display = 'flex';

    // 드롭존 초기화
    setupImageDropZone();
}

/**
 * 상품 수정
 */
async function editProduct(id) {
    try {
        // 카테고리 로드
        await loadCategories();

        console.log('📝 [EDIT] 상품 로드 중, ID:', id);
        const res = await api(`/admin/products/${id}`);
        const product = await res.json();
        console.log('📝 [EDIT] 받은 데이터:', product);
        console.log('📝 [EDIT] name:', product.name);
        console.log('📝 [EDIT] description:', product.description);
        console.log('📝 [EDIT] detail_info:', product.detail_info);

        document.getElementById('productModalTitle').textContent = '상품 수정';
        document.getElementById('productId').value = product.id;
        document.getElementById('productImage').value = product.image || '';
        document.getElementById('productPartNo').value = product.part_no || '';
        document.getElementById('productPrice').value = product.price || '';
        document.getElementById('productBrand').value = product.brand || '';
        document.getElementById('productCategory').value = product.category || '';

        // 다국어 필드 로드 (안전하게 파싱)
        // JSONB 필드가 문자열로 올 수 있으므로 파싱
        var name = product.name || {};
        if (typeof name === 'string') {
            try { name = JSON.parse(name); } catch(e) { name = {}; }
        }

        var description = product.description || {};
        if (typeof description === 'string') {
            try { description = JSON.parse(description); } catch(e) { description = {}; }
        }

        var detailInfo = product.detail_info || {};
        if (typeof detailInfo === 'string') {
            try { detailInfo = JSON.parse(detailInfo); } catch(e) { detailInfo = {}; }
        }

        console.log('📝 [EDIT] 파싱된 name:', name);
        console.log('📝 [EDIT] 파싱된 description:', description);
        console.log('📝 [EDIT] 파싱된 detailInfo:', detailInfo);

        document.getElementById('productNameKo').value = name.ko || '';
        document.getElementById('productNameEn').value = name.en || '';
        document.getElementById('productNameCn').value = name.cn || '';
        document.getElementById('productDescKo').value = description.ko || '';
        document.getElementById('productDescEn').value = description.en || '';
        document.getElementById('productDescCn').value = description.cn || '';
        document.getElementById('productDetailInfoKo').value = detailInfo.ko || '';
        document.getElementById('productDetailInfoEn').value = detailInfo.en || '';
        document.getElementById('productDetailInfoCn').value = detailInfo.cn || '';
        document.getElementById('productDeleteBtn').style.display = 'block';

        // 언어별 스펙/호환정보 로드 (안전하게 파싱)
        var specs = product.specs || {};
        if (typeof specs === 'string') {
            try { specs = JSON.parse(specs); } catch(e) { specs = {}; }
        }

        var compatibility = product.compatibility || {};
        if (typeof compatibility === 'string') {
            try { compatibility = JSON.parse(compatibility); } catch(e) { compatibility = {}; }
        }

        populateSpecsByLang('ko', specs.ko || {});
        populateSpecsByLang('en', specs.en || {});
        populateSpecsByLang('cn', specs.cn || {});
        populateCompatibilityByLang('ko', compatibility.ko || []);
        populateCompatibilityByLang('en', compatibility.en || []);
        populateCompatibilityByLang('cn', compatibility.cn || []);

        // 한국어 탭으로 초기화
        switchProductLang('ko');

        // 이미지 미리보기 표시
        if (product.image) {
            document.getElementById('previewImg').src = product.image;
            document.getElementById('imagePreview').style.display = 'block';
            document.getElementById('dropZonePlaceholder').style.display = 'none';
        } else {
            document.getElementById('imagePreview').style.display = 'none';
            document.getElementById('dropZonePlaceholder').style.display = 'block';
        }

        document.getElementById('productModal').style.display = 'flex';

        // 드롭존 초기화
        setupImageDropZone();
    } catch (e) {
        console.error('상품 로드 실패:', e);
        alert('상품 정보를 불러올 수 없습니다.');
    }
}

/**
 * 상품 삭제 확인
 */
async function deleteProductConfirm() {
    const id = document.getElementById('productId').value;
    if (!id) return;

    if (!confirm('이 상품을 삭제하시겠습니까?')) return;

    try {
        await api(`/admin/products/${id}`, { method: 'DELETE' });
        alert('상품이 삭제되었습니다.');
        closeProductModal();
        loadProducts();
    } catch (e) {
        console.error('삭제 실패:', e);
        alert('삭제에 실패했습니다: ' + e.message);
    }
}

/**
 * 상품 삭제 (backward compatibility)
 */
async function deleteProduct(id) {
    if (!confirm('이 상품을 삭제하시겠습니까?')) return;
    try {
        await api(`/admin/products/${id}`, { method: 'DELETE' });
        loadProducts();
    } catch (e) {
        console.error('삭제 실패:', e);
        alert('삭제에 실패했습니다.');
    }
}

/**
 * 상품 저장
 */
async function saveProduct() {
    console.log('💾 [DEBUG] saveProduct 시작');
    const id = document.getElementById('productId').value;
    console.log('💾 [DEBUG] productId:', id);

    // 다국어 데이터 수집
    const data = {
        image: document.getElementById('productImage').value.trim(),
        part_no: document.getElementById('productPartNo').value.trim(),
        price: document.getElementById('productPrice').value.trim(),
        brand: document.getElementById('productBrand').value.trim(),
        category: document.getElementById('productCategory').value,
        name: {
            ko: document.getElementById('productNameKo').value.trim(),
            en: document.getElementById('productNameEn').value.trim(),
            cn: document.getElementById('productNameCn').value.trim()
        },
        description: {
            ko: document.getElementById('productDescKo').value.trim(),
            en: document.getElementById('productDescEn').value.trim(),
            cn: document.getElementById('productDescCn').value.trim()
        },
        detail_info: {
            ko: document.getElementById('productDetailInfoKo').value.trim(),
            en: document.getElementById('productDetailInfoEn').value.trim(),
            cn: document.getElementById('productDetailInfoCn').value.trim()
        },
        specs: {
            ko: collectSpecsByLang('ko'),
            en: collectSpecsByLang('en'),
            cn: collectSpecsByLang('cn')
        },
        compatibility: {
            ko: collectCompatibilityByLang('ko'),
            en: collectCompatibilityByLang('en'),
            cn: collectCompatibilityByLang('cn')
        },
        category_name: (function() {
            var selectedCode = document.getElementById('productCategory').value;
            var cat = allCategories.find(function(c) { return c.code === selectedCode; });
            if (cat) return { ko: cat.name_ko || '', en: cat.name_en || '' };
            return {};
        })()
    };

    console.log('💾 [DEBUG] 저장할 데이터:', data);

    if (!data.part_no || !data.name.ko) {
        alert('부품번호와 상품명(한국어)은 필수입니다.');
        return;
    }

    // 자동 번역 필요 여부 확인
    var needTranslation = !data.name.en || !data.name.cn || !data.description.en || !data.description.cn;

    if (needTranslation) {
        if (!confirm('영어 또는 중국어가 비어있습니다.\n\n자동 번역을 진행하시겠습니까?\n(LLM + 웹 검색 사용, 약 10-20초 소요)')) {
            return;
        }

        try {
            console.log('💾 [DEBUG] 자동 번역 시작...');
            await autoTranslateProduct(data);
            console.log('💾 [DEBUG] 자동 번역 완료');
        } catch (e) {
            console.error('❌ [ERROR] 자동 번역 실패:', e);
            if (!confirm('자동 번역에 실패했습니다.\n\n번역 없이 저장하시겠습니까?')) {
                return;
            }
        }
    }

    try {
        var res;
        if (id) {
            console.log('💾 [DEBUG] 상품 수정 요청:', `/admin/products/${id}`);
            res = await api(`/admin/products/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            console.log('💾 [DEBUG] 수정 응답 status:', res.status);
            if (!res.ok) {
                const errorText = await res.text();
                console.error('❌ [ERROR] 수정 실패 응답:', errorText);
                throw new Error('수정 실패: ' + res.status + ' - ' + errorText);
            }
            alert('상품이 수정되었습니다.');
        } else {
            console.log('💾 [DEBUG] 상품 추가 요청:', '/admin/products');
            res = await api('/admin/products', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            console.log('💾 [DEBUG] 추가 응답 status:', res.status);
            if (!res.ok) {
                const errorText = await res.text();
                console.error('❌ [ERROR] 추가 실패 응답:', errorText);
                throw new Error('추가 실패: ' + res.status + ' - ' + errorText);
            }
            alert('상품이 추가되었습니다.');
        }
        console.log('💾 [DEBUG] 모달 닫기');
        closeProductModal();
        console.log('💾 [DEBUG] 상품 목록 다시 로드');
        await loadProducts();
        console.log('✅ [DEBUG] saveProduct 완료');
    } catch (e) {
        console.error('❌ [ERROR] 상품 저장 실패:', e);
        console.error('❌ [ERROR] 에러 스택:', e.stack);
        alert('상품 저장에 실패했습니다. 콘솔을 확인하세요.\n' + e.message);
    }
}

/**
 * 상품 생성 (backward compatibility)
 */
async function createProduct(data) {
    return api('/admin/products', {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

/**
 * 상품 업데이트 (backward compatibility)
 */
async function updateProduct(id, data) {
    return api(`/admin/products/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data)
    });
}

/**
 * 상품 모달 닫기
 */
function closeProductModal() {
    const modal = document.getElementById('productModal');
    if (modal) modal.style.display = 'none';
}

/**
 * 자동 번역
 */
async function autoTranslateProduct(data) {
    var context = {
        part_no: data.part_no,
        brand: data.brand,
        category: data.category
    };

    // 상품명 번역
    if (!data.name.en && data.name.ko) {
        console.log('🌐 [TRANSLATE] 상품명 → 영어');
        var res = await api('/admin/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: data.name.ko,
                target_lang: 'en',
                context: context
            })
        });
        var result = await res.json();
        data.name.en = result.translated;
    }

    if (!data.name.cn && data.name.ko) {
        console.log('🌐 [TRANSLATE] 상품명 → 중국어');
        var res = await api('/admin/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: data.name.ko,
                target_lang: 'cn',
                context: context
            })
        });
        var result = await res.json();
        data.name.cn = result.translated;
    }

    // 설명 번역
    if (!data.description.en && data.description.ko) {
        console.log('🌐 [TRANSLATE] 설명 → 영어');
        var res = await api('/admin/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: data.description.ko,
                target_lang: 'en',
                context: context
            })
        });
        var result = await res.json();
        data.description.en = result.translated;
    }

    if (!data.description.cn && data.description.ko) {
        console.log('🌐 [TRANSLATE] 설명 → 중국어');
        var res = await api('/admin/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: data.description.ko,
                target_lang: 'cn',
                context: context
            })
        });
        var result = await res.json();
        data.description.cn = result.translated;
    }

    // 상세정보 번역
    if (!data.detail_info.en && data.detail_info.ko) {
        console.log('🌐 [TRANSLATE] 상세정보 → 영어');
        var res = await api('/admin/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: data.detail_info.ko,
                target_lang: 'en',
                context: context
            })
        });
        var result = await res.json();
        data.detail_info.en = result.translated;
    }

    if (!data.detail_info.cn && data.detail_info.ko) {
        console.log('🌐 [TRANSLATE] 상세정보 → 중국어');
        var res = await api('/admin/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: data.detail_info.ko,
                target_lang: 'cn',
                context: context
            })
        });
        var result = await res.json();
        data.detail_info.cn = result.translated;
    }

    // 스펙과 호환정보는 간단하게 처리 (여기서는 생략, 필요시 추가)
    // TODO: specs, compatibility 번역
}

/**
 * 다국어 탭 전환
 */
function switchProductLang(lang) {
    // 모든 탭 비활성화
    document.querySelectorAll('.lang-tab').forEach(tab => {
        tab.classList.remove('active');
        tab.style.color = 'var(--text-muted)';
        tab.style.borderBottomColor = 'transparent';
    });

    // 모든 콘텐츠 숨기기
    document.querySelectorAll('.lang-content').forEach(content => {
        content.style.display = 'none';
    });

    // 선택한 탭 활성화
    var activeTab = document.querySelector(`.lang-tab[data-lang="${lang}"]`);
    if (activeTab) {
        activeTab.classList.add('active');
        activeTab.style.color = 'var(--primary)';
        activeTab.style.borderBottomColor = 'var(--primary)';
    }

    // 선택한 콘텐츠 표시
    var activeContent = document.querySelector(`.lang-content[data-lang="${lang}"]`);
    if (activeContent) {
        activeContent.style.display = 'block';
    }
}

/**
 * 동적 키-값 필드 관리 (다국어 지원)
 */

// 언어별 스펙 행 추가
function addSpecRowLang(lang, key = '', value = '') {
    var container = document.getElementById('specsList' + lang.charAt(0).toUpperCase() + lang.slice(1));
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:8px;align-items:center;';

    var placeholders = {
        ko: { key: '스펙 (예: 부품번호)', value: '값 (예: 4TNV98)' },
        en: { key: 'Spec (e.g., Part Number)', value: 'Value (e.g., 4TNV98)' },
        cn: { key: '规格 (例: 零件编号)', value: '值 (例: 4TNV98)' }
    };

    row.innerHTML = `
        <input type="text" placeholder="${placeholders[lang].key}" value="${esc(key)}" style="flex:1;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:0.85rem;">
        <input type="text" placeholder="${placeholders[lang].value}" value="${esc(value)}" style="flex:2;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:0.85rem;">
        <button type="button" onclick="this.parentElement.remove()" style="padding:8px 12px;background:var(--error);color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.85rem;">×</button>
    `;
    container.appendChild(row);
}

// 언어별 호환 정보 행 추가 (배열 형식)
function addCompatibilityRowLang(lang, value = '') {
    var container = document.getElementById('compatibilityList' + lang.charAt(0).toUpperCase() + lang.slice(1));
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:8px;align-items:center;';

    var placeholders = {
        ko: '예: YANMAR 4TNV98 시리즈',
        en: 'e.g., YANMAR 4TNV98 Series',
        cn: '例: YANMAR 4TNV98 系列'
    };

    row.innerHTML = `
        <input type="text" placeholder="${placeholders[lang]}" value="${esc(value)}" style="flex:1;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:0.85rem;">
        <button type="button" onclick="this.parentElement.remove()" style="padding:8px 12px;background:var(--error);color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.85rem;">×</button>
    `;
    container.appendChild(row);
}

/**
 * 레거시 함수들 (하위 호환성)
 */

// 상세 정보 행 추가
function addDetailInfoRow(key = '', value = '') {
    var container = document.getElementById('detailInfoList');
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:8px;align-items:center;';
    row.innerHTML = `
        <input type="text" placeholder="항목 (예: 원산지)" value="${esc(key)}" style="flex:1;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:0.85rem;">
        <input type="text" placeholder="값 (예: 독일)" value="${esc(value)}" style="flex:2;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:0.85rem;">
        <button type="button" onclick="this.parentElement.remove()" style="padding:8px 12px;background:var(--error);color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.85rem;">삭제</button>
    `;
    container.appendChild(row);
}

// 스펙 행 추가
function addSpecRow(key = '', value = '') {
    var container = document.getElementById('specsList');
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:8px;align-items:center;';
    row.innerHTML = `
        <input type="text" placeholder="스펙 (예: 최대압력)" value="${esc(key)}" style="flex:1;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:0.85rem;">
        <input type="text" placeholder="값 (예: 250bar)" value="${esc(value)}" style="flex:2;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:0.85rem;">
        <button type="button" onclick="this.parentElement.remove()" style="padding:8px 12px;background:var(--error);color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.85rem;">삭제</button>
    `;
    container.appendChild(row);
}

// 호환 정보 행 추가
function addCompatibilityRow(key = '', value = '') {
    var container = document.getElementById('compatibilityList');
    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:8px;align-items:center;';
    row.innerHTML = `
        <input type="text" placeholder="항목 (예: 엔진모델)" value="${esc(key)}" style="flex:1;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:0.85rem;">
        <input type="text" placeholder="값 (예: D4-180, D6-310)" value="${esc(value)}" style="flex:2;padding:8px;border:1px solid var(--border);border-radius:6px;font-size:0.85rem;">
        <button type="button" onclick="this.parentElement.remove()" style="padding:8px 12px;background:var(--error);color:white;border:none;border-radius:6px;cursor:pointer;font-size:0.85rem;">삭제</button>
    `;
    container.appendChild(row);
}

// 키-값 쌍을 객체로 변환
function collectKeyValuePairs(containerId) {
    var container = document.getElementById(containerId);
    var rows = container.querySelectorAll('div');
    var result = {};

    rows.forEach(function(row) {
        var inputs = row.querySelectorAll('input[type="text"]');
        if (inputs.length >= 2) {
            var key = inputs[0].value.trim();
            var value = inputs[1].value.trim();
            if (key) {
                result[key] = value;
            }
        }
    });

    return result;
}

// 객체를 키-값 행으로 표시
function populateKeyValuePairs(containerId, data, addRowFunction) {
    var container = document.getElementById(containerId);
    container.innerHTML = '';

    if (data && typeof data === 'object') {
        Object.keys(data).forEach(function(key) {
            addRowFunction(key, data[key]);
        });
    }

    // 빈 행이면 하나 추가
    if (container.children.length === 0) {
        addRowFunction();
    }
}

// 언어별 스펙 수집 (객체 형식)
function collectSpecsByLang(lang) {
    var containerId = 'specsList' + lang.charAt(0).toUpperCase() + lang.slice(1);
    var container = document.getElementById(containerId);
    var rows = container.querySelectorAll('div');
    var result = {};

    rows.forEach(function(row) {
        var inputs = row.querySelectorAll('input[type="text"]');
        if (inputs.length >= 2) {
            var key = inputs[0].value.trim();
            var value = inputs[1].value.trim();
            if (key) {
                result[key] = value;
            }
        }
    });

    return result;
}

// 언어별 호환정보 수집 (배열 형식)
function collectCompatibilityByLang(lang) {
    var containerId = 'compatibilityList' + lang.charAt(0).toUpperCase() + lang.slice(1);
    var container = document.getElementById(containerId);
    var rows = container.querySelectorAll('div');
    var result = [];

    rows.forEach(function(row) {
        var input = row.querySelector('input[type="text"]');
        if (input) {
            var value = input.value.trim();
            if (value) {
                result.push(value);
            }
        }
    });

    return result;
}

// 언어별 스펙 표시
function populateSpecsByLang(lang, data) {
    var containerId = 'specsList' + lang.charAt(0).toUpperCase() + lang.slice(1);
    var container = document.getElementById(containerId);
    container.innerHTML = '';

    if (data && typeof data === 'object') {
        Object.keys(data).forEach(function(key) {
            addSpecRowLang(lang, key, data[key]);
        });
    }

    // 빈 행이면 하나 추가
    if (container.children.length === 0) {
        addSpecRowLang(lang);
    }
}

// 언어별 호환정보 표시
function populateCompatibilityByLang(lang, data) {
    var containerId = 'compatibilityList' + lang.charAt(0).toUpperCase() + lang.slice(1);
    var container = document.getElementById(containerId);
    container.innerHTML = '';

    if (Array.isArray(data)) {
        data.forEach(function(value) {
            addCompatibilityRowLang(lang, value);
        });
    }

    // 빈 행이면 하나 추가
    if (container.children.length === 0) {
        addCompatibilityRowLang(lang);
    }
}
