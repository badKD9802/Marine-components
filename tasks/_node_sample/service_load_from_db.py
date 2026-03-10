import json
import logging
from datetime import datetime

import pandas
from fastapi import WebSocket
from langgraph.graph import END, START
from pymilvus.client.types import LoadState

from app.core.config import GlobalSettings

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.db.database import db_connector
from app.justtype.rag import JustMessage, LangGraphState, service, util
from app.justtype.rag.just_retrieve import JustRetriever, Tokenizer
from app.justtype.rag.service import Worker
from app.orm import admin_orm, service_orm
from app.tasks.lib_justtype.vector import MilvusConstant, MilvusDataset, milvus_service

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== SERVICE LOAD ==")


# ------------------------------------------------------------------------
# 응답 생성에 필요한 Chunk를 retrieve한다.
# ------------------------------------------------------------------------
# async def start_service(session, req_info, settings):
async def service_load(stat: LangGraphState):
    # --------- 변수 가져오기 ---------
    just = JustMessage(stat)
    settings: GlobalSettings = just.get_settings()
    service_name = just.get_value("service_name")
    user_id = just.get_value("user_id")
    # v2_service = just.get_config("v2_service")
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
    await Worker.delete_all_workers(session_status, service_name)  # 해당 서비스의 모든 worker들의 db를 지운다. (다시 add해라)
    await service.delete_retriever(service_name)  # 혹시 찌꺼기 지우고 시작한다.
    logger.info("========== SERVICE LOADING ===============")
    try:
        # -------------------------------------------------------
        # DB에서 Loading으로 Service 상태 바꾸기
        # -------------------------------------------------------
        await service.update_agent_data(session_status, service_name, data_status="loading")
        await admin_orm.update_service_status(session_status, service_name, "Loading", True)  # 없어질놈.
        logger.info(f"SERVICE LOAD({service_name}) STEP 1 (set RDB stat ==> 'Loading')")

        # -------------------------------------------------------
        # DB에서 svc_info의 값을 가져온다.
        # -------------------------------------------------------
        svc_info = await service_orm.select_service(session_status, service_name)
        logger.info(f"SERVICE LOAD({service_name}) STEP 2 (select svc_info from RDB)")
        field2column = {v: k for k, v in MilvusConstant.service_column_2field.items()}  # HHHHHHH 왜 하는 걸까?
        service_name = svc_info["service_name"]

        Tokenizer(svc_info["tokenizer"])
        # chatsam_util.action_tokenizer(svc_info["tokenizer"], req_info.action)
        logger.info(f"SERVICE LOAD({service_name}) STEP 3 (tokenizer name=[{svc_info['tokenizer']}] load)")

        # -------------------------------------------------------
        # Retriever생성해서 global memory에 올린다.
        # -------------------------------------------------------
        retriever = JustRetriever(svc_info, settings, 0)  # 생성자는 pid를 일단 0으로 한다.
        logger.info(f"SERVICE LOAD({service_name}) STEP 3.1 (create Retriever) ")
        retriever.connect_vector_db()
        logger.info(f"SERVICE LOAD({service_name}) STEP 3.2 (connect vectorDB) ")
        retriever.load_bm25()
        logger.info(f"SERVICE LOAD({service_name}) STEP 3.3 (load bm25 from pickle file) ")
        retriever.load_embedding_model()
        logger.info(f"SERVICE LOAD({service_name}) STEP 3.4 (---- Retriever OK --------)")

        # -------------------------------------------------------
        # 있는거 지우고 다시 만든다.
        # -------------------------------------------------------
        milvus_handler = retriever.milvus_handler
        logger.info(f"SERVICE LOAD({service_name}) STEP 4 (---- VectorDB 넣기 시작 --------)")
        milvus_handler.drop_collection(service_name)
        logger.info("SERVICE LOAD (REGEN) STEP 4.1 (drop collection) ")

        collection = milvus_handler.create_collection(service_name, MilvusConstant.service_fields, MilvusConstant.VECTOR_DIMENSION)
        logger.info("SERVICE LOAD (REGEN) STEP 4.2 (create collection)")

        if svc_info["index_params"] and svc_info["index_params"] != "None":
            index_params = json.loads(svc_info["index_params"])
            index_params["metric_type"] = "COSINE"  # metric_type은 COSINE으로 해야 함
        else:
            index_params = MilvusConstant.INDEX_PARAMS
        milvus_handler.create_index(collection, MilvusConstant.EMBEDDING_FILED_NAME, index_params)
        logger.info("SERVICE LOAD (REGEN) STEP 4.3 (create index)")

        milvus_handler.collection_load(collection)
        logger.info("SERVICE LOAD (REGEN) STEP 4.4 (load collection)")

        chunk_data = await admin_orm.select_service_data_chunk(session_status, svc_info["service_id"])
        header_data = [
            "document_name",
            "category_1",
            "category_2",
            "category_3",
            "main_chunk",
            "sub_chunk",
            "sub_chunk_seq",
            "question",
            "answer",
            "page_number",
            "main_chunk_link",
            "search_key",
        ]
        df_chunk_data = pandas.DataFrame(chunk_data, columns=header_data)
        df_chunk_data.to_csv(r"C:\chatSAM\kamco-apiserver\app\tasks\agent_modules\etl\보고서.csv")
        # file_path = r"C:\chatSAM\kamco-apiserver\app\tasks\agent_modules\etl\chunking_result1.csv"
        # df_chunk_data = pandas.read_csv(file_path, encoding="utf-8-sig")  # 파일 읽기

        # q_columns = df_chunk_data[svc_info["query_column"]].tolist()  # 이코드는 None에 대한 예외처리를 못함.
        q_columns = df_chunk_data[svc_info["query_column"]].fillna("").tolist()
        logger.info("SERVICE LOAD STEP 4.5 (select chunk data from RDB)")

        embedded_data = retriever.embedder.encode(q_columns, convert_to_tensor=False)
        logger.info(f"SERVICE LOAD STEP 4.6 RDB column({svc_info['query_column']}) embedding")

        dataset = MilvusDataset(df_chunk_data, embedded_data, field2column, MilvusConstant.EMBEDDING_FILED_NAME)
        ins_count = milvus_service.dataset_to_vector(milvus_handler, collection, service_name, dataset)
        logger.info(f"SERVICE LOAD STEP 4.7 (insert embedding Chunk cnt=({ins_count}) to vectorDB)")

        if svc_info["search_type"] == "bert_bm25":
            retriever.save_bm25()
            logger.info("SERVICE LOAD STEP 4.8 (save bm25 to pickle file)")

        await service.update_agent_data(session_status, service_name, data_status="loaded", changed_data_at=datetime.now(), changer=user_id)
        await service.update_worker_status(session_status, service_name)
        await admin_orm.update_service_status(session_status, service_name, "Loaded", True)
        logger.info(f"SERVICE LOAD({service_name}) STEP 5 (set RDB stat ==> 'Success')")

        # await admin_orm.update_service_status(session_status, service_name, "Running", True)
        # t_log.info(f"SERVICE LOAD({service_name}) STEP 6 (set RDB stat ==> 'Running')")

        # if req_info.requester_pid != 0:  # parents call 성공을 보내면 count가 하나 더 많게 된다. (client만 보낸다)
        #     await redis.publish(f"{req_info.service_path}:start", json.dumps({str(os.getpid()): "OK"}))
        # async with redis.client() as conn:
        #     await conn.hset("app:workers", os.getpid(), f"running({service_name})")

        logger.info("========== SERVICE LOAD FINISH ===============")

    except Exception as e:
        logger.info(f"SERVICE LOAD FAIL({service_name})  : {e}")
        await service.update_agent_data(session_status, service_name, data_status="unloaded")
        await admin_orm.update_service_status(session_status, service_name, "Fail", True)
        if milvus_handler and milvus_handler.load_state(service_name) == LoadState.Loaded:
            milvus_handler.collection_release(service_name)

        # if req_info.requester_pid != 0:  # parents call 성공을 보내면 count가 하나 더 많게 된다. (client만 보낸다)
        #     await redis.publish(f"{req_info.service_path}:start", json.dumps({str(os.getpid()): "FAIL"}))
        # async with redis.client() as conn:
        #     await conn.hset("app:workers", os.getpid(), f"fail({service_name}<{e})")

        raise Exception(f"service action Exception {e}") from e
    finally:
        await service.delete_retriever(service_name)  # 다 올렸으니깐, 어쨌든 지운다.
        await session_status.close()

    just.append_answer(f"서비스({service_name}) 로드 성공")
    return_stat = LangGraphState(rag_code="succ")
    logger.info(f"SERVICE LOAD SUCCESS ({service_name})")
    return return_stat

    # await redis.close()


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("SERVICE_LOAD", service_load)

    workflow.add_edge(START, "SERVICE_LOAD")
    workflow.add_edge("SERVICE_LOAD", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
