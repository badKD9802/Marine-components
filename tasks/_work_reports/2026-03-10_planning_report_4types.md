# 기획보고서 4종 (□○―※ 기호 체계) + 문서 검수 도구 구현

> 작성일: 2026-03-10 | 카테고리: feat

## 배경
기존 `draft_document` 도구는 공문, 보고서, 회의록, 기안서 등 7종의 공공기관 문서를 지원하며, 모두 유형 A(행정문서) 번호 체계(1. → 가. → 1) → 가))를 사용한다. 실제 공공기관에서 가장 많이 쓰는 기획보고서(정책보고서) 양식은 완전히 다른 유형 B 기호 체계(Ⅰ,Ⅱ,Ⅲ + □○―※)를 사용하므로, 4종의 새 템플릿과 HWPX 빌드 로직을 추가하고, 생성된 문서의 품질을 검증하는 `review_document` 도구도 함께 구현했다.

## 에이전트 파이프라인 (6단계)

| 단계 | 에이전트 | 결과 | 산출물 |
|------|----------|------|--------|
| 1. 조사 | researcher | PASS | `.claude/research/planning_report_research.md` |
| 2. 검토 | review-checker | PASS (24/25) | `.claude/research/planning_report_review.md` |
| 3. 계획 | planner | PASS | `.claude/plans/planning_report_implementation.md` |
| 4. 개발 | developer x2 (병렬) | PASS | Part A + Part B 동시 구현 |
| 5. QA | qa | PASS (전 항목) | `.claude/qa-reports/2026-03-10_planning_report_qa.md` |
| 6. 최종 검수 | supervisor | APPROVED | `.claude/supervisor-reports/2026-03-10_planning_report_final.md` |

## 변경 사항

### Part A: 기획보고서 4종

| 파일 | 변경 내용 |
|------|----------|
| `react_system/hwpx_templates/planning_report/header.xml` | **신규 생성**. proposal 기반 + charPr 4개(id 12~15: □16pt bold, ○15pt, ―15pt, ※13pt 중고딕) + paraPr 4개(id 29~32: 기호별 before spacing 차등) |
| `react_system/hwpx_templates/planning_report/section0.xml` | **신규 생성**. 표지(기관명/제목/작성일/작성자) + pageBreak + `{{DYNAMIC_BODY}}` 동적 삽입 영역 |
| `react_system/tools/hwpx_builder.py` | `_split_sections_roman()` 로마숫자 파싱, `_build_symbol_paragraphs()` 기호별 XML `<hp:p>` 동적 생성, `_build_major_heading_xml()`/`_build_minor_heading_xml()` 대소제목 테이블, `_build_planning_report_placeholders()` 전체 조립, `_RAW_XML_PREFIX` 마커로 이스케이프 방지 |
| `react_system/tools/draft_tools.py` | `_PUBLIC_DOC_TEMPLATES`에 4종 추가 (정책제안보고서, 사업계획보고서, 실적보고서, 현안보고서) + `_PLANNING_REPORT_SYMBOL_RULES` 공통 프롬프트 + `_style_planning_symbols()` CSS 스타일링 + `_build_public_doc_html()` 확장 |
| `react_system/tool_definitions.py` | `draft_document`의 `document_type` enum에 4종 추가 |
| `react_system/prompts.py` | 기획보고서 4종 + □○―※ 기호 체계 안내 추가 |

### Part B: 문서 검수 도구 (review_document)

| 파일 | 변경 내용 |
|------|----------|
| `react_system/tools/draft_tools.py` | `review_document()` async 함수 추가 — LLM 기반 4개 영역(형식/문체/내용/어문규범) 검수, 기획보고서일 때 □○―※ 추가 검수 기준, `_build_review_html()` 점수 게이지 바 + severity별 색상 렌더링, `_build_review_html_fallback()` JSON 파싱 실패 시 원본 텍스트 렌더링 |
| `react_system/tool_definitions.py` | `review_document` 스키마 추가 — `document_content`(필수), `document_type`, `review_focus`(전체/형식/내용/기호체계) |
| `react_system/tool_registry.py` | `"review_document": draft_tools.review_document` 등록 |
| `react_system/react_agent.py` | `TOOL_SENTENCE_ACTIVE/DONE` progress 문구 추가 |
| `react_system/prompts.py` | review_document 도구 설명 추가 |

## 핵심 코드

### ID 범위 분리 (충돌 방지)
- 템플릿 고정 ID: `1000000001~`
- 동적 paragraph ID: `2000000001~`
- 테이블 내부 paragraph ID: `2500000001~`
- 테이블 ID: `3000000001~`

### RAW XML 삽입 메커니즘
```python
_RAW_XML_PREFIX = "<!--RAW_XML-->"
# _apply_replacements()에서 이 prefix가 있으면 _esc() 건너뜀
# planning_report의 {{DYNAMIC_BODY}}에 기호별 XML을 안전하게 삽입
```

### 기호 → charPr/paraPr 매핑
```python
_SYMBOL_MAP = {
    "□": (12, 29),   # 16pt bold, left=600
    "○": (13, 30),   # 15pt, left=1200
    "―": (14, 31),   # 15pt, left=1800
    "※": (15, 32),   # 13pt, left=600
}
```

### 기획보고서 4종 (hwpx_template 공유: "planning_report")
| 문서 유형 | aliases | 주요 섹션 |
|----------|---------|----------|
| 정책제안보고서 | 정책제안, 정책보고서 | 개요, 추진배경, 현황 및 문제점, 개선방안, 향후계획 |
| 사업계획보고서 | 사업계획보고 | 추진배경, 사업개요, 세부추진계획, 소요예산, 기대효과, 행정사항 |
| 실적보고서 | 실적보고, 성과보고서 | 개요, 추진현황, 주요성과, 문제점 및 개선방안, 향후계획 |
| 현안보고서 | 현안보고, 현안분석 | 현안개요, 현황분석, 대응방안, 건의사항 |

### review_document 검수 영역
| 영역 | 설명 | 기획보고서 추가 기준 |
|------|------|---------------------|
| 형식 | 문서 구조, 번호 체계 | □○―※ 기호 체계 정확성, 들여쓰기 규칙 |
| 문체 | 경어체, 개조식 | 대제목(Ⅰ~Ⅴ) 순서 및 형식 |
| 내용 | 논리 흐름, 근거 | 기호 계층 구조 (□→○→―→※) |
| 어문규범 | 맞춤법, 띄어쓰기 | "끝." 마감 여부 |

## 기술적 의사결정

| 결정 사항 | 선택 | 근거 |
|----------|------|------|
| HWPX 템플릿 | planning_report/ 전용 폴더 신규 생성 | 기존 proposal 템플릿에 영향 없이 독립적 관리 |
| 본문 생성 방식 | `{{DYNAMIC_BODY}}` 단일 플레이스홀더 + 동적 XML | 기호별 charPr/paraPr을 정확히 적용하려면 줄 단위 `<hp:p>` 생성 필요 |
| XML 이스케이프 | `_RAW_XML_PREFIX` 마커 방식 | 기존 `_apply_replacements()` 수정 최소화 |
| Part A/B 병렬 개발 | developer 에이전트 2개 동시 실행 | draft_tools.py 추가 영역이 겹치지 않아 병렬 가능 |

## 후속 작업
- [ ] 서버 재시작 후 E2E 테스트: 채팅에서 "정책제안보고서 작성해줘" 요청
- [ ] 생성된 HWPX의 한글(Hancom) 프로그램 열기 확인
- [ ] review_document E2E 흐름: 문서 생성 → "검수해줘" 요청 → 점수/수정사항 확인
- [ ] proposal 템플릿 플레이스홀더 추가 (기존 미완료 항목)

## 참고 사항
- `header.xml`의 paraPr ID에 갭(22→29)이 있으나 HWPX 스펙상 허용됨
- `react_agent.py`, `tool_registry.py`의 lint 경고는 기존 코드의 pre-existing 이슈 (이번 변경과 무관)
- lxml 미사용 — 모든 XML은 f-string/str.join으로 텍스트 기반 생성
