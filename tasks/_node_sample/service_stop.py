import logging
import os

from fastapi import WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.db.database import db_connector
from app.justtype.rag import JustMessage, LangGraphState, service, util
from app.justtype.rag.service import Worker

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== SERVICE STOP ==")


async def service_stop(stat: LangGraphState):
    # --------- 변수 가져오기 ---------
    just = JustMessage(stat)
    service_name = just.get_value("service_name")
    user_id = just.get_value("user_id")

    session_status = db_connector.scoped_session()
    worker = Worker(session_status, os.getpid(), service_name)
    logger.info("========== SERVICE STOPING ===============")
    try:
        # -------------------------------------------------------
        # DB에서 Loading으로 Service 상태 바꾸기
        # -------------------------------------------------------
        await worker.delete_worker()
        await service.update_agent_data(session_status, service_name, service_status="stopping")
        await service.update_worker_status(session_status, service_name)
        await service.delete_retriever(service_name)

        # await admin_orm.update_service_status(session_status, service_name, "Stop", True)
        logger.info("========== SERVICE STOP FINISH ===============")
        await service.update_agent_data(session_status, service_name, service_status="stopped", starter=user_id)

    except Exception as e:
        logger.info(f"SERVICE STOP FAIL({service_name})  : {e}")
        await service.update_agent_data(session_status, service_name, service_status="stopped", starter=user_id)
        # await admin_orm.update_service_status(session_status, service_name, "Fail", True)
        raise Exception(f"service action Exception {e}") from e
    finally:
        await session_status.close()

    just.append_answer(f"서비스({service_name}) 종료 성공")
    return_stat = LangGraphState(rag_code="succ")
    logger.info(f"SERVICE STOP SUCCESS ({service_name})")
    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("SERVICE_STOP", service_stop)

    workflow.add_edge(START, "SERVICE_STOP")
    workflow.add_edge("SERVICE_STOP", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
