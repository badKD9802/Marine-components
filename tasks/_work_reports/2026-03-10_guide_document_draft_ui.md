# 문서초안 단계별 가이드 UI 구현 (`guide_document_draft`)

> 작성일: 2026-03-10 | 카테고리: feat

## 배경
현재 react_system의 `draft_document` 도구는 11종의 공문서를 지원하지만, 사용자가 "문서초안 생성해줘"라고 하면 유형/필요 정보 안내 없이 바로 생성을 시도한다. 사용자 경험 개선을 위해 문서 유형 선택 → 필요 정보 안내 → 생성의 단계별 가이드 UI를 추가했다.

## 사용자 경험 흐름
```
"문서초안 생성해줘" → guide_document_draft(step="select_type") → 11종 리스트 HTML
→ "정책제안보고서" → guide_document_draft(step="show_requirements", document_type="정책제안보고서") → 필요 정보 안내 HTML
→ 내용 제공 → draft_document() 호출 → HWPX 생성

※ "공문 작성해줘"처럼 유형이 명확하면 guide 없이 draft_document 바로 호출
```

## 변경 사항
| 파일 | 변경 내용 |
|------|----------|
| `react_system/tools/draft_tools.py` | `guide_document_draft()` 함수 추가. `_guide_select_type()`, `_guide_show_requirements()` 내부 헬퍼 2개. `_PUBLIC_DOC_TEMPLATES`의 `hwpx_template` 값으로 행정문서(gonmun)/기획보고서(report 등) 그룹 구분. `<style>` + CSS 클래스 기반 HTML 생성 |
| `react_system/tool_definitions.py` | `guide_document_draft` OpenAI function calling 스키마 추가 (`step` enum: select_type/show_requirements, `document_type` optional) |
| `react_system/tool_registry.py` | `guide_document_draft` → `draft_tools.guide_document_draft` 등록 |
| `react_system/react_agent.py` | `TOOL_SENTENCE_ACTIVE`/`TOOL_SENTENCE_DONE`에 `guide_document_draft` progress 문구 추가 |
| `react_system/prompts.py` | 문서 초안 섹션에 가이드 호출 규칙 3가지 추가 + 도구 목록에 반영 |

## 핵심 코드

### guide_document_draft 함수 구조
```python
def guide_document_draft(step: str = "select_type", document_type: str = None) -> dict:
    if step == "select_type":
        return _guide_select_type()
    elif step == "show_requirements":
        return _guide_show_requirements(document_type)
```

### select_type 반환 구조
```python
{
    "status": "success",
    "html_content": "<style>...</style><div>행정문서 7종 + 기획보고서 4종 리스트</div>",
    "text_summary": "문서 유형 목록: 1=공문, 2=협조문, ... 11=프로젝트제안서. 번호 또는 유형명으로 선택 가능"
}
```

### 프롬프트 가이드 규칙
- 유형 미특정 → `guide_document_draft(step="select_type")` 먼저 호출
- 유형 선택 후 → `guide_document_draft(step="show_requirements")` 호출
- 유형 명확 → `draft_document` 바로 호출

## 설계 결정
- **전용 도구 방식 채택**: 프롬프트만으로는 HTML 스타일 제어가 불가하고 LLM 출력이 비일관적. `_PUBLIC_DOC_TEMPLATES` 데이터를 직접 읽어 일관된 HTML 생성
- **CSS 클래스 방식**: 인라인 `style` 속성은 프론트엔드 MarkdownViewer가 제거하므로 `<style>` 태그 + 클래스 사용
- **sync 함수**: LLM 호출 없이 딕셔너리에서 데이터만 읽으므로 async 불필요

## 후속 작업
- [ ] 실제 서버 환경에서 HTML 렌더링 확인 (MarkdownViewer에서 `<style>` 태그 처리 검증)
- [ ] 각 11종 유형별 `show_requirements` 안내 내용 정확성 검증
- [ ] 번호 매핑("8번") 입력 시 LLM이 올바른 유형으로 매핑하는지 E2E 테스트
