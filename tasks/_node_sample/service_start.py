import logging
import os
from datetime import datetime

from fastapi import WebSocket
from langgraph.graph import END, START
from pymilvus import utility as milvus_util
from pymilvus.client.types import LoadState

from app.core.config import GlobalSettings

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.db.database import db_connector
from app.justtype.rag import JustMessage, LangGraphState, service, util
from app.justtype.rag.just_retrieve import JustRetriever, Tokenizer
from app.justtype.rag.service import Worker
from app.tasks.lib_justtype.vector import MilvusConstant

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== SERVICE START ==")


async def service_start(stat: LangGraphState):
    # --------- 변수 가져오기 ---------
    just = JustMessage(stat)
    settings: GlobalSettings = just.get_settings()
    service_name = just.get_value("service_name")
    user_id = just.get_value("user_id")
    v2_service = just.get_config("v2_service")
    # if v2_service is None:
    #     just.append_answer(f"service({service_name})의 config 값에 'v2_service'가 없습니다.", -1)
    #     return LangGraphState(rag_code="fail")
    # chunk_count = v2_service["chunk_count"]
    # sim_limit = v2_service["sim_limit"]
    ##################
    # -------------------------------------------------------------
    # 이 코드 결국은 삭제하고, 메모리 없애는 코드 찾아라.
    # -------------------------------------------------------------
    milvus_handler = None
    session_status = db_connector.scoped_session()
    worker = Worker(session_status, os.getpid(), service_name)
    await worker.delete_worker()  # db에 있으면 지워라.
    await worker.create_worker()  # db에 생성하라.
    await worker.starting_worker(just.get_value("task_name"))  # 일단, 시작중이다.
    logger.info("========== SERVICE STARTING ===============")
    try:
        # -------------------------------------------------------
        # DB에서 Loading으로 Service 상태 바꾸기
        # -------------------------------------------------------
        await service.update_agent_data(session_status, service_name, service_status="starting")
        # await admin_orm.update_service_status(session_status, service_name, "Loading", True)  # 없어질놈.
        logger.info(f"SERVICE START({service_name}) STEP 1 (set RDB stat ==> 'Loading')")

        # -------------------------------------------------------
        # DB에서 svc_info의 값을 가져온다.
        # -------------------------------------------------------
        # svc_info = await service_orm.select_service(session_status, service_name)
        # svc_data = await service.get_service_info(session_status, service_name)
        # svc_info = {        # 이 값은 config가 제공해줘야 한다.
        #     "service_name": svc_data.service_name,
        #     "search_type": "bert",
        #     "query_column": "sub_chunk",
        #     "tokenizer": "beomi/Llama-3-Open-Ko-8B",
        #     "model_name": "dragonkue/bge-m3-ko",
        #     "db_regeneration": 1,
        #     "cpu": 0,
        # }
        logger.info(f"SERVICE START({service_name}) STEP 2 (select svc_info from RDB)")
        field2column = {v: k for k, v in MilvusConstant.service_column_2field.items()}  # HHHHHHH 왜 하는 걸까?
        service_name = v2_service["service_name"]

        Tokenizer(v2_service["tokenizer"])
        # chatsam_util.action_tokenizer(svc_info["tokenizer"], req_info.action)
        logger.info(f"SERVICE START({service_name}) STEP 3 (tokenizer name=[{v2_service['tokenizer']}] load)")

        # -------------------------------------------------------
        # Retriever생성해서 global memory에 올린다.
        # -------------------------------------------------------
        retriever = JustRetriever(v2_service, settings, 0)  # 생성자는 pid를 일단 0으로 한다.
        logger.info(f"SERVICE START({service_name}) STEP 3.1 (create Retriever) ")
        retriever.connect_vector_db()
        logger.info(f"SERVICE START({service_name}) STEP 3.2 (Retriever.connect vectorDB) ")
        retriever.load_bm25()
        logger.info(f"SERVICE START({service_name}) STEP 3.3 (load Retriever.bm25 from pickle file) ")
        retriever.load_embedding_model()
        logger.info(f"SERVICE START({service_name}) STEP 3.4 (load Retriever.embedding model) ")
        collection = milvus_util.has_collection(service_name)
        if not collection:
            logger.info("SERVICE SART ERROR (data is not loaded) ")
            raise Exception("SERVICE SART ERROR (data is not loaded!!)")
        milvus_handler = retriever.milvus_handler
        milvus_handler.collection_load_by_name(service_name)

        logger.info(f"SERVICE START({service_name}) STEP 4 (---- Retriever OK --------)")

        await service.update_agent_data(session_status, service_name, service_status="started", started_at=datetime.now(), starter=user_id)
        # await admin_orm.update_service_status(session_status, service_name, "Loaded", True)
        logger.info(f"SERVICE START({service_name}) STEP 5 (set RDB stat ==> 'Success')")

        # if req_info.requester_pid != 0:  # parents call 성공을 보내면 count가 하나 더 많게 된다. (client만 보낸다)
        #     await redis.publish(f"{req_info.service_path}:start", json.dumps({str(os.getpid()): "OK"}))
        # async with redis.client() as conn:
        #     await conn.hset("app:workers", os.getpid(), f"running({service_name})")
        logger.info("========== SERVICE START FINISH ===============")
        await worker.finish_worker()
        await service.update_worker_status(session_status, service_name)

    except Exception as e:
        logger.info(f"SERVICE START FAIL({service_name})  : {e}")
        await service.update_agent_data(session_status, service_name, service_status="stopped", starter=user_id)
        # await admin_orm.update_service_status(session_status, service_name, "Fail", True)
        if milvus_handler and milvus_handler.load_state(service_name) == LoadState.Loaded:
            milvus_handler.collection_release(service_name)

        # if req_info.requester_pid != 0:  # parents call 성공을 보내면 count가 하나 더 많게 된다. (client만 보낸다)
        #     await redis.publish(f"{req_info.service_path}:start", json.dumps({str(os.getpid()): "FAIL"}))
        # async with redis.client() as conn:
        #     await conn.hset("app:workers", os.getpid(), f"fail({service_name}<{e})")

        raise Exception(f"service action Exception {e}") from e
    finally:
        await session_status.close()

    just.append_answer(f"서비스({service_name}) 스타트 성공")
    return_stat = LangGraphState(rag_code="succ")
    logger.info(f"SERVICE START SUCCESS ({service_name})")
    return return_stat

    # await redis.close()


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("SERVICE_START", service_start)

    workflow.add_edge(START, "SERVICE_START")
    workflow.add_edge("SERVICE_START", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
