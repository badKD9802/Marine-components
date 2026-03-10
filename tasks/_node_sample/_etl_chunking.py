import logging

from fastapi import HTTPException, WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustMessage, LangGraphState, util
from app.tasks.lib_justtype.etl.just_etl import JustETL

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== ETL-PARSING ==")


async def node_etl_chunking(stat: LangGraphState):
    logger.info("PARSING : START ------------------")
    just = JustMessage(stat)
    just_etl = JustETL(stat)

    # 전체 결과를 저장할 딕셔너리
    try:
        # 먼저 로그인을 한다.
        await just_etl.login()
        await just_etl.get_json_to_csv()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"폴더 처리 중 오류 발생: {str(e)}") from e

    just.update_answer("ETL연동하여 Chunk을 성공했습니다.", percentage=100)

    return_stat = LangGraphState(rag_code="succ", rag_answer="Chunking 성공")

    # 5. DB에 넣기 (DB Table 생성부터 해야 한다) - 이때 kamco로 넣는다.
    # 5.1 먼저 현재의 db에서 가져오는 내용을 보자. (이걸 결국 vectordb에 넣지 않느냐?)
    # 5.2 그 가져오는 내용 그대로, table을 만들자.

    # 6. 이 내용을 load하는 기능을 넣어야 한다. - 이때 kamco로 조회해서 vector에 넣는다.

    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("ETL", node_etl_chunking)

    workflow.add_edge(START, "ETL")
    workflow.add_edge("ETL", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
