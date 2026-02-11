// js/sendMessage.js

let chatHistory = []; // 대화 기록을 저장할 배열

async function sendMessage() {
    const inputField = document.getElementById('userInput');
    const message = inputField.value.trim();
    if (!message) return;

    // 1. 내 메시지 표시 및 기록
    appendMessage(message, 'user-msg', false);
    chatHistory.push({ role: 'user', parts: message }); // 사용자 메시지 기록
    inputField.value = '';

    // 2. 로딩 애니메이션 표시
    const loadingId = showLoading();
    
    // 이전 제안된 질문들을 제거
    clearSuggestedQuestions();

    try {
        // 3. FastAPI 서버로 전송 (history 포함)
        // const response = await fetch('http://127.0.0.1:8000/chat', { 
        const response = await fetch('https://marine-parts-production-60a3.up.railway.app/chat', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, history: chatHistory }) // history 추가
        });
        
        const data = await response.json();
        
        // 4. 로딩 삭제
        removeLoading(loadingId);

        // 5. [변경됨] 타자 치는 효과로 메시지 출력 및 기록
        typeWriter(data.reply, 'bot-msg');
        chatHistory.push({ role: 'model', parts: data.reply }); // 봇 메시지 기록

        // 6. 제안된 질문 표시 (새로 추가)
        if (data.suggested_questions && data.suggested_questions.length > 0) {
            displaySuggestedQuestions(data.suggested_questions);
        }

    } catch (error) {
        console.error('Error:', error);
        removeLoading(loadingId);
        appendMessage(error, 'bot-msg', false);
    }
}

// [추가됨] 타자 치는 효과 함수
function typeWriter(text, className, callback = null) {
    const chatMessages = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `message ${className}`;
    chatMessages.appendChild(div);

    let i = 0;
    const speed = 30; // 글자 찍히는 속도 (ms) - 숫자가 작을수록 빠름

    function type() {
        if (i < text.length) {
            // 한 글자씩 추가
            div.innerHTML += text.charAt(i);
            i++;
            chatMessages.scrollTop = chatMessages.scrollHeight; // 스크롤 따라가기
            setTimeout(type, speed); // 다음 글자 찍기 예약
        } else {
            // [중요] 타자가 다 끝나면 마크다운으로 변환해서 예쁘게 보여줌
            // 타자 칠 때는 **안녕** 이렇게 보이다가, 다 치면 굵게 변함
            div.innerHTML = marked.parse(text); 
            if (callback) {
                callback(); // 콜백 함수 실행
            }
        }
    }
    type(); // 타자 시작
}

function appendMessage(content, className, isHtml) {
    const chatMessages = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `message ${className}`;
    
    if (isHtml) {
        div.innerHTML = content;
    } else {
        div.innerText = content;
    }
    
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showLoading() {
    const chatMessages = document.getElementById('chatMessages');
    const div = document.createElement('div');
    const id = 'loading-' + Date.now();
    div.id = id;
    div.className = 'message bot-msg';
    div.innerHTML = `
        <div class="typing-indicator">
            <span></span><span></span><span></span>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeLoading(id) {
    const element = document.getElementById(id);
    if (element) {
        element.remove();
    }
}

// [추가됨] 제안된 질문 표시 함수
function displaySuggestedQuestions(questions) {
    let suggestedQuestionsContainer = document.getElementById('suggestedQuestionsContainer');
    if (!suggestedQuestionsContainer) {
        suggestedQuestionsContainer = document.createElement('div');
        suggestedQuestionsContainer.id = 'suggestedQuestionsContainer';
        suggestedQuestionsContainer.className = 'suggested-questions'; // CSS 클래스 추가
        document.getElementById('chatMessages').appendChild(suggestedQuestionsContainer);
    }
    
    suggestedQuestionsContainer.innerHTML = ''; // 기존 질문 지우기

    questions.forEach(question => {
        const button = document.createElement('button');
        button.className = 'suggested-btn'; // CSS 클래스 추가
        button.textContent = question;
        button.onclick = () => {
            document.getElementById('userInput').value = question;
            sendMessage();
            clearSuggestedQuestions();
        };
        suggestedQuestionsContainer.appendChild(button);
    });
    document.getElementById('chatMessages').scrollTop = document.getElementById('chatMessages').scrollHeight;
}

// [추가됨] 제안된 질문 지우기 함수
function clearSuggestedQuestions() {
    const suggestedQuestionsContainer = document.getElementById('suggestedQuestionsContainer');
    if (suggestedQuestionsContainer) {
        suggestedQuestionsContainer.innerHTML = '';
    }
}

// [추가됨] 초기 빠른 질문 표시 함수 (채팅창 열릴 때)
function showQuickQuestions() {
    const quickQuestionsContainer = document.getElementById('quickQuestionsContainer');
    if (quickQuestionsContainer) {
        quickQuestionsContainer.style.display = 'flex'; // 다시 보이도록 설정
    }
}