"""
회의실 관리 도구
회의실을 조회, 예약, 수정, 취소합니다.

원본 시스템(parsing.yaml)에 맞춰 구현:
- meeting_reservation, meeting_check, meeting_update, meeting_cancellation
- get_meeting_room_list: 회의실 목록 조회 (신규)
"""

import logging
from datetime import datetime, timedelta
from react_system.utils import parse_relative_date, parse_time, validate_time_range

logger = logging.getLogger(__name__)


def _get_gw_url(stat):
    """stat에서 gw_url 추출 헬퍼."""
    from app.tasks.lib_justtype.common.just_env import JustEnv
    env = JustEnv(stat)
    ai_config = env.get_config("retrieval")
    gw_api_url = ai_config.get("gw_api_url", {})
    return gw_api_url.get("gw_url", "")


async def get_meeting_room_list(floor=None, min_capacity=None, _auth=None):
    """
    회의실 목록을 조회합니다 (예약 정보 제외).

    Args:
        floor: 층수 필터 (선택, 예: 8)
        min_capacity: 최소 수용 인원 (선택, 예: 10)

    Returns:
        dict: 회의실 목록
    """
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.db_extract.db_search import OracleSearchClient
            db = OracleSearchClient(_auth.stat)
            meetingroom_par_list, meetingroom_list = await db.meetingroom_db_list()

            if meetingroom_par_list and meetingroom_list:
                rooms = []
                titles = meetingroom_par_list.get("TITLE", [])
                par_titles = meetingroom_par_list.get("PAR_TITLE", [])
                for i, room_name in enumerate(titles):
                    location = par_titles[i] if i < len(par_titles) else "-"
                    rooms.append({
                        "room_name": room_name,
                        "location": location,
                    })

                # 필터링 (DB에는 floor/capacity 정보가 없으므로 문자열 매칭)
                if floor:
                    floor_str = f"{floor}층"
                    rooms = [r for r in rooms if floor_str in r["room_name"] or floor_str in r.get("location", "")]

                return {
                    "status": "success",
                    "message": f"회의실 {len(rooms)}개를 조회했습니다.",
                    "rooms": rooms,
                    "total_count": len(rooms),
                }
        except Exception as e:
            logger.error(f"get_meeting_room_list API 오류: {e}")
            return {"status": "error", "message": "회의실 목록 조회 중 오류가 발생했습니다."}

    # 더미 데이터 (테스트 환경)
    mock_room_list = [
        {"room_name": "8층 영상회의실", "location": "본사 8층 동관"},
        {"room_name": "8층 소회의실", "location": "본사 8층 서관"},
        {"room_name": "대회의실", "location": "본사 7층"},
        {"room_name": "전산교육실", "location": "본사 6층"},
        {"room_name": "임원회의실", "location": "본사 9층"},
        {"room_name": "7층 회의실 A", "location": "본사 7층 동관"},
        {"room_name": "7층 회의실 B", "location": "본사 7층 서관"},
    ]

    return {
        "status": "success",
        "message": f"회의실 {len(mock_room_list)}개를 조회했습니다. (더미 데이터)",
        "rooms": mock_room_list,
        "total_count": len(mock_room_list),
    }


async def reserve_meeting_room(meetingroom, title, date, start_time, end_time,
                               description=None, calendar_name=None, _auth=None):
    """
    회의실을 예약합니다.

    Args:
        meetingroom: 회의실 이름
        title: 회의 제목
        date: 예약 날짜 (YYYY-MM-DD 또는 '오늘', '내일' 등)
        start_time: 시작 시간 (HH:MM 또는 '오후 3시' 등)
        end_time: 종료 시간 (HH:MM 또는 '오후 4시' 등)
        description: 회의 내용 상세 설명
        calendar_name: 달력 이름

    Returns:
        dict: 예약 결과
    """
    # 1. 날짜/시간 파싱
    parsed_date = parse_relative_date(date)
    parsed_start_time = parse_time(start_time)
    parsed_end_time = parse_time(end_time)

    # 2. 시간 범위 검증
    is_valid, error_msg = validate_time_range(parsed_start_time, parsed_end_time)
    if not is_valid:
        return {"status": "error", "message": f"시간 범위 오류: {error_msg}"}

    # 3. ISO 8601 형식으로 변환
    start_dt = f"{parsed_date}T{parsed_start_time}:00"
    end_dt = f"{parsed_date}T{parsed_end_time}:00"

    # 4. 실제 GW API 호출
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.services.api_collection import APICollection
            from app.tasks.node_agent.aiassistant.services.xml_parsing import (
                xml_parsing_result_message, xml_parsing_meeting_insert, calendarid_call_meeting,
                xml_parsing_meetingroom, xml_parsing_meeting_dupinsert,
            )
            from app.tasks.node_agent.aiassistant.db_extract.db_search import OracleSearchClient
            from app.tasks.node_agent.aiassistant.services.meetingroom_html import build_slots_html, dup_html
            from datetime import time as dt_time

            api = APICollection(_auth.stat)
            db = OracleSearchClient(_auth.stat)
            gw_url = _get_gw_url(_auth.stat)

            # 회의실 이름 → CALENDAR_ID 변환
            meetingroom_par_list, meetingroom_list = await db.meetingroom_db_list()
            if meetingroom not in (meetingroom_list or []):
                return {
                    "status": "error",
                    "message": f"'{meetingroom}'은(는) 존재하지 않는 회의실입니다.",
                    "available_rooms": meetingroom_list or [],
                }

            meetingroom_num = await db.meetingroom_db(meetingroom)

            # 달력 ID 조회
            calendar_id = ""
            if calendar_name:
                try:
                    calendar_id = await calendarid_call_meeting(gw_url, _auth.k, _auth.user_id, calendar_name, _auth.user_nm)
                except Exception:
                    calendar_id = ""

            # 날짜 형식 변환
            api_start = f"{parsed_date.replace('-', '.')} {parsed_start_time}:00"
            api_end = f"{parsed_date.replace('-', '.')} {parsed_end_time}:00"
            meetingroom_num_clean = meetingroom_num.replace(";", "")

            # 등록 전 기존 예약 조회 (중복 시 시간대 안내용)
            search_date = parsed_date.replace("-", ".")
            next_days_end = (datetime.strptime(parsed_date, "%Y-%m-%d") + timedelta(days=3)).strftime("%Y.%m.%d")
            before_response = api.getHsEventList(
                K=_auth.k,
                USER_ID=_auth.user_id,
                DEPT_ID=_auth.dept_id,
                ORG_USER_ID=_auth.user_id,
                TARGET_START_DATE=search_date,
                TARGET_END_DATE=next_days_end,
                CALENDAR_IDS=calendar_id,
                TITLE="",
                EQUIPMENT_IDS=meetingroom_num,
                EVENT_EQUIP_PAGE="equipment_page",
            )
            before_result = await xml_parsing_meetingroom(before_response, _auth.stat)

            result = api.add(
                K=_auth.k,
                USER_ID=_auth.user_id,
                DEPT_ID=_auth.dept_id,
                ORG_USER_ID=_auth.user_id,
                TITLE=title,
                START_DT=api_start,
                END_DT=api_end,
                CALENDAR_ID=calendar_id,
                DESCRIPTION=description or "",
                EQUIPMENT=meetingroom_num_clean,
                EVENT_ID="",
            )

            duplication = await xml_parsing_result_message(result)

            if duplication == "중복되었습니다.":
                try:
                    dup = await xml_parsing_meeting_dupinsert(result, _auth.stat)
                    dup_title = dup.get("title", "")
                    dup_name = dup.get("owner_name", "")
                    dup_phone = dup.get("phone", "")
                    dup_date = dup.get("start_date", "") + " ~ " + dup.get("end_date", "")
                    dup_room = dup.get("equipment_nm", meetingroom)

                    bookings = []
                    for item in before_result:
                        b_start = item.get("start_date", "").replace(".", "-")
                        b_end = item.get("end_date", "").replace(".", "-")
                        bookings.append((b_start, b_end))

                    dup_time_html = build_slots_html(
                        parsed_date, bookings,
                        avail_start=dt_time(8, 0), avail_end=dt_time(23, 0), slot_minutes=60,
                    )
                    full_html = dup_html(
                        parsed_date, dup_time_html, bookings,
                        dup_title, dup_name, dup_phone, dup_date, dup_room,
                    )

                    return {
                        "status": "duplicate",
                        "message": f"'{meetingroom}' 해당 시간에 이미 예약이 있습니다.",
                        "html_content": full_html,
                        "text_summary": f"회의실 '{meetingroom}'은 {dup_date}에 '{dup_title}' ({dup_name})이 이미 예약되어 있습니다. 시간대별 예약 현황이 HTML로 표시됩니다. 사용자에게 다른 시간을 추천해주세요.",
                        "meetingroom": meetingroom,
                        "start_dt": start_dt,
                        "end_dt": end_dt,
                    }
                except Exception as e:
                    logger.error(f"reserve_meeting_room 중복 상세 조회 오류: {e}")
                    return {
                        "status": "duplicate",
                        "message": f"'{meetingroom}' 해당 시간에 이미 예약이 있습니다. 다른 시간을 선택해주세요.",
                        "meetingroom": meetingroom,
                        "start_dt": start_dt,
                        "end_dt": end_dt,
                    }
            elif duplication == "유효하지 않은 요청입니다.":
                return {"status": "error", "message": "유효하지 않은 예약 요청입니다. 시간을 확인해주세요."}

            # 성공 — XML에서 결과 파싱
            result_data = await xml_parsing_meeting_insert(result, _auth.stat)

            # 선점승인 체크
            meet_admission = ""
            try:
                meet_admission = await db.get_meetingroom_admission(meetingroom)
            except Exception:
                pass

            response = {
                "status": "success",
                "message": f"'{meetingroom}' 예약이 완료되었습니다.",
                "reservation": {
                    "meetingroom": meetingroom,
                    "title": result_data.get("title", title),
                    "start_dt": result_data.get("start_date", start_dt),
                    "end_dt": result_data.get("end_date", end_dt),
                    "description": description or "",
                    "event_id": result_data.get("event_id", ""),
                },
            }
            if meet_admission:
                response["admission_required"] = True
                response["admission_info"] = meet_admission
            return response
        except Exception as e:
            logger.error(f"reserve_meeting_room API 오류: {e}")
            return {"status": "error", "message": "회의실 예약 중 오류가 발생했습니다. 다시 시도해주세요."}

    # 5. 더미 데이터 (테스트 환경)
    return {
        "status": "success",
        "message": f"'{meetingroom}' 예약이 완료되었습니다. (더미 데이터)",
        "reservation": {
            "meetingroom": meetingroom,
            "title": title,
            "start_dt": start_dt[:10].replace("-", ".") + " " + (start_dt[11:16] if "T" in start_dt else start_dt[-5:]),
            "end_dt": end_dt[:10].replace("-", ".") + " " + (end_dt[11:16] if "T" in end_dt else end_dt[-5:]),
            "description": description or "",
            "event_id": "EVT-DUMMY-MTG-001",
        },
    }


async def get_meeting_rooms(meetingroom, date=None, date_range_start=None, date_range_end=None,
                            start_time=None, end_time=None, _auth=None):
    """
    특정 회의실의 예약 현황을 조회합니다.

    Args:
        meetingroom: 회의실 이름 (필수)
        date: 특정 날짜 조회 (선택)
        date_range_start: 기간 시작 날짜 (선택)
        date_range_end: 기간 종료 날짜 (선택)
        start_time: 조회 시작 시간 (선택)
        end_time: 조회 종료 시간 (선택)

    Returns:
        dict: 특정 회의실의 예약 정보
    """
    # 1. 날짜 범위 파싱
    _today = datetime.now().date()

    if date:
        parsed_date = parse_relative_date(date)
        start_dt = f"{parsed_date}T00:00:00"
        end_dt = f"{parsed_date}T23:59:59"
    elif date_range_start and date_range_end:
        parsed_start = parse_relative_date(date_range_start)
        parsed_end = parse_relative_date(date_range_end)
        start_dt = f"{parsed_start}T00:00:00"
        end_dt = f"{parsed_end}T23:59:59"
    elif date_range_start:
        parsed_start = parse_relative_date(date_range_start)
        ds = datetime.strptime(parsed_start, "%Y-%m-%d").date()
        mon = ds - timedelta(days=ds.weekday())
        fri = mon + timedelta(days=4)
        start_dt = f"{mon.strftime('%Y-%m-%d')}T00:00:00"
        end_dt = f"{fri.strftime('%Y-%m-%d')}T23:59:59"
    else:
        start_dt = f"{_today.strftime('%Y-%m-%d')}T00:00:00"
        end_dt = f"{_today.strftime('%Y-%m-%d')}T23:59:59"

    if start_time:
        parsed_start_time = parse_time(start_time)
        start_dt = f"{start_dt[:10]}T{parsed_start_time}:00"
    if end_time:
        parsed_end_time = parse_time(end_time)
        end_dt = f"{end_dt[:10]}T{parsed_end_time}:00"

    # 2. 실제 GW API 호출
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.services.api_collection import APICollection
            from app.tasks.node_agent.aiassistant.services.xml_parsing import xml_parsing_meetingroom, calendarid_call_meeting
            from app.tasks.node_agent.aiassistant.db_extract.db_search import OracleSearchClient

            api = APICollection(_auth.stat)
            db = OracleSearchClient(_auth.stat)
            gw_url = _get_gw_url(_auth.stat)

            # 회의실 목록 조회 + 유효성 검증
            meetingroom_par_list, meetingroom_list = await db.meetingroom_db_list()

            # 회의실 이름이 list인 경우 (복수 조회)
            if isinstance(meetingroom, list):
                meetingroom_num_list = []
                for item in meetingroom:
                    num = await db.meetingroom_db(item)
                    meetingroom_num_list.append(num)
                meetingroom_num = ";".join(meetingroom_num_list) + ";"
            else:
                if meetingroom not in (meetingroom_list or []):
                    return {
                        "status": "error",
                        "message": f"'{meetingroom}'은(는) 존재하지 않는 회의실입니다.",
                        "available_rooms": meetingroom_list or [],
                    }
                meetingroom_num = await db.meetingroom_db(meetingroom)

            # 달력 ID 조회
            calendar_id = ""
            try:
                calendar_id = await calendarid_call_meeting(gw_url, _auth.k, _auth.user_id, "", _auth.user_nm)
            except Exception:
                pass

            api_start = start_dt[:10].replace("-", ".")
            api_end = end_dt[:10].replace("-", ".")

            response = api.getHsEventList(
                K=_auth.k,
                USER_ID=_auth.user_id,
                DEPT_ID=_auth.dept_id,
                ORG_USER_ID=_auth.user_id,
                TARGET_START_DATE=api_start,
                TARGET_END_DATE=api_end,
                CALENDAR_IDS=calendar_id,
                TITLE="",
                EQUIPMENT_IDS=meetingroom_num,
                EVENT_EQUIP_PAGE="equipment_page",
            )

            reservations = await xml_parsing_meetingroom(response, _auth.stat)

            return {
                "status": "success",
                "message": f"'{meetingroom}' {api_start}~{api_end} 조회 완료 ({len(reservations)}건)",
                "query": {"meetingroom": meetingroom, "start_dt": start_dt, "end_dt": end_dt},
                "room_info": {
                    "meetingroom": meetingroom,
                    "reservations": reservations,
                    "reservation_count": len(reservations),
                },
            }
        except Exception as e:
            logger.error(f"get_meeting_rooms API 오류: {e}")
            return {"status": "error", "message": "회의실 예약 현황 조회 중 오류가 발생했습니다."}

    # 3. 더미 데이터 (테스트 환경)
    VALID_ROOMS = ["8층 영상회의실", "8층 소회의실", "대회의실", "전산교육실", "임원회의실", "7층 회의실 A", "7층 회의실 B"]

    if meetingroom not in VALID_ROOMS:
        available_rooms = await get_meeting_room_list(_auth=_auth)
        return {
            "status": "error",
            "message": f"'{meetingroom}'은(는) 존재하지 않는 회의실입니다.",
            "suggestion": "아래 회의실 목록에서 선택해주세요.",
            "available_rooms": available_rooms["rooms"],
            "total_count": available_rooms["total_count"],
        }

    _mon = _today - timedelta(days=_today.weekday())

    def _d(wo, wd):
        return (_mon + timedelta(weeks=wo, days=wd)).strftime("%Y.%m.%d")

    # xml_parsing_meetingroom() 반환 형식과 동일
    mock_reservations = {
        "8층 영상회의실": [
            {"num": "1", "title": "경영진 전략 회의", "start_date": f"{_d(0,0)} 09:00", "end_date": f"{_d(0,0)} 10:00", "description": "2026년 사업 전략 수립", "owner_name": "김대표", "event_id": "EVT-D-101", "owner_id": "USR001", "phone": "02-1234-8001", "meetingroom": "8층 영상회의실"},
            {"num": "2", "title": "AI 프로젝트 킥오프", "start_date": f"{_d(0,0)} 10:00", "end_date": f"{_d(0,0)} 11:30", "description": "AI 비서 개발 착수 회의", "owner_name": "이팀장", "event_id": "EVT-D-102", "owner_id": "USR002", "phone": "02-1234-5001", "meetingroom": "8층 영상회의실"},
            {"num": "3", "title": "고객사 제안 발표", "start_date": f"{_d(0,1)} 11:30", "end_date": f"{_d(0,1)} 13:00", "description": "KAMCO 프로젝트 제안서 프레젠테이션", "owner_name": "박과장", "event_id": "EVT-D-103", "owner_id": "USR003", "phone": "02-1234-5002", "meetingroom": "8층 영상회의실"},
            {"num": "4", "title": "시스템 아키텍처 리뷰", "start_date": f"{_d(0,2)} 13:00", "end_date": f"{_d(0,2)} 14:00", "description": "마이크로서비스 설계 검토", "owner_name": "최차장", "event_id": "EVT-D-104", "owner_id": "USR004", "phone": "02-1234-5003", "meetingroom": "8층 영상회의실"},
        ],
        "8층 소회의실": [],
        "대회의실": [
            {"num": "1", "title": "전사 미팅", "start_date": f"{_d(0,2)} 09:00", "end_date": f"{_d(0,2)} 12:00", "description": "전사 업무 보고", "owner_name": "최상무", "event_id": "EVT-D-201", "owner_id": "USR005", "phone": "02-1234-8002", "meetingroom": "대회의실"},
        ],
        "전산교육실": [
            {"num": "1", "title": "프로젝트 미팅", "start_date": f"{_d(0,3)} 14:00", "end_date": f"{_d(0,3)} 16:00", "description": "신규 프로젝트 킥오프", "owner_name": "이영희", "event_id": "EVT-D-301", "owner_id": "USR006", "phone": "02-1234-5004", "meetingroom": "전산교육실"},
        ],
        "임원회의실": [],
        "7층 회의실 A": [],
        "7층 회의실 B": [
            {"num": "1", "title": "1:1 미팅", "start_date": f"{_d(0,1)} 11:00", "end_date": f"{_d(0,1)} 12:00", "description": "팀원 면담", "owner_name": "홍길동", "event_id": "EVT-D-401", "owner_id": "USR007", "phone": "02-1234-7001", "meetingroom": "7층 회의실 B"},
        ],
    }

    all_reservations = mock_reservations.get(meetingroom, [])

    filter_start = start_dt[:10].replace("-", ".")
    filter_end = end_dt[:10].replace("-", ".")

    filtered = [r for r in all_reservations if filter_start <= r.get("start_date", "")[:10] <= filter_end]

    return {
        "status": "success",
        "message": f"'{meetingroom}' {filter_start}~{filter_end} 조회 완료 ({len(filtered)}건, 더미 데이터)",
        "query": {"meetingroom": meetingroom, "start_dt": start_dt, "end_dt": end_dt},
        "room_info": {
            "meetingroom": meetingroom,
            "reservations": filtered,
            "reservation_count": len(filtered),
        },
    }


async def get_all_meeting_rooms(date=None, date_range_start=None, date_range_end=None, _auth=None):
    """
    전체 회의실의 예약 현황을 한번에 조회합니다.

    Args:
        date: 특정 날짜 조회 (선택)
        date_range_start: 기간 시작 날짜 (선택)
        date_range_end: 기간 종료 날짜 (선택)

    Returns:
        dict: 전체 회의실 예약 현황
    """
    # 회의실 목록 조회
    room_list_result = await get_meeting_room_list(_auth=_auth)
    if room_list_result["status"] != "success":
        return room_list_result

    room_names = [r["room_name"] for r in room_list_result["rooms"]]

    rooms_data = []
    total_count = 0
    query = {}

    for room_name in room_names:
        result = await get_meeting_rooms(
            meetingroom=room_name,
            date=date,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            _auth=_auth,
        )
        if result.get("status") == "success" and "room_info" in result:
            ri = result["room_info"]
            rooms_data.append(ri)
            total_count += ri.get("reservation_count", 0)
            if not query:
                query = result.get("query", {})

    suffix = "" if (_auth and _auth.is_authenticated) else " (더미 데이터)"
    return {
        "status": "success",
        "message": f"전체 회의실 {len(rooms_data)}개, 총 예약 {total_count}건 조회 완료{suffix}",
        "query": query,
        "rooms": rooms_data,
        "total_rooms": len(rooms_data),
        "total_reservations": total_count,
    }


async def update_meeting_room(cal_id=None, title=None, title_chg=None,
                              meetingroom_chg=None, date=None, start_time=None,
                              end_time=None, description=None, _auth=None):
    """
    회의실 예약을 변경합니다.

    Args:
        cal_id: 예약 번호
        title: 기존 회의 제목 (검색용)
        title_chg: 변경할 새 제목
        meetingroom_chg: 변경할 회의실 이름
        date: 변경할 날짜
        start_time: 변경할 시작 시간
        end_time: 변경할 종료 시간
        description: 변경할 회의 내용

    Returns:
        dict: 변경 결과
    """
    # 1. 파라미터 준비
    update_params = {}

    if title_chg:
        update_params["title"] = title_chg
    if meetingroom_chg:
        update_params["meetingroom"] = meetingroom_chg
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

    # 2. 시간 범위 검증
    if "start_dt" in update_params and "end_dt" in update_params:
        start_t = update_params["start_dt"].split("T")[1][:5]
        end_t = update_params["end_dt"].split("T")[1][:5]
        is_valid, error_msg = validate_time_range(start_t, end_t)
        if not is_valid:
            return {"status": "error", "message": f"시간 범위 오류: {error_msg}"}

    # 3. 실제 GW API 호출
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.services.api_collection import APICollection
            from app.tasks.node_agent.aiassistant.services.xml_parsing import (
                xml_parsing_search, xml_parsing_result_message, xml_parsing_meeting_insert,
                calendarid_call_meeting, xml_parsing_meetingroom, xml_parsing_meeting_dupinsert,
            )
            from app.tasks.node_agent.aiassistant.db_extract.db_search import OracleSearchClient
            from app.tasks.node_agent.aiassistant.services.meetingroom_html import build_slots_html, dup_html
            from datetime import time as dt_time

            api = APICollection(_auth.stat)
            db = OracleSearchClient(_auth.stat)
            gw_url = _get_gw_url(_auth.stat)

            # 달력 ID
            calendar_id = ""
            try:
                calendar_id = await calendarid_call_meeting(gw_url, _auth.k, _auth.user_id, "", _auth.user_nm)
            except Exception:
                pass

            # 회의실 이름 → CALENDAR_ID
            meetingroom_for_search = meetingroom_chg or ""
            meetingroom_num = ""
            meetingroom_chg_num = ""
            if meetingroom_for_search:
                try:
                    meetingroom_num = await db.meetingroom_db(meetingroom_for_search)
                    meetingroom_chg_num = meetingroom_num
                except Exception:
                    pass
            if meetingroom_chg:
                try:
                    meetingroom_chg_num = await db.meetingroom_db(meetingroom_chg)
                except Exception:
                    pass

            # 일정 검색 (제목으로)
            now_date = datetime.now()
            search_start = now_date.strftime("%Y.%m.%d")
            search_end = (now_date + timedelta(days=30)).strftime("%Y.%m.%d")

            if title:
                response = api.getHsEventList(
                    K=_auth.k,
                    USER_ID=_auth.user_id,
                    DEPT_ID=_auth.dept_id,
                    ORG_USER_ID=_auth.user_id,
                    TARGET_START_DATE=search_start,
                    TARGET_END_DATE=search_end,
                    CALENDAR_IDS=calendar_id,
                    TITLE=title,
                    EQUIPMENT_IDS=meetingroom_num,
                    EVENT_EQUIP_PAGE="equipment_page",
                )

                all_events = await xml_parsing_search(response)
                matching = [e for e in all_events if e.get("title") == title]

                if not matching:
                    return {"status": "not_found", "message": f"'{title}' 제목의 회의실 예약을 찾을 수 없습니다."}

                event = matching[0]
                event_id = event.get("event_id", "")
            elif cal_id:
                event_id = cal_id
                event = {}
            else:
                return {"status": "error", "message": "변경할 예약의 제목(title) 또는 예약번호(cal_id)를 입력해주세요."}

            # 변경할 시간 설정
            select_start_dt = update_params.get("start_dt", event.get("start_date", ""))
            select_end_dt = update_params.get("end_dt", event.get("end_date", ""))

            if select_start_dt and "T" in select_start_dt:
                select_start_dt = select_start_dt.replace("T", " ").replace("-", ".")
                if len(select_start_dt) == 16:
                    select_start_dt += ":00"
            if select_end_dt and "T" in select_end_dt:
                select_end_dt = select_end_dt.replace("T", " ").replace("-", ".")
                if len(select_end_dt) == 16:
                    select_end_dt += ":00"

            select_dt = select_start_dt or event.get("start_date", "")
            final_title = title_chg or event.get("title", title or "")

            # 변경 전 기존 예약 조회 (중복 시 시간대 안내용)
            target_equip = meetingroom_chg_num or meetingroom_num or ""
            target_date = select_start_dt[:10] if select_start_dt else search_start
            target_date_end = (datetime.strptime(target_date.replace(".", "-"), "%Y-%m-%d") + timedelta(days=3)).strftime("%Y.%m.%d")
            if "-" in target_date:
                target_date = target_date.replace("-", ".")
            before_result = []
            if target_equip:
                before_response = api.getHsEventList(
                    K=_auth.k,
                    USER_ID=_auth.user_id,
                    DEPT_ID=_auth.dept_id,
                    ORG_USER_ID=_auth.user_id,
                    TARGET_START_DATE=target_date,
                    TARGET_END_DATE=target_date_end,
                    CALENDAR_IDS=calendar_id,
                    TITLE="",
                    EQUIPMENT_IDS=target_equip,
                    EVENT_EQUIP_PAGE="equipment_page",
                )
                before_result = await xml_parsing_meetingroom(before_response, _auth.stat)

            response = api.update(
                USER_ID=_auth.user_id,
                DEPT_ID=_auth.dept_id,
                USER_NM=_auth.user_nm,
                K=_auth.k,
                EVENT_ID=event_id,
                VIEW="event_openapi_update_data",
                SELECT_DT=select_dt,
                CALENDAR_ID=meetingroom_num or calendar_id,
                TITLE=final_title,
                START_DT=select_start_dt,
                END_DT=select_end_dt,
                EQUIPMENT=meetingroom_chg_num,
                DESCRIPTION=description or event.get("description", ""),
            )

            result_msg = await xml_parsing_result_message(response)
            if result_msg == "성공하였습니다.":
                return {"status": "success", "message": f"예약이 변경되었습니다.", "updated_params": update_params}
            elif result_msg == "중복되었습니다.":
                try:
                    dup = await xml_parsing_meeting_dupinsert(response, _auth.stat)
                    dup_title = dup.get("title", "")
                    dup_name = dup.get("owner_name", "")
                    dup_phone = dup.get("phone", "")
                    dup_date = dup.get("start_date", "") + " ~ " + dup.get("end_date", "")
                    dup_room = dup.get("equipment_nm", meetingroom_chg or "")

                    bookings = []
                    for item in before_result:
                        b_start = item.get("start_date", "").replace(".", "-")
                        b_end = item.get("end_date", "").replace(".", "-")
                        bookings.append((b_start, b_end))

                    date_str = target_date.replace(".", "-")
                    dup_time_html = build_slots_html(
                        date_str, bookings,
                        avail_start=dt_time(8, 0), avail_end=dt_time(23, 0), slot_minutes=60,
                    )
                    full_html = dup_html(
                        date_str, dup_time_html, bookings,
                        dup_title, dup_name, dup_phone, dup_date, dup_room,
                    )

                    return {
                        "status": "duplicate",
                        "message": "변경하려는 시간에 이미 다른 예약이 있습니다.",
                        "html_content": full_html,
                        "text_summary": f"변경하려는 시간({dup_date})에 '{dup_title}' ({dup_name})이 이미 예약되어 있습니다. 시간대별 예약 현황이 HTML로 표시됩니다. 사용자에게 다른 시간을 추천해주세요.",
                    }
                except Exception as e:
                    logger.error(f"update_meeting_room 중복 상세 조회 오류: {e}")
                    return {"status": "duplicate", "message": "변경하려는 시간에 이미 다른 예약이 있습니다."}
            elif "권한" in (result_msg or ""):
                return {"status": "error", "message": "이 예약을 변경할 권한이 없습니다."}
            else:
                return {"status": "error", "message": f"예약 변경에 실패했습니다: {result_msg}"}
        except Exception as e:
            logger.error(f"update_meeting_room API 오류: {e}")
            return {"status": "error", "message": "회의실 예약 변경 중 오류가 발생했습니다."}

    # 4. 더미 데이터 (테스트 환경)
    return {
        "status": "success",
        "message": f"예약 {cal_id or title}이(가) 변경되었습니다. (더미 데이터)",
        "updated_params": update_params,
    }


async def cancel_meeting_room(cal_id=None, title=None, meetingroom=None,
                              date=None, start_time=None, end_time=None, _auth=None):
    """
    회의실 예약을 취소합니다.

    Args:
        cal_id: 취소할 예약 번호
        title: 취소할 회의 제목
        meetingroom: 취소할 회의실 이름
        date: 취소할 예약 날짜
        start_time: 취소할 예약 시작 시간
        end_time: 취소할 예약 종료 시간

    Returns:
        dict: 취소 결과
    """
    search_params = {}
    if cal_id:
        search_params["cal_id"] = cal_id
    if title:
        search_params["title"] = title
    if meetingroom:
        search_params["meetingroom"] = meetingroom
    if date:
        parsed_date = parse_relative_date(date)
        search_params["date"] = parsed_date

    # 실제 GW API 호출
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.services.api_collection import APICollection
            from app.tasks.node_agent.aiassistant.services.xml_parsing import (
                xml_parsing_search, xml_parsing_result_message, calendarid_call_meeting,
            )
            from app.tasks.node_agent.aiassistant.db_extract.db_search import OracleSearchClient

            api = APICollection(_auth.stat)
            db = OracleSearchClient(_auth.stat)
            gw_url = _get_gw_url(_auth.stat)

            # 일정 검색하여 event_id 확보
            calendar_id = ""
            try:
                calendar_id = await calendarid_call_meeting(gw_url, _auth.k, _auth.user_id, "", _auth.user_nm)
            except Exception:
                pass

            meetingroom_num = ""
            if meetingroom:
                try:
                    meetingroom_num = await db.meetingroom_db(meetingroom)
                except Exception:
                    pass

            now_date = datetime.now()
            search_start = parsed_date.replace("-", ".") if date else now_date.strftime("%Y.%m.%d")
            search_end = (datetime.strptime(search_start, "%Y.%m.%d") + timedelta(days=30)).strftime("%Y.%m.%d")

            response = api.getHsEventList(
                K=_auth.k,
                USER_ID=_auth.user_id,
                DEPT_ID=_auth.dept_id,
                ORG_USER_ID=_auth.user_id,
                TARGET_START_DATE=search_start,
                TARGET_END_DATE=search_end,
                CALENDAR_IDS=calendar_id,
                TITLE=title or "",
                EQUIPMENT_IDS=meetingroom_num,
                EVENT_EQUIP_PAGE="equipment_page",
            )

            all_events = await xml_parsing_search(response)
            event_id = None
            select_dt = None

            if title:
                matching = [e for e in all_events if e.get("title") == title]
                if matching:
                    event_id = matching[0].get("event_id")
                    select_dt = matching[0].get("start_date")
            elif cal_id:
                event_id = cal_id

            if not event_id:
                return {"status": "not_found", "message": "취소할 회의실 예약을 찾을 수 없습니다."}

            if not select_dt:
                select_dt = search_start

            result = api.delete(
                USERID=_auth.user_id,
                EVENT_ID=event_id,
                SELECT_DT=select_dt,
                K=_auth.k,
            )

            result_msg = await xml_parsing_result_message(result)
            if result_msg == "성공하였습니다.":
                return {"status": "success", "message": f"예약이 취소되었습니다."}
            elif "권한" in (result_msg or ""):
                return {"status": "error", "message": "이 예약을 취소할 권한이 없습니다."}
            else:
                return {"status": "error", "message": f"예약 취소에 실패했습니다: {result_msg}"}
        except Exception as e:
            logger.error(f"cancel_meeting_room API 오류: {e}")
            return {"status": "error", "message": "회의실 예약 취소 중 오류가 발생했습니다."}

    # 더미 데이터 (테스트 환경)
    return {
        "status": "success",
        "message": f"예약이 취소되었습니다. (더미 데이터)",
    }


async def find_available_room(date, start_time, end_time, min_capacity=None, _auth=None):
    """
    빈 회의실 찾기

    특정 시간대에 예약 가능한 회의실 목록을 조회합니다.

    Args:
        date: 날짜 (YYYY-MM-DD 또는 '오늘', '내일' 등)
        start_time: 시작 시간 (HH:MM)
        end_time: 종료 시간 (HH:MM)
        min_capacity: 최소 수용 인원 (선택)

    Returns:
        dict: 예약 가능한 회의실 목록
    """
    parsed_date = parse_relative_date(date)
    parsed_start = parse_time(start_time)
    parsed_end = parse_time(end_time)

    is_valid, error_msg = validate_time_range(parsed_start, parsed_end)
    if not is_valid:
        return {"status": "error", "message": f"시간 범위 오류: {error_msg}"}

    # 전체 회의실 목록 조회
    all_rooms_result = await get_meeting_room_list(_auth=_auth)
    if all_rooms_result["status"] != "success":
        return all_rooms_result

    all_rooms = all_rooms_result["rooms"]

    # 수용 인원 필터링 (capacity 필드가 있는 경우만)
    if min_capacity:
        all_rooms = [r for r in all_rooms if r.get("capacity", 999) >= min_capacity]

    # 각 회의실의 예약 현황 확인
    available_rooms = []

    for room in all_rooms:
        room_name = room.get("room_name", "")

        reservation_result = await get_meeting_rooms(
            meetingroom=room_name,
            date=date,
            _auth=_auth,
        )

        if reservation_result.get("status") == "success":
            reservations = reservation_result.get("room_info", {}).get("reservations", [])

            # 시간 겹침 확인
            has_conflict = False
            conflicts = []
            req_start = f"{parsed_date.replace('-', '.')} {parsed_start}"
            req_end = f"{parsed_date.replace('-', '.')} {parsed_end}"

            for res in reservations:
                res_start = res.get("start_date", "")
                res_end = res.get("end_date", "")
                # 시간 겹침: 요청 시작 < 기존 종료 AND 요청 종료 > 기존 시작
                if res_start and res_end and req_start < res_end and req_end > res_start:
                    has_conflict = True
                    conflicts.append(res)

            available_rooms.append({
                **room,
                "available": not has_conflict,
                "conflict_count": len(conflicts),
                "conflicts": conflicts if has_conflict else [],
            })

    available_rooms.sort(key=lambda x: (not x["available"], -x.get("capacity", 0)))

    truly_available = [r for r in available_rooms if r["available"]]

    if len(truly_available) == 0:
        return {
            "status": "not_found",
            "message": f"{parsed_date} {parsed_start}-{parsed_end}에 예약 가능한 회의실이 없습니다.",
            "query": {"date": parsed_date, "start_time": parsed_start, "end_time": parsed_end, "min_capacity": min_capacity},
            "available_rooms": [],
            "total_count": 0,
            "all_rooms_with_conflicts": available_rooms,
        }

    return {
        "status": "success",
        "message": f"{len(truly_available)}개의 회의실을 사용할 수 있습니다.",
        "query": {"date": parsed_date, "start_time": parsed_start, "end_time": parsed_end, "min_capacity": min_capacity},
        "available_rooms": truly_available,
        "total_count": len(truly_available),
    }
