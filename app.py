from fastapi import FastAPI
from decouple import config
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.genai as genai
from google.genai import types
import os
from dotenv import load_dotenv


# 1. 앱 생성
print("app 생성 중...")
app = FastAPI()

# 2. CORS 설정 (이 부분이 '보안 문지기'에게 허락 맡는 부분입니다)
# 반드시 app = FastAPI() 바로 밑에 있어야 합니다!
print("app 생성 중...2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 모든 주소에서 접속 허용 (가장 중요)
    allow_credentials=True,
    allow_methods=["*"],      # GET, POST 다 허용
    allow_headers=["*"],      # 모든 헤더 허용
)
print("app 생성완료")

# 3. 데이터 형식 정의 (이게 FastAPI의 장점! - Pydantic)
# 유저가 보낼 JSON 데이터는 무조건 "message"라는 문자열이 있어야 한다고 선언
class ChatRequest(BaseModel):
    message: str


### AI 모델 답변 생성 함수 ### 
def model_answer(api_key, model_name, system_prompt, user_message):
    # 1. System Prompt (시스템 지시문) - 모델을 만들 때 '딱 한 번' 주입합니다.
    # 여기에 "너는 ~야", "JSON으로만 대답해" 같은 절대 규칙을 넣습니다.
    print("모델에 프롬프트 전달 중...")
    client = genai.Client(api_key=api_key)

    # 2. User Prompt (사용자 질문) - 대화할 때 사용합니다.
    user_prompt = user_message

    print(f"사용자 질문 전달 중...{user_prompt}")

    response = client.models.generate_content(
        model=model_name, 
        contents=user_prompt,
        config=types.GenerateContentConfig(
        system_instruction=system_prompt, # 여기에 시스템 프롬프트가 들어갑니다
        temperature=0.7, # 창의성 조절 (0.0: 정확함 ~ 1.0: 창의적임)
        )
    )
    
    print(f"답변 생성 완료")

    return response.text

# --- [AI 로직 (여기에 파이썬 코드 작성)] ---
def get_ai_response(user_message: str):
    user_message = user_message.strip() # 공백 제거
    ## config

    # Railway가 관리하는 비밀금고(환경변수)에서 키를 가져오는 코드

    api_key = config("GOOGLE_API_KEY")
    print(len(api_key))
    print(api_key[:3])

    if api_key:
        print(f"✅ API Key 로드 성공 {len(api_key)}", flush=True)

        model_name = 'gemini-2.5-flash'
        system_prompt = """
        당신은 사용자의 질문에 대답을 하는 AI 비서입니다. 질문에 알맞는 답변을 생성하여 주세요.
        당신은 영마린테크 AI 상담원입니다.
        영마린테크는 선박 엔진 및 부품을 판매하는 회사입니다.
        아래는 영마린테크에서 판매하는 제품들의 가격 설명입니다.

        제품에 대해 물어보면 해당 주어진 정보로 답변을 하고 이외의 질문이 들어오면 일반적인 질문에 대한 답변을 생성하세요.
        
        ## 제품 가격 설명
        얀마 커넥팅 로드 베어링 : 2,000원
        마린 디젤 엔진 플린저 베럴 : 400,000원
        선박 엔진 예비 부품 모음 : 문의 바람
        피스톤 핀 부시 : 100,000원
        다이하츠 밸브 스템 씰: 2,600원

        자세한 내용은 추천 부품 목록을 참고하세요.
        """
        
        if "안녕" in user_message:
            return "안녕하세요! 영마린테크 AI 상담원입니다."
        else:
            return model_answer(api_key, model_name, system_prompt, user_message)
    else:
        print("⚠️ API Key를 환경변수에서 찾지 못했습니다. .env 파일을 확인하세요.", flush=True)

        return "API Key를 환경변수에서 찾지 못했습니다"

    
# -------------------------------------------

# 4. API 엔드포인트 만들기
@app.post("/chat")
async def chat(request: ChatRequest):
    # request.message 로 바로 데이터를 꺼낼 수 있음 (검증 완료된 상태)
    print(f"유저 질문: {request.message}")

    ai_reply = get_ai_response(request.message)
    print(f"AI 답변: {ai_reply}")
    
    return {"reply": ai_reply}

# 실행 방법 주석:
# 터미널에서: uvicorn app:app --reload


if __name__ == "__main__":
    import uvicorn
    from decouple import config

    # Railway가 제공하는 포트 번호를 가져옴 (없으면 기본값 8000)
    port = int(os.environ.get("PORT", 8000))
    api_key = config("GOOGLE_API_KEY")
    
    print(f"🚀 서버를 시작합니다! 포트: {port}")
    print(f"🚀 api_key를 확인합니다.! 포트: {api_key[:5]}")
    
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)

