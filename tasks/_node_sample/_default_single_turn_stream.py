import logging

from langgraph.graph import END, START
from langgraph.types import StreamWriter

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustLLM, JustMessage, JustMilvus, LangGraphState, service, util
from app.justtype.rag.just_retrieve import JustRetriever
from app.schemas.session import ChunkInfo

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==DEFAULT_SINGLE_TURN_STREAM==")


# ------------------------------------------------------------------------
# 응답 생성에 필요한 Chunk를 retrieve한다.
# ------------------------------------------------------------------------
async def node_retrieve_chunk(stat: LangGraphState, writer: StreamWriter):
    logger.info("retrieve_chunk (검색 시작: only bert)")
    # --------- 변수 가져오기 ---------
    just = JustMessage(stat)
    just_milvus = JustMilvus(stat)
    service_name = just.get_value("service_name")
    question = just.get_question()
    question_type = just.get_question_type()
    v2_service = just.get_config("v2_service")
    if question_type == "llm_question":
        just.append_answer("청크검색 없이 LLM으로만 응답합니다.", 10)
        writer(stat)
        return

    if v2_service is None:
        just.append_answer(f"service({service_name})의 config 값에 'v2_service'가 없습니다.", -1)
        return LangGraphState(rag_code="fail")
    chunk_count = v2_service["chunk_count"]
    sim_limit = v2_service["sim_limit"]

    retriever: JustRetriever = service.retriver(service_name)
    if retriever is None:
        raise Exception(f"service({service_name}) retriever is not exists")

    # --------- 검색 대상 질문에 대한 EMBEDDING. ---------
    logger.info(f"retrieve_chunk question: {question}")
    embedded_question = retriever.embed(question)

    # --------- 검색 실행 ---------
    chunk_list = just_milvus.search_similar_chunks(embedded_question, ["연구소"], ["홍길동"], 0, top_k=30)

    # --------- 검색결과 유사도 체크 ---------
    score = chunk_list[0]["distance"]
    if score < sim_limit:  # 보통 0.82값을 넘지 못하면 llm까지 가지 않는다.
        just.append_answer(f"문서내에서 응답이 있는 위치를 찾을 수 없습니다. 유사도=[{score}]", -1)
        return_stat = LangGraphState(rag_code="fail")
    else:
        # --------- 검색 결과 청크 저장 ---------
        chunk_cnt = chunk_count if len(chunk_list) > chunk_count else len(chunk_list)
        chunks = service.pack_chunk_infos(question, chunk_cnt, chunk_list)
        just.append_answer("응답이 존재하는 청크검색까지 성공했습니다.", 40, chunks)
        return_stat = LangGraphState(rag_code="succ")

    logger.info("retrieve_chunk (검색 종료: only bert)")
    writer(stat)
    return


# ------------------------------------------------------------------------
# token을 적당한 크기로 자른다.
# ------------------------------------------------------------------------
def truncate_token_limit(tokenizer_name, chunk_infos: list[ChunkInfo], token_cnt=1600, merge_cnt=3):
    max_token_cnt = token_cnt

    max_merge_cnt = merge_cnt
    merge_cnt = max_merge_cnt if len(chunk_infos) > max_merge_cnt else len(chunk_infos)

    merge_text = "\n".join([info.chunk for info in chunk_infos[:merge_cnt]]) if merge_cnt > 1 else chunk_infos[0].chunk

    return_text = []
    logger.info(f"tokenizer ({tokenizer_name})")
    tokenizer = util.get_tokenizer(tokenizer_name)
    tokens = tokenizer.encode(merge_text, add_special_tokens=False)
    if len(tokens) > max_token_cnt:
        tokens = tokens[:max_token_cnt]

    return tokenizer.decode(tokens)


# ------------------------------------------------------------------------
# ChatGPT로 응답을 생성한다 (스트리밍 방식)
# ------------------------------------------------------------------------
async def node_generate(stat: LangGraphState, writer: StreamWriter):
    logger.info("generation (생성 시작 - 스트리밍)")
    if stat["rag_code"] == "fail":  # 더이상 진행할 필요가 없다.
        return
    # --------------------------------------------------------------------------------------------
    # --- 변수 가져오기.
    # --------------------------------------------------------------------------------------------
    just = JustMessage(stat)
    just_llm = JustLLM(stat, is_stream=True)
    service_name = just.get_value("service_name")
    question = just.get_question()
    v2_service = just.get_config("v2_service")
    if v2_service is None:
        just.append_answer(f"service({service_name})의 config 값에 'v2_service'가 없습니다.", -1)
        stat["rag_code"] = "fail"
        return
    tokenizer_name = v2_service["tokenizer"]

    logger.info(f"node_generate question: {question}")
    # --------------------------------------------------------------------------------------------
    # --- llm에게 보낼 prompt를 생성해서, llm에게 질문을 보내고 응답을 받는다.
    # --------------------------------------------------------------------------------------------
    question_type = just.get_question_type()
    if question_type == "llm_question":
        prompt_content = v2_service["llm_prompt_content"]
        prompt_str = prompt_content.replace("{q_str}", question)
    else:
        prompt_content = v2_service["prompt_content"]
        chunks = just.get_chunks()
        chunk_str = truncate_token_limit(tokenizer_name, chunks, 2048, 3)
        prompt_str = prompt_content.replace("{chunk_str}", chunk_str)
        prompt_str = prompt_str.replace("{q_str}", question)

    if just_llm:
        send_message = await just_llm.make_send_msg(prompt_str)
        full_response = ""
        async for content in await just_llm.get_response(send_message):
            if content:
                full_response += content
                writer(content)

        # 최종 응답 설정
        just.update_answer(full_response, 100)
    else:
        response_message = "The information about the LLM in the [system config] is inaccurate"
        just.update_answer(response_message, -1)

    logger.info("generation (생성 종료 - 스트리밍)")
    stat["rag_code"] = "succ"
    writer(stat)
    return


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, stream_mode=None):
    workflow.add_node("RETRIEVE_CHUNK", node_retrieve_chunk)
    workflow.add_node("GENERATE_ANSWER", node_generate)

    workflow.add_edge(START, "RETRIEVE_CHUNK")
    workflow.add_edge("RETRIEVE_CHUNK", "GENERATE_ANSWER")
    workflow.add_edge("GENERATE_ANSWER", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
