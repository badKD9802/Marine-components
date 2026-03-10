import functools
import json
import logging
import re

import numpy
import pandas
from fastapi import WebSocket
from langgraph.graph import END, START
from rank_bm25 import BM25Okapi

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import ClientInfo, LangGraphState, ServiceInfo, llm_api, service, util
from app.justtype.rag.just_retrieve import JustRetriever

# ==========================================================
# HHHHHHHHHHH chat이 보이면 안 됨.
# ==========================================================
from app.schemas import chat
from app.schemas.session import ChunkInfo
from app.tasks.lib_justtype.vector import milvus_service

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== KAMCO_STREAM ==")


# ------------------------------------------------------------------------
# 요구사항을 받아서 분석하고, 이후 진행에 필요한 request_type값을 저장한다.
# ------------------------------------------------------------------------
async def node_get_request(stat: LangGraphState):
    client_info: ClientInfo = stat["client_info"]
    return {"rag_job": client_info.req_type}  # rag_job = "doc_list" or "question"


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
    service_info: ServiceInfo = stat["service_info"]
    client_info: ClientInfo = stat["client_info"]
    retriever: JustRetriever = service.retriver(service_info.service_name)
    if retriever is None:
        raise Exception(f"service {service_info.service_name} is not exists")

    # --------- 검색 대상 질문에 대한 EMBEDDING. ---------
    vectordb_handler = retriever.milvus_handler
    embedded_question = retriever.embed(stat["client_info"].question)

    # --------- 검색 실행 ---------
    result_list = milvus_service.list_partition_by_search(
        vectordb_handler, embedded_question, service_info.service_name, client_info.doc_list, top_k=30, search_params=None
    )

    # --------- 검색결과 유사도 체크 ---------
    score = result_list[0]["distance"]
    if score < service_info.sim_limit:  # 보통 0.82값을 넘지 못하면 llm까지 가지 않는다.
        return {"rag_code": "no_doc", "rag_answer": f"문서내에서 응답이 있는 위치를 찾을 수 없습니다. 유사도=[{score}]"}

    # --------- 검색 결과 청크 저장 ---------
    chunk_cnt = service_info.chunk_count if len(result_list) > service_info.chunk_count else len(result_list)
    chunk_infos = service.pack_chunk_infos(client_info.question, chunk_cnt, result_list)

    # --------- RETRIEVE Chunk 정보 응답에 저장 ---------
    return_stat = LangGraphState(
        rag_code="succ",
        chunk_infos=chunk_infos,
    )

    logger.info("retrieve_chunk (검색 종료: only bert)")
    return return_stat


# ------------------------------------------------------------------------
# 응답 생성에 필요한 Chunk를 retrieve한다.
# ------------------------------------------------------------------------
async def node_retrieve_chunk_bm25(stat: LangGraphState):
    logger.info("retrieve_chunk (검색 시작: only hybrid(bert & bm25))")
    # --------- 변수 가져오기 ---------
    service_info: ServiceInfo = stat["service_info"]
    client_info: ClientInfo = stat["client_info"]
    retriever: JustRetriever = service.retriver(service_info.service_name)
    if retriever is None:
        raise Exception(f"service {service_info.service_name} is not exists")

    # --------- 검색 대상 질문에 대한 EMBEDDING. ---------
    vectordb_handler = retriever.milvus_handler
    embedded_question = retriever.embed(client_info.question)

    # --------- 검색 실행 ---------
    mecab = service.Mecab()
    top_k = 30
    logger.info("retrieve_chunk_bm25 - Mecab()")

    filtered_idx = []
    if len(client_info.doc_list) > 0:
        pattern = "|".join([re.escape(doc_name) for doc_name in client_info.doc_list])
        filtered_rows = retriever.bm25_pickle_data["document_name"].str.contains(pattern, regex=True)

        filtered_idx.extend(retriever.bm25_pickle_data[filtered_rows].index)
        bm25_df = retriever.bm25_pickle_data.iloc[filtered_idx]  # 여기서는 일단 일부만 갖고오게 된다.
        bm25_df.reset_index(inplace=True, drop=True)  # indexing을 다시 한다.
    else:
        bm25_df = retriever.bm25_pickle_data

    tokenized_corpus = bm25_df["mecab_data"].tolist()
    results = []
    if len(tokenized_corpus) < 1:  # doc으로 filtering한 후에 값이 없으면, 한 건도 없는거다.
        results.append({"distance": 0})
        return results

    bm25 = BM25Okapi(tokenized_corpus)
    bm25_results = bm25.get_scores(mecab.morphs(client_info.question))
    bm25_results_id = bm25_df["id"].tolist()
    bm25_query_column = bm25_df[service_info.chunk_column].tolist()
    logger.info("retrieve_chunk_bm25 - get_score")

    sim = milvus_service.list_partition_by_search(
        vectordb_handler, embedded_question, service_info.service_name, client_info.doc_list, top_k=30, search_params=None
    )

    tmp_list = numpy.argsort(bm25_results)[::-1].tolist()
    if len(tmp_list) < top_k:
        bm25_results = tmp_list
    else:
        bm25_results = tmp_list[:top_k]

    # hybrid 추가 @제이든
    # ----------------------------------------------------------------------------------
    # sparse_results와 dense_result를 조합하여 뽑는다.
    # 결과적으로 result_df를 3개 생성한다.
    # ----------------------------------------------------------------------------------
    def reciprocal_rank_fusion(rank_lists):
        num_documents = len(rank_lists[0])
        fused_rank = [0] * num_documents

        for rank_list in rank_lists:
            for i, rank in enumerate(rank_list):
                fused_rank[i] += 1 / (rank + 1)
        return fused_rank

    sparse_results = []
    for i in bm25_results:
        sparse_results.append([bm25_results_id[i], bm25_query_column[i]])

    dense_results = []
    for results in sim:
        dense_results.append([results["id"], results[service_info.chunk_column]])

    dense_df = pandas.DataFrame(list(dense_results))
    dense_df.columns = ["id", "text"]
    dense_df["rank_dense"] = range(1, len(dense_df) + 1)  # dense_df에 'rank_dense' column을 추가한다.
    if len(sparse_results) > 0:
        sparse_df = pandas.DataFrame(sparse_results)
        sparse_df.columns = ["id", "text"]
        sparse_df["rank_sparse"] = range(1, len(sparse_df) + 1)  # sparse_df에 'rank_sparse' column을 추가한다.
        uni_results = dense_df.merge(sparse_df, how="outer")
    else:
        dense_df["rank_sparse"] = range(1, len(dense_df) + 1)  # dense_df에 'rank_sparse' column을 추가한다.
        uni_results = dense_df

    uni_results["rank_sparse"].fillna(len(uni_results) + 1, inplace=True)
    uni_results["rank_dense"].fillna(len(uni_results) + 1, inplace=True)
    uni_results["RRF"] = reciprocal_rank_fusion([uni_results["rank_dense"], uni_results["rank_sparse"]])
    rrf_df = uni_results.sort_values(["RRF"], ascending=False)

    search_idx_list = rrf_df["id"].tolist()[:20]  # 30개중에 10개만 뽑는다.
    search_score_list = [results["distance"] for results in sim]

    # 다른 컬럼 정보를 가져와야 함
    expr = f"id in {search_idx_list}"
    res = milvus_service.list_milvus_by_query(retriever.milvus_handler, service_info.service_name, expr)  # SAM: 여기는 왜 온대?
    result_list = []
    for i in range(len(search_idx_list)):
        found_objects = [obj for obj in res if obj["id"] == search_idx_list[i]]
        found_objects[0]["distance"] = search_score_list[i]
        result_list.append(found_objects[0])

    # --------- 검색결과 유사도 체크 ---------
    score = result_list[0]["distance"]
    if score < service_info.sim_limit:  # 보통 0.82값을 넘지 못하면 llm까지 가지 않는다.
        return {"rag_code": "no_doc", "rag_answer": f"문서내에서 응답이 있는 위치를 찾을 수 없습니다. 유사도=[{score}]"}

    # --------- 검색 결과 청크 저장 ---------
    chunk_cnt = service_info.chunk_count if len(result_list) > service_info.chunk_count else len(result_list)
    chunk_infos = service.pack_chunk_infos(client_info.question, chunk_cnt, result_list)

    # --------- RETRIEVE Chunk 정보 응답에 저장 ---------
    return_stat = LangGraphState(
        rag_code="succ",
        chunk_infos=chunk_infos,
    )
    logger.info("retrieve_chunk (검색 종료: only hybrid(bert & bm25))")
    return return_stat


# ------------------------------------------------------------------------
# token을 적당한 크기로 자른다.
# ------------------------------------------------------------------------
def truncate_token_limit(tokenizer_name, chunk_infos: list[ChunkInfo], token_cnt=1600, merge_cnt=3):
    max_token_cnt = token_cnt

    max_merge_cnt = merge_cnt
    merge_cnt = max_merge_cnt if len(chunk_infos) > max_merge_cnt else len(chunk_infos)

    merge_text = "\n".join([info.chunk for info in chunk_infos[:merge_cnt]]) if merge_cnt > 1 else chunk_infos[0].chunk

    return_text = []
    tokenizer = util.get_tokenizer(tokenizer_name)
    tokens = tokenizer.encode(merge_text, add_special_tokens=False)
    if len(tokens) > max_token_cnt:
        tokens = tokens[:max_token_cnt]

    return_text.append(tokenizer.decode(tokens))
    return return_text


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
    return {"rag_answer": f"질문[{stat['client_info'].question}]에 대한 응답처리에 실패했습니다."}


# ------------------------------------------------------------------------
# ChatGPT로 응답을 생성한다.
# ------------------------------------------------------------------------
async def node_generate(stat: LangGraphState, websocket: WebSocket):
    logger.info("generation (생성 시작)")
    if stat["rag_code"] == "fail":  # 더이상 진행할 필요가 없다.
        return

    answer = chat.ResponseByLLM(
        question=stat["client_info"].question,
        question_synonym=None,  # 유의어 변형했음을 고객에게 표시하기 위해.
        answer=stat["rag_answer"],
        type="answer",  # link인 경우 product값에 display_text, ans_src값은 서버에게 돌려주는 값.(search_item값)
        link=stat["chunk_infos"],
        svc_type=stat["client_info"].req_type,  # 필요없는 값으로 보인다. (확인 후 삭제 대상)
    )

    return_obj = {
        "result": {"code": 0, "message": "success"},
        "data": answer.model_dump(),
    }
    # 1차 : Chunk자료 먼저 전달.
    await websocket.send_text(json.dumps(return_obj, ensure_ascii=False))
    await websocket.send_text("start_typewriter")

    # --------------------------------------------------------------------------------------------
    # --- llm에게 보낼 prompt를 생성해서, llm에게 질문을 보내고 응답을 받는다.
    # --------------------------------------------------------------------------------------------
    if stat["rag_code"] == "no_doc":  # 문서 못 찾았다. 그냥 나가자.
        llm_result_str = stat["rag_answer"]
    else:
        prompt_template = stat["service_info"].prompt_template
        chunk_str = truncate_token_limit(stat["service_info"].tokenizer_name, stat["chunk_infos"], 2048, 3)
        prompt_str = prompt_template.replace("{chunk_str}", chunk_str[0])
        prompt_str = prompt_str.replace("{q_str}", stat["client_info"].question)

        chat_gpt = llm_api.ChatGpt(stat=stat, websocket=websocket)

        if chat_gpt:
            send_message = await chat_gpt.make_send_msg(prompt_str)
            llm_result_str = await chat_gpt.get_response(send_message)
        else:
            llm_result_str = "The information about the LLM in the [system config] is inaccurate"

    # llm_result_str = "저는 지금 대답할 수 없는 상태입니다."
    logger.info("generation (생성 종료)")
    await websocket.send_text("end_typewriter")
    await websocket.send_text("end_stream")
    logger.info("generation (통신 종료)")

    # stat["websocket"] = None        # output으로 돌려줄때, 직렬화에서 Error가 발생해서..
    return {"rag_answer": llm_result_str}


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):
    workflow.add_node("GET_REQUEST", node_get_request)
    workflow.add_node("RETRIEVE_CHUNK", node_retrieve_chunk)
    workflow.add_node("GET_DOCUMENT_LIST", node_get_doc_list)
    # workflow.add_node("GENERATE_ANSWER", node_generate)
    workflow.add_node("GENERATE_ANSWER", functools.partial(node_generate, websocket=websocket))
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
