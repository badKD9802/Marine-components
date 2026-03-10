import json
import base64
import logging
import uuid
import urllib.parse
from datetime import datetime

import requests

from app.tasks.lib_justtype.common import util
from app.tasks.lib_justtype.common.just_env import JustEnv
from app.tasks.lib_justtype.common.just_message import JustMessage, LangGraphState

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== JUST RPA ==")


class JustRPA:
    def __init__(self, stat: LangGraphState, job: str = "search_employee"):
        logger.debug("STEP 1")
        self.stat = stat
        self.dataset: str = ""
        self.rpa_id: str = ""
        self.result_code: int = -1
        self.result_msg: str = ""
        self.result_data: int = 0
        self.max_wait_time = 10
        self.sleep_interval = 1

        try:
            just_env = JustEnv(self.stat)
            rpa_config = just_env.get_config("rpa").get(job)
            if rpa_config is None:
                logger.warning(f"RPA config for job '{job}' not found. Using defaults.")
                return
            self.base_url = rpa_config.get("base_url", "http://172.16.4.147:8888/api/QueueAdd")
            self.company = rpa_config.get("company", "KAMCO")
            self.queue_name = rpa_config.get("queue_name", "AI 직원 실거 테스트")
            self.box_id = rpa_config.get("box_id", 54)
            self.box_version = rpa_config.get("box_version", 0)
            self.queue_group = rpa_config.get("queue_group", 0)
            self.con_api_code = rpa_config.get("con_api_code", "0111")
            self.max_wait_time = rpa_config.get("max_wait_time", 10)  # 최대 대기 시간 (초)
            self.sleep_interval = rpa_config.get("sleep_interval", 1)  # 루프 간 대기 시간 (초)
            drm_config = just_env.get_config("rpa").get("drm_decrypt")
            self.drm_base_url1: str = drm_config.get("base_url1", "http://172.16.4.121:8001/drm/decrypt")
            self.drm_base_url2: str = drm_config.get("base_url2", "http://172.16.4.122:8001/drm/decrypt")
            self.session = requests.Session()
            self.session.headers.update({"Content-Type": "application/json"})
        except Exception as e:
            logger.error(f"JustRPA 초기화 실패: {e}")

    def send_request(self, search_field: str, search_cond: str):
        if self.rpa_id != "":
            logger.error("req_id가 비어있지 않습니다. JustRPA를 다시 생성하세요.")
            return

        self.rpa_id = "RPA" + datetime.today().strftime("%m%d%S") + str(uuid.uuid4())[:8]

        dataset = f"searchField={search_field},searchCond={search_cond},rpa_id={self.rpa_id}"

        # 요청 데이터 구성
        request_data = {
            "Company": self.company,
            "QueueName": self.queue_name,
            "BoxId": self.box_id,
            "BoxVersion": self.box_version,
            "QueueGroup": self.queue_group,
            "DataSet": dataset,
        }

        # self.result_code = 1
        # return # 테스트를 위하여 통신은 SKIP한다.

        try:
            # POST 요청 전송
            response = self.session.post(self.base_url, json=request_data)

            # 응답 상태 코드 확인
            response.raise_for_status()

            # JSON 응답 파싱
            result = response.json()

            logger.debug("API 호출 성공:")
            logger.debug(f"URL: {self.base_url}")
            logger.debug(f"Request: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
            logger.debug(f"Response: {json.dumps(result, ensure_ascii=False, indent=2)}")

            self.result_code = result.get("code")
            self.result_msg = result.get("result")
            self.result_data = result.get("code")

        except requests.exceptions.RequestException as e:
            logger.debug(f"API 호출 중 오류 발생: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.debug(f"응답 상태 코드: {e.response.status_code}")
                logger.debug(f"응답 내용: {e.response.text}")

        except json.JSONDecodeError as e:
            logger.debug(f"JSON 파싱 오류: {e}")

    def encode_file_to_base64(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return encoded

    def encode_filename_to_url(self, file_path: str) -> str:
        encoded = urllib.parse.quote(file_path)
        return encoded

    def send_file(self, file_path: str):
        if self.rpa_id != "":
            logger.error("req_id가 비어있지 않습니다. JustRPA를 다시 생성하세요.")
            return

        self.rpa_id = "RPA" + datetime.today().strftime("%m%d%S") + str(uuid.uuid4())[:8]
        encoded_file = self.encode_file_to_base64(file_path)
        encoded_file_name = self.encode_filename_to_url(file_path)

        # dataset = f"searchField={search_field},searchCond={search_cond},rpa_id={self.rpa_id}"
        # conApiCode의 값 - 0001:PDF변환, 0010:DRM해제, 0011:DRM해제&PDF변환, 0111:DRM해제&PDF변환&BM적용
        dataset = (
            f"rpa_id={self.rpa_id},"
            f"filePath={encoded_file},"
            f"conApiCode={self.con_api_code},"          # 0111(DRM), 0001(pdf변환)
            f"fileName={encoded_file_name},"
            f"pathType=base64"
        )

        # 요청 데이터 구성
        request_data = {
            "Company": self.company,
            "QueueName": self.queue_name,
            "BoxId": self.box_id,
            "BoxVersion": self.box_version,
            "QueueGroup": self.queue_group,
            "DataSet": dataset,
        }

        # self.result_code = 1
        # return # 테스트를 위하여 통신은 SKIP한다.

        try:
            # POST 요청 전송
            response = self.session.post(self.base_url, json=request_data)

            # 응답 상태 코드 확인
            response.raise_for_status()

            # JSON 응답 파싱
            result = response.json()

            logger.debug("API 호출 성공:")
            logger.debug(f"URL: {self.base_url}")
            # logger.debug(f"RPA Request: >>>>>>>>>> \n{json.dumps(request_data, ensure_ascii=False, indent=2)}")
            # logger.debug(f"RPA Response: <<<<<<<<< \n{json.dumps(result, ensure_ascii=False, indent=2)}")
            logger.debug(f"RPA Request: >>>>>>>>>> QueyeName={self.queue_name}, conApiCode={self.con_api_code}")
            logger.debug(f"RPA Response: <<<<<<<<< \n{json.dumps(result, ensure_ascii=False, indent=2)}")

            self.result_code = result.get("code")
            self.result_msg = result.get("result")
            self.result_data = result.get("code")

        except requests.exceptions.RequestException as e:
            logger.debug(f"API 호출 중 오류 발생: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.debug(f"응답 상태 코드: {e.response.status_code}")
                logger.debug(f"응답 내용: {e.response.text}")

        except json.JSONDecodeError as e:
            logger.debug(f"JSON 파싱 오류: {e}")

    def receive_answer(self):
        just_msg = JustMessage(self.stat)
        content = just_msg.get_question()
        logger.debug(f"RPA로 부터 받은 응답: {content}")
        response_info = json.loads(content)
        self.rpa_id = response_info.get("rpa_id")
        self.result_code = 0

        return content

    def drm_decrypt(self, file_path: str) -> bool:
        # 요청 데이터 구성
        drm_file_path = file_path.replace("/home/upload/pdf", "/app/files/chatsam", 1)
        request_data = {
            "input_path": drm_file_path,
        }
        
        drm_urls = [
            self.drm_base_url1,
            self.drm_base_url2,
        ]

        for idx, drm_url in enumerate(drm_urls, start=1):
            try:
                logger.debug(f"[DRM 시도 {idx}] URL: {drm_url}")
                logger.debug(f"Request: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
                # POST 요청 전송
                response = self.session.post(drm_url, json=request_data, timeout=5)

                # 응답 상태 코드 확인
                response.raise_for_status()

                # JSON 응답 파싱
                result = response.json()

                logger.debug("DRM API 호출 성공:")
                logger.debug(f"Response: {json.dumps(result, ensure_ascii=False, indent=2)}")

                self.result_code = result.get("code")
                self.result_msg = result.get("message")
                
                return True

            except requests.exceptions.RequestException as e:
                logger.debug(f"DRM API 호출 중 오류 발생: {e}")
                
                continue

            except json.JSONDecodeError as e:
                logger.debug(f"JSON 파싱 오류: {e}")
                return False
            
        logger.debug("DRM API 호출 2 번 실패")
        return False
            
            