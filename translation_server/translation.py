from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
import uvicorn

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
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        return "오류: API Key가 없습니다. Railway 환경변수를 확인해주세요."

    print(api_key)
    client = genai.Client(api_key=api_key)

    # ★ 핵심 변경: 시스템 프롬프트를 번역가 설정으로 변경
    system_prompt = """
    당신은 세계 최고의 전문 번역가입니다.
    사용자가 입력한 텍스트를 분석하여 다음과 같이 처리하세요:
    
    1. 입력된 텍스트가 한국어라면 -> '영어'로 번역하세요.
    2. 입력된 텍스트가 외국어(영어 등)라면 -> 자연스러운 '한국어'로 번역하세요.
    3. 번역 결과 외에 다른 말(설명, 인사 등)은 절대 하지 마세요. 오직 번역된 문장만 출력하세요.
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 번역 서버 시작! 포트: {port}")
    uvicorn.run("translation:app", host="0.0.0.0", port=port, reload=False)