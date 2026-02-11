"""문서 텍스트 추출 모듈 — PDF(PyMuPDF) + 이미지(pytesseract) OCR"""

import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image


def extract_text(file_path: str, file_type: str) -> str:
    """파일에서 텍스트를 추출한다.

    Args:
        file_path: 파일 경로
        file_type: 'pdf' 또는 'image'

    Returns:
        추출된 텍스트 문자열
    """
    if file_type == "pdf":
        return _extract_from_pdf(file_path)
    else:
        return _extract_from_image(file_path)


def _extract_from_pdf(file_path: str) -> str:
    """PDF에서 텍스트 추출. 텍스트 레이어가 없으면 OCR 수행."""
    doc = fitz.open(file_path)
    texts = []

    for page_num, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            texts.append(text)
        else:
            # 텍스트 레이어 없음 → 페이지를 이미지로 변환 후 OCR
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = pytesseract.image_to_string(img, lang="kor+eng").strip()
            if ocr_text:
                texts.append(ocr_text)

    doc.close()
    return "\n\n".join(texts)


def _extract_from_image(file_path: str) -> str:
    """이미지(jpg/png)에서 OCR로 텍스트 추출."""
    img = Image.open(file_path)
    text = pytesseract.image_to_string(img, lang="kor+eng").strip()
    return text
