# Function Calling 작업 로그

## 1. 개요

ReAct Agent 시스템의 도구(tools) 함수들을 실제 그룹웨어 API에 연결하고,
더미 데이터를 실제 API 응답 형식에 맞춰 정리하는 작업을 수행함.

작업 일자: 2026-03-07
작업 범위: `react_system/` 하위 전체

---

## 2. 완료된 작업

### 2-1. AuthContext + ToolRegistry 패턴 구현

**목적**: 각 tool 함수에서 실제 DB/API를 호출할 수 있도록 인증 정보를 자동 주입

**AuthContext** (`react_system/auth_context.py`)
- `AuthContext.from_stat(stat)` 로 SLO 1회 호출하여 인증 정보 캐싱
- 속성: `user_id`, `emp_code`, `dept_id`, `k`, `user_nm`, `docdept_nm`, `docdept_id`, `stat`, `is_authenticated`

**ToolRegistry** (`react_system/tool_registry.py`)
- `dispatch(func_name, args, auth_context)` 에서 `_auth` 파라미터를 자동 주입
- 모든 tool 함수는 `_auth=None` 기본값으로 선언 → 인증 없으면 더미 데이터 반환

**적용된 tool 함수 패턴:**
```python
async def some_tool(param1, param2, _auth=None):
    # 1. 실제 API 호출 (인증 있을 때)
    if _auth and _auth.is_authenticated:
        try:
            # DB/API 호출
            ...
        except Exception as e:
            logger.error(f"API 오류: {e}")

    # 2. 더미 데이터 (테스트 환경 또는 인증 없음)
    return { "status": "success", ... }
```

### 2-2. 실제 API 연동 (DB 조회 + GW API 호출)

아래 tool 함수들에 실제 API 호출 코드 추가:

| 파일 | 함수 | 연동 방식 |
|------|------|-----------|
| `tools/schedule_tools.py` | `get_schedule` | `calendar.py` → GW XML API → `xml_parsing_search()` |
| `tools/schedule_tools.py` | `create_schedule` | `calendar.py` → GW XML API → `xml_parsing_insert()` |
| `tools/schedule_tools.py` | `update_schedule` | `calendar.py` → GW XML API → `xml_parsing_result_message()` |
| `tools/schedule_tools.py` | `delete_schedule` | `calendar.py` → GW XML API → `xml_parsing_result_message()` |
| `tools/meeting_tools.py` | `get_meeting_room_list` | `OracleSearchClient.meetingroom_db_list()` |
| `tools/meeting_tools.py` | `get_meeting_rooms` | `meeting.py` → GW XML API → `xml_parsing_meetingroom()` |
| `tools/meeting_tools.py` | `reserve_meeting_room` | `meeting.py` → GW XML API → `xml_parsing_meeting_insert()` |
| `tools/meeting_tools.py` | `cancel_meeting_room` | `meeting.py` → GW XML API → `xml_parsing_result_message()` |
| `tools/employee_tools.py` | `find_employee` | `OracleSearchClient` (이름/사번/이메일/부서/팀 검색) |
| `tools/executive_tools.py` | `get_executive_schedule` | DB API (`get_imwon_sch_name` / `get_imwon_sch_pos`) |
| `tools/approval_tools.py` | `get_approval_form` | `OracleSearchClient.document_search()` + 양식 URL 생성 |
| `tools/user_tools.py` | `get_my_info` | `OracleSearchClient.search_by_empcode()` |
| `tools/user_tools.py` | `get_my_team` | `OracleSearchClient.search_by_team()` / `search_by_dept()` |

### 2-3. 더미 데이터를 실제 API 응답 형식에 맞춰 수정

**기준**: `xml_parsing.py`의 파싱 결과 형식 (실제 API가 반환하는 최종 구조)

#### 실제 API 반환 형식 (xml_parsing.py 기준)

```
xml_parsing_search():        [{title, description, start_date, end_date, event_id, owner_name, num, calendar_nm}]
xml_parsing_insert():        [{title, description, start_date, end_date, event_id, owner_name, calendar_nm(list)}]
xml_parsing_meetingroom():   [{title, description, start_date, end_date, event_id, owner_name, num, owner_id, phone, meetingroom}]
xml_parsing_meeting_insert():{message, meetingroom, title, description, start_date, end_date, owner_name, event_id, phone}
xml_parsing_result_message(): str ("성공하였습니다.", "중복되었습니다." 등)
```

날짜 형식: `"YYYY.MM.DD HH:MM"` (xml_parsing에서 파싱)

#### 파일별 수정 내역

**1) `tools/schedule_tools.py` — create_schedule 더미**

| 변경 전 | 변경 후 |
|---------|---------|
| `start_dt` / `end_dt` (키명) | `start_date` / `end_date` |
| ISO 형식 (`2026-03-07T14:00`) | `"2026.03.07 14:00"` |
| `num` 필드 | 제거 |
| — | `event_id`: `"EVT-DUMMY-001"` 추가 |
| — | `owner_name`: `"홍길동"` 추가 |
| `calendar_name` (문자열) | `calendar_nm` (리스트) |

**2) `tools/meeting_tools.py` — 4개 함수**

- **get_meeting_room_list**: `room_id`, `floor`, `capacity`, `facilities`, `has_screen`, `has_video` 제거 → `room_name`, `location`만 유지 (7개 회의실)
- **reserve_meeting_room**: `num`, `calendar_name` 제거, `event_id` 추가, `start_dt`/`end_dt` 날짜 형식 변경
- **get_meeting_rooms**: 중첩 dict(`{capacity, floor, facilities, reservations}`) → flat 리스트로 변경. 각 예약에 `event_id`, `owner_id`, `phone` 추가
- **cancel_meeting_room**: `cancelled` dict 제거 → 메시지만 반환 (실제 API와 동일)

**3) `tools/employee_tools.py` — find_employee 더미**

- 모든 더미 직원(16명)에서 `location`, `phone` 필드 제거 (실제 DB에 없는 필드)
- `_build_employee_text_summary()`: `location` 참조 제거
- 더미 데이터 location 필터: `"location" in df.columns` 가드 추가
- 최종 필드: `empno, empname, position, dept, team, duty, email, ext, fax, mobile`

**4) `tools/executive_tools.py` — get_executive_schedule 더미**

- **executive**: `dept`, `email`, `phone`, `ext` 제거 → `name`, `position`만 유지
- **schedule**: `location`, `description`, `status` 제거
- **날짜 형식**: `f"{query_date}T09:00:00"` → `f"{query_date} 09:00"` (T 제거, 초 제거)
- `date` 필드 추가 (`query_date` 값)

**5) `tools/approval_tools.py` — get_approval_form 더미**

- 반환 구조: `{"form": 단일 dict}` → `{"forms": 배열, "html_content", "text_summary"}`
- 각 양식에서 `fields`, `approvers` 제거
- `description`, `form_url` 추가 (더미 URL)
- HTML 테이블 생성 코드 추가 (실제 API와 동일한 형식)

**6) `tools/user_tools.py`**

- **get_my_info 더미**: `ext` 제거, `mobile`, `fax`, `duty` 추가
- **get_my_team 더미**: 각 member에 `mobile` 추가

**7) `react_system/prompts.py` — 가이드 추가**

- 일정 JSON 구조에 `event_id` 필드 추가 (수정/삭제 시 필수)
- 새 섹션 추가: "일정 수정/삭제 시 필수 절차"
  - 수정/삭제 전 반드시 `get_schedule()`로 조회하여 `event_id` 확인
  - 이전 대화 참조 시 히스토리에서 `event_id` 확인
  - `event_id` 모르면 사용자에게 확인 후 조회

---

## 3. 일정 수정/삭제 처리 방식 (설계 결정)

### 문제
- 사용자가 event_id를 모르는 상태에서 "일정 바꿔줘", "아까 등록한 거 취소해줘" 요청

### 결정: LLM(ReAct Agent)에 위임

도구(tool)를 복잡하게 만들지 않고, LLM이 자연스럽게 2단계로 처리:

```
1단계: get_schedule() 호출 → event_id 확인
2단계: update_schedule(event_id=...) 또는 delete_schedule(event_id=...) 호출
```

- "회의일정 바꿔줘" → LLM이 "어떤 일정을 변경하시겠어요?" 자연어로 확인
- "아까 등록한 거 취소해줘" → LLM이 대화 히스토리에서 event_id 찾아서 처리
- prompts.py에 가이드 추가하여 LLM이 이 패턴을 따르도록 유도

---

## 4. 검증 결과

아래 테스트 스크립트로 모든 더미 데이터 형식 검증 완료:

```bash
ENV_TYPE=local python -c "
import asyncio, json
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools.schedule_tools import create_schedule
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools.meeting_tools import get_meeting_room_list, get_meeting_rooms, reserve_meeting_room
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools.employee_tools import find_employee
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools.executive_tools import get_executive_schedule
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools.approval_tools import get_approval_form
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools.user_tools import get_my_info, get_my_team

async def test():
    for name, coro in [
        ('create_schedule', create_schedule(title='테스트', date='2026-03-07', start_time='14:00', end_time='15:00')),
        ('get_meeting_room_list', get_meeting_room_list()),
        ('get_meeting_rooms', get_meeting_rooms(meetingroom='8층 영상회의실', date='2026-03-07')),
        ('reserve_meeting_room', reserve_meeting_room(meetingroom='8층 대회의실', title='테스트', date='2026-03-07', start_time='14:00', end_time='15:00')),
        ('find_employee', find_employee(name='홍길동')),
        ('get_executive_schedule', get_executive_schedule(executive_name='김태영')),
        ('get_approval_form', get_approval_form(form_name='지출결의서')),
        ('get_my_info', get_my_info()),
        ('get_my_team', get_my_team()),
    ]:
        r = await coro
        print(f'=== {name} ===')
        print(json.dumps(r, ensure_ascii=False, indent=2)[:600])
        print()
asyncio.run(test())
"
```

---

## 5. 수정된 파일 목록

```
react_system/
├── auth_context.py          # AuthContext 클래스 (신규)
├── tool_registry.py         # _auth 자동 주입 (수정)
├── prompts.py               # event_id + 수정/삭제 가이드 추가
├── tools/
│   ├── schedule_tools.py    # 실제 API 연동 + 더미 형식 수정
│   ├── meeting_tools.py     # 실제 API 연동 + 더미 형식 수정 (4함수)
│   ├── employee_tools.py    # 실제 API 연동 + 더미 형식 수정 (location/phone 제거)
│   ├── executive_tools.py   # 실제 API 연동 + 더미 형식 수정
│   ├── approval_tools.py    # 실제 API 연동 + 더미 형식 수정
│   └── user_tools.py        # 실제 API 연동 + 더미 형식 수정
```

---

## 6. 미완료 / 향후 작업

- [ ] `find_available_room` 실제 API 연동 (현재 더미만)
- [ ] `update_meeting_room` 실제 API 연동
- [ ] `get_my_approvals`, `approve_document`, `reject_document` 실제 GW API 연동 (현재 TODO 상태)
- [ ] `draft_email`, `draft_document` 실제 연동
- [ ] `search_knowledge_base` RAG 파이프라인 연동
- [ ] `get_weekly_summary` 구현
- [ ] Rerank 모델 연동 (employee_tools.py 내 TODO 주석 참조)
- [ ] 실제 서버 환경에서 E2E 테스트 (DB/API 연결 상태)
