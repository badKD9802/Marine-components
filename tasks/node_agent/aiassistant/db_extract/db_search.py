import oracledb
from app.tasks.lib_justtype.common.just_env import JustEnv
from app.tasks.lib_justtype.common.just_message import JustMessage, LangGraphState
import logging
from app.tasks.lib_justtype.common import util
import pandas as pd
from app.tasks.node_agent.aiassistant.services.xml_parsing import *
import requests
import json

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== DB SEARCH ==")


def k_userinfo(gw_url, ip, empcode):
    url = f'{gw_url}/jsp/openapi/OpenApi.jsp?target=session&todo=loginByCert&certKey=handy&clientName={ip}&loginType=empcode&loginName={empcode}'
    response = requests.get(url)
    
    root = ET.fromstring(response.text)

    try:
        data = {
            'id': root.find('id').text,
            'empcode': root.find('empcode').text,
            'deptid': root.find('deptid').text,
            'key': root.find('key').text,
            'user_nm': root.find('name').text,
            'docdept_nm': root.find('saveDocDeptName').text
        }
    except Exception as e:
        logger.error(e)
        data = {}
    
    return data

class OracleSearchClient:
    def __init__(self, stat: LangGraphState):
        self.stat = stat
        self.env = JustEnv(stat)
        self.msg = JustMessage(stat)
        self.client_info = stat["client_info"]
        self._set_db_config()
        
    def _set_db_config(self):
        ai_config = self.env.get_config("aiassistant")
        db_api = ai_config.get("db_api", {})
        db_api_url = db_api.get("db_api_url", {})
        
        client_info = self.stat["client_info"]
        req_data = client_info.req_data
        res_data = client_info.res_data
        try:
            if req_data.extra_data and req_data.extra_data.get("cookie"):
                k_value = req_data.extra_data.get("cookie").get("K", "None")
                if k_value == "None":
                    k_value = req_data.extra_data.get("k", "None")
            else:
                k_value = "None"
        except Exception as e:
            logger.error(e)
        # logger.info(f'=== K vlaue === : {k_value}')
        
        self.k = k_value
        self.url = db_api_url
        
    def _query(self, query_id: str, params: dict = None, fetch_df: bool = True):
        try:
            data = {
                "query_id": query_id,
                "params": params
                }
                
            headers = {
                "K-API-KEY": self.k
            }

            response = requests.post(self.url, json=data, headers=headers)
            response_json = json.loads(response.text)['data']
            result = pd.DataFrame(response_json)
            return result
        except Exception as e:
            logger.error(e)
            return pd.DataFrame()

    ### 회의실 예약자 사내번호 조회 ###
    async def search_db_owner_id(self, user_id):
        try:
            query_id = 'get_user_info'
            rows = self._query(query_id, {"user_id": user_id})
            empcode = rows['EMPNO'][0]
    		
            query_id = 'get_emp_srch_telno'
            phone_rows = self._query(query_id, {"empcode": empcode})
            phone = phone_rows['TEL_NO'][0]
        except Exception as e:
            logger.error(e)
            phone = ""
        return phone

    ### 회의실 조회 ###
    async def meetingroom_db(self, title):
        query_id = 'get_calendar_id'
        rows = self._query(query_id, {"title": title})
        df = rows['CALENDAR_ID'][0]
        return df
                
    async def meetingroom_db_list(self):
        query_id = 'get_meetingroom'
        try:
            rows = self._query(query_id)
            df = pd.DataFrame(rows)
            df = list(df['TITLE'])
        except Exception as e:
            logger.error(e)
            rows = ""
            df = ""
        return rows, df

    ### 직원 찾기 ###                
    async def search_by_name(self, name: str):
        query_id = 'get_emp_srch_name'
        return self._query(query_id, {"name": name})
    
    async def employee_all_search(self):
        query_id = 'get_emp_srch_all'
        return self._query(query_id)
    
    # async def search_by_phone_number(self, number: str,):
    #     sql = """
    #     SELECT * FROM intraware10.V_AI_EMP_SRCH
    #     WHERE NAME = :name AND MOBILE_PHONE LIKE '%' || :number || '%'
    #     """
    #     return self._query(sql, {"number": number})
    
    async def search_by_posname(self, pos_name: str):
        query_id = 'get_emp_srch_pos'
        return self._query(query_id, {"posname": pos_name})
    
    async def search_by_email(self, email: str):
        query_id = 'get_emp_srch_email'
        return self._query(query_id, {"email": email})
    
    async def search_by_empcode(self, empcode: str):
        query_id = 'get_emp_srch_empno'
        return self._query(query_id, {"empcode": empcode})
    
    async def search_by_team(self, dept_nm:str):
        query_id = 'get_emp_deptnm'
        return self._query(query_id, {'dept_nm': dept_nm})
    
    async def search_by_dept(self, szteam:str):
        query_id = 'get_emp_szteam'
        return self._query(query_id, {'szteam': szteam})
    
    ### 회의실 등록자 번호 조회(회의실 중복 등록 시, 등록된 회의실의 등록자에 대한 번호 조회용) ###
    async def search_owner_id(self, user_id: str):
        query_id = 'get_emp_srch_userid'
        rows = self._query(query_id, {"user_id": user_id}, fetch_df=False)
        return rows[0][0] if rows else ""
    
    ### 임원 일정 조회 시, 직위(ex: 사장, 이사, 부사장, 감사 등..) 추출
    async def imwon_posnm(self):
        query_id = 'get_imwon_pos'
        return self._query(query_id)
    
    
    ## 회의실 번호 조회(회의실 이름을 통해 회의실 id 조회하는 함수)
    async def get_meetingroom_admission(self, title: str):
        query_id = 'get_equip_admission'
        rows = self._query(query_id, {"title": title}, fetch_df=False)
        return rows["EQUIPMENT_ADMISSION_FG"][0]
    
    ## 회의실의 모든 리스트 출력(사용자에게 회의실에 대한 정보를 전달해주기 위함) ##
    async def list_meetingrooms(self):
        query_id = 'get_meetingroom'
        df = self._query(query_id)
        return df["TITLE"].tolist()
    
    async def par_list_meetingrooms(self):
        query_id = 'get_meetingroom'
        df = self._query(query_id)
        return df.to_records(index=False)
    
    # async def admission_meetingrooms(self):
    #     sql = """
    #     SELECT c1.EQUIPMENT_ADMISSION_FG
    #     FROM intraware10.V_TN_CALENDAR c1
    #     LEFT JOIN intraware10.V_TN_CALENDAR c2 ON c1.PAR_CALENDAR_ID = c2.CALENDAR_ID
    #     WHERE c1.EQUIPMENT_FG = 1
    #     AND c1.CALENDAR_ST = 1
    #     AND c1.PAR_CALENDAR_ID !='00000000000000000000'    
    #     AND c2.title NOT LIKE '%차량%'
    #     AND c1.title NOT LIKE '%PC-%'
    #     ORDER BY c2.title, c1.title
    #     """
    #     df = self._query(sql)
    #     return df.to_records(index=False)
    
## 팀 달력을 가져오기위해 사용자의 팀 정보 조회 함수 ##
    async def get_dept_from_empcode(self, number: str):
        query_id = 'get_emp_srch_szid'
        rows = self._query(query_id, {"number": number}, fetch_df=False)
        if rows:
            return rows[0][0]
        return "그룹웨어 재구축 시스템실" # TODO"  운영단계에서 제거 예정

## 팀 달력을 가져오기위해 사용자의 팀 정보 조회 함수 ##
    async def get_empcode_calendar(self, number: str):
        query_id = 'get_emp_srch_szid'
        columns = [col[0] for col in cursor.description]
        rows = self._query(query_id, {"number": number}, fetch_df=False)
        if rows:
            result = rows[0][0]
            # logger.info(f"===============result {result}=============")
        else:
            result = '그룹웨어 재구축 시스템구축팀'

## 결재 문서 양식 호출 #완료
    async def document_search(self):
        query_id = 'get_appr_formid'
        #logger.info(sql)
        return self._query(query_id)
           
        
        
    
async def search_db_empcode_calendar(number,stat: LangGraphState):
    result = ''
    # just_env = JustEnv(stat)
    # logger.info("소속팀을 가져오겠습니다.")
    
    # retrieval_config = just_env.get_config("retrieval")
    # search_config = retrieval_config.get("search_config", {})
    # user_doc_filter = search_config.get("user_doc_filter", {})
    # ip = user_doc_filter.get("ip", '')
    # port = user_doc_filter.get("port", '')
    # sid = user_doc_filter.get("sid", '')
    # username = user_doc_filter.get("username", '')
    # password = user_doc_filter.get("password", '')

    # dsn = f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP) (HOST={ip}) (PORT={port})) (CONNECT_DATA=(SID={sid})))"
    # logger.info(dsn)
    
    # try:
    #     connection = oracledb.connect(user=username, password=password, dsn=dsn)
        
    #     # print("DB연결 성공")
        
    #     cursor = connection.cursor()
    
    #     sql = """
    #     SELECT DEPT_NAME
    #     FROM intraware10.V_AI_EMP_SRCH
    #     WHERE SZUSERID = '{number}'
    #     """
    #     # print(sql.format(name=name))
    #     cursor.execute(sql.format(number=number))
    
    #     columns = [col[0] for col in cursor.description]
    #     rows = cursor.fetchall()
    #     logger.info(f"================rows {rows}=========")
    #     if rows:
    #         result = rows[0][0]
    #         logger.info(f"================result {result}=========")
    #     else:
    #         result = '그룹웨어 재구축 시스템구축팀'
    #     # for row in rows:
    #     #     print(row)
    #     df = pd.DataFrame(rows, columns=columns)
    #     print(df)
        
    
    # except oracledb.DatabaseError as e:
    #     print(f"DB 연결 실패: {e}")
    #     result = ''
    
    # finally:
    #     if 'cursor' in locals():
    #         cursor.close()
    #     if 'connection' in locals():
    #         connection.close()
    #         # print("DB연결 종료")

    return result  



async def DEPT_NM_list(stat):
    just_env = JustEnv(stat)
    logger.info("소속팀을 가져오겠습니다.")

    retrieval_config = just_env.get_config("retrieval")
    search_config = retrieval_config.get("search_config", {})
    user_doc_filter = search_config.get("user_doc_filter", {})
    ip = user_doc_filter.get("ip", '')
    port = user_doc_filter.get("port", '')
    sid = user_doc_filter.get("sid", '')
    username = user_doc_filter.get("username", '')
    password = user_doc_filter.get("password", '')

    dsn = f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP) (HOST={ip}) (PORT={port})) (CONNECT_DATA=(SID={sid})))"

    connection = oracledb.connect(user=username, password=password, dsn=dsn)


    logger.info("팀이름 리스트를 가져옵니다.")
    # print("DB연결 성공")

    cursor = connection.cursor()

    sql = """
    SELECT distinct DEPT_NM
    FROM intraware10.V_AI_EMP_SRCH
    """

    cursor.execute(sql)

    columns = [col[0] for col in cursor.description]
    # print(columns)
    rows = cursor.fetchall()
    # print(rows)
    # result = rows[0][0]
    # print(result)

    df = pd.DataFrame(rows, columns=columns)
    df = list(df['DEPT_NM'])

    return df