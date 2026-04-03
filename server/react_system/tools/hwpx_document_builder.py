"""
HWPX 문서 빌드 엔진 -- python-hwpx 라이브러리 기반

DocumentOutput (JSON 스키마) → HWPX 네이티브 파일 변환.
python-hwpx v2.9.0의 HwpxDocument API를 사용하여
문단, 테이블, 목록 등을 프로그래밍 방식으로 생성한다.

기존 hwpx_builder.py (텍스트 치환 방식)와는 독립적인 구현이다.
"""

import logging
import tempfile

logger = logging.getLogger(__name__)


def _patch_hwpx_et():
    """python-hwpx의 ET(xml.etree.ElementTree) / lxml 호환성 문제를 해결한다.

    python-hwpx 2.9.0에서 ensure_run_style() 등이
    xml.etree.ElementTree.SubElement를 호출하지만,
    실제 요소는 lxml.etree._Element 타입이어서 TypeError가 발생한다.
    이를 lxml.etree.SubElement로 대체하여 해결한다.
    """
    try:
        import hwpx.oxml.document as doc_mod
        from lxml import etree as LET

        original_ET = doc_mod.ET

        class _PatchedET:
            """ET 모듈 래퍼: SubElement/Element만 lxml으로 위임."""

            def __getattr__(self, name):
                if name == "SubElement":
                    return LET.SubElement
                if name == "Element":
                    return LET.Element
                return getattr(original_ET, name)

        doc_mod.ET = _PatchedET()
        return True
    except Exception as exc:
        logger.warning("python-hwpx ET 패치 실패: %s", exc)
        return False


# ─── 요소 변환 함수 ───


def _add_heading(hwpx_doc, content, bold_char_pr_id=None):
    """heading 요소를 HWPX 문서에 추가한다.

    볼드 처리가 가능하면 bold run을 사용하고,
    실패 시 일반 문단으로 대체한다.
    """
    text = content.text
    if content.bold and bold_char_pr_id is not None:
        para = hwpx_doc.add_paragraph("", char_pr_id_ref=bold_char_pr_id)
        para.add_run(text, char_pr_id_ref=bold_char_pr_id)
    else:
        hwpx_doc.add_paragraph(text)


def _add_paragraph(hwpx_doc, content):
    """paragraph 요소를 HWPX 문서에 추가한다."""
    hwpx_doc.add_paragraph(content.text)


def _add_table(hwpx_doc, content):
    """table 요소를 HWPX 문서에 추가한다.

    - caption이 있으면 테이블 위에 캡션 문단 삽입
    - columns로 헤더 행 구성 (첫 번째 행)
    - rows로 데이터 행 채우기
    - merge가 있으면 셀 병합 적용
    """
    # 캡션 문단
    if content.caption:
        hwpx_doc.add_paragraph(content.caption)

    num_cols = len(content.columns)
    num_data_rows = len(content.rows)
    # 헤더 1행 + 데이터 행
    total_rows = 1 + num_data_rows

    table = hwpx_doc.add_table(total_rows, num_cols)

    # 헤더 행 채우기
    for col_idx, col_def in enumerate(content.columns):
        table.set_cell_text(0, col_idx, col_def.name)

    # 데이터 행 채우기
    for row_idx, row_data in enumerate(content.rows):
        for col_idx, cell_value in enumerate(row_data):
            if col_idx < num_cols:
                table.set_cell_text(row_idx + 1, col_idx, cell_value)

    # 셀 병합 적용
    if content.merge:
        for m in content.merge:
            try:
                # merge 인덱스에 헤더 행 오프셋 적용 (+1)
                table.merge_cells(
                    m.start_row + 1, m.start_col,
                    m.end_row + 1, m.end_col,
                )
                # 병합 후 값 설정
                if m.value:
                    table.set_cell_text(m.start_row + 1, m.start_col, m.value)
            except Exception as exc:
                logger.warning("셀 병합 실패 (%s): %s", m, exc)


def _add_list(hwpx_doc, content):
    """list 요소를 HWPX 문서에 추가한다.

    - bullet: 각 항목에 '• ' 접두사
    - numbered: 각 항목에 '1. ', '2. ' 등 접두사
    """
    for idx, item in enumerate(content.items):
        if content.list_type == "numbered":
            prefix = f"{idx + 1}. "
        else:
            prefix = "• "
        hwpx_doc.add_paragraph(f"{prefix}{item}")


# ─── 메인 빌드 함수 ───


async def build_hwpx(doc, output_path: str = None) -> dict:
    """DocumentOutput JSON → HWPX 파일 생성.

    Args:
        doc: DocumentOutput 스키마 객체
        output_path: 저장할 파일 경로. None이면 tempfile 사용.

    Returns:
        {"status": "success", "file_path": ..., "message": ...}
        또는 {"status": "error", "message": ...}
    """
    try:
        from hwpx import HwpxDocument
    except ImportError as exc:
        return {
            "status": "error",
            "message": f"python-hwpx 라이브러리를 찾을 수 없습니다: {exc}",
        }

    try:
        # lxml 호환성 패치 적용
        _patch_hwpx_et()

        hwpx_doc = HwpxDocument.new()

        # 볼드 스타일 ID 준비 (실패해도 계속 진행)
        bold_char_pr_id = None
        try:
            bold_char_pr_id = hwpx_doc.ensure_run_style(bold=True)
        except Exception as exc:
            logger.warning("볼드 스타일 생성 실패 (무시됨): %s", exc)

        # 문서 제목 추가
        if doc.title:
            _add_heading(
                hwpx_doc,
                _make_title_content(doc.title),
                bold_char_pr_id=bold_char_pr_id,
            )

        # 섹션별 처리
        for section in doc.sections:
            # 섹션 제목 추가
            if section.section_title:
                _add_heading(
                    hwpx_doc,
                    _make_title_content(section.section_title),
                    bold_char_pr_id=bold_char_pr_id,
                )

            # 섹션 내 요소 순서대로 변환
            for element in section.elements:
                _process_element(hwpx_doc, element, bold_char_pr_id)

        # 파일 저장
        if output_path is None:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".hwpx", delete=False, prefix="hwpx_doc_"
            )
            output_path = tmp.name
            tmp.close()

        hwpx_doc.save_to_path(output_path)
        hwpx_doc.close()

        return {
            "status": "success",
            "file_path": output_path,
            "message": f"HWPX 문서가 생성되었습니다: {output_path}",
        }

    except Exception as exc:
        logger.error("HWPX 빌드 실패: %s", exc, exc_info=True)
        return {
            "status": "error",
            "message": f"HWPX 빌드 중 오류 발생: {exc}",
        }


def _make_title_content(text: str):
    """제목용 간이 TextContent 객체를 생성한다."""
    from react_system.document_schema import TextContent
    return TextContent(text=text, bold=True)


def _process_element(hwpx_doc, element, bold_char_pr_id):
    """DocumentElement의 type에 따라 적절한 변환 함수를 호출한다."""
    etype = element.type
    content = element.content

    if etype == "heading":
        _add_heading(hwpx_doc, content, bold_char_pr_id)
    elif etype == "paragraph":
        _add_paragraph(hwpx_doc, content)
    elif etype == "table":
        _add_table(hwpx_doc, content)
    elif etype == "list":
        _add_list(hwpx_doc, content)
    else:
        logger.warning("알 수 없는 요소 타입: %s", etype)
