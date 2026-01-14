// js/data.js 파일
// [수정됨] 메시지 전송 함수 (로딩 및 마크다운 적용)
async function sendMessage() {
    const inputField = document.getElementById('userInput');
    const message = inputField.value.trim();
    if (!message) return;

    // 1. 내 메시지 표시 (유저는 그냥 텍스트)
    appendMessage(message, 'user-msg', false);
    inputField.value = '';

    // 2. 로딩 애니메이션 표시 ("답변 생성 중...")
    const loadingId = showLoading();

    try {
        // 3. FastAPI 서버로 전송
        const response = await fetch('http://127.0.0.1:8000/chat', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        
        const data = await response.json();
        
        // 4. 응답 오면 로딩 메시지 삭제
        removeLoading(loadingId);

        // 5. AI 메시지 표시 (마크다운 -> HTML 변환)
        // marked.parse()가 **안녕**을 <b>안녕</b>으로 바꿔줍니다.
        const htmlContent = marked.parse(data.reply); 
        appendMessage(htmlContent, 'bot-msg', true);

    } catch (error) {
        console.error('Error:', error);
        removeLoading(loadingId);
        appendMessage("죄송합니다. 서버 연결에 실패했습니다.", 'bot-msg', false);
    }
}

// [수정됨] 메시지 추가 함수 (isHtml: true면 HTML 태그로 넣음)
function appendMessage(content, className, isHtml) {
    const chatMessages = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `message ${className}`;
    
    if (isHtml) {
        div.innerHTML = content; // 마크다운 변환된 HTML
    } else {
        div.innerText = content; // 일반 텍스트 (보안상 안전)
    }
    
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// [추가됨] 로딩 애니메이션 보여주기
function showLoading() {
    const chatMessages = document.getElementById('chatMessages');
    const div = document.createElement('div');
    const id = 'loading-' + Date.now(); // 유니크한 ID 생성
    div.id = id;
    div.className = 'message bot-msg';
    
    // 점 3개 애니메이션 HTML
    div.innerHTML = `
        <div class="typing-indicator">
            <span></span><span></span><span></span>
        </div>
    `;
    
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id; // 나중에 지우기 위해 ID 반환
}

// [추가됨] 로딩 애니메이션 지우기
function removeLoading(id) {
    const element = document.getElementById(id);
    if (element) {
        element.remove();
    }
}

const products = [
    {
        id: 1,
        image: "./parts_image/YANMAR CON BOD BEARING(4TNV98 129900-23600).jpg", 
        partNo: "4TNV98 129900-23600",
        price: "2,000",
        name: { ko: "얀마 커넥팅 로드 베어링", en: "YANMAR CON ROD BEARING", cn: "YANMAR 连杆轴承" },
        desc: { ko: "4TNV98 엔진 호환", en: "Compatible with 4TNV98", cn: "兼容 4TNV98" }
    },
    {
        id: 2,
        image: "./parts_image/YANMAR EY18AL.jpg",
        partNo: "PB1002 / PB1003",
        price: "400,000",
        name: { ko: "마린 디젤 엔진 플린저 베럴", en: "YANMAR EY18AL Plunger", cn: "YANMAR EY18AL 柱塞" },
        desc: { ko: "AL-SERIES / AL-PLUS 모델", en: "AL-SERIES / AL-PLUS", cn: "AL-SERIES / AL-PLUS" }
    },
    {
        id: 3,
        image: "./parts_image/DAIHATSU,KASAKA,YAN MAR,HANSHIN MAN,Etc.jpg",
        partNo: "Multi-Brand Parts",
        price: "문의 (Contact Us)",
        name: { ko: "선박 엔진 예비 부품 모음", en: "Marine Spare Parts (Daihatsu, Yanmar...)", cn: "船用备件 (Daihatsu, Yanmar...)" },
        desc: { ko: "다이하츠, 얀마, 한신 등 취급", en: "Daihatsu, Yanmar, Hanshin etc.", cn: "Daihatsu, Yanmar, Hanshin 等" }
    },
    {
        id: 4,
        image: "./parts_image/E205250040Z.jpg",
        partNo: "E205250040Z",
        price: "100,000",
        name: { ko: "피스톤 핀 부시", en: "Piston Pin Bush", cn: "活塞销衬套" },
        desc: { ko: "해양 엔진 부품", en: "Marine Engine Parts", cn: "船用发动机零件" }
    },
        {
        id: 5,
        image: "./parts_image/Daihatsu_DL22.jpg",
        partNo: "DL22",
        price: "2,600",
        name: { ko: "다이하츠 밸브 스템 씰", en: "Daihatsu DL22 Valve Stem Seal", cn: "Daihatsu DL22 气门杆密封" },
        desc: { ko: "DL22 모델 전용", en: "For DL22 Model", cn: "仅限 DL22 型号" }
    }
];