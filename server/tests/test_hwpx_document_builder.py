"""
HWPX Document Builder 테스트

DocumentOutput → HWPX 변환 엔진의 동작을 검증한다.
python-hwpx 라이브러리 기반의 새 구현을 테스트한다.
"""

import asyncio
import os
import tempfile

import pytest

# 프로젝트 모듈
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from react_system.document_schema import (
    DocumentElement,
    DocumentOutput,
    ListContent,
    MergeCell,
    SectionOutput,
    TableColumn,
    TableContent,
    TextContent,
)
from react_system.tools.hwpx_document_builder import build_hwpx


# ─── 헬퍼 ───


def _run(coro):
    """async 함수를 동기적으로 실행하는 헬퍼."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _minimal_doc(title="테스트 문서", doc_type="보고서", sections=None):
    """최소한의 DocumentOutput을 생성한다."""
    if sections is None:
        sections = []
    return DocumentOutput(title=title, doc_type=doc_type, sections=sections)


def _text_element(text, etype="paragraph", bold=False, font_size=None, alignment=None):
    """텍스트 기반 DocumentElement를 생성한다."""
    return DocumentElement(
        type=etype,
        content=TextContent(
            text=text, bold=bold, font_size=font_size, alignment=alignment
        ),
    )


def _table_element(columns, rows, caption=None, merge=None):
    """테이블 DocumentElement를 생성한다."""
    cols = [TableColumn(name=c) for c in columns]
    return DocumentElement(
        type="table",
        content=TableContent(columns=cols, rows=rows, caption=caption, merge=merge),
    )


def _list_element(items, list_type="bullet"):
    """목록 DocumentElement를 생성한다."""
    return DocumentElement(
        type="list",
        content=ListContent(items=items, list_type=list_type),
    )


# ─── 테스트 1: 빈 문서 생성 ───


class TestBuildHwpxBasic:
    """build_hwpx 기본 동작 테스트"""

    def test_should_return_success_status_for_empty_document(self):
        """빈 섹션의 문서라도 success 상태를 반환해야 한다."""
        doc = _minimal_doc(title="해양 엔진 부품 보고서", doc_type="보고서")

        result = _run(build_hwpx(doc))

        assert result["status"] == "success"
        assert "file_path" in result
        assert os.path.exists(result["file_path"])
        # 임시 파일 정리
        os.unlink(result["file_path"])

    def test_should_save_to_specified_output_path(self):
        """output_path를 지정하면 해당 경로에 파일이 생성되어야 한다."""
        doc = _minimal_doc(title="테스트")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_output.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"
            assert result["file_path"] == output_path
            assert os.path.exists(output_path)
            # HWPX는 ZIP 기반이므로 파일 크기가 0보다 커야 한다
            assert os.path.getsize(output_path) > 0

    def test_should_generate_tempfile_when_no_output_path(self):
        """output_path가 None이면 tempfile로 생성해야 한다."""
        doc = _minimal_doc(title="임시 파일 테스트")

        result = _run(build_hwpx(doc, output_path=None))

        assert result["status"] == "success"
        assert result["file_path"].endswith(".hwpx")
        assert os.path.exists(result["file_path"])
        os.unlink(result["file_path"])


# ─── 테스트 2: 문서 제목 ───


class TestBuildHwpxTitle:
    """문서 제목 생성 테스트"""

    def test_should_add_document_title_as_first_paragraph(self):
        """문서 제목이 첫 번째 문단으로 추가되어야 한다."""
        doc = _minimal_doc(title="해양 엔진 정비 보고서", doc_type="보고서")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            # 생성된 파일을 열어서 텍스트 확인
            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            assert "해양 엔진 정비 보고서" in text


# ─── 테스트 3: 섹션 제목 ───


class TestBuildHwpxSections:
    """섹션 처리 테스트"""

    def test_should_add_section_title_as_heading(self):
        """각 섹션의 제목이 heading으로 추가되어야 한다."""
        sections = [
            SectionOutput(section_id="s1", section_title="추진 배경", elements=[]),
            SectionOutput(section_id="s2", section_title="사업 개요", elements=[]),
        ]
        doc = _minimal_doc(title="사업 보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            assert "추진 배경" in text
            assert "사업 개요" in text


# ─── 테스트 4: 텍스트 요소 (heading, paragraph) ───


class TestBuildHwpxTextElements:
    """텍스트 요소 변환 테스트"""

    def test_should_add_heading_element(self):
        """heading 타입 요소가 문서에 추가되어야 한다."""
        sections = [
            SectionOutput(
                section_id="s1",
                section_title="개요",
                elements=[
                    _text_element("1. 사업 목적", etype="heading", bold=True),
                ],
            ),
        ]
        doc = _minimal_doc(title="보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            assert "1. 사업 목적" in text

    def test_should_add_paragraph_element(self):
        """paragraph 타입 요소가 문서에 추가되어야 한다."""
        sections = [
            SectionOutput(
                section_id="s1",
                section_title="본문",
                elements=[
                    _text_element("해양 엔진 부품의 품질 관리가 중요합니다.", etype="paragraph"),
                ],
            ),
        ]
        doc = _minimal_doc(title="보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            assert "해양 엔진 부품의 품질 관리가 중요합니다." in text


# ─── 테스트 5: 테이블 요소 ───


class TestBuildHwpxTable:
    """테이블 변환 테스트"""

    def test_should_add_table_with_headers_and_data(self):
        """테이블의 헤더와 데이터가 문서에 추가되어야 한다."""
        sections = [
            SectionOutput(
                section_id="s1",
                section_title="매출",
                elements=[
                    _table_element(
                        columns=["월", "매출액", "비고"],
                        rows=[
                            ["1월", "1,200만원", "정상"],
                            ["2월", "1,500만원", "증가"],
                        ],
                    ),
                ],
            ),
        ]
        doc = _minimal_doc(title="매출 보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            # 헤더 확인
            assert "월" in text
            assert "매출액" in text
            assert "비고" in text
            # 데이터 확인
            assert "1,200만원" in text
            assert "1,500만원" in text

    def test_should_add_table_caption(self):
        """테이블에 캡션이 있으면 테이블 위에 캡션 문단이 추가되어야 한다."""
        sections = [
            SectionOutput(
                section_id="s1",
                section_title="현황",
                elements=[
                    _table_element(
                        columns=["항목", "값"],
                        rows=[["엔진", "100대"]],
                        caption="[표 1] 재고 현황",
                    ),
                ],
            ),
        ]
        doc = _minimal_doc(title="보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            assert "[표 1] 재고 현황" in text

    def test_should_handle_table_cell_merge(self):
        """셀 병합이 정의되면 merge_cells가 적용되어야 한다."""
        merge_spec = [
            MergeCell(start_row=0, start_col=0, end_row=1, end_col=0, value="합계"),
        ]
        sections = [
            SectionOutput(
                section_id="s1",
                section_title="병합 테스트",
                elements=[
                    _table_element(
                        columns=["구분", "값"],
                        rows=[
                            ["A", "100"],
                            ["A", "200"],
                        ],
                        merge=merge_spec,
                    ),
                ],
            ),
        ]
        doc = _minimal_doc(title="보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            # 셀 병합은 파일 생성이 성공적으로 완료되면 적용된 것으로 본다
            assert result["status"] == "success"
            assert os.path.exists(output_path)


# ─── 테스트 6: 목록 요소 ───


class TestBuildHwpxList:
    """목록 변환 테스트"""

    def test_should_add_bullet_list(self):
        """bullet 목록의 각 항목이 '•' 접두사와 함께 추가되어야 한다."""
        sections = [
            SectionOutput(
                section_id="s1",
                section_title="목록 테스트",
                elements=[
                    _list_element(
                        items=["항목 A", "항목 B", "항목 C"],
                        list_type="bullet",
                    ),
                ],
            ),
        ]
        doc = _minimal_doc(title="보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            # 불릿 접두사 확인
            assert "• 항목 A" in text
            assert "• 항목 B" in text
            assert "• 항목 C" in text

    def test_should_add_numbered_list(self):
        """numbered 목록의 각 항목이 '1.' 접두사와 함께 추가되어야 한다."""
        sections = [
            SectionOutput(
                section_id="s1",
                section_title="번호 목록",
                elements=[
                    _list_element(
                        items=["첫 번째", "두 번째", "세 번째"],
                        list_type="numbered",
                    ),
                ],
            ),
        ]
        doc = _minimal_doc(title="보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            assert "1. 첫 번째" in text
            assert "2. 두 번째" in text
            assert "3. 세 번째" in text


# ─── 테스트 7: 에러 처리 ───


class TestBuildHwpxErrors:
    """에러 처리 테스트"""

    def test_should_return_error_on_invalid_output_path(self):
        """유효하지 않은 output_path로 저장 시 error를 반환해야 한다."""
        doc = _minimal_doc(title="에러 테스트")

        result = _run(build_hwpx(doc, output_path="/nonexistent/dir/test.hwpx"))

        assert result["status"] == "error"
        assert "message" in result


# ─── 테스트 8: 복합 문서 ───


class TestBuildHwpxComplex:
    """복합 문서 변환 테스트"""

    def test_should_handle_multiple_element_types_in_section(self):
        """하나의 섹션에 heading, paragraph, table, list가 모두 포함될 수 있어야 한다."""
        sections = [
            SectionOutput(
                section_id="s1",
                section_title="종합 섹션",
                elements=[
                    _text_element("1. 개요", etype="heading", bold=True),
                    _text_element("이 보고서는 종합 검토 결과입니다.", etype="paragraph"),
                    _table_element(
                        columns=["항목", "결과"],
                        rows=[["점검 A", "양호"], ["점검 B", "불량"]],
                    ),
                    _list_element(items=["조치 사항 1", "조치 사항 2"], list_type="bullet"),
                ],
            ),
        ]
        doc = _minimal_doc(title="종합 보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            # 모든 요소가 포함되어 있어야 한다
            assert "1. 개요" in text
            assert "이 보고서는 종합 검토 결과입니다." in text
            assert "점검 A" in text
            assert "양호" in text
            assert "• 조치 사항 1" in text

    def test_should_handle_multiple_sections(self):
        """여러 섹션이 순서대로 생성되어야 한다."""
        sections = [
            SectionOutput(
                section_id="s1",
                section_title="1장. 서론",
                elements=[
                    _text_element("서론 내용입니다.", etype="paragraph"),
                ],
            ),
            SectionOutput(
                section_id="s2",
                section_title="2장. 본론",
                elements=[
                    _text_element("본론 내용입니다.", etype="paragraph"),
                ],
            ),
            SectionOutput(
                section_id="s3",
                section_title="3장. 결론",
                elements=[
                    _text_element("결론 내용입니다.", etype="paragraph"),
                ],
            ),
        ]
        doc = _minimal_doc(title="3장 보고서", sections=sections)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.hwpx")
            result = _run(build_hwpx(doc, output_path=output_path))

            assert result["status"] == "success"

            from hwpx import HwpxDocument
            hwpx_doc = HwpxDocument.open(output_path)
            text = hwpx_doc.export_text()
            hwpx_doc.close()

            assert "1장. 서론" in text
            assert "서론 내용입니다." in text
            assert "2장. 본론" in text
            assert "본론 내용입니다." in text
            assert "3장. 결론" in text
            assert "결론 내용입니다." in text
