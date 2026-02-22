from contextlib import asynccontextmanager
from fastapi import FastAPI
from decouple import config
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import google.genai as genai
from google.genai import types
import os
from dotenv import load_dotenv
import json

load_dotenv()

import asyncio

from db import init_db, close_db, init_vector_db, close_vector_db, get_all_products, get_product_by_id, create_product, get_products_for_ai_prompt
from admin import router as admin_router
from rag_chat import router as rag_chat_router, cleanup_old_conversations
from mail_compose import router as mail_compose_router, gmail_auto_check_loop
from inquiry import router as inquiry_router
from rag import search_similar_chunks
from portfolio_rag import init_portfolio_rag, search_portfolio

_scheduler_task = None


# Lifespan: DB init/close + Gmail 자동 체크 스케줄러 + Portfolio RAG 초기화
@asynccontextmanager
async def lifespan(app):
    global _scheduler_task
    await init_db()
    await init_vector_db()
    await cleanup_old_conversations()

    # Portfolio RAG 초기화
    openai_api_key = config("OPENAI_API_KEY")
    if openai_api_key:
        init_portfolio_rag(openai_api_key)
        print("[App] Portfolio RAG 초기화 완료")
    else:
        print("[App] Warning: OPENAI_API_KEY 없음, Portfolio RAG 비활성화")

    _scheduler_task = asyncio.create_task(gmail_auto_check_loop())
    yield
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    await close_vector_db()
    await close_db()


# 1. 앱 생성
print("app 생성 중...")
app = FastAPI(lifespan=lifespan)
print("=== 환경변수 확인 ===")
print(f"  GOOGLE_API_KEY: {'설정됨 (' + os.environ['GOOGLE_API_KEY'][:8] + '...)' if os.environ.get('GOOGLE_API_KEY') else '미설정'}")
print(f"  OPENAI_API_KEY: {'설정됨 (' + os.environ['OPENAI_API_KEY'][:8] + '...)' if os.environ.get('OPENAI_API_KEY') else '미설정'}")
print(f"  ADMIN_PASSWORD: {'설정됨 (' + str(len(os.environ.get('ADMIN_PASSWORD',''))) + '자)' if os.environ.get('ADMIN_PASSWORD') else '미설정'}")
print(f"  DATABASE_URL:   {'설정됨' if os.environ.get('DATABASE_URL') else '미설정'}")
print(f"  PGVECTOR_DB:    {'설정됨' if os.environ.get('PGVECTOR_DATABASE_URL') else '미설정'}")
print("====================")


# 2. CORS 설정
print("app 생성 중...2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin_router)
app.include_router(rag_chat_router)
app.include_router(mail_compose_router)
app.include_router(inquiry_router)
print("app 생성완료")


# 3. 데이터 형식 정의
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    niceContext: dict = None  # NICE평가정보 관련 컨텍스트 (선택적)


class ProductCreate(BaseModel):
    image: str
    part_no: str
    price: str
    brand: str = ""
    category: str = ""
    name: dict
    description: dict
    category_name: dict = {}
    detail_info: dict = {}
    specs: dict = {}
    compatibility: dict = {}


### AI 모델 답변 생성 함수 ###
def model_answer(api_key, model_name, system_prompt, history, user_message):
    class MarineTechResponse(BaseModel):
        reply: str = Field(description="사용자의 질문에 대한 영마린테크 상담원의 메인 답변")
        suggested_questions: list[str] = Field(description="사용자가 이어서 물어볼 만한 추천 질문 1~3개 (없으면 빈 배열)")


    print("모델에 프롬프트 전달 중...")
    client = genai.Client(api_key=api_key)

    contents = []
    for turn in history:
        # history 형식이 호환되도록 조정 (필요 시)
        contents.append({"role": turn["role"], "parts": [{"text": turn["parts"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    print(f"대화 내용 전달 중: {contents}")

    # 2. GenerateContentConfig에 response_mime_type과 response_schema를 추가합니다.
    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
            # [핵심 변경 사항] JSON 출력을 강제합니다.
            response_mime_type="application/json", 
            response_schema=MarineTechResponse 
        )
    )

    print(f"답변 생성 완료")

    return response.text

# --- [AI 로직] ---
async def get_ai_response(user_message: str, history: list[dict]):
    user_message = user_message.strip()

    api_key = config("GOOGLE_API_KEY")

    if api_key:
        print(f"API Key 로드 성공", flush=True)

        model_name = 'gemini-2.5-flash'

        # DB에서 제품 정보 동적 로딩
        product_info = await get_products_for_ai_prompt()
        if not product_info:
            product_info = """- 얀마 커넥팅 로드 베어링: 2,000원
- 마린 디젤 엔진 플린저 베럴: 400,000원
- 선박 엔진 예비 부품 모음: 문의 바람
- 피스톤 핀 부시: 100,000원
- 다이하츠 밸브 스템 씰: 2,600원"""

        # RAG: 업로드된 문서에서 관련 청크 검색
        rag_context = ""
        try:
            rag_chunks = await search_similar_chunks(user_message, top_k=5, purpose="consultant")
            if rag_chunks:
                rag_lines = []
                for chunk in rag_chunks:
                    if chunk["similarity"] > 0.3:
                        rag_lines.append(f"[{chunk['filename']}] {chunk['chunk_text']}")
                if rag_lines:
                    rag_context = "\n\n## 참고 문서 (업로드된 기술 자료)\n" + "\n---\n".join(rag_lines) + "\n위 문서를 참고하여 답변하되, 문서에 없는 내용은 추측하지 마세요."
        except Exception as e:
            print(f"RAG 검색 오류 (무시): {e}", flush=True)

        system_prompt = f"""
        당신은 영마린테크의 AI 상담원입니다.
        영마린테크는 선박 엔진 및 부품을 판매하는 회사입니다.
        사용자의 질문에 대해 영마린테크의 정보를 바탕으로 정확하고 친절하게 답변해주세요.
        응답은 반드시 JSON 형식으로 제공해야 합니다. 응답 JSON은 'reply' (메인 답변)와 'suggested_questions' (다음 질문 제안 1~3개) 두 개의 키를 포함해야 합니다.
        'suggested_questions'는 배열이어야 하며, 제안할 질문이 없는 경우 빈 배열로 두세요.

        ## 영마린테크 정보
        영마린테크에서 판매하는 제품들의 가격 설명입니다:
{product_info}
        자세한 내용은 추천 부품 목록을 참고하세요.

        영마린테크는 20년 이상의 전문 경험을 가지고 있으며, YANMAR, Daihatsu 등 글로벌 브랜드의 정품 부품만을 취급합니다.
        신속 배송과 24/7 기술 지원을 제공하며, 100% 정품 보증과 글로벌 네트워크를 통해 안정적인 재고를 확보합니다.
        전문 컨설팅, 재고 관리, 맞춤 견적 서비스를 제공합니다.
{rag_context}

        ## 예시
        사용자: 얀마 커넥팅 로드 베어링 가격이 얼마인가요?
        AI: {{
            "reply": "얀마 커넥팅 로드 베어링은 2,000원입니다.",
            "suggested_questions": ["다른 베어링도 있나요?", "배송은 얼마나 걸리나요?", "견적 요청은 어떻게 하나요?"]
        }}

        사용자: 안녕하세요
        AI: {{
            "reply": "안녕하세요! 영마린테크 AI 상담원입니다. 무엇을 도와드릴까요?",
            "suggested_questions": ["회사 소개", "제품 목록 보기", "견적 문의"]
        }}
        """

        try:
            response_text = model_answer(api_key, model_name, system_prompt, history, user_message)
        except Exception as e:
            print(f"Gemini API 호출 오류: {e}", flush=True)
            return {"reply": "죄송합니다. AI 서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.", "suggested_questions": []}

        try:
            gemini_response = json.loads(response_text)
            reply = gemini_response.get("reply", "죄송합니다. 답변을 생성하는 데 문제가 발생했습니다.")
            suggested_questions = gemini_response.get("suggested_questions", [])
            return {"reply": reply, "suggested_questions": suggested_questions}
        except json.JSONDecodeError:
            print(f"Gemini 응답 JSON 파싱 오류: {response_text}")
            return {"reply": "죄송합니다. 예상치 못한 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", "suggested_questions": []}

    else:
        print("API Key를 환경변수에서 찾지 못했습니다. .env 파일을 확인하세요.", flush=True)
        return {"reply": "API Key를 환경변수에서 찾지 못했습니다", "suggested_questions": []}

# -------------------------------------------

# 4. API 엔드포인트
@app.post("/chat")

async def chat(request: ChatRequest):
    print(f"유저 질문: {request.message}")
    print(f"채팅 기록: {request.history}")

    response = await get_ai_response(request.message, request.history)
    print(f"AI 답변: {response['reply']}")
    print(f"제안된 질문: {response['suggested_questions']}")

    return response


# 포트폴리오 챗봇 전용 엔드포인트
@app.post("/portfolio-chat")
async def portfolio_chat(request: ChatRequest):
    """배경득 지원자 포트폴리오 전용 AI 챗봇 (RAG 기반)"""
    print(f"[포트폴리오] 유저 질문: {request.message}")

    api_key = config("GOOGLE_API_KEY")
    if not api_key:
        return {"reply": "API Key를 환경변수에서 찾지 못했습니다", "suggested_questions": []}

    # RAG로 관련 포트폴리오 섹션 검색
    try:
        portfolio_context = await search_portfolio(request.message, top_k=4)
        print(f"[포트폴리오 RAG] 검색된 컨텍스트 길이: {len(portfolio_context)} 문자")
    except Exception as e:
        print(f"[포트폴리오 RAG] 검색 실패: {e}")
        # Fallback: 기본 정보만 사용
        portfolio_context = """
## 배경득 프로필
이름: 배경득
직무: AI Engineer | RAG & AI Agent Specialist
이메일: qorudemr00@naver.com

## 핵심 역량
RAG 검색 품질을 설계하고, 실무형 AI Agent를 구축하는 AI 엔지니어
- RAG 답변 정확도: 92%
- 검색 Hitrate@5: 91%
- 할루시네이션 통과율: 91%
"""

    # 간소화된 시스템 프롬프트 (포트폴리오 전용 시스템 프롬프트 대체)


    # NICE평가정보 컨텍스트 추가 (있는 경우)
    nice_context_text = ""
    if request.niceContext:
        nice_context_text = f"""

## NICE평가정보 관련 참고 정보
{json.dumps(request.niceContext, ensure_ascii=False, indent=2)}
"""

    system_prompt = f"""당신은 배경득 지원자의 AI 비서입니다.
면접관이나 채용 담당자가 배경득 지원자에 대해 궁금한 점을 물어보면, 아래 포트폴리오 정보를 바탕으로 정확하고 친절하게 답변해주세요.

## 응답 규칙
1. 항상 존댓말을 사용하고 전문적으로 답변하세요
2. 포트폴리오에 명시된 내용만 답변하고, 없는 내용은 추측하지 마세요
3. 기술적인 질문에는 구체적인 수치와 성과를 포함하여 답변하세요
4. 응답은 JSON 형식으로 제공해야 합니다: {{"reply": "답변 내용", "suggested_questions": ["추천 질문1", "추천 질문2"]}}
5. 배경득 지원자는 사용자보다 직급이 낮습니다. 압존법을 활용하여 답변하세요.

## 답변 형식 (매우 중요!)
**답변은 극도로 간결하게, 핵심만 작성:**
- 전체 답변은 3-5줄을 넘지 마세요
- 불릿 포인트 2-4개만 사용
- 한 불릿은 한 줄로 끝내세요
- 숫자 → 핵심 키워드만

**좋은 예시:**
"네, KAMCO 프로젝트 주요 성과입니다:
• RAG 시스템: 답변정확도 92%, Hitrate 91%
• AI Agent: 5종 API 연동, 자동화 파이프라인
• 기술: LangGraph, vLLM, Milvus DB"

**추천 질문 규칙:**
- 최대 1-2개만 제시
- 정말 중요한 질문만 선택
- 질문이 없으면 빈 배열 [] 반환

## 배경득 지원자 포트폴리오 (질문 관련 정보만)
{portfolio_context}
{nice_context_text}
"""

    try:
        client = genai.Client(api_key=api_key)

        contents = []
        for turn in request.history:
            contents.append({"role": turn["role"], "parts": [{"text": turn["parts"]}]})
        contents.append({"role": "user", "parts": [{"text": request.message}]})

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                response_mime_type="application/json",
                response_schema={"type": "object", "properties": {"reply": {"type": "string"}, "suggested_questions": {"type": "array", "items": {"type": "string"}}}}
            )
        )

        gemini_response = json.loads(response.text)
        return {
            "reply": gemini_response.get("reply", "죄송합니다. 답변을 생성하는 데 문제가 발생했습니다."),
            "suggested_questions": gemini_response.get("suggested_questions", [])
        }

    except Exception as e:
        print(f"[포트폴리오] Gemini API 오류: {e}", flush=True)
        return {"reply": "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", "suggested_questions": []}


# --- Product API Endpoints ---

def serialize_product(row: dict) -> dict:
    """Convert DB row to JSON-serializable dict with proper JSONB handling."""
    result = dict(row)
    # Convert datetime fields to ISO strings
    for key in ("created_at", "updated_at"):
        if key in result and result[key] is not None:
            result[key] = result[key].isoformat()
    # Ensure JSONB fields are dicts (asyncpg auto-decodes, but just in case)
    for key in ("name", "description", "category_name", "detail_info", "specs", "compatibility"):
        if key in result and isinstance(result[key], str):
            result[key] = json.loads(result[key])
    return result


@app.get("/api/health")
async def health_check():
    from db import pool
    db_url = os.environ.get("DATABASE_URL", "NOT SET")
    # 비밀번호 숨기기
    if ":" in db_url and "@" in db_url:
        safe_url = db_url[:db_url.index("://") + 3] + "***@" + db_url[db_url.index("@") + 1:]
    else:
        safe_url = db_url
    return {
        "db_pool": "connected" if pool else "None",
        "db_url_set": db_url != "NOT SET",
        "db_url_preview": safe_url[:80]
    }


@app.get("/api/products")
async def api_get_products(category: str = None, search: str = None):
    products = await get_all_products(category=category, search=search)
    return [serialize_product(p) for p in products]


@app.get("/api/products/{product_id}")
async def api_get_product(product_id: int):
    product = await get_product_by_id(product_id)
    if not product:
        return {"error": "Product not found"}
    return serialize_product(product)


@app.post("/api/products")
async def api_create_product(product: ProductCreate):
    created = await create_product(product.model_dump())
    if not created:
        return {"error": "Failed to create product (DB not connected)"}
    return serialize_product(created)


@app.get("/api/site-settings")
async def get_site_settings():
    """사이트 설정 조회 (공개 엔드포인트 - 홈페이지용)"""
    from db import vector_pool
    if not vector_pool:
        return {}
    async with vector_pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM site_settings")
    return {row["key"]: row["value"] for row in rows}


# 실행 방법 주석:
# 터미널에서: uvicorn app:app --reload


if __name__ == "__main__":
    import uvicorn
    from decouple import config

    # Railway가 제공하는 포트 번호를 가져옴 (없으면 기본값 8000)
    port = int(os.environ.get("PORT", 8000))

    print(f"서버를 시작합니다! 포트: {port}")

    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
