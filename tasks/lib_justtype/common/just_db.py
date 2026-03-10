import json
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.schemas.langgraph_data import LangGraphState
from app.tasks.lib_justtype.common.just_env import JustEnv
from app.tasks.lib_justtype.common.just_message import JustMessage

logger = logging.getLogger(__name__)


class JustSyncDB:
    def __init__(self, stat: LangGraphState):
        self.just_env = JustEnv(stat)
        self.just_msg = JustMessage(stat)
        config = self.just_env.get_config("summary")
        url = config["summary"]["db_url"]

        self.engine = create_engine(url, echo=False, pool_recycle=900)
        self.session_local = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

    def get_session(self):
        return self.session_local()

    def update_percentage(self, session, percentage: int):
        res_data = self.just_msg.get_response_session()
        # 진행률 업데이트 전용 헬퍼 함수
        sql_script = text(
            """
            UPDATE agent_session 
            SET percentage = :percentage 
            WHERE id = :session_id
        """
        )
        session.execute(sql_script, {"percentage": percentage, "session_id": res_data.session_id})
        session.commit()

    def update_message(self, session):
        res_data = self.just_msg.get_response_session()
        # res_data의 변경 내용을 db에 저장한다.
        messages_dump = json.dumps([message.model_dump(mode="json") for message in res_data.messages], ensure_ascii=False)
        sql_script = text(
            """
              UPDATE agent_session
                 SET messages_dump = :messages_dump,
                     percentage = 100
               WHERE id = :session_id
             """
        )
        session.execute(sql_script, {"messages_dump": messages_dump, "session_id": res_data.session_id})
        session.commit()  # 커밋

    def __enter__(self):
        self.session = self.get_session()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
        self.engine.dispose()
