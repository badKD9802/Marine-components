"""
문서 생성 중간 포맷 스키마

LLM이 생성하는 각 섹션의 출력 포맷을 정의한다.
Worker LLM → JSON (이 스키마) → Builder(HWPX/PPTX/XLSX) → 네이티브 파일
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


# ─── 요소 타입 ───

class TextContent(BaseModel):
    """텍스트 콘텐츠"""
    text: str
    bold: bool = False
    font_size: Optional[int] = None  # pt 단위
    alignment: Optional[Literal["left", "center", "right"]] = None


class TableColumn(BaseModel):
    """테이블 열 정의"""
    name: str
    width: Optional[int] = None   # 비율 (합계 100 기준)
    align: Literal["left", "center", "right"] = "left"


class MergeCell(BaseModel):
    """셀 병합 정의"""
    start_row: int
    start_col: int
    end_row: int
    end_col: int
    value: str = ""


class TableContent(BaseModel):
    """테이블 콘텐츠"""
    caption: Optional[str] = None
    columns: list[TableColumn]
    rows: list[list[str]]
    merge: Optional[list[MergeCell]] = None


class ListContent(BaseModel):
    """목록 콘텐츠"""
    items: list[str]
    list_type: Literal["bullet", "numbered"] = "bullet"


# ─── 문서 요소 ───

class DocumentElement(BaseModel):
    """문서를 구성하는 개별 요소"""
    type: Literal["heading", "paragraph", "table", "list"]
    content: Union[TextContent, TableContent, ListContent]


# ─── 섹션 출력 ───

class SectionOutput(BaseModel):
    """Worker LLM이 생성하는 섹션 결과물"""
    section_id: str
    section_title: str
    elements: list[DocumentElement]


# ─── 문서 전체 ───

class DocumentOutput(BaseModel):
    """전체 문서 결과물 (섹션 모음)"""
    title: str
    doc_type: str  # "보고서", "공문", "기획서" 등
    sections: list[SectionOutput]


# ─── 리뷰 결과 ───

class ReviewScore(BaseModel):
    """개별 평가 기준 점수"""
    criterion: str
    score: float  # 0.0 또는 1.0
    feedback: str = ""


class ReviewResult(BaseModel):
    """Reviewer 에이전트의 평가 결과"""
    passed: bool
    total_score: float  # 0.0 ~ 1.0
    scores: list[ReviewScore]
    feedback: list[str] = Field(default_factory=list)  # 미달 항목 피드백
