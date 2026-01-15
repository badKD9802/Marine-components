// js/sendMessage.js

async function sendMessage() {
    const inputField = document.getElementById('userInput');
    const message = inputField.value.trim();
    if (!message) return;

    // 1. 내 메시지 표시
    appendMessage(message, 'user-msg', false);
    inputField.value = '';

    // 2. 로딩 애니메이션 표시
    const loadingId = showLoading();
    

    try {
        // 3. FastAPI 서버로 전송http://127.0.0.1:8000
        // const response = await fetch('http://127.0.0.1:8000/chat', { 
        const response = await fetch('https://marine-parts-production-60a3.up.railway.app/chat', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        
        const data = await response.json();
        
        // 4. 로딩 삭제
        removeLoading(loadingId);

        // 5. [변경됨] 타자 치는 효과로 메시지 출력
        // 답변을 바로 보여주지 않고 typeWriter 함수에 넘김
        typeWriter(data.reply, 'bot-msg');

    } catch (error) {
        console.error('Error:', error);
        removeLoading(loadingId);
        appendMessage(error, 'bot-msg', false);
    }
}

// [추가됨] 타자 치는 효과 함수
function typeWriter(text, className) {
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