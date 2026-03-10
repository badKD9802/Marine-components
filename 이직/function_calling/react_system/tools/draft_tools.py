"""
메일/문서 초안 작성 도구
업무 메일 및 공식 문서의 초안을 생성합니다.

주요 기능:
- draft_email: 업무 메일 초안 작성
- draft_document: 공식 문서(보고서, 기획서 등) 초안 작성

선택적으로 OpenAI API를 활용한 고급 초안 생성 가능
"""

import logging
from app.tasks.lib_justtype.common import util

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== DRAFT TOOLS ==")


async def _get_sender_info(_auth=None):
    """인증 정보로 발신자 정보를 DB에서 조회한다."""
    if not _auth or not _auth.is_authenticated:
        # 더미 데이터 (테스트 환경)
        return {
            "name": "홍길동",
            "position": "팀장",
            "dept": "경영지원팀",
            "team": "재무팀",
            "email": "hong.gd@kamco.co.kr",
            "phone": "02-1234-7001",
            "mobile": "010-1234-7001",
        }
    try:
        from app.tasks.node_agent.aiassistant.db_extract.db_search_api import OracleSearchClient
        db = OracleSearchClient(_auth.stat)
        df = await db.search_by_empcode(_auth.emp_code)
        if df is not None and not df.empty:
            row = df.iloc[0]
            return {
                "name": str(row.get("EMP_NM", _auth.user_nm)),
                "position": str(row.get("POSN_NM", "")),
                "dept": str(row.get("DEPT_NM", _auth.docdept_nm or "")),
                "team": str(row.get("TEAM_NM", "")),
                "email": str(row.get("EML", "")),
                "phone": str(row.get("TEL_NO", "")),
                "mobile": str(row.get("MBPH", "")),
            }
    except Exception as e:
        logger.error(f"발신자 정보 조회 실패: {e}")
    # DB 조회 실패 시 SLO 기본 정보
    return {
        "name": _auth.user_nm or "",
        "dept": _auth.docdept_nm or "",
    }


def _build_signature(sender: dict, tone: str = "formal") -> str:
    """발신자 정보로 서명 블록을 생성한다."""
    if not sender:
        return "[발신자명]"
    name = sender.get("name", "")
    if not name:
        return "[발신자명]"

    parts = [name]
    position = sender.get("position", "")
    if position and position != "-":
        parts[0] = f"{name} {position}"

    dept = sender.get("dept", "")
    team = sender.get("team", "")
    org = " ".join(filter(None, [dept, team])) if (dept and dept != "-") or (team and team != "-") else ""
    if org:
        parts.append(org)

    email = sender.get("email", "")
    if email and email != "-":
        parts.append(f"E-mail: {email}")

    phone = sender.get("phone", "")
    if phone and phone != "-":
        parts.append(f"Tel: {phone}")

    mobile = sender.get("mobile", "")
    if mobile and mobile != "-":
        parts.append(f"Mobile: {mobile}")

    return "\n".join(parts)


async def draft_email(recipient, purpose, subject=None, key_points=None, tone="formal", _auth=None):
    """
    업무 메일 초안을 작성합니다.

    Args:
        recipient: 수신자 (예: 김팀장, 경영지원팀)
        purpose: 메일 목적 (예: 회의 일정 안내, 보고서 제출)
        subject: 메일 제목 (선택, 자동 생성)
        key_points: 핵심 내용 리스트 (선택)
        tone: 어조 (formal: 격식, casual: 친근, 기본값: formal)

    Returns:
        dict: 메일 초안
    """

    # 발신자 정보 조회
    sender = await _get_sender_info(_auth)
    signature = _build_signature(sender, tone)

    # 어조별 인사말/맺음말
    if tone == "formal":
        greeting = f"{recipient}님께,\n\n안녕하십니까."
        closing = f"감사합니다.\n\n{signature}"
    else:
        greeting = f"{recipient}님,\n\n안녕하세요!"
        closing = f"감사합니다.\n\n{signature}"

    # 본문 생성
    body_parts = [greeting, f"\n\n{purpose}에 대해 말씀드립니다.\n"]

    if key_points:
        body_parts.append("\n주요 내용은 다음과 같습니다:\n")
        for i, point in enumerate(key_points, 1):
            body_parts.append(f"{i}. {point}\n")
    else:
        body_parts.append("\n[구체적인 내용을 작성하세요]\n")

    body_parts.append(f"\n추가 문의사항이 있으시면 언제든 연락 부탁드립니다.\n\n{closing}")
    body = "".join(body_parts)

    # 제목 자동 생성
    if not subject:
        subject = f"[{purpose}] 안내"

    # 발신자 요약 (메타 정보용)
    sender_name = sender.get("name", "") if sender else ""
    sender_pos = sender.get("position", "") if sender else ""
    sender_org = " ".join(filter(None, [
        sender.get("dept", ""), sender.get("team", "")
    ])) if sender else ""
    from_label = sender_name
    if sender_pos and sender_pos != "-":
        from_label += f" {sender_pos}"
    if sender_org:
        from_label += f" ({sender_org})"

    # HTML: 복사 버튼 + 본문 박스
    import html as html_mod
    body_escaped = html_mod.escape(body)
    uid = f"email-draft-{id(body) % 100000}"
    html_content = f"""<style>#{uid} ::selection, #{uid}::selection {{ background:#264F78 !important; color:#fff !important; }}</style>
<div style="font-family:'Pretendard','Malgun Gothic',sans-serif;max-width:100%;margin:4px 0;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
    <span style="font-size:0.85em;color:#64748b;">📌 제목: <b>{html_mod.escape(subject)}</b>&nbsp;&nbsp;👤 수신: <b>{html_mod.escape(recipient)}</b>&nbsp;&nbsp;👤 발신: <b>{html_mod.escape(from_label)}</b></span>
    <button onclick="(function(){{var t=document.getElementById('{uid}').innerText;navigator.clipboard.writeText(t).then(function(){{var b=event.target;b.textContent='복사됨 ✓';setTimeout(function(){{b.textContent='📋 복사'}},1500)}})}})()" style="cursor:pointer;padding:4px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc;font-size:0.82em;color:#475569;white-space:nowrap;">📋 복사</button>
  </div>
  <div id="{uid}" style="white-space:pre-wrap;padding:16px 20px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;font-size:0.95em;line-height:1.7;color:#1e293b;">{body_escaped}</div>
</div>"""

    result = {
        "status": "success",
        "html_content": html_content,
        "text_summary": f"제목: {subject}\n수신: {recipient}\n발신: {from_label}\n\n{body}",
        "draft": {
            "to": recipient,
            "from": sender or {"name": "[발신자명]"},
            "subject": subject,
            "body": body,
            "tone": tone,
        },
        "message": "메일 초안이 작성되었습니다.",
    }
    return result


def draft_document(document_type, title, content_requirements=None, sections=None, _auth=None):
    """
    공식 문서 초안을 작성합니다.

    Args:
        document_type: 문서 유형 (보고서, 기획서, 제안서, 회의록, 공문)
        title: 문서 제목
        content_requirements: 포함할 내용 (선택)
        sections: 섹션 목록 (선택, 자동 생성)

    Returns:
        dict: 문서 초안
    """

    # ==========================================
    # 1. OpenAI API 활용 (선택적)
    # ==========================================
    # TODO: OpenAI API를 활용한 고급 문서 초안 생성
    # 실제 연동 시 아래 주석 해제하고 구현
    # try:
    #     import openai
    #     import os
    #     openai.api_key = os.getenv("OPENAI_API_KEY")
    #
    #     prompt = f"""
    #     다음 정보를 바탕으로 {document_type} 초안을 작성해주세요:
    #     - 제목: {title}
    #     - 포함 내용: {content_requirements if content_requirements else '없음'}
    #     - 섹션 구성: {sections if sections else '표준 형식'}
    #
    #     한국어로 작성하며, 공식 문서 형식을 유지해주세요.
    #     """
    #
    #     response = openai.ChatCompletion.create(
    #         model="gpt-4",
    #         messages=[
    #             {"role": "system", "content": "당신은 전문적인 업무 문서 작성 도우미입니다."},
    #             {"role": "user", "content": prompt}
    #         ],
    #         temperature=0.7
    #     )
    #
    #     generated_content = response.choices[0].message.content
    #     if generated_content:
    #         return {
    #             "status": "success",
    #             "draft": {
    #                 "document_type": document_type,
    #                 "title": title,
    #                 "body": generated_content,
    #                 "generated_by": "OpenAI GPT-4"
    #             },
    #             "message": f"{document_type} 초안이 작성되었습니다."
    #         }
    # except Exception as e:
    #     print(f"OpenAI API 호출 실패: {e}")
    #     # API 실패 시 템플릿으로 fallback
    #     pass


    # ==========================================
    # 2. 템플릿 기반 문서 생성 (fallback)
    # ==========================================

    # 문서 유형별 기본 섹션 템플릿
    templates = {
        "보고서": ["1. 개요", "2. 추진 배경 및 목적", "3. 주요 내용", "4. 추진 결과", "5. 향후 계획", "6. 결론"],
        "기획서": ["1. 기획 배경", "2. 목적 및 목표", "3. 추진 전략", "4. 세부 실행 계획", "5. 일정 및 예산", "6. 기대 효과"],
        "제안서": ["1. 제안 배경", "2. 제안 내용", "3. 기술적 접근 방법", "4. 예산 및 일정", "5. 기대 효과", "6. 결론"],
        "회의록": ["1. 회의 개요", "2. 참석자", "3. 주요 논의 사항", "4. 결정 사항", "5. 향후 조치 사항"],
        "공문": ["1. 제목", "2. 수신", "3. 참조", "4. 제목 (재명시)", "5. 본문", "6. 붙임", "7. 끝"]
    }

    # 기본 섹션 또는 사용자 지정 섹션
    if not sections:
        sections = templates.get(document_type, ["1. 서론", "2. 본론", "3. 결론"])

    # 문서 헤더
    document_body = f"""{'=' * 60}
{document_type.upper()}
{'=' * 60}

제목: {title}
작성일: {__import__('datetime').datetime.now().strftime("%Y년 %m월 %d일")}

{'=' * 60}

"""

    # 섹션별 내용
    for section in sections:
        document_body += f"\n{section}\n"
        document_body += "-" * 40 + "\n"
        document_body += f"[{section} 내용을 작성하세요]\n\n"

    # 추가 요구사항
    if content_requirements:
        document_body += f"\n\n{'=' * 60}\n"
        document_body += f"참고사항:\n{content_requirements}\n"
        document_body += f"{'=' * 60}\n"

    return {
        "status": "success",
        "draft": {
            "document_type": document_type,
            "title": title,
            "sections": sections,
            "body": document_body,
            "generated_by": "Template"
        },
        "message": f"{document_type} 초안이 작성되었습니다. (템플릿 기반)"
    }


# ==========================================
# 테스트용
# ==========================================
if __name__ == "__main__":
    print("=" * 70)
    print("메일/문서 초안 작성 도구 테스트")
    print("=" * 70)

    # 테스트 1: 격식 있는 메일
    print("\n[테스트 1: 격식 있는 업무 메일]")
    result1 = draft_email(
        recipient="김팀장",
        purpose="월간 보고서 제출",
        key_points=["2월 실적 보고서 첨부", "주요 성과 3가지", "차월 계획 포함"],
        tone="formal"
    )
    print(f"상태: {result1['status']}")
    print(f"메시지: {result1['message']}")
    print(f"제목: {result1['draft']['subject']}")
    print(f"본문 미리보기:\n{result1['draft']['body'][:200]}...\n")

    # 테스트 2: 친근한 메일
    print("\n[테스트 2: 친근한 메일]")
    result2 = draft_email(
        recipient="AI팀",
        purpose="팀 회식 일정 공유",
        tone="casual"
    )
    print(f"상태: {result2['status']}")
    print(f"제목: {result2['draft']['subject']}")

    # 테스트 3: 보고서 초안
    print("\n[테스트 3: 보고서 초안]")
    result3 = draft_document(
        document_type="보고서",
        title="2026년 1분기 AI 시스템 구축 추진 현황",
        content_requirements="LangGraph 적용, ReAct 패턴 구현, 15개 도구 통합"
    )
    print(f"상태: {result3['status']}")
    print(f"메시지: {result3['message']}")
    print(f"섹션 수: {len(result3['draft']['sections'])}개")
    print(f"본문 미리보기:\n{result3['draft']['body'][:300]}...\n")

    # 테스트 4: 회의록 초안
    print("\n[테스트 4: 회의록 초안]")
    result4 = draft_document(
        document_type="회의록",
        title="AI 시스템 개발 진행상황 점검 회의"
    )
    print(f"상태: {result4['status']}")
    print(f"메시지: {result4['message']}")

    print("\n" + "=" * 70)
