"""
일정 관리 도구
사용자의 일정을 조회, 등록, 수정, 삭제합니다.

원본 시스템(parsing.yaml)에 맞춰 구현:
- calendar_reservation, calendar_check, calendar_update, calendar_cancellation
"""

import logging
from datetime import datetime, timedelta
from app.tasks.node_agent.aiassistant.function_calling.react_system.utils import parse_relative_date, parse_time, validate_time_range
from app.tasks.lib_justtype.common import util

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== SCHEDULE TOOLS ==")


async def get_schedule(date=None, date_range_start=None, date_range_end=None,
                 title=None, calendar_name=None, cal_id=None, _auth=None):
    """
    일정을 조회합니다.

    Args:
        date: 특정 날짜 조회
        date_range_start: 기간 시작 날짜
        date_range_end: 기간 종료 날짜
        title: 제목으로 검색
        calendar_name: 특정 달력에서 조회
        cal_id: 일정 번호로 조회

    Returns:
        dict: 조회 결과
    """
    # 1. 날짜 파싱
    if date:
        parsed_date = parse_relative_date(date)
        start_dt = f"{parsed_date}T00:00:00"
        end_dt = f"{parsed_date}T23:59:59"
    elif date_range_start and date_range_end:
        parsed_start = parse_relative_date(date_range_start)
        parsed_end = parse_relative_date(date_range_end)
        start_dt = f"{parsed_start}T00:00:00"
        end_dt = f"{parsed_end}T23:59:59"
    else:
        _today = datetime.now().date()
        _mon = _today - timedelta(days=_today.weekday())
        _end = _mon + timedelta(days=11)
        start_dt = f"{_mon.strftime('%Y-%m-%d')}T00:00:00"
        end_dt = f"{_end.strftime('%Y-%m-%d')}T23:59:59"

    # 2. 실제 GW API 호출
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.services.api_collection import APICollection
            from app.tasks.node_agent.aiassistant.services.xml_parsing import xml_parsing_search, calendarid_search_call

            api = APICollection(_auth.stat)

            # gw_url 추출
            ai_config = api.env.get_config("retrieval")
            gw_api_url = ai_config.get("gw_api_url", {})
            gw_url = gw_api_url.get("gw_url", "")

            # 달력 ID 조회
            calendar_ids, _ = await calendarid_search_call(gw_url, _auth.k, _auth.user_id)

            # 날짜 형식 변환: YYYY-MM-DD → YYYY.MM.DD
            api_start = start_dt[:10].replace("-", ".")
            api_end = end_dt[:10].replace("-", ".")

            response = api.getHsEventList(
                USER_ID=_auth.user_id,
                DEPT_ID=_auth.dept_id,
                K=_auth.k,
                TARGET_START_DATE=api_start,
                TARGET_END_DATE=api_end,
                CALENDAR_IDS=calendar_ids,
                ORG_USER_ID=_auth.user_id,
                TITLE=title or "",
            )

            events = await xml_parsing_search(response)

            # calendar_name으로 필터링
            if calendar_name and events:
                events = [e for e in events if e.get("calendar_nm") == calendar_name]

            return {
                "status": "success",
                "message": f"일정 {len(events)}건 조회 완료",
                "query": {"start_dt": start_dt, "end_dt": end_dt, "title": title, "calendar_name": calendar_name},
                "schedules": events,
            }
        except Exception as e:
            logger.error(f"get_schedule API 오류: {e}")

    # 3. 더미 데이터 반환 (API 미구현 또는 실패 시)
    # HTML 표 기능 테스트를 위해 15개 일정 반환
    # 실제 API 형식에 맞춤: start_date, end_date, calendar_nm, owner_name

    # 전체 더미 일정 생성 — 현재일 기준 상대 날짜로 이번 주/다음 주에 분산
    today = datetime.now().date()
    # 이번 주 월요일 기준
    mon = today - timedelta(days=today.weekday())

    def d(week_offset, weekday):
        """week_offset: 0=이번주, 1=다음주 / weekday: 0=월~6=일"""
        return (mon + timedelta(weeks=week_offset, days=weekday)).strftime("%Y.%m.%d")

    # 시간순 정렬: 이번주 월~금 → 다음주 월~금, 번호는 시간순 자동 부여
    _raw = [
        # ── 이번 주 ──
        (d(0, 0), "09:00", "10:00", "팀 회의",           "주간 업무 공유 및 진행상황 점검", "나의달력", "홍길동"),
        (d(0, 0), "14:00", "15:00", "코드 리뷰",         "React 컴포넌트 코드 리뷰",       "나의달력", "박지민"),
        (d(0, 1), "10:00", "11:30", "프로젝트 킥오프",   "신규 프로젝트 착수 회의",         "업무달력", "김철수"),
        (d(0, 1), "15:00", "16:00", "배포 계획 회의",    "프로덕션 배포 일정 조율",         "업무달력", "권도윤"),
        (d(0, 2), "09:30", "10:30", "보안 점검 미팅",    "시스템 보안 취약점 점검",         "나의달력", "윤서준"),
        (d(0, 2), "11:00", "12:00", "인프라 점검 회의",  "클라우드 인프라 현황 점검",        "공유일정", "강민지"),
        (d(0, 2), "13:00", "14:00", "고객사 미팅",       "요구사항 분석 및 제안서 발표",     "업무달력", "이영희"),
        (d(0, 3), "11:00", "12:00", "UX 개선 회의",      "사용자 피드백 반영 논의",         "나의달력", "한서연"),
        (d(0, 4), "10:00", "11:00", "성능 테스트 리뷰",  "부하 테스트 결과 분석",           "업무달력", "임지우"),
        (d(0, 4), "16:00", "17:00", "데일리 스크럼",     "금주 작업 내용 공유",             "나의달력", "정수현"),
        # ── 다음 주 ──
        (d(1, 0), "09:00", "10:00", "주간 회의",         "다음 주 업무 계획 수립",           "나의달력", "홍길동"),
        (d(1, 1), "13:00", "14:00", "API 설계 리뷰",     "RESTful API 엔드포인트 설계",     "업무달력", "오준혁"),
        (d(1, 2), "14:00", "15:00", "QA 미팅",           "테스트 케이스 검토",              "나의달력", "송하은"),
        (d(1, 3), "10:30", "11:30", "AI 모델 개발 회의", "LangChain 통합 방안 논의",        "업무달력", "최민수"),
        (d(1, 3), "15:00", "16:00", "DB 설계 회의",      "PostgreSQL 스키마 설계",          "업무달력", "강민호"),
        (d(1, 4), "16:00", "17:00", "월간 회고",         "이번 달 성과 및 개선사항 공유",    "업무달력", "조예은"),
    ]
    all_schedules = [
        {
            "num": str(i + 1),
            "title": r[3],
            "start_date": f"{r[0]} {r[1]}",
            "end_date": f"{r[0]} {r[2]}",
            "description": r[4],
            "calendar_nm": r[5],
            "owner_name": r[6],
        }
        for i, r in enumerate(_raw)
    ]

    # 날짜 범위로 필터링
    filter_start = start_dt[:10].replace("-", ".")  # YYYY.MM.DD
    filter_end = end_dt[:10].replace("-", ".")

    filtered_schedules = []
    for s in all_schedules:
        s_date = s.get('start_date', '')[:10]  # YYYY.MM.DD
        if s_date and filter_start <= s_date <= filter_end:
            filtered_schedules.append(s)

    # calendar_name으로 추가 필터링 (요청된 경우)
    if calendar_name:
        filtered_schedules = [
            s for s in filtered_schedules
            if s.get('calendar_nm') == calendar_name
        ]
        message = f"'{calendar_name}' 일정 {len(filtered_schedules)}건 조회 완료 (더미 데이터)"
    else:
        message = f"일정 {len(filtered_schedules)}건 조회 완료 (더미 데이터)"

    return {
        "status": "success",
        "message": message,
        "query": {
            "start_dt": start_dt,
            "end_dt": end_dt,
            "title": title,
            "calendar_name": calendar_name,
            "cal_id": cal_id
        },
        "schedules": filtered_schedules
    }


def _check_time_overlap(existing_schedules, new_start, new_end):
    """기존 일정과 시간 겹침을 확인합니다."""
    conflicts = []
    for s in existing_schedules:
        s_start = s.get("start_date", "")
        s_end = s.get("end_date", "")
        # "YYYY.MM.DD HH:MM" 형식에서 시간만 추출
        try:
            s_start_time = s_start.split(" ")[1] if " " in s_start else ""
            s_end_time = s_end.split(" ")[1] if " " in s_end else ""
            if not s_start_time or not s_end_time:
                continue
            # 시간 비교: 겹치는 조건 = new_start < s_end AND new_end > s_start
            if new_start < s_end_time and new_end > s_start_time:
                conflicts.append(s)
        except (IndexError, ValueError):
            continue
    return conflicts


def _find_available_slots(all_schedules, start_hour=8, end_hour=22):
    """하루 일정에서 빈 시간 슬롯을 찾습니다. (1시간 단위)"""
    occupied = set()
    for s in all_schedules:
        try:
            s_start = s.get("start_date", "").split(" ")[1] if " " in s.get("start_date", "") else ""
            s_end = s.get("end_date", "").split(" ")[1] if " " in s.get("end_date", "") else ""
            if not s_start or not s_end:
                continue
            sh = int(s_start.split(":")[0])
            eh = int(s_end.split(":")[0])
            em = int(s_end.split(":")[1]) if ":" in s_end else 0
            if em > 0:
                eh += 1  # 14:30 끝나면 14시도 occupied
            for h in range(sh, eh):
                occupied.add(h)
        except (IndexError, ValueError):
            continue

    slots = []
    for h in range(start_hour, end_hour):
        if h not in occupied:
            slots.append(f"{h:02d}:00~{h + 1:02d}:00")
    return slots


async def create_schedule(title, date, start_time, end_time,
                   description=None, calendar_name=None, force=False, _auth=None):
    """
    새로운 일정을 등록합니다.

    Args:
        title: 일정 제목
        date: 날짜 (YYYY-MM-DD 또는 '오늘', '내일' 등)
        start_time: 시작 시간 (HH:MM 또는 '오후 3시' 등)
        end_time: 종료 시간 (HH:MM 또는 '오후 4시' 등)
        description: 상세 설명
        calendar_name: 달력 이름
        force: True이면 충돌 무시하고 강제 등록

    Returns:
        dict: 등록 결과
    """
    # 1. 날짜/시간 파싱
    parsed_date = parse_relative_date(date)
    parsed_start_time = parse_time(start_time)
    parsed_end_time = parse_time(end_time)

    # 2. 시간 범위 검증
    is_valid, error_msg = validate_time_range(parsed_start_time, parsed_end_time)
    if not is_valid:
        return {
            "status": "error",
            "message": f"시간 범위 오류: {error_msg}"
        }

    # 3. ISO 8601 형식으로 변환 (원본 시스템 형식)
    start_dt = f"{parsed_date}T{parsed_start_time}:00"
    end_dt = f"{parsed_date}T{parsed_end_time}:00"

    # 4. 충돌 확인 (force=False일 때만)
    if not force:
        try:
            existing = await get_schedule(date=date, _auth=_auth)
            if existing.get("status") == "success" and existing.get("schedules"):
                conflicts = _check_time_overlap(
                    existing["schedules"], parsed_start_time, parsed_end_time
                )
                if conflicts:
                    conflict_list = []
                    for c in conflicts:
                        conflict_list.append({
                            "title": c.get("title", ""),
                            "start_date": c.get("start_date", ""),
                            "end_date": c.get("end_date", ""),
                            "calendar_nm": c.get("calendar_nm", ""),
                        })
                    available_slots = _find_available_slots(existing["schedules"])
                    return {
                        "status": "conflict",
                        "message": f"{parsed_date} {parsed_start_time}~{parsed_end_time}에 기존 일정 {len(conflicts)}건이 있습니다.",
                        "conflicts": conflict_list,
                        "available_slots": available_slots,
                        "pending_schedule": {
                            "title": title,
                            "date": date,
                            "start_time": start_time,
                            "end_time": end_time,
                            "description": description,
                            "calendar_name": calendar_name,
                        },
                    }
        except Exception as e:
            logger.error(f"create_schedule 충돌 확인 오류 (무시하고 진행): {e}")

    # 5. 실제 GW API 호출
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.services.api_collection import APICollection
            from app.tasks.node_agent.aiassistant.services.xml_parsing import xml_parsing_insert, calendarid_call

            api = APICollection(_auth.stat)
            ai_config = api.env.get_config("retrieval")
            gw_url = ai_config.get("gw_api_url", {}).get("gw_url", "")

            # 달력 이름 → ID 변환
            cal_name = calendar_name or "나의달력"
            calendar_id = await calendarid_call(gw_url, _auth.k, _auth.user_id, cal_name, _auth.user_nm)

            # 날짜 형식: YYYY-MM-DDTHH:MM:00 → YYYY.MM.DD HH:MM:SS
            api_start = start_dt.replace("-", ".").replace("T", " ")
            api_end = end_dt.replace("-", ".").replace("T", " ")

            response = api.add(
                K=_auth.k,
                USER_ID=_auth.user_id,
                DEPT_ID=_auth.dept_id,
                ORG_USER_ID=_auth.user_id,
                TITLE=title,
                START_DT=api_start,
                END_DT=api_end,
                CALENDAR_ID=calendar_id,
                DESCRIPTION=description or "",
            )

            result = await xml_parsing_insert(response)
            if result:
                return {
                    "status": "success",
                    "message": f"일정 '{title}'이(가) 등록되었습니다.",
                    "schedule": result[0] if isinstance(result, list) else result,
                }
        except Exception as e:
            logger.error(f"create_schedule API 오류: {e}")

    # 6. 더미 데이터 반환 (API 미구현 또는 실패 시)
    # xml_parsing_insert() 반환 형식과 동일
    return {
        "status": "success",
        "message": f"일정 '{title}'이(가) 등록되었습니다. (더미 데이터)",
        "schedule": {
            "title": title,
            "description": description or "",
            "start_date": start_dt[:10].replace("-", ".") + " " + (start_dt[11:16] if "T" in start_dt else start_dt[-5:]),
            "end_date": end_dt[:10].replace("-", ".") + " " + (end_dt[11:16] if "T" in end_dt else end_dt[-5:]),
            "event_id": "EVT-DUMMY-001",
            "owner_name": "홍길동",
            "calendar_nm": [calendar_name or "나의달력"],
        }
    }


async def update_schedule(cal_id=None, title=None, title_chg=None,
                   date=None, start_time=None, end_time=None,
                   description=None, calendar_name=None, _auth=None):
    """
    일정을 수정합니다.

    Args:
        cal_id: 일정 번호
        title: 기존 제목 (검색용)
        title_chg: 변경할 제목
        date: 변경할 날짜
        start_time: 변경할 시작 시간
        end_time: 변경할 종료 시간
        description: 변경할 설명
        calendar_name: 달력 이름

    Returns:
        dict: 수정 결과
    """
    # 1. 파라미터 준비
    update_params = {}

    if title_chg:
        update_params["title"] = title_chg

    if date and start_time:
        parsed_date = parse_relative_date(date)
        parsed_start = parse_time(start_time)
        update_params["start_dt"] = f"{parsed_date}T{parsed_start}:00"

    if date and end_time:
        parsed_date = parse_relative_date(date)
        parsed_end = parse_time(end_time)
        update_params["end_dt"] = f"{parsed_date}T{parsed_end}:00"

    if description:
        update_params["description"] = description

    # 2. 시간 범위 검증 (둘 다 있을 때)
    if "start_dt" in update_params and "end_dt" in update_params:
        start_t = update_params["start_dt"].split("T")[1][:5]
        end_t = update_params["end_dt"].split("T")[1][:5]
        is_valid, error_msg = validate_time_range(start_t, end_t)
        if not is_valid:
            return {
                "status": "error",
                "message": f"시간 범위 오류: {error_msg}"
            }

    # 3. 실제 GW API 호출
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.services.api_collection import APICollection
            from app.tasks.node_agent.aiassistant.services.xml_parsing import xml_parsing_search

            api = APICollection(_auth.stat)
            ai_config = api.env.get_config("retrieval")
            gw_url = ai_config.get("gw_api_url", {}).get("gw_url", "")

            # event_id 확보: cal_id가 있으면 사용, 없으면 제목으로 검색
            event_id = cal_id
            select_dt = None
            if not event_id and title:
                from app.tasks.node_agent.aiassistant.services.xml_parsing import calendarid_search_call
                calendar_ids, _ = await calendarid_search_call(gw_url, _auth.k, _auth.user_id)
                today = datetime.now().strftime("%Y.%m.%d")
                future = (datetime.now() + timedelta(days=90)).strftime("%Y.%m.%d")
                resp = api.getHsEventList(
                    USER_ID=_auth.user_id, DEPT_ID=_auth.dept_id, K=_auth.k,
                    TARGET_START_DATE=today, TARGET_END_DATE=future,
                    CALENDAR_IDS=calendar_ids, ORG_USER_ID=_auth.user_id, TITLE=title,
                )
                events = await xml_parsing_search(resp)
                if events:
                    event_id = events[0].get("event_id")
                    select_dt = events[0].get("start_date", "")[:10]

            if event_id:
                api_params = {
                    "USER_ID": _auth.user_id, "DEPT_ID": _auth.dept_id,
                    "USER_NM": _auth.user_nm, "K": _auth.k, "EVENT_ID": event_id,
                    "SELECT_DT": select_dt,
                }
                if "title" in update_params:
                    api_params["TITLE"] = update_params["title"]
                if "start_dt" in update_params:
                    api_params["START_DT"] = update_params["start_dt"].replace("-", ".").replace("T", " ")
                if "end_dt" in update_params:
                    api_params["END_DT"] = update_params["end_dt"].replace("-", ".").replace("T", " ")
                if "description" in update_params:
                    api_params["DESCRIPTION"] = update_params["description"]

                result = api.update(**api_params)
                return {
                    "status": "success",
                    "message": f"일정이 수정되었습니다.",
                    "updated_params": update_params,
                }
        except Exception as e:
            logger.error(f"update_schedule API 오류: {e}")

    # 4. 더미 데이터 반환
    return {
        "status": "success",
        "message": f"일정 {cal_id or title}이(가) 수정되었습니다. (더미 데이터)",
        "updated_params": update_params
    }


async def delete_schedule(cal_id=None, title=None, date=None,
                   start_time=None, end_time=None, calendar_name=None, _auth=None):
    """
    일정을 삭제합니다.

    Args:
        cal_id: 삭제할 일정 번호
        title: 삭제할 일정 제목
        date: 삭제할 일정 날짜
        start_time: 삭제할 일정 시작 시간
        end_time: 삭제할 일정 종료 시간
        calendar_name: 달력 이름

    Returns:
        dict: 삭제 결과
    """
    # 1. 검색 조건 준비
    search_params = {}

    if cal_id:
        search_params["cal_id"] = cal_id
    if title:
        search_params["title"] = title
    if date:
        parsed_date = parse_relative_date(date)
        search_params["date"] = parsed_date

    # 2. 실제 GW API 호출
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.services.api_collection import APICollection
            from app.tasks.node_agent.aiassistant.services.xml_parsing import xml_parsing_search, calendarid_search_call

            api = APICollection(_auth.stat)
            ai_config = api.env.get_config("retrieval")
            gw_url = ai_config.get("gw_api_url", {}).get("gw_url", "")

            event_id = cal_id
            select_dt = search_params.get("date", "").replace("-", ".")

            # event_id 없으면 제목으로 검색
            if not event_id and title:
                calendar_ids, _ = await calendarid_search_call(gw_url, _auth.k, _auth.user_id)
                today = datetime.now().strftime("%Y.%m.%d")
                future = (datetime.now() + timedelta(days=90)).strftime("%Y.%m.%d")
                resp = api.getHsEventList(
                    USER_ID=_auth.user_id, DEPT_ID=_auth.dept_id, K=_auth.k,
                    TARGET_START_DATE=today, TARGET_END_DATE=future,
                    CALENDAR_IDS=calendar_ids, ORG_USER_ID=_auth.user_id, TITLE=title,
                )
                events = await xml_parsing_search(resp)
                if events:
                    event_id = events[0].get("event_id")
                    select_dt = events[0].get("start_date", "")[:10]

            if event_id:
                api.delete(USERID=_auth.user_id, EVENT_ID=event_id, SELECT_DT=select_dt, K=_auth.k)
                return {
                    "status": "success",
                    "message": f"일정이 삭제되었습니다.",
                    "deleted": search_params,
                }
        except Exception as e:
            logger.error(f"delete_schedule API 오류: {e}")

    # 3. 더미 데이터 반환
    return {
        "status": "success",
        "message": f"일정 {cal_id or title}이(가) 삭제되었습니다. (더미 데이터)",
        "deleted": search_params
    }

