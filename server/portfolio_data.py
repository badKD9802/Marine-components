"""
포트폴리오 RAG용 데이터
섹션별로 나눠서 필요한 부분만 검색할 수 있도록 구조화
"""

import pandas as pd

# 포트폴리오 섹션별 데이터
PORTFOLIO_SECTIONS = [
    {
        "category": "기본정보",
        "title": "배경득 프로필",
        "content": """이름: 배경득
직무: AI Engineer | RAG & AI Agent Specialist
이메일: qorudemr00@naver.com
전화: 010-4056-2656
위치: 부산광역시 남구
GitHub: github.com/badKD9802
홈페이지: marine-componentsweb-production.up.railway.app"""
    },
    {
        "category": "핵심역량",
        "title": "핵심 역량 및 주요 성과",
        "content": """RAG 검색 품질을 설계하고, 실무형 AI Agent를 구축하는 AI 엔지니어

주요 성과:
- RAG 답변 정확도: 92%
- 검색 Hitrate@5: 91%
- 할루시네이션 통과율: 91%
- G-EVAL 품질 평가: 4.3/5.0"""
    },
    {
        "category": "프로젝트",
        "title": "KAMCO 그룹웨어 - RAG 시스템",
        "content": """한국자산관리공사(KAMCO) 그룹웨어 재구축 사업 - AI 도입 (2024.10 ~ 2026.01)
역할: 애자일소다 선임연구원 | 기여도 30%
기술 스택: Python, LangGraph, vLLM, Milvus DB, Oracle/MariaDB, H100/H200 GPU

대규모 문서 기반 RAG 시스템 구축:
- 1,000만건 규모의 내부 문서 처리
- Context-Aware RAG Pipeline: OCR에서 검색까지 전 과정 설계
- 메타데이터 활용으로 검색 성능 향상
- Chunk 컨텍스트 보강: LLM으로 '요약'과 '예상 질문' 생성
- 하이브리드 검색 + Reranking: Sparse(키워드) + Dense(의미) 결합
- 청크 검증 로직으로 답변 가능 여부 검증
- 성과: 답변 정확도 92%, Hitrate@5 91%, 할루시네이션 통과율 91%"""
    },
    {
        "category": "프로젝트",
        "title": "KAMCO 그룹웨어 - AI Agent",
        "content": """LangGraph 기반 업무 자동화 AI Agent:
- 자연어 요청 → 의도 파악 → API 실행 → 결과 응답의 End-to-End 파이프라인
- 5종 API 연동: 회의실 예약, 일정 관리, 임원 일정 조회, 결재 양식 호출 등
- 파라미터 누락 시 역질문(Slot Filling), API 실패 시 원인 안내
- 사용자 평가: "불편함 없고 매끄럽다" """
    },
    {
        "category": "프로젝트",
        "title": "KAMCO 그룹웨어 - 문서 요약/번역",
        "content": """문서 요약 · 번역 · 초안 작성 서비스:
- 문서 유형별 프롬프트: 보고서, 이메일, 규정 등 전용 템플릿 개발
- 비동기 병렬 처리로 속도 2배 개선 (5페이지 17.5초 → 9페이지 12.3초)
- 다국어 지원: 일본어, 영어 번역 및 회신문/보고서 초안 생성
- G-EVAL 품질 평가: 4.3/5.0"""
    },
    {
        "category": "프로젝트",
        "title": "영마린테크 - B2B 쇼핑몰 개요",
        "content": """영마린테크 - 해양 엔진 부품 B2B 쇼핑몰 (2025.11 ~ 2026.02, 개인 프로젝트 100%)
실전 배포된 Full-Stack B2B 전자상거래 플랫폼

배포: Railway CI/CD (자동 배포)
백엔드 API: https://marine-parts-production-60a3.up.railway.app
관리자 페이지: https://adminmarine-component-production.up.railway.app
고객용 홈페이지: https://marine-componentsweb-production.up.railway.app
GitHub: https://github.com/badKD9802/Marine-components

기술 스택: Python, FastAPI, PostgreSQL, pgvector, RAG, Gemini-2.5-Flash, OpenAI Embedding, React, Railway CI/CD, 다국어(KO/EN/CN)"""
    },
    {
        "category": "프로젝트",
        "title": "영마린테크 - 시스템 아키텍처",
        "content": """시스템 아키텍처 - Full-Stack 구현
6개 레이어로 구성된 완전한 웹 서비스:

Layer 1 (고객 페이지): HTML5, Vanilla JavaScript, 다국어 지원, SEO 최적화
Layer 2 (관리자 페이지): React 18 SPA, JWT 인증, 제품/문서/메일 통합 관리
Layer 3 (FastAPI 서버): 비동기 처리(asyncpg), Lifespan 이벤트, 35개 이상 RESTful API
Layer 4 (PostgreSQL): JSONB 다국어 스키마 (name, description, specs 모두 {ko,en,cn} 구조)
Layer 5 (pgvector): 벡터 검색 엔진, OpenAI text-embedding-3-small (1536차원), 코사인 유사도
Layer 6 (AI APIs): Gemini 2.5 Flash (챗봇), GPT-4o-mini (번역), OpenAI Embedding (RAG)"""
    },
    {
        "category": "프로젝트",
        "title": "영마린테크 - RAG 파이프라인",
        "content": """RAG 파이프라인 - 문서 기반 AI 상담:
PDF 카탈로그 업로드 → PyPDF2 텍스트 추출 → RecursiveCharacterTextSplitter 청킹(1000자, overlap 200)
→ OpenAI Embedding 벡터화 → pgvector 저장 → 유사도 검색(Top-3) → Gemini 답변 생성

핵심 기능:
- Structured Output: Gemini API에 JSON 스키마 강제 (reply + suggested_questions)
- 대화 이력 관리: DB conversation 테이블로 세션별 메시지 저장, 1주일 후 자동 정리
- Fallback 처리: RAG 검색 실패 시 DB 제품 정보로 대체"""
    },
    {
        "category": "프로젝트",
        "title": "영마린테크 - 다국어 JSONB",
        "content": """다국어 JSONB 스키마 설계:
- JSONB 컬럼: name, description, specs, compatibility를 {ko, en, cn} 구조로 저장
- 정규화 없이 유연성 확보: 언어 추가 시 컬럼 수정 불필요
- API 응답 최적화: FastAPI에서 언어 파라미터 받아 해당 언어만 추출"""
    },
    {
        "category": "프로젝트",
        "title": "영마린테크 - FastAPI 명세",
        "content": """FastAPI 명세서 (8개 카테고리, 35개 이상 엔드포인트):
- 공개 API (4개): POST /chat (챗봇), GET /api/products (제품 목록/상세), GET /api/health
- 관리자 인증 (1개): POST /admin/login (JWT 토큰 발급)
- 제품 관리 (5개): GET/POST/PUT/DELETE /admin/products, POST /admin/translate (자동 번역)
- 문서 관리/RAG (5개): PDF 업로드, 문서 CRUD, 청크 수정
- RAG 채팅 (5개): POST /rag/chat (RAG 기반), POST /rag/chat/stream (SSE 스트리밍), Conversations CRUD
- 메일 작성 (4개): AI 메일 작성, 번역, 이력 조회, 초안 저장
- 문의 관리 (3개): 고객 문의 등록(공개), 관리자 문의 관리, 답변 발송
- 설정 관리 (3개): 사이트 설정 조회/수정, 대시보드 통계

비즈니스 임팩트:
- 70% 고객 응대 시간 단축 (RAG 기반 카탈로그 검색)
- 24/7 무인 고객 대응 가능 (3개 국가 대상 다국어 자동화)"""
    },
    {
        "category": "프로젝트",
        "title": "기타 프로젝트",
        "content": """KMI 지정학적 이슈 영향 분석 (2024.05 ~ 2024.07)
- 한국해양수산개발원 북극항로지원단
- 한국-북유럽 항로의 물동량/운임/운송일수 데이터 수집
- OLS 회귀분석으로 코로나, 러-우전쟁, 홍해 사태의 영향 분석

NLP 논문 - SMOTE 기법 연구 (2024.01 ~ 2024.07, 석사 논문)
- 스팀게임리뷰 불균형 텍스트 분류 성능 평가
- SMOTE/B-SMOTE/ADASYN 3가지 기법 비교

CIFAR-10 이미지 분류 (2022.10 ~ 2022.11, 3팀 중 1등)
- PyTorch로 VGG16/ResNet50/EfficientNet 개발
- 앙상블 기법으로 ACC 0.8096 달성 (1등)

IMDB 텍스트 분류 모델 (2022.10 ~ 2022.11)
- TensorFlow로 RNN/LSTM/BiLSTM 모델 구현
- 다중 레이어 조합으로 최고 ACC 0.8861 달성"""
    },
    {
        "category": "기술스택",
        "title": "기술 스택",
        "content": """AI / ML Framework:
- LangGraph, LangChain, vLLM, OpenAI API, AsyncOpenAI
- PyTorch, TensorFlow

Database:
- Milvus DB, Oracle DB, MariaDB, PostgreSQL, pgvector

Language & Tools:
- Python, JavaScript, HTML/CSS, Selenium, React, FastAPI

Infrastructure:
- H100 GPU (8장), H200 GPU (8장), gpt-oss-120b
- Railway CI/CD"""
    },
    {
        "category": "경력학력",
        "title": "경력 및 학력",
        "content": """애자일소다 (2024.10 ~ 현재)
- 선임연구원, DS팀 (정규직)
- RAG 및 AI Agent 개발 담당
- 한국자산관리공사 그룹웨어 AI 도입 프로젝트 주도

한국해양수산개발원(KMI) (2024.05 ~ 2024.07)
- 북극항로지원단
- 지정학적 이슈가 항만 물동량에 미치는 영향 분석

부산대학교 대학원 (2022.09 ~ 2024.08)
- 통계학과 석사 졸업 | GPA 4.19/4.5
- 자연어처리, 이미지 분류, 불균형 데이터 처리 등 AI/ML 연구

부산대학교 (2017.03 ~ 2022.08)
- 통계학과 학사 졸업 | GPA 3.67/4.5"""
    },
    {
        "category": "자격증",
        "title": "자격증 및 어학",
        "content": """빅데이터분석기사 (2023.12 취득)
- 한국데이터산업진흥원장 발급

TOEIC Speaking (2024.09)
- Intermediate High
- 영어 회화 능력 검증"""
    },
    {
        "category": "NICE",
        "title": "NICE평가정보 회사 개요",
        "content": """NICE평가정보는 1985년 재무센터로 시작하여 40년 가까운 역사를 가진 대한민국 1위 신용정보 및 평가 기업입니다.

기업 규모:
- 임직원: 약 700명 이상
- 본사: 서울특별시
- 시장 위치: 대한민국 신용정보 시장 점유율 1위

주요 사업 분야:
- 개인 신용정보(CB): 매출의 65%
- 기업 신용정보: 매출의 20%
- 빅데이터 및 채권추심: 매출의 15%
- 마이데이터 서비스 (2021년 허가 획득)"""
    },
    {
        "category": "NICE",
        "title": "NICE평가정보 AI 사업",
        "content": """현재 진행 중인 AI 사업 및 기술:

1. AI 기반 신용평가 모델 개발
   - 한국 최초 머신러닝 신용평가 모델 솔루션 개발
   - ML/AI 기반 기업 신용 의사결정 모델 구축

2. 비대면 여신심사 자동화 시스템
   - AI/비대면 여신심사 및 의사결정 지원 솔루션 운영
   - 사업자 전용 신용평가 서비스 출시

3. 빅데이터 분석 및 예측 모델
   - 전국 320만 점포 데이터 기반 상권 분석
   - 고객 행동 패턴 분석 및 상권 변화 예측

4. AI 솔루션 개발 조직 운영
   - IT 부서 내 AI 솔루션 개발팀 운영
   - AI/ML 전문 인력 채용 및 육성

기술 스택:
- 백엔드: Spring Framework, Python
- 인프라: Container, Serverless
- AI/ML: 머신러닝 모델 개발, 빅데이터 처리"""
    },
    {
        "category": "NICE",
        "title": "NICE에서의 기여 방안",
        "content": """배경득이 NICE평가정보에서 기여할 수 있는 분야:

1. AI 기반 신용평가 모델 개발 및 고도화
   - KAMCO에서 RAG 시스템 구축 시 1,000만건 문서 처리 경험
   - 92% 답변 정확도 달성 기술을 NICE 신용평가 데이터 처리에 적용

2. 비대면 여신심사 자동화 시스템 구축
   - LangGraph 기반 AI Agent 개발 경험
   - 문서 검색, 요약, 회신문 생성 자동화 구현 경험

3. 대규모 금융 데이터 기반 RAG 시스템 개발
   - 하이브리드 검색, BGE 리랭킹, LLM 청크 검증 등 고도화된 RAG 파이프라인 설계
   - Hitrate@5 91%, 할루시네이션 통과율 91% 달성

4. 마이데이터 서비스 고도화
   - Context 보강으로 검색 재현율 18%p 향상
   - vLLM으로 실시간 LLM 추론 최적화

5. 신용평가 모델 성능 모니터링 및 지속 개선
   - 멀티 쿼리 생성, 동의어 확장, 키워드 부스팅 등 최적화 기법 적용 경험"""
    }
]

def get_portfolio_dataframe():
    """포트폴리오 데이터를 pandas DataFrame으로 반환"""
    df = pd.DataFrame(PORTFOLIO_SECTIONS)
    return df

def get_sections_by_category(category: str):
    """특정 카테고리의 섹션들만 반환"""
    return [section for section in PORTFOLIO_SECTIONS if section["category"] == category]
