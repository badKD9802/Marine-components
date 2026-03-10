import logging

from fastapi import WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustMessage, JustMilvus, LangGraphState, service, util
from app.justtype.rag.just_retrieve import JustRetriever

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==DEFAULT_RETRIEVE==")


# ------------------------------------------------------------------------
# 응답 생성에 필요한 Chunk를 retrieve한다.
# ------------------------------------------------------------------------
async def node_retrieve(stat: LangGraphState):
    logger.info("retrieve_chunk (검색 시작: only bert)")
    # --------- 변수 가져오기 ---------
    just = JustMessage(stat)
    just_milvus = JustMilvus(stat)
    service_name = just.get_value("service_name")
    question = just.get_question()
    v2_service = just.get_config("v2_service")
    if v2_service is None:
        just.update_answer(f"service({service_name})의 config 값에 'v2_service'가 없습니다.", -1)
        just.set_rag_code("fail")
        return
    chunk_count = v2_service["chunk_count"]
    sim_limit = v2_service["sim_limit"]

    retriever: JustRetriever = service.retriver(service_name)
    if retriever is None:
        raise Exception(f"service({service_name}) retriever is not 'exists")

    # --------- 검색 대상 질문에 대한 EMBEDDING. ---------
    logger.info(f"retrieve_chunk question: {question}")
    embedded_question = retriever.embed(question)

    # --------- 검색 실행 ---------
    chunk_list = just_milvus.search_similar_chunks(embedded_question, ["연구소"], ["홍길동"], 0, top_k=30)

    score = chunk_list[0]["distance"]
    if score < sim_limit:  # 보통 0.82값을 넘지 못하면 llm까지 가지 않는다.
        just.update_answer(f"문서내에서 응답이 있는 위치를 찾을 수 없습니다. 유사도=[{score}]", -1)
        stat["rag_code"] = "fail"
        just.set_rag_code("fail")
    else:
        # --------- 검색 결과 청크 저장 ---------
        chunk_cnt = chunk_count if len(chunk_list) > chunk_count else len(chunk_list)
        chunks = service.pack_chunk_infos(question, chunk_cnt, chunk_list)
        just.update_answer("응답이 존재하는 청크검색까지 성공했습니다.", 40, chunks)
        just.set_rag_code("succ")

    logger.info("retrieve_chunk (검색 종료: only bert)")
    return


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):
    workflow.add_node("RETRIEVE_CHUNK", node_retrieve)
    workflow.add_edge(START, "RETRIEVE_CHUNK")
    workflow.add_edge("RETRIEVE_CHUNK", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
