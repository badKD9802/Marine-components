from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
import uvicorn
from decouple import config

## 메일 가져오기 ##

# 기존 import 아래에 추가
import imaplib
import email
from email.header import decode_header

def clean_text(text, encoding):
    if isinstance(text, bytes):
        if encoding:
            return text.decode(encoding)
        else:
            return text.decode('utf-8', errors='ignore')
    return text

# 1. 메일 가져오기용 데이터 모델 (ID, 비번 받기 위함)
class FetchMailRequest(BaseModel):
    gmail_id: str
    gmail_pw: str

# 2. 메일 보내기용 데이터 모델 (ID, 비번 추가)
class SendMailRequest(BaseModel):
    gmail_id: str
    gmail_pw: str
    to_email: str
    subject: str
    content: str

# 1. 앱 생성
print("app 생성 중...")
app = FastAPI()

# 2. CORS 설정 (보안 문지기)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 모든 주소 허용
    allow_credentials=True,
    allow_methods=["*"],      # 모든 방식(GET, POST) 허용
    allow_headers=["*"],      # 모든 헤더 허용
)
print("app 생성완료")

# 3. 데이터 형식 정의 (번역할 텍스트 받기)
class TranslationRequest(BaseModel):
    text: str  # 기존 message -> text로 변경 (더 직관적)

### AI 번역 함수 ### 
def get_translation(user_text):
    # 환경변수 로드
    api_key = config("GOOGLE_API_KEY")
    print(len(api_key))
    print(api_key[:3])

    if not api_key:
        return "오류: API Key가 없습니다. Railway 환경변수를 확인해주세요."

    print(api_key)
    client = genai.Client(api_key=api_key)

    # ★ 핵심 변경: 시스템 프롬프트를 번역가 설정으로 변경
    system_prompt = """ 
    당신은 최고의 “한국어 번역기”입니다. 사용자가 입력한 모든 언어를 자연스럽고 정확한 한국어로 번역하세요.
    목표는 배부품(마린 파츠) 견적 문의 이메일을 한국인이 쉽게 읽도록 만드는 것입니다.
    원문의 의미·수량·모델명·규격·가격·납기·연락처 정보를 절대 바꾸지 마세요.
    고유명사(회사명/제품명/모델명/부품번호)는 원문 그대로 유지하세요.
    숫자, 단위, 통화(USD 등), 날짜, 이메일/URL은 변경하지 마세요.
    문장이 어색하면 한국어 어순으로만 자연스럽게 다듬되 내용 추가/삭제는 금지합니다.
    줄바꿈과 목록 형식은 가능한 유지하세요.
    번역 결과만 출력하고, 설명이나 추가 질문은 하지 마세요.

    예시)
    [원문] Please send me a quote for 10 units of model X123 by next Friday.
    [번역] 다음 주 금요일까지 모델 X123 10대에 대한 견적서를 보내주시기 바랍니다.

    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', # 최신 모델 사용 (속도 빠름)
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3, # 번역은 정확성이 중요하므로 창의성(temperature)을 낮춤
            )
        )
        return response.text
    except Exception as e:
        return f"번역 중 오류 발생: {str(e)}"

# 4. API 엔드포인트
@app.post("/translate") # 주소를 /chat 에서 /translate 로 변경
async def translate(request: TranslationRequest):
    print(f"원본 텍스트: {request.text}")
    
    translated_result = get_translation(request.text)
    print(f"번역 결과: {translated_result}")
    
    return {
        "original": request.text,
        "translated": translated_result
    }

# 3. 메일 가져오기 (POST로 변경!)
@app.post("/get-emails")  # <--- GET에서 POST로 변경됨
async def get_emails(request: FetchMailRequest):
    # 이제 환경변수가 아니라, 유저가 보낸 request에서 꺼내 씁니다.
    user = request.gmail_id
    pwd = request.gmail_pw

    print(user)
    print(pwd)

    if not user or not pwd:
        return {"error": "아이디와 앱 비밀번호를 입력해주세요."}

    try:
        # 로직은 그대로인데 변수만 바뀜 (gmail_user -> user)
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, pwd) # <--- 여기서 유저 입력값으로 로그인
        mail.select("inbox")

        status, messages = mail.search(None, "ALL")
        mail_ids = messages[0].split()
        latest_email_ids = mail_ids[-5:] 
        
        email_list = []

        for i in reversed(latest_email_ids):
            res, msg = mail.fetch(i, "(RFC822)")
            for response in msg:
                if isinstance(response, tuple):
                    msg = email.message_from_bytes(response[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    subject = clean_text(subject, encoding)
                    sender, encoding = decode_header(msg["From"])[0]
                    sender = clean_text(sender, encoding)
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')

                    email_list.append({
                        "subject": subject,
                        "sender": sender,
                        "body": body[:500] + "..."
                    })

        mail.logout()
        return {"emails": email_list}

    except Exception as e:
        return {"error": "로그인 실패! 앱 비밀번호가 맞나요? (" + str(e) + ")"}


# 4. 메일 보내기 (입력받은 정보로 전송)
@app.post("/send-email")
async def send_email(request: SendMailRequest):
    try:
        msg = MIMEText(request.content)
        msg['Subject'] = request.subject
        msg['From'] = request.gmail_id
        msg['To'] = request.to_email

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            # 유저가 입력한 ID/PW로 로그인
            server.login(request.gmail_id, request.gmail_pw)
            server.send_message(msg)
            
        return {"status": "이메일 전송 성공! 🚀"}
    except Exception as e:
        return {"status": f"전송 실패: {str(e)}"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 번역 서버 시작! 포트: {port}")
    api_key = os.environ
    print(f"🚀 api_key를 확인합니다.! 포트: {api_key}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)