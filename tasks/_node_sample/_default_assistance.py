import logging

from fastapi import WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import ClientInfo, LangGraphState, ServiceInfo, llm_api, service, util
from app.schemas.session import ChunkInfo, MessageSchema, RequestSchema, SessionSchema

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==DEFAULT_MULTI_TURN==")


# ------------------------------------------------------------------------
# 요구사항을 받아서 분석하고, 이후 진행에 필요한 request_type값을 저장한다.
# ------------------------------------------------------------------------
async def node_get_request(stat: LangGraphState):
    client_info: ClientInfo = stat["client_info"]
    req_data: RequestSchema = client_info.req_data
    if req_data.messages[-1].content is None:
        return {"rag_job": "common"}
    elif req_data.messages[-1].content == "회의실 예약":
        return {"rag_job": "booking"}
    else:
        return {"rag_job": "file_searh"}


# ------------------------------------------------------------------------
# "request_type" 값에 따라서 분기.
# ------------------------------------------------------------------------
async def node_check_req(stat: LangGraphState):
    logger.info(f"check_req rag_job=[{stat['rag_job']}]")
    if stat["rag_job"] is None:
        return stat["rag_job"]
    return "fail"


# ------------------------------------------------------------------------
# token을 적당한 크기로 자른다.
# ------------------------------------------------------------------------
def truncate_token_limit(tokenizer_name, chunk_infos: list[ChunkInfo], token_cnt=1600, merge_cnt=3):
    max_token_cnt = token_cnt

    max_merge_cnt = merge_cnt
    merge_cnt = max_merge_cnt if len(chunk_infos) > max_merge_cnt else len(chunk_infos)

    merge_text = (
        "\n\n".join([f"청크{i + 1}:\n{info.chunk}" for i, info in enumerate(chunk_infos[:merge_cnt])])
        if merge_cnt > 1
        else f"청크1:\n{chunk_infos[0].chunk}"
    )

    logger.info(f"tokenizer ({tokenizer_name})")
    tokenizer = util.get_tokenizer(tokenizer_name)
    tokens = tokenizer.encode(merge_text, add_special_tokens=False)
    if len(tokens) > max_token_cnt:
        tokens = tokens[:max_token_cnt]

    return tokenizer.decode(tokens)


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
async def node_gen_common(stat: LangGraphState):
    rag_prompt_template = """
        당신의 고객의 질문데 대해서 성실히 대답하는 것 입니다.
        이전 대화 내역은 Q/A 쌍으로 제공되며, 첫 대화인 경우 이전 대화 내역에는 아무 내용이 없습니다.

        ## 이전 대화 내역
        {HISTORY}

        ## 지침
        1. 질문의 의도가 명확하지 않다면 되묻는 것도 가능합니다.
        2. 표나 차트의 값을 다룰 때 단위에 주의를 기울이세요.
        3. 이전 대화 내역 중 답변에 도움이 되는 내용이 있다면 참고해도 됩니다.
        4. 표 형식으로 제시할 수 있는 수치 데이터, 비교 정보 또는 구조화된 정보가 있다면 표 형태로 생성하세요.

        ## 위 지침을 바탕으로 다음 질문에 답해주세요.
        {QUESTION}
    """

    logger.info("generation (생성 시작)")
    if stat["rag_code"] == "fail":  # 더이상 진행할 필요가 없다.
        return
    # --------------------------------------------------------------------------------------------
    # --- 변수 가져오기.
    # --------------------------------------------------------------------------------------------
    service_info: ServiceInfo = stat["service_info"]
    client_info: ClientInfo = stat["client_info"]
    res_data: SessionSchema = client_info.res_data
    req_data: RequestSchema = client_info.req_data
    question = req_data.messages[-1].content  # 한개이겠지만, 혹시나 모르니..
    logger.info(f"node_generate question: {question}")

    # --------------------------------------------------------------------------------------------
    # --- llm에게 보낼 prompt를 생성해서, llm에게 질문을 보내고 응답을 받는다.
    # --------------------------------------------------------------------------------------------
    # prompt_template = service_info.prompt_template
    last_message: MessageSchema = service.get_last_message(res_data, "answer")

    qna_str = service.get_qna_str(res_data)
    chunk_str = truncate_token_limit(service_info.tokenizer_name, last_message.chunks, 2048, 3)
    prompt_str = rag_prompt_template.replace("{HISTORY}", qna_str)
    prompt_str = prompt_str.replace("{QUESTION}", question)
    prompt_str = prompt_str.replace("{DOCUMENT}", chunk_str)
    logger.info(f"node_generate prompt: \n{prompt_str}")

    chat_gpt = llm_api.ChatGpt(stat=stat, websocket=None)

    if chat_gpt:
        send_message = await chat_gpt.make_send_msg(prompt_str)
        last_message.content = await chat_gpt.get_response(send_message)
        last_message.percentage = 100
    else:
        last_message.content = "The information about the LLM in the [system config] is inaccurate"

    # llm_result_str = "저는 지금 대답할 수 없는 상태입니다."
    # --------------------------------------------------------------------------------------------
    # --- llm에게 보낼 prompt를 생성해서, llm에게 질문을 보내고 응답을 받는다.
    # --------------------------------------------------------------------------------------------

    service.update_message(res_data, last_message)
    logger.info("generation (생성 종료)")
    return_stat = LangGraphState(rag_code="succ")
    return return_stat


async def node_gen_booking(stat: LangGraphState):
    rag_prompt_template = """
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
    service_info: ServiceInfo = stat["service_info"]
    client_info: ClientInfo = stat["client_info"]
    res_data: SessionSchema = client_info.res_data
    req_data: RequestSchema = client_info.req_data
    question = req_data.messages[-1].content  # 한개이겠지만, 혹시나 모르니..
    logger.info(f"node_generate question: {question}")

    # --------------------------------------------------------------------------------------------
    # --- llm에게 보낼 prompt를 생성해서, llm에게 질문을 보내고 응답을 받는다.
    # --------------------------------------------------------------------------------------------
    # prompt_template = service_info.prompt_template
    last_message: MessageSchema = service.get_last_message(res_data, "answer")

    qna_str = service.get_qna_str(res_data)
    chunk_str = truncate_token_limit(service_info.tokenizer_name, last_message.chunks, 2048, 3)
    prompt_str = rag_prompt_template.replace("{HISTORY}", qna_str)
    prompt_str = prompt_str.replace("{QUESTION}", question)
    prompt_str = prompt_str.replace("{DOCUMENT}", chunk_str)
    logger.info(f"node_generate prompt: \n{prompt_str}")

    chat_gpt = llm_api.ChatGpt(stat=stat, websocket=None)

    if chat_gpt:
        send_message = await chat_gpt.make_send_msg(prompt_str)
        last_message.content = await chat_gpt.get_response(send_message)
        last_message.percentage = 100
    else:
        last_message.content = "The information about the LLM in the [system config] is inaccurate"

    # llm_result_str = "저는 지금 대답할 수 없는 상태입니다."
    # --------------------------------------------------------------------------------------------
    # --- llm에게 보낼 prompt를 생성해서, llm에게 질문을 보내고 응답을 받는다.
    # --------------------------------------------------------------------------------------------

    service.update_message(res_data, last_message)
    logger.info("generation (생성 종료)")
    return_stat = LangGraphState(rag_code="succ")
    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("GET_REQUEST", node_get_request)
    workflow.add_node("GENERATE_COMM_ANSWER", node_gen_common)
    workflow.add_node("GENERATE_BOOK_ANSWER", node_gen_booking)
    workflow.add_node("ANSWER_FAIL", node_response_fail)

    workflow.add_edge(START, "GET_REQUEST")
    workflow.add_conditional_edges(
        "GET_REQUEST",
        node_check_req,
        # fmt: off
        {
            "common": "GENERATE_COMM_ANSWER",
            "booking": "GENERATE_BOOK_ANSWER",
            "fail": "ANSWER_FAIL"
        },
        # fmt: on
    )
    workflow.add_edge("GET_DOCUMENT_LIST", END)
    workflow.add_edge("RETRIEVE_CHUNK", "GENERATE_ANSWER")
    workflow.add_edge("GENERATE_ANSWER", END)
    workflow.add_edge("ANSWER_FAIL", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
