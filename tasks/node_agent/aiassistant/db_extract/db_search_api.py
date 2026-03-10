import oracledb
from app.tasks.lib_justtype.common.just_env import JustEnv
from app.tasks.lib_justtype.common.just_message import JustMessage, LangGraphState
import logging
from app.tasks.lib_justtype.common import util
import pandas as pd
from app.tasks.node_agent.aiassistant.services.xml_parsing import *
import requests
import json

logger = util.TimeCheckLogger(logging.getLogger(__name__), "==DEFAULT_MULTI_TURN==")

class OracleSearchClient:
    def __init__(self, stat: LangGraphState):
        self.stat = stat
        self.env = JustEnv(stat)
        self._set_db_config()
        
    def _set_db_config(self):
        ai_config = self.env.get_config("aiassistant")
        db_api = ai_config.get("db_api", {})
        db_api_url = db_api.get("db_api_url", {})
        just_msg = JustMessage(self.stat)
        req_session = just_msg.get_request_session()
        client_info = stat["client_info"]
        req_data = client_info.req_data
        extra_data = req_session.messages[0].extra_data
        k_value = req_data.extra_data.get("K") or (req_data.extra_data.get("cookie", {}).get("K"))
        # if k_value is None:
        #     raise f"'{e}'값이 존재하지 않습니다. 재로그인을 해주시기 바랍니다."
        # k_value = req_data.extra_data.get("k", req_data.extra_data["cookie"]["K"])
        self.k = k_value
        self.url = db_api_url
        
    def _query(self, sql: str, params: dict = None, fetch_df: bool = True):
        try:
            data = {
                "query": sql,
                "params": params
                }
                
            headers = {
                "K-API-KEY": self.k
            }

            response = requests.post(self.url, json=data, headers=headers)
            response_json = json.loads(response.text)['data']
            result = pd.DataFrame(result)
            return result
        except Exception as e:
            logger.info(e)
            return pd.DataFrame()
                
    ### 직원 찾기 ###                
    async def search_by_name(self, name: str):
        sql = """
        SELECT * FROM intraware10.V_AI_EMP_SRCH
        WHERE EMP_NM LIKE '%' || :name || '%'
        """
        return self._query(sql, {"name": name})
    
    async def bm25_search(self):
        sql = """
        SELECT * FROM intraware10.V_AI_EMP_SRCH
        """
        return self._query(sql)
    
    # async def search_by_phone_number(self, number: str,):
    #     sql = """
    #     SELECT * FROM intraware10.V_AI_EMP_SRCH
    #     WHERE NAME = :name AND MOBILE_PHONE LIKE '%' || :number || '%'
    #     """
    #     return self._query(sql, {"number": number})
    
    async def search_by_posname(self, pos_name: str):
        sql = """
        SELECT * FROM intraware10.V_AI_EMP_SRCH
        WHERE POSN_NM LIKE '%' || :posname || '%'
        """
        return self._query(sql, {"posname": pos_name})
    
    async def search_by_email(self, email: str):
        sql = """
        SELECT * FROM intraware10.V_AI_EMP_SRCH
        WHERE EML LIKE '%' || :email || '%'
        """
        return self._query(sql, {"email": email})
    
    async def search_by_empcode(self, empcode: str):
        sql = """
        SELECT * FROM intraware10.V_AI_EMP_SRCH
        WHERE EMPNO = :empcode
        """
        return self._query(sql, {"empcode": empcode})
    
    async def search_by_team(self, dept_nm:str):
        sql = """
        SELECT * FROM intraware10.V_AI_EMP_SRCH
        WHERE REPLACE(TEAM_NM, ' ' , '') = REPLACE(:dept_nm, ' ', '')
        """
        return self._query(sql, {'dept_nm': dept_nm})
    
    async def search_by_dept(self, szteam:str):
        sql = """
        SELECT * FROM intraware10.V_AI_EMP_SRCH
        WHERE REPLACE(DEPT_NM, ' ' , '') = REPLACE(:szteam, ' ', '')
        ORDER BY TEAM_NM
        """
        logger.info(sql)
        return self._query(sql, {'szteam': szteam})
    
    ### 회의실 등록자 번호 조회(회의실 중복 등록 시, 등록된 회의실의 등록자에 대한 번호 조회용) ###
    async def search_owner_id(self, user_id: str):
        sql = """
        SELECT PHONE FROM intraware10.V_AI_EMP_SRCH
        WHERE USER_ID = :user_id
        """
        rows = self._query(sql, {"user_id": user_id}, fetch_df=False)
        return rows[0][0] if rows else ""
    
    ## 회의실 번호 조회(회의실 이름을 통해 회의실 id 조회하는 함수)
    async def get_meetingroom_id(self, title: str):
        sql = """
        SELECT CALENDAR_ID FROM intraware10.V_TN_CALENDAR
        WHERE EQUIPMENT_FG = 1 AND CALENDAR_ST = 1 AND TITLE = :title
        """
        rows = self._query(sql, {"title": title}, fetch_df=False)
        return rows[0][0] if rows else ""
    
    ## 회의실의 모든 리스트 출력(사용자에게 회의실에 대한 정보를 전달해주기 위함) ##
    async def list_meetingrooms(self):
        sql = """
        SELECT c2.TITLE AS PAR_TITLE, c1.TITLE
        FROM intraware10.V_TN_CALENDAR c1
        LEFT JOIN intraware10.V_TN_CALENDAR c2 ON c1.PAR_CALENDAR_ID = c2.CALENDAR_ID
        WHERE c1.EQUIPMENT_FG = 1
        AND c1.CALENDAR_ST = 1
        AND c1.PAR_CALENDAR_ID !='00000000000000000000'    
        AND c2.title NOT LIKE '%차량%'
        AND c1.title NOT LIKE '%PC-%'
        ORDER BY c2.title, c1.title
        """
        df = self._query(sql)
        return df["TITLE"].tolist()
    
    async def par_list_meetingrooms(self):
        sql = """
        SELECT c2.TITLE AS PAR_TITLE, c1.TITLE
        FROM intraware10.V_TN_CALENDAR c1
        LEFT JOIN intraware10.V_TN_CALENDAR c2 ON c1.PAR_CALENDAR_ID = c2.CALENDAR_ID
        WHERE c1.EQUIPMENT_FG = 1
        AND c1.CALENDAR_ST = 1
        AND c1.PAR_CALENDAR_ID !='00000000000000000000'    
        AND c2.title NOT LIKE '%차량%'
        AND c1.title NOT LIKE '%PC-%'
        ORDER BY c2.title, c1.title
        """
        df = self._query(sql)
        return df.to_records(index=False)
    
## 팀 달력을 가져오기위해 사용자의 팀 정보 조회 함수 ##
    async def get_dept_from_empcode(self, number: str):
        sql = """
        SELECT DEPT_NM FROM intraware10.V_AI_EMP_SRCH
        WHERE SZUSERID = :number
        """
        rows = self._query(sql, {"number": number}, fetch_df=False)
        if rows:
            return rows[0][0]
        return "그룹웨어 재구축 시스템실" # TODO"  운영단계에서 제거 예정

## 팀 달력을 가져오기위해 사용자의 팀 정보 조회 함수 ##
    async def get_empcode_calendar(self, number: str):
        sql = """
        SELECT DEPT_NM
        FROM intraware10.V_AI_EMP_SRCH
        WHERE SZUSERID = :number
        """
        columns = [col[0] for col in cursor.description]
        rows = self._query(sql, {"number": number}, fetch_df=False)
        if rows:
            result = rows[0][0]
            logger.info(f"===============result {result}=============")
        else:
            result = '그룹웨어 재구축 시스템구축팀'

## 결재 문서 양식 호출
    async def document_search(self):
        sql = """
        SELECT DISTINCT FORMID, FLDRNAME, FORMNAME, FORMCLASSNAME, DESCRIPTION
        FROM intraware10.V_AI_APPRFORM
        """
        logger.info(sql)
        return self._query(sql)
           
        
        
    
async def search_db_empcode_calendar(number,stat: LangGraphState):
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
    logger.info(dsn)

    try:
        connection = oracledb.connect(user=username, password=password, dsn=dsn)

        # print("DB연결 성공")

        cursor = connection.cursor()

        sql = """
        SELECT DEPT_NAME
        FROM intraware10.V_AI_EMP_SRCH
        WHERE SZUSERID = '{number}'
        """
        # print(sql.format(name=name))
        cursor.execute(sql.format(number=number))

        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        logger.info(f"================rows {rows}=========")
        if rows:
            result = rows[0][0]
            logger.info(f"================result {result}=========")
        else:
            result = '그룹웨어 재구축 시스템구축팀'##TODO: 임시로 넣어놨음 추후 그룹웨어 API를 통해서 user정보를 더 가져오든 운영DB를 바라봐야해야함
        # for row in rows:
        #     print(row)
        df = pd.DataFrame(rows, columns=columns)
        print(df)


    except oracledb.DatabaseError as e:
        print(f"DB 연결 실패: {e}")
        result = ''

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
            # print("DB연결 종료")

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