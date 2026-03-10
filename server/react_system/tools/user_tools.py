"""
사용자 정보 관리 도구
현재 로그인한 사용자의 정보와 팀 정보를 조회합니다.
"""

import logging

logger = logging.getLogger(__name__)


async def get_my_info(_auth=None):
    """
    내 정보 조회

    Returns:
        dict: 현재 사용자 정보
    """
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.db_extract.db_search_api import OracleSearchClient
            db = OracleSearchClient(_auth.stat)
            df = await db.search_by_empcode(_auth.emp_code)

            if df is not None and not df.empty:
                row = df.iloc[0]
                return {
                    "status": "success",
                    "message": "사용자 정보 조회 완료",
                    "user": {
                        "empno": str(row.get("EMPNO", _auth.emp_code)),
                        "name": str(row.get("EMP_NM", _auth.user_nm)),
                        "position": str(row.get("POSN_NM", "-")),
                        "dept": str(row.get("DEPT_NM", _auth.docdept_nm or "-")),
                        "team": str(row.get("TEAM_NM", "-")),
                        "email": str(row.get("EML", "-")),
                        "phone": str(row.get("TEL_NO", "-")),
                        "mobile": str(row.get("MBPH", "-")),
                        "fax": str(row.get("FAX_NO", "-")),
                        "duty": str(row.get("BIZ", "-")),
                    }
                }
            # DB 조회 결과 없으면 SLO 정보로 최소 응답
            return {
                "status": "success",
                "message": "사용자 기본 정보 조회 완료",
                "user": {
                    "empno": _auth.emp_code or "-",
                    "name": _auth.user_nm or "-",
                    "dept": _auth.docdept_nm or "-",
                }
            }
        except Exception as e:
            logger.error(f"get_my_info API 오류: {e}")

    # 더미 데이터 (테스트 환경 또는 인증 없음)
    return {
        "status": "success",
        "message": "사용자 정보 조회 완료 (더미 데이터)",
        "user": {
            "empno": "2022001",
            "name": "홍길동",
            "position": "팀장",
            "dept": "경영지원팀",
            "team": "재무팀",
            "email": "hong.gd@kamco.co.kr",
            "phone": "02-1234-7001",
            "mobile": "010-1234-7001",
            "fax": "02-1234-7099",
            "duty": "재무 관리",
        }
    }


async def get_my_team(_auth=None):
    """
    내 팀원 목록 조회

    Returns:
        dict: 팀 정보 및 팀원 목록
    """
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.db_extract.db_search_api import OracleSearchClient
            db = OracleSearchClient(_auth.stat)

            # 내 부서/팀 확인
            my_df = await db.search_by_empcode(_auth.emp_code)
            dept_nm = _auth.docdept_nm or ""
            team_nm = ""
            if my_df is not None and not my_df.empty:
                dept_nm = str(my_df.iloc[0].get("DEPT_NM", dept_nm))
                team_nm = str(my_df.iloc[0].get("TEAM_NM", ""))

            # 같은 팀 직원 조회
            search_key = team_nm or dept_nm
            if search_key:
                if team_nm:
                    team_df = await db.search_by_team(team_nm)
                else:
                    team_df = await db.search_by_dept(dept_nm)

                if team_df is not None and not team_df.empty:
                    members = []
                    for _, row in team_df.iterrows():
                        members.append({
                            "empno": str(row.get("EMPNO", "-")),
                            "name": str(row.get("EMP_NM", "-")),
                            "position": str(row.get("POSN_NM", "-")),
                            "email": str(row.get("EML", "-")),
                            "phone": str(row.get("TEL_NO", "-")),
                            "mobile": str(row.get("MBPH", "-")),
                            "is_me": str(row.get("EMPNO", "")) == _auth.emp_code,
                        })
                    return {
                        "status": "success",
                        "message": f"팀 정보 조회 완료 ({len(members)}명)",
                        "team_info": {
                            "team_name": team_nm,
                            "dept_name": dept_nm,
                            "total_count": len(members),
                        },
                        "members": members,
                    }
        except Exception as e:
            logger.error(f"get_my_team API 오류: {e}")

    # 더미 데이터
    return {
        "status": "success",
        "message": "팀 정보 조회 완료 (더미 데이터)",
        "team_info": {
            "team_name": "재무팀",
            "dept_name": "경영지원팀",
            "total_count": 3,
        },
        "members": [
            {"empno": "2022001", "name": "홍길동", "position": "팀장", "email": "hong.gd@kamco.co.kr", "phone": "02-1234-7001", "mobile": "010-1234-7001", "is_me": True},
            {"empno": "2022101", "name": "김철수", "position": "차장", "email": "kim.cs@kamco.co.kr", "phone": "02-1234-7101", "mobile": "010-1234-7101", "is_me": False},
            {"empno": "2022102", "name": "이영희", "position": "과장", "email": "lee.yh@kamco.co.kr", "phone": "02-1234-7102", "mobile": "010-1234-7102", "is_me": False},
        ],
    }


async def get_next_schedule(from_time=None, _auth=None):
    """
    다음 일정 조회

    Args:
        from_time: 기준 시간 (선택, 기본값: 현재)

    Returns:
        dict: 다음 예정된 일정 정보
    """
    from datetime import datetime, timedelta
    from react_system.tools.schedule_tools import get_schedule

    # 기준 시간 설정
    if from_time:
        base_time = datetime.fromisoformat(from_time)
    else:
        base_time = datetime.now()

    # 오늘과 내일 일정 조회 (_auth 전달)
    today = base_time.strftime("%Y-%m-%d")
    tomorrow = (base_time + timedelta(days=1)).strftime("%Y-%m-%d")

    today_schedules = await get_schedule(date=today, _auth=_auth)
    tomorrow_schedules = await get_schedule(date=tomorrow, _auth=_auth)

    all_schedules = []
    if today_schedules.get("status") == "success":
        all_schedules.extend(today_schedules.get("schedules", []))
    if tomorrow_schedules.get("status") == "success":
        all_schedules.extend(tomorrow_schedules.get("schedules", []))

    # 현재 시간 이후 일정 필터링
    future_schedules = []
    for s in all_schedules:
        start_str = s.get('start_date', '')
        if start_str:
            try:
                start_dt = datetime.strptime(start_str, "%Y.%m.%d %H:%M")
            except ValueError:
                continue
            if start_dt > base_time:
                s['_start_dt'] = start_dt
                future_schedules.append(s)

    if not future_schedules:
        return {
            "status": "not_found",
            "message": "다음 일정이 없습니다.",
            "next_schedule": None
        }

    future_schedules.sort(key=lambda x: x['_start_dt'])
    next_schedule = future_schedules[0]

    time_until = next_schedule['_start_dt'] - base_time
    hours = int(time_until.total_seconds() // 3600)
    minutes = int((time_until.total_seconds() % 3600) // 60)

    del next_schedule['_start_dt']

    return {
        "status": "success",
        "message": f"다음 일정은 {hours}시간 {minutes}분 후입니다.",
        "time_until": {
            "hours": hours,
            "minutes": minutes,
            "total_minutes": int(time_until.total_seconds() // 60)
        },
        "next_schedule": next_schedule,
        "total_upcoming": len(future_schedules)
    }
