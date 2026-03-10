import glob
import logging
import os
from datetime import datetime

import pandas
from fastapi import HTTPException, WebSocket
from langgraph.graph import END, START
from pymilvus.client.types import LoadState

from app.core.config import GlobalSettings

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.db.database import db_connector
from app.justtype.rag import JustMessage, JustMilvus, LangGraphState, service, util
from app.justtype.rag.just_retrieve import JustRetriever, Tokenizer
from app.justtype.rag.service import Worker

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== SERVICE LOAD FROM FILES ==")


async def service_load_from_file(stat: LangGraphState):
    # --------- 변수 가져오기 ---------
    just = JustMessage(stat)
    settings: GlobalSettings = just.get_settings()
    service_name = just.get_value("service_name")
    user_id = just.get_value("user_id")
    v2_service = just.get_config("v2_service")
    config_etl = just.get_config("etl")
    if config_etl is None:
        just.append_answer(f"service({service_name})의 config 값에 'etl'가 없습니다.", -1)
        return LangGraphState(rag_code="fail")

    folder_path = config_etl["document"]["folder_path"]
    file_filther_path = os.path.join(folder_path, "*.csv")
    file_pathes = glob.glob(file_filther_path)
    if not file_pathes:
        raise HTTPException(status_code=404, detail=f"[{folder_path}]에 파일이 없습니다.")

    # -------------------------------------------------------------
    # 이 코드 결국은 삭제하고, 메모리 없애는 코드 찾아라.
    # -------------------------------------------------------------
    milvus_handler = None
    session_status = db_connector.scoped_session()
    await Worker.delete_all_workers(session_status, service_name)  # 해당 서비스의 모든 worker들의 db를 지운다. (다시 add해라)
    await service.delete_retriever(service_name)  # 혹시 찌꺼기 지우고 시작한다.
    logger.info("========== SERVICE LOADING ===============")
    try:
        # -------------------------------------------------------
        # DB에서 Loading으로 Service 상태 바꾸기
        # -------------------------------------------------------
        await service.update_agent_data(session_status, service_name, data_status="loading")
        # await admin_orm.update_service_status(session_status, service_name, "Loading", True)  # 없어질놈.
        logger.info(f"SERVICE LOAD({service_name}) STEP 1 (set RDB stat ==> 'Loading')")

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
        logger.info(f"SERVICE LOAD({service_name}) STEP 2 (select svc_info from RDB)")
        service_name = v2_service["service_name"]

        Tokenizer(v2_service["tokenizer"])
        logger.info(f"SERVICE LOAD({service_name}) STEP 3 (tokenizer name=[{v2_service['tokenizer']}] load)")

        # -------------------------------------------------------
        # Retriever생성해서 global memory에 올린다.
        # -------------------------------------------------------
        retriever = JustRetriever(v2_service, settings, 0)  # 생성자는 pid를 일단 0으로 한다.
        logger.info(f"SERVICE LOAD({service_name}) STEP 3.1 (Retriever: created) ")
        retriever.connect_vector_db()
        logger.info(f"SERVICE LOAD({service_name}) STEP 3.2 (Retriever: connect vectorDB) ")
        retriever.load_bm25()
        logger.info(f"SERVICE LOAD({service_name}) STEP 3.3 (Retriever: load bm25 from pickle file) ")
        retriever.load_embedding_model()
        logger.info(f"SERVICE LOAD({service_name}) STEP 3.4 (Retriever: -------- OK --------)")
        # -------------------------------------------------------
        # 있는거 지우고 다시 만든다.
        # -------------------------------------------------------
        just_milvus = JustMilvus(stat)
        just_milvus.drop_collection()
        logger.info(f"SERVICE LOAD({service_name}) STEP 4 (JustMilvus: drop collection)")
        logger.info("SERVICE LOAD (REGEN) STEP 4.1 (drop collection) ")

        just_milvus.create_collection()
        logger.info("SERVICE LOAD (REGEN) STEP 4.2 (create collection)")

        just_milvus.create_index()
        logger.info("SERVICE LOAD (REGEN) STEP 4.3 (create index)")

        just_milvus.load()
        logger.info("SERVICE LOAD (REGEN) STEP 4.4 (load collection)")

        for file_path in file_pathes:
            df_chunk_data = pandas.read_csv(file_path, encoding="utf-8-sig")
            just_milvus.insert_data(df_chunk_data, retriever)
            logger.info(f"SERVICE LOAD STEP 4.5 file[{file_path}]")

        logger.info(f"SERVICE LOAD STEP 4.6 RDB column({v2_service['query_column']}) embedding")
        if v2_service["search_type"] == "bert_bm25":
            retriever.save_bm25()
            logger.info("SERVICE LOAD STEP 4.8 (save bm25 to pickle file)")

        await service.update_agent_data(session_status, service_name, data_status="loaded", changed_data_at=datetime.now(), changer=user_id)
        await service.update_worker_status(session_status, service_name)
        # await admin_orm.update_service_status(session_status, service_name, "Loaded", True)
        logger.info(f"SERVICE LOAD({service_name}) STEP 5 (set RDB stat ==> 'Success')")

        logger.info("========== SERVICE LOAD FINISH ===============")

    except Exception as e:
        logger.info(f"SERVICE LOAD FAIL({service_name})  : {e}")
        await service.update_agent_data(session_status, service_name, data_status="unloaded")
        # await admin_orm.update_service_status(session_status, service_name, "Fail", True)
        if milvus_handler and milvus_handler.load_state(service_name) == LoadState.Loaded:
            milvus_handler.collection_release(service_name)

        raise Exception(f"service action Exception {e}") from e
    finally:
        await service.delete_retriever(service_name)  # 다 올렸으니깐, 어쨌든 지운다.
        await session_status.close()

    just.append_answer(f"서비스({service_name}) 로드 성공")
    return_stat = LangGraphState(rag_code="succ")
    logger.info(f"SERVICE LOAD SUCCESS ({service_name})")
    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):
    workflow.add_node("SERVICE_LOAD", service_load_from_file)

    workflow.add_edge(START, "SERVICE_LOAD")
    workflow.add_edge("SERVICE_LOAD", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
