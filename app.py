from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

# 1. 앱 생성
app = FastAPI()

# 2. CORS 설정 (보안 해제)
# HTML(127.0.0.1:5500)에서 이 서버(127.0.0.1:8000)로 접속할 수 있게 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 곳에서 접속 허용 (배포 시에는 실제 주소로 바꾸는 게 좋음)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용 (GET, POST 등)
    allow_headers=["*"],  # 모든 헤더 허용
)

# 3. 데이터 형식 정의 (이게 FastAPI의 장점! - Pydantic)
# 유저가 보낼 JSON 데이터는 무조건 "message"라는 문자열이 있어야 한다고 선언
class ChatRequest(BaseModel):
    message: str


### AI 모델 답변 생성 함수 ### 
def model_answer(api_key, model_name, system_prompt, user_message):
    genai.configure(api_key=api_key)
    
    # 1. System Prompt (시스템 지시문) - 모델을 만들 때 '딱 한 번' 주입합니다.
    # 여기에 "너는 ~야", "JSON으로만 대답해" 같은 절대 규칙을 넣습니다.
    
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt  
    )
    
    # 2. User Prompt (사용자 질문) - 대화할 때 사용합니다.
    user_prompt = user_message
    response = model.generate_content(user_prompt)
    print(response.text)
    
    return response.text

# --- [AI 로직 (여기에 파이썬 코드 작성)] ---
def get_ai_response(user_message: str):
    user_message = user_message.strip() # 공백 제거
    ## config
    api_key = 'AIzaSyAvDPbTyvHawAl3_WYE0xSMPWpO7ZX3cAA'
    model_name = 'gemini-2.5-flash'
    system_prompt = "당신은 사용자의 질문에 대답을 하는 AI 비서입니다. 질문에 알맞는 답변을 생성하여 주세요."

    if "가격" in user_message:
        return "제품 가격은 상세페이지를 참고해 주세요. (FastAPI가 답변 중)"
    elif "배송" in user_message:
        return "배송은 영업일 기준 2~3일 소요됩니다."
    elif "안녕" in user_message:
        return "안녕하세요! 영마린테크 AI 상담원입니다."
    else:
        return model_answer(api_key, model_name, system_prompt, user_message)
# -------------------------------------------

# 4. API 엔드포인트 만들기
@app.post("/chat")
async def chat(request: ChatRequest):
    # request.message 로 바로 데이터를 꺼낼 수 있음 (검증 완료된 상태)
    print(f"유저 질문: {request.message}")
    print(f"유저 질문: {request}")

    ai_reply = get_ai_response(request.message)
    print(f"AI 답변: {ai_reply}")
    
    return {"reply": ai_reply}

# 실행 방법 주석:
# 터미널에서: uvicorn app:app --reload