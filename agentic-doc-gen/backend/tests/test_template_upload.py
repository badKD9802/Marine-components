"""
양식/예시 업로드 파이프라인 테스트

template_upload.py의 함수들을 검증한다:
- parse_hwpx_to_sections: HWPX 파일 파싱 (python-hwpx 없는 환경 포함)
- split_content_to_sections: 텍스트 자동 분할
- upload_template: 양식 업로드 (TemplateStore.insert mock)
- upload_example: 예시 업로드 (TemplateStore.insert mock)
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 프로젝트 모듈
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from react_system.template_upload import (
    parse_hwpx_to_sections,
    split_content_to_sections,
    upload_example,
    upload_template,
)


# ─── 헬퍼 ───


def _run(coro):
    """async 함수를 동기적으로 실행하는 헬퍼."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_mock_store():
    """TemplateStore mock 생성."""
    store = MagicMock()
    store.insert = AsyncMock()
    return store


def _dummy_embedding_fn():
    """더미 임베딩 함수 (테스트용)."""
    async def embed(texts):
        return [[0.1] * 1024 for _ in texts]
    return embed


def _dummy_tokenize_fn():
    """더미 토크나이즈 함수 (테스트용)."""
    def tokenize(text):
        return {hash(w) % (2**31): 1.0 for w in text.split()}
    return tokenize


# ─── 테스트 1: split_content_to_sections ───


class TestSplitContentToSections:
    """텍스트 자동 분할 기능 테스트"""

    def test_should_return_single_section_for_short_text(self):
        """짧은 텍스트는 단일 섹션으로 반환해야 한다."""
        result = split_content_to_sections("짧은 텍스트입니다.")
        assert len(result) == 1
        assert result[0]["content"] == "짧은 텍스트입니다."

    def test_should_split_on_double_newline(self):
        """이중 줄바꿈 기준으로 분할해야 한다 (각 문단이 max_chars 초과 시)."""
        content = "첫 번째 문단입니다.\n\n두 번째 문단입니다.\n\n세 번째 문단입니다."
        # max_chars를 각 문단 길이 이하로 설정하여 분할 유도
        result = split_content_to_sections(content, max_chars=15)
        assert len(result) == 3
        assert result[0]["content"] == "첫 번째 문단입니다."
        assert result[1]["content"] == "두 번째 문단입니다."
        assert result[2]["content"] == "세 번째 문단입니다."

    def test_should_merge_small_paragraphs_within_max_chars(self):
        """짧은 문단들은 max_chars 이내로 합쳐야 한다."""
        content = "가\n\n나\n\n다"
        result = split_content_to_sections(content, max_chars=100)
        # 모두 합쳐도 100자 이하이므로 1개 섹션
        assert len(result) == 1
        assert "가" in result[0]["content"]
        assert "나" in result[0]["content"]
        assert "다" in result[0]["content"]

    def test_should_not_exceed_max_chars_per_section(self):
        """각 섹션이 max_chars를 초과하지 않아야 한다."""
        # 각 문단이 20자 정도, max_chars=30이면 합쳐질 수 없다
        content = "이것은 첫 번째 긴 문단입니다.\n\n이것은 두 번째 긴 문단입니다."
        result = split_content_to_sections(content, max_chars=30)
        assert len(result) == 2
        for section in result:
            assert len(section["content"]) <= 30

    def test_should_have_title_field_in_each_section(self):
        """각 섹션에 title 필드가 있어야 한다."""
        result = split_content_to_sections("텍스트")
        assert "title" in result[0]

    def test_should_generate_sequential_section_titles(self):
        """섹션 제목은 순차적으로 생성되어야 한다."""
        content = "첫 번째 문단입니다.\n\n두 번째 문단입니다."
        result = split_content_to_sections(content, max_chars=15)
        assert len(result) == 2
        assert result[0]["title"] == "섹션 1"
        assert result[1]["title"] == "섹션 2"

    def test_should_return_empty_list_for_empty_content(self):
        """빈 문자열은 빈 리스트를 반환해야 한다."""
        result = split_content_to_sections("")
        assert result == []

    def test_should_strip_whitespace_from_paragraphs(self):
        """각 문단의 앞뒤 공백을 제거해야 한다."""
        content = "  앞뒤 공백  \n\n  다른 문단  "
        result = split_content_to_sections(content, max_chars=50)
        for section in result:
            assert section["content"] == section["content"].strip()


# ─── 테스트 2: parse_hwpx_to_sections ───


class TestParseHwpxToSections:
    """HWPX 파일 파싱 테스트"""

    def test_should_return_single_section_when_hwpx_not_installed(self):
        """python-hwpx가 없으면 파일 전체를 단일 섹션으로 반환해야 한다."""
        # python-hwpx import를 실패하도록 mock
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("전체 내용입니다.")
            f.flush()
            tmp_path = f.name

        try:
            with patch(
                "react_system.template_upload._import_hwpx_text_extractor",
                return_value=None,
            ):
                result = parse_hwpx_to_sections(tmp_path)
            assert len(result) == 1
            assert result[0]["content"] == "전체 내용입니다."
            assert result[0]["title"] == "전체"
        finally:
            os.unlink(tmp_path)

    def test_should_parse_sections_when_hwpx_installed(self):
        """python-hwpx가 있으면 섹션별로 파싱해야 한다."""
        # TextExtractor mock 설정
        mock_para1 = MagicMock()
        mock_para1.text.return_value = "첫 번째 문단"
        mock_para2 = MagicMock()
        mock_para2.text.return_value = "두 번째 문단"

        mock_section1 = MagicMock()
        mock_section2 = MagicMock()

        mock_extractor = MagicMock()
        mock_extractor.__enter__ = MagicMock(return_value=mock_extractor)
        mock_extractor.__exit__ = MagicMock(return_value=False)
        mock_extractor.iter_sections.return_value = [mock_section1, mock_section2]
        mock_extractor.iter_paragraphs.side_effect = [
            [mock_para1],
            [mock_para2],
        ]

        MockTextExtractor = MagicMock(return_value=mock_extractor)

        with patch(
            "react_system.template_upload._import_hwpx_text_extractor",
            return_value=MockTextExtractor,
        ):
            result = parse_hwpx_to_sections("/dummy/path.hwpx")

        assert len(result) == 2
        assert result[0]["content"] == "첫 번째 문단"
        assert result[1]["content"] == "두 번째 문단"

    def test_should_skip_empty_sections(self):
        """빈 섹션은 건너뛰어야 한다."""
        mock_para1 = MagicMock()
        mock_para1.text.return_value = "내용 있음"
        mock_para_empty = MagicMock()
        mock_para_empty.text.return_value = ""

        mock_section1 = MagicMock()
        mock_section2 = MagicMock()

        mock_extractor = MagicMock()
        mock_extractor.__enter__ = MagicMock(return_value=mock_extractor)
        mock_extractor.__exit__ = MagicMock(return_value=False)
        mock_extractor.iter_sections.return_value = [mock_section1, mock_section2]
        mock_extractor.iter_paragraphs.side_effect = [
            [mock_para_empty],
            [mock_para1],
        ]

        MockTextExtractor = MagicMock(return_value=mock_extractor)

        with patch(
            "react_system.template_upload._import_hwpx_text_extractor",
            return_value=MockTextExtractor,
        ):
            result = parse_hwpx_to_sections("/dummy/path.hwpx")

        assert len(result) == 1
        assert result[0]["content"] == "내용 있음"


# ─── 테스트 3: upload_template ───


class TestUploadTemplate:
    """양식 업로드 기능 테스트"""

    def test_should_create_template_record(self):
        """양식 전체를 chunk_type='template'으로 삽입해야 한다."""
        store = _make_mock_store()
        result = _run(upload_template(
            file_path=None,
            template_id="test001",
            title="테스트 양식",
            category="보고서",
            store=store,
        ))

        assert result["status"] == "success"
        assert result["template_id"] == "test001"

        # insert 호출 검증
        store.insert.assert_called_once()
        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]

        # 첫 번째 레코드는 template 타입
        template_rec = records[0]
        assert template_rec["chunk_type"] == "template"
        assert template_rec["id"] == "tpl_test001"
        assert template_rec["template_id"] == "test001"
        assert template_rec["title"] == "테스트 양식"
        assert template_rec["category"] == "보고서"
        assert template_rec["visibility"] == "public"

    def test_should_create_section_records_when_sections_provided(self):
        """sections가 제공되면 각 섹션을 chunk_type='section'으로 삽입해야 한다."""
        store = _make_mock_store()
        sections = [
            {"title": "개요", "content": "개요 내용"},
            {"title": "본론", "content": "본론 내용"},
        ]
        result = _run(upload_template(
            file_path=None,
            template_id="test002",
            title="섹션 양식",
            category="기획서",
            sections=sections,
            store=store,
        ))

        assert result["chunk_count"] == 3  # 1 template + 2 sections

        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]

        # 섹션 레코드 검증
        sec_records = [r for r in records if r["chunk_type"] == "section"]
        assert len(sec_records) == 2
        assert sec_records[0]["id"] == "tpl_test002_sec00"
        assert sec_records[0]["parent_id"] == "tpl_test002"
        assert sec_records[0]["title"] == "개요"
        assert sec_records[0]["content"] == "개요 내용"
        assert sec_records[1]["id"] == "tpl_test002_sec01"

    def test_should_pass_embedding_and_tokenize_fns_to_store(self):
        """embedding_fn과 tokenize_fn을 store.insert에 전달해야 한다."""
        store = _make_mock_store()
        result = _run(upload_template(
            file_path=None,
            template_id="test003",
            title="함수 전달 테스트",
            category="공문",
            store=store,
        ))

        call_args = store.insert.call_args
        # embedding_fn과 tokenize_fn이 키워드로 전달되어야 함
        assert "embedding_fn" in call_args[1]
        assert "tokenize_fn" in call_args[1]

    def test_should_include_subcategory_and_metadata(self):
        """subcategory와 metadata가 레코드에 포함되어야 한다."""
        store = _make_mock_store()
        result = _run(upload_template(
            file_path=None,
            template_id="test004",
            title="메타데이터 테스트",
            category="보고서",
            subcategory="월간보고",
            metadata={"version": "1.0"},
            store=store,
        ))

        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]
        template_rec = records[0]
        assert template_rec["subcategory"] == "월간보고"
        assert template_rec["metadata"]["version"] == "1.0"

    def test_should_auto_split_content_when_no_sections(self):
        """sections가 없고 file_path의 내용이 길면 자동 분할해야 한다."""
        store = _make_mock_store()
        import tempfile
        long_content = "문단A 내용\n\n문단B 내용\n\n문단C 내용"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(long_content)
            f.flush()
            tmp_path = f.name

        try:
            # HWPX 파싱 우회
            with patch(
                "react_system.template_upload._import_hwpx_text_extractor",
                return_value=None,
            ):
                result = _run(upload_template(
                    file_path=tmp_path,
                    template_id="test005",
                    title="자동분할 테스트",
                    category="기획서",
                    store=store,
                ))

            call_args = store.insert.call_args
            records = call_args[1].get("records") or call_args[0][0]

            # template 1개 + 자동 분할된 section들
            template_recs = [r for r in records if r["chunk_type"] == "template"]
            section_recs = [r for r in records if r["chunk_type"] == "section"]
            assert len(template_recs) == 1
            assert len(section_recs) >= 1
        finally:
            os.unlink(tmp_path)


# ─── 테스트 4: upload_example ───


class TestUploadExample:
    """예시 업로드 기능 테스트"""

    def test_should_create_example_record_with_content(self):
        """content로 예시를 chunk_type='example'로 삽입해야 한다."""
        store = _make_mock_store()
        result = _run(upload_example(
            content="예시 내용입니다.",
            template_id="tpl001",
            title="예시 제목",
            category="보고서",
            store=store,
        ))

        assert result["status"] == "success"
        assert "example_id" in result

        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]

        example_rec = records[0]
        assert example_rec["chunk_type"] == "example"
        assert example_rec["template_id"] == "tpl001"
        assert example_rec["title"] == "예시 제목"
        assert example_rec["content"] == "예시 내용입니다."
        assert example_rec["visibility"] == "public"

    def test_should_set_private_visibility_with_user_id(self):
        """user_id가 있으면 visibility='user:{user_id}'로 설정해야 한다."""
        store = _make_mock_store()
        result = _run(upload_example(
            content="비공개 예시",
            template_id="tpl002",
            title="비공개 예시",
            category="공문",
            user_id="user123",
            store=store,
        ))

        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]

        example_rec = records[0]
        assert example_rec["visibility"] == "user:user123"
        assert example_rec["user_id"] == "user123"

    def test_should_set_public_visibility_without_user_id(self):
        """user_id가 없으면 visibility='public'으로 설정해야 한다."""
        store = _make_mock_store()
        result = _run(upload_example(
            content="공개 예시",
            template_id="tpl003",
            title="공개 예시",
            category="기획서",
            store=store,
        ))

        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]

        example_rec = records[0]
        assert example_rec["visibility"] == "public"
        assert example_rec["user_id"] == ""

    def test_should_generate_example_id_with_pub_prefix(self):
        """user_id가 없으면 example ID에 'pub' 접두사가 있어야 한다."""
        store = _make_mock_store()
        result = _run(upload_example(
            content="공개",
            store=store,
        ))

        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]
        assert records[0]["id"].startswith("ex_pub_")

    def test_should_generate_example_id_with_user_prefix(self):
        """user_id가 있으면 example ID에 user_id 접두사가 있어야 한다."""
        store = _make_mock_store()
        result = _run(upload_example(
            content="비공개",
            user_id="myuser",
            store=store,
        ))

        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]
        assert records[0]["id"].startswith("ex_myuser_")

    def test_should_create_section_records_for_example(self):
        """sections가 제공되면 예시에도 섹션 레코드를 생성해야 한다."""
        store = _make_mock_store()
        sections = [
            {"title": "도입", "content": "도입 내용"},
            {"title": "결론", "content": "결론 내용"},
        ]
        result = _run(upload_example(
            content="예시 전체 내용",
            sections=sections,
            store=store,
        ))

        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]

        example_recs = [r for r in records if r["chunk_type"] == "example"]
        section_recs = [r for r in records if r["chunk_type"] == "section"]
        assert len(example_recs) == 1
        assert len(section_recs) == 2
        assert result["chunk_count"] == 3

    def test_should_pass_embedding_and_tokenize_fns_to_store(self):
        """embedding_fn과 tokenize_fn을 store.insert에 전달해야 한다."""
        store = _make_mock_store()
        result = _run(upload_example(
            content="예시",
            store=store,
        ))

        call_args = store.insert.call_args
        assert "embedding_fn" in call_args[1]
        assert "tokenize_fn" in call_args[1]

    def test_should_include_metadata_in_record(self):
        """metadata가 레코드에 포함되어야 한다."""
        store = _make_mock_store()
        result = _run(upload_example(
            content="메타데이터 예시",
            metadata={"source": "수동입력"},
            store=store,
        ))

        call_args = store.insert.call_args
        records = call_args[1].get("records") or call_args[0][0]
        assert records[0]["metadata"]["source"] == "수동입력"
