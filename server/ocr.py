"""문서 텍스트 추출 모듈 — PDF(PyMuPDF 텍스트+테이블) + 이미지(pytesseract) OCR"""

import os
import shutil
import fitz  # PyMuPDF
from PIL import Image

# tesseract는 선택 사항 (없으면 OCR 스킵)
_has_tesseract = shutil.which("tesseract") is not None
if _has_tesseract:
    import pytesseract
    print("tesseract OCR 사용 가능")
else:
    print("WARNING: tesseract 미설치 — OCR 비활성, 텍스트 레이어 + 테이블만 추출")


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


def _extract_table_text(page) -> str:
    """페이지에서 테이블을 찾아 마크다운 형식으로 변환한다."""
    try:
        tables = page.find_tables()
        if not tables.tables:
            return ""
        parts = []
        for table in tables:
            rows = table.extract()  # list[list[str]]
            if not rows:
                continue
            # 마크다운 테이블 생성
            lines = []
            header = [str(c or "") for c in rows[0]]
            lines.append("| " + " | ".join(header) + " |")
            lines.append("| " + " | ".join("---" for _ in header) + " |")
            for row in rows[1:]:
                cells = [str(c or "") for c in row]
                lines.append("| " + " | ".join(cells) + " |")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)
    except Exception:
        return ""


def _extract_from_pdf(file_path: str) -> str:
    """PDF에서 텍스트 + 테이블 추출. 텍스트 레이어 없으면 OCR fallback."""
    doc = fitz.open(file_path)
    texts = []

    for page_num, page in enumerate(doc):
        page_parts = []

        # 1) 일반 텍스트 추출
        text = page.get_text().strip()
        if text:
            page_parts.append(text)

        # 2) 테이블 추출 (마크다운 형식)
        table_text = _extract_table_text(page)
        if table_text:
            page_parts.append(table_text)

        # 3) 텍스트도 테이블도 없으면 OCR fallback
        if not page_parts and _has_tesseract:
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = pytesseract.image_to_string(img, lang="kor+eng").strip()
            if ocr_text:
                page_parts.append(ocr_text)

        if page_parts:
            texts.append("\n\n".join(page_parts))

    doc.close()
    return "\n\n".join(texts)


def _extract_from_image(file_path: str) -> str:
    """이미지(jpg/png)에서 OCR로 텍스트 추출."""
    if not _has_tesseract:
        return ""
    img = Image.open(file_path)
    text = pytesseract.image_to_string(img, lang="kor+eng").strip()
    return text
