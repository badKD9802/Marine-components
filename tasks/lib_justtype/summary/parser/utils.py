import json
import os
import re

import fitz
import pdfplumber


def save_json_file(file, output_file):
    """
    JSON 파일로 데이터를 저장
    """
    # 241115 주석처리(json 파일 저장 중단)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(file, f, ensure_ascii=False, indent=4)
    # pass


def load_json_file(file_path):
    """
    JSON 파일을 로드
    """
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    return data


def get_file_mime_type(file_path):
    """
    파일의 MIME 타입을 반환
    """
    return "application/pdf"

    # mime.from_file이 한글 file을 못 열어서 일단 통과 시킨다.
    # 어차피 pdf만 처리한다.

    # file_path = os.path.normpath(file_path)     # HHHHH (한글파일 못여는 문제 해결)
    # file_path = str(Path(file_path).resolve())  # HHHHH (한글파일 못여는 문제 해결)
    # if not os.path.exists(file_path):
    #     raise FileNotFoundError(f"파일이 존재하지 않습니다: {file_path}")
    #
    # mime = magic.Magic(mime=True)
    # return mime.from_file(file_path)


def extract_file_name(file_path):
    """
    파일 이름에서 확장자를 제거한 이름을 반환
    """
    base_name = os.path.basename(file_path)
    name_without_ext = os.path.splitext(base_name)[0]
    return name_without_ext


def is_likely_image_based(file_path, num_pages_to_check=5, word_threshold=20):
    try:
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            pages_to_check = list(range(min(num_pages_to_check, total_pages)))
            if total_pages > num_pages_to_check:
                pages_to_check += list(range(total_pages - num_pages_to_check, total_pages))

            for page_index in pages_to_check:
                page = pdf.pages[page_index]
                text = page.extract_text()

                if text:
                    words = text.strip().split()
                    if len(words) >= word_threshold:
                        return False  # 충분한 양의 단어가 있는 페이지가 하나라도 있으면 텍스트 기반

            return True  # 모든 샘플링한 페이지에 충분한 양의 텍스트가 없으면 이미지 기반
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return None  # 에러 발생 시 None 반환


def extract_sample_text_with_cid(pdf_path, sample_pages=10):
    text_content = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        pages_to_sample = min(sample_pages, total_pages)

        for page_num in range(0, total_pages, max(1, total_pages // sample_pages)):
            page = pdf.pages[page_num]
            text = page.extract_text()
            if text:
                text_content.append(text)
    return text_content


def is_cid_document(text_content, threshold=0.1):
    cid_pattern = re.compile(r"\(cid:\d+\)")
    total_length = sum(len(text) for text in text_content)
    cid_count = sum(len(cid_pattern.findall(text)) for text in text_content)

    if total_length == 0:
        return False
    return (cid_count / total_length) > threshold


def classify_pdf(pdf_path, sample_pages=5, threshold=0.1):
    text_content = extract_sample_text_with_cid(pdf_path, sample_pages)
    return is_cid_document(text_content, threshold)


# fitz를 이용해 PDF 재저장
def resave_pdf(file_path, output_path):
    # PyMuPDF를 사용하여 PDF 열기
    doc = fitz.open(file_path)
    # 빈 PDF 생성
    output_pdf = fitz.open()
    # 전체 페이지를 새 PDF에 추가
    output_pdf.insert_pdf(doc)
    # 파일로 저장
    output_pdf.save(output_path)
