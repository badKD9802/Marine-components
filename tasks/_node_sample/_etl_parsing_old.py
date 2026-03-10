import glob
import json
import logging
import os

import requests
from fastapi import HTTPException, WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustMessage, LangGraphState, util

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== ETL-PARSING ==")


async def node_etl_parsing(stat: LangGraphState):
    logger.info("NODE INIT : START")
    just = JustMessage(stat)
    config_etl = just.get_config("etl")

    login_url = config_etl["login"]["url"]
    login_headers = {"accept": "application/json", "Content-Type": "application/json"}
    login_payload = {"user_id": config_etl["login"]["user_id"], "user_pw": config_etl["login"]["user_pw"]}

    session = requests.Session()
    try:
        login_response = session.post(login_url, headers=login_headers, json=login_payload)
        login_response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=login_response.status_code if login_response else 500, detail=f"로그인 API 호출 오류: {str(e)}"
        ) from e

    # 2. 응답 쿠키에서 token 추출
    token = login_response.cookies.get("token")
    if not token:
        raise HTTPException(status_code=500, detail="로그인 응답에서 token을 찾을 수 없습니다.")

    # token을 쿠키에 추가
    session.cookies.set("token", token)

    # 3. 실제 파일 전송을 포함한 parsing요청
    parsing_url = config_etl["parsing"]["url"]
    parsing_config = config_etl["parsing"]

    folder_path = config_etl["document"]["folder_path"]
    file_pattern = config_etl["document"]["file_pattern"]
    files_path = os.path.join(folder_path, file_pattern)

    # 전체 결과를 저장할 딕셔너리
    results = {}
    try:
        # 폴더 내의 모든 파일 목록 가져오기
        pdf_files = glob.glob(files_path)
        if not pdf_files:
            raise HTTPException(status_code=404, detail=f"[{folder_path}]에 파일이 없습니다.")

        for full_path in pdf_files:
            # full_path = os.path.join(folder_path, pdf_file)
            file_name = os.path.basename(full_path)  # 현재 Kamco에서 발생한 Error에 대한 처리.
            try:
                # 파일 열기
                with open(full_path, "rb") as file_to_upload:
                    logger.info(json.dumps(parsing_config))
                    files = [
                        ("tr_data", (None, json.dumps(parsing_config), "application/json")),
                        ("upfiles", (file_name, file_to_upload, "application/pdf")),  # pdf가 아닌경우, 대응코드 없음. HHHHHHHHHHH
                    ]

                    # API 요청
                    response = session.post(parsing_url, files=files)
                    response.raise_for_status()

                    # 응답 처리
                    try:
                        parsed_response = response.json()
                        if "result" in parsed_response and parsed_response["result"].get("code") != 0:
                            error_msg = parsed_response["result"].get("message", "ETL 응답 오류")
                            results[full_path] = {"error": f"ETL 응답 오류: {error_msg}"}
                        else:
                            data_content = parsed_response.get("data", parsed_response)
                            results[full_path] = data_content
                    except ValueError as e:
                        results[full_path] = {"error": f"ETL의 응답에 예측값과 다릅니다. ({e})"}

            except Exception as e:
                results[full_path] = {"error": f"파일 처리 중 오류 발생: {str(e)}"}  # 나머지 파일들은 계속 돈다.

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"폴더 처리 중 오류 발생: {str(e)}") from e

    just.append_answer(str(results))

    return_stat = LangGraphState(rag_code="succ", rag_answer="요약 시작 성공")
    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("ETL", node_etl_parsing)

    workflow.add_edge(START, "ETL")
    workflow.add_edge("ETL", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
