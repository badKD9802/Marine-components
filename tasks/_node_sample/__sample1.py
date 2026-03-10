import logging

from fastapi import WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import ClientInfo, JustMessage, LangGraphState, llm_api, service, util
from app.justtype.rag.just_retrieve import JustRetriever
from app.schemas.session import ChunkInfo, RequestSchema, SessionSchema
from app.tasks.lib_justtype.vector import milvus_service

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==DEFAULT_MULTI_TURN==")


# ------------------------------------------------------------------------
# 요구사항을 받아서 분석하고, 이후 진행에 필요한 request_type값을 저장한다.
# ------------------------------------------------------------------------
async def node_get_request(stat: LangGraphState):
    client_info: ClientInfo = stat["client_info"]
    req_data: RequestSchema = client_info.req_data
    if req_data.type is None:
        return {"rag_job": "question"}
    else:
        return {"rag_job": "question"}  # doc_list는 일단 없다.
        # return {"rag_job": req_data.type}  # rag_job = "doc_list" or "question"


# ------------------------------------------------------------------------
# "request_type" 값에 따라서 분기.
# ------------------------------------------------------------------------
async def node_check_req(stat: LangGraphState):
    logger.info(f"check_req rag_job=[{stat['rag_job']}]")
    if stat["rag_job"] == "doc_list":
        return "get_doc_list"
    elif stat["rag_job"] == "question":
        return "retrieve_chunk"
    return "fail"


# ------------------------------------------------------------------------
# 응답 생성에 필요한 Chunk를 retrieve한다.
# ------------------------------------------------------------------------
async def node_retrieve_chunk(stat: LangGraphState):
    logger.info("retrieve_chunk (검색 시작: only bert)")
    # --------- 변수 가져오기 ---------
    just = JustMessage(stat)
    service_name = just.get_value("service_name")
    question = just.get_question()
    v2_service = just.get_config("v2_service")
    if v2_service is None:
        just.append_answer(f"service({service_name})의 config 값에 'v2_service'가 없습니다.", -1)
        return LangGraphState(rag_code="fail")
    chunk_count = v2_service["chunk_count"]
    sim_limit = v2_service["sim_limit"]

    retriever: JustRetriever = service.retriver(service_name)
    if retriever is None:
        raise Exception(f"service({service_name}) retriever is not exists")

    # --------- 검색 대상 질문에 대한 EMBEDDING. ---------
    vectordb_handler = retriever.milvus_handler
    logger.info(f"retrieve_chunk question: {question}")
    embedded_question = retriever.embed(question)

    # --------- 검색 실행 ---------
    result_list = milvus_service.list_partition_by_search(
        vectordb_handler, embedded_question, service_name, [], top_k=30, search_params=None
    )

    # --------- 검색결과 유사도 체크 ---------
    score = result_list[0]["distance"]
    if score < sim_limit:  # 보통 0.82값을 넘지 못하면 llm까지 가지 않는다.
        just.append_answer(f"문서내에서 응답이 있는 위치를 찾을 수 없습니다. 유사도=[{score}]", -1)
        return_stat = LangGraphState(rag_code="fail")
        # return {"rag_code": "fail", "rag_answer": f"문서내에서 응답이 있는 위치를 찾을 수 없습니다. 유사도=[{score}]"}
    else:
        # --------- 검색 결과 청크 저장 ---------
        chunk_cnt = chunk_count if len(result_list) > chunk_count else len(result_list)
        chunks = service.pack_chunk_infos(question, chunk_cnt, result_list)
        just.append_answer("응답이 존재하는 청크검색까지 성공했습니다.", 40, chunks)
        return_stat = LangGraphState(rag_code="succ")

    logger.info("retrieve_chunk (검색 종료: only bert)")
    return return_stat


# ------------------------------------------------------------------------
# token을 적당한 크기로 자른다.
# ------------------------------------------------------------------------
def truncate_token_limit(tokenizer_name, chunk_infos: list[ChunkInfo], token_cnt=1600, merge_cnt=3):
    max_token_cnt = token_cnt

    max_merge_cnt = merge_cnt
    merge_cnt = max_merge_cnt if len(chunk_infos) > max_merge_cnt else len(chunk_infos)

    # merge_text = "\n".join([info.chunk for info in chunk_infos[:merge_cnt]]) if merge_cnt > 1 else chunk_infos[0].chunk
    merge_text = (
        "\n\n".join([f"청크{i + 1}:\n{info.chunk}" for i, info in enumerate(chunk_infos[:merge_cnt])])
        if merge_cnt > 1
        else f"청크1:\n{chunk_infos[0].chunk}"
    )

    return_text = []
    logger.info(f"tokenizer ({tokenizer_name})")
    tokenizer = util.get_tokenizer(tokenizer_name)
    tokens = tokenizer.encode(merge_text, add_special_tokens=False)
    if len(tokens) > max_token_cnt:
        tokens = tokens[:max_token_cnt]

    # return_text.append(tokenizer.decode(tokens))
    # return return_text
    return tokenizer.decode(tokens)


# ------------------------------------------------------------------------
# 검색 대상 document list를 리스트업한다.
# ------------------------------------------------------------------------
async def node_get_doc_list(stat: LangGraphState):
    retriever: JustRetriever = service.retriver(stat["service_info"].service_name)
    # retriever = util.get_retriever(stat["service_info"].service_name)
    if retriever is None:
        raise Exception(f"service {stat['service_info'].service_name} is not exists")

    milvus_handler = retriever.milvus_handler
    if milvus_handler is None:
        raise Exception("milvus_handler(ServiceObject) is None")

    svc_obj_list = stat["service_info"].all_svc_list
    link_info = milvus_service.list_document(milvus_handler, svc_obj_list)
    return {"doc_infos": link_info}


# ------------------------------------------------------------------------
# Fail 응답을 보내는 node
# ------------------------------------------------------------------------
async def node_response_fail(stat: LangGraphState):
    client_info: ClientInfo = stat["client_info"]
    res_data: SessionSchema = client_info.res_data
    last_message = service.get_last_message(res_data, "question")
    return {"rag_answer": f"질문[{last_message.content}]에 대한 응답처리에 실패했습니다."}


# ------------------------------------------------------------------------
# ChatGPT로 응답을 생성한다.
# ------------------------------------------------------------------------
async def node_generate(stat: LangGraphState):
    prompt_template = """
        당신의 임무는 청크를 분석하고 오직 청크에 제공된 정보만을 사용하여 질문에 답하는 것입니다. 각 청크는 <chunk> 태그로 묶여 있으며 인덱스와 파일명 등 다양한 메타데이터를 포함합니다.
        또한 각 청크안의 <supplement> 태그 안에는 해당 청크의 전후 내용을 취합한 내용이 정리되어 있으니 참고해도 됩니다.
        이전 대화 내역은 Q/A 쌍으로 제공되며, 첫 대화인 경우 이전 대화 내역에는 아무 내용이 없습니다.

        ## 청크
        <chunks>
        {DOCUMENT}
        </chunks>

        ## 이전 대화 내역
        {HISTORY}

        ## 지침
        1. 질문을 분석하여 청크에서 어떤 정보를 찾아야 하는지 파악하세요. 질문의 의도가 명확하지 않다면 되묻는 것도 가능합니다.
        2. 제공된 청크만으로 답변할 수 있는 부분은 상세히 답변하고 답변할 수 없는 부분은 "제공된 문서를 바탕으로 답변할 수 없습니다."라고 명시하세요.
        3. 제공된 청크에 없는 정보를 가정하거나 추가하지 마세요.
        4. 표나 차트의 값을 다룰 때 단위에 주의를 기울이세요.
        5. 이전 대화 내역 중 답변에 도움이 되는 내용이 있다면 참고해도 됩니다.
        6. 표 형식으로 제시할 수 있는 수치 데이터, 비교 정보 또는 구조화된 정보가 있다면 표 형태로 생성하세요.

        ## 위 지침을 바탕으로 다음 질문에 답해주세요.
        {QUESTION}
    """

    logger.info("generation (생성 시작)")
    if stat["rag_code"] == "fail":  # 더이상 진행할 필요가 없다.
        return
    # --------------------------------------------------------------------------------------------
    # --- 변수 가져오기.
    # --------------------------------------------------------------------------------------------
    just = JustMessage(stat)
    service_name = just.get_value("service_name")
    question = just.get_question()
    v2_service = just.get_config("v2_service")
    v2_llm_info = just.get_config("v2_llm_info")
    if v2_service is None:
        just.append_answer(f"service({service_name})의 config 값에 'v2_service'가 없습니다.", -1)
        return LangGraphState(rag_code="fail")
    tokenizer_name = v2_service["tokenizer"]

    logger.info(f"node_generate question: {question}")
    # --------------------------------------------------------------------------------------------
    # --- llm에게 보낼 prompt를 생성해서, llm에게 질문을 보내고 응답을 받는다.
    # --------------------------------------------------------------------------------------------
    history_str = just.get_history()
    chunks = just.get_chunks()
    chunk_str = truncate_token_limit(tokenizer_name, chunks, 2048, 3)
    prompt_str = prompt_template.replace("{HISTORY}", history_str)
    prompt_str = prompt_str.replace("{QUESTION}", question)
    prompt_str = prompt_str.replace("{DOCUMENT}", chunk_str)
    logger.info(f"node_generate prompt: \n{prompt_str}")

    chat_gpt = llm_api.ChatGpt(llm_info=v2_llm_info, websocket=None)

    if chat_gpt:
        send_message = await chat_gpt.make_send_msg(prompt_str)
        response_message = await chat_gpt.get_response(send_message)
        just.update_answer(response_message, 100)
    else:
        response_message = "The information about the LLM in the [system config] is inaccurate"
        just.update_answer(response_message, -1)

    # llm_result_str = "저는 지금 대답할 수 없는 상태입니다."
    # --------------------------------------------------------------------------------------------
    # --- llm에게 보낼 prompt를 생성해서, llm에게 질문을 보내고 응답을 받는다.
    # --------------------------------------------------------------------------------------------

    logger.info("generation (생성 종료)")
    return_stat = LangGraphState(rag_code="succ")
    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("GET_REQUEST", node_get_request)
    workflow.add_node("RETRIEVE_CHUNK", node_retrieve_chunk)
    workflow.add_node("GET_DOCUMENT_LIST", node_get_doc_list)
    workflow.add_node("GENERATE_ANSWER", node_generate)
    workflow.add_node("ANSWER_FAIL", node_response_fail)

    workflow.add_edge(START, "GET_REQUEST")
    workflow.add_conditional_edges(
        "GET_REQUEST",
        node_check_req,
        # fmt: off
        {
            "get_doc_list": "GET_DOCUMENT_LIST",
            "retrieve_chunk": "RETRIEVE_CHUNK",
            "fail": "ANSWER_FAIL"
        },
        # fmt: on
    )
    workflow.add_edge("GET_DOCUMENT_LIST", END)
    workflow.add_edge("RETRIEVE_CHUNK", "GENERATE_ANSWER")
    # workflow.add_edge("RETRIEVE", "ANSWER_FAIL")
    workflow.add_edge("GENERATE_ANSWER", END)
    workflow.add_edge("ANSWER_FAIL", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
