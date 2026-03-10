import json
import logging

import requests
from fastapi import HTTPException, WebSocket
from langgraph.graph import END, START

# ==========================================================
# JUSTTYPE.RAG Library.
# ==========================================================
from app.justtype.rag import JustMessage, LangGraphState, util

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== ETL-PARSING ==")


async def node_etl_status(stat: LangGraphState):
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

    # 3. 파일 정보 조회 GET 요청 (POST 사용하지 않음)
    # curl 요청 예시:
    parsing_url = config_etl["status"]["url"]
    params = {"wsId": config_etl["parsing"]["ws_id"]}
    headers = {"accept": "application/json"}

    # 세션에 token 쿠키 설정 (이미 존재할 수 있으나 명시적으로 설정)
    session.cookies.set("token", token)

    try:
        file_info_response = session.get(parsing_url, headers=headers, params=params)
        file_info_response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=file_info_response.status_code if file_info_response else 500, detail=f"파일 정보 요청 오류: {str(e)}"
        ) from e

    # 4. 응답 내용 그대로 반환 (JSON 형식이면 JSON, 아니면 텍스트)
    try:
        parsed_response = file_info_response.json()
        if "result" in parsed_response and parsed_response["result"].get("code") != 0:
            error_msg = parsed_response["result"].get("message", "ETL 응답 오류")
            raise HTTPException(status_code=500, detail=f"ETL 응답 오류: {error_msg}")

        data_content = parsed_response.get("data", parsed_response)
        response_data = json.dumps(data_content, ensure_ascii=False)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"ETL의 응답에 예측값과 다릅니다. ({e})") from e

    just.append_answer(response_data)

    return_stat = LangGraphState(rag_code="succ", rag_answer="요약 시작 성공")
    return return_stat


# ------------------------------------------------------------------------
# DS에게 공개될 기능
# ------------------------------------------------------------------------
def build_workflow(workflow, websocket: WebSocket = None):

    workflow.add_node("ETL", node_etl_status)

    workflow.add_edge(START, "ETL")
    workflow.add_edge("ETL", END)


# ------------------------------------------------------------------------
# End of file
# ------------------------------------------------------------------------
