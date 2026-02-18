
/**
 * settings.js
 * 홈페이지 설정 관리
 */

var siteSettings = {};

/**
 * 사이트 로고 로드 (전역 변수용)
 */
async function loadSiteLogo() {
    try {
        const res = await fetch(API_BASE + '/api/site-settings');
        if (res.ok) {
            const settings = await res.json();
            if (settings.logo) {
                siteLogoUrl = settings.logo;
            }
        }
    } catch (e) {
        console.log('로고 로드 실패 (무시):', e);
    }
}

/**
 * 사이트 설정 로드
 */
async function loadSiteSettings() {
    try {
        const res = await api('/admin/settings');
        siteSettings = await res.json();

        // 로고 표시
        const logoValue = siteSettings.logo?.value || '';
        const currentLogoEl = document.getElementById('currentLogo');
        if (logoValue) {
            currentLogoEl.innerHTML = `<img src="${logoValue}" style="max-width:100%;max-height:100px;object-fit:contain;" alt="로고">`;
        } else {
            currentLogoEl.innerHTML = '<span style="color:var(--text-muted);font-size:0.85rem;">등록된 로고가 없습니다</span>';
        }

        // 회사 정보
        document.getElementById('companyName').value = siteSettings.company_name?.value || '';
        document.getElementById('companyAddress').value = siteSettings.company_address?.value || '';
        document.getElementById('companyPhone').value = siteSettings.company_phone?.value || '';
        document.getElementById('companyEmail').value = siteSettings.company_email?.value || '';

        // 히어로 섹션
        document.getElementById('heroTitle').value = siteSettings.hero_title?.value || '';
        document.getElementById('heroSubtitle').value = siteSettings.hero_subtitle?.value || '';

        // 기타 설정
        document.getElementById('footerCopyright').value = siteSettings.footer_copyright?.value || '';

    } catch (e) {
        console.error('설정 로드 실패:', e);
        alert('설정을 불러오는데 실패했습니다.');
    }
}

/**
 * 로고 저장
 */
async function saveLogo() {
    const logoValue = document.getElementById('logoInput').value.trim();
    if (!logoValue) {
        alert('로고 URL 또는 이미지 파일을 선택해주세요.');
        return;
    }

    try {
        await api('/admin/settings/logo', {
            method: 'POST',
            body: JSON.stringify({ logo: logoValue })
        });
        alert('로고가 저장되었습니다.');
        document.getElementById('logoInput').value = '';
        loadSiteSettings();
    } catch (e) {
        console.error('로고 저장 실패:', e);
        alert('로고 저장에 실패했습니다: ' + e.message);
    }
}

/**
 * 로고 이미지 파일 처리 (드래그앤드롭 또는 파일 선택)
 */
function handleLogoFile(file) {
    if (!file || !file.type.startsWith('image/')) {
        alert('이미지 파일만 업로드 가능합니다.');
        return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
        const base64Data = e.target.result;
        try {
            await api('/admin/settings/logo', {
                method: 'POST',
                body: JSON.stringify({ logo: base64Data })
            });
            alert('로고가 업로드되었습니다.');
            loadSiteSettings();
        } catch (err) {
            console.error('로고 업로드 실패:', err);
            alert('로고 업로드에 실패했습니다: ' + err.message);
        }
    };
    reader.readAsDataURL(file);
}

/**
 * 로고 드래그앤드롭 초기화
 */
function initLogoUpload() {
    const dropZone = document.getElementById('logoDropZone');
    const fileInput = document.getElementById('logoFileInput');

    if (!dropZone || !fileInput) return;

    // 드래그오버 효과
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--accent)';
        dropZone.style.background = 'var(--primary-light)';
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'var(--bg-gray)';
    });

    // 드롭 처리
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'var(--bg-gray)';

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleLogoFile(files[0]);
        }
    });

    // 파일 선택 처리
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleLogoFile(e.target.files[0]);
        }
    });
}

/**
 * 회사 정보 저장
 */
async function saveCompanyInfo() {
    const data = {
        company_name: document.getElementById('companyName').value.trim(),
        company_address: document.getElementById('companyAddress').value.trim(),
        company_phone: document.getElementById('companyPhone').value.trim(),
        company_email: document.getElementById('companyEmail').value.trim(),
    };

    try {
        for (const [key, value] of Object.entries(data)) {
            await api(`/admin/settings/${key}`, {
                method: 'PUT',
                body: JSON.stringify({ value })
            });
        }
        alert('회사 정보가 저장되었습니다.');
        loadSiteSettings();
    } catch (e) {
        console.error('회사 정보 저장 실패:', e);
        alert('회사 정보 저장에 실패했습니다: ' + e.message);
    }
}

/**
 * 히어로 섹션 저장
 */
async function saveHeroSection() {
    const data = {
        hero_title: document.getElementById('heroTitle').value.trim(),
        hero_subtitle: document.getElementById('heroSubtitle').value.trim(),
    };

    try {
        for (const [key, value] of Object.entries(data)) {
            await api(`/admin/settings/${key}`, {
                method: 'PUT',
                body: JSON.stringify({ value })
            });
        }
        alert('히어로 섹션이 저장되었습니다.');
        loadSiteSettings();
    } catch (e) {
        console.error('히어로 섹션 저장 실패:', e);
        alert('히어로 섹션 저장에 실패했습니다: ' + e.message);
    }
}

/**
 * 기타 설정 저장
 */
async function saveOtherSettings() {
    const footerCopyright = document.getElementById('footerCopyright').value.trim();

    try {
        await api('/admin/settings/footer_copyright', {
            method: 'PUT',
            body: JSON.stringify({ value: footerCopyright })
        });
        alert('설정이 저장되었습니다.');
        loadSiteSettings();
    } catch (e) {
        console.error('설정 저장 실패:', e);
        alert('설정 저장에 실패했습니다: ' + e.message);
    }
}
