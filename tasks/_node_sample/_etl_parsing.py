import logging

from fastapi import HTTPException, WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustMessage, LangGraphState, util
from app.tasks.lib_justtype.etl.just_etl import JustETL

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== ETL-PARSING ==")


async def node_etl_parsing(stat: LangGraphState):
    logger.info("PARSING : START ------------------")
    just = JustMessage(stat)
    just_etl = JustETL(stat)

    # 전체 결과를 저장할 딕셔너리
    try:
        # 먼저 로그인을 한다.
        await just_etl.login()
        await just_etl.parsing()  # path를 제공하지 않으면 config["etl"]["document"]["folder_path"]의 내용을 parsing한다.

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"폴더 처리 중 오류 발생: {str(e)}") from e

    just.update_answer("ETL연동하여 Parsing을 요청 했습니다.", percentage=100)

    return_stat = LangGraphState(rag_code="succ", rag_answer="Parsing시작 성공")
    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("ETL", node_etl_parsing)

    workflow.add_edge(START, "ETL")
    workflow.add_edge("ETL", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
