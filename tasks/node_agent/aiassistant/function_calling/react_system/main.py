"""LangGraph node entry point for ReAct agent using JustLLM."""

import asyncio
import re

from langgraph.types import StreamWriter

from app.schemas.session import ButtonInfoSchema, ButtonSchema
from app.tasks.lib_justtype.rag.just_llm import JustLLM
from app.tasks.node_agent.aiassistant.function_calling.react_system.tool_definitions import TOOLS
from app.tasks.node_agent.aiassistant.function_calling.react_system.tool_registry import ToolRegistry
from app.tasks.node_agent.aiassistant.function_calling.react_system.react_agent import ReactAgent
from app.tasks.node_agent.aiassistant.function_calling.react_system.auth_context import AuthContext
from app.tasks.lib_justtype.common.just_message import JustMessage, LangGraphState
from app.tasks.lib_justtype.common.just_env import JustEnv

# SUGGEST_SEARCH 마커 패턴: <!--SUGGEST_SEARCH:버튼라벨-->
_SUGGEST_SEARCH_RE = re.compile(r"<!--SUGGEST_SEARCH:(.+?)-->")
# QUICK_REPLY 마커 패턴: <!--QUICK_REPLY_YES:라벨--><!--QUICK_REPLY_NO:라벨-->
_QUICK_REPLY_YES_RE = re.compile(r"<!--QUICK_REPLY_YES:(.+?)-->")
_QUICK_REPLY_NO_RE = re.compile(r"<!--QUICK_REPLY_NO:(.+?)-->")


def _extract_suggest_search(text: str) -> tuple[str, str | None]:
    """응답 텍스트에서 SUGGEST_SEARCH 마커를 추출하고 제거한다.

    Returns:
        (마커 제거된 텍스트, 버튼 라벨 또는 None)
    """
    match = _SUGGEST_SEARCH_RE.search(text)
    if not match:
        return text, None
    button_label = match.group(1).strip()
    cleaned = _SUGGEST_SEARCH_RE.sub("", text).rstrip()
    return cleaned, button_label


def _extract_quick_replies(text: str) -> tuple[str, str | None, str | None]:
    """응답 텍스트에서 QUICK_REPLY 마커를 추출하고 제거한다.

    Returns:
        (마커 제거된 텍스트, YES 버튼 라벨, NO 버튼 라벨)
    """
    yes_match = _QUICK_REPLY_YES_RE.search(text)
    no_match = _QUICK_REPLY_NO_RE.search(text)
    if not yes_match and not no_match:
        return text, None, None
    yes_label = yes_match.group(1).strip() if yes_match else None
    no_label = no_match.group(1).strip() if no_match else None
    cleaned = _QUICK_REPLY_YES_RE.sub("", text)
    cleaned = _QUICK_REPLY_NO_RE.sub("", cleaned).rstrip()
    return cleaned, yes_label, no_label


async def llm(stat: LangGraphState, writer: StreamWriter):
    """LangGraph node: ReAct agent using JustLLM."""

    # 환경 변수
    writer(stat)
    just_msg = JustMessage(stat)
    just_env = JustEnv(stat)
    just_llm = JustLLM(stat, is_stream=False)

    ex_data = just_msg.get_cur_extra_data()
    ex_data_org = just_msg.get_extra_data() or {}

    # 현재 시간
    question = just_msg.get_question()
    # 과거 대화 내역
    history = just_msg.get_history_msg_list() or []

    # fallback 시 우선 사용할 서비스 힌트
    preferred_intent = (ex_data or {}).get("alternative_intent", "")

    # SLO 1회 호출 → AuthContext 생성 → 전체 ReAct 루프에서 재사용
    auth = await AuthContext.from_stat(stat)
    registry = ToolRegistry(auth=auth)
    max_iterations = 10  # just_env.get_config("llm").get("max_iterations", 10) 추후 config로 수정할 수 있게끔 변경 필요

    # 사용자 전체 정보 조회 (DB → SLO fallback)
    user_info = None
    if auth.is_authenticated:
        try:
            from app.tasks.node_agent.aiassistant.db_extract.db_search_api import OracleSearchClient
            db = OracleSearchClient(auth.stat)
            df = await db.search_by_empcode(auth.emp_code)
            if df is not None and not df.empty:
                row = df.iloc[0]
                user_info = {
                    "name": str(row.get("EMP_NM", auth.user_nm)),
                    "empno": str(row.get("EMPNO", auth.emp_code)),
                    "position": str(row.get("POSN_NM", "")),
                    "dept": str(row.get("DEPT_NM", auth.docdept_nm or "")),
                    "team": str(row.get("TEAM_NM", "")),
                    "email": str(row.get("EML", "")),
                    "phone": str(row.get("TEL_NO", "")),
                    "mobile": str(row.get("MBPH", "")),
                    "fax": str(row.get("FAX_NO", "")),
                    "duty": str(row.get("BIZ", "")),
                }
        except Exception:
            pass
        if not user_info:
            user_info = {
                "name": auth.user_nm,
                "empno": auth.emp_code,
                "dept": auth.docdept_nm or "",
            }

    agent = ReactAgent(just_llm, registry, TOOLS, max_iterations=max_iterations, writer=writer,
                       preferred_intent=preferred_intent, user_info=user_info)
    result = await agent.run(question, history)

    text_answer = result["answer"]
    html_blocks = result.get("html_blocks", [])
    was_streamed = result.get("streamed", False)

    # SUGGEST_SEARCH 마커 감지 → 버튼 생성
    text_answer, suggest_label = _extract_suggest_search(text_answer)
    button_info = None
    if suggest_label:
        button_info = ButtonInfoSchema(
            name="suggest_search_buttons",
            title="",
            purpose="intent_suggest",
            layout="horizontal",
            buttons=[
                ButtonSchema(
                    title=suggest_label,
                    name="intent_switch",
                    value=question,
                    value_type="question",
                    hint="사내 문서에서 검색합니다",
                ),
            ],
        )

    # QUICK_REPLY 마커 감지 → 확인/거절 버튼 생성
    if not button_info:
        text_answer, yes_label, no_label = _extract_quick_replies(text_answer)
        if yes_label or no_label:
            qr_buttons = []
            if yes_label:
                qr_buttons.append(
                    ButtonSchema(
                        title=yes_label,
                        name="intent_switch",
                        value=yes_label,
                        value_type="llm_question",
                        hint="",
                    )
                )
            if no_label:
                qr_buttons.append(
                    ButtonSchema(
                        title=no_label,
                        name="intent_keep",
                        value=no_label,
                        value_type="llm_question",
                        hint="",
                    )
                )
            button_info = ButtonInfoSchema(
                name="quick_reply_buttons",
                title="",
                purpose="intent_suggest",
                layout="horizontal",
                buttons=qr_buttons,
            )

    # 진행 UI를 summary 태그로 교체 (화면에 유지됨) + summary 태그 반환
    # (스트리밍된 경우 이미 react_agent 내부에서 finalize 호출됨 → 캐싱된 값 반환)
    summary_tag = agent.finalize_progress()

    # fallback 진입 시 이전 실패 단계를 앞에 합성
    fallback_steps = (ex_data or {}).get("fallback_steps")
    if fallback_steps:
        from app.tasks.node_agent.prompts.node_retrieve_prompts import build_step, make_agent_summary
        llm_step = build_step(len(fallback_steps) + 1, "💬 AI 답변 생성", "completed")
        all_steps = fallback_steps + [llm_step]
        summary_tag = make_agent_summary(all_steps)

    writer(stat)

    if not was_streamed:
        # 스트리밍되지 않은 경우에만 텍스트 재생
        for chunk in re.split(r'(?<=[ \n,.!?;:)])', text_answer):
            if chunk:
                writer(chunk)
                await asyncio.sleep(0.018)

    # summary 태그 + HTML 블록 + 텍스트 답변을 합쳐서 DB에 저장 (새로고침 후에도 진행 UI + HTML 유지)
    full_answer = summary_tag + "".join(html_blocks) + text_answer
    just_msg.update_answer(full_answer, 100, button_info=button_info)
    if button_info:
        writer({"button_info": button_info.model_dump(mode="json")})
    writer(stat)
