import asyncio
import logging
import os

from fastapi import WebSocket
from langgraph.graph import END, START
from pydantic.main import BaseModel

from app.db.database import db_connector

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustMessage, LangGraphState, service, util
from app.schemas.session import FileSchema, SessionSchema, SummarySchema
from app.tasks.lib_justtype.summary import parser_main, summary_main


class LocalSummaryInfo(BaseModel):
    summation_id: str
    file_name: str
    file_path: str
    work_dir: str
    log_dir: str
    parsing_dir: str
    result_dir: str


logger = util.TimeCheckLogger(logging.getLogger(__name__), "== DEFAULT_SUMMARY ==")


async def node_init(stat: LangGraphState):
    logger.info("NODE INIT : START")
    try:
        just = JustMessage(stat)
        sum_conf = just.get_config("summary")

        service_name = just.get_value("service_name")
        user_id = just.get_value("user_id")
        files: list[FileSchema] = just.get_files()
        res_data: SessionSchema = just.get_response_session()
        res_data.session_title = files[0].name  # session_title을 요약대상 파일명으로 바꾼다.
        service_info = just.get_service_info()
        logger.info(f"sum_conf:{sum_conf}")
        logger.info(f"service_name:{service_name}")
        logger.info(f"user_id:{user_id}")

        work_dir = sum_conf["working_dirs"]["work_dir"].replace("{service_dir}", service_name).replace("{user_id}", user_id)
        log_dir = sum_conf["working_dirs"]["log_dir"].replace("{service_dir}", service_name).replace("{user_id}", user_id)
        parsing_dir = sum_conf["working_dirs"]["parsing_dir"].replace("{service_dir}", service_name).replace("{user_id}", user_id)
        result_dir = sum_conf["working_dirs"]["result_dir"].replace("{service_dir}", service_name).replace("{user_id}", user_id)

        work_dir = os.path.join(service_info.settings.USER_PATH, work_dir)
        log_dir = os.path.join(service_info.settings.USER_PATH, log_dir)
        parsing_dir = os.path.join(service_info.settings.USER_PATH, parsing_dir)
        result_dir = os.path.join(service_info.settings.USER_PATH, result_dir)

        for directory in [work_dir, log_dir, parsing_dir, result_dir]:
            util.ensure_directory_exists(directory)

        summarize_info = LocalSummaryInfo(
            file_path=files[0].path,  # 요약 대상 파일 위치
            file_name=files[0].name,  # 요약 대상 파일명
            summation_id=res_data.session_id,  # 요약 id 명
            work_dir=work_dir,
            log_dir=log_dir,  # 작업 로그 폴더
            parsing_dir=parsing_dir,  # 작업 파징 폴더
            result_dir=result_dir,  # 작업 결과 폴더
        )

    except Exception as e:
        logger.error(f"Init Error: {e}")
        raise

    logger.info("NODE INIT : END")
    return_stat = LangGraphState(rag_code="succ", rag_answer="요약 시작 성공", custom_info=summarize_info)
    return return_stat


# ------------------------------------------------------------------------
# ChatGPT로 응답을 생성한다.
# ------------------------------------------------------------------------
async def node_insert_db(stat: LangGraphState):
    if stat["rag_code"] == "fail":  # 더 진행 필요없다.
        return
    just = JustMessage(stat)
    files = just.get_files()
    res_data = just.get_response_session()
    logger.info("NODE INSERT_DB : START")

    # just.append_answer(f"[{res_data.session_title}]에 대한 요약을 시작합니다.", 10, files=files)
    just.update_answer(f"[{res_data.session_title}]에 대한 요약을 시작합니다.", 10, files=files)
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
async def summary_background_thread(stat: LangGraphState, summarize_info: LocalSummaryInfo):
    just = JustMessage(stat)
    res_data: SessionSchema = just.get_response_session()
    config = just.get_config("summary")

    logger.info("=====================<< thread 진입 >>=====================")
    logger.info(f"summation_id: {summarize_info.summation_id}")
    logger.info(f"file_name: {summarize_info.file_name}")
    logger.info(f"file_path: {summarize_info.file_path}")
    logger.info(f"log_dir: {summarize_info.log_dir}")
    logger.info(f"parsing_dir: {summarize_info.parsing_dir}")
    logger.info(f"result_dir: {summarize_info.result_dir}")

    try:
        loop = asyncio.get_event_loop()
        # 문서 파싱
        text_output, error_ = await loop.run_in_executor(
            None,
            parser_main,
            summarize_info.file_path,
            summarize_info.summation_id,
            summarize_info.log_dir,
            summarize_info.parsing_dir,
        )

        # 에러 발생 시 raise
        if error_:
            raise ValueError(error_)

        # 요약과 RAG 병렬 처리
        summary_task = loop.run_in_executor(
            None,
            summary_main,
            text_output,
            summarize_info.file_name,
            summarize_info.summation_id,
            summarize_info.log_dir,
            summarize_info.result_dir,
            stat,
        )
        summary_list = await summary_task
        logger.info(f"data:\n{summary_list}")

    except Exception as e:
        logger.error(f"Error in background processing: {e}")
        last_message = service.get_last_message(res_data, "answer")
        last_message.percentage = -1
        summary_data = SummarySchema(
            result_order=-1, index_text="", start_page_text="", end_page_text="", content=f"요약에 실패했습니다. {e}"
        )
        last_message.summaries = [summary_data]
        res_data.percentage = -1
        service.update_message(res_data, last_message)

        scoped_session = db_connector.scoped_session()
        await service.save_session_data(scoped_session, res_data)  # 응답 보내기전에 전체 history를 db에 저장
        await scoped_session.commit()
        await scoped_session.close()

        raise


# ------------------------------------------------------------------------
# ChatGPT로 응답을 생성한다.
# ------------------------------------------------------------------------
async def node_sum(stat: LangGraphState):
    logger.info("NODE SUM : START")

    try:
        summarize_info: LocalSummaryInfo = stat["custom_info"]

        asyncio.create_task(summary_background_thread(stat, summarize_info))

    except Exception as e:
        logger.error(f"Error call thread: {e}")
        return {"rag_code": "fail", "rag_answer": f"요약 시작 실패[{e}]"}

    logger.info("NODE SUM : END")
    return {"rag_answer": "요약 시작 성공", "custom_info": summarize_info}


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("INIT_VAR", node_init)
    workflow.add_node("INSERT_DB", node_insert_db)
    workflow.add_node("DOCUMENT_SUMMARIZE", node_sum)

    workflow.add_edge(START, "INIT_VAR")
    workflow.add_edge("INIT_VAR", "INSERT_DB")
    workflow.add_edge("INSERT_DB", "DOCUMENT_SUMMARIZE")
    workflow.add_edge("DOCUMENT_SUMMARIZE", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
