import json
import logging
import os

from app.schemas.langgraph_data import LangGraphState
from app.tasks.lib_justtype.common import util
from app.tasks.lib_justtype.common.just_db import JustSyncDB
from app.tasks.lib_justtype.common.just_env import JustEnv
from app.tasks.lib_justtype.common.just_message import JustMessage
from app.tasks.lib_justtype.summary.common.models import DataClient, load_model
from app.tasks.lib_justtype.summary.common.utils import check_runtime

from .data_structures import SummaryGroup
from .summarizer import DocumentSemanticGrouper, PageClassifier, PageFilter, Summarizer

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== SUMMARY_MAIN ==")


def data_converter(data, summation_id):
    """ "파싱된 데이터 재구조화"""
    try:
        doc_contents = data["contents"]
        document = {"summation_id": summation_id, "group_list": [{"depth": 0, "groups": {}}]}
        # 표 제외 / 텍스트만 추출
        first_group = document["group_list"][0]["groups"]
        for page, dct in doc_contents.items():
            for typ, text_list in dct.items():
                text_list = [t.replace("\n", " ").strip() for t in text_list]
                text_list = [t for t in text_list if t]
                if (typ == "text") and (text_list != []):
                    first_group[page] = SummaryGroup(
                        text="\n".join(text_list),
                        sentences=text_list,
                        page_labels=[page],
                    )
                else:
                    pass
        assert first_group != {}, "No document"
        return document

    except Exception as e:
        raise f"Error during loading data: {e}" from e


def save_results(document, output_path: str, summation_id: str):
    """ "결과 파일 저장"""
    output_file_path = os.path.join(output_path, f"{summation_id}.json")
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False, indent=4)


def save_results_final(just_db: JustSyncDB, session, document, output_path: str, file_name: str, just_msg: JustMessage):
    # 결과 파일 저장
    output_file_path = os.path.join(output_path, f"{file_name}.json")
    with open(output_file_path, "w", encoding="utf-8") as f:
        json.dump([item.model_dump() for item in document], f, ensure_ascii=False, indent=4)

    try:
        answer_message = just_msg.get_answer_message()
        answer_message.percentage = 100
        answer_message.summaries = document

        just_db.update_message(session)
    except Exception as e:
        logger.error(f"Error: {e}")


def summary_main(data, file_name, summation_id, log_dir, result_dir, stat: LangGraphState):
    just_msg = JustMessage(stat)
    just_env = JustEnv(stat)
    just_db = JustSyncDB(stat)
    config = just_env.get_config("summary")
    logger.info(f"Summarization processing: {file_name}")

    @check_runtime(logger)
    def _summary_main(session, data, file_name, summation_id, config):
        # json 파일로드
        full_document = data_converter(data, summation_id)
        logger.info("Parsing data conversion successfully.")

        # llm models load
        base_llm = load_model(config["rag_model"])
        tuned_llm = load_model(config["summary_model"])
        # embedding model load
        embedding_client = DataClient(config["embed_model"])
        just_db.update_percentage(session, 15)

        kargs = {"embedding_client": embedding_client, "logger": logger, "config": config["summary"]}
        # 목차와 참고문헌 분류
        page_clasifier = PageClassifier(base_llm, **kargs)
        # 사용하지 않는 페이지 필터링
        page_filter = PageFilter(tuned_llm, **kargs)
        # 유사도에 따라 그룹화
        page_grouper = DocumentSemanticGrouper(tuned_llm, **kargs)
        # 그룹 text 요약
        summarizer = Summarizer(tuned_llm, **kargs)

        # 각 페이지 타입 분류 및 필터링
        page_groups = full_document["group_list"][0]["groups"]
        page_clasifier.analyze_pages(page_groups)
        just_db.update_percentage(session, 69)
        page_filter.filter_summary_pages(page_groups)
        logger.info("Page filtering successfully.")

        # 페이지 그룹화(긴 문서라면 최대 3번까지 반복)
        summarizer.recursive_group_and_summarize(
            full_document,
            page_grouper,
        )
        logger.info("Group summaries generated successfully.")
        just_db.update_percentage(session, 83)

        # 최종 요약문 생성 및 변환
        summarizer.generate_final_summary(full_document, file_name=file_name)
        just_db.update_percentage(session, 96)
        logger.info("Final summary generated successfully.")

        # 결과 재구조화
        summary_list = summarizer.restructure_data(full_document)
        # TODO) 저장
        return summary_list, full_document

    try:
        with just_db as session:
            summary_list, full_document = _summary_main(session, data, file_name, summation_id, config)

            # 결과 저장
            save_results(full_document, result_dir, summation_id)
            save_results_final(just_db, session, summary_list, result_dir, f"[final]{file_name}", just_msg)
            logger.info(f"Results saved to {result_dir}")
            return summary_list

    except Exception as e:
        # session.rollback()  # 오류 발생 시 롤백
        logger.error(f"Summarization processing: {e}", exc_info=True)
        raise f"Summarization processing: {e}" from e
    finally:
        # session.close()  # 세션 종료
        # engine.dispose()  # 엔진 리소스 해제
        logger.info("Database connection closed.")
