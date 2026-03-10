"""SLO 인증 결과를 담는 컨테이너. 1회 생성, 전체 ReAct 루프에서 재사용."""

import logging
from app.tasks.lib_justtype.common import util

logger = util.TimeCheckLogger(logging.getLogger(__name__), "== AUTH CONTEXT ==")


class AuthContext:
    """SLO 인증 결과 + stat 참조를 보관하는 컨테이너.

    - ReAct 루프 시작 시 `from_stat(stat)` 으로 1회 생성
    - 각 tool 함수에서 `_auth` 파라미터로 받아 재사용
    - `self.stat` 으로 APICollection(stat), OracleSearchClient(stat) 생성 가능
    """

    def __init__(self, stat, user_id, emp_code, dept_id, k, user_nm, docdept_nm, docdept_id):
        self.stat = stat            # LangGraphState 참조 (API/DB 클라이언트 생성용)
        self.user_id = user_id
        self.emp_code = emp_code
        self.dept_id = dept_id
        self.k = k                  # 세션키 (GW API 인증)
        self.user_nm = user_nm
        self.docdept_nm = docdept_nm
        self.docdept_id = docdept_id

    @classmethod
    async def from_stat(cls, stat):
        """stat(LangGraphState)에서 SLO 1회 호출하여 AuthContext 생성."""
        from app.tasks.node_agent.aiassistant.services.xml_parsing import xml_parsing_userinfo_slo

        user_id, emp_code, dept_id, k, user_nm, docdept_nm, docdept_id = await xml_parsing_userinfo_slo(stat)
        logger.info(f"[AuthContext] SLO 1회 호출 완료: user={user_nm}, emp={emp_code}")

        return cls(stat, user_id, emp_code, dept_id, k, user_nm, docdept_nm, docdept_id)

    @property
    def is_authenticated(self):
        """인증 성공 여부."""
        return self.k is not None and self.user_id is not None
