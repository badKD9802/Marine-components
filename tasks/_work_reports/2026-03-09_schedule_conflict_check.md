# 일정 등록 시 충돌 확인 + Quick Reply 버튼 기능

> 작성일: 2026-03-09 | 카테고리: feat

## 배경
일정 등록(`create_schedule`) 시 해당 시간에 기존 일정이 있어도 그대로 등록되는 문제.
사용자에게 "해당 시간에 일정이 있는데 등록하시겠습니까?" 확인 후 클릭 가능한 버튼을 제공하도록 요청됨.

## 변경 사항

| 파일 | 변경 내용 |
|------|----------|
| `react_system/tools/schedule_tools.py` | `_check_time_overlap()` 헬퍼 추가, `create_schedule()`에 `force` 파라미터 + 충돌 확인 로직 추가 |
| `react_system/tool_definitions.py` | `create_schedule` 스키마에 `force` boolean 파라미터 + 충돌 관련 description 추가 |
| `react_system/main.py` | `<!--QUICK_REPLY_YES:-->`, `<!--QUICK_REPLY_NO:-->` 마커 파싱 + `ButtonInfoSchema` 생성 로직 추가 |
| `react_system/prompts.py` | 충돌 시 QUICK_REPLY 마커 사용 가이드 추가 (LLM 행동 지침) |
| `CLAUDE.md` | `수행 내역 자동 저장` 섹션 추가 (`app/tasks/_work_reports/`) |

## 핵심 코드

### 충돌 확인 (`schedule_tools.py`)
```python
def _check_time_overlap(existing_schedules, new_start, new_end):
    """시간 겹침 조건: new_start < s_end AND new_end > s_start"""
    conflicts = []
    for s in existing_schedules:
        s_start_time = s.get("start_date", "").split(" ")[1]
        s_end_time = s.get("end_date", "").split(" ")[1]
        if new_start < s_end_time and new_end > s_start_time:
            conflicts.append(s)
    return conflicts
```

`create_schedule(force=False)` → 내부에서 `get_schedule()` 호출 → `_check_time_overlap()` → 충돌 시 `status: "conflict"` 반환

### Quick Reply 버튼 (`main.py`)
```python
_QUICK_REPLY_YES_RE = re.compile(r"<!--QUICK_REPLY_YES:(.+?)-->")
_QUICK_REPLY_NO_RE = re.compile(r"<!--QUICK_REPLY_NO:(.+?)-->")
```

기존 `ChatIntentSuggest` 프론트엔드 컴포넌트를 재사용:
- YES 버튼 → `name="intent_switch"` (보라색), `value_type="llm_question"`
- NO 버튼 → `name="intent_keep"` (회색), `value_type="llm_question"`
- 클릭 시 버튼 텍스트가 `llm_question`으로 전송 → ReAct 에이전트가 처리

### 대화 플로우
```
사용자: "내일 2시에 회의 등록해줘"
  → create_schedule(title="회의", date="내일", start_time="14:00", end_time="15:00")
  → status: "conflict" (기존 일정 발견)
  → LLM 응답: "⚠️ 해당 시간에 이미 일정이 있어요!..." + QUICK_REPLY 마커
  → 버튼 2개 표시: [네, 등록해주세요 ✅] [아니요, 다른 시간에 등록할게요 🔄]

[버튼1 클릭] → "네, 등록해주세요" 전송 → create_schedule(force=true) → 등록 완료
[버튼2 클릭] → "아니요, 다른 시간에 등록할게요" 전송
  → LLM: "해당 날짜의 빈 시간: 🟢 09:00~10:00, 🟢 15:00~16:00 ..." (available_slots 활용)
  → 사용자: "3시에" → create_schedule(이전 title/desc 유지, start_time="15:00") → 등록 완료
```

### 빈 시간 계산 (`_find_available_slots`)
```python
def _find_available_slots(all_schedules, start_hour=8, end_hour=22):
    """하루 일정에서 빈 시간 슬롯을 찾습니다. (1시간 단위, 08:00~22:00)"""
    occupied = set()
    for s in all_schedules:
        sh = int(s_start.split(":")[0])
        eh = int(s_end.split(":")[0])
        if em > 0: eh += 1  # 14:30 끝나면 14시도 occupied
        for h in range(sh, eh): occupied.add(h)
    return [f"{h:02d}:00~{h+1:02d}:00" for h in range(start_hour, end_hour) if h not in occupied]
```

conflict 응답에 `available_slots: ["09:00~10:00", "15:00~16:00", ...]` 포함 → LLM이 바로 안내 가능

## 후속 작업
- [ ] 실제 서버 환경에서 E2E 테스트 (더미 데이터 환경에서는 항상 충돌 발생)
- [ ] QUICK_REPLY 마커를 다른 도구(회의실 예약 등)에도 확장 가능
