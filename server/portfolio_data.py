"""
포트폴리오 RAG용 데이터
한화시스템 AI 서비스 직무 면접 대비 버전
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
- G-EVAL 품질 평가: 4.3/5.0

핵심 강점:
- SI 프로젝트 경험: 공공기관(한국자산관리공사)에 AI 서비스를 도입하는 SI형 프로젝트 수행
- 고객사 요구사항 분석 → 설계 → 개발 → 배포까지 End-to-End 경험
- ReAct Agent + Function Calling 기반 복합 업무 자동화 설계/구현
- Claude Code 등 최신 AI 도구를 활용한 개인 프로젝트 지속 수행"""
    },
    {
        "category": "프로젝트",
        "title": "KAMCO 그룹웨어 - RAG 시스템",
        "content": """한국자산관리공사(KAMCO) 그룹웨어 재구축 사업 - AI 도입 (2024.10 ~ 2026.01)
소속: 애자일소다 (SI 기업) → KAMCO에 파견되어 AI 서비스 개발
역할: 선임연구원 | 기여도 30%
기술 스택: Python, LangGraph, vLLM, Milvus DB, Oracle/MariaDB, H100/H200 GPU

SI 프로젝트로서의 특징:
- 고객사(KAMCO)의 요구사항을 분석하고, AI 서비스를 설계/개발/배포
- 기존 그룹웨어 시스템과의 연동 (Oracle DB, XML API, SLO 인증)
- 현업 담당자 인터뷰를 통한 업무 도구 요구사항 정의
- 주기적 검증 미팅을 통한 품질 확보

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
- 초기 LangGraph 분기형 구조의 한계를 분석하고 ReAct + OpenAI Function Calling 구조로 전면 재설계 제안/구현
- 기존 26개 서비스 파일(~12,700줄) → ReAct 구조(~6,000줄)로 코드량 53% 감소
- 37개 업무 도구 구현: 일정 관리, 회의실 예약, 직원 검색, 결재, 문서 초안 등
- 복합 요청 처리: "회의실 예약하고 참석자에게 메일 초안도 작성해줘" → LLM이 도구 조합 자동 결정
- SSE 스트리밍으로 도구 실행 진행 상황 실시간 전송
- 파라미터 누락 시 역질문(Slot Filling), API 실패 시 원인 안내
- ToolRegistry + AuthContext 패턴으로 인증 1회 캐싱, 전체 도구 공유
- 사용자 평가: "불편함 없고 매끄럽다" """
    },
    {
        "category": "프로젝트",
        "title": "KAMCO 그룹웨어 - 문서 요약/번역",
        "content": """문서 요약 · 번역 · 초안 작성 서비스:
- 문서 유형별 프롬프트: 보고서, 이메일, 규정 등 전용 템플릿 개발
- 비동기 병렬 처리로 속도 2배 개선 (5페이지 17.5초 → 9페이지 12.3초)
- Adaptive Batch Processing: vLLM GPU 부하에 따라 배치 크기 자동 조절
- 다국어 지원: 일본어, 영어 번역 및 회신문/보고서 초안 생성
- G-EVAL 품질 평가: 4.3/5.0
- 공공기관 문서 자동 생성: 행정안전부 공문서 규정 기반 11종 문서 템플릿, HWPX 파일 자동 생성
- AI 문서 검수: 형식/스타일/내용/문법 40점 만점 자동 채점"""
    },
    {
        "category": "프로젝트",
        "title": "안전법령 특화 RAG 구축",
        "content": """공공데이터포털 API에서 산업안전보건법 등 18개 법령을 수집하여 특화 RAG 시스템 구축 (개인 프로젝트):
- Parent-Child Chunking: 법령의 조·항·호 계층 구조를 보존하는 청킹 전략
- Milvus 벡터 DB에 Dense+Sparse 하이브리드 인덱싱 (9,492 청크)
- 검색: Dense+Sparse RRF (0.4:0.6), 초기 k=40 → Top-K 7, 법령별 최대 3건
- Redis 임베딩 캐시 (TTL=2h)
- LLM 교차 참조 확장: 조문 내 「타 법령」 참조 자동 감지 → 연관 조문 추가 조회
- ReAct 에이전트 도구로 통합하여 챗봇에서 법령 검색 가능
- 프론트엔드부터 백엔드까지 1인 풀스택 구현"""
    },
    {
        "category": "프로젝트",
        "title": "영마린테크 - B2B 쇼핑몰",
        "content": """영마린테크 - 해양 엔진 부품 B2B 쇼핑몰 (2025.11 ~ 2026.02, 개인 프로젝트 100%)
실전 배포된 Full-Stack B2B 전자상거래 플랫폼

기술 스택: Python, FastAPI, PostgreSQL, pgvector, RAG, Gemini-2.5-Flash, OpenAI Embedding, React, Railway CI/CD, 다국어(KO/EN/CN)

핵심 구현:
- 6개 레이어 아키텍처: 고객 페이지, 관리자 페이지(React 18), FastAPI 서버, PostgreSQL, pgvector, AI APIs
- 다국어 JSONB 스키마: name, description, specs를 {ko, en, cn} 구조로 저장
- RAG 파이프라인: PDF 카탈로그 → 청킹 → 임베딩 → pgvector → Gemini 답변 생성
- 35개 이상 RESTful API 엔드포인트
- 비즈니스 임팩트: 70% 고객 응대 시간 단축, 24/7 무인 고객 대응"""
    },
    {
        "category": "프로젝트",
        "title": "AI 챗봇 데모 - 풀스택 개인 프로젝트",
        "content": """ReAct Agent 기반 실시간 스트리밍 AI 챗봇 + 안전법령 RAG 시스템 (개인 프로젝트, Claude Code 활용):

프론트엔드 (Next.js 15 + React 19 + TypeScript):
- SSE 실시간 스트리밍: 6가지 이벤트 타입 (token/progress/html/buttons/done/error)
- Zustand 상태 관리: conversations → messages → parts 3단계 중첩 상태
- 15개 React 컴포넌트, 1,242줄 TypeScript/TSX

백엔드 (Python FastAPI):
- ReAct Agent (GPT-4o Function Calling)
- 안전법령 RAG 파이프라인 (~1,500줄)
- SSE 스트리밍 + PostgreSQL 세션 관리

Claude Code 활용:
- Claude Code를 활용하여 퇴근 후 개인 프로젝트를 진행하며 새로운 기술 적용
- TDD 방식으로 테스트 작성 → 구현 → 리팩토링 사이클 반복
- 프론트엔드부터 백엔드, RAG, DB까지 1인 풀스택 개발"""
    },
    {
        "category": "기술스택",
        "title": "기술 스택",
        "content": """AI / ML Framework:
- LangGraph, LangChain, vLLM, OpenAI API, AsyncOpenAI
- PyTorch, TensorFlow
- Claude Code (AI 기반 개발 도구 활용)

Database:
- Milvus DB, Oracle DB, MariaDB, PostgreSQL, pgvector

Language & Tools:
- Python, JavaScript, TypeScript, HTML/CSS, Selenium, React, Next.js, FastAPI

Infrastructure:
- H100 GPU (8장), H200 GPU (8장), gpt-oss-120b
- Railway CI/CD
- Redis (임베딩 캐시, pub/sub)
- SSE (Server-Sent Events) 스트리밍"""
    },
    {
        "category": "경력학력",
        "title": "경력 및 학력",
        "content": """애자일소다 (2024.10 ~ 현재)
- 선임연구원, DS팀 (정규직)
- RAG 및 AI Agent 개발 담당
- 한국자산관리공사 그룹웨어 AI 도입 프로젝트 주도 (SI 형태)
- SI 기업에서 공공기관에 AI 서비스를 도입하는 프로젝트 수행

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
        "category": "한화시스템",
        "title": "한화시스템 회사 개요",
        "content": """한화시스템은 2000년 설립(삼성톰슨CSF → 삼성탈레스 → 한화탈레스), 2018년 한화S&C 흡수합병으로 방산+ICT 통합법인으로 출범한 국내 유일 방산·ICT 융합 기업입니다.

기업 규모:
- 임직원: 약 4,846명 (2024년 기준)
- 2024년 연결 매출: 약 2조 8,037억 원 / 영업이익 약 2,193억 원
- 2026년 전망: 매출 4.2조 원 (전년비 50% 성장)
- 상장: 코스피 (종목코드: 272210)

주요 사업 부문:
1. 방산 부문:
   - 감시정찰, 지휘통제/통신, 항공전자, 해양체계, 전자전
   - AI 기반 지능형 지휘결심지원 시스템
   - AI 스마트 배틀십 (세계 최초 CMS+ECS+IBS 통합)
   - AI 위성영상 분석 (VLEO 초고해상도 SAR 위성)
   - AI 특허 52건 (국내 방산기업 최다, 대기업 전체 6위)
2. ICT 부문:
   - 시스템통합(SI), IT아웃소싱(ITO)
   - AI/데이터 서비스: 자체 AI 브랜드 'HAIQV(하이큐브)'
   - ERP/솔루션: W1NE(보험), ai-CODI(교육)
   - 클라우드/인프라
3. 우주/UAM:
   - 위성통신, 저궤도위성 시스템
   - UAM(도심항공모빌리티) - 미국 Overair 인수

한화시스템의 차별점 (vs 삼성SDS, LG CNS 등):
- 국내 유일 방산+SI 이중구조: 방산 AI 기술의 민수 확산 가능
- 방산 소버린 AI 생태계 구축 (2025년, 서울대/KAIST/POSTECH/네이버클라우드 등 10여개 기관 MOU)
- K-방산 성장: 미 해군 자율수상함 30억 달러 공동개발 등 글로벌 수주
- 한화그룹 전 계열사 IT 서비스 (한화생명, 한화솔루션 등)"""
    },
    {
        "category": "한화시스템",
        "title": "한화시스템 ICT 부문 AI 서비스",
        "content": """한화시스템 ICT 부문의 AI 서비스 사업:

1. SI 프로젝트 (배경득 경험과 직결):
   - 한화그룹 전 계열사에 IT 시스템 구축 (SI)
   - 국방 SI: MIMS 등 군 정보시스템
   - ERP, SCM, HR 등 기간계 시스템에 AI 기능 통합
   - CMMi 국제수준 프로세스 적용
   - 배경득의 KAMCO SI 경험과 동일한 형태의 업무

2. ITO (IT 아웃소싱):
   - 한화그룹 전 계열사 IT 자산 관리/운영
   - SAP ERP 구축/운영

3. HAIQV(하이큐브) AI 솔루션:
   - Computer Vision: 객체 인식/분류/탐지, 영상 복원
   - NLP/챗봇: 자체 한국어 NLP 엔진, 챗봇 플랫폼
   - ai-CODI: AI 교육/취업지원 시스템 (중앙대, 숭실대 등 구축)
   - AI 플랫폼: 데이터 수집~ML~시각화 End-to-End 환경
   - 텍스트/이미지/동영상 AI 서비스 구축

4. 스마트팩토리:
   - IoT + 빅데이터 제조 최적화
   - 설비 예지보전(Predictive Maintenance)

5. 솔루션:
   - W1NE(보험 솔루션)
   - AI 디지털교과서
   - 클라우드/인프라

ICT 부문 매출: 약 5,760억 원 (2022년 기준)"""
    },
    {
        "category": "한화시스템",
        "title": "한화시스템 AI 서비스 직무 상세",
        "content": """한화시스템 AI 서비스 직무에서 하는 일:

주요 업무:
- 한화그룹 계열사 및 외부 고객사에 AI 서비스를 기획/설계/개발/배포
- 생성형 AI(LLM) 기반 업무 자동화 서비스 개발
- RAG 시스템 구축: 사내 문서 검색, FAQ 자동 응답 등
- AI Agent 개발: 업무 프로세스 자동화
- 데이터 파이프라인 설계 및 운영
- 클라우드 기반 AI 인프라 구축/운영

요구 기술 스택:
- 언어: Python (필수), JavaScript/TypeScript
- AI/ML: LangChain, LangGraph, OpenAI API, RAG, Vector DB
- 백엔드: FastAPI, Django, Spring Boot
- DB: PostgreSQL, MySQL, Oracle, Milvus, Elasticsearch
- 인프라: Docker, Kubernetes, AWS/Azure/GCP
- 프론트엔드: React, Next.js (우대)

한화시스템 직무 유튜브 내용:
- 실제 업무가 배경득이 하는 업무와 매우 유사
- SI 형태로 고객사에 AI 서비스를 도입하는 프로젝트 중심
- RAG, 챗봇, 문서 자동화 등 LLM 기반 서비스 개발
- 팀 단위 프로젝트 수행, 고객사와의 소통 중요"""
    },
    {
        "category": "한화시스템",
        "title": "한화시스템 핵심 가치와 인재상",
        "content": """한화시스템 핵심 가치:

한화그룹 경영 이념 - "신용과 의리":
- 신용: 고객, 동료, 파트너와의 약속을 지키는 것
- 의리: 어려울 때 함께하고, 성과를 함께 나누는 것

3대 핵심가치:
1. 도전(Challenge): 새로운 기술과 시장에 과감히 도전
2. 헌신(Dedication): 맡은 업무에 책임감 있게 헌신
3. 정도(Integrity): 투명하고 정직한 업무 수행

인재상 - Great Challenger:
- 주인의식: 회사의 일을 자신의 일처럼
- 월등한 차별성: 남다른 전문성과 역량
- 변화 수용성: 새로운 환경과 기술에 빠르게 적응

면접 핵심 (매우 중요):
- ⚠️ 협업/커뮤니케이션을 매우 중시 (SI 산업 특성상 독선적 모습은 부정적 평가)
- SI 프로젝트 경험: 고객사 요구사항 분석부터 배포까지 전 과정 경험
- 도전: 기존 구조의 한계를 인식하고 ReAct Agent로 전면 재설계 제안
- 헌신: Claude Code 등 최신 도구를 활용한 개인 프로젝트 지속 (퇴근 후에도 성장)
- 정도: 실험 결과(Gemma vs 프롬프트)가 가리키는 방향을 따르는 정직한 판단
- 변화 수용성: 기존 구조를 부정하고 새 구조로 전환할 수 있는 유연성

자소서 3문항 (2026 상반기):
- Q1: 지원동기/커리어 (1000자)
- Q2: 직무강점/경험 (700자)
- Q3: 인재상 키워드 경험 (700자)

채용 프로세스:
서류 → Codepie 코딩테스트 (프로그래머스 2~3 수준) → 1차 면접 → 2차 면접"""
    },
    {
        "category": "한화시스템",
        "title": "한화시스템에서의 기여 방안",
        "content": """배경득이 한화시스템 AI 서비스에서 기여할 수 있는 분야:

1. 그룹사 AI 서비스 도입 프로젝트 즉시 투입 가능
   - KAMCO에서 공공기관에 AI 서비스를 도입한 SI 경험이 한화시스템의 핵심 사업과 직결
   - 고객사 요구사항 분석 → 설계 → 개발 → 배포의 전 과정을 경험
   - 현업 담당자와의 소통, 주기적 검증 미팅 등 SI 프로젝트 방법론 체득

2. RAG 시스템 구축 역량
   - 1,000만건 규모 문서 기반 RAG 파이프라인 설계 경험
   - Hitrate@5 91%, 답변 정확도 92% 달성 경험
   - 한화그룹 계열사의 사내 문서 검색, FAQ 시스템에 즉시 적용 가능

3. AI Agent 개발 역량
   - ReAct + Function Calling 기반 37개 업무 도구 설계/구현
   - 복합 요청 처리, SSE 스트리밍, 세션 관리 등 프로덕션 레벨 구현
   - 한화그룹의 업무 프로세스 자동화에 활용

4. 풀스택 개발 역량
   - Python(FastAPI) 백엔드 + React/Next.js 프론트엔드 모두 가능
   - 개인 프로젝트로 기획부터 배포까지 전 과정 경험
   - PoC/프로토타입 빠른 개발 가능

5. 최신 기술 트렌드 파악 및 적용
   - Claude Code를 활용한 AI 기반 개발 생산성 향상
   - 퇴근 후에도 개인 프로젝트로 새로운 기술 적용 (TDD, Next.js 15, Milvus 등)
   - 기술 검증 프로젝트를 통해 실무 적용 가능성 사전 검증

6. 방산+민수 AI 시너지
   - 자연어처리, RAG, AI Agent 기술은 방산(지능형 감시, 지휘통제)과 민수(업무 자동화) 모두에 적용 가능
   - 대규모 문서 처리 경험은 방산 분야의 기술문서/매뉴얼 검색에도 활용 가능"""
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
        "category": "자소서핵심",
        "title": "자소서 핵심 소재 - SI 경험과 구조 재설계",
        "content": """배경득의 가장 강력한 경험 소재:

[구조 재설계 경험 - 자율적 판단과 책임]
- 초기 LangGraph 분기형 단일 파이프라인(40개 노드)의 한계를 직접 분석
- 사용자들의 복합 요청("회의실 예약하고 메일 초안도 작성해줘")을 처리할 수 없는 구조적 문제 발견
- 수개월 투자한 기존 구조를 스스로 부정하고 ReAct + Function Calling 전환 제안
- 프로토타입 데모를 개발하여 팀을 설득
- 기존 서비스를 유지하면서 새 구조를 병행 개발하여 프로덕션 배포

[RAG 품질 개선 - 숫자로 방향을 바꾸다]
- Hitrate@5 72%에서 시작 → KPI 85% 미달
- Contextual Retrieval, Parent-Child Chunking, 하이브리드 검색+Reranking 적용
- 최종 Hitrate@5 91%, 답변 정확도 92% 달성

[Gemma-27B 학습 vs 프롬프트 고도화 판단]
- 7만 건 학습 데이터로 LoRA 학습 → 정확성 88%→91%
- 프롬프트 고도화한 gptoss-120b가 92% 기록
- 수주간의 학습 시간 대비 성과를 분석하여 "프롬프트 고도화" 방향 선택
- 실험 결과가 가리키는 방향을 따르는 판단력

[1인 풀스택 도전 - 개인 프로젝트]
- 아버지의 해양 선박부품 판매 웹사이트를 기획부터 배포까지 혼자 개발
- Claude Code를 활용하여 개발 생산성을 높이면서도 코드 검증 습관 유지
- 퇴근 후에도 새로운 기술을 적용하며 지속적으로 성장하는 개발자"""
    },
    {
        "category": "자소서핵심",
        "title": "자소서 핵심 소재 - Claude Code와 AI 사회 이슈",
        "content": """[Claude Code 활용 경험 - AI 도구를 활용한 생산성 향상]
배경득은 현재 Claude Code를 적극 활용하여 개인 프로젝트를 수행하고 있습니다:
- 해양 선박부품 B2B 쇼핑몰: Claude Code로 프론트엔드부터 백엔드까지 개발
- AI 챗봇 데모: Next.js 15 + FastAPI + Milvus RAG 풀스택을 Claude Code와 함께 개발
- TDD 방식: Claude Code와 함께 테스트 작성 → 구현 → 리팩토링 사이클 반복
- 퇴근 후에도 새로운 기술(Next.js 15, Milvus, Zustand 등)을 적용하며 성장

[AI Agent 사회 이슈에 대한 견해]
- 생성형 AI가 대화형 챗봇에서 자율적으로 판단하는 AI Agent로 전환 중
- OpenAI Operator, Google Project Mariner, Anthropic Computer Use 등
- Agent의 자율 범위를 명확히 정의하고, 전문가의 판단이 필요한 경계를 엔지니어링으로 설계해야 함
- "안전한 자율성"은 구호가 아니라 코드로 구현해야 할 과제
- AI Agent가 산업 현장에서 신뢰를 얻으려면 자율성과 안전성을 동시에 설계할 수 있는 전문가 필요

[한화시스템과의 연결]
- 한화시스템의 방산 AI(지능형 감시, 자율주행)에서 "안전한 자율성"은 핵심 과제
- ICT 부문의 AI 서비스 도입에서도 기업 환경에 맞는 Agent 자율 범위 설계 필요
- 배경득의 ReAct Agent 설계 경험이 이러한 과제에 직접 적용 가능"""
    }
]

def get_portfolio_dataframe():
    """포트폴리오 데이터를 pandas DataFrame으로 반환"""
    df = pd.DataFrame(PORTFOLIO_SECTIONS)
    return df

def get_sections_by_category(category: str):
    """특정 카테고리의 섹션들만 반환"""
    return [section for section in PORTFOLIO_SECTIONS if section["category"] == category]
