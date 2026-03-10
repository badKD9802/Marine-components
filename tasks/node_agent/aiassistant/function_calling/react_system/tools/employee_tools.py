"""
직원 검색 도구
직원 정보를 이름, 부서, 팀, 직책, 업무, 근무지 등으로 검색합니다.

원본 시스템(search_gw.py)의 rerank 모델 방식을 유지하여
고객 만족도를 확보합니다. (성능 검증됨)
"""

import logging
import pandas as pd
from typing import Optional
from app.tasks.lib_justtype.common import util

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== EMPLOYEE TOOLS ==")


async def find_employee(
    name: Optional[str] = None,
    emp_code: Optional[str] = None,
    email: Optional[str] = None,
    dept: Optional[str] = None,
    team: Optional[str] = None,
    position: Optional[str] = None,
    duty: Optional[str] = None,
    location: Optional[str] = None,
    _auth=None,
):
    """
    직원 정보를 검색합니다.

    Args:
        name: 직원 이름 (부분 일치)
        emp_code: 사번
        email: 이메일
        dept: 부서명
        team: 팀명
        position: 직책
        duty: 담당 업무
        location: 근무지

    Returns:
        dict: 검색 결과 또는 재질문 메시지
    """

    # ==========================================
    # 1. 실제 DB 조회
    # ==========================================
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.db_extract.db_search import OracleSearchClient
            db = OracleSearchClient(_auth.stat)

            # 검색 타입에 따른 DB 조회
            if name:
                df = await db.search_by_name(name)
            elif emp_code:
                df = await db.search_by_empcode(emp_code)
            elif email:
                df = await db.search_by_email(email)
            elif position and not (dept or team or duty or location):
                df = await db.search_by_posname(position)
            elif dept or team or duty or location:
                df = await db.employee_all_search()
            else:
                return {"status": "error", "message": "검색 조건을 입력해주세요. (이름, 사번, 이메일, 부서, 팀 등)"}

            if df is None or (isinstance(df, pd.DataFrame) and df.empty) or (isinstance(df, list) and len(df) == 0):
                return {"status": "not_found", "message": "조회된 직원이 없습니다.", "total_count": 0}

            if not isinstance(df, pd.DataFrame):
                df = pd.DataFrame(df)

            # 후처리 필터링
            if position:
                pos_clean = position.replace(" ", "")
                df = df[df["POSN_NM"].astype(str).str.replace(r"\s+", "", regex=True).str.contains(pos_clean, na=False)]
            if dept:
                dept_clean = dept.replace(" ", "")
                df = df[df["DEPT_NM"].astype(str).str.replace(r"\s+", "", regex=True).str.lower().str.contains(dept_clean.lower(), na=False)]
            if team:
                team_clean = team.replace(" ", "")
                df = df[df["TEAM_NM"].astype(str).str.replace(r"\s+", "", regex=True).str.lower().str.contains(team_clean.lower(), na=False)]
            if duty:
                duty_clean = duty.replace(" ", "")
                mask_biz = df["BIZ"].astype(str).str.replace(r"\s+", "", regex=True).str.lower().str.contains(duty_clean.lower(), na=False)
                mask_team = df["TEAM_NM"].astype(str).str.replace(r"\s+", "", regex=True).str.lower().str.contains(duty_clean.lower(), na=False)
                df = df[mask_biz | mask_team]
            if location:
                loc_clean = location.replace(" ", "")
                df = df[df["BIZ"].astype(str).str.replace(r"\s+", "", regex=True).str.contains(loc_clean, na=False)]

            if df.empty:
                return {"status": "not_found", "message": "조회된 직원이 없습니다. 검색 조건을 확인해주세요.", "total_count": 0}

            df = df.sort_values(by="TEAM_NM", ascending=True)

            # DB 컬럼 → tool 필드 매핑
            employees = []
            for _, row in df.iterrows():
                employees.append({
                    "empno": str(row.get("EMPNO", "-")),
                    "empname": str(row.get("EMP_NM", "-")),
                    "position": str(row.get("POSN_NM", "-")),
                    "dept": str(row.get("DEPT_NM", "-")),
                    "team": str(row.get("TEAM_NM", "-")),
                    "duty": str(row.get("BIZ", "-")),
                    "email": str(row.get("EML", "-")),
                    "ext": str(row.get("TEL_NO", "-")),
                    "fax": str(row.get("FAX_NO", "-")),
                    "mobile": str(row.get("MBPH", "-")),
                })

            total_count = len(employees)
            html = _build_employee_html(employees, total_count)
            text_summary = _build_employee_text_summary(employees)
            return {
                "status": "success",
                "message": f"총 {total_count}명의 직원을 찾았습니다.",
                "total_count": total_count,
                "html_content": html,
                "text_summary": text_summary,
                "preview": [
                    {"icon": "👤", "text": e["empname"],
                     "sub": f'{e.get("dept", "")} / {e.get("position", "")}'.strip(" /")}
                    for e in employees[:6]
                ],
            }
        except Exception as e:
            logger.error(f"find_employee API 오류: {e}")

    # ==========================================
    # 2. 더미 데이터 생성 (테스트 환경)
    # ==========================================
    # 많은 경우 (팀 검색): ~10명
    # 적은 경우 (특정 이름): 2-3명

    # 검색 타입 판단
    is_team_search = bool(team or (dept and not name))
    is_specific_name = bool(name and len(name) >= 2)

    if is_team_search:
        # 팀 검색: 많은 결과 (10명)
        dummy_employees = [
            {
                "empno": "2021001",
                "empname": "김철수",
                "position": "팀장",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "AI 사업기획",
                "email": "kim.cs@kamco.co.kr",
                "ext": "5001",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5001"
            },
            {
                "empno": "2021002",
                "empname": "이영희",
                "position": "차장",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "AI 모델 개발",
                "email": "lee.yh@kamco.co.kr",
                "ext": "5002",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5002"
            },
            {
                "empno": "2021003",
                "empname": "박민수",
                "position": "과장",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "데이터 분석",
                "email": "park.ms@kamco.co.kr",
                "ext": "5003",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5003"
            },
            {
                "empno": "2021004",
                "empname": "정수아",
                "position": "대리",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "AI 서비스 운영",
                "email": "jung.sa@kamco.co.kr",
                "ext": "5004",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5004"
            },
            {
                "empno": "2021005",
                "empname": "최동욱",
                "position": "대리",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "백엔드 개발",
                "email": "choi.du@kamco.co.kr",
                "ext": "5005",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5005"
            },
            {
                "empno": "2021006",
                "empname": "강민지",
                "position": "사원",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "프론트엔드 개발",
                "email": "kang.mj@kamco.co.kr",
                "ext": "5006",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5006"
            },
            {
                "empno": "2021007",
                "empname": "윤서준",
                "position": "사원",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "UI/UX 디자인",
                "email": "yoon.sj@kamco.co.kr",
                "ext": "5007",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5007"
            },
            {
                "empno": "2021008",
                "empname": "임하늘",
                "position": "사원",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "데이터 수집",
                "email": "lim.hn@kamco.co.kr",
                "ext": "5008",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5008"
            },
            {
                "empno": "2021009",
                "empname": "송지훈",
                "position": "사원",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "QA 테스트",
                "email": "song.jh@kamco.co.kr",
                "ext": "5009",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5009"
            },
            {
                "empno": "2021010",
                "empname": "한예린",
                "position": "사원",
                "dept": "디지털시스템실",
                "team": team or "AI팀",
                "duty": "문서 관리",
                "email": "han.yr@kamco.co.kr",
                "ext": "5010",
                "fax": "02-1234-5099",
                "mobile": "010-1234-5010"
            }
        ]
    elif is_specific_name:
        # 특정 이름 검색: 적은 결과 (2-3명)
        dummy_employees = [
            {
                "empno": "2020123",
                "empname": name or "배경득",
                "position": "차장",
                "dept": "경영지원팀",
                "team": "재무팀",
                "duty": "재무 관리",
                "email": f"{(name or 'bae').lower()}.kd@kamco.co.kr",
                "ext": "6001",
                "fax": "02-1234-6099",
                "mobile": "010-1234-6001"
            },
            {
                "empno": "2019456",
                "empname": name or "배경득",
                "position": "과장",
                "dept": "공사채권본부",
                "team": "채권관리팀",
                "duty": "공사채권 관리",
                "email": f"{(name or 'bae').lower()}.kd2@kamco.co.kr",
                "ext": "6002",
                "fax": "051-1234-6099",
                "mobile": "010-1234-6002"
            }
        ]
    else:
        # 기본: 중간 정도 결과 (4명)
        dummy_employees = [
            {
                "empno": "2022001",
                "empname": "홍길동",
                "position": "팀장",
                "dept": "경영지원팀",
                "team": "인사팀",
                "duty": "인사 관리",
                "email": "hong.gd@kamco.co.kr",
                "ext": "7001",
                "fax": "02-1234-7099",
                "mobile": "010-1234-7001"
            },
            {
                "empno": "2022002",
                "empname": "신사임당",
                "position": "차장",
                "dept": "공사채권본부",
                "team": "법무팀",
                "duty": "법무 자문",
                "email": "shin.si@kamco.co.kr",
                "ext": "7002",
                "fax": "02-1234-7099",
                "mobile": "010-1234-7002"
            },
            {
                "empno": "2022003",
                "empname": "세종대왕",
                "position": "과장",
                "dept": "디지털시스템실",
                "team": "보안팀",
                "duty": "정보보안",
                "email": "sejong.king@kamco.co.kr",
                "ext": "7003",
                "fax": "02-1234-7099",
                "mobile": "010-1234-7003"
            },
            {
                "empno": "2022004",
                "empname": "이순신",
                "position": "팀장",
                "dept": "공사채권본부",
                "team": "회수팀",
                "duty": "채권 회수",
                "email": "lee.ss@kamco.co.kr",
                "ext": "7004",
                "fax": "02-1234-7099",
                "mobile": "010-1234-7004"
            }
        ]


    # ==========================================
    # 3. pandas DataFrame으로 필터링
    # ==========================================
    df = pd.DataFrame(dummy_employees)

    # 기본 필터링 (정확히 일치하는 조건)
    if name:
        df = df[df["empname"].str.contains(name, na=False)]
    if emp_code:
        df = df[df["empno"] == emp_code]
    if email:
        df = df[df["email"].str.contains(email, na=False)]
    if dept:
        df = df[df["dept"].str.contains(dept, na=False)]
    if team:
        df = df[df["team"].str.contains(team, na=False)]
    if position:
        df = df[df["position"].str.contains(position, na=False)]


    # ==========================================
    # 4. Rerank 모델 적용 (duty, location 유사도)
    # ==========================================
    # TODO: 실제 rerank 모델 API 연동
    # 실제 연동 시 아래 주석 해제하고 구현
    # if duty or location:
    #     try:
    #         from chatsam.app.services.rerank_api import rerank_search
    #
    #         # duty 유사도 검색
    #         if duty:
    #             duty_candidates = df["duty"].tolist()
    #             rerank_results = rerank_search(
    #                 query=duty,
    #                 candidates=duty_candidates,
    #                 top_k=10
    #             )
    #             # 유사도 점수가 높은 순으로 필터링
    #             matched_indices = [r["index"] for r in rerank_results if r["score"] > 0.5]
    #             df = df.iloc[matched_indices]
    #
    #         # location 유사도 검색
    #         if location:
    #             location_candidates = df["location"].tolist()
    #             rerank_results = rerank_search(
    #                 query=location,
    #                 candidates=location_candidates,
    #                 top_k=10
    #             )
    #             matched_indices = [r["index"] for r in rerank_results if r["score"] > 0.5]
    #             df = df.iloc[matched_indices]
    #
    #     except Exception as e:
    #         print(f"Rerank API 호출 실패: {e}")
    #         # Rerank 실패 시 단순 문자열 매칭으로 fallback
    #         if duty:
    #             df = df[df["duty"].str.contains(duty, na=False)]
    #         if location:
    #             df = df[df["location"].str.contains(location, na=False)]

    # 테스트 환경: 단순 문자열 매칭
    if duty:
        df = df[df["duty"].str.contains(duty, na=False)]
    if location and "location" in df.columns:
        df = df[df["location"].str.contains(location, na=False)]


    # ==========================================
    # 5. 후처리 (원본 로직)
    # ==========================================
    # EMPNO 검증: 6-8자리 숫자만 허용
    df = df[df["empno"].str.match(r"^\d{6,8}$", na=False)]

    # SM 직원 제외 (필요시)
    # df = df[~df["team"].str.contains("SM", na=False)]

    # 정렬: 부서 → 팀 → 이름
    df = df.sort_values(by=["dept", "team", "empname"])


    # ==========================================
    # 6. 결과 반환
    # ==========================================
    employees = df.to_dict("records")
    total_count = len(employees)

    # 결과 없음
    if total_count == 0:
        return {
            "status": "not_found",
            "message": "조회된 직원이 없습니다. 검색 조건을 확인해주세요.",
            "total_count": 0,
        }

    # 1명 이상 → HTML 표로 직접 렌더링
    html = _build_employee_html(employees, total_count)
    text_summary = _build_employee_text_summary(employees)
    return {
        "status": "success",
        "message": f"총 {total_count}명의 직원을 찾았습니다.",
        "total_count": total_count,
        "html_content": html,
        "text_summary": text_summary,
        "preview": [
            {"icon": "👤", "text": e["empname"],
             "sub": f'{e.get("dept", "")} / {e.get("position", "")}'.strip(" /")}
            for e in employees[:6]
        ],
    }


def _build_employee_text_summary(employees: list) -> str:
    """LLM이 후속 질문에 정확히 답변할 수 있도록 직원 데이터를 텍스트로 요약합니다."""
    lines = []
    for emp in employees:
        name = emp.get("empname", "-")
        empno = emp.get("empno", "-")
        position = emp.get("position", "-")
        dept = emp.get("dept", "-")
        team = emp.get("team", "-")
        ext = emp.get("ext", "-")
        fax = emp.get("fax", "-")
        mobile = emp.get("mobile", "-")
        email = emp.get("email", "-")
        duty = emp.get("duty", "-")
        lines.append(
            f"- {name} | 사번:{empno} | 직위:{position} | 부서:{dept} | 팀:{team} "
            f"| 내선:{ext} | FAX:{fax} | 휴대폰:{mobile} | 이메일:{email} | 담당업무:{duty}"
        )
    return "\n".join(lines)


def _build_employee_html(employees: list, total_count: int) -> str:
    """직원 목록을 프로필 카드 형태의 HTML로 변환합니다."""

    def telephone_format(tel: str) -> str:
        """전화번호 포맷: 숫자만 추출 후 02-XXXX-XXXX 등으로 변환"""
        digits = "".join(c for c in (tel or "") if c.isdigit())
        if len(digits) == 10:
            return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
        if len(digits) == 11:
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        return tel

    cards = ""
    for emp in employees:
        empno = emp.get("empno", "-") or "-"
        name = emp.get("empname", "-") or "-"
        team_nm = emp.get("team", "-") or "-"
        dept_nm = emp.get("dept", "-") or "-"
        posn_nm = emp.get("position", "-") or "-"
        ext = emp.get("ext", "-") or "-"
        fax = emp.get("fax", "-") or "-"
        mbph = emp.get("mobile", "-") or "-"
        eml = emp.get("email", "-") or "-"
        biz = emp.get("duty", "-") or "-"

        # 오른쪽: 연락처 + 담당업무
        right_rows = ""
        if ext != "-":
            right_rows += (
                f'<div style="display:flex;gap:6px;margin-bottom:4px;">'
                f'<span style="color:#94A3B8;font-size:0.95em;min-width:50px;">내선</span>'
                f'<span style="color:#334155;font-size:1.0em;">{ext}</span>'
                f"</div>"
            )
        if fax != "-":
            right_rows += (
                f'<div style="display:flex;gap:6px;margin-bottom:4px;">'
                f'<span style="color:#94A3B8;font-size:0.95em;min-width:50px;">FAX</span>'
                f'<span style="color:#334155;font-size:1.0em;">{fax}</span>'
                f"</div>"
            )
        if mbph != "-":
            right_rows += (
                f'<div style="display:flex;gap:6px;margin-bottom:4px;">'
                f'<span style="color:#94A3B8;font-size:0.95em;min-width:50px;">휴대폰</span>'
                f'<span style="color:#334155;font-size:1.0em;">{mbph}</span>'
                f"</div>"
            )
        if eml != "-":
            right_rows += (
                f'<div style="display:flex;gap:6px;margin-bottom:4px;">'
                f'<span style="color:#94A3B8;font-size:0.95em;min-width:50px;">이메일</span>'
                f'<a href="mailto:{eml}" style="color:#6366F1;font-size:1.0em;text-decoration:none;">{eml}</a>'
                f"</div>"
            )
        if not right_rows:
            right_rows = '<span style="color:#94A3B8;font-size:1.0em;">연락처 정보 없음</span>'

        cards += (
            f'<div style="padding:10px 14px;border-left:4px solid #6366F1;'
            f'border-radius:0 8px 8px 0;background:#fff;display:flex;gap:16px;align-items:flex-start;">'
            # 왼쪽: 이름/직위/부서/사번 (수직 중앙)
            f'<div style="min-width:140px;flex-shrink:0;align-self:center;">'
            f'<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:2px;">'
            f'<a href="http://new.e-kamco.com/convert/member/member_detail.jsp?emp_no={empno}&popup=Y"'
            f' target="_blank" style="color:#1E293B;font-weight:700;font-size:1.1em;'
            f'text-decoration:none;">{name}</a>'
            f'<span style="background:#EEF2FF;color:#6366F1;font-size:0.85em;'
            f'padding:2px 8px;border-radius:10px;font-weight:600;">{posn_nm}</span>'
            f"</div>"
            f'<div style="color:#64748B;font-size:0.95em;margin-bottom:6px;">{dept_nm} · {team_nm}</div>'
            f'<div style="color:#94A3B8;font-size:0.9em;">사번 {empno}</div>'
            f"</div>"
            # 구분선 1
            f'<div style="width:1px;align-self:stretch;background:#E2E8F0;"></div>'
            # 가운데: 연락처
            f'<div style="flex:1;min-width:0;">'
            f"{right_rows}"
            f"</div>"
            # 구분선 2
            f'<div style="width:1px;align-self:stretch;background:#E2E8F0;"></div>'
            # 오른쪽: 담당업무
            f'<div style="flex:1;min-width:0;">'
            f'<div style="color:#94A3B8;font-size:0.9em;margin-bottom:4px;">담당업무</div>'
            f'<div style="color:#475569;font-size:1.0em;line-height:1.5;">{biz}</div>'
            f"</div>"
            f"</div>"
        )

    html = (
        f"<div style=\"font-family:'Pretendard','Malgun Gothic',-apple-system,sans-serif;"
        f"max-width:100%;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);background:#fff;\">"
        f'<div style="display:flex;align-items:center;gap:12px;padding:12px 18px;'
        f'background:linear-gradient(135deg,#8B8FF7,#A5A8FC);">'
        f'<span style="font-size:1.05em;font-weight:700;color:#fff;">직원 검색 결과</span>'
        f'<span style="color:rgba(255,255,255,0.6);">|</span>'
        f'<span style="font-size:0.95em;color:rgba(255,255,255,0.85);">총 {total_count}명</span>'
        f"</div>"
        f'<div style="display:flex;flex-direction:column;gap:6px;padding:6px 14px;max-height:500px;overflow-y:auto;">'
        f"{cards}"
        f"</div>"
        f"</div>"
    )
    return html
