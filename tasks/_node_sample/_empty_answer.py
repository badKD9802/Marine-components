import logging

from fastapi import WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustMessage, LangGraphState, util

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==EMPTY_ANSWER==")


# ------------------------------------------------------------------------
# 응답 생성에 필요한 Chunk를 retrieve한다.
# ------------------------------------------------------------------------
async def node_empty_answer(stat: LangGraphState):
    # --------- 변수 가져오기 ---------
    just = JustMessage(stat)
    service_name = just.get_value("service_name")

    # --------- 응답생성 ---------
    just.append_answer(f"서비스({service_name})가 정상 작동중입니다.")
    return_stat = LangGraphState(rag_code="succ")

    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("EMPTY_ANSER", node_empty_answer)
    workflow.add_edge(START, "EMPTY_ANSER")
    workflow.add_edge("EMPTY_ANSER", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
