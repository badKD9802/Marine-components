# 공공기관 문서 초안 생성 기능 구현 (draft_document LLM 연동)

> 작성일: 2026-03-09 | 카테고리: feat

## 배경
기존 `draft_document` 도구는 섹션 제목 + `[내용을 작성하세요]` 플레이스홀더만 출력하여 실용성이 없었음.
행정안전부 공문서 작성 규정에 맞는 프롬프트를 적용하고, Tool 내부에서 LLM을 호출해 실제 내용을 생성하도록 개선.

## 변경 사항

| 파일 | 변경 내용 |
|------|----------|
| `react_system/tools/draft_tools.py` | 핵심 변경 - 공공기관 문서 7종 템플릿 + LLM 호출 + HTML 렌더링 |
| `react_system/tool_definitions.py` | `draft_document` 스키마에 `enum`, `recipient`, `reference` 추가 |
| `react_system/prompts.py` | 문서 초안 표시 규칙 + 도구 목록 업데이트 |

### 1. `react_system/tools/draft_tools.py` (핵심)

**추가된 구조:**

- `_PUBLIC_DOC_TEMPLATES` dict — 공공기관 문서 7종 (공문/협조전, 업무보고서, 기획안, 회의록, 결과보고서, 사업계획서, 검토보고서)
  - 각 유형별 `system_prompt`, `sections`, `header_fields`, `has_footer`, `aliases` 정의
  - system_prompt는 행정안전부 공문서 작성 규정 기반 (경어체, 계층 번호, "끝." 마감 등)
- `_GENERAL_DOC_TEMPLATES` dict — 기존 일반 문서 3종 (보고서, 기획서, 제안서) 하위호환
- `_find_public_template(document_type)` — 이름 + alias 매칭
- `_get_llm_config(_auth)` — `config.ini`에서 LLM 설정(base_url, api_key, model) 추출 (JustLLM과 동일 소스)
- `_generate_document_content()` — AsyncOpenAI로 LLM 호출, 문서 유형별 프롬프트 구성
- `_build_public_doc_html()` — HTML 렌더링 (복사 버튼, slate 그라디언트 헤더, 결재란 테이블)

**`draft_document()` 변경:**
- `def` → `async def`
- `recipient`, `reference` 파라미터 추가
- 공공기관 유형 → LLM 호출 + HTML 렌더링 (`html_content` 패턴)
- 일반 유형 → 기존 템플릿 로직 유지
- LLM 실패 시 → 섹션 구조만 반환 (graceful fallback)

### 2. `react_system/tool_definitions.py` (lines 605-659)

- `document_type`에 `enum` 추가: 공공기관 7종 + 일반 3종
- `recipient` (수신 기관/부서), `reference` (참조 기관/부서) 파라미터 추가
- `description` 업데이트: 공공기관 vs 일반 문서 안내

### 3. `react_system/prompts.py`

- 도구 목록 "7. 문서" 항목에 공공기관 문서 7종 언급 추가
- 메일 초안 규칙 뒤에 `📝 문서 초안 (draft_document) 표시 규칙` 섹션 추가

## 수정하지 않은 파일 (이유)

- `tool_registry.py` — `"draft_document": draft_tools.draft_document` 이미 등록 (line 46)
- `react_agent.py` — `TOOL_SENTENCE_ACTIVE/DONE`에 `"draft_document"` 이미 존재

## 핵심 코드

### LLM config 추출 (_auth.stat → config.ini)
```python
def _get_llm_config(_auth=None) -> dict:
    if _auth and _auth.stat:
        from app.tasks.lib_justtype.common.just_env import JustEnv
        just_env = JustEnv(_auth.stat)
        llm_config = just_env.get_config("llm")
        default_name = llm_config.get("default_llm_name", "")
        config = llm_config.get(default_name, llm_config) if default_name else llm_config
        return {
            "base_url": config.get("base_url"),
            "api_key": config.get("api_key", ""),
            "model": config.get("model_name", "gpt-4o"),
        }
    return {"base_url": None, "api_key": None, "model": "gpt-4o"}
```

### LLM 호출 (AsyncOpenAI — translate_tools.py 패턴)
```python
async def _generate_document_content(template, doc_type, title, ..., _auth=None):
    try:
        llm_cfg = _get_llm_config(_auth)
        client = AsyncOpenAI(**{k: v for k, v in llm_cfg.items() if k != "model" and v})
        response = await client.chat.completions.create(
            model=llm_cfg["model"],
            messages=[
                {"role": "system", "content": template["system_prompt"]},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5, max_tokens=4000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return None  # fallback to template-only
```

## 버그 수정 이력

### 런타임 오류 (AsyncOpenAI 초기화 실패)
- **증상**: 채팅에서 "일시적인 문제가 발생했네요" 응답
- **원인**: `AsyncOpenAI()` 생성자를 파라미터 없이 호출 → `OPENAI_API_KEY` 환경변수 미설정 → 생성자에서 예외 발생. 이 예외가 try/except **밖**에 있어서 fallback 없이 크래시.
- **수정**:
  1. `_get_llm_config(_auth)` 추가 — `config.ini`에서 `base_url`, `api_key`, `model` 추출
  2. `AsyncOpenAI(**client_kwargs)` — 올바른 인증 정보 전달
  3. 전체 LLM 호출을 try/except **안**으로 이동 → 실패 시 graceful fallback

## 후속 작업
- [ ] 실제 서버 환경에서 LLM 호출 E2E 테스트
- [ ] KAMCO 내부 양식 샘플 기반 프롬프트 보정 (현재는 행정안전부 공문서 작성 규정 일반 원칙 기반)
- [ ] `translate_tools.py`도 동일한 `_get_llm_config` 패턴 적용 필요 (현재 bare `AsyncOpenAI()` 사용)

## 참고 사항
- `dynamic_reload.sh on` 상태에서는 서버 재시작 없이 코드 변경 즉시 반영됨
- 프롬프트의 문서 형식 규칙은 Claude의 학습 데이터에 포함된 행정안전부 공문서 작성 규정을 기반으로 작성 (특정 기관 실제 프롬프트 참조 아님)
- `html_content` 패턴: Tool이 `html_content` 키를 반환하면 `react_agent.py`가 SSE로 프론트에 직접 스트리밍 → `text_summary`는 LLM 후속 컨텍스트용
