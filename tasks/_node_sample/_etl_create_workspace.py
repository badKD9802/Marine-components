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

    # 3. 2번 API 호출 (파일 전송 포함)
    # second_api_url = "http://192.168.100.170/api/v1/etl/auto/start"
    # 3. 파일 정보 조회 GET 요청 (POST 사용하지 않음)
    # curl 요청 예시:
    workspace_url = config_etl["workspace"]["url"]
    headers = {"Content-Type": "application/json", "accept": "application/json"}
    payload = {
        "workspace_name": config_etl["workspace"]["name"],
        "description": config_etl["workspace"]["description"],
        "access_level": config_etl["workspace"]["access_level"],
        "created_by": config_etl["workspace"]["created_by"],
    }

    # 세션에 token 쿠키 설정 (이미 존재할 수 있으나 명시적으로 설정)
    session.cookies.set("token", token)

    try:
        response = session.post(workspace_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=response.status_code if response else 500, detail=f"워크스페이스 생성 요청 오류: {str(e)}") from e

    # 4. 응답 내용 그대로 반환 (JSON 형식이면 JSON, 아니면 텍스트)
    try:
        parsed_response = response.json()
        if "result" in parsed_response and parsed_response["result"].get("code") != 0:
            error_msg = parsed_response["result"].get("message", "ETL 응답 오류")
            raise HTTPException(status_code=500, detail=f"ETL 응답 오류: {error_msg}")

        data_content = parsed_response.get("data", parsed_response)
        response_data = json.dumps(data_content, ensure_ascii=False)
        logger.info(str(data_content))
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"ETL의 응답에 예측값과 다릅니다. ({e})") from e

    just.append_answer(response_data)

    return_stat = LangGraphState(rag_code="succ", rag_answer="WS생성 성공")
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
