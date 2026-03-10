import logging
import os
import time
import uuid
from datetime import datetime

from app.core.util import action_model, deprecated_action_tokenizer


class TimeCheckLogger(logging.LoggerAdapter):
    def __init__(self, logger, prefix=None):
        super().__init__(logger, {})
        self.last_log_time = None
        self.prefix = prefix

    def process(self, msg, kwargs):
        current_time = time.time()
        if self.last_log_time is None:
            delta = "START"
        else:
            delta = f"{current_time - self.last_log_time:.3f}"
        self.last_log_time = current_time
        if self.prefix:
            return f"<{delta}> [{self.prefix}] {msg}", kwargs
        else:
            return f"<{delta}> {msg}", kwargs

    def setLevel(self, level):
        self.logger.setLevel(level)

    def getEffectiveLevel(self):
        return self.logger.getEffectiveLevel()

    def isEnabledFor(self, level):
        return self.logger.isEnabledFor(level)


def embedding_model(model_name: str, action_str: str = "get", device_opt: str = None):
    return action_model(model_name, action_str, device_opt)


def deprecated_get_tokenizer(model_name):
    return deprecated_action_tokenizer(model_name)


def generate_uuid(gbn):
    return gbn + datetime.today().strftime("%m%d%S") + str(uuid.uuid4())[:8]


def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
