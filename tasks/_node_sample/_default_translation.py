import asyncio
import json
import logging
import time

from fastapi import HTTPException, WebSocket
from langgraph.graph import END, START

from app.db.database import db_connector

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustLLM, JustMessage, LangGraphState, service, util
from app.schemas.session import FileSchema, SessionSchema, SummarySchema
from app.tasks.lib_justtype.etl.just_etl import JustETL

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== DEFAULT_TRANSLATE ==")
prompt_template = """
    당신의 임무는 {FROM_LANG}언어의 청크를 {TO_LANG}의 언어로 번역 하는 것 입니다. 
    각 청크는 <chunk> 태그로 묶여 있으며 인덱스와 파일명 등 다양한 메타데이터를 포함합니다.
    메타 데이터도 그대로 번역합니다.

    ## 청크
    <chunks>
    {DOCUMENT}
    </chunks>

    ## 지침
    1. 번역 청크의 내용이 이미 번역 대상 언어인 경우는 원문을 그대로 보여 줍니다. 
    2. 제공된 청크의 내용만 번역 합니다.
    3. 제공된 청크에 없는 정보를 가정하거나 추가하지 마세요.
    4. 표나 차트의 값을 다룰 때 단위에 주의를 기울이세요.
    5. 번역한 내용만 보여주세요.
    6. 즉, <chunk>를 보여주면 안 됩니다.

    ## 위 지침을 바탕으로 번역해주세요.
"""


# ------------------------------------------------------------------------
# ChatGPT로 응답을 생성한다.
# ------------------------------------------------------------------------
async def node_init_db(stat: LangGraphState):
    logger.info("NODE INSERT_DB : START")

    just = JustMessage(stat)
    files = just.get_files()
    res_data = just.get_response_session()

    res_data.session_title = f"[{files[0].name}]의 번역"  # 번역 제목을 파일명으로 정한다.
    just.update_answer(f"[{files[0].name}]에 대한 번역을 시작합니다.", 10, files=files)

    scoped_session = db_connector.scoped_session()
    await service.save_session_data(scoped_session, res_data)  # 응답 보내기전에 전체 history를 db에 저장
    await scoped_session.commit()
    await scoped_session.close()

    return_stat = LangGraphState(rag_code="succ")

    logger.info("NODE INSERT_DB : END")
    return return_stat


# ------------------------------------------------------------------------
# thread로 parsing과 요약을 병렬로 처리하면서 Client에게 바로 응답을 보낸다.
# ------------------------------------------------------------------------
async def translate_background_thread(stat: LangGraphState):
    just = JustMessage(stat)
    just_llm = JustLLM(stat, is_stream=False)
    res_data: SessionSchema = just.get_response_session()

    # 여러개의 file을 upload해도, 맨 앞의 하나만 번역한다.
    files: list[FileSchema] = just.get_files()

    just_etl = JustETL(stat)
    scoped_session = db_connector.scoped_session()
    try:
        #
        # id별로 etl_workspace를 생성해야 한다. (kamco에서는 그래야 한다)
        # 일단 회사 etl(155번)과 연동하는 코드이므로 kmaco로 workspace를 지정하고, WS번호를 config에 넣었다.
        # >>> 생성된 WorkSpace ID는 db에 따로 저장해야 한다. (SSO할때 고민해야 한다) = 일단, kamco로 한다.
        #
        await just_etl.login()

        #
        # etl과 통신으로 Parsing을 수행한다.
        #
        await just_etl.parsing(files[0].path)

        #
        # etl과 parsing을 요청했으니 끝날때까지 기다린다.
        # 단, timeout_seconds만큼만 기다린다.
        #
        timeout_seconds = just_etl.etl_config["status"]["timeout_seconds"]
        poll_interval = just_etl.etl_config["status"]["polling_interval"]
        start_time = time.time()
        while True:
            chunk_status = await just_etl.status(files[0].path)
            if chunk_status == "002":  # "000": 준비, "001": 작업중, "002": 완료.
                break

            if chunk_status in ["997", "998", "999"]:  # 999: 분석 오류, 998: 업로드 오류, 997: 파일 이동 오류
                raise HTTPException(status_code=500, detail=f"ETL 연동 처리 중 오류 발생: etl code=[{chunk_status}]")

            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise HTTPException(status_code=504, detail=f"ETL 대기 시간 초과 ({timeout_seconds}초)")

            await asyncio.sleep(poll_interval)
        #
        # etl과 통신으로 page별 데이터를 가져 와야 한다.
        #
        json_datas = await just_etl.get_json_pages(files[0].path)

        #
        # page별로 looping을 돌면서 번역을 하자.
        #
        trans_lang = json.loads(just.get_question())  # 질문 형식: "{\"from\":\"영어\", \"to\":\"한국어\"}"
        summary_data_list = []
        total_pages = len(json_datas)
        for idx, (page_number, page_content) in enumerate(json_datas.items()):
            # 매 페이지 마다 번역을 한다.
            prompt_str = prompt_template.replace("{FROM_LANG}", trans_lang["from"])
            prompt_str = prompt_str.replace("{TO_LANG}", trans_lang["to"])
            prompt_str = prompt_str.replace("{DOCUMENT}", page_content)
            logger.info(f"node_generate prompt: \n{prompt_str}")

            send_message = await just_llm.make_send_msg(prompt_str)
            response_message = await just_llm.get_response(send_message)

            summary_data = SummarySchema(
                result_order=int(page_number),
                index_text="",
                start_page_text=page_number,
                end_page_text=page_number,
                content=response_message,
            )
            summary_data_list.append(summary_data)
            percentage = int(f"{round((idx + 1) / total_pages * 100)}")
            just.update_answer(f"[{percentage}%]번역했습니다.", percentage=percentage, summaries=summary_data_list)
            await service.save_session_data(scoped_session, res_data)  # 응답 보내기전에 전체 history를 db에 저장
            await scoped_session.commit()

    except Exception as e:
        just.update_answer(f"번역에 실패 했습니다.[{e}]", -1)
        await service.save_session_data(scoped_session, res_data)  # 응답 보내기전에 전체 history를 db에 저장
        await scoped_session.commit()

        raise
    finally:
        await scoped_session.close()


# ------------------------------------------------------------------------
# ChatGPT로 응답을 생성한다.
# ------------------------------------------------------------------------
async def node_trans(stat: LangGraphState):
    logger.info("NODE TRANSLATE : START")

    try:
        asyncio.create_task(translate_background_thread(stat))

    except Exception as e:
        logger.error(f"Error call thread: {e}")
        return {"rag_code": "fail", "rag_answer": f"요약 시작 실패[{e}]"}

    logger.info("NODE TRANSLATE : END")
    return {"rag_answer": "번역 시작 성공"}


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("INIT_DB", node_init_db)
    workflow.add_node("TRANSLATE", node_trans)

    workflow.add_edge(START, "INIT_DB")
    workflow.add_edge("INIT_DB", "TRANSLATE")
    workflow.add_edge("TRANSLATE", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
