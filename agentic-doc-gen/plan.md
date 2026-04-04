# Plan: Agentic AI 문서 생성 시스템

> 공공기관용 AI 문서 자동화 — 양식 + 예시 기반 HWP/PPT/Excel 생성

## 비전

사용자가 "A 문서를 참고해서 B 양식으로 보고서 작성하고 요약 PPT도 만들어줘"라고 요청하면, AI가 양식 구조 + 잘 쓴 예시 + 참고문서를 분석하여 섹션별로 문서를 생성하고, Reviewer가 품질을 검증한 후 최종 산출물을 전달하는 시스템.

## 아키텍처 개요

```
사용자 요청: "A문서 참고해서 B양식으로 보고서 써주고 요약 PPT도"
  ↓
[Planner] 요청 파싱 → "참고=A, 양식=B, 산출물=HWP+PPT"
  ↓
[RAG] ── Milvus에서 B양식 구조 + B양식 잘 쓴 예시(최대 5개) + A문서 내용 검색
  ↓
[Orchestrator] 양식을 섹션으로 분해, 각 Worker에게 배분
  ↓
[Worker LLM] (섹션별 호출, 32K input 제한)
  ← 오케스트레이터 지시
  ← 해당 섹션 양식 구조 (JSON)
  ← 해당 섹션 잘 쓴 예시 5개 원본
  ← 참고문서 관련 내용
  → 섹션 결과물 (구조화 JSON)
  ↓
[Builder] 섹션 조립 → HWPX(python-hwpx) / PPTX(python-pptx) / XLSX(openpyxl)
  ↓
[Reviewer LLM] 체크리스트 기반 품질 평가 (80점 이상 → 통과, 미달 → 재작성)
  ↓
사용자에게 전달 + 섹션별 수정 UI
```

## 기술 스택

| 구성요소 | 기술 | 근거 |
|---------|------|------|
| HWPX 생성 | python-hwpx (v2.9.0) | 순수 Python, 크로스플랫폼, 테이블/셀병합 지원 |
| PPT 생성 | python-pptx | 성숙한 라이브러리, 레이아웃/플레이스홀더 기반 |
| Excel 생성 | openpyxl + pandas | Bread Excel Agent 3-tier 패턴 참고 |
| 벡터 DB | Milvus (기존 인스턴스) | Partition Key 멀티테넌시, 하이브리드 검색 |
| 임베딩 | BGE-M3 또는 BGE-m3-ko (dim=1024) | Dense+Sparse 동시 생성, 기존 safety_reg과 호환 |
| 중간 포맷 | Pydantic 모델 → JSON | FastAPI 호환, 타입 안전, 검증 용이 |
| 품질 평가 | LLM-as-a-Judge + 체크리스트 | RocketEval/CheckEval 패턴 (ICLR/EMNLP 2025) |
| 에이전트 패턴 | Plan-and-Execute + Reflexion | 계획/실행 분리, 자기평가 기반 재생성 |
| 백엔드 | FastAPI (`server/react_system/`) | 기존 ReAct 에이전트 + tool_registry 확장 |
| 프론트엔드 | Next.js (`chatbot-demo/frontend/`) | 기존 SSE 스트리밍 + 문서 미리보기 UI 추가 |

## 중간 포맷 JSON 스키마

```python
# LLM이 생성하는 각 섹션의 출력 포맷
class DocumentElement(BaseModel):
    type: Literal["heading", "paragraph", "table", "list", "image_placeholder"]
    content: Union[TextContent, TableContent, ListContent]

class TextContent(BaseModel):
    text: str
    style: Optional[dict]  # {"bold": True, "font_size": 14, "alignment": "center"}

class TableContent(BaseModel):
    caption: Optional[str]
    columns: list[dict]    # [{"name": "항목", "width": 30, "align": "left"}]
    rows: list[list[str]]
    merge: Optional[list]  # [{"range": "A5:D5", "value": "합계"}]

class ListContent(BaseModel):
    items: list[str]
    list_type: Literal["bullet", "numbered"]

class SectionOutput(BaseModel):
    section_id: str
    section_title: str
    elements: list[DocumentElement]
```

## Milvus 컬렉션 설계

```
컬렉션: document_templates (단일 컬렉션, Partition Key 멀티테넌시)

필드:
├── id (PK, VARCHAR)
├── dense_vector (FLOAT_VECTOR, dim=1024)
├── sparse_vector (SPARSE_FLOAT_VECTOR)
├── template_id (VARCHAR) — 양식 ID
├── chunk_type (VARCHAR) — "template" | "section" | "example"
├── parent_id (VARCHAR, nullable) — 섹션/예시 → 양식 연결
├── title (VARCHAR)
├── content (VARCHAR)
├── category (VARCHAR) — "예산/회계", "인사/복무" 등
├── subcategory (VARCHAR, nullable)
├── visibility (VARCHAR, partition_key) — "public" | "user:{id}"
├── user_id (VARCHAR, nullable)
├── metadata (JSON) — tags, quality_score, version 등
├── created_at (INT64)
└── updated_at (INT64)

검색 모드:
1. RAG 추천 → hybrid_search (dense + sparse + 스칼라 필터)
2. 키워드 재검색 → hybrid_search + 새 쿼리
3. 카테고리 브라우징 → query + offset/limit
```

## DB 테이블 설계

```sql
-- 생성된 문서 상태 관리 (대화와 분리)
CREATE TABLE generated_documents (
    doc_id VARCHAR PRIMARY KEY,
    session_id VARCHAR,          -- 대화 세션 연결
    user_id VARCHAR,
    template_id VARCHAR,
    status VARCHAR DEFAULT 'draft',  -- draft | completed
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE document_sections (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR REFERENCES generated_documents(doc_id),
    section_index INTEGER,
    section_title VARCHAR,
    content JSONB,               -- SectionOutput JSON
    version INTEGER DEFAULT 1,   -- 수정할 때마다 +1
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## 구현 단계

---

### Phase 1: 중간 포맷 + Builder (기반 인프라)

LLM 없이도 JSON → 네이티브 포맷 변환이 정확히 동작하는지 검증.

- [ ] **1.1** Pydantic 중간 포맷 스키마 정의 (`server/react_system/document_schema.py`)
  - SectionOutput, DocumentElement, TextContent, TableContent, ListContent
  - JSON 직렬화/역직렬화 테스트

- [ ] **1.2** HWPX Builder (`server/react_system/tools/hwpx_document_builder.py`)
  - JSON → HWPX 변환: heading, paragraph, table, list
  - 테이블: 셀 병합, 너비, 정렬 지원
  - python-hwpx 라이브러리 사용
  - 테스트: 샘플 JSON → HWPX 생성 → 한글에서 열기 검증

- [ ] **1.3** PPTX Builder (`server/react_system/tools/pptx_builder.py`)
  - JSON → PPTX 변환: 제목 슬라이드, 본문 슬라이드, 표 슬라이드
  - python-pptx 라이브러리 사용
  - 레이아웃/플레이스홀더 기반 안정적 생성

- [ ] **1.4** XLSX Builder (`server/react_system/tools/xlsx_builder.py`)
  - JSON → XLSX 변환: 데이터 시트, 차트, 서식
  - openpyxl 라이브러리 사용

---

### Phase 2: Milvus 양식/예시 저장소

양식과 잘 쓴 예시를 벡터 DB에 저장하고 검색하는 파이프라인.

- [ ] **2.1** Milvus 컬렉션 생성 (`server/react_system/template_store.py`)
  - document_templates 컬렉션 스키마 (위 설계안 기반)
  - Partition Key: visibility 필드
  - 인덱스: IVF_FLAT(dense) + SPARSE_INVERTED(sparse) + INVERTED(스칼라)

- [ ] **2.2** 양식 업로드 파이프라인
  - HWPX 파싱 → 섹션 분해 → 임베딩 → Milvus 저장
  - chunk_type="template" (전체) + chunk_type="section" (섹션별)
  - BGE-M3로 dense+sparse 벡터 동시 생성

- [ ] **2.3** 예시 업로드 파이프라인
  - HWPX/문서 파싱 → 섹션 분해 → 임베딩 → Milvus 저장
  - chunk_type="example", template_id로 양식 연결
  - 사용자 업로드: visibility="user:{id}", user_id 설정

- [ ] **2.4** 양식 검색 API (`server/react_system/template_search.py`)
  - RAG 추천: hybrid_search (의미+키워드+스칼라 필터)
  - 카테고리 브라우징: query + offset/limit
  - 특정 양식의 예시 조회: template_id 필터
  - 멀티테넌시: visibility in ["public", "user:{id}"]

---

### Phase 3: 문서 생성 에이전트 (핵심)

Planner → Worker (섹션별) → Builder → Reviewer 파이프라인.

- [ ] **3.1** 문서 상태 DB 테이블 생성
  - generated_documents, document_sections 테이블
  - 대화 히스토리와 분리된 문서 상태 관리

- [ ] **3.2** Planner 도구 (`server/react_system/tools/document_planner.py`)
  - 사용자 요청 분석 → 참고문서, 양식, 산출물 유형 파싱
  - 양식을 섹션으로 분해
  - 각 섹션에 필요한 예시 + 참고문서 부분 매핑

- [ ] **3.3** Writer 도구 (`server/react_system/tools/document_writer.py`)
  - 섹션별 LLM 호출: 양식 구조 + 예시 원본 + 참고문서 → JSON 생성
  - 32K 토큰 예산 관리
  - 결과를 document_sections 테이블에 저장

- [ ] **3.4** Reviewer 도구 (`server/react_system/tools/document_reviewer.py`)
  - 체크리스트 기반 품질 평가 (5대 기준)
    - 완성도 (0.25), 정확성 (0.25), 형식 준수 (0.20), 명확성 (0.15), 일관성 (0.15)
  - 기준별 개별 LLM 호출 → 가중 합산
  - 80점 이상: 통과, 미달: 구체적 피드백 + Worker 재작성 (최대 2회)

- [ ] **3.5** 문서 생성 오케스트레이터 (`server/react_system/tools/document_orchestrator.py`)
  - Planner → RAG 검색 → Writer (섹션별) → Builder → Reviewer 파이프라인 통합
  - 실패 섹션만 재생성 (Reflexion 패턴)
  - SSE 진행상황 스트리밍 (기존 progress 시스템 활용)

- [ ] **3.6** tool_definitions.py + tool_registry.py 에 새 도구 등록
  - generate_document, search_templates, upload_example 등 Function Calling 스키마

---

### Phase 4: 프론트엔드 UI

양식 선택, 예시 선택, 문서 미리보기, 섹션 수정 UI.

- [ ] **4.1** 양식 선택 UI
  - RAG 추천 결과를 버튼으로 표시 (기존 buttons 메시지 파트 활용)
  - 페이지네이션: "다음 10개 더 보기" 버튼
  - "직접 검색하기" + "전체 양식 보기" (카테고리 브라우징)

- [ ] **4.2** 예시 선택 UI
  - 양식 선택 후 → 연결된 예시 목록 표시
  - 체크박스 선택 (전체 사용 / 개별 선택)
  - "내 예시" (user) 상단 표시 + "기본 제공 예시" (public) 하단
  - "내 파일 업로드" 버튼 → 파일 업로드 → Milvus 저장

- [ ] **4.3** 문서 미리보기 + 섹션 수정 UI
  - 생성 완료 후: 섹션별 미리보기 (HTML 렌더링)
  - 각 섹션에 [수정] 버튼
  - 클릭 → 팝업: 현재 내용 + 수정 요청 입력 → Worker 재호출 → 해당 섹션만 교체
  - document_sections 테이블에서 최신 버전 사용 (version +1)

- [ ] **4.4** 문서 다운로드 API
  - GET /api/documents/{doc_id}/download?format=hwpx|pptx|xlsx
  - document_sections에서 최신 버전 조립 → Builder → 파일 스트리밍

- [ ] **4.5** 채팅 + 문서 상태 통합
  - 채팅은 최초 생성 요청용, 수정은 UI 직접 조작
  - 새로고침 → DB에서 문서 상태 복원 (session_id로 연결)

---

### Phase 5: 고도화

- [ ] **5.1** 섹션 수정 시 Reviewer 재평가 (수정된 섹션만)
- [ ] **5.2** 문서 생성 이력 관리 (버전 히스토리)
- [ ] **5.3** 인기 양식 / 최근 사용 양식 추천
- [ ] **5.4** 양식 관리 어드민 (양식 추가/수정/삭제, 예시 관리)
- [ ] **5.5** 다중 문서 동시 생성 (HWP + PPT + Excel 한번에)
- [ ] **5.6** 비용 최적화: Writer는 빠른 모델, Reviewer는 가벼운 모델

---

## 주의사항

### python-hwpx 라이선스
- 비상업적 사용 무료, 상업적 사용 시 별도 허가 필요
- 대안: pypandoc-hwpx (Markdown→HWPX), hwpx-mcp-server (MIT)

### 토큰 관리 (32K 제한)
- 각 Worker 호출 시 예산: 시스템 프롬프트(2K) + 양식구조(1K) + 예시 5개 해당 섹션(5K) + 참고문서(8K) + 생성 여유(16K) = ~32K
- 예시가 커서 안 들어가면 → 가장 유사한 2-3개만 선별

### HWPX 기술 포인트
- linesegarray 요소는 제거/무시 (한글이 열 때 자동 재계산)
- 줄바꿈은 `<hp:lineBreak/>` 태그 사용
- 셀 병합: merge_cells(row1, col1, row2, col2)

## 리서치 보고서 위치

- `.claude/research/hwpx-automation.md` — HWPX 자동화 라이브러리 비교
- `.claude/research/multi-agent-architecture.md` — 멀티에이전트 아키텍처, MCP/A2A, Reviewer 패턴
- `.claude/research/document-generation-ai.md` — 문서 생성 AI 논문/레포, 중간 포맷, 품질 평가
- `.claude/research/milvus-rag-design.md` — Milvus 스키마, 멀티테넌시, 하이브리드 검색, 한국어 임베딩
