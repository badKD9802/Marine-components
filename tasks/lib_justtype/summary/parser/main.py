import logging
import os
import time
from datetime import datetime

# from .parsing import detect_and_rotate_pdf_pages
from .dataload import get_loader
from .utils import classify_pdf, get_file_mime_type, is_likely_image_based  # , extract_file_name


def setup_logger(log_dir, log_file_name) -> logging.Logger:
    log_path = f"{log_dir}/{log_file_name}"
    logger = logging.getLogger(log_path)
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


# # Logging 설정
# logging.basicConfig(level=logging.INFO,
#                     format='%(asctime)s [%(levelname)s] %(message)s',
#                     handlers=[
#                         logging.FileHandler("parser.log"),
#                         logging.StreamHandler()
#                     ])


# TODO) check_runtime
# def parser_main(file_path, summation_id, log_dir, parsing_dir, rotation_option=False):
def parser_main(file_path, summation_id, log_dir, parsing_dir):
    """
    주어진 파일 경로에서 파일을 처리하는 메인 함수
    """
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logger(log_dir, f"{current_time}_psr_{summation_id}.log")
    start_time = time.time()  # 시작 시간 기록

    likely_image_based = None
    text_output = None
    tool_ = None
    error_ = None

    try:
        logger.info(f"File Path : {file_path}")

        output_path = os.path.join(parsing_dir, summation_id)
        text_output_path = os.path.join(output_path, "file_text")
        image_output_path = os.path.join(output_path, "file_image")

        if not os.path.exists(text_output_path):
            os.makedirs(text_output_path)
        if not os.path.exists(image_output_path):
            os.makedirs(image_output_path)

        # 파일 타입 감지
        file_type = get_file_mime_type(file_path)
        logger.info(f"Detected file type: {file_type}")

        # 데이터 로더 생성 (HHHHHHHH file_type에 맞는 loader를 가져온다. 여기서는 pdf만 처리)
        loader = get_loader(file_path, file_type, output_path, summation_id)

        # 파일 정보 로드
        total_pages = loader.load()
        logger.info(f"Total Pages: {total_pages}")

        # Text/Image based PDF Distinguish
        if file_type in ("application/x-hwp", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
            file_path = loader.get_convert_pdf_file()  # HHHHHHHHHH pdf만 처리했으니, 여기로 올 수가 없다.
        else:
            pass

        if file_type != "application/zip":
            if is_likely_image_based(file_path):
                logger.info(" ### image-based PDF ### ")
                error_ = "이미지 기반 pdf는 parsing 불가"

            else:
                logger.info(" ### text-based PDF ### ")
                is_cid_doc = classify_pdf(file_path)
                if is_cid_doc:  # HHHHHHHHHH cid가 너무 많으면, parsing불가로 판단한다.
                    logger.info(" ### text-based PDF but cid DOC ### ")
                    error_ = "인코딩 에러로 인해 pdf parsing 불가"
                else:
                    # 파일 파싱
                    text_output, tool_, error_ = loader.parse(text_output_path, image_output_path)
                    if error_:
                        logger.debug(error_)
                    logger.info(f"Files are saved in {output_path}")
        else:
            # 파일 파싱
            text_output, tool_, error_ = loader.parse(text_output_path, image_output_path)
            logger.info(f"Files are saved in {output_path}")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        error_ = "기타 parsing 과정 에러"
        # shutil.rmtree(output_path)

    end_time = time.time()  # 종료 시간 기록
    elapsed_time = end_time - start_time  # 소요 시간 계산
    elapsed_minutes = int(elapsed_time // 60)  # 분 계산
    elapsed_seconds = int(elapsed_time % 60)  # 초 계산
    logger.info(f"Total time: {elapsed_minutes} minutes, {elapsed_seconds} seconds")

    return text_output, error_
