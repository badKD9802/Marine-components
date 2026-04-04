"""
문서 생성 도구 등록 테스트

tool_definitions.py에 3개 도구 스키마가 등록되었는지,
tool_registry.py에 3개 도구가 디스패치 가능한지 검증한다.

도구 3개:
  - generate_document (문서 생성)
  - search_document_templates (양식 검색)
  - upload_document_example (예시 업로드)
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================
# tool_definitions.py 스키마 테스트
# ============================================================


class TestDocumentToolDefinitions:
    """tool_definitions.py에 문서 도구 스키마가 올바르게 등록되었는지 검증."""

    def test_generate_document_tool_in_definitions(self):
        from react_system.tool_definitions import TOOLS

        names = [t["function"]["name"] for t in TOOLS]
        assert "generate_document" in names

    def test_search_document_templates_tool_in_definitions(self):
        from react_system.tool_definitions import TOOLS

        names = [t["function"]["name"] for t in TOOLS]
        assert "search_document_templates" in names

    def test_upload_document_example_tool_in_definitions(self):
        from react_system.tool_definitions import TOOLS

        names = [t["function"]["name"] for t in TOOLS]
        assert "upload_document_example" in names

    def test_generate_document_schema_has_required_params(self):
        from react_system.tool_definitions import TOOLS

        tool = next(
            t for t in TOOLS if t["function"]["name"] == "generate_document"
        )
        params = tool["function"]["parameters"]["properties"]
        assert "user_request" in params
        assert "template_id" in params
        assert "reference_content" in params
        assert "example_ids" in params
        assert "output_formats" in params
        # user_request는 required
        assert "user_request" in tool["function"]["parameters"]["required"]

    def test_search_document_templates_schema_has_required_params(self):
        from react_system.tool_definitions import TOOLS

        tool = next(
            t for t in TOOLS
            if t["function"]["name"] == "search_document_templates"
        )
        params = tool["function"]["parameters"]["properties"]
        assert "query" in params
        assert "category" in params
        assert "limit" in params
        # query는 required
        assert "query" in tool["function"]["parameters"]["required"]

    def test_upload_document_example_schema_has_required_params(self):
        from react_system.tool_definitions import TOOLS

        tool = next(
            t for t in TOOLS
            if t["function"]["name"] == "upload_document_example"
        )
        params = tool["function"]["parameters"]["properties"]
        assert "content" in params
        assert "template_id" in params
        assert "title" in params
        assert "category" in params
        # content는 required
        assert "content" in tool["function"]["parameters"]["required"]

    def test_generate_document_output_formats_enum(self):
        """output_formats의 items에 enum이 올바르게 정의되었는지."""
        from react_system.tool_definitions import TOOLS

        tool = next(
            t for t in TOOLS if t["function"]["name"] == "generate_document"
        )
        output_formats = tool["function"]["parameters"]["properties"]["output_formats"]
        assert output_formats["type"] == "array"
        assert set(output_formats["items"]["enum"]) == {"hwpx", "pptx", "xlsx"}

    def test_all_three_tools_have_type_function(self):
        """3개 도구 모두 type='function' 형식."""
        from react_system.tool_definitions import TOOLS

        tool_names = [
            "generate_document",
            "search_document_templates",
            "upload_document_example",
        ]
        for name in tool_names:
            tool = next(
                t for t in TOOLS if t["function"]["name"] == name
            )
            assert tool["type"] == "function", f"{name}의 type이 'function'이 아님"


# ============================================================
# tool_registry.py 등록 테스트
# ============================================================


class TestDocumentToolRegistry:
    """tool_registry.py에 문서 도구가 올바르게 등록되었는지 검증."""

    def test_generate_document_registered(self):
        from react_system.tool_registry import ToolRegistry

        registry = ToolRegistry()
        assert registry.has_function("generate_document")

    def test_search_document_templates_registered(self):
        from react_system.tool_registry import ToolRegistry

        registry = ToolRegistry()
        assert registry.has_function("search_document_templates")

    def test_upload_document_example_registered(self):
        from react_system.tool_registry import ToolRegistry

        registry = ToolRegistry()
        assert registry.has_function("upload_document_example")

    def test_all_three_in_list_functions(self):
        from react_system.tool_registry import ToolRegistry

        registry = ToolRegistry()
        funcs = registry.list_functions()
        assert "generate_document" in funcs
        assert "search_document_templates" in funcs
        assert "upload_document_example" in funcs
