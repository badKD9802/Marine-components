from fastapi import FastAPI
from decouple import config
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.genai as genai
from google.genai import types
import os
from dotenv import load_dotenv
import json


# 1. 앱 생성
print("app 생성 중...")
app = FastAPI()
print("has GOOGLE_API_KEY?", "GOOGLE_API_KEY" in os.environ)
print("GOOGLE_API_KEY =", os.environ.get("GOOGLE_API_KEY"))


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
    history: list[dict] = [] # 대화 기록 추가

### AI 모델 답변 생성 함수 ### 
def model_answer(api_key, model_name, system_prompt, history, user_message):
    print("모델에 프롬프트 전달 중...")
    client = genai.Client(api_key=api_key)

    contents = []
    for turn in history:
        contents.append({"role": turn["role"], "parts": [turn["parts"]]}) # Assuming 'parts' in history is a single string
    contents.append({"role": "user", "parts": [user_message]})
    
    print(f"대화 내용 전달 중: {contents}")

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7,
        )
    )
    
    print(f"답변 생성 완료")

    return response.text

# --- [AI 로직 (여기에 파이썬 코드 작성)] ---
def get_ai_response(user_message: str, history: list[dict]):
    user_message = user_message.strip() # 공백 제거

    api_key = config("GOOGLE_API_KEY")

    if api_key:
        print(f"✅ API Key 로드 성공", flush=True)

        model_name = 'gemini-2.5-flash'
        system_prompt = """
        당신은 영마린테크의 AI 상담원입니다.
        영마린테크는 선박 엔진 및 부품을 판매하는 회사입니다.
        사용자의 질문에 대해 영마린테크의 정보를 바탕으로 정확하고 친절하게 답변해주세요.
        응답은 반드시 JSON 형식으로 제공해야 합니다. 응답 JSON은 'reply' (메인 답변)와 'suggested_questions' (다음 질문 제안 1~3개) 두 개의 키를 포함해야 합니다.
        'suggested_questions'는 배열이어야 하며, 제안할 질문이 없는 경우 빈 배열로 두세요.

        ## 영마린테크 정보
        영마린테크에서 판매하는 제품들의 가격 설명입니다:
        - 얀마 커넥팅 로드 베어링: 2,000원
        - 마린 디젤 엔진 플린저 베럴: 400,000원
        - 선박 엔진 예비 부품 모음: 문의 바람
        - 피스톤 핀 부시: 100,000원
        - 다이하츠 밸브 스템 씰: 2,600원
        자세한 내용은 추천 부품 목록을 참고하세요.

        영마린테크는 20년 이상의 전문 경험을 가지고 있으며, YANMAR, Daihatsu 등 글로벌 브랜드의 정품 부품만을 취급합니다.
        신속 배송과 24/7 기술 지원을 제공하며, 100% 정품 보증과 글로벌 네트워크를 통해 안정적인 재고를 확보합니다.
        전문 컨설팅, 재고 관리, 맞춤 견적 서비스를 제공합니다.

        ## 예시
        사용자: 얀마 커넥팅 로드 베어링 가격이 얼마인가요?
        AI: {
            "reply": "얀마 커넥팅 로드 베어링은 2,000원입니다.",
            "suggested_questions": ["다른 베어링도 있나요?", "배송은 얼마나 걸리나요?", "견적 요청은 어떻게 하나요?"]
        }

        사용자: 안녕하세요
        AI: {
            "reply": "안녕하세요! 영마린테크 AI 상담원입니다. 무엇을 도와드릴까요?",
            "suggested_questions": ["회사 소개", "제품 목록 보기", "견적 문의"]
        }
        """

        response_text = model_answer(api_key, model_name, system_prompt, history, user_message)
        
        try:
            gemini_response = json.loads(response_text)
            reply = gemini_response.get("reply", "죄송합니다. 답변을 생성하는 데 문제가 발생했습니다.")
            suggested_questions = gemini_response.get("suggested_questions", [])
            return {"reply": reply, "suggested_questions": suggested_questions}
        except json.JSONDecodeError:
            print(f"⚠️ Gemini 응답 JSON 파싱 오류: {response_text}")
            return {"reply": "죄송합니다. 예상치 못한 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", "suggested_questions": []}

    else:
        print("⚠️ API Key를 환경변수에서 찾지 못했습니다. .env 파일을 확인하세요.", flush=True)
        return {"reply": "API Key를 환경변수에서 찾지 못했습니다", "suggested_questions": []}
    
# -------------------------------------------

# 4. API 엔드포인트 만들기
@app.post("/chat")
async def chat(request: ChatRequest):
    print(f"유저 질문: {request.message}")
    print(f"채팅 기록: {request.history}")

    response = get_ai_response(request.message, request.history)
    print(f"AI 답변: {response['reply']}")
    print(f"제안된 질문: {response['suggested_questions']}")
    
    return response

# 실행 방법 주석:
# 터미널에서: uvicorn app:app --reload


if __name__ == "__main__":
    import uvicorn
    from decouple import config

    # Railway가 제공하는 포트 번호를 가져옴 (없으면 기본값 8000)
    port = int(os.environ.get("PORT", 8000))
    # api_key = config("GOOGLE_API_KEY")
    api_key = os.environ
    
    print(f"🚀 서버를 시작합니다! 포트: {port}")
    print(f"🚀 api_key를 확인합니다.! 포트: {api_key}")
    
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)

