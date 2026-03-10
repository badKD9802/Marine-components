# Function Calling (ReAct Agent) 개발 가이드

> **이 문서는 ReAct 에이전트 시스템에 새로운 도구를 추가하거나 기존 도구를 수정할 때 참고하는 가이드입니다.**
> 처음 접하는 개발자도 이 문서를 따라가면 도구를 추가할 수 있도록 작성되었습니다.

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [디렉토리 구조](#2-디렉토리-구조)
3. [핵심 파일 설명](#3-핵심-파일-설명)
4. [도구 추가 가이드 (Step by Step)](#4-도구-추가-가이드-step-by-step)
5. [도구 반환값 패턴](#5-도구-반환값-패턴)
6. [HTML 렌더링 도구 만들기](#6-html-렌더링-도구-만들기)
7. [시스템 프롬프트 수정 가이드](#7-시스템-프롬프트-수정-가이드)
8. [테스트 및 디버깅](#8-테스트-및-디버깅)
9. [실전 예제: 처음부터 끝까지](#9-실전-예제-처음부터-끝까지)
10. [주의사항 및 FAQ](#10-주의사항-및-faq)

---

## 1. 시스템 개요

### ReAct 패턴이란?

**Re**asoning + **Act**ing 패턴입니다. LLM이 사용자 질문을 받으면:

```
1. 질문 분석 (Reasoning) → 어떤 도구를 써야 할지 판단
2. 도구 호출 (Acting) → 실제 함수 실행
3. 결과 분석 (Reasoning) → 결과를 보고 추가 작업 필요한지 판단
4. 반복 또는 최종 답변 생성
```

### 전체 LangGraph 워크플로우 (`multi_turn_stream.py`)

ReAct 에이전트는 전체 LangGraph 워크플로우의 **하나의 노드(`llm_answer`)**로 동작합니다.

```
사용자 메시지
  ↓
node_is_rag_service (진입점 — 의도 분류)
  │
  ├─ "rag"            → RAG 파이프라인 (사내 문서 검색 → 답변 생성)
  ├─ "route"          → llm_answer (= ReAct 에이전트) ← 여기
  ├─ "multi_question" → 복합 질문 처리
  ├─ "admin"          → 관리자 워크플로우
  └─ "intent_suggest" → 의도 모호 시 선택 버튼 제시
```

**핵심 연결부:**

```python
# multi_turn_stream.py
from app.tasks.node_agent.aiassistant.function_calling.react_system.main import llm

workflow.add_node("llm_answer", llm)  # ReAct 에이전트 = llm_answer 노드
```

#### 의도 분류 (Intent Detection)

`node_is_rag_service`에서 LLM(`_classify_intent`)으로 질문 의도를 분류합니다:

| 의도 | confidence | 라우팅 | 설명 |
|------|-----------|--------|------|
| `rag` | high | RAG 파이프라인 | 사내 문서/규정 관련 질문 |
| `calendar`/`meeting`/`employee`/`general` | high | ReAct 에이전트 | 그룹웨어/일반 질문 |
| 둘 다 가능 | ambiguous | intent_suggest | 사용자에게 선택 버튼 제시 |
| 판단 불가 | low | 토글 따름 | FE 토글(RAG/서비스) 기준 |

#### 마이그레이션 보고서

구 `aiassistant/services/` → 신 `react_system/tools/` 마이그레이션 상세 분석은 `report/` 폴더 참고:

- **`01_migration_comparison.md`** — 기능 대조: 구/신 파일별 함수 매핑, 완료/미구현 현황 (34개 기능 중 19개 완료, 6개 미구현)
- **`02_regression_prevention.md`** — 회귀 방지: 구 시스템에서 되던 기능이 신 시스템에서 안 되는 8개 항목 + 구현 코드 포함 보완 방안

#### 레거시 서비스 노드 vs ReAct 에이전트

| 항목 | 레거시 (기존) | ReAct (신규) |
|------|-------------|-------------|
| 경로 | `router` → `parser` → 개별 GW API 노드 | `node_is_rag_service` → `llm_answer` |
| 노드 수 | 서비스별 20+ 노드 | 단일 노드 |
| 도구 수 | 각 노드 1기능 | 30개 도구 자유 조합 |
| 유연성 | 고정 분기 | 멀티턴, 도구 체이닝, 병렬 호출 |

**레거시 노드는 아직 존재합니다** (`multi_turn_stream.py`의 `build_workflow()`).
현재 `"route"` 경로만 ReAct 에이전트로 연결되어 있으며, 레거시 노드들은 병행 운영 중입니다.

#### Fallback 체계

```
ReAct 에이전트 → 결과 부족 → rag_fallback → RAG 파이프라인
RAG 파이프라인 → 결과 부족 → llm_fallback → ReAct 에이전트
```

양방향 fallback으로 항상 최선의 답변을 제공합니다.

### ReAct 에이전트 내부 실행 흐름

```
main.py (LangGraph 노드 진입점)
  ↓
AuthContext.from_stat(stat) — SLO 1회 호출, 인증 정보 캐싱
  ↓
ToolRegistry(auth=auth) — 인증 정보를 레지스트리에 주입
  ↓
ReactAgent.run(question, history) — ReAct 루프 시작
  ↓
LLM 호출 (tool_definitions.py 스키마 기반으로 도구 선택)
  ↓
ToolRegistry.dispatch() — 실제 함수 실행 (_auth 자동 주입)
  ↓
결과를 LLM에 전달 → 반복 또는 최종 답변
  ↓
SSE 스트림으로 프론트엔드에 전송
```

### 데이터 흐름 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│  JustLLM + ToolRegistry + TOOLS → ReactAgent            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   react_agent.py                        │
│                                                         │
│  ┌─────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ _call_   │───▶│ tool_        │───▶│ tool_         │  │
│  │ llm()    │    │ definitions  │    │ registry      │  │
│  │          │◀───│ .py (스키마) │    │ .py (실행)    │  │
│  └─────────┘    └──────────────┘    └───────┬───────┘  │
│       ▲                                      │          │
│       │              도구 결과                │          │
│       └──────────────────────────────────────┘          │
│                                                         │
│  html_content 있으면 → writer()로 직접 스트림 전송       │
│  text_summary → LLM에게 전달 (후속 질문 참조용)          │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 디렉토리 구조

```
function_calling/
├── README.md                # 이 문서
├── WORK_LOG.md              # 작업 로그 (API 연동, 더미 데이터 수정 기록)
│
├── report/                  # 마이그레이션 보고서
│   ├── 01_migration_comparison.md   # 기능 대조 보고서 (구 services/ ↔ 신 react_system/tools/)
│   └── 02_regression_prevention.md  # 회귀 방지 보고서 (미구현 8항목 + 보완 방안)
│
└── react_system/
    ├── __init__.py          # 패키지 초기화
    ├── main.py              # LangGraph 노드 진입점 (이 파일에서 에이전트 실행)
    ├── react_agent.py       # ReAct 루프 핵심 로직 + 진행 UI 관리
    ├── auth_context.py      # AuthContext — SLO 인증 정보 캐싱
    ├── tool_definitions.py  # OpenAI function calling 스키마 (도구 목록)
    ├── tool_registry.py     # 함수 이름 → 실제 구현 매핑 + _auth 자동 주입
    ├── prompts.py           # LLM 시스템 프롬프트
    ├── config.py            # 환경 설정 (API 키, 모델명 등)
    │
    ├── tools/               # 도구 구현 파일들
    │   ├── __init__.py
    │   ├── schedule_tools.py       # 일정 CRUD (4개 함수)
    │   ├── meeting_tools.py        # 회의실 관리 (7개 함수)
    │   ├── executive_tools.py      # 임원 일정 (1개 함수)
    │   ├── employee_tools.py       # 직원 검색 (1개, HTML 카드 반환)
    │   ├── approval_tools.py       # 전자결재 (4개 함수, HTML 반환)
    │   ├── draft_tools.py          # 문서/메일 초안 (2개 함수)
    │   ├── rag_tools.py            # 지식베이스 검색 (1개 함수)
    │   ├── translate_tools.py      # 번역 (1개 함수)
    │   ├── html_format_tools.py    # HTML 표/달력 변환 (5개 함수)
    │   ├── excel_tools.py          # Excel 다운로드 + 표 표시 (1개 함수)
    │   ├── user_tools.py           # 사용자 정보 (3개 함수)
    │   └── summary_tools.py        # 주간 요약 (1개 함수)
    │
    └── utils/               # 유틸리티
        ├── __init__.py
        ├── time_parser.py          # "내일", "오후 3시" 등 파싱
        └── date_validator.py       # 날짜/시간 검증
```

---

## 3. 핵심 파일 설명

### 3.1 `main.py` — 진입점

LangGraph 워크플로우에서 호출되는 노드 함수입니다. **수정할 일이 거의 없습니다.**

```python
async def llm(stat: LangGraphState, writer: StreamWriter):
    # 1. JustLLM, JustMessage, JustEnv 초기화
    # 2. ToolRegistry + TOOLS로 ReactAgent 생성
    # 3. agent.run(question, history) 실행
    # 4. 결과를 writer()로 SSE 스트림 전송
    # 5. DB에 저장 (update_answer)
```

### 3.2 `react_agent.py` — ReAct 루프 엔진

**도구를 추가할 때 수정하는 부분:**

| 위치 | 내용 | 수정 시점 |
|------|------|-----------|
| `TOOL_SENTENCE_ACTIVE` (dict) | 도구 실행 중 표시 문구 | 도구 추가 시 |
| `TOOL_SENTENCE_DONE` (dict) | 도구 실행 완료 표시 문구 | 도구 추가 시 |

**수정하지 않는 부분:**
- `ReactAgent` 클래스 — 도구 추가 시 건드릴 필요 없음
- `_execute_tool_calls()` — `html_content` 자동 감지 로직이 이미 구현되어 있음
- `_update_progress()`, `finalize_progress()` — 진행 UI 자동 관리

### 3.3 `tool_definitions.py` — 도구 스키마

OpenAI function calling 형식의 도구 정의입니다. **LLM이 이 스키마를 보고 어떤 도구를 호출할지 결정합니다.**

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "도구_이름",
            "description": "도구 설명 (LLM이 읽고 판단하므로 매우 중요!)",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "파라미터 설명"
                    }
                },
                "required": ["param1"]
            }
        }
    },
    # ... 다른 도구들
]
```

> **중요:** `description`은 LLM이 도구를 선택하는 유일한 기준입니다. 언제 사용해야 하는지, 언제 사용하면 안 되는지를 명확하게 작성하세요.

### 3.4 `tool_registry.py` — 함수 이름 ↔ 실제 구현 매핑 + 인증 주입

```python
class ToolRegistry:
    def __init__(self, auth=None):
        self._auth = auth  # AuthContext 인스턴스
        self._registry = {
            "get_schedule": schedule_tools.get_schedule,
            "format_data_as_table": html_format_tools.format_data_as_table,
            # ... 도구 이름: 실제 함수 참조 (총 30개)
        }

    async def dispatch(self, function_name, arguments):
        # auth가 있으면 _auth 파라미터를 자동 주입
        if self._auth:
            arguments = {**arguments, "_auth": self._auth}
        # async 함수 → await, sync 함수 → asyncio.to_thread
        func = self._registry[function_name]
        if asyncio.iscoroutinefunction(func):
            return await func(**arguments)
        else:
            return await asyncio.to_thread(func, **arguments)
```

> **참고:** `dispatch()`가 sync/async 함수를 자동 판별하므로 도구 구현 시 `def` 또는 `async def` 모두 사용 가능합니다.

### 3.5 `prompts.py` — 시스템 프롬프트

LLM의 행동 방침을 결정합니다. 도구 사용 규칙, 대화 스타일, 데이터 표시 형식 등을 정의합니다.

### 3.6 `auth_context.py` — 인증 컨텍스트

SLO(Single Log-On)를 1회 호출하여 인증 정보를 캐싱합니다. 모든 도구 호출에 `_auth` 파라미터로 자동 주입됩니다.

```python
class AuthContext:
    @classmethod
    async def from_stat(cls, stat) -> "AuthContext":
        # SLO XML API 1회 호출 → 사용자 정보 파싱
        ...

    # 속성: user_id, emp_code, dept_id, k, user_nm, docdept_nm, docdept_id, stat, is_authenticated
```

`main.py`에서 생성 → `ToolRegistry`에 전달 → `dispatch()` 시 `_auth=auth` 자동 주입:

```python
# main.py
auth = await AuthContext.from_stat(stat)
registry = ToolRegistry(auth=auth)
```

### 3.7 `tools/` — 도구 구현 파일

각 파일에 도메인별 함수들이 구현되어 있습니다. `dict`를 반환합니다.
함수는 `def` (동기) 또는 `async def` (비동기) 모두 가능합니다 — `ToolRegistry.dispatch()`가 자동 판별합니다.

#### 실제 API 연동 패턴 (`_auth=None`)

대부분의 도구 함수는 아래 패턴을 따릅니다:

```python
async def some_tool(param1, param2, _auth=None):
    # 1. 실제 API 호출 (인증 있을 때)
    if _auth and _auth.is_authenticated:
        try:
            result = await call_real_api(_auth.emp_code, param1, ...)
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"API 오류: {e}")

    # 2. 더미 데이터 (테스트 환경 또는 인증 없음)
    return {"status": "success", "data": dummy_data}
```

- `_auth=None` 기본값 → 인증 없이도 더미 데이터로 동작 (로컬 테스트)
- `ToolRegistry.dispatch()`가 `_auth`를 자동 주입하므로 함수 시그니처에만 선언하면 됨
- `_auth.is_authenticated`가 `True`이면 실제 GW API/DB 호출, 실패 시 더미로 폴백

---

## 4. 도구 추가 가이드 (Step by Step)

새로운 도구를 추가할 때 **반드시 아래 5개 파일을 수정**해야 합니다.

### 체크리스트

```
□ Step 1. tools/ 에 함수 구현
□ Step 2. tool_definitions.py 에 스키마 추가
□ Step 3. tool_registry.py 에 등록
□ Step 4. react_agent.py 에 TOOL_SENTENCE 추가
□ Step 5. prompts.py 에 사용 가이드 추가 (선택, 복잡한 도구만)
```

---

### Step 1. 함수 구현 (`tools/` 디렉토리)

기존 파일에 함수를 추가하거나, 새 파일을 만듭니다.

**기존 파일에 추가하는 경우:**
- 관련 도메인의 파일에 함수를 추가합니다.
- 예: 회의실 관련 → `meeting_tools.py`, 일정 관련 → `schedule_tools.py`

**새 파일을 만드는 경우:**
```python
# tools/my_new_tools.py

"""
새 도구 설명
"""

import logging

logger = logging.getLogger(__name__)


async def my_new_function(param1: str, param2: int = 0, _auth=None) -> dict:
    """
    함수 설명

    Args:
        param1: 파라미터 설명
        param2: 파라미터 설명 (기본값: 0)
        _auth: AuthContext (ToolRegistry가 자동 주입, 직접 전달 불필요)

    Returns:
        dict: 결과
    """
    # 1. 실제 API 호출 (인증 있을 때)
    if _auth and _auth.is_authenticated:
        try:
            result = await call_real_api(_auth.emp_code, param1, param2)
            return {
                "status": "success",
                "message": "처리 완료",
                "data": result
            }
        except Exception as e:
            logger.error(f"API 오류: {e}")

    # 2. 더미 데이터 (테스트 환경 또는 인증 없음)
    try:
        result = do_something(param1, param2)
        return {
            "status": "success",
            "message": "처리 완료",
            "data": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"오류 발생: {str(e)}"
        }
```

**규칙:**
- 반드시 `dict`를 반환
- `status` 필드 포함 (`"success"`, `"error"`, `"not_found"`, `"ask_user"`)
- 모든 파라미터에 기본값 권장 (LLM이 생략할 수 있으므로)
- `_auth=None` 파라미터 추가 — 실제 API 연동 시 필수 (3.6 패턴 참고)
- `def` 또는 `async def` 모두 가능 — ToolRegistry가 자동 판별
- 예외 처리 필수 (`try/except`)

---

### Step 2. 스키마 추가 (`tool_definitions.py`)

`TOOLS` 리스트에 OpenAI function calling 스키마를 추가합니다.

```python
# tool_definitions.py의 TOOLS 리스트 안에 추가

{
    "type": "function",
    "function": {
        "name": "my_new_function",     # Step 1에서 만든 함수 이름과 동일해야 함
        "description": """도구 설명을 여기에 작성합니다.

**사용 시나리오:**
- 언제 이 도구를 사용해야 하는지
- 구체적인 예시

**사용하면 안 되는 경우:**
- 다른 도구를 써야 하는 상황 명시

**예시:**
- "OOO 해줘" → 이 도구 사용""",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "파라미터 설명"
                },
                "param2": {
                    "type": "integer",
                    "description": "파라미터 설명 (선택, 기본값: 0)"
                }
            },
            "required": ["param1"]   # 필수 파라미터만
        }
    }
},
```

**description 작성 팁:**
- LLM은 이 설명만 보고 도구를 선택합니다. **구체적으로** 작성하세요.
- "사용해야 하는 경우"와 "사용하면 안 되는 경우"를 명확히 구분하세요.
- 비슷한 도구가 있으면 차이점을 명시하세요.
- 예시를 포함하면 LLM의 판단 정확도가 올라갑니다.

**parameters 타입:**
| JSON 타입 | Python 타입 | 예시 |
|-----------|-------------|------|
| `"string"` | `str` | `"안녕하세요"` |
| `"integer"` | `int` | `10` |
| `"number"` | `float` | `3.14` |
| `"boolean"` | `bool` | `true` |
| `"array"` | `list` | `[1, 2, 3]` |
| `"object"` | `dict` | `{"key": "value"}` |

---

### Step 3. 레지스트리 등록 (`tool_registry.py`)

**3-1. import 추가** (새 파일을 만든 경우):

```python
# tool_registry.py 상단
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools import (
    schedule_tools, meeting_tools, ...,
    my_new_tools  # ← 추가
)
```

> 기존 파일에 함수를 추가한 경우 import는 이미 되어 있으므로 이 단계는 건너뜁니다.

**3-2. _registry에 매핑 추가:**

```python
self._registry = {
    # ... 기존 도구들 ...

    # My new tools (1) ⭐ NEW
    "my_new_function": my_new_tools.my_new_function,  # ← 추가
}
```

**3-3. 도구 수 주석 업데이트:**

```python
def __init__(self, auth=None):
    """Initialize the registry with all 31 tools (이전 수 + 추가 수)."""
```

> **주의:** `name` 값은 `tool_definitions.py`의 `"name"` 필드, 그리고 함수의 실제 이름과 **모두 동일**해야 합니다.

---

### Step 4. 진행 문구 추가 (`react_agent.py`)

도구가 실행될 때 사용자에게 보여주는 진행 UI 문구입니다.

```python
# 실행 중 문구 (TOOL_SENTENCE_ACTIVE dict에 추가)
"my_new_function": "새 작업을 처리하고 있습니다",

# 실행 완료 문구 (TOOL_SENTENCE_DONE dict에 추가)
"my_new_function": "새 작업을 처리했습니다",
```

**문구 작성 규칙:**
- ACTIVE: `"~하고 있습니다"` (현재 진행형)
- DONE: `"~했습니다"` (완료형)
- 간결하게 작성 (한 줄, 20자 이내 권장)

---

### Step 5. 시스템 프롬프트 업데이트 (`prompts.py`) — 선택

단순한 도구는 `tool_definitions.py`의 description만으로 충분합니다.
아래 경우에만 `prompts.py`를 수정하세요:

- **복잡한 사용 규칙**이 있는 경우 (예: "5건 이상이면 표로 보여주기")
- **다른 도구와 연계**하는 경우 (예: "조회 후 format_data_as_table 호출")
- **데이터 변환이 필요**한 경우 (예: "중첩 구조를 flat하게 변환")
- **도구 목록 카운트** 업데이트 (현재 `30개 함수`)
- **도구 목록**에 추가 (카테고리별 함수 리스트)

```python
# prompts.py의 get_system_prompt() 함수 안에서 수정

# 1. 도구 수 업데이트
**📋 업무 도구 (30개 함수 사용 가능):**

# 2. 카테고리에 추가
10. 새 카테고리: my_new_function

# 3. 사용 규칙 추가 (필요시)
**새 도구 사용 규칙:**
- 언제 사용하는지
- 데이터 전달 방법
- 예시
```

---

## 5. 도구 반환값 패턴

### 패턴 A: 일반 데이터 반환 (기본)

LLM이 결과를 받아서 텍스트로 답변을 생성합니다.

```python
def get_something(query: str) -> dict:
    return {
        "status": "success",
        "message": "조회 완료",
        "data": [
            {"name": "김철수", "dept": "AI팀"},
            {"name": "이영희", "dept": "개발팀"},
        ],
        "total_count": 2
    }
```

→ LLM이 data를 읽고 자연어로 답변: "김철수님(AI팀), 이영희님(개발팀) 2명을 찾았습니다."

### 패턴 B: HTML 렌더링 반환 (시각적 UI)

`html_content` 키가 있으면 `react_agent.py`가 **자동으로** SSE 스트림에 직접 전송합니다.
LLM에게는 `text_summary`만 전달됩니다.

```python
def format_something(data: list) -> dict:
    html = "<div>... 예쁜 HTML ...</div>"

    return {
        "status": "success",
        "html_content": html,             # ← 이 키가 있으면 자동 스트림 전송
        "text_summary": "요약 텍스트",     # ← LLM 참조용 (후속 질문 대응)
    }
```

→ 사용자 화면에 HTML이 바로 표시됨
→ LLM은 "HTML로 화면에 표시 완료" + text_summary만 받음
→ LLM이 같은 데이터를 텍스트로 다시 나열하지 않음

**html_content 자동 처리 흐름 (react_agent.py 410~424행):**

```
도구 반환값에 html_content 존재?
  ├─ Yes → writer()로 SSE 스트림에 ```html 블록 전송
  │        _html_blocks에 누적 (DB 저장용)
  │        LLM에게는 text_summary만 전달
  │
  └─ No  → 일반 JSON으로 LLM에게 전달
```

### 패턴 C: 사용자 확인 필요

결과가 애매하거나 선택이 필요할 때:

```python
def find_employee(name: str) -> dict:
    results = search(name)
    if len(results) > 5:
        return {
            "status": "ask_user",
            "message": f"'{name}'으로 {len(results)}명이 검색되었습니다. 부서나 팀을 추가로 알려주세요.",
            "total_count": len(results)
        }
```

---

## 6. HTML 렌더링 도구 만들기

HTML UI를 반환하는 도구를 만들 때의 가이드입니다.

### 디자인 시스템

기존 도구들이 사용하는 공통 스타일:

```css
/* 폰트 */
font-family: 'Pretendard', 'Apple SD Gothic Neo', 'Malgun Gothic', -apple-system, sans-serif;

/* 색상 팔레트 (Slate 계열) */
--slate-900: #0f172a;   /* 가장 진한 배경 */
--slate-800: #1e293b;   /* 헤더 그라디언트 시작 */
--slate-700: #334155;   /* 헤더 그라디언트 끝 */
--slate-600: #475569;   /* 테이블 헤더 텍스트 */
--slate-500: #64748b;   /* 보조 텍스트 */
--slate-400: #94a3b8;   /* 약한 텍스트 */
--slate-200: #e2e8f0;   /* 구분선 */
--slate-100: #f1f5f9;   /* 테이블 헤더 배경, 짝수행 */
--slate-50:  #f8fafc;   /* 홀수행 배경 */

/* 헤더 그라디언트 */
background: linear-gradient(135deg, #1e293b 0%, #334155 100%);

/* 테이블 기본 */
border-radius: 14px;
box-shadow: 0 4px 20px rgba(0,0,0,0.08);
overflow: hidden;
```

### HTML 반환 구조

```python
def my_html_tool(data: list) -> dict:
    # 1. HTML 생성
    html = """
<div style="font-family:'Pretendard',...; max-width:100%; border-radius:14px; overflow:hidden;
            box-shadow:0 4px 20px rgba(0,0,0,0.08); background:#fff; margin:8px 0;">
  <!-- 헤더 -->
  <div style="background:linear-gradient(135deg,#1e293b,#334155); color:#fff; padding:12px 18px;">
    <span style="font-size:1.1em; font-weight:700;">제목</span>
    <span style="font-size:0.85em; color:#94a3b8; margin-left:10px;">총 N건</span>
  </div>
  <!-- 내용 -->
  <div style="...">
    ...
  </div>
</div>
"""

    # 2. 텍스트 요약 (LLM 참조용)
    text_summary = "- 항목1\n- 항목2\n..."

    # 3. 반환 (html_content 키 필수!)
    return {
        "status": "success",
        "html_content": html,
        "text_summary": text_summary,
    }
```

### 프론트엔드에서의 렌더링

`react_agent.py`가 html_content를 감지하면 아래 형식으로 SSE에 전송합니다:

```
\n```html\n{html_content}\n```\n
```

프론트엔드의 `MarkdownViewer`가 ` ```html ` 블록을 감지하면 `RenderableCodeBlock` 컴포넌트에서
`dangerouslySetInnerHTML`로 직접 렌더링합니다.

**따라서:**
- JavaScript를 포함하면 안 됩니다 (`<script>` 태그 불가)
- 인라인 스타일만 사용하세요 (`style="..."`)
- `<style>` 태그는 scoped가 아니므로 전역 오염 주의
- CSS `:has()`, `<details>/<summary>`, `<input type="checkbox">` 등 순수 HTML/CSS 기능은 사용 가능

---

## 7. 시스템 프롬프트 수정 가이드

### 프롬프트 구조 (`prompts.py`)

```python
def get_system_prompt():
    return f"""
    ━━━ 역할 정의 ━━━
    대화 스타일, 이모지 사용법, 자연스러운 표현

    ━━━ 도구 목록 ━━━
    27개 함수 카테고리별 나열

    ━━━ 대화 흐름 가이드 ━━━
    멀티턴 대화 규칙, 재호출 기준

    ━━━ HTML 표시 규칙 ━━━
    5개 이상 → 표/달력 제안
    4개 이하 → 텍스트

    ━━━ 범용 표 도구 규칙 ━━━
    format_data_as_table 사용법

    ━━━ JSON 구조 설명 ━━━
    각 도구의 반환값 구조 + 표시 형식

    ━━━ 상황 인지 ━━━
    프로액티브 제안 규칙

    ━━━ 금지/필수 사항 ━━━
    """
```

### 수정 시 주의

- `f-string` 안에서 중괄호 `{}`를 리터럴로 쓰려면 `{{}}` 이중 중괄호 사용
- 프롬프트가 너무 길면 LLM 성능이 떨어질 수 있음 (토큰 비용도 증가)
- 새 도구의 JSON 구조 예시를 추가하면 LLM의 결과 해석 정확도가 올라감

---

## 8. 테스트 및 디버깅

### Dynamic Reload (개발 시 필수)

```bash
# 코드 변경 시 서버 재시작 없이 자동 반영
./dynamic_reload.sh on

# 프로덕션에서는 반드시 끄기 (성능)
./dynamic_reload.sh off

# 상태 확인
./dynamic_reload.sh status
```

`dynamic_reload.sh on` 상태에서는 `node_agent/`와 `lib_justtype/` 모듈이 매 요청마다 재로드됩니다.
도구 코드를 수정하면 다음 채팅 메시지부터 바로 반영됩니다.

### 로그 확인

```bash
# 서버 로그에서 ReactAgent 관련 로그 확인
# 로그 레벨: INFO
# 로그 접두사: [ReactAgent]

# 주요 로그 포인트:
# [ReactAgent] run() 시작 | 질문: ... | history 길이: ...
# [ReactAgent] LLM 응답 수신 | tool_calls 수: ... | content 길이: ...
# [ReactAgent] 도구 실행: {이름} | args: {인자}
# [ReactAgent] 도구 결과: {이름} → {결과 요약}
# [ReactAgent] html_content 감지 → 스트림에 직접 출력
```

### 디버깅 팁

1. **도구가 호출되지 않을 때:**
   - `tool_definitions.py`의 description 확인 — LLM이 판단하기 충분한 설명인지
   - `tool_registry.py`에 등록했는지 확인
   - 비슷한 도구가 있어서 LLM이 다른 도구를 선택하고 있는지 확인

2. **도구가 에러를 반환할 때:**
   - 서버 로그에서 `[ReactAgent] 도구 실행 오류` 확인
   - `ToolRegistry.dispatch()`의 에러 핸들링이 상세 메시지를 반환함

3. **HTML이 표시되지 않을 때:**
   - 반환값에 `"html_content"` 키가 있는지 확인 (오타 주의!)
   - 프론트엔드에서 ` ```html ` 블록을 `RenderableCodeBlock`이 렌더링하는지 확인

4. **LLM이 잘못된 파라미터로 호출할 때:**
   - `tool_definitions.py`의 파라미터 description을 더 구체적으로 작성
   - `required` 배열에 필수 파라미터가 포함되어 있는지 확인

---

## 9. 실전 예제: 처음부터 끝까지

### 예제: "공지사항 검색" 도구 추가

사용자가 "최근 공지사항 알려줘"라고 하면 사내 공지사항을 검색하는 도구를 추가한다고 가정합니다.

---

#### Step 1. 함수 구현

```python
# tools/notice_tools.py (새 파일 생성)

"""
사내 공지사항 검색 도구
"""

from datetime import datetime


def search_notices(keyword: str = None, category: str = None,
                   date_from: str = None, date_to: str = None,
                   limit: int = 10) -> dict:
    """
    사내 공지사항을 검색합니다.

    Args:
        keyword: 검색 키워드
        category: 공지 분류 (전체, 인사, 총무, IT 등)
        date_from: 검색 시작일 (YYYY-MM-DD)
        date_to: 검색 종료일 (YYYY-MM-DD)
        limit: 최대 결과 수 (기본 10)

    Returns:
        dict: 검색 결과
    """
    try:
        # TODO: 실제 API 연동
        # response = api.search_notices(keyword=keyword, ...)

        # 더미 데이터
        today = datetime.now().strftime("%Y-%m-%d")
        mock_notices = [
            {
                "num": "1",
                "title": "2026년 상반기 인사이동 안내",
                "category": "인사",
                "author": "인사팀",
                "date": today,
                "views": 342,
                "important": True
            },
            {
                "num": "2",
                "title": "사내 네트워크 점검 안내 (3/8 토요일)",
                "category": "IT",
                "author": "정보보안팀",
                "date": today,
                "views": 128,
                "important": False
            },
            {
                "num": "3",
                "title": "직원 건강검진 일정 안내",
                "category": "총무",
                "author": "총무팀",
                "date": today,
                "views": 89,
                "important": False
            },
        ]

        # 키워드 필터링
        if keyword:
            mock_notices = [n for n in mock_notices if keyword in n["title"]]

        # 카테고리 필터링
        if category:
            mock_notices = [n for n in mock_notices if category in n["category"]]

        return {
            "status": "success",
            "message": f"공지사항 {len(mock_notices)}건을 찾았습니다.",
            "notices": mock_notices[:limit],
            "total_count": len(mock_notices)
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"공지사항 검색 중 오류: {str(e)}"
        }
```

---

#### Step 2. 스키마 추가

```python
# tool_definitions.py의 TOOLS 리스트에 추가

{
    "type": "function",
    "function": {
        "name": "search_notices",
        "description": """사내 공지사항을 검색합니다.

**사용 시나리오:**
- "최근 공지사항 알려줘"
- "인사 관련 공지 있어?"
- "이번 주 공지사항 보여줘"

**반환 데이터:** 제목, 분류, 작성자, 날짜, 조회수, 중요 여부""",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "검색 키워드 (제목에서 검색)"
                },
                "category": {
                    "type": "string",
                    "description": "공지 분류 (전체, 인사, 총무, IT, 경영 등)"
                },
                "date_from": {
                    "type": "string",
                    "description": "검색 시작일 (YYYY-MM-DD)"
                },
                "date_to": {
                    "type": "string",
                    "description": "검색 종료일 (YYYY-MM-DD)"
                },
                "limit": {
                    "type": "integer",
                    "description": "최대 결과 수 (기본 10)"
                }
            },
            "required": []
        }
    }
},
```

---

#### Step 3. 레지스트리 등록

```python
# tool_registry.py

# 상단 import에 추가
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools import (
    ..., notice_tools  # ← 추가
)

# _registry에 추가
"search_notices": notice_tools.search_notices,
```

---

#### Step 4. 진행 문구 추가

```python
# react_agent.py

# TOOL_SENTENCE_ACTIVE에 추가
"search_notices": "공지사항을 검색하고 있습니다",

# TOOL_SENTENCE_DONE에 추가
"search_notices": "공지사항을 검색했습니다",
```

---

#### Step 5. 프롬프트 업데이트

```python
# prompts.py

# 도구 수 업데이트
**📋 업무 도구 (30개 함수 사용 가능):**

# 카테고리에 추가
10. 공지사항: search_notices
```

---

#### 완성! 동작 확인

```
사용자: "최근 공지사항 알려줘"

→ LLM 판단: search_notices() 호출
→ ToolRegistry: notice_tools.search_notices() 실행
→ 결과: {"status": "success", "notices": [...], "total_count": 3}
→ LLM 답변: "최근 공지사항 3건을 찾았어요! 📋
   1. [중요] 2026년 상반기 인사이동 안내 (인사팀, 조회 342)
   2. 사내 네트워크 점검 안내 (정보보안팀, 조회 128)
   3. 직원 건강검진 일정 안내 (총무팀, 조회 89)"
```

---

## 10. 주의사항 및 FAQ

### 이름 일치 규칙 (가장 흔한 실수!)

아래 3곳의 이름이 **정확히 동일**해야 합니다:

```
tool_definitions.py  →  "name": "my_function"
tool_registry.py     →  "my_function": module.my_function
tools/module.py      →  def my_function(...):
```

하나라도 다르면 "Function not found" 에러가 발생합니다.

### 파라미터 이름 일치

`tool_definitions.py`의 `properties` 키 이름과 함수의 매개변수 이름이 동일해야 합니다:

```python
# tool_definitions.py
"properties": {
    "meeting_room": { ... }   # ← 이 이름
}

# tools/my_tools.py
def my_function(meeting_room: str):   # ← 이 이름과 동일해야 함
    ...
```

### 새 파일 import 누락

새 파일을 만들었는데 import를 안 하면 서버가 시작될 때는 에러가 안 나지만, 도구 호출 시 `ModuleNotFoundError`가 발생합니다.

```python
# tool_registry.py 상단의 import에 반드시 추가!
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools import (
    ..., my_new_tools
)
```

### 병렬 도구 호출 (Parallel Tool Calls)

OpenAI API는 한 번의 LLM 응답에서 **여러 도구를 동시에 호출**할 수 있습니다.
예: "8층 영상회의실이랑 대회의실 예약 현황"
→ `get_meeting_rooms(meetingroom="8층 영상회의실")` + `get_meeting_rooms(meetingroom="대회의실")` 동시 호출

`react_agent.py`가 자동으로 모든 tool_calls를 처리하므로, 도구 개발 시 특별히 신경 쓸 필요는 없습니다.

### 도구 반환값 크기

- 반환값이 너무 크면 LLM 컨텍스트 윈도우를 초과할 수 있습니다.
- `text_summary`는 50행/5열 이내로 제한하는 것을 권장합니다.
- HTML은 크기 제한이 없지만, SSE 스트림 성능을 고려하세요.

### 기존 도구 수정 시

기존 도구의 **반환값 구조를 변경**하면 프롬프트의 JSON 구조 설명도 함께 업데이트해야 합니다.
파라미터를 추가할 때는 반드시 **기본값**을 설정해서 기존 호출이 깨지지 않게 하세요.

### 도구 간 의존성

한 도구의 결과를 다른 도구에 전달하는 패턴:

```
get_executive_schedule() → 결과를 LLM이 가공 → format_data_as_table(data=가공된_데이터)
```

이 경우 LLM이 중간에서 데이터를 변환합니다. 도구끼리 직접 호출하지 않습니다.

---

## 부록: 현재 등록된 도구 목록 (30개)

| # | 카테고리 | 함수명 | 파일 | 반환 패턴 | API 연동 |
|---|----------|--------|------|-----------|----------|
| 1 | 일정 | `get_schedule` | schedule_tools.py | 일반 | ✅ |
| 2 | 일정 | `create_schedule` | schedule_tools.py | 일반 | ✅ |
| 3 | 일정 | `update_schedule` | schedule_tools.py | 일반 | ✅ |
| 4 | 일정 | `delete_schedule` | schedule_tools.py | 일반 | ✅ |
| 5 | 회의실 | `get_meeting_room_list` | meeting_tools.py | 일반 | ✅ |
| 6 | 회의실 | `reserve_meeting_room` | meeting_tools.py | 일반 | ✅ |
| 7 | 회의실 | `get_meeting_rooms` | meeting_tools.py | 일반 | ✅ |
| 8 | 회의실 | `update_meeting_room` | meeting_tools.py | 일반 | 더미 |
| 9 | 회의실 | `cancel_meeting_room` | meeting_tools.py | 일반 | ✅ |
| 10 | 회의실 | `find_available_room` | meeting_tools.py | 일반 | 더미 |
| 11 | 회의실 | `get_all_meeting_rooms` | meeting_tools.py | 일반 | 더미 |
| 12 | 임원 | `get_executive_schedule` | executive_tools.py | 일반 | ✅ |
| 13 | 직원 | `find_employee` | employee_tools.py | HTML | ✅ |
| 14 | 결재 | `get_approval_form` | approval_tools.py | HTML | ✅ |
| 15 | 결재 | `get_my_approvals` | approval_tools.py | 일반 | 더미 |
| 16 | 결재 | `approve_document` | approval_tools.py | 일반 | 더미 |
| 17 | 결재 | `reject_document` | approval_tools.py | 일반 | 더미 |
| 18 | 문서 | `draft_email` | draft_tools.py | 일반 | 더미 |
| 19 | 문서 | `draft_document` | draft_tools.py | 일반 | 더미 |
| 20 | 검색 | `search_knowledge_base` | rag_tools.py | 일반 | 더미 |
| 21 | 번역 | `translate_text` | translate_tools.py | 일반 | 더미 |
| 22 | HTML | `format_schedule_as_calendar` | html_format_tools.py | HTML | — |
| 23 | HTML | `format_schedule_as_table` | html_format_tools.py | HTML | — |
| 24 | HTML | `format_meeting_rooms_as_calendar` | html_format_tools.py | HTML | — |
| 25 | HTML | `format_meeting_rooms_as_table` | html_format_tools.py | HTML | — |
| 26 | HTML | `format_data_as_table` | html_format_tools.py | HTML | — |
| 27 | Excel | `format_data_as_excel` | excel_tools.py | HTML | — |
| 28 | 사용자 | `get_my_info` | user_tools.py | 일반 | ✅ |
| 29 | 사용자 | `get_my_team` | user_tools.py | 일반 | ✅ |
| 30 | 사용자 | `get_next_schedule` | user_tools.py | 일반 | 더미 |
| 31 | 요약 | `get_weekly_summary` | summary_tools.py | 일반 | 더미 |

> **반환 패턴:** "일반" = LLM이 텍스트로 답변 생성, "HTML" = `html_content`를 SSE 스트림으로 직접 전송
> **API 연동:** ✅ = 실제 GW API/DB 연동 완료, "더미" = 더미 데이터만, "—" = 데이터 변환 도구 (API 불필요)
