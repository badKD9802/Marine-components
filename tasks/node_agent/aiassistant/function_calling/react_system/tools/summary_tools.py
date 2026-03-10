"""
요약/통계 도구
주간/월간 요약, 통계 정보를 제공합니다.

⚠️ 참고: 이 도구는 선택적으로 활성화할 수 있습니다.
tool_definitions.py에서 주석 처리하면 비활성화됩니다.
"""

from datetime import datetime, timedelta
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools.schedule_tools import get_schedule
from app.tasks.node_agent.aiassistant.function_calling.react_system.tools.approval_tools import get_my_approvals


def get_weekly_summary(week_offset=0, _auth=None):
    """
    주간 요약 정보

    일정, 회의, 결재 등을 주간 단위로 요약합니다.

    Args:
        week_offset: 주 오프셋 (0=이번주, -1=지난주, 1=다음주)

    Returns:
        dict: 주간 요약 정보
    """

    # ==========================================
    # 1. 주간 범위 계산
    # ==========================================
    today = datetime.now()

    # 이번 주 월요일 찾기
    days_since_monday = today.weekday()  # 0=월요일, 6=일요일
    this_monday = today - timedelta(days=days_since_monday)

    # offset 적용
    target_monday = this_monday + timedelta(weeks=week_offset)
    target_sunday = target_monday + timedelta(days=6)

    # 날짜 문자열
    start_date = target_monday.strftime("%Y-%m-%d")
    end_date = target_sunday.strftime("%Y-%m-%d")
    week_label = target_monday.strftime("%Y년 %W주차")
    date_range = f"{target_monday.strftime('%m.%d')} ~ {target_sunday.strftime('%m.%d')}"

    # ==========================================
    # 2. 일정 조회
    # ==========================================
    schedules_result = get_schedule(
        date_range_start=start_date,
        date_range_end=end_date
    )

    total_schedules = 0
    total_meetings = 0
    busiest_day = None
    schedules_by_day = {}

    if schedules_result.get('status') == 'success':
        schedules = schedules_result.get('schedules', [])
        total_schedules = len(schedules)

        # 회의 카운트 (제목에 "회의" 포함)
        total_meetings = sum(1 for s in schedules if '회의' in s.get('title', ''))

        # 요일별 일정 수
        for s in schedules:
            start_date_str = s.get('start_date', '')[:10]  # "2026.02.27" 형식
            if start_date_str not in schedules_by_day:
                schedules_by_day[start_date_str] = 0
            schedules_by_day[start_date_str] += 1

        # 가장 바쁜 날
        if schedules_by_day:
            busiest_date = max(schedules_by_day, key=schedules_by_day.get)
            busiest_count = schedules_by_day[busiest_date]
            # 요일 변환
            busiest_dt = datetime.strptime(busiest_date, "%Y.%m.%d")
            weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
            busiest_day = {
                "date": busiest_date,
                "weekday": weekday_names[busiest_dt.weekday()],
                "count": busiest_count
            }

    # ==========================================
    # 3. 결재 조회
    # ==========================================
    # TODO: 기간별 결재 조회가 가능하면 사용
    # 현재는 전체 결재 조회
    approvals_result = get_my_approvals()

    total_approvals = 0
    approved_count = 0
    rejected_count = 0
    pending_count = 0

    if approvals_result.get('status') == 'success':
        approvals = approvals_result.get('approvals', [])
        total_approvals = len(approvals)

        # 상태별 카운트
        for a in approvals:
            status = a.get('status', '')
            if status == 'approved':
                approved_count += 1
            elif status == 'rejected':
                rejected_count += 1
            elif status == 'pending':
                pending_count += 1

    # ==========================================
    # 4. 여유 시간 찾기 (간단 버전)
    # ==========================================
    free_time = None
    if schedules_by_day:
        # 일정이 가장 적은 날 찾기
        quietest_date = min(schedules_by_day, key=schedules_by_day.get)
        quietest_dt = datetime.strptime(quietest_date, "%Y.%m.%d")
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        free_time = {
            "date": quietest_date,
            "weekday": weekday_names[quietest_dt.weekday()],
            "count": schedules_by_day[quietest_date]
        }

    # ==========================================
    # 5. 결과 반환
    # ==========================================
    return {
        "status": "success",
        "message": f"{week_label} 주간 요약",
        "week_info": {
            "week_label": week_label,
            "date_range": date_range,
            "start_date": start_date,
            "end_date": end_date,
            "week_offset": week_offset
        },
        "summary": {
            "total_schedules": total_schedules,
            "total_meetings": total_meetings,
            "total_approvals": total_approvals,
            "approved": approved_count,
            "rejected": rejected_count,
            "pending": pending_count
        },
        "insights": {
            "busiest_day": busiest_day,
            "free_time": free_time,
            "schedules_by_day": schedules_by_day
        }
    }


# ==========================================
# 테스트용
# ==========================================
if __name__ == "__main__":
    print("=" * 70)
    print("요약 도구 테스트")
    print("=" * 70)

    # 테스트 1: 이번 주 요약
    print("\n[테스트 1: 이번 주 요약]")
    result1 = get_weekly_summary(week_offset=0)
    print(f"상태: {result1['status']}")
    print(f"주차: {result1['week_info']['week_label']}")
    print(f"기간: {result1['week_info']['date_range']}")
    print(f"총 일정: {result1['summary']['total_schedules']}개")
    print(f"회의: {result1['summary']['total_meetings']}개")
    if result1['insights']['busiest_day']:
        bd = result1['insights']['busiest_day']
        print(f"가장 바쁜 날: {bd['weekday']} ({bd['count']}개 일정)")

    # 테스트 2: 지난 주 요약
    print("\n[테스트 2: 지난 주 요약]")
    result2 = get_weekly_summary(week_offset=-1)
    print(f"주차: {result2['week_info']['week_label']}")
    print(f"기간: {result2['week_info']['date_range']}")

    print("\n" + "=" * 70)
