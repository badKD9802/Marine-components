"""
날짜 검증 유틸리티

날짜 형식 검증 및 시간 범위 검증
"""

from datetime import datetime
import re


def validate_date_format(date_str: str) -> tuple[bool, str]:
    """
    날짜 형식이 유효한지 검증

    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD 형식)

    Returns:
        tuple: (유효성 여부, 에러 메시지)

    Examples:
        >>> validate_date_format("2026-02-25")
        (True, "")
        >>> validate_date_format("2026-13-01")
        (False, "유효하지 않은 날짜 형식입니다.")
    """
    # 형식 검증
    if not re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        return False, "날짜는 YYYY-MM-DD 형식이어야 합니다."

    # 날짜 유효성 검증
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True, ""
    except ValueError:
        return False, "유효하지 않은 날짜입니다."


def validate_time_format(time_str: str) -> tuple[bool, str]:
    """
    시간 형식이 유효한지 검증

    Args:
        time_str: 시간 문자열 (HH:MM 형식)

    Returns:
        tuple: (유효성 여부, 에러 메시지)

    Examples:
        >>> validate_time_format("09:00")
        (True, "")
        >>> validate_time_format("25:00")
        (False, "유효하지 않은 시간입니다.")
    """
    # 형식 검증
    if not re.match(r'\d{1,2}:\d{2}', time_str):
        return False, "시간은 HH:MM 형식이어야 합니다."

    # 시간 유효성 검증
    try:
        hour, minute = map(int, time_str.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return False, "유효하지 않은 시간입니다."
        return True, ""
    except ValueError:
        return False, "유효하지 않은 시간 형식입니다."


def validate_time_range(start_time: str, end_time: str) -> tuple[bool, str]:
    """
    시작 시간이 종료 시간보다 빠른지 검증

    Args:
        start_time: 시작 시간 (HH:MM)
        end_time: 종료 시간 (HH:MM)

    Returns:
        tuple: (유효성 여부, 에러 메시지)

    Examples:
        >>> validate_time_range("09:00", "18:00")
        (True, "")
        >>> validate_time_range("18:00", "09:00")
        (False, "시작 시간이 종료 시간보다 늦습니다.")
    """
    # 형식 검증
    valid_start, err_start = validate_time_format(start_time)
    if not valid_start:
        return False, f"시작 시간 오류: {err_start}"

    valid_end, err_end = validate_time_format(end_time)
    if not valid_end:
        return False, f"종료 시간 오류: {err_end}"

    # 시간 비교
    start_hour, start_min = map(int, start_time.split(':'))
    end_hour, end_min = map(int, end_time.split(':'))

    start_minutes = start_hour * 60 + start_min
    end_minutes = end_hour * 60 + end_min

    if start_minutes >= end_minutes:
        return False, "시작 시간이 종료 시간보다 늦거나 같습니다."

    return True, ""


def validate_date_range(start_date: str, end_date: str) -> tuple[bool, str]:
    """
    시작 날짜가 종료 날짜보다 빠른지 검증

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)

    Returns:
        tuple: (유효성 여부, 에러 메시지)

    Examples:
        >>> validate_date_range("2026-02-25", "2026-02-28")
        (True, "")
        >>> validate_date_range("2026-02-28", "2026-02-25")
        (False, "시작 날짜가 종료 날짜보다 늦습니다.")
    """
    # 형식 검증
    valid_start, err_start = validate_date_format(start_date)
    if not valid_start:
        return False, f"시작 날짜 오류: {err_start}"

    valid_end, err_end = validate_date_format(end_date)
    if not valid_end:
        return False, f"종료 날짜 오류: {err_end}"

    # 날짜 비교
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        if start_dt > end_dt:
            return False, "시작 날짜가 종료 날짜보다 늦습니다."

        return True, ""
    except ValueError as e:
        return False, f"날짜 비교 오류: {str(e)}"


def is_past_date(date_str: str) -> bool:
    """
    날짜가 과거인지 확인

    Args:
        date_str: 날짜 (YYYY-MM-DD)

    Returns:
        bool: 과거면 True
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        return target_date < today
    except ValueError:
        return False


# 테스트용
if __name__ == "__main__":
    print("=" * 60)
    print("날짜 검증 유틸리티 테스트")
    print("=" * 60)

    # 날짜 형식 검증
    print("\n[날짜 형식 검증]")
    test_dates = ["2026-02-25", "2026-13-01", "2026-02-30", "invalid"]
    for date_str in test_dates:
        valid, msg = validate_date_format(date_str)
        status = "✓" if valid else "✗"
        print(f"  {status} {date_str:15s} → {msg if msg else 'OK'}")

    # 시간 형식 검증
    print("\n[시간 형식 검증]")
    test_times = ["09:00", "25:00", "12:60", "invalid"]
    for time_str in test_times:
        valid, msg = validate_time_format(time_str)
        status = "✓" if valid else "✗"
        print(f"  {status} {time_str:15s} → {msg if msg else 'OK'}")

    # 시간 범위 검증
    print("\n[시간 범위 검증]")
    test_ranges = [
        ("09:00", "18:00"),
        ("18:00", "09:00"),
        ("14:00", "14:00")
    ]
    for start, end in test_ranges:
        valid, msg = validate_time_range(start, end)
        status = "✓" if valid else "✗"
        print(f"  {status} {start} ~ {end} → {msg if msg else 'OK'}")

    # 날짜 범위 검증
    print("\n[날짜 범위 검증]")
    date_ranges = [
        ("2026-02-25", "2026-02-28"),
        ("2026-02-28", "2026-02-25")
    ]
    for start, end in date_ranges:
        valid, msg = validate_date_range(start, end)
        status = "✓" if valid else "✗"
        print(f"  {status} {start} ~ {end} → {msg if msg else 'OK'}")

    print("\n" + "=" * 60)
