import logging

from fastapi import WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustMessage, LangGraphState, util
from app.tasks.node_sample.node_generate_batch import node_generate
from app.tasks.node_sample.node_retrieve import node_retrieve

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==DEFAULT_SINGLE_TURN==")


async def node_check_req(stat: LangGraphState):
    logger.info("요구사항 분석 시작")
    just = JustMessage(stat)
    question_type = just.get_question_type()
    if not question_type:
        return "fail"

    if question_type == "question":
        return "retrieve"
    elif question_type == "llm_question":
        return "generate"
    else:
        return "generate"


async def node_response_fail(stat: LangGraphState):
    just = JustMessage(stat)
    just.update_answer("질문에 메타정보가 부족하여 응답생성을 시작할 수 없습니다.", -1)
    just.set_rag_code("fail")
    logger.info("node_response_fail (종료)")
    return


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):
    workflow.add_node("RETRIEVE_CHUNK", node_retrieve)
    workflow.add_node("GENERATE_ANSWER", node_generate)
    workflow.add_node("ANSWER_FAIL", node_response_fail)

    workflow.add_conditional_edges(
        START,
        node_check_req,
        # fmt: off
        {
            "generate": "GENERATE_ANSWER",
            "retrieve": "RETRIEVE_CHUNK",
            "fail": "ANSWER_FAIL"
        },
        # fmt: on
    )

    # workflow.add_edge(START, "RETRIEVE_CHUNK")
    workflow.add_edge("RETRIEVE_CHUNK", "GENERATE_ANSWER")
    workflow.add_edge("GENERATE_ANSWER", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
