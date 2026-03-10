import logging
import os
import re
import time
from functools import wraps


def extract_contents(text: str, tag: str) -> list[str]:
    pattern = rf"<{tag}>(.*?)</{tag}>"
    matches = re.findall(pattern, text, flags=re.DOTALL)
    matches = [m.replace("\n", " ").strip() for m in matches]
    matches = [m for m in matches if m]
    return matches


def setup_logger(log_dir, log_file_name) -> logging.Logger:
    log_path = os.path.join(log_dir, log_file_name)
    logger = logging.getLogger(log_path)
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(log_path, encoding="utf-8")

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(funcName)s: %(message)s")
    stream_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    return logger


def check_runtime(logger: logging.Logger):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                run_time = int(time.time() - start_time)
                logger.error(f"Function '{func.__name__}' failed after {run_time // 60}분 {run_time % 60}초: {e}")
                raise
            else:
                run_time = int(time.time() - start_time)
                logger.info(f"Processing time: {run_time // 60}분 {run_time % 60}초")
                return result

        return wrapper

    return decorator
