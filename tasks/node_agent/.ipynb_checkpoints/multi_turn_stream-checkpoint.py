import logging

from langgraph.graph import END, START

# =============================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.tasks.lib_justtype.common import util
from app.tasks.lib_justtype.common.just_message import JustMessage, LangGraphState
from app.tasks.node_agent.aiassistant.services.call import call
from app.tasks.node_agent.aiassistant.services.confirm import confirm
from app.tasks.node_agent.aiassistant.services.llm import llm
from app.tasks.node_agent.aiassistant.services.mail_draft import mail_draft
from app.tasks.node_agent.aiassistant.services.requery import requery
from app.tasks.node_agent.aiassistant.services.route import router
from app.tasks.node_agent.aiassistant.services.schedule import schedule
from app.tasks.node_agent.aiassistant.services.search import search
from app.tasks.node_agent.aiassistant.services.translate import translate
from app.tasks.node_agent.aiassistant.services.verification import verification
from app.tasks.node_agent.nodes.node_generate_stream import node_generate
from app.tasks.node_agent.nodes.node_retrieve_kamco import node_retrieve
from app.tasks.node_agent.nodes.node_multi_question import node_multi_question

from app.tasks.node_agent.aiassistant.services.parsing import (
    parser,
    check_for_missing_info,
    ask_for_missing_info,
    LLM_answer,
    translate_answer,
    call_answer,
    schedule_answer,
    mail_draft_answer,
)
from app.tasks.node_agent.aiassistant.services.calendar import (
    gw_api_calendar_insert,
    gw_api_calendar_search,
    gw_api_calendar_update,
    gw_api_calendar_delete,
    calendar_reservation_api_result,
    calendar_check_api_result,
    calendar_delete_api_result,
    calendar_update_api_result,
)
from app.tasks.node_agent.aiassistant.services.meeting import (
    gw_api_meeting_insert,
    gw_api_meeting_search,
    gw_api_meeting_update,
    gw_api_meeting_delete,
    meeting_reservation_api_result,
    meeting_check_api_result,
    meeting_delete_api_result,
    meeting_update_api_result,
)
from app.tasks.node_agent.aiassistant.services.api_collection import APICollection
from app.tasks.node_agent.aiassistant.services.imwon_search import *

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==DEFAULT_MULTI_TURN==")
api = APICollection()


# ------------------------------------------------------------------------
# 응답 생성에 필요한 Chunk를 retrieve한다.
# ------------------------------------------------------------------------
async def node_is_rag_service(stat: LangGraphState):
    logger.info("요구사항 분석 시작")
    just_msg = JustMessage(stat)
    question_type = just_msg.get_question_type()
    if not question_type:
        return "route"

    if question_type == "question":
        return "rag"
    elif question_type == "multi_question":
        return "multi_question"
    else:
        return "route"


# async def node_response_fail(stat: LangGraphState, writer: StreamWriter):
#     just_msg = JustMessage(stat)
#     just_msg.update_answer("질문 메타정보가 부족하여 응답생성을 시작할 수 없습니다.", -1)
#     logger.info("node_response_fail (종료)")
#     writer(stat)


def route_result(stat: LangGraphState) -> str:
    logger.info("요구사항 분석 시작")
    just_msg = JustMessage(stat)
    ex_data = just_msg.get_cur_extra_data()
    logger.info(f"========ex_data check  {ex_data}=========")

    # if missing_keys:
    #     return "ask_for_missing_info"
    # else:
    just_msg = JustMessage(stat)
    question_type = just_msg.get_question_type()
    logger.info(f"= paser 끝 STEP 1=")
    if not question_type:
        return "llm"
    logger.info(f"= STEP 2=")
    if question_type == "question":
        return "rag_generate"

    logger.info(f"= STEP 3=")
    # question_type의 값이 "llm_question"인 경우 아래로 흘러감:
    ex_data = just_msg.get_cur_extra_data()
    if ex_data:
        route = ex_data.get("route", "")
        logger.info(f"= 분기 마지막 STEP 4={route}=====")

    # route = ex_data_route.get("route", "llm")
    # logger.info(f"= STEP 5={route}=====")

    return route


def parser_result(stat: LangGraphState) -> str:
    logger.info("요구사항 분석 시작")
    just_msg = JustMessage(stat)
    ex_data = just_msg.get_cur_extra_data()
    logger.info(f"========ex_data check  {ex_data}=========")
    missing_keys = ex_data.get("missing_keys", "")
    logger.info(f"==========={missing_keys}=====missing값 확인")
    if missing_keys:
        return "ask_for_missing_info"
    else:
        just_msg = JustMessage(stat)
        question_type = just_msg.get_question_type()
        logger.info(f"= paser 끝 STEP 1=")
        if not question_type:
            return "llm"
        logger.info(f"= STEP 2=")
        if question_type == "question":
            return "rag_generate"

        logger.info(f"= STEP 3=")
        # question_type의 값이 "llm_question"인 경우 아래로 흘러감:
        ex_data = just_msg.get_cur_extra_data()
        route = ex_data.get("route", "")

        logger.info(f"= 분기 마지막 STEP 4={route}=====")
        # route = ex_data_route.get("route", "llm")
        # logger.info(f"= STEP 5={route}=====")

        return route


def verification_result(stat: LangGraphState) -> str:
    just_msg = JustMessage(stat)
    ex_data = just_msg.get_cur_extra_data()

    retry = ex_data.get("retry", False)

    if retry == "yes":
        return "fail"
    else:
        return "success"


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, stream_mode=None):
    workflow.add_node("router", router)
    # workflow.add_node("calendar_answer", calendar)
    # workflow.add_node("meeting_answer", meeting)
    workflow.add_node("schedule_answer", schedule)
    workflow.add_node("search_answer", search)
    workflow.add_node("call_answer", call)
    workflow.add_node("mail_answer", llm)  # 메일 초안 개발시 변경
    workflow.add_node("translate_answer", llm)  # 번역 개발시 변경
    workflow.add_node("llm_answer", llm)
    workflow.add_node("verification", verification)
    workflow.add_node("requery", requery)
    workflow.add_node("confirm", confirm)
    workflow.add_node("rag_retrieve", node_retrieve)
    workflow.add_node("rag_generate", node_generate)
    workflow.add_node("multi_question", node_multi_question)
    # workflow.add_node("ANSWER_FAIL", node_response_fail)
    workflow.add_node("ask_for_missing_info", ask_for_missing_info)
    ## 일정 노드 추가
    workflow.add_node("parser", parser)
    workflow.add_node("gw_api_calendar_insert", gw_api_calendar_insert)
    workflow.add_node("gw_api_calendar_update", gw_api_calendar_update)
    workflow.add_node("gw_api_calendar_delete", gw_api_calendar_delete)
    workflow.add_node("gw_api_calendar_search", gw_api_calendar_search)

    workflow.add_node("calendar_check_api_result", calendar_check_api_result)
    workflow.add_node("calendar_reservation_api_result", calendar_reservation_api_result)
    workflow.add_node("calendar_update_api_result", calendar_update_api_result)
    workflow.add_node("calendar_delete_api_result", calendar_delete_api_result)

    ## 회의실 노드 추가 gw_api_meeting_insert
    workflow.add_node("gw_api_meeting_insert", gw_api_meeting_insert)
    workflow.add_node("gw_api_meeting_update", gw_api_meeting_update)
    workflow.add_node("gw_api_meeting_delete", gw_api_meeting_delete)
    workflow.add_node("gw_api_meeting_search", gw_api_meeting_search)

    workflow.add_node("meeting_check_api_result", meeting_check_api_result)
    workflow.add_node("meeting_reservation_api_result", meeting_reservation_api_result)
    workflow.add_node("meeting_update_api_result", meeting_update_api_result)
    workflow.add_node("meeting_delete_api_result", meeting_delete_api_result)

    ##임원 일정 추가
    workflow.add_node("imwon_search", imwon_search)

    # RAG 요구사항인지 체크크
    workflow.add_conditional_edges(
        START,
        node_is_rag_service,
        {
            "rag": "rag_retrieve",
            "multi_question": "multi_question",
            "route": "router",
        },
    )

    # 조건부 엣지 추가
    workflow.add_conditional_edges(
        "parser",
        parser_result,
        {
            "ask_for_missing_info": "ask_for_missing_info",
            # "calendar": 'calendar_answer',
            "meeting_check": "gw_api_meeting_search",
            "meeting_reservation": "gw_api_meeting_insert",
            "meeting_cancellation": "gw_api_meeting_delete",
            "meeting_update": "gw_api_meeting_update",
            "schedule": "imwon_search",
            "search": "search_answer",
            "call": "call_answer",
            # "mail": "mail_answer",
            # "translate": "translate_answer",
            # "LLM": "llm_answer",
            "calendar_check": "gw_api_calendar_search",
            "calendar_reservation": "gw_api_calendar_insert",
            "calendar_cancellation": "gw_api_calendar_delete",
            "calendar_update": "gw_api_calendar_update",
        },
    )

    workflow.add_conditional_edges(
        "router",
        route_result,
        {
            # "calendar": 'parser',
            "meeting_check": "parser",
            "meeting_reservation": "parser",
            "meeting_cancellation": "parser",
            "meeting_update": "parser",
            "schedule": "parser",
            "search": "parser",
            "call": "parser",
            "mail": "mail_answer",
            "translate": "translate_answer",
            "LLM": "llm_answer",
            "calendar_check": "parser",
            "calendar_reservation": "parser",
            "calendar_cancellation": "parser",
            "calendar_update": "parser",
        },
    )

    # workflow.add_conditional_edges(
    #     "verification",
    #     verification_result,
    #     {
    #         "success": "confirm",  # 테스트용 종료, 실제 는 컨펌 받는 노드로 이동
    #         "fail": "requery",  # 재질문 노드로 이동
    #     },
    # )

    ##일정 노드 추가
    workflow.add_edge("gw_api_calendar_insert", "calendar_reservation_api_result")
    workflow.add_edge("gw_api_calendar_update", "calendar_update_api_result")
    workflow.add_edge("gw_api_calendar_search", "calendar_check_api_result")
    workflow.add_edge("gw_api_calendar_delete", "calendar_delete_api_result")
    workflow.add_edge("calendar_reservation_api_result", END)
    # workflow.add_edge("calendar_cancle_api_result", END)
    workflow.add_edge("calendar_check_api_result", END)
    workflow.add_edge("calendar_delete_api_result", END)
    workflow.add_edge("calendar_update_api_result", END)

    ##임원 일정 노드 연결
    workflow.add_edge("imwon_search", END)

    ##회의실 노드 추가
    workflow.add_edge("gw_api_meeting_insert", "meeting_reservation_api_result")
    workflow.add_edge("gw_api_meeting_update", "meeting_update_api_result")
    workflow.add_edge("gw_api_meeting_search", "meeting_check_api_result")
    workflow.add_edge("gw_api_meeting_delete", "meeting_delete_api_result")

    workflow.add_edge("meeting_reservation_api_result", END)
    workflow.add_edge("meeting_check_api_result", END)
    workflow.add_edge("meeting_delete_api_result", END)
    workflow.add_edge("meeting_update_api_result", END)

    workflow.add_edge("ask_for_missing_info", END)

    workflow.add_edge("rag_retrieve", "rag_generate")

    workflow.add_edge("rag_generate", END)
    workflow.add_edge("multi_question", END)

    workflow.add_edge("requery", END)  # 재질문 후 종료
    workflow.add_edge("confirm", END)  # 컨펌 후 종료

    workflow.add_edge("mail_answer", END)
    workflow.add_edge("translate_answer", END)
    workflow.add_edge("llm_answer", END)

    # workflow.add_edge("RETRIEVE_CHUNK", "GENERATE_ANSWER")
    # workflow.add_edge("GENERATE_ANSWER", END)
    # 에디 추가 코드
    # workflow.add_edge()


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
