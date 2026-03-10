"""
임원 일정 조회 도구
임원(경영진)의 일정을 조회합니다.

일정 관리 도구와 동일한 패턴 적용:
- 날짜/시간 파싱 (utils 활용)
- 더미 데이터 반환
- 실제 API 호출 준비 (주석 처리)
"""

import logging
import json
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
from app.tasks.node_agent.aiassistant.function_calling.react_system.utils import parse_relative_date
from app.tasks.lib_justtype.common import util

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== EXECUTIVE TOOLS ==")


async def get_executive_schedule(
    executive_name=None,
    position=None,
    date=None,
    date_range_start=None,
    date_range_end=None,
    _auth=None,
):
    """
    임원(경영진)의 일정을 조회합니다.

    Args:
        executive_name: 임원 이름 (예: 홍길동)
        position: 직책 (예: 사장, 부사장, 본부장)
        date: 조회할 날짜 (YYYY-MM-DD 또는 '오늘', '내일' 등)
        date_range_start: 조회 시작 날짜
        date_range_end: 조회 종료 날짜

    Returns:
        dict: 임원 일정 목록
    """

    # ==========================================
    # 1. 날짜 파싱
    # ==========================================
    now_date = datetime.now()
    if date:
        parsed_date = parse_relative_date(date)
        start_dt = f"{parsed_date} 00:00"
        end_dt = f"{parsed_date} 23:59"
    elif date_range_start and date_range_end:
        parsed_start = parse_relative_date(date_range_start)
        parsed_end = parse_relative_date(date_range_end)
        start_dt = f"{parsed_start} 00:00"
        end_dt = f"{parsed_end} 23:59"
    else:
        start_dt = (now_date - relativedelta(weeks=1)).strftime("%Y-%m-%d %H:%M")
        end_dt = (now_date + relativedelta(weeks=1)).strftime("%Y-%m-%d %H:%M")

    # ==========================================
    # 2. 실제 DB API 호출
    # ==========================================
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.lib_justtype.common.just_env import JustEnv
            from app.tasks.node_agent.aiassistant.db_extract.db_search import OracleSearchClient

            env = JustEnv(_auth.stat)
            db = OracleSearchClient(_auth.stat)

            ai_config = env.get_config("aiassistant")
            db_api = ai_config.get("db_api", {})
            db_api_url = db_api.get("db_api_url", "")
            headers = {"K-API-KEY": _auth.k}

            # 이름에서 존칭 제거
            search_name = (executive_name or "").replace("님", "").strip()

            # 직위 목록 조회 (이름이 실제로 직위인지 확인)
            try:
                unique_posnm_df = await db.imwon_posnm()
                unique_pos_nm = list(unique_posnm_df["POS_NAME"].unique())
                if search_name and any(search_name.replace(" ", "") == w.replace(" ", "") for w in unique_pos_nm):
                    # 이름이 실제로는 직위 → position으로 이동
                    if not position:
                        position = search_name
                    search_name = ""
            except Exception:
                unique_pos_nm = []

            if not search_name and not position:
                return {"status": "error", "message": "임원 이름 또는 직위를 입력해주세요."}

            # 직위 검색 vs 이름 검색
            if position and not search_name:
                query_id = "get_imwon_sch_pos"
                ex_name = position
            else:
                query_id = "get_imwon_sch_name"
                ex_name = search_name

            data = {
                "query_id": query_id,
                "params": {
                    "ex_end_date": end_dt,
                    "ex_start_date": start_dt,
                    "ex_name": ex_name,
                },
            }
            response = requests.post(db_api_url, json=data, headers=headers)
            imwon_result = json.loads(response.text).get("data", [])

            if not imwon_result:
                return {
                    "status": "not_found",
                    "message": "조회된 임원 일정이 없습니다.",
                    "query": {"executive_name": executive_name, "position": position, "start_dt": start_dt, "end_dt": end_dt},
                    "executives": [],
                    "total_count": 0,
                }

            # DB 결과를 tool 형식으로 변환 (임원별 그룹핑)
            exec_map = {}
            for item in imwon_result:
                if not item.get("MEMO"):
                    continue
                name_key = item.get("NAME", "")
                if name_key not in exec_map:
                    exec_map[name_key] = {
                        "executive": {"name": name_key, "position": item.get("POS_NAME", "-")},
                        "schedules": [],
                    }
                sta_ymd = item.get("STA_YMD", "")
                end_ymd = item.get("END_YMD", "")
                try:
                    sta_dt = datetime.strptime(sta_ymd, "%Y-%m-%dT%H:%M:%S") if sta_ymd else None
                    end_d = datetime.strptime(end_ymd, "%Y-%m-%dT%H:%M:%S") if end_ymd else None
                except (ValueError, TypeError):
                    sta_dt = None
                    end_d = None
                exec_map[name_key]["schedules"].append({
                    "num": f"EXE-{len(exec_map[name_key]['schedules']) + 1:03d}",
                    "title": item.get("MEMO", ""),
                    "start_dt": sta_dt.strftime("%Y-%m-%d %H:%M") if sta_dt else sta_ymd,
                    "end_dt": end_d.strftime("%Y-%m-%d %H:%M") if end_d else end_ymd,
                    "date": sta_dt.strftime("%Y-%m-%d") if sta_dt else "",
                })

            executives = list(exec_map.values())
            total_schedules = sum(len(e["schedules"]) for e in executives)
            return {
                "status": "success",
                "message": f"{len(executives)}명의 임원, 총 {total_schedules}개의 일정을 찾았습니다.",
                "query": {"executive_name": executive_name, "position": position, "start_dt": start_dt, "end_dt": end_dt},
                "executives": executives,
                "total_count": len(executives),
            }
        except Exception as e:
            logger.error(f"get_executive_schedule API 오류: {e}")

    # ==========================================
    # 3. 더미 데이터 생성 (테스트 환경)
    # ==========================================
    # 조회 날짜 기준
    query_date = parsed_date if date else datetime.now().strftime("%Y-%m-%d")

    # 임원 더미 데이터 (KAMCO 조직 구조 반영)
    mock_executives = [
        {
            "executive": {
                "name": "김태영",
                "position": "사장",
            },
            "schedules": [
                {
                    "num": "EXE-001",
                    "title": "이사회",
                    "start_dt": f"{query_date} 09:00",
                    "end_dt": f"{query_date} 11:00",
                    "date": query_date,
                },
                {
                    "num": "EXE-002",
                    "title": "경영진 회의",
                    "start_dt": f"{query_date} 14:00",
                    "end_dt": f"{query_date} 16:00",
                    "date": query_date,
                }
            ]
        },
        {
            "executive": {
                "name": "이민호",
                "position": "부사장",
            },
            "schedules": [
                {
                    "num": "EXE-003",
                    "title": "채권관리 전략회의",
                    "start_dt": f"{query_date} 10:00",
                    "end_dt": f"{query_date} 12:00",
                    "date": query_date,
                },
                {
                    "num": "EXE-004",
                    "title": "고객사 미팅",
                    "start_dt": f"{query_date} 15:00",
                    "end_dt": f"{query_date} 17:00",
                    "date": query_date,
                }
            ]
        },
        {
            "executive": {
                "name": "박서현",
                "position": "전무",
            },
            "schedules": [
                {
                    "num": "EXE-005",
                    "title": "디지털 전환 TF",
                    "start_dt": f"{query_date} 11:00",
                    "end_dt": f"{query_date} 12:30",
                    "date": query_date,
                }
            ]
        },
        {
            "executive": {
                "name": "최진우",
                "position": "상무",
            },
            "schedules": [
                {
                    "num": "EXE-006",
                    "title": "예산 검토 회의",
                    "start_dt": f"{query_date} 13:00",
                    "end_dt": f"{query_date} 14:30",
                    "date": query_date,
                }
            ]
        }
    ]


    # ==========================================
    # 4. 필터링 (검색 조건)
    # ==========================================
    filtered_executives = mock_executives

    # 임원 이름으로 필터링
    if executive_name:
        filtered_executives = [
            e for e in filtered_executives
            if executive_name in e["executive"]["name"]
        ]

    # 직책으로 필터링
    if position:
        filtered_executives = [
            e for e in filtered_executives
            if position in e["executive"]["position"]
        ]


    # ==========================================
    # 5. 결과 반환
    # ==========================================
    total_executives = len(filtered_executives)
    total_schedules = sum(len(e["schedules"]) for e in filtered_executives)

    if total_executives == 0:
        return {
            "status": "not_found",
            "message": "조회된 임원 일정이 없습니다.",
            "query": {
                "executive_name": executive_name,
                "position": position,
                "start_dt": start_dt,
                "end_dt": end_dt
            },
            "executives": [],
            "total_count": 0
        }

    return {
        "status": "success",
        "message": f"{total_executives}명의 임원, 총 {total_schedules}개의 일정을 찾았습니다. (더미 데이터)",
        "query": {
            "executive_name": executive_name,
            "position": position,
            "start_dt": start_dt,
            "end_dt": end_dt
        },
        "executives": filtered_executives,
        "total_count": total_executives
    }
