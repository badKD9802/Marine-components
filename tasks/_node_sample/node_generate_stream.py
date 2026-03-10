import logging

from langgraph.graph import END, START
from langgraph.types import StreamWriter

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustLLM, JustMessage, JustMilvus, LangGraphState, service, util
from app.justtype.rag.just_retrieve import JustRetriever
from app.schemas.session import ChunkInfo

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==DEFAULT_MULTI_TURN==")


# ------------------------------------------------------------------------
# 응답 생성에 필요한 Chunk를 retrieve한다.
# ------------------------------------------------------------------------
async def node_retrieve_chunk__(stat: LangGraphState, writer: StreamWriter):
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
        # return {"rag_code": "fail", "rag_answer": f"문서내에서 응답이 있는 위치를 찾을 수 없습니다. 유사도=[{score}]"}
    else:
        # --------- 검색 결과 청크 저장 ---------
        chunk_cnt = chunk_count if len(chunk_list) > chunk_count else len(chunk_list)
        chunks = service.pack_chunk_infos(question, chunk_cnt, chunk_list)
        just.append_answer("응답이 존재하는 청크검색까지 성공했습니다.", 40, chunks)
        return_stat = LangGraphState(rag_code="succ")

    logger.info("retrieve_chunk (검색 종료: only bert)")
    writer(stat)
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

    return tokenizer.decode(tokens)


# ------------------------------------------------------------------------
# ChatGPT로 응답을 생성한다.
# ------------------------------------------------------------------------
async def node_generate(stat: LangGraphState, writer: StreamWriter):
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

    just = JustMessage(stat)
    logger.info("generation (생성 시작)")
    if just.get_rag_code() == "fail":  # 더이상 진행할 필요가 없다.
        return

    # --------------------------------------------------------------------------------------------
    # --- 일단, 응답을 생성하기전에 이제까지의 Chunk정보를 먼저 날린다.
    # --------------------------------------------------------------------------------------------
    writer(stat)

    # --------------------------------------------------------------------------------------------
    # --- 변수 가져오기.
    # --------------------------------------------------------------------------------------------
    just_llm = JustLLM(stat, is_stream=True)
    service_name = just.get_value("service_name")
    question = just.get_question()
    v2_service = just.get_config("v2_service")
    if v2_service is None:
        just.append_answer(f"service({service_name})의 config 값에 'v2_service'가 없습니다.", -1)
        return LangGraphState(rag_code="fail")
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
        history_str = just.get_history_str()
        chunks = just.get_chunks()
        chunk_str = truncate_token_limit(tokenizer_name, chunks, 2048, 3)
        prompt_str = prompt_template.replace("{HISTORY}", history_str)
        prompt_str = prompt_str.replace("{QUESTION}", question)
        prompt_str = prompt_str.replace("{DOCUMENT}", chunk_str)
        logger.info(f"node_generate prompt: \n{prompt_str}")

    if just_llm:
        send_message = await just_llm.make_send_msg(prompt_str)
        full_response = ""
        async for content in await just_llm.get_response(send_message):
            if content:
                full_response += content
                writer(content)

        just.update_answer(full_response, 100)  # 최종 응답 설정
    else:
        response_message = "The information about the LLM in the [system config] is inaccurate"
        just.update_answer(response_message, -1)

    logger.info("generation (생성 종료)")
    stat["rag_code"] = "succ"
    writer(stat)
    return


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, stream_mode=None):
    workflow.add_node("GENERATE_ANSWER", node_generate)

    workflow.add_edge(START, "GENERATE_ANSWER")
    workflow.add_edge("GENERATE_ANSWER", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
