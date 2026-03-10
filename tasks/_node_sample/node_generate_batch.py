import logging

from fastapi import WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustLLM, JustMessage, LangGraphState, util
from app.schemas.session import ChunkInfo

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==NODE GENERATE BATCH ==")


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
# ChatGPT로 응답을 생성한다.
# ------------------------------------------------------------------------
async def node_generate(stat: LangGraphState):
    just = JustMessage(stat)
    logger.info("generation (생성 시작)")
    if just.get_rag_code() == "fail":  # 더이상 진행할 필요가 없다.
        return
    # --------------------------------------------------------------------------------------------
    # --- 변수 가져오기.
    # --------------------------------------------------------------------------------------------
    just_llm = JustLLM(stat, is_stream=False)
    service_name = just.get_value("service_name")
    question = just.get_question()
    v2_service = just.get_config("v2_service")
    if v2_service is None:
        just.append_answer(f"service({service_name})의 config 값에 'chatgpt_config'가 없습니다.", -1)
        return LangGraphState(rag_code="fail")
    prompt_content = v2_service["prompt_content"]
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
        chunks = just.get_chunks()
        chunk_str = truncate_token_limit(tokenizer_name, chunks, 2048, 3)
        prompt_str = prompt_content.replace("{chunk_str}", chunk_str)
        prompt_str = prompt_str.replace("{q_str}", question)

    send_message = await just_llm.make_send_msg(prompt_str)
    response_message = await just_llm.get_response(send_message)
    just.update_answer(response_message, 100)

    logger.info("generation (생성 종료)")
    return_stat = LangGraphState(rag_code="succ")
    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):
    workflow.add_node("GENERATE_ANSWER", node_generate)
    workflow.add_edge(START, "GENERATE_ANSWER")
    workflow.add_edge("GENERATE_ANSWER", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
