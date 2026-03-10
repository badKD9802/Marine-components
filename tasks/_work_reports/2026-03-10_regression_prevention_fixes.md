# ReAct Agent 회귀 방지 항목 일괄 구현

> 작성일: 2026-03-10 | 카테고리: fix/feat

## 배경
`function_calling/report/02_regression_prevention.md`에 정리된 8개 회귀 방지 항목 중 #1(Rerank 모델)을 제외한 7개 항목을 일괄 구현.
기존 LangGraph 노드(`meeting.py`, `schedule.py` 등)에서 제공하던 기능이 ReAct agent로 마이그레이션되면서 누락된 부분들을 보완하는 작업.

## 변경 사항

| 파일 | 변경 내용 |
|------|----------|
| `react_system/tools/schedule_tools.py` | #2 팀달력 자동 치환, #3 24:00/종일 처리, #6 에러 분류(update/delete), #8 API 실패 시 에러 반환 |
| `react_system/tools/meeting_tools.py` | #4 회의실 중복 시 시간대 HTML, #5 선점승인 안내, #8 API 실패 시 에러 반환 |
| `react_system/tools/approval_tools.py` | #7 결재 양식 퍼지 검색(`difflib.SequenceMatcher`), #8 API 실패 시 에러 반환 |
| `react_system/utils/time_parser.py` | `parse_time()`에 24:00/자정/종일 처리 추가 |
| `react_system/utils/date_validator.py` | `validate_time_format()`에 24:00, ALL_DAY 허용 추가 |
| `react_system/prompts.py` | 선점승인 안내 가이드 추가 |

## 핵심 코드

### #2 팀달력 자동 치환 (`schedule_tools.py`)
`create_schedule()`에서 사용자가 "팀달력"이라고 입력하면 `_auth.docdept_nm`(소속 부서명)으로 자동 변환:
```python
if calendar_name and "팀달력" in calendar_name.replace(" ", ""):
    cal_name = _auth.docdept_nm
else:
    cal_name = calendar_name or "나의달력"
```

### #3 24:00/종일 처리 (`time_parser.py` + `schedule_tools.py`)
`parse_time()`에서 "종일", "하루종일", "자정", "24:00" 등을 인식하고, `create_schedule()`에서 ALL_DAY일 때 `00:00~24:00`으로 설정:
```python
if parsed_start_time == "ALL_DAY" or parsed_end_time == "ALL_DAY":
    start_dt = f"{parsed_date}T00:00:00"
    end_dt = f"{parsed_date}T24:00:00"
```

### #4 회의실 중복 시 시간대 HTML (`meeting_tools.py`)
`reserve_meeting_room()` / `update_meeting_room()`에서 중복 발생 시, 기존 `meetingroom_html.py`의 `build_slots_html()` + `dup_html()`을 재사용하여 시간대 시각화 HTML 생성:
- 등록/수정 전 `getHsEventList()`로 기존 예약 조회
- 중복 시 `xml_parsing_meeting_dupinsert()`로 충돌 상세 정보 추출
- `build_slots_html()`로 08:00~23:00 시간대별 파란색(가용)/빨간색(점유) 시각화
- `html_content` 키로 반환하여 SSE를 통해 프론트엔드에 직접 렌더링

### #5 선점승인 안내 (`meeting_tools.py` + `prompts.py`)
예약 성공 후 `db.get_meetingroom_admission(meetingroom)` 호출하여 선점승인 필요 여부 확인:
```python
meet_admission = await db.get_meetingroom_admission(meetingroom)
if meet_admission:
    response["admission_required"] = True
    response["admission_info"] = meet_admission
```
`prompts.py`에 LLM이 `admission_required: true`일 때 사용자에게 안내하도록 가이드 추가.

### #6 에러 분류 (`schedule_tools.py`)
`update_schedule()` / `delete_schedule()`에서 `xml_parsing_result_message()`로 GW 응답 파싱:
- "성공하였습니다." → `status: "success"`
- "중복되었습니다." → `status: "duplicate"`
- "권한" 포함 → `status: "error"` + 권한 없음 안내

### #7 결재 양식 퍼지 검색 (`approval_tools.py`)
`difflib.SequenceMatcher` 기반 `_fuzzy_search_forms()` 함수 구현:
- 정확 매칭(1.0) → 포함 매칭(0.9) → 유사도 매칭(threshold 0.3)
- 양식명(`FORMNAME`) + 폴더명(`FLDRNAME`) 양쪽 검색
- BM25+Embedding 대비 장점: 외부 의존성 없음, API 호출 불필요, ~100-500건 양식명 검색에 충분

### #8 API 실패 시 에러 반환 (공통)
모든 tool 함수에서 API 예외 발생 시 더미 데이터 대신 `status: "error"` 반환:
- `_auth` 있음 + API 실패 → `{"status": "error", "message": "..."}`
- `_auth` 없음 (테스트 환경) → 더미 데이터 반환 (기존 동작 유지)

## 후속 작업
- [ ] 서버 재시작 후 E2E 테스트 (실제 `_auth` 환경)
- [ ] 회의실 중복 HTML이 프론트엔드에서 정상 렌더링되는지 확인
- [ ] 선점승인 안내 메시지가 LLM을 통해 적절히 전달되는지 확인
- [ ] `_fuzzy_search_forms()` 실제 양식 데이터로 검색 정확도 검증
