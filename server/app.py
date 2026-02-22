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

_scheduler_task = None


# Lifespan: DB init/close + Gmail 자동 체크 스케줄러
@asynccontextmanager
async def lifespan(app):
    global _scheduler_task
    await init_db()
    await init_vector_db()
    await cleanup_old_conversations()
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
    """배경득 지원자 포트폴리오 전용 AI 챗봇"""
    print(f"[포트폴리오] 유저 질문: {request.message}")

    api_key = config("GOOGLE_API_KEY")
    if not api_key:
        return {"reply": "API Key를 환경변수에서 찾지 못했습니다", "suggested_questions": []}

    # 포트폴리오 전용 시스템 프롬프트
    portfolio_content = """
## 배경득 (AI Engineer) 프로필

### 기본 정보
- 이름: 배경득
- 직무: AI Engineer | RAG & AI Agent Specialist
- 이메일: qorudemr00@naver.com
- 전화: 010-4056-2656
- 위치: 부산광역시 남구
- GitHub: github.com/badKD9802
- 홈페이지: badkd9802.github.io/Marine-components/docs/

### 핵심 역량
"RAG 검색 품질을 설계하고, 실무형 AI Agent를 구축하는 AI 엔지니어"

**주요 성과:**
- RAG 답변 정확도: 92%
- 검색 Hitrate@5: 91%
- 할루시네이션 통과율: 91%
- G-EVAL 품질 평가: 4.3/5.0

### 주요 프로젝트

#### 1. 한국자산관리공사(KAMCO) 그룹웨어 재구축 사업 - AI 도입 (2024.10 ~ 2026.01)
**역할:** 애자일소다 선임연구원 | 기여도 30%
**기술 스택:** Python, LangGraph, vLLM, Milvus DB, Oracle/MariaDB, H100/H200 GPU

**핵심 성과:**
1. **대규모 문서 기반 RAG 시스템 구축**
   - 1,000만건 규모의 내부 문서 처리
   - Context-Aware RAG Pipeline: OCR에서 검색까지 전 과정 설계
   - 메타데이터 활용으로 검색 성능 향상
   - Chunk 컨텍스트 보강: LLM으로 '요약'과 '예상 질문' 생성
   - 하이브리드 검색 + Reranking: Sparse(키워드) + Dense(의미) 결합
   - 청크 검증 로직으로 답변 가능 여부 검증
   - **성과:** 답변 정확도 92%, Hitrate@5 91%, 할루시네이션 통과율 91%

2. **LangGraph 기반 업무 자동화 AI Agent**
   - 자연어 요청 → 의도 파악 → API 실행 → 결과 응답의 End-to-End 파이프라인
   - 5종 API 연동: 회의실 예약, 일정 관리, 임원 일정 조회, 결재 양식 호출 등
   - 파라미터 누락 시 역질문(Slot Filling), API 실패 시 원인 안내
   - 사용자 평가: "불편함 없고 매끄럽다"

3. **문서 요약 · 번역 · 초안 작성 서비스**
   - 문서 유형별 프롬프트: 보고서, 이메일, 규정 등 전용 템플릿 개발
   - 비동기 병렬 처리로 속도 2배 개선 (5페이지 17.5초 → 9페이지 12.3초)
   - 다국어 지원: 일본어, 영어 번역 및 회신문/보고서 초안 생성
   - G-EVAL 품질 평가: 4.3/5.0

#### 2. 영마린테크 - 해양 엔진 부품 B2B 쇼핑몰 (2025.11 ~ 2026.02, 개인 프로젝트 100%)
**실전 배포된 Full-Stack B2B 전자상거래 플랫폼**
- 배포: Railway CI/CD (자동 배포)
- 백엔드 API: https://marine-parts-production-60a3.up.railway.app
- 관리자 페이지: https://adminmarine-component-production.up.railway.app
- 고객용 홈페이지: https://marine-componentsweb-production.up.railway.app
- GitHub: https://github.com/badKD9802/Marine-components

**기술 스택:**
Python, FastAPI, PostgreSQL, pgvector, RAG, Gemini-2.5-Flash, OpenAI Embedding, React, Railway CI/CD, 다국어(KO/EN/CN)

**1. 시스템 아키텍처 - Full-Stack 구현**
6개 레이어로 구성된 완전한 웹 서비스:
- Layer 1 (고객 페이지): HTML5, Vanilla JavaScript, 다국어 지원, SEO 최적화
- Layer 2 (관리자 페이지): React 18 SPA, JWT 인증, 제품/문서/메일 통합 관리
- Layer 3 (FastAPI 서버): 비동기 처리(asyncpg), Lifespan 이벤트, 35개 이상 RESTful API
- Layer 4 (PostgreSQL): JSONB 다국어 스키마 (name, description, specs 모두 {ko,en,cn} 구조)
- Layer 5 (pgvector): 벡터 검색 엔진, OpenAI text-embedding-3-small (1536차원), 코사인 유사도
- Layer 6 (AI APIs): Gemini 2.5 Flash (챗봇), GPT-4o-mini (번역), OpenAI Embedding (RAG)

**2. RAG 파이프라인 - 문서 기반 AI 상담**
PDF 카탈로그 업로드 → PyPDF2 텍스트 추출 → RecursiveCharacterTextSplitter 청킹(1000자, overlap 200)
→ OpenAI Embedding 벡터화 → pgvector 저장 → 유사도 검색(Top-3) → Gemini 답변 생성

핵심 기능:
- Structured Output: Gemini API에 JSON 스키마 강제 (reply + suggested_questions)
- 대화 이력 관리: DB conversation 테이블로 세션별 메시지 저장, 1주일 후 자동 정리
- Fallback 처리: RAG 검색 실패 시 DB 제품 정보로 대체

**3. 다국어 JSONB 스키마 설계**
- JSONB 컬럼: name, description, specs, compatibility를 {ko, en, cn} 구조로 저장
- 정규화 없이 유연성 확보: 언어 추가 시 컬럼 수정 불필요
- API 응답 최적화: FastAPI에서 언어 파라미터 받아 해당 언어만 추출
- 성과: 3개 언어 지원, 100% 자동 번역, 0건 수동 작업

**4. FastAPI 명세서 (8개 카테고리, 35개 이상 엔드포인트)**
- 공개 API (4개): POST /chat (챗봇), GET /api/products (제품 목록/상세), GET /api/health
- 관리자 인증 (1개): POST /admin/login (JWT 토큰 발급)
- 제품 관리 (5개): GET/POST/PUT/DELETE /admin/products, POST /admin/translate (자동 번역)
- 문서 관리/RAG (5개): PDF 업로드, 문서 CRUD, 청크 수정
- RAG 채팅 (5개): POST /rag/chat (RAG 기반), POST /rag/chat/stream (SSE 스트리밍), Conversations CRUD
- 메일 작성 (4개): AI 메일 작성, 번역, 이력 조회, 초안 저장
- 문의 관리 (3개): 고객 문의 등록(공개), 관리자 문의 관리, 답변 발송
- 설정 관리 (3개): 사이트 설정 조회/수정, 대시보드 통계

**비즈니스 임팩트:**
- 70% 고객 응대 시간 단축 (RAG 기반 카탈로그 검색)
- 24/7 무인 고객 대응 가능 (3개 국가 대상 다국어 자동화)

**기술적 하이라이트:**
- Railway CI/CD: git push 시 자동 빌드/배포, PostgreSQL 플러그인 자동 연동
- 비동기 처리: asyncpg로 DB 커넥션 풀 관리, 모든 API 엔드포인트 async/await 패턴
- CORS 및 보안: 환경변수 관리(.env), JWT 기반 관리자 인증, HTTPS 통신
- 에러 핸들링: try-except로 Fallback 처리, API 실패 시 사용자 친화적 메시지

#### 3. KMI 지정학적 이슈 영향 분석 (2024.05 ~ 2024.07)
- 한국해양수산개발원 북극항로지원단
- 한국-북유럽 항로의 물동량/운임/운송일수 데이터 수집
- OLS 회귀분석으로 코로나, 러-우전쟁, 홍해 사태의 영향 분석
- Python, OLS 회귀분석, 데이터 시각화

#### 4. NLP 논문 - SMOTE 기법 연구 (2024.01 ~ 2024.07, 석사 논문)
- 스팀게임리뷰 불균형 텍스트 분류 성능 평가
- SMOTE/B-SMOTE/ADASYN 3가지 기법 비교 및 클래스 비율 최적화 연구
- NLP, SMOTE, 나이브 베이즈

#### 5. CIFAR-10 이미지 분류 (2022.10 ~ 2022.11, 3팀 중 1등)
- PyTorch로 VGG16/ResNet50/EfficientNet 개발
- 앙상블 기법으로 ACC 0.8096 달성 (1등)
- 4인 팀 프로젝트

#### 6. IMDB 텍스트 분류 모델 (2022.10 ~ 2022.11)
- TensorFlow로 RNN/LSTM/BiLSTM 모델 구현
- 다중 레이어 조합으로 최고 ACC 0.8861 달성
- 개인 프로젝트

### 기술 스택

**AI / ML Framework:**
- LangGraph, LangChain, vLLM, OpenAI API, AsyncOpenAI
- PyTorch, TensorFlow

**Database:**
- Milvus DB, Oracle DB, MariaDB

**Language & Tools:**
- Python, JavaScript, HTML/CSS, Selenium

**Infrastructure:**
- H100 GPU (8장), H200 GPU (8장), gpt-oss-120b

### 경력 및 학력

**애자일소다 (2024.10 ~ 현재)**
- 선임연구원, DS팀 (정규직)
- RAG 및 AI Agent 개발 담당
- 한국자산관리공사 그룹웨어 AI 도입 프로젝트 주도

**한국해양수산개발원(KMI) (2024.05 ~ 2024.07)**
- 북극항로지원단
- 지정학적 이슈가 항만 물동량에 미치는 영향 분석
- 데이터 수집/전처리/통계 모델링

**부산대학교 대학원 (2022.09 ~ 2024.08)**
- 통계학과 석사 졸업 | GPA 4.19/4.5
- 자연어처리, 이미지 분류, 불균형 데이터 처리 등 AI/ML 연구
- 석사 논문 작성

**부산대학교 (2017.03 ~ 2022.08)**
- 통계학과 학사 졸업 | GPA 3.67/4.5
- 통계학 이론 및 데이터 분석
- Python 기반 모델링 학습

### 자격증 및 어학

**빅데이터분석기사** (2023.12 취득)
- 한국데이터산업진흥원장 발급

**TOEIC Speaking** (2024.09)
- Intermediate High
- 영어 회화 능력 검증

---

## NICE평가정보 회사 소개 및 AI 사업 현황

### 회사 개요
**NICE평가정보**는 1985년 재무센터로 시작하여 40년 가까운 역사를 가진 대한민국 1위 신용정보 및 평가 기업입니다.

**기업 규모:**
- 임직원: 약 700명 이상
- 본사: 서울특별시
- 계열사: NICE지니데이타, NICE신용평가, NICE그룹 등

**시장 위치:**
- 대한민국 신용정보 시장 점유율 1위
- 40년간 축적된 신용 데이터와 평가 노하우 보유
- 금융권 및 공공기관 대상 안정적 비즈니스 모델

### 주요 사업 분야

**1. 신용정보 서비스 (매출 구성)**
- **개인 신용정보(CB: Credit Bureau)**: 매출의 65%
  - 개인 신용등급 평가 및 관리
  - 신용조회 서비스
  - 신용점수 산출 및 제공

- **기업 신용정보(기업 CB)**: 매출의 20%
  - 기업 신용평가 및 등급 산정
  - 재무 정보 분석
  - 기업 리스크 평가

- **빅데이터 및 채권추심**: 매출의 15%
  - 빅데이터 분석 및 인사이트 제공
  - 채권 관리 및 추심 서비스

**2. 마이데이터(MyData) 서비스**
- 2021년 신용정보관리업 허가 획득, 마이데이터 사업 진출
- 개인의 분산된 금융정보를 한 곳에 모아 유용한 서비스로 제공
- 금융 상품 추천, 자산 관리, 신용 개선 조언 등

**3. 광고 및 마케팅 인프라**
- 데이터 기반 타겟 마케팅 솔루션
- 금융 상품 광고 플랫폼

### 현재 진행 중인 AI 사업 및 기술

**1. AI 기반 신용평가 모델 개발**
- **한국 최초 머신러닝 신용평가 모델 솔루션** 개발
- ML/AI 기반 기업 신용 의사결정 모델 구축
- 전통적 신용평가 방식을 AI로 고도화하여 정확도 및 효율성 향상

**2. 비대면 여신심사 자동화 시스템**
- **AI/비대면 여신심사 및 의사결정 지원 솔루션** 운영
- 사업자 전용 신용평가 서비스 출시
- 신청서 자동 분석, 리스크 평가, 승인/거부 의사결정 자동화

**3. 빅데이터 분석 및 예측 모델**
- **NICE지니데이타** 계열사를 통한 데이터 분석 사업
- 전국 320만 점포 데이터 기반 상권 분석 및 예측 모델 개발
- 고객 행동 패턴 분석 및 상권 변화 예측

**4. AI 솔루션 개발 조직 운영**
- IT 부서 내 **AI 솔루션 개발팀** 운영
- AI/ML 전문 인력 채용 및 육성
- 최신 AI 기술 도입 및 연구개발 지속 투자

### NICE평가정보의 기술 스택 및 방향성

**현재 사용 중인 기술:**
- **백엔드**: Spring Framework, Python
- **인프라**: Container 기술, Serverless 기술
- **AI/ML**: 머신러닝 모델 개발, 빅데이터 처리
- **데이터베이스**: 대규모 신용정보 DB 관리

**AI 기술 방향성:**
- 데이터 기반 의사결정 구현
- 실시간 신용평가 및 리스크 모니터링
- 자연어 처리 기반 문서 자동화
- 예측 모델 고도화 (신용등급, 연체율, 부도 확률 등)

### NICE평가정보의 AI 비전

**목표:**
데이터와 AI 기술을 활용한 신용평가 및 의사결정 지원 분야의 글로벌 리더

**핵심 전략:**
1. 40년간 축적된 신용 데이터 + 최신 AI 기술 결합
2. 마이데이터 시장 선도 기업으로서 AI 기반 개인화 서비스 확대
3. 비대면 금융 시대에 대응하는 자동화 솔루션 강화
4. 금융권 및 공공기관 대상 신뢰성 높은 AI 솔루션 제공

### 채용 중인 AI 관련 직무 (2026년 상반기)

**AI 솔루션 개발 (IT 부서)**
- AI/ML 모델 개발 및 고도화
- 신용평가 자동화 시스템 구축
- 대규모 데이터 처리 및 분석
- Python, Spring 기반 백엔드 개발
- 클라우드 및 컨테이너 환경 시스템 운영

**기타 IT 직무:**
- Full Stack Developer (인증서비스)
- 솔루션 개발
- 모바일앱 개발
- 데이터 분석
- 신용평가 모델 개발

**주의사항:** 현재 진행 중인 NICE평가정보 정규직 채용 공고 중 하나의 직무만 지원 가능 (중복지원 불가)
"""

    # NICE평가정보 컨텍스트 추가 (있는 경우)
    nice_context_text = ""
    if request.niceContext:
        nice_context_text = f"""

## NICE평가정보 관련 참고 정보
아래 정보를 참조하여 배경득 지원자가 NICE평가정보에서 어떤 기여를 할 수 있는지 구체적으로 답변하세요.

{json.dumps(request.niceContext, ensure_ascii=False, indent=2)}

**답변 시 주의사항:**
- NICE평가정보의 사업 분야와 배경득의 경험을 매칭하여 설명하세요
- 구체적인 프로젝트 예시와 기대 효과를 제시하세요
- 배경득의 정량적 성과(92% 정확도 등)를 NICE에서 어떻게 활용할 수 있는지 연결하세요
"""

    system_prompt = f"""당신은 배경득 지원자의 AI 비서입니다.
면접관이나 채용 담당자가 배경득 지원자에 대해 궁금한 점을 물어보면, 아래 포트폴리오 정보를 바탕으로 정확하고 친절하게 답변해주세요.

## 응답 규칙
1. 항상 존댓말을 사용하고 전문적으로 답변하세요
2. 포트폴리오에 명시된 내용만 답변하고, 없는 내용은 추측하지 마세요
3. 기술적인 질문에는 구체적인 수치와 성과를 포함하여 답변하세요
4. 프로젝트 관련 질문에는 역할, 기여도, 사용 기술, 성과를 명확히 설명하세요
5. 응답은 JSON 형식으로 제공해야 합니다: {{"reply": "답변 내용", "suggested_questions": ["추천 질문1", "추천 질문2"]}}
6. 배경득 지원자는 사용자보다 직급이 낮습니다. 압존법을 활용하여 사용자보다 낮은 직급에 대한 소개를 하듯이 답변하세요.

## 답변 형식 (매우 중요!)
**답변은 극도로 간결하게, 핵심만 작성:**
- 전체 답변은 3-5줄을 넘지 마세요
- 불릿 포인트 2-4개만 사용 (그 이상 금지)
- 한 불릿은 한 줄로 끝내세요
- 숫자 → 핵심 키워드만 (설명 최소화)
- 배경 설명, 부연 설명 모두 제거

**좋은 예시 (이것처럼!):**
"네, KAMCO 프로젝트 주요 성과입니다:
• RAG 시스템: 답변정확도 92%, Hitrate 91%
• AI Agent: 5종 API 연동, 자동화 파이프라인 구축
• 기술: LangGraph, vLLM, Milvus DB"

**나쁜 예시 (절대 금지):**
"배경득 지원자는 한국자산관리공사 프로젝트에서 대규모 문서 기반 RAG 시스템을 구축하였으며..."

**추천 질문 규칙:**
- 최대 1-2개만 제시 (3개 이상 금지)
- 정말 중요한 질문만 선택
- 질문이 없으면 빈 배열 [] 반환

## NICE평가정보 관련 질문 응답 (극도로 간결하게!)

**회사 소개 질문**
3줄로 끝내기:
• 1985년 설립, 국내 1위 신용정보 (매출: 개인CB 65%)
• AI 사업: 신용평가 모델, 여신심사 자동화
• 700명 규모, 마이데이터 선도 기업

**기여 방안 질문**
2-3개 핵심만:
• KAMCO RAG 경험 → NICE 신용평가 데이터 처리
• 92% 정확도 기술 → 여신심사 자동화
• AI Agent 개발 → 의사결정 시스템 구축

**절대 하지 말 것:**
- 장황한 배경 설명
- "~을 통해", "~함으로써" 같은 긴 표현
- 5줄 이상 답변

## 배경득 지원자 포트폴리오
{portfolio_content}{nice_context_text}

## 추천 질문 가이드
**중요:** 추천 질문은 최대 1-2개만! 정말 중요한 것만 선택
- 이미 답변한 내용과 관련된 질문만
- 너무 일반적이거나 뻔한 질문은 제외
- 질문이 적절치 않으면 빈 배열 [] 반환

**질문 예시 (참고용, 모두 제시하지 말 것):**
- "RAG 92% 정확도 달성 방법은?"
- "AI Agent 핵심 기능은?"
- "NICE 기여 방안은?"
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
