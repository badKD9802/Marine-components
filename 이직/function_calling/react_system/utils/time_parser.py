"""
시간 파싱 유틸리티

상대적 날짜 표현을 실제 날짜로 변환
예: "내일", "모레", "다음주 월요일" → YYYY-MM-DD
"""

from datetime import datetime, timedelta
import re


def parse_relative_date(date_str: str) -> str:
    """
    상대적 날짜 표현을 YYYY-MM-DD 형식으로 변환

    Args:
        date_str: 날짜 표현 ("오늘", "내일", "모레", "이번주", "다음주" 등)

    Returns:
        str: YYYY-MM-DD 형식 날짜

    Examples:
        >>> parse_relative_date("오늘")
        '2026-02-25'
        >>> parse_relative_date("내일")
        '2026-02-26'
    """
    today = datetime.now()

    # 이미 YYYY-MM-DD 형식이면 그대로 반환
    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        return date_str

    # YYYYMMDD 형식을 YYYY-MM-DD로 변환
    if re.match(r'\d{8}', date_str):
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    date_str_lower = date_str.lower().strip()

    # 오늘
    if "오늘" in date_str_lower or "today" in date_str_lower:
        return today.strftime("%Y-%m-%d")

    # 내일
    if "내일" in date_str_lower or "tomorrow" in date_str_lower:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # 모레
    if "모레" in date_str_lower:
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")

    # 글피
    if "글피" in date_str_lower:
        return (today + timedelta(days=3)).strftime("%Y-%m-%d")

    # 이번주 (월요일 기준)
    if "이번주" in date_str_lower or "this week" in date_str_lower:
        # 이번주 월요일
        days_to_monday = (today.weekday() - 0) % 7
        this_monday = today - timedelta(days=days_to_monday)
        return this_monday.strftime("%Y-%m-%d")

    # 다음주 (월요일 기준)
    if "다음주" in date_str_lower or "next week" in date_str_lower:
        days_to_next_monday = (7 - today.weekday()) % 7
        if days_to_next_monday == 0:
            days_to_next_monday = 7
        next_monday = today + timedelta(days=days_to_next_monday)
        return next_monday.strftime("%Y-%m-%d")

    # 다음달
    if "다음달" in date_str_lower or "next month" in date_str_lower:
        next_month = today.replace(day=1) + timedelta(days=32)
        next_month = next_month.replace(day=1)
        return next_month.strftime("%Y-%m-%d")

    # 파싱 실패 시 오늘 날짜 반환
    return today.strftime("%Y-%m-%d")


def parse_time(time_str: str) -> str:
    """
    시간 표현을 HH:MM 형식으로 변환

    Args:
        time_str: 시간 표현 ("9시", "오후 3시", "14시 30분", "09:00" 등)

    Returns:
        str: HH:MM 형식 시간

    Examples:
        >>> parse_time("9시")
        '09:00'
        >>> parse_time("오후 3시")
        '15:00'
        >>> parse_time("14시 30분")
        '14:30'
    """
    # 이미 HH:MM 형식이면 그대로 반환
    if re.match(r'\d{1,2}:\d{2}', time_str):
        hour, minute = time_str.split(':')
        return f"{int(hour):02d}:{minute}"

    time_str_lower = time_str.lower().strip()

    # 오전/오후 처리
    is_pm = "오후" in time_str_lower or "pm" in time_str_lower

    # 숫자 추출
    numbers = re.findall(r'\d+', time_str_lower)

    if not numbers:
        return "09:00"  # 기본값

    hour = int(numbers[0])
    minute = int(numbers[1]) if len(numbers) > 1 else 0

    # 오후면 12시간 더하기 (12시는 제외)
    if is_pm and hour != 12:
        hour += 12

    # 오전 12시 처리
    if not is_pm and hour == 12:
        hour = 0

    return f"{hour:02d}:{minute:02d}"


def get_weekday_offset(weekday_str: str) -> int:
    """
    요일 문자열을 숫자 오프셋으로 변환

    Args:
        weekday_str: 요일 ("월요일", "화", "수요일" 등)

    Returns:
        int: 0(월) ~ 6(일)
    """
    weekday_map = {
        "월": 0, "월요일": 0, "monday": 0,
        "화": 1, "화요일": 1, "tuesday": 1,
        "수": 2, "수요일": 2, "wednesday": 2,
        "목": 3, "목요일": 3, "thursday": 3,
        "금": 4, "금요일": 4, "friday": 4,
        "토": 5, "토요일": 5, "saturday": 5,
        "일": 6, "일요일": 6, "sunday": 6,
    }

    weekday_lower = weekday_str.lower().strip()
    return weekday_map.get(weekday_lower, 0)


# 테스트용
if __name__ == "__main__":
    print("=" * 60)
    print("시간 파싱 유틸리티 테스트")
    print("=" * 60)

    # 날짜 파싱 테스트
    print("\n[날짜 파싱]")
    test_dates = ["오늘", "내일", "모레", "다음주", "2026-03-01", "20260301"]
    for date_str in test_dates:
        result = parse_relative_date(date_str)
        print(f"  {date_str:15s} → {result}")

    # 시간 파싱 테스트
    print("\n[시간 파싱]")
    test_times = ["9시", "오후 3시", "14시 30분", "09:00", "21:45"]
    for time_str in test_times:
        result = parse_time(time_str)
        print(f"  {time_str:15s} → {result}")

    print("\n" + "=" * 60)
