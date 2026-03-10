"""
전자결재 관리 도구
전자결재 양식 조회, 결재 목록 확인, 승인/반려 처리합니다.

주요 기능:
- get_approval_form: 결재 양식 조회
- get_my_approvals: 내 결재함 (대기 중인 결재)
- approve_document: 결재 승인
- reject_document: 결재 반려
"""

import logging
from datetime import datetime, timedelta
from app.tasks.lib_justtype.common import util

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== APPROVAL TOOLS ==")


async def get_approval_form(form_name, department=None, _auth=None):
    """
    전자결재 양식을 조회합니다.

    Args:
        form_name: 양식 이름 (예: 지출결의서, 휴가신청서)
        department: 부서별 양식 (선택)

    Returns:
        dict: 결재양식 정보
    """

    # ==========================================
    # 1. 실제 DB 조회 + 양식 URL 생성
    # ==========================================
    if _auth and _auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.db_extract.db_search import OracleSearchClient

            db = OracleSearchClient(_auth.stat)
            document_list = await db.document_search()

            if document_list is None or (hasattr(document_list, "empty") and document_list.empty):
                return {"status": "error", "message": "결재 양식 DB 조회에 실패했습니다."}

            import pandas as pd
            if not isinstance(document_list, pd.DataFrame):
                document_list = pd.DataFrame(document_list)

            # 양식명 검색 (공백 제거 후 비교)
            query_clean = form_name.replace(" ", "")
            # 정확 매칭
            mask_name = document_list["FORMNAME"].str.replace(" ", "").apply(lambda x: query_clean in x or x in query_clean)
            mask_fldr = document_list["FLDRNAME"].str.replace(" ", "").apply(lambda x: query_clean in x or x in query_clean)
            df = document_list[mask_name | mask_fldr]

            if df.empty:
                # 부분 매칭
                mask_partial = document_list["FORMNAME"].str.contains(form_name, na=False, case=False)
                df = document_list[mask_partial]

            if df.empty:
                return {
                    "status": "not_found",
                    "message": f"'{form_name}' 양식을 찾을 수 없습니다.",
                    "available_forms": document_list["FORMNAME"].tolist()[:20],
                }

            df = df.fillna("-")
            # 양식 URL 생성
            forms = []
            for _, row in df.iterrows():
                form_id = row.get("FORMID", "")
                form_url = (
                    f"https://new.e-kamco.com/kamcoSupport/sanc/standard/formDraftExecute.do"
                    f"?form={form_id}&K={_auth.k}&viewpage=executeDraft#default"
                )
                forms.append({
                    "form_id": str(form_id),
                    "form_name": str(row.get("FORMNAME", "-")),
                    "category": str(row.get("FLDRNAME", "-")),
                    "description": str(row.get("DESCRIPTION", "-")),
                    "form_url": form_url,
                })

            # HTML 생성
            html = '<div class="doccall-table">'
            html += "<style>.doccall-table {max-height: 500px; overflow-y: auto;}.doccall-table th {min-width: 50px;} .doccall-table th:nth-child(2) {min-width: 120px;} .doccall-table th:nth-child(3) {min-width: 100px;} .doccall-table th:nth-child(4) {min-width: 150px;}</style>\n"
            html += "<table><thead><tr><th>no</th><th>결재 양식</th><th>분류</th><th>설명</th></tr></thead><tbody>"
            for idx, f in enumerate(forms):
                html += f'<tr><td><center>{idx + 1}</center></td>'
                html += f'<td><center><a href="{f["form_url"]}" target="_blank">{f["form_name"]}</a></center></td>'
                html += f'<td><center>{f["category"]}</center></td>'
                html += f'<td>{f["description"]}</td></tr>'
            html += "</tbody></table></div>"

            return {
                "status": "success",
                "message": f"'{form_name}' 관련 양식 {len(forms)}건을 찾았습니다.",
                "html_content": html,
                "text_summary": "\n".join([f"- {f['form_name']} ({f['category']}): {f['description']}" for f in forms]),
                "forms": forms,
            }
        except Exception as e:
            logger.error(f"get_approval_form API 오류: {e}")

    # ==========================================
    # 2. 더미 데이터 - 양식 템플릿
    # ==========================================
    form_templates = {
        "지출결의서": {
            "form_id": "FORM-001",
            "form_name": "지출결의서",
            "category": "회계",
            "description": "업무 관련 지출 결의",
            "form_url": "https://new.e-kamco.com/kamcoSupport/sanc/standard/formDraftExecute.do?form=FORM-001&viewpage=executeDraft#default",
        },
        "휴가신청서": {
            "form_id": "FORM-002",
            "form_name": "휴가신청서",
            "category": "인사",
            "description": "연차/반차/병가/경조사 휴가 신청",
            "form_url": "https://new.e-kamco.com/kamcoSupport/sanc/standard/formDraftExecute.do?form=FORM-002&viewpage=executeDraft#default",
        },
        "출장신청서": {
            "form_id": "FORM-003",
            "form_name": "출장신청서",
            "category": "업무",
            "description": "국내/해외 출장 신청",
            "form_url": "https://new.e-kamco.com/kamcoSupport/sanc/standard/formDraftExecute.do?form=FORM-003&viewpage=executeDraft#default",
        },
        "통합기안양식": {
            "form_id": "FORM-004",
            "form_name": "통합기안양식",
            "category": "일반",
            "description": "일반 업무 기안",
            "form_url": "https://new.e-kamco.com/kamcoSupport/sanc/standard/formDraftExecute.do?form=FORM-004&viewpage=executeDraft#default",
        },
        "구매요청서": {
            "form_id": "FORM-005",
            "form_name": "구매요청서",
            "category": "회계",
            "description": "물품 및 서비스 구매 요청",
            "form_url": "https://new.e-kamco.com/kamcoSupport/sanc/standard/formDraftExecute.do?form=FORM-005&viewpage=executeDraft#default",
        },
    }

    # 양식 검색
    form_data = form_templates.get(form_name)

    if not form_data:
        return {
            "status": "not_found",
            "message": f"'{form_name}' 양식을 찾을 수 없습니다.",
            "available_forms": list(form_templates.keys())
        }

    forms = [form_data]
    html = '<div class="doccall-table">'
    html += '<style>.doccall-table {max-height: 500px; overflow-y: auto;}.doccall-table th {min-width: 50px;} .doccall-table th:nth-child(2) {min-width: 120px;} .doccall-table th:nth-child(3) {min-width: 100px;} .doccall-table th:nth-child(4) {min-width: 150px;}</style>\n'
    html += "<table><thead><tr><th>no</th><th>결재 양식</th><th>분류</th><th>설명</th></tr></thead><tbody>"
    for idx, f in enumerate(forms):
        html += f'<tr><td><center>{idx + 1}</center></td>'
        html += f'<td><center><a href="{f["form_url"]}" target="_blank">{f["form_name"]}</a></center></td>'
        html += f'<td><center>{f["category"]}</center></td>'
        html += f'<td>{f["description"]}</td></tr>'
    html += "</tbody></table></div>"

    return {
        "status": "success",
        "message": f"'{form_name}' 관련 양식 1건을 찾았습니다. (더미 데이터)",
        "html_content": html,
        "text_summary": f"- {form_data['form_name']} ({form_data['category']}): {form_data['description']}",
        "forms": forms,
    }


async def get_my_approvals(status=None, date_from=None, date_to=None, _auth=None):
    """
    내 결재함(대기 중인 결재 문서)을 조회합니다.

    Args:
        status: 결재 상태 (pending: 대기, approved: 승인, rejected: 반려)
        date_from: 조회 시작일 (YYYY-MM-DD)
        date_to: 조회 종료일 (YYYY-MM-DD)

    Returns:
        dict: 결재 문서 목록
    """

    # ==========================================
    # 1. API 호출 시도 (실제 환경)
    # ==========================================
    # TODO: 실제 GW API 연동 (내 결재함 조회)
    # try:
    #     from chatsam.app.tasks.node_agent.aiassistant.services.gw_api import get_my_approvals_api
    #     response = get_my_approvals_api(
    #         status=status,
    #         date_from=date_from,
    #         date_to=date_to
    #     )
    #     if response["status"] == "success":
    #         return response
    # except Exception as e:
    #     print(f"API 호출 실패: {e}")
    #     pass


    # ==========================================
    # 2. 더미 데이터 - 결재 문서 목록
    # ==========================================
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    mock_approvals = [
        {
            "doc_id": "APPR-2026-001",
            "form_name": "지출결의서",
            "title": "2월 업무 회식비 지출",
            "drafter": {
                "name": "김철수",
                "dept": "디지털시스템실",
                "team": "AI팀"
            },
            "amount": 500000,
            "created_at": today.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",
            "current_approver": "나",
            "approval_line": ["김철수(기안)", "나(팀장)", "박서현(본부장)"]
        },
        {
            "doc_id": "APPR-2026-002",
            "form_name": "출장신청서",
            "title": "부산 고객사 방문 출장",
            "drafter": {
                "name": "이영희",
                "dept": "공사채권본부",
                "team": "채권관리팀"
            },
            "created_at": yesterday.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",
            "current_approver": "나",
            "approval_line": ["이영희(기안)", "나(팀장)", "이민호(본부장)"]
        },
        {
            "doc_id": "APPR-2026-003",
            "form_name": "휴가신청서",
            "title": "연차 신청 (3/1-3/2)",
            "drafter": {
                "name": "박민수",
                "dept": "디지털시스템실",
                "team": "AI팀"
            },
            "created_at": two_days_ago.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "approved",
            "current_approver": "완료",
            "approval_line": ["박민수(기안)", "나(팀장-승인)"]
        },
        {
            "doc_id": "APPR-2026-004",
            "form_name": "구매요청서",
            "title": "개발 서버 장비 구매",
            "drafter": {
                "name": "정수아",
                "dept": "디지털시스템실",
                "team": "AI팀"
            },
            "amount": 3000000,
            "created_at": two_days_ago.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",
            "current_approver": "나",
            "approval_line": ["정수아(기안)", "나(팀장)", "박서현(본부장)", "구매팀"]
        }
    ]

    # 상태 필터링
    if status:
        mock_approvals = [
            doc for doc in mock_approvals
            if doc["status"] == status
        ]

    # 날짜 필터링 (간단히 구현)
    # 실제로는 created_at을 파싱해서 비교해야 함

    pending_count = sum(1 for doc in mock_approvals if doc["status"] == "pending")

    return {
        "status": "success",
        "message": f"결재 문서 {len(mock_approvals)}건을 조회했습니다. (대기: {pending_count}건) (더미 데이터)",
        "query": {
            "status": status,
            "date_from": date_from,
            "date_to": date_to
        },
        "approvals": mock_approvals,
        "total_count": len(mock_approvals),
        "pending_count": pending_count
    }


async def approve_document(doc_id, comment=None, _auth=None):
    """
    결재 문서를 승인합니다.

    Args:
        doc_id: 문서 ID (예: APPR-2026-001)
        comment: 승인 의견 (선택)

    Returns:
        dict: 승인 결과
    """

    # ==========================================
    # 1. API 호출 시도 (실제 환경)
    # ==========================================
    # TODO: 실제 GW API 연동 (결재 승인)
    # try:
    #     from chatsam.app.tasks.node_agent.aiassistant.services.gw_api import approve_document_api
    #     response = approve_document_api(
    #         doc_id=doc_id,
    #         comment=comment
    #     )
    #     if response["status"] == "success":
    #         return response
    # except Exception as e:
    #     print(f"API 호출 실패: {e}")
    #     pass


    # ==========================================
    # 2. 더미 응답
    # ==========================================
    if not doc_id:
        return {
            "status": "error",
            "message": "문서 ID가 필요합니다."
        }

    return {
        "status": "success",
        "message": f"문서 {doc_id}을(를) 승인했습니다. (더미 데이터)",
        "doc_id": doc_id,
        "action": "approved",
        "comment": comment or "",
        "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "next_approver": "박서현 본부장"  # 예시
    }


async def reject_document(doc_id, reason, _auth=None):
    """
    결재 문서를 반려합니다.

    Args:
        doc_id: 문서 ID (예: APPR-2026-001)
        reason: 반려 사유 (필수)

    Returns:
        dict: 반려 결과
    """

    # ==========================================
    # 1. API 호출 시도 (실제 환경)
    # ==========================================
    # TODO: 실제 GW API 연동 (결재 반려)
    # try:
    #     from chatsam.app.tasks.node_agent.aiassistant.services.gw_api import reject_document_api
    #     response = reject_document_api(
    #         doc_id=doc_id,
    #         reason=reason
    #     )
    #     if response["status"] == "success":
    #         return response
    # except Exception as e:
    #     print(f"API 호출 실패: {e}")
    #     pass


    # ==========================================
    # 2. 더미 응답
    # ==========================================
    if not doc_id or not reason:
        return {
            "status": "error",
            "message": "문서 ID와 반려 사유가 필요합니다."
        }

    return {
        "status": "success",
        "message": f"문서 {doc_id}을(를) 반려했습니다. (더미 데이터)",
        "doc_id": doc_id,
        "action": "rejected",
        "reason": reason,
        "rejected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "returned_to": "기안자"
    }
