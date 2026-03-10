import glob
import json
import logging
import os
import asyncio
import re

import requests
from PIL import Image
from app.justtype import service
from app.schemas.agent import AgentQueueSchema
from app.db.database import db_connector

from app.tasks.lib_justtype.common.just_env import JustEnv, LangGraphState
from app.tasks.lib_justtype.common.just_message import JustMessage
from app.tasks.lib_justtype.etl.chatsam_structure_maker import ChatsamStructureMaker
from app.tasks.lib_justtype.rpa.just_rpa import JustRPA

logger = logging.getLogger(__name__)

### 테이블내 이미지, 테이블 정보 처리
def merge_tables_page(page):
    paragraphs = page["paragraphs"]
    id_to_contents = {int(p["paragraphId"]): p["contents"] for p in paragraphs}

    # childId 기준으로 inline 대상 수집
    inlined_ids = set()
    for p in paragraphs:
        for cid in p.get("childId", []):
            try:
                inlined_ids.add(int(cid))
            except ValueError:
                pass
    # add_table 치환
    def repl(m):
        target_id = int(m.group(1))
        return id_to_contents.get(target_id, "")
        
    pattern_table = r"\[add_table\]\s*(\d+)\s*\[/add_table\]"
    for p in paragraphs:
        p["contents"] = re.sub(pattern_table, repl, p["contents"], flags=re.DOTALL)

    pattern_equation = r"\[add_equation\]\s*(\d+)\s*\[/add_equation\]"
    for p in paragraphs:
        p["contents"] = re.sub(pattern_equation, repl, p["contents"], flags=re.DOTALL)

    pattern_figure = r"\[add_figure\]\s*(\d+)\s*\[/add_figure\]"
    for p in paragraphs:
        p["contents"] = re.sub(pattern_figure, repl, p["contents"], flags=re.DOTALL)

    # inline된 paragraphId는 결과에서 제거
    results = []
    for p in paragraphs:
        pid = int(p["paragraphId"])
        if pid in inlined_ids:
            continue
        results.append({"contents": p["contents"]})
    return results
    
def ocr_add_info(updated_ocr_data):
    logger.info(" 진입 ")
    page_grouped = []
    
    for page in updated_ocr_data['pages']:
        page_id = page['pageId']
        
        # 컨텐츠 추출
        contents = merge_tables_page(page) # Table in Table 처리
        content_list = [s['contents'] for s in contents]
        
        # 빈 페이지 스킵
        if not contents:
            continue
                    
        # 일반 페이지 컨텐츠
        page_content = {'page': page_id, 'contents': content_list}
        page_grouped.append(page_content)

    return page_grouped        
####

class JustETL:
    def __init__(self, stat: LangGraphState):
        self.stat = stat
        self.just_env = JustEnv(stat)
        self.just_msg = JustMessage(stat)
        self.etl_config = self.just_env.get_config("etl")
        self.session = None
        self.json_data = None

    def get_config(self):
        if self.etl_config is None:
            self.etl_config = self.just_env.get_config("etl")
            if self.etl_config is None:
                logger.error(f"config(etl) is exist in service_name[{self.just_env.get_value('service_name')}]")
                raise Exception(f"config(etl) is exist in service_name[{self.just_env.get_value('service_name')}]")

    async def trans_file_rpa(self, job_type, file_path):
        # 1. config 값을 check한다.
        if job_type == "summary":
            if self.etl_config["use_rpa"]["summary"] != "True":
                return "_SKIP"
        elif job_type == "translate":
            if self.etl_config["use_rpa"]["translate"] != "True":
                return "_SKIP"
        elif job_type == "ocr":
            if self.etl_config["use_rpa"]["ocr"] != "True":
                return "_SKIP"
        elif job_type == "pdf_trans":
            if self.etl_config["use_rpa"]["pdf_trans"] != "True":
                return "_SKIP"                
        else:
            return "_SKIP"

        # 2. config 값을 check한다.
        if job_type == "pdf_trans":
            just_rpa = JustRPA(self.stat, "pdf_trans")
        else:            
            just_rpa = JustRPA(self.stat, "file_trans")

        # 1. RPA와 통신
        logger.debug("JustETL_trans_file_rpa: 1. RPA와 통신:")
        # just_rpa.drm_decrypt(file_path)
        just_rpa.send_file(file_path)
        logger.debug(f"결과1: rpa_id: {just_rpa.rpa_id}")

        # 2. 기본 설정으로 API 호출
        logger.debug("JustETL_trans_file_rpa: 2. RPA결과를 DB에 넣고 대기중.")
        queue_info = AgentQueueSchema(queue_id=just_rpa.rpa_id)
        if just_rpa.result_code > 0:    # send_request성공.
            logger.debug(f"JustETL_trans_file_rpa: 3. 결과: {just_rpa.result_code}\n")

            scoped_session = db_connector.scoped_session()
            await service.add_queue_data(scoped_session, just_rpa.rpa_id)  # 응답 보내기전에 전체 rpa request를 db에 저장
            await scoped_session.commit()
            elapsed_time = 0.0

            # 3. 응답이 올때까지 just_rpa.max_wait_time까지만 기다린다.
            new_file_path = "_MAX_WAIT_TIME_OVER"
            while True:
                await asyncio.sleep(just_rpa.sleep_interval)
                elapsed_time += just_rpa.sleep_interval

                queue_info = await service.get_queue_data(scoped_session, just_rpa.rpa_id)  # POOLING..
                logger.debug(f"queue의 db 내용: {queue_info}\n")    # <== 결과 파일명. (즉, pdf겠지?)

                if queue_info.data_dump and len(queue_info.data_dump) > 0:
                    new_file_path = queue_info.data_dump
                    break

                if elapsed_time >= just_rpa.max_wait_time:
                    logger.warning(f"최대 대기 시간 {just_rpa.max_wait_time}초 초과. 종료합니다.")
                    break

            await scoped_session.commit()
            await scoped_session.close()

            # 4. 응답 못 받았으면 None이 날라가고, 아니면 file_path가 날라간다.
            return new_file_path
        else:
            return "_FAIL"
    
    async def login(self, user_id=None, user_pw=None, job="몰라"):
        logger.info(f"EWL({job}) LOGIN START")
        self.get_config()
        login_url = self.etl_config["login"]["url"]
        login_headers = {"accept": "application/json", "Content-Type": "application/json"}
        if user_id and user_pw:
            login_payload = {"user_id": user_id, "user_pw": user_pw}
        else:
            login_payload = {"user_id": self.etl_config["login"]["user_id"], "user_pw": self.etl_config["login"]["user_pw"]}

        self.session = requests.Session()
        try:
            login_response = self.session.post(login_url, headers=login_headers, json=login_payload)
            login_response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"ETL API LOGIN 오류: {str(e)}")
            raise Exception(f"ETL API LOGIN 오류: {str(e)}") from e

        # 2. 응답 쿠키에서 token 추출
        token = login_response.cookies.get("token")
        if not token:
            logger.error("로그인 응답에서 token을 찾을 수 없습니다.")
            raise Exception("로그인 응답에서 token을 찾을 수 없습니다.")

        # token을 쿠키에 추가
        self.session.cookies.set("token", token)
        logger.info(f"EWL({job}) LOGIN END")

    async def delete (self, retention_period: int = 14):
        logger.info(f"DELETE retention_period={retention_period}")
        self.get_config()
        ws_id = self.etl_config["parsing"]["ws_id"]
        delete_url = self.etl_config["delete"]["url"]
        delete_headers = {"accept": "application/json", "Content-Type": "application/json"}
        delete_payload = {"ws_id": ws_id, "before_days": retention_period}
        logger.info(f"1. ws_id={ws_id}")
        logger.info(f"2. delete_url={delete_url}")
        logger.info(f"3. delete_headers={delete_headers}")
        logger.info(f"4. delete_payload={delete_payload}")
        self.session = requests.Session()
        try:
            login_response = self.session.post(delete_url, headers=delete_headers, json=delete_payload)
            login_response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"ETL API DELETE 오류: {str(e)}")
            raise Exception(f"ETL API DELETE 오류: {str(e)}") from e

        logger.info(f"EWL DELETE END")

    async def parsing(self, file_path=None, job="몰라"):
        logger.info(f"EWL({job}) PARSING START")
        # 파일 전송을 포함한 parsing요청
        self.get_config()
        parsing_url = self.etl_config["parsing"]["url"]
        parsing_config = self.etl_config["parsing"]

        if file_path is None:
            folder_path = self.etl_config["document"]["folder_path"]
            file_pattern = self.etl_config["document"]["file_pattern"]
            files_path = os.path.join(folder_path, file_pattern)
            pdf_files = glob.glob(files_path)
            if not pdf_files:
                logger.error(f"[{folder_path}]에 파일이 없습니다.")
                raise Exception(f"[{folder_path}]에 파일이 없습니다.")
        else:
            if isinstance(file_path, str):
                pdf_files = [file_path]
            else:
                logger.error(f"ETL 대상 문서를 찾을 수 없습니다: {str(file_path)}")
                raise Exception(f"ETL 대상 문서를 찾을 수 없습니다: {str(file_path)}")

        # 전체 결과를 저장할 딕셔너리
        results = {}
        try:
            # 폴더 내의 모든 파일 목록 가져오기
            for full_path in pdf_files:
                file_name = os.path.basename(full_path)
                try:
                    # 파일 열기
                    with open(full_path, "rb") as file_to_upload:
                        logger.info(json.dumps(parsing_config))
                        files = [
                            ("tr_data", (None, json.dumps(parsing_config), "application/json")),
                            ("upfiles", (file_name, file_to_upload, "application/pdf")),  # pdf가 아닌경우, 대응코드 없음.
                        ]

                        # API 요청
                        response = self.session.post(parsing_url, files=files)
                        response.raise_for_status()

                        # 응답 처리
                        try:
                            parsed_response = response.json()
                            if "result" in parsed_response and parsed_response["result"].get("code") != 0:
                                error_msg = parsed_response["result"].get("message", "ETL 응답 오류")
                                results[full_path] = {"error": f"ETL 응답 오류: {error_msg}"}
                                return parsed_response["result"].get("code")
                            else:
                                data_content = parsed_response.get("data", parsed_response)
                                results[full_path] = data_content
                        except ValueError as e:
                            logger.error(f"ETL의 응답에 예측값과 다릅니다. ({e})")
                            results[full_path] = {"error": f"ETL의 응답에 예측값과 다릅니다. ({e})"}
                            return -1
                            # raise

                except Exception as e:
                    logger.error(f"ETL의 응답 에러: 그래도 다음 파일 진행 ({e})")
                    results[full_path] = {"error": f"파일 처리 중 오류 발생: {str(e)}"}  # 나머지 파일들은 계속 돈다.
                    return -1

        except Exception as e:
            logger.error(f"폴더 처리 중 오류 발생: {str(e)}")
            raise Exception(f"폴더 처리 중 오류 발생: {str(e)}") from e

        self.just_msg.update_answer(f"문서에서 내용 추출을 완료했습니다.", 15)
        logger.info(f"EWL({job}) PARSING END")
        return 0

    async def status(self, file_path=None, job="몰라"):
        self.get_config()
        status_url = self.etl_config["status"]["url"]
        headers = {"accept": "application/json", "Content-Type": "application/json"}

        # folder_path = self.etl_config["document"]["folder_path"]
        try:
            file_path = file_path.replace(" ", "_").replace(",", "_").replace("+", "_")
            file_name = os.path.basename(file_path)
            base_name, _ = os.path.splitext(file_name)
            # http://192.168.100.170/api/vl/file/info?file_path=test_document_0320.pdf/vl/test_document_0320.pdf
            params = {"file_path": f"{file_name}/vl/{file_name}"}  # 가장 큰 것으로 가져올 수 없나?
            logger.debug(f"EWL({job}) STATUS : params=[{params}]")
            response = self.session.get(status_url, headers=headers, params=params)
            response.raise_for_status()
            # json_files_path = os.path.join(folder_path, f"{base_name}.json")

            # 응답 처리
            parsed_response = response.json()

            # with open(json_files_path, "w", encoding="utf-8") as f:
            #     json.dump(parsed_response, f, ensure_ascii=False, indent=2)
            if "result" in parsed_response and parsed_response["result"].get("code") != 0:
                error_msg = parsed_response["result"].get("message", "ETL 응답 오류")
                logger.error(f"ETL 연동  처리 중 오류 발생: {error_msg}")
                raise Exception(f"ETL 연동  처리 중 오류 발생: {error_msg}")
            else:
                # with open(json_files_path, "r", encoding="utf-8") as f:
                #     self.json_data = json.load(f)
                self.json_data = parsed_response
                chunk_status = parsed_response["data"]["datasource"][0]["chunk_status"]
                if chunk_status in ["000", "001", "002"]:
                    return chunk_status
                else:
                    logger.error(f"ETL의 처리 오류: error_code {chunk_status}")
                    raise Exception(f"ETL의 처리 오류: error_code {chunk_status}")

        except Exception as e:
            logger.error(f"ETL 연동  처리 중 오류 발생: {str(e)}")
            raise Exception(f"ETL 연동  처리 중 오류 발생: {str(e)}") from e

    #### summary ####
    async def summary_status(self, file_path=None, job="몰라"):
        self.get_config()
        status_url = self.etl_config["status"]["url"]
        headers = {"accept": "application/json", "Content-Type": "application/json"}

        # folder_path = self.etl_config["document"]["folder_path"]
        try:
            file_path = file_path.replace(" ", "_").replace(",", "_").replace("+", "_")
            file_name = os.path.basename(file_path)
            base_name, _ = os.path.splitext(file_name)
            # http://192.168.100.170/api/vl/file/info?file_path=test_document_0320.pdf/vl/test_document_0320.pdf
            params = {"file_path": f"{file_name}/vl/{file_name}"}  # 가장 큰 것으로 가져올 수 없나?
            logger.debug(f"EWL({job}) STATUS : params=[{params}]")
            response = self.session.get(status_url, headers=headers, params=params)
            response.raise_for_status()
            # json_files_path = os.path.join(folder_path, f"{base_name}.json")

            # 파일 길이 테스트
            # if len(file_name) > 50:
            #     logger.debug(f" 업로드한 파일명 이름 길이 {file_name}")
            #     raise Exception(f"업로드하신 파일명의 이름의 길이를 줄여서 업로드 해주세요.")
            
            # 응답 처리
            parsed_response = response.json()

            # with open(json_files_path, "w", encoding="utf-8") as f:
            #     json.dump(parsed_response, f, ensure_ascii=False, indent=2)
            if "result" in parsed_response and parsed_response["result"].get("code") != 0:
                error_msg = parsed_response["result"].get("message", "ETL 응답 오류")
                logger.error(f"ETL 연동  처리 중 오류 발생: {error_msg}")
            else:
                # with open(json_files_path, "r", encoding="utf-8") as f:
                #     self.json_data = json.load(f)
                self.json_data = parsed_response
                chunk_status = parsed_response["data"]["datasource"][0]["chunk_status"]
                if chunk_status in ["000", "001", "002"]:
                    return chunk_status
                else:
                    chunk_status = parsed_response["data"]["datasource"][0]["chunk_status"]
                    logger.error(f"ETL의 처리 오류: error_code {chunk_status}")
                return chunk_status

        except Exception as e:
            chunk_status = parsed_response["data"]["datasource"][0]["chunk_status"]
            logger.error(f"ETL 연동  처리 중 오류 발생: {str(e)}")
            return chunk_status

        # return self.json_data

    async def get_json_pages(self, file_path: str = None, get_type="json", job="몰라"):
        logger.info(f"EWL({job}) GET JSON START")
        self.get_config()
        chunking_url = self.etl_config["chunking"]["url"]
        headers = {"accept": "application/json", "Content-Type": "application/json"}

        if file_path is None:  # 현재 이런 경우가 없다. 심지어 document라는 config도 없다
            folder_path = self.etl_config["document"]["folder_path"]
            file_pattern = self.etl_config["document"]["file_pattern"]
            files_path = os.path.join(folder_path, file_pattern)
            pdf_files = glob.glob(files_path)
            if not pdf_files:
                logger.error(f"[{folder_path}]에 파일이 없습니다.")
                raise Exception(f"[{folder_path}]에 파일이 없습니다.")
        else:
            folder_path = os.path.dirname(file_path)
            if isinstance(file_path, str):
                pdf_files = [file_path]
            else:
                logger.error(f"ETL 대상 문서를 찾을 수 없습니다: {str(file_path)}")
                raise Exception(f"ETL 대상 문서를 찾을 수 없습니다: {str(file_path)}")

        get_type = "json"   # 일본어 이미지 처리를 위한 base64 인코딩에 적합한 format으로 강제 지정.

        if get_type == "pages":
            get_str = "_pages.json"
        elif get_type == "json":
            get_str = ".json"
        else:
            get_str = "_page_grouped.json"
            
        try:
            for full_path in pdf_files:
                # ------------------------------------------------------
                #  파일 path, 파일명등 가져오기.
                # ------------------------------------------------------
                dir_name = os.path.dirname(full_path)
                logger.debug(f"dir_name = {dir_name}]")
                base_name = os.path.basename(full_path)
                logger.debug(f"base_name = {base_name}]")
                file_name, ext_name = os.path.splitext(base_name)
                logger.debug(f"file_name = {file_name}]")
                logger.debug(f"ext_name = {ext_name}]")
                ext_name = ext_name.lower()     # 대문자 확장자도 처리한다.
                etl_file_name = file_name.replace(" ", "_").replace(",", "_").replace("+", "_")

                # ------------------------------------------------------
                #  parsing의 결과물에서 pdf파일 만들기.. (image는 별도 생성)
                # ------------------------------------------------------
                logger.debug(f"ext_name = {ext_name}]")
                if ext_name in [".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"]:
                    image = Image.open(f"{full_path}")
                    rgb_image = image.convert("RGB")  # PDF는 RGB 모드만 지원
                    rgb_image.save(f"{dir_name}/{etl_file_name}.pdf", "PDF", resolution=100.0)
                    logger.debug(f"이미지 변환 {ext_name}를 >>>> PDF File로 변환 : file_path=[{dir_name}/{etl_file_name}.pdf]")

                elif ext_name != ".pdf":
                    params = {"docResultPath": f"{etl_file_name}{ext_name}/vl/{etl_file_name}.pdf"}  # 가장 큰 것으로 가져올 수 없나?
                    logger.debug(f"{ext_name}를 >>>> PDF File로 변환 : params=[{params}]")

                    response = self.session.get(chunking_url, headers=headers, params=params)
                    response.raise_for_status()
                    pdf_files_path = os.path.join(folder_path, f"{etl_file_name}.pdf")

                    # 응답 처리
                    try:
                        with open(pdf_files_path, "wb") as f:
                            f.write(response.content)
                    except ValueError as e:
                        logger.error(f"(PDF생성) ETL의 응답에 예측값과 다릅니다. 작업진행({e})")
                        raise

                # ------------------------------------------------------
                #  parsing의 결과물을 통신으로 요청하고 응답 받기.
                # ------------------------------------------------------
                params = {"docResultPath": f"{etl_file_name}{ext_name}/vl/{etl_file_name}{get_str}"}
                logger.debug(f"get_json_pages : params=[{params}]")
                response = self.session.get(chunking_url, headers=headers, params=params)
                response.raise_for_status()
                try:
                    parsed_response = response.json()
                    json_files_path = os.path.join(folder_path, f"{etl_file_name}.json")
                    with open(json_files_path, "w", encoding="utf-8") as f:
                        json.dump(parsed_response, f, ensure_ascii=False, indent=2)
                    if "result" in parsed_response and parsed_response["result"].get("code") != 0:
                        error_msg = parsed_response["result"].get("message", "ETL 응답 오류")
                        raise Exception(f"ETL 연동  처리 중 오류 발생: {error_msg}")
                    else:
                        with open(json_files_path, encoding="utf-8") as f:
                            json_data = ocr_add_info(json.load(f))
                            self.json_data = json_data # json.load(f)
                        # self.json_data = parsed_response
                except ValueError as e:
                    logger.error(f"(json생성) ETL의 응답에 예측값과 다릅니다. 작업진행({e})")
                    self.json_data = {"error": f"(json생성) ETL의 응답에 예측값과 다릅니다. ({e})"}
                    raise

        except Exception as e:
            logger.error(f"ETL 연동  처리 중 오류 발생: {str(e)}")
            raise Exception(f"ETL 연동  처리 중 오류 발생: {str(e)}") from e

        logger.info(f"EWL({job}) GET JSON END")
        return self.json_data

    async def get_json_to_csv(self, file_path=None):
        self.get_config()
        config_chunk = self.just_env.get_config("chunking")  # csv로 만들기 위해서 사용함.
        chunking_url = self.etl_config["chunking"]["url"]
        headers = {"accept": "application/json", "Content-Type": "application/json"}

        if file_path is None:
            folder_path = self.etl_config["document"]["folder_path"]
            file_pattern = self.etl_config["document"]["file_pattern"]
            files_path = os.path.join(folder_path, file_pattern)
            pdf_files = glob.glob(files_path)
            if not pdf_files:
                logger.error(f"[{folder_path}]에 파일이 없습니다.")
                raise Exception(f"[{folder_path}]에 파일이 없습니다.")
        else:
            if isinstance(file_path, str):
                pdf_files = [file_path]
                folder_path = os.path.dirname(file_path)
            else:
                logger.error(f"ETL 대상 문서를 찾을 수 없습니다: {str(file_path)}")
                raise Exception(f"ETL 대상 문서를 찾을 수 없습니다: {str(file_path)}")

        try:
            for full_path in pdf_files:
                full_path = full_path.replace(" ", "_").replace(",", "_").replace("+", "_")
                logger.info(f"==ETL_GET_JSON_TO_CSV==1 [{full_path}]")
                file_name = os.path.basename(full_path)
                base_name, _ = os.path.splitext(file_name)
                params = {"docResultPath": f"{base_name}.pdf/vl/{base_name}.json"}  # 가장 큰 것으로 가져올 수 없나?
                logger.info(f"==ETL_GET_JSON_TO_CSV==2 {params}")
                response = self.session.get(chunking_url, headers=headers, params=params)
                logger.info(f"==ETL_GET_JSON_TO_CSV==3 {response}")
                response.raise_for_status()

                # 응답 처리
                try:
                    parsed_response = response.json()
                    if "result" in parsed_response and parsed_response["result"].get("code") != 0:
                        error_msg = parsed_response["result"].get("message", "ETL 응답 오류")
                        logger.error(f"ETL 연동  처리 중 오류 발생: {error_msg}")
                        raise Exception(f"ETL 연동  처리 중 오류 발생: {error_msg}")

                    else:
                        logger.info(f"==ETL_GET_JSON_TO_CSV==4 [{base_name}.pdf]")
                        self.json_data = parsed_response
                        chatsam_structure_maker = ChatsamStructureMaker(parsed_response, config_chunk, f"{base_name}.pdf")
                        logger.info("==ETL_GET_JSON_TO_CSV==5")
                        result = await chatsam_structure_maker.chunking(self.just_env.get_config("v2_service")["tokenizer"])
                        logger.info("==ETL_GET_JSON_TO_CSV==6")
                        result_path = os.path.join(folder_path, f"{base_name}.csv")
                        logger.info(f"==ETL_GET_JSON_TO_CSV==7 [{result_path}]")
                        result.to_csv(result_path, index=False, encoding="utf-8-sig")

                except ValueError as e:
                    logger.error(f"ETL의 응답에 예측값과 다릅니다. 계속진행({e})")
                    self.json_data = {"error": f"ETL의 응답에 예측값과 다릅니다. ({e})"}

        except Exception as e:
            logger.error(f"ETL연동 처리 중 오류 발생: {str(e)}")
            raise Exception(f"ETL연동 처리 중 오류 발생: {str(e)}") from e

        return self.json_data
