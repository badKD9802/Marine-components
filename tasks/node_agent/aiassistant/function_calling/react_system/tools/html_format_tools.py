"""
HTML 포맷 도구
일정/회의실 조회 결과를 HTML 형식으로 변환합니다.

2가지 포맷 제공:
1. 달력 형식 - 월별 캘린더 뷰 (원본 calendar_html.py 재사용)
2. 표 형식 - 단순 테이블 목록

결과가 많을 때 (10개 이상) 사용자에게 선택지 제안:
- "달력 또는 표 형식으로 보여드릴까요?"
"""

import os
import webbrowser
from datetime import datetime
import sys
import calendar
import re
from typing import List, Dict
from collections import defaultdict

# 로그 파일 경로
LOG_FILE = os.path.expanduser("~/Desktop/KAMCO_HTML_결과/html_format_debug.log")

def clear_log():
    """로그 파일 초기화"""
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"=== HTML 포맷 도구 디버그 로그 시작 ({datetime.now()}) ===\n\n")
    except:
        pass

def log_debug(message):
    """디버그 메시지를 콘솔과 파일에 동시 출력"""
    print(message)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except:
        pass  # 파일 쓰기 실패해도 무시

# 모듈 로드 시 로그 초기화
clear_log()

# 원본 calendar_html 모듈 import
# Windows와 WSL 둘 다 지원
def get_chatsam_path():
    """chatsam 경로를 자동으로 찾기"""
    possible_paths = [
        # Windows 경로
        r"C:\Users\qorud\Desktop\KAMCO_프로젝트\chatsam\chatsam\app\tasks\node_agent\aiassistant\services",
        # WSL 경로
        "/mnt/c/Users/qorud/Desktop/KAMCO_프로젝트/chatsam/chatsam/app/tasks/node_agent/aiassistant/services",
        # 상대 경로 (혹시 모를 경우)
        os.path.join(os.path.dirname(__file__), "../../../chatsam/chatsam/app/tasks/node_agent/aiassistant/services")
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None

chatsam_path = get_chatsam_path()
if chatsam_path and chatsam_path not in sys.path:
    sys.path.insert(0, chatsam_path)

try:
    from app.tasks.node_agent.aiassistant.services.calendar_html import render_graphic_calendar
    CALENDAR_AVAILABLE = True
    log_debug(f"[INFO] calendar_html.py 로드 성공")
except ImportError as e:
    CALENDAR_AVAILABLE = False
    log_debug(f"[WARNING] calendar_html.py를 찾을 수 없습니다: {e}")


def _extract_meeting_reservations(meeting_data, meetingroom_name=None):
    """
    meeting_data에서 reservations와 room_name을 추출합니다.
    LLM이 불완전한 데이터를 전달할 경우 자동 재조회합니다.

    Returns:
        tuple: (reservations: list, room_name: str)
    """
    # 1. 정상: get_meeting_rooms() 결과 전체
    if isinstance(meeting_data, dict) and 'room_info' in meeting_data:
        room_info = meeting_data['room_info']
        return room_info.get('reservations', []), room_info.get('meetingroom', meetingroom_name or '회의실')

    # 2. room_info만 전달된 경우
    if isinstance(meeting_data, dict) and 'reservations' in meeting_data:
        return meeting_data['reservations'], meeting_data.get('meetingroom', meetingroom_name or '회의실')

    # 3. reservations 배열만 전달된 경우
    if isinstance(meeting_data, list):
        return meeting_data, meetingroom_name or '회의실'

    # 4. fallback: 불완전한 dict → 회의실명을 찾아서 재조회
    room_to_fetch = None
    if isinstance(meeting_data, dict):
        # query.meetingroom 또는 meetingroom 키에서 회의실명 추출
        room_to_fetch = (
            meeting_data.get('meetingroom')
            or (meeting_data.get('query', {}) or {}).get('meetingroom')
            or (meeting_data.get('room_info', {}) or {}).get('meetingroom')
        )
    if not room_to_fetch:
        room_to_fetch = meetingroom_name

    if room_to_fetch:
        log_debug(f"[INFO] meeting_data 불완전 → '{room_to_fetch}' 자동 재조회")
        try:
            from app.tasks.node_agent.aiassistant.function_calling.react_system.tools.meeting_tools import get_meeting_rooms
            # query에 날짜 정보가 있으면 활용
            query = (meeting_data.get('query', {}) or {}) if isinstance(meeting_data, dict) else {}
            fetch_kwargs = {"meetingroom": room_to_fetch}
            if query.get('start_dt') and query.get('end_dt'):
                fetch_kwargs["date_range_start"] = query['start_dt'][:10]
                fetch_kwargs["date_range_end"] = query['end_dt'][:10]
            refetched = get_meeting_rooms(**fetch_kwargs)
            if refetched.get('status') == 'success' and 'room_info' in refetched:
                ri = refetched['room_info']
                return ri.get('reservations', []), ri.get('meetingroom', room_to_fetch)
        except Exception as e:
            log_debug(f"[WARNING] 자동 재조회 실패: {e}")

    return [], meetingroom_name or '회의실'


def _save_and_open_html(html_content, title="result"):
    """
    HTML을 파일로 저장하고 브라우저에서 자동으로 엽니다.

    Args:
        html_content: HTML 문자열
        title: 파일명에 사용할 제목

    Returns:
        str: 저장된 파일 경로 안내 메시지
    """
    try:
        # 임시 디렉토리 생성
        output_dir = os.path.expanduser("~/Desktop/KAMCO_HTML_결과")
        os.makedirs(output_dir, exist_ok=True)

        # 타임스탬프 포함 파일명
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{title}_{timestamp}.html"
        filepath = os.path.join(output_dir, filename)

        # 완전한 HTML 문서로 래핑
        full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Malgun Gothic', sans-serif;
            padding: 20px;
            background: #f5f5f5;
            max-width: 1400px;
            margin: 0 auto;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""

        # 파일 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_html)

        # 브라우저에서 열기 시도
        try:
            webbrowser.open('file://' + os.path.abspath(filepath))
            return f"✅ HTML이 생성되어 브라우저에서 열렸습니다!\n📁 저장 위치: {filepath}"
        except:
            return f"✅ HTML이 생성되었습니다.\n📁 파일 위치: {filepath}\n💡 브라우저에서 직접 열어주세요."

    except Exception as e:
        return f"❌ 파일 저장 중 오류: {str(e)}"


# ============================================================================
# 일정 - 달력 형식
# ============================================================================
def format_schedule_as_calendar(schedules, user_name="사용자", start_dt=None, end_dt=None, _auth=None):
    """
    일정 목록을 달력 형식으로 변환합니다.
    원본 calendar_html.py의 render_graphic_calendar 함수를 재사용합니다.

    Args:
        schedules: 일정 목록 (list of dict) 또는 get_schedule() 결과 전체
        user_name: 사용자 이름
        start_dt: 조회 시작 날짜 (YYYY.MM.DD)
        end_dt: 조회 종료 날짜 (YYYY.MM.DD)

    Returns:
        str: 파일 저장 안내 메시지
    """
    log_debug(f"[DEBUG] ===== format_schedule_as_calendar 함수 진입 =====")
    log_debug(f"[DEBUG] 받은 파라미터: schedules={type(schedules)}, user_name={user_name}, start_dt={start_dt}, end_dt={end_dt}")
    try:
        log_debug(f"[DEBUG] format_schedule_as_calendar 호출됨")
        log_debug(f"[DEBUG] schedules 타입: {type(schedules)}")
        log_debug(f"[DEBUG] schedules 내용 (처음 200자): {str(schedules)[:200]}")
        log_debug(f"[DEBUG] user_name: {user_name}, start_dt: {start_dt}, end_dt: {end_dt}")

        # calendar_html 모듈 사용 불가능한 경우
        if not CALENDAR_AVAILABLE:
            return {
                "status": "error",
                "message": "❌ 달력 형식을 사용할 수 없습니다. calendar_html.py 모듈이 필요합니다."
            }

        # AI가 get_schedule() 결과 전체를 전달한 경우 처리
        query_info = None
        if isinstance(schedules, dict):
            log_debug(f"[DEBUG] schedules는 dict입니다. keys: {list(schedules.keys())}")
            # query 정보 추출 (있으면)
            if 'query' in schedules:
                query_info = schedules['query']
                log_debug(f"[DEBUG] ✅ query 정보 발견!")
                log_debug(f"[DEBUG] query 내용: {query_info}")
                log_debug(f"[DEBUG] query['start_dt'] = {query_info.get('start_dt')}")
                log_debug(f"[DEBUG] query['end_dt'] = {query_info.get('end_dt')}")
            else:
                log_debug(f"[WARNING] query 정보가 없습니다!")
            # schedules 배열 추출
            if 'schedules' in schedules:
                schedules = schedules['schedules']
                log_debug(f"[DEBUG] schedules 배열 추출, 개수: {len(schedules)}")
            else:
                log_debug(f"[WARNING] schedules 키가 없습니다!")

        if not schedules or not isinstance(schedules, list):
            log_debug(f"[DEBUG] schedules가 비어있거나 리스트가 아님")
            return {
                "status": "error",
                "message": f"❌ 일정 데이터가 올바르지 않습니다. (타입: {type(schedules)}, 값: {schedules})"
            }

        # 날짜 형식 확인 및 기본값 설정
        # 우선순위: 1) query 정보 (항상 우선!) 2) 파라미터 3) schedules에서 추출 4) 오늘 날짜
        log_debug(f"[DEBUG] === 날짜 추출 시작 ===")
        log_debug(f"[DEBUG] 초기 start_dt={start_dt}, end_dt={end_dt}")
        log_debug(f"[DEBUG] query_info={query_info}")

        if query_info:
            log_debug(f"[DEBUG] query_info가 있습니다! 날짜 추출 시도...")
            # query에서 날짜 추출 (ISO 형식 → YYYY.MM.DD 형식) - 항상 우선 사용!
            try:
                if 'start_dt' in query_info and query_info['start_dt']:
                    original_start = query_info['start_dt']
                    start_dt = query_info['start_dt'][:10].replace('-', '.')
                    log_debug(f"[DEBUG] ✅ query에서 start_dt 추출 성공: {original_start} → {start_dt}")
                else:
                    log_debug(f"[WARNING] query에 start_dt가 없거나 비어있음")

                if 'end_dt' in query_info and query_info['end_dt']:
                    original_end = query_info['end_dt']
                    end_dt = query_info['end_dt'][:10].replace('-', '.')
                    log_debug(f"[DEBUG] ✅ query에서 end_dt 추출 성공: {original_end} → {end_dt}")
                else:
                    log_debug(f"[WARNING] query에 end_dt가 없거나 비어있음")
            except Exception as e:
                log_debug(f"[WARNING] query에서 날짜 추출 실패: {e}")
                import traceback
                log_debug(traceback.format_exc())
        else:
            log_debug(f"[WARNING] query_info가 None입니다!")

        log_debug(f"[DEBUG] query 처리 후 start_dt={start_dt}, end_dt={end_dt}")

        if not start_dt or not end_dt:
            log_debug(f"[WARNING] start_dt 또는 end_dt가 비어있음! schedules에서 추출 시도...")
            # 첫 일정과 마지막 일정의 날짜 추출
            dates = [s.get('start_date', '')[:10] for s in schedules if s.get('start_date')]
            log_debug(f"[DEBUG] schedules에서 추출한 날짜들: {dates}")
            if dates:
                start_dt = min(dates) if not start_dt else start_dt
                end_dt = max(dates) if not end_dt else end_dt
                log_debug(f"[DEBUG] schedules에서 날짜 추출: {start_dt} ~ {end_dt}")
            else:
                today = datetime.now().strftime("%Y.%m.%d")
                start_dt = end_dt = today
                log_debug(f"[WARNING] ⚠️ 기본값 사용 (오늘): {start_dt}")
        else:
            log_debug(f"[DEBUG] ✅ 최종 날짜 확정: {start_dt} ~ {end_dt}")

        # render_graphic_calendar 호출
        title = f"{user_name}님의 일정"
        log_debug(f"[DEBUG] === render_graphic_calendar 호출 ===")
        log_debug(f"[DEBUG] title={title}")
        log_debug(f"[DEBUG] start_dt={start_dt}")
        log_debug(f"[DEBUG] end_dt={end_dt}")
        log_debug(f"[DEBUG] schedules 개수={len(schedules)}")
        html_content = render_graphic_calendar(schedules, title, start_dt, end_dt)
        log_debug(f"[DEBUG] ✅ render_graphic_calendar 완료")

        return {
            "status": "success",
            "html_content": html_content
        }

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_msg = f"❌ HTML 생성 실패!\n📋 에러: {str(e)}\n📜 스택:\n{error_details}"
        log_debug(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }


# ============================================================================
# 일정 - 표 형식
# ============================================================================
def format_schedule_as_table(schedules, user_name="사용자", start_dt=None, end_dt=None, _auth=None):
    """
    일정 목록을 카드 리스트 형식으로 변환합니다.
    날짜별 그룹핑 + 좌측 컬러 바로 달력 구분.

    Args:
        schedules: 일정 목록 (list of dict)
        user_name: 사용자 이름
        start_dt: 조회 시작 날짜
        end_dt: 조회 종료 날짜

    Returns:
        dict: HTML 결과
    """
    log_debug(f"[DEBUG] ===== format_schedule_as_table 함수 진입 =====")
    try:
        # AI가 get_schedule() 결과 전체를 전달한 경우 처리
        query_info = None
        if isinstance(schedules, dict):
            if 'query' in schedules:
                query_info = schedules['query']
            if 'schedules' in schedules:
                schedules = schedules['schedules']

        if not schedules or not isinstance(schedules, list):
            return {
                "status": "error",
                "message": f"일정 데이터가 올바르지 않습니다. (타입: {type(schedules)}, 값: {schedules})"
            }

        # 날짜 자동 추출 (query 정보 항상 우선!)
        if query_info:
            try:
                if 'start_dt' in query_info and query_info['start_dt']:
                    start_dt = query_info['start_dt'][:10].replace('-', '.')
                if 'end_dt' in query_info and query_info['end_dt']:
                    end_dt = query_info['end_dt'][:10].replace('-', '.')
            except Exception as e:
                log_debug(f"[WARNING] query에서 날짜 추출 실패: {e}")

        if not start_dt or not end_dt:
            dates = [s.get('start_date', '')[:10] for s in schedules if s.get('start_date')]
            if dates:
                start_dt = min(dates) if not start_dt else start_dt
                end_dt = max(dates) if not end_dt else end_dt

        # ============================================================
        # 날짜별 그룹핑
        # ============================================================
        WEEKDAYS_KR = ['월', '화', '수', '목', '금', '토', '일']
        CAL_COLORS = {
            '나의달력': '#6366F1',
            '업무달력': '#10B981',
            '공유일정': '#F59E0B',
        }
        DEFAULT_COLOR = '#6366F1'

        grouped = defaultdict(list)
        for s in schedules:
            date_key = s.get('start_date', '')[:10]
            if date_key:
                grouped[date_key].append(s)

        count = len(schedules)
        date_range = f"{start_dt or '오늘'} ~ {end_dt or '오늘'}"

        # ============================================================
        # 달력 필터용 — 사용 중인 달력 목록 추출
        # ============================================================
        used_calendars = []
        seen_cal = set()
        for s in schedules:
            cal = s.get('calendar_nm', '나의달력')
            if cal not in seen_cal:
                seen_cal.add(cal)
                used_calendars.append(cal)

        # 달력별 CSS 클래스명 생성 (한글 → 인덱스 기반)
        cal_class_map = {cal: f"sch-cal-{i}" for i, cal in enumerate(used_calendars)}

        # ============================================================
        # 카드 리스트 HTML 생성
        # ============================================================

        # CSS-only 달력 필터 스타일
        filter_css = ""
        for cal, cls in cal_class_map.items():
            color = CAL_COLORS.get(cal, DEFAULT_COLOR)
            # 체크 해제 시 카드 숨기기 + 라벨 스타일 변경 (반투명 + 취소선)
            filter_css += f"#sch-toggle-{cls}:not(:checked) ~ .sch-body .{cls} {{ display:none !important; }}\n"
            filter_css += (
                f"#sch-toggle-{cls}:not(:checked) ~ .sch-body .sch-label-{cls} {{"
                f" opacity:0.4; text-decoration:line-through; background:transparent !important;"
                f" border-style:dashed !important; }}\n"
            )

        # 체크박스 (숨김)
        checkboxes_html = ""
        for cal in used_calendars:
            cls = cal_class_map[cal]
            checkboxes_html += f'<input type="checkbox" id="sch-toggle-{cls}" checked style="display:none;">\n'

        # 필터 라벨 버튼
        filter_labels = ""
        for cal in used_calendars:
            cls = cal_class_map[cal]
            color = CAL_COLORS.get(cal, DEFAULT_COLOR)
            filter_labels += (
                f'<label for="sch-toggle-{cls}" class="sch-label-{cls}" style="cursor:pointer;display:inline-flex;align-items:center;gap:5px;'
                f'padding:4px 12px;border-radius:20px;border:1.5px solid {color};font-size:0.92em;font-weight:600;'
                f'color:{color};background:{color}15;user-select:none;">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{color};display:inline-block;"></span>'
                f'{cal}</label>\n'
            )

        html = f"""
<style>
{filter_css}
summary::-webkit-details-marker {{ display:none; }}
summary::marker {{ display:none; }}
</style>
{checkboxes_html}
<div class="sch-body" style="font-family:'Pretendard','Malgun Gothic',-apple-system,sans-serif; max-width:100%; border-radius:14px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.08); background:#fff;">
    <div style="display:flex;align-items:center;gap:12px;padding:12px 18px;background:linear-gradient(135deg,#8B8FF7,#A5A8FC);">
        <span style="font-size:1.05em;font-weight:700;color:#fff;">{user_name}님의 일정</span>
        <span style="color:rgba(255,255,255,0.6);">|</span>
        <span style="font-size:0.95em;color:rgba(255,255,255,0.85);">{date_range}</span>
        <span style="color:rgba(255,255,255,0.6);">|</span>
        <span style="font-size:0.95em;color:rgba(255,255,255,0.85);">총 {count}건</span>
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;padding:10px 18px;border-bottom:1px solid #e2e8f0;">
        {filter_labels}
    </div>
    <div style="padding:6px 0;">
"""

        for date_key in sorted(grouped.keys()):
            items = grouped[date_key]
            # 날짜 파싱
            try:
                dt = datetime.strptime(date_key, "%Y.%m.%d")
                date_label = f"{dt.month}월 {dt.day}일 ({WEEKDAYS_KR[dt.weekday()]})"
            except:
                date_label = date_key

            # 날짜 그룹 — 접기/펼치기 (기본 펼침)
            html += f"""
        <details open style="margin-bottom:4px;">
            <summary style="cursor:pointer; list-style:none; display:flex; align-items:center; padding:10px 20px 6px; gap:8px;">
                <span style="font-size:1.05em; font-weight:700; color:#1e293b;">{date_label}</span>
                <span style="flex:1; height:1px; background:#e2e8f0;"></span>
                <span style="font-size:0.85em; color:#94a3b8; font-weight:600;">{len(items)}건</span>
            </summary>
            <div style="display:flex; flex-wrap:wrap; gap:8px; padding:0 14px 6px;">
"""

            for item in items:
                title = item.get('title', '제목 없음')
                start_date = item.get('start_date', '')
                end_date = item.get('end_date', '')
                description = item.get('description', '') or ''
                calendar_nm = item.get('calendar_nm', '나의달력')
                owner_name = item.get('owner_name', '-')
                bar_color = CAL_COLORS.get(calendar_nm, DEFAULT_COLOR)
                card_cls = cal_class_map.get(calendar_nm, '')

                # 시간 추출 (HH:MM)
                start_time = start_date[11:16] if len(start_date) > 15 else ''
                end_time = end_date[11:16] if len(end_date) > 15 else ''
                time_str = f"{start_time} - {end_time}" if start_time and end_time else (start_time or '-')

                html += f"""
                <div class="{card_cls}" style="flex:1 1 calc(50% - 8px); min-width:280px; padding:10px 14px; border-left:4px solid {bar_color}; border-radius:0 8px 8px 0; background:#fff; box-sizing:border-box;">
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:3px;">
                        <span style="font-size:1.0em; font-weight:600; color:#64748b; min-width:100px;">{time_str}</span>
                        <span style="font-size:1.12em; font-weight:700; color:#1e293b;">{title}</span>
                    </div>"""

                if description:
                    html += f"""
                    <div style="font-size:1.0em; color:#94a3b8; margin-bottom:3px; padding-left:108px;">{description}</div>"""

                html += f"""
                    <div style="display:flex; align-items:center; gap:6px; padding-left:108px;">
                        <span style="font-size:0.85em; padding:1px 7px; border-radius:10px; background:{bar_color}18; color:{bar_color}; font-weight:600;">{calendar_nm}</span>
                        <span style="font-size:0.88em; color:#94a3b8;">{owner_name}</span>
                    </div>
                </div>
"""

            html += """
            </div>
        </details>
"""

        html += """
    </div>
</div>
"""

        # LLM이 후속 질문에 답변할 수 있도록 텍스트 요약 생성
        text_lines = []
        for s in schedules:
            title = s.get('title', '-')
            start = s.get('start_date', '-')
            end = s.get('end_date', '-')
            cal = s.get('calendar_nm', '-')
            owner = s.get('owner_name', '-')
            desc = s.get('description', '') or ''
            text_lines.append(f"- {title} | {start}~{end} | {cal} | {owner}" + (f" | {desc}" if desc else ""))

        return {
            "status": "success",
            "html_content": html,
            "text_summary": "\n".join(text_lines),
        }

    except Exception as e:
        import traceback
        error_msg = f"표 생성 중 오류:\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        return {"status": "error", "message": error_msg}


# ============================================================================
# 회의실 - 달력 형식
# ============================================================================
def format_meeting_rooms_as_calendar(meeting_data, user_name="사용자", meetingroom_name=None, start_dt=None, end_dt=None, _auth=None):
    """
    회의실 예약 목록을 달력 형식으로 변환합니다.

    Args:
        meeting_data: 회의실 예약 목록
        user_name: 사용자 이름
        meetingroom_name: 회의실 이름
        start_dt: 조회 시작 날짜
        end_dt: 조회 종료 날짜

    Returns:
        str: 파일 저장 안내 메시지
    """
    log_debug(f"[DEBUG] ===== format_meeting_rooms_as_calendar 함수 진입 =====")
    log_debug(f"[DEBUG] 받은 파라미터: meeting_data={type(meeting_data)}, user_name={user_name}, meetingroom_name={meetingroom_name}, start_dt={start_dt}, end_dt={end_dt}")
    try:
        log_debug(f"[DEBUG] format_meeting_rooms_as_calendar 호출됨")
        log_debug(f"[DEBUG] meeting_data 타입: {type(meeting_data)}")
        log_debug(f"[DEBUG] meeting_data 내용 (처음 200자): {str(meeting_data)[:200]}")
        log_debug(f"[DEBUG] user_name: {user_name}, meetingroom_name: {meetingroom_name}, start_dt: {start_dt}, end_dt: {end_dt}")

        if not CALENDAR_AVAILABLE:
            return "❌ 달력 형식을 사용할 수 없습니다. calendar_html.py 모듈이 필요합니다."

        # meeting_data에서 회의실명 우선 추출 (LLM이 meetingroom_name을 잘못 넘기는 경우 방지)
        if isinstance(meeting_data, dict):
            data_room_name = (
                (meeting_data.get('room_info') or {}).get('meetingroom')
                or (meeting_data.get('query') or {}).get('meetingroom')
                or meeting_data.get('meetingroom')
            )
            if data_room_name:
                meetingroom_name = data_room_name

        # 데이터 구조 정규화
        reservations, room_name = _extract_meeting_reservations(meeting_data, meetingroom_name)

        if not reservations:
            return {
                "status": "success",
                "message": f"{room_name}의 예약이 없습니다."
            }

        # 날짜 형식 확인 및 기본값 설정
        if not start_dt or not end_dt:
            dates = [r.get('start_date', '')[:10] for r in reservations if r.get('start_date')]
            if dates:
                start_dt = min(dates)
                end_dt = max(dates)
            else:
                today = datetime.now().strftime("%Y.%m.%d")
                start_dt = end_dt = today

        # render_graphic_calendar 호출 (회의실 예약도 동일 구조)
        title = f"{room_name} 예약 현황"
        html_content = render_graphic_calendar(reservations, title, start_dt, end_dt)

        return {
            "status": "success",
            "html_content": html_content
        }

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_msg = f"❌ HTML 생성 실패!\n📋 에러: {str(e)}\n📜 스택:\n{error_details}"
        log_debug(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }


# ============================================================================
# 회의실 - 표 형식
# ============================================================================
def format_meeting_rooms_as_table(meeting_data, user_name="사용자", meetingroom_name=None, start_dt=None, end_dt=None, _auth=None):
    """
    회의실 예약 목록을 카드 리스트 형식으로 변환합니다.
    - 단일 회의실: 날짜별 그룹핑, <details open> (열린 상태)
    - 다중 회의실 (get_all_meeting_rooms): 회의실별 <details> (닫힌 상태), 내부 날짜별 그룹핑

    Args:
        meeting_data: 단일 회의실(room_info) 또는 다중 회의실(rooms 배열) 결과
        user_name: 사용자 이름
        meetingroom_name: 회의실 이름
        start_dt: 조회 시작 날짜
        end_dt: 조회 종료 날짜

    Returns:
        dict: HTML 결과
    """
    log_debug(f"[DEBUG] ===== format_meeting_rooms_as_table 함수 진입 =====")
    try:
        WEEKDAYS_KR = ['월', '화', '수', '목', '금', '토', '일']
        _PALETTE = [
            '#6366F1', '#10B981', '#F59E0B', '#EF4444', '#3B82F6',
            '#EC4899', '#8B5CF6', '#14B8A6', '#F97316', '#06B6D4',
            '#84CC16', '#E11D48', '#7C3AED', '#0EA5E9', '#D946EF',
            '#F43F5E', '#22D3EE', '#A3E635', '#FB923C', '#818CF8',
        ]

        def _room_color(name):
            return _PALETTE[hash(name) % len(_PALETTE)]

        # ============================================================
        # 데이터 구조 판별: 다중 회의실 vs 단일 회의실
        # ============================================================
        multi_room = False
        rooms_list = []  # [{meetingroom, capacity, reservations, ...}, ...]

        if isinstance(meeting_data, dict) and 'rooms' in meeting_data:
            # get_all_meeting_rooms() 결과
            multi_room = True
            rooms_list = meeting_data['rooms']
            query = meeting_data.get('query', {})
            if query:
                start_dt = start_dt or query.get('start_dt', '')[:10].replace('-', '.')
                end_dt = end_dt or query.get('end_dt', '')[:10].replace('-', '.')
        else:
            # 단일 회의실 — 기존 로직
            reservations, room_name = _extract_meeting_reservations(meeting_data, meetingroom_name)
            if not reservations:
                return {"status": "success", "message": f"{room_name}의 예약이 없습니다."}
            rooms_list = [{"meetingroom": room_name, "reservations": reservations}]

        if not rooms_list:
            return {"status": "success", "message": "조회된 회의실이 없습니다."}

        # 날짜 자동 추출
        all_reservations = []
        for rm_data in rooms_list:
            all_reservations.extend(rm_data.get('reservations', []))

        if not start_dt or not end_dt:
            dates = [r.get('start_date', '')[:10] for r in all_reservations if r.get('start_date')]
            if dates:
                start_dt = start_dt or min(dates)
                end_dt = end_dt or max(dates)

        date_range = f"{start_dt or '오늘'} ~ {end_dt or '오늘'}"
        total_count = len(all_reservations)

        if total_count == 0 and multi_room:
            return {"status": "success", "message": f"전체 회의실에 해당 기간 예약이 없습니다. ({date_range})"}

        # ============================================================
        # 헤더
        # ============================================================
        header_title = "전체 회의실 예약 현황" if multi_room else f"{rooms_list[0]['meetingroom']} 예약 현황"

        html = f"""
<style>
summary::-webkit-details-marker {{ display:none; }}
summary::marker {{ display:none; }}
</style>
<div style="font-family:'Pretendard','Malgun Gothic',-apple-system,sans-serif; max-width:100%; border-radius:14px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.08); background:#fff;">
    <div style="display:flex;align-items:center;gap:12px;padding:12px 18px;background:linear-gradient(135deg,#475569,#64748B);">
        <span style="font-size:1.05em;font-weight:700;color:#fff;">{header_title}</span>
        <span style="color:rgba(255,255,255,0.6);">|</span>
        <span style="font-size:0.95em;color:rgba(255,255,255,0.85);">{date_range}</span>
        <span style="color:rgba(255,255,255,0.6);">|</span>
        <span style="font-size:0.95em;color:rgba(255,255,255,0.85);">총 {total_count}건</span>
    </div>
    <div style="padding:6px 0;">
"""

        # ============================================================
        # 회의실별 렌더링
        # ============================================================
        for rm_idx, rm_data in enumerate(rooms_list):
            rm_name = rm_data.get('meetingroom', f'회의실 {rm_idx+1}')
            rm_reservations = rm_data.get('reservations', [])
            rm_count = len(rm_reservations)
            rm_color = _room_color(rm_name)
            rm_capacity = rm_data.get('capacity', '')
            capacity_str = f" · {rm_capacity}명" if rm_capacity else ""

            # 단일이면 open, 다중이면 closed (예약 있는 첫번째만 open)
            if not multi_room:
                details_attr = "open"
            else:
                details_attr = ""  # 닫힌 상태

            # 회의실 헤더 (다중일 때만 details로 감싸기)
            if multi_room:
                html += f"""
        <details {details_attr} style="margin-bottom:2px;">
            <summary style="cursor:pointer; list-style:none; display:flex; align-items:center; padding:10px 18px 8px; gap:10px; border-bottom:1px solid #f1f5f9;">
                <span style="width:10px;height:10px;border-radius:50%;background:{rm_color};display:inline-block;flex-shrink:0;"></span>
                <span style="font-size:1.05em; font-weight:700; color:#1e293b;">{rm_name}</span>
                <span style="font-size:0.85em; color:#94a3b8;">{capacity_str}</span>
                <span style="flex:1; height:1px; background:#e2e8f0;"></span>
                <span style="font-size:0.88em; color:{rm_color}; font-weight:700; background:{rm_color}12; padding:2px 10px; border-radius:12px;">{rm_count}건</span>
            </summary>
"""

            if rm_count == 0:
                html += f"""
            <div style="padding:12px 24px; color:#94a3b8; font-size:0.95em;">예약이 없습니다.</div>
"""
                if multi_room:
                    html += """        </details>
"""
                continue

            # 날짜별 그룹핑
            grouped = defaultdict(list)
            for r in rm_reservations:
                date_key = r.get('start_date', '')[:10]
                if date_key:
                    grouped[date_key].append(r)

            for date_key in sorted(grouped.keys()):
                items = grouped[date_key]
                try:
                    dt = datetime.strptime(date_key, "%Y.%m.%d")
                    date_label = f"{dt.month}월 {dt.day}일 ({WEEKDAYS_KR[dt.weekday()]})"
                except:
                    date_label = date_key

                html += f"""
            <details open style="margin-bottom:4px;">
                <summary style="cursor:pointer; list-style:none; display:flex; align-items:center; padding:8px 20px 4px; gap:8px;">
                    <span style="font-size:1.0em; font-weight:600; color:#475569;">{date_label}</span>
                    <span style="flex:1; height:1px; background:#e2e8f0;"></span>
                    <span style="font-size:0.82em; color:#94a3b8; font-weight:600;">{len(items)}건</span>
                </summary>
                <div style="display:flex; flex-wrap:wrap; gap:8px; padding:0 14px 6px;">
"""

                for item in items:
                    title = item.get('title', '제목 없음')
                    start_date = item.get('start_date', '')
                    end_date = item.get('end_date', '')
                    description = item.get('description', '') or ''
                    meetingroom = item.get('meetingroom', rm_name)
                    owner_name = item.get('owner_name', '-')
                    bar_color = _room_color(meetingroom)

                    s_time = start_date[11:16] if len(start_date) > 15 else ''
                    e_time = end_date[11:16] if len(end_date) > 15 else ''
                    time_str = f"{s_time} - {e_time}" if s_time and e_time else (s_time or '-')

                    html += f"""
                    <div style="flex:1 1 calc(50% - 8px); min-width:280px; padding:10px 14px; border-left:4px solid {bar_color}; border-radius:0 8px 8px 0; background:#fff; box-sizing:border-box;">
                        <div style="display:flex; align-items:center; gap:8px; margin-bottom:3px;">
                            <span style="font-size:1.0em; font-weight:600; color:#64748b; min-width:100px;">{time_str}</span>
                            <span style="font-size:1.12em; font-weight:700; color:#1e293b;">{title}</span>
                        </div>"""

                    if description:
                        html += f"""
                        <div style="font-size:1.0em; color:#94a3b8; margin-bottom:3px; padding-left:108px;">{description}</div>"""

                    html += f"""
                        <div style="display:flex; align-items:center; gap:6px; padding-left:108px;">
                            <span style="font-size:0.85em; padding:1px 7px; border-radius:10px; background:{bar_color}18; color:{bar_color}; font-weight:600;">{meetingroom}</span>
                            <span style="font-size:0.88em; color:#94a3b8;">{owner_name}</span>
                        </div>
                    </div>
"""

                html += """
                </div>
            </details>
"""

            if multi_room:
                html += """        </details>
"""

        html += """
    </div>
</div>
"""

        # 텍스트 요약
        text_lines = []
        for rm_data in rooms_list:
            rm_name = rm_data.get('meetingroom', '회의실')
            for r in rm_data.get('reservations', []):
                title = r.get('title', '-')
                start = r.get('start_date', '-')
                end = r.get('end_date', '-')
                owner = r.get('owner_name', '-')
                desc = r.get('description', '') or ''
                text_lines.append(f"- [{rm_name}] {title} | {start}~{end} | {owner}" + (f" | {desc}" if desc else ""))

        return {
            "status": "success",
            "html_content": html,
            "text_summary": "\n".join(text_lines),
        }

    except Exception as e:
        import traceback
        error_msg = f"표 생성 중 오류:\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        return {"status": "error", "message": error_msg}


# ============================================================
# 범용 HTML 테이블 생성 도구
# ============================================================

# 자동 라벨 매핑 (영문 키 → 한글)
_AUTO_LABELS = {
    "name": "이름", "empname": "이름", "NAME": "이름",
    "position": "직책", "POS_NAME": "직위", "posn_nm": "직위",
    "dept": "부서", "department": "부서", "team": "팀",
    "email": "이메일", "eml": "이메일",
    "phone": "전화번호", "mobile": "휴대폰", "ext": "내선", "fax": "FAX",
    "duty": "담당업무", "location": "근무지",
    "title": "제목", "subject": "제목",
    "date": "날짜", "start_date": "시작일", "end_date": "종료일",
    "start_dt": "시작일시", "end_dt": "종료일시",
    "start_time": "시작시간", "end_time": "종료시간",
    "STA_YMD": "날짜", "MEMO": "일정 내용",
    "status": "상태", "description": "설명",
    "empno": "사번", "emp_code": "사번",
    "calendar_nm": "달력", "owner_name": "등록자",
    "meetingroom": "회의실", "doc_id": "문서번호",
    "form_name": "양식명", "category": "분류", "form_id": "양식번호",
    "count": "건수", "total": "합계", "amount": "금액",
    "num": "번호", "recipient": "수신자", "purpose": "목적",
    "document_type": "문서유형", "comment": "의견", "reason": "사유",
}


def _fmt_cell(key: str, value) -> str:
    """셀 값 포맷: ISO datetime 변환, None/빈값 처리"""
    if value is None or value == "":
        return "-"
    s = str(value)
    # ISO datetime 패턴 (2026-03-05T09:00:00) → 2026-03-05 09:00
    if re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", s):
        try:
            dt = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
    return s


def format_data_as_table(title: str, data: list = None, columns: list = None, column_labels: dict = None, _auth=None) -> dict:
    """구조화된 데이터를 깔끔한 HTML 테이블로 변환합니다.

    Args:
        title: 테이블 상단 제목 (예: "임원 일정 현황", "결재 대기 목록")
        data: dict 리스트 (예: [{"이름": "김철수", "직위": "사장", ...}, ...])
        columns: 표시할 컬럼 키 목록 (순서대로). 생략 시 data[0]의 키를 자동 사용.
        column_labels: 컬럼 키 → 한글 라벨 매핑. 생략 시 자동 매핑.

    Returns:
        dict: {"status": "success", "html_content": str, "text_summary": str}
    """
    try:
        if not data or not isinstance(data, list):
            return {"status": "error", "message": "data가 비어있거나 리스트가 아닙니다."}

        rows = [row for row in data if isinstance(row, dict)]
        if not rows:
            return {"status": "error", "message": "data에 유효한 dict 항목이 없습니다."}

        # 컬럼 결정: 모든 행의 키를 합집합 (첫 행 순서 유지)
        if not columns:
            seen = set()
            columns = []
            for row in rows:
                for k in row.keys():
                    if k not in seen:
                        seen.add(k)
                        columns.append(k)

        # 라벨 결정
        labels = dict(column_labels) if column_labels else {}
        for col in columns:
            if col not in labels:
                labels[col] = _AUTO_LABELS.get(col, col)

        row_count = len(rows)
        display_title = title or "조회 결과"

        # ── HTML 생성 ──
        html = f"""
<div style="font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic',-apple-system,sans-serif;
            max-width:100%; border-radius:14px; overflow:hidden;
            box-shadow:0 4px 20px rgba(0,0,0,0.08); background:#fff; margin:8px 0;">
  <div style="background:linear-gradient(135deg,#1e293b 0%,#334155 100%);
              color:#fff; padding:12px 18px;">
    <span style="font-size:1.1em; font-weight:700;">{display_title}</span>
    <span style="font-size:0.85em; color:#94a3b8; margin-left:10px;">총 {row_count}건</span>
  </div>
  <div style="overflow-x:auto; max-height:500px; overflow-y:auto;">
    <table style="width:100%; border-collapse:collapse;">
      <thead>
        <tr>"""

        for col in columns:
            label = labels.get(col, col)
            html += f"""
          <th style="position:sticky; top:0; z-index:1;
                     background:#f1f5f9; color:#475569; font-weight:600; font-size:0.9em;
                     padding:10px 14px; text-align:left; border-bottom:2px solid #e2e8f0;
                     white-space:nowrap;">{label}</th>"""

        html += """
        </tr>
      </thead>
      <tbody>"""

        for i, row in enumerate(rows):
            bg = "#f8fafc" if i % 2 == 1 else "#fff"
            html += f"""
        <tr style="background:{bg};" onmouseover="this.style.background='#eef2ff'" onmouseout="this.style.background='{bg}'">"""
            for col in columns:
                val = _fmt_cell(col, row.get(col))
                html += f"""
          <td style="padding:10px 14px; color:#334155; font-size:0.95em;
                     border-bottom:1px solid #f1f5f9;">{val}</td>"""
            html += """
        </tr>"""

        html += """
      </tbody>
    </table>
  </div>
</div>
"""

        # ── 텍스트 요약 (LLM 참조용, 최대 50행) ──
        text_lines = []
        display_cols = columns[:5]  # 텍스트 요약은 5열까지
        for row in rows[:50]:
            parts = [f"{labels.get(c, c)}: {_fmt_cell(c, row.get(c))}" for c in display_cols]
            text_lines.append("- " + " | ".join(parts))
        if len(rows) > 50:
            text_lines.append(f"... 외 {len(rows) - 50}건")

        return {
            "status": "success",
            "html_content": html,
            "text_summary": "\n".join(text_lines),
        }

    except Exception as e:
        import traceback
        error_msg = f"범용 테이블 생성 중 오류:\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        return {"status": "error", "message": error_msg}
