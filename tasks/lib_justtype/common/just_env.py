import json
import logging
from typing import Any

import yaml
from pydantic import BaseModel

from app.core.config import GlobalSettings
from app.schemas.langgraph_data import LangGraphState, ServiceInfo

logger = logging.getLogger(__name__)


class JustEnv:
    def __init__(self, stat: LangGraphState):
        self.stat = stat
        self.global_var = {}
        try:
            global_var_conf = self.get_conf("global_var")
            if global_var_conf and global_var_conf.config_dump:
                self.global_var = yaml.safe_load(global_var_conf.config_dump) or {}
        except Exception as e:
            logger.error(f"[JustEnv] global_var 파싱 실패 — 빈 dict로 폴백합니다: {e}")

    def get_conf(self, config_name: str) -> Any | None:
        service_info = self.get_service_info()
        if not service_info or not service_info.configs:
            return None

        for config in service_info.configs:
            if config.config_name == config_name:
                return config
        return None

    def get_config(self, config_name: str) -> Any | None:
        # config 찾기
        config = self.get_conf(config_name)
        if config is None:
            return None

        try:
            # 파싱
            if config.config_format == "json":
                actual_config = config.config_dump.format(**self.global_var)
                parsed = json.loads(actual_config)

            elif config.config_format == "raw_json":
                # str.format() 없이 json.loads만 수행 (Jinja2 {{ }} 변수 보존)
                parsed = json.loads(config.config_dump)

            elif config.config_format == "yaml":
                if config_name == "global_var":
                    parsed = yaml.safe_load(config.config_dump)
                else:
                    actual_config = config.config_dump.format(**self.global_var)
                    parsed = yaml.safe_load(actual_config)
            else:
                return None

            return parsed
        except Exception as e:
            logger.error(f"[JustEnv] config '{config_name}' (format={config.config_format}) 파싱 실패: {e}")
            return None

    def set_rag_code(self, rag_code: str):
        self.stat["rag_code"] = rag_code
        return

    def get_rag_code(self) -> str | None:
        return self.stat["rag_code"]

    def get_service_info(self) -> ServiceInfo | None:
        if self.stat:
            return self.stat["service_info"]
        return None

    def get_settings(self) -> GlobalSettings | None:
        service_info = self.get_service_info()
        if service_info and service_info.settings:
            return service_info.settings
        return None

    def get_value(self, key: str) -> Any | None:
        if not self.stat:
            return None

        # 1. service_info에서 값 확인 (pydantic 모델)
        service_info = self.stat.get("service_info")
        if service_info and hasattr(service_info, key):
            return getattr(service_info, key)

        # 2. client_info에서 직접 확인 (pydantic 모델)
        client_info = self.stat.get("client_info")
        if client_info and hasattr(client_info, key):
            return getattr(client_info, key)

        # 3. client_info의 req_data에서 확인 (pydantic 모델)
        if client_info and hasattr(client_info, "req_data"):
            req_data = client_info.req_data
            if req_data and hasattr(req_data, key):
                return getattr(req_data, key)

        # 4. client_info의 res_data에서 확인 (pydantic 모델)
        if client_info and hasattr(client_info, "res_data"):
            res_data = client_info.res_data
            if res_data and hasattr(res_data, key):
                return getattr(res_data, key)

        # 5. LangGraphState 최상위 (TypedDict)에서 확인
        if key in self.stat and self.stat[key] is not None:
            return self.stat[key]

        return None

    def set_var(self, var_name: str, var_value: Any) -> None:
        """
        변수를 stat에 저장합니다.
        custom_info BaseModel에 동적 속성으로 저장하여 node 간 전달 시 데이터 무결성을 보장합니다.
        """
        custom_info = self.stat.get("custom_info")

        # custom_info가 None인 경우 새로운 BaseModel 인스턴스 생성
        if custom_info is None:
            class CustomInfo(BaseModel):
                class Config:
                    extra = "allow"  # 동적 속성 허용 (Python 예약어 포함)

            custom_info = CustomInfo()
            self.stat["custom_info"] = custom_info

        # BaseModel에 동적 속성으로 변수 저장
        # Python 예약어인 경우를 위해 __dict__ 직접 조작
        custom_info.__dict__[var_name] = var_value

    def get_var(self, var_name: str) -> Any | None:
        """
        stat에서 변수를 가져옵니다.
        custom_info BaseModel의 속성에서 변수를 조회합니다.
        """
        custom_info = self.stat.get("custom_info")
        if custom_info is None:
            return None

        # BaseModel에서 속성으로 변수 조회 (Python 예약어 포함)
        return custom_info.__dict__.get(var_name)

    def apply_log_level(self):
        # ------------------------------------------------------------------------
        # log level setting
        # ------------------------------------------------------------------------
        gl_var = self.get_config("global_var")
        if not gl_var:
            logger.warning("[JustEnv] global_var config를 로드할 수 없어 기본 로그 레벨(WARNING)을 사용합니다.")
            return
        config_log_level = gl_var.get("log_level", 30)      # 값을 지정하지 않으면 WARNING이상만 보여줌. 즉, 거의 안 보여줌
        log_detail = gl_var.get("log_detail", "false")
        root_logger = logging.getLogger()                   # root_loger 가져오기.
        current_log_level = root_logger.getEffectiveLevel() # 현재의 적용중인 loglevel
        
        if config_log_level != current_log_level:           # 서로 다르면 config_log_level을 적용한다.
            logger.warning(f"LOG의 LEVEL을 변경합니다. [{current_log_level}] => [{config_log_level}]")
            root_logger.setLevel(config_log_level)             
            for name, logger_inst in logging.root.manager.loggerDict.items():    # 이하 모든 node에 적용된다.
                if log_detail == "true":
                    if isinstance(logger_inst, logging.Logger):
                        # httpcore/httpx trace 로그는 항상 억제
                        if name.startswith(("httpcore", "httpx")):
                            logger_inst.setLevel(logging.WARNING)
                            continue
                        logger.warning(f"LOG[{name}] => [{logger_inst}]")
                        logger_inst.setLevel(config_log_level)
                else:
                    if isinstance(logger_inst, logging.Logger) and name.startswith("app."):
                        logger.warning(f"LOG[{name}] => [{logger_inst}]")
                        logger_inst.setLevel(config_log_level)
                    
                    
