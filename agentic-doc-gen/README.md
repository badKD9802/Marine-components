# Agentic AI 문서 생성 시스템

공공기관용 AI 문서 자동화 모듈. 양식 + 잘 쓴 예시 + 참고문서 기반으로 HWP/PPT/Excel 문서를 자동 생성.

## 구조

```
agentic-doc-gen/
├── backend/
│   ├── core/                    # 핵심 모듈
│   │   ├── document_schema.py   # Pydantic 중간 포맷 (DocumentOutput, SectionOutput)
│   │   ├── document_db.py       # 문서 상태 DB (PostgreSQL, 버전 관리)
│   │   ├── template_store.py    # Milvus 벡터 DB 연결/CRUD/하이브리드 검색
│   │   ├── template_upload.py   # 양식/예시 업로드 파이프라인
│   │   └── template_search.py   # 양식 검색 API (RAG 추천, 카테고리 브라우징)
│   ├── tools/                   # 에이전트 도구
│   │   ├── hwpx_document_builder.py  # JSON → HWPX 변환 (python-hwpx)
│   │   ├── pptx_builder.py           # JSON → PPTX 변환 (python-pptx)
│   │   ├── xlsx_builder.py           # JSON → XLSX 변환 (openpyxl)
│   │   ├── document_planner.py       # 요청 분석 → 문서 생성 계획
│   │   ├── document_writer.py        # 섹션별 LLM 생성
│   │   ├── document_reviewer.py      # 체크리스트 기반 품질 평가
│   │   └── document_orchestrator.py  # 전체 파이프라인 오케스트레이션
│   ├── api/
│   │   └── document_api.py      # FastAPI 엔드포인트 (다운로드, 섹션 수정)
│   └── tests/                   # 테스트 208개
│       └── test_*.py
├── frontend/
│   ├── components/
│   │   ├── TemplateSelector.tsx  # 양식 선택 UI
│   │   ├── ExampleSelector.tsx   # 예시 선택 UI (체크박스, 내 예시/공개 분리)
│   │   ├── DocumentPreview.tsx   # 문서 미리보기 (섹션별 카드, 다운로드)
│   │   └── SectionEditModal.tsx  # 섹션 수정 (AI 수정 + WYSIWYG 직접 수정)
│   ├── types/
│   │   └── message.ts           # TypeScript 타입 정의
│   └── demo/
│       └── page.tsx             # 데모 페이지 (백엔드 없이 UI 확인)
└── plan.md                      # 전체 구현 계획
```

## 필요 의존성

### Python (백엔드)
```
python-hwpx>=2.9.0
python-pptx>=1.0.0
openpyxl
pydantic>=2.0
fastapi
asyncpg
pymilvus>=2.4.0
openai
```

### Node.js (프론트엔드)
```
next >= 15
react >= 19
zustand
lucide-react
tailwindcss
```

## 다른 서비스에 적용하는 방법

1. `backend/core/`와 `backend/tools/`를 서비스의 백엔드에 복사
2. `backend/api/document_api.py`의 라우터를 FastAPI app에 등록
3. `frontend/components/`를 프론트엔드에 복사
4. `frontend/types/message.ts`의 타입을 기존 메시지 타입에 병합
5. 환경변수 설정: `OPENAI_API_KEY`, `MILVUS_HOST`, `DATABASE_URL`
6. Milvus 컬렉션 생성: `template_store.TemplateStore().create_collection()`
7. DB 테이블 생성: `document_db.create_document_tables()`

## 아키텍처

```
사용자 → 채팅 "보고서 써줘"
  → [Planner] 양식 추천 or 계획 수립
  → [RAG] Milvus에서 양식 + 예시 검색
  → [Writer] 섹션별 LLM 생성 (32K 토큰 관리)
  → [Builder] JSON → HWPX/PPTX/XLSX
  → [Reviewer] 5대 기준 품질 평가 (80점 통과)
  → 사용자에게 전달 + 섹션별 수정 UI
```
