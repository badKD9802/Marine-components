"""
문서 생성 계획 도구

사용자 요청을 분석하여 문서 생성 계획을 수립한다.
ReAct 에이전트의 tool로 호출됨.

주요 기능:
- 양식 미지정 시: 양식 추천 (상위 5개)
- 양식 지정 시: 섹션별 SectionPlan 생성 → DocumentPlan 반환
"""

import logging
from typing import Optional

from pydantic import BaseModel

from react_system.template_search import (
    get_examples_for_template,
    get_template_detail,
    search_templates,
)

logger = logging.getLogger(__name__)

# 예시 최대 개수
MAX_EXAMPLES = 5
# 양식 추천 최대 개수
MAX_CANDIDATES = 5


# ─── Pydantic 모델 ───


class SectionPlan(BaseModel):
    """개별 섹션 생성 계획"""

    section_index: int
    section_title: str
    instruction: str  # Writer에게 전달할 지시사항
    template_content: str  # 양식에서 가져온 섹션 구조
    examples: list[str]  # 잘 쓴 예시 원본 (해당 섹션)
    reference_content: str  # 참고문서에서 관련 내용


class DocumentPlan(BaseModel):
    """문서 생성 계획"""

    title: str
    doc_type: str  # "보고서", "공문" 등
    template_id: str
    output_formats: list[str]  # ["hwpx", "pptx", "xlsx"]
    sections: list[SectionPlan]
    reference_summary: str  # 참고문서 요약


# ─── 헬퍼 ───


def _extract_candidates(templates: list[dict], limit: int = MAX_CANDIDATES) -> list[dict]:
    """검색 결과에서 양식 후보 목록을 추출한다."""
    candidates = []
    for tpl in templates[:limit]:
        candidates.append({
            "id": tpl.get("id", ""),
            "title": tpl.get("title", ""),
            "category": tpl.get("category", ""),
            "score": tpl.get("score", 0.0),
        })
    return candidates


def _filter_examples_by_ids(
    examples: list[dict],
    example_ids: Optional[list[str]],
) -> list[dict]:
    """example_ids가 지정되면 해당 예시만 필터링, 아니면 전체 반환 (최대 MAX_EXAMPLES개)."""
    if example_ids is not None:
        filtered = [ex for ex in examples if ex.get("id") in example_ids]
        return filtered[:MAX_EXAMPLES]
    return examples[:MAX_EXAMPLES]


def _map_examples_to_section(
    examples: list[dict],
    section_id: str,
) -> list[str]:
    """
    예시를 섹션에 매핑한다.

    - 예시가 섹션별로 분리되어 있으면 (parent_id == section_id) 해당 부분만 사용
    - 분리되어 있지 않으면 예시 전체 content를 사용
    """
    # 섹션별 분리된 예시가 있는지 확인
    section_examples = [
        ex for ex in examples
        if ex.get("parent_id") == section_id and ex.get("chunk_type") == "example"
    ]

    if section_examples:
        return [ex.get("content", "") for ex in section_examples]

    # 분리되지 않은 경우: 전체 예시의 content를 각 섹션에 전달
    return [ex.get("content", "") for ex in examples]


def _build_section_plans(
    sections: list[dict],
    examples: list[dict],
    reference_content: str,
) -> list[SectionPlan]:
    """섹션 목록에서 SectionPlan 리스트를 생성한다."""
    plans = []
    for idx, section in enumerate(sections):
        title = section.get("title", f"섹션 {idx + 1}")
        content = section.get("content", "")
        section_id = section.get("id", "")

        example_contents = _map_examples_to_section(examples, section_id)

        instruction = (
            f"이 섹션은 {title}입니다. "
            f"양식 구조를 따르고 예시의 문체를 참고하여 작성하세요."
        )

        plans.append(SectionPlan(
            section_index=idx,
            section_title=title,
            instruction=instruction,
            template_content=content,
            examples=example_contents,
            reference_content=reference_content,
        ))

    return plans


# ─── 메인 함수 ───


async def plan_document(
    user_request: str,
    template_id: str = None,
    reference_content: str = None,
    example_ids: list[str] = None,
    output_formats: list[str] = None,
    user_id: str = None,
    _auth=None,
    **kwargs,
) -> dict:
    """
    문서 생성 계획 수립.

    1. template_id가 있으면 → 양식 상세 + 섹션 가져오기
       template_id가 없으면 → user_request로 양식 추천 (상위 5개 반환)
    2. 예시 가져오기 (example_ids 지정 시 해당 예시, 아니면 자동 검색)
    3. 참고문서를 섹션별로 매핑
    4. 각 섹션의 SectionPlan 생성

    Returns:
        template_id가 없을 때:
        {
            "status": "need_template_selection",
            "candidates": [{"id", "title", "category", "score"}],
            "message": "어떤 양식으로 작성할까요?"
        }

        template_id가 있을 때:
        {
            "status": "success",
            "plan": DocumentPlan.model_dump(),
            "message": "문서 생성 계획이 수립되었습니다."
        }
    """
    try:
        # ── 양식 미지정: 양식 추천 ──
        if template_id is None:
            return await _handle_no_template(user_request, user_id)

        # ── 양식 지정: 계획 수립 ──
        return await _handle_with_template(
            user_request=user_request,
            template_id=template_id,
            reference_content=reference_content or "",
            example_ids=example_ids,
            output_formats=output_formats or ["hwpx"],
            user_id=user_id,
        )
    except Exception as e:
        logger.error(f"문서 계획 수립 실패: {e}")
        return {"status": "error", "message": str(e)}


async def _handle_no_template(user_request: str, user_id: str = None) -> dict:
    """양식 미지정 시 양식 검색 후 후보 반환."""
    search_result = await search_templates(
        query=user_request,
        user_id=user_id,
    )

    if search_result.get("status") != "success":
        return {
            "status": "error",
            "message": search_result.get("message", "양식 검색 실패"),
        }

    templates = search_result.get("templates", [])
    candidates = _extract_candidates(templates, limit=MAX_CANDIDATES)

    return {
        "status": "need_template_selection",
        "candidates": candidates,
        "message": "어떤 양식으로 작성할까요?",
    }


async def _handle_with_template(
    user_request: str,
    template_id: str,
    reference_content: str,
    example_ids: Optional[list[str]],
    output_formats: list[str],
    user_id: str = None,
) -> dict:
    """양식 지정 시 DocumentPlan 생성."""
    # 1. 양식 상세 + 섹션 가져오기
    detail_result = await get_template_detail(template_id)
    if detail_result.get("status") != "success":
        return {
            "status": "error",
            "message": detail_result.get("message", "양식 조회 실패"),
        }

    template = detail_result["template"]
    sections = detail_result.get("sections", [])

    # 2. 예시 가져오기
    examples_result = await get_examples_for_template(
        template_id=template_id,
        user_id=user_id,
    )
    raw_examples = []
    if examples_result.get("status") == "success":
        raw_examples = examples_result.get("examples", [])

    # 3. example_ids 필터링
    filtered_examples = _filter_examples_by_ids(raw_examples, example_ids)

    # 4. 섹션별 SectionPlan 생성
    section_plans = _build_section_plans(
        sections=sections,
        examples=filtered_examples,
        reference_content=reference_content,
    )

    # 5. DocumentPlan 생성
    plan = DocumentPlan(
        title=template.get("title", ""),
        doc_type=template.get("category", ""),
        template_id=template_id,
        output_formats=output_formats,
        sections=section_plans,
        reference_summary=reference_content,
    )

    return {
        "status": "success",
        "plan": plan.model_dump(),
        "message": "문서 생성 계획이 수립되었습니다.",
    }
