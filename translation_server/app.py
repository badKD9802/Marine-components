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
    api_key = config("GOOGLE_API_KEY")
    print(len(api_key))
    print(api_key[:3])

    if not api_key:
        return "오류: API Key가 없습니다. Railway 환경변수를 확인해주세요."

    print(api_key)
    client = genai.Client(api_key=api_key)

    # ★ 핵심 변경: 시스템 프롬프트를 번역가 설정으로 변경
    system_prompt = """
    당신은 “한국어 번역기”입니다. 사용자가 입력한 모든 언어를 자연스럽고 정확한 한국어로 번역하세요.
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 번역 서버 시작! 포트: {port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)