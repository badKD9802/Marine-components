"""
문서 생성 오케스트레이터

전체 문서 생성 파이프라인을 오케스트레이션하는 메인 도구.
Planner -> Writer (섹션별) -> Builder -> Reviewer -> (재작성) 파이프라인.
ReAct 에이전트의 tool로 호출됨.

단계:
1. [Plan] plan_document() 호출 -> DocumentPlan
2. [DB] create_document()로 문서 레코드 생성 (session_id 있을 때만)
3. [Write] 각 섹션별 write_section() 호출 -> SectionOutput들
4. [Build] 섹션 조립 -> DocumentOutput -> Builder 호출 (format별)
5. [Review] review_document() 호출 -> 통과/재작성
6. [Complete] update_document_status("completed")
"""

import logging
import uuid

from react_system import document_db
from react_system.document_schema import DocumentOutput, SectionOutput
from react_system.tools.document_planner import DocumentPlan, plan_document
from react_system.tools.document_reviewer import review_document
from react_system.tools.document_writer import write_section
from react_system.tools.hwpx_document_builder import build_hwpx
from react_system.tools.pptx_builder import build_pptx
from react_system.tools.xlsx_builder import build_xlsx

logger = logging.getLogger(__name__)

MAX_REVIEW_RETRIES = 2  # 최대 재작성 횟수


async def generate_document(
    user_request: str,
    template_id: str = None,
    reference_content: str = None,
    example_ids: list[str] = None,
    output_formats: list[str] = None,
    session_id: str = None,
    user_id: str = None,
    _auth=None,
    **kwargs,
) -> dict:
    """
    문서 생성 전체 파이프라인.

    Args:
        user_request: 사용자의 문서 생성 요청
        template_id: 사용할 양식 ID (없으면 양식 추천)
        reference_content: 참고할 문서 내용
        example_ids: 참고할 예시 ID 목록
        output_formats: 출력 형식 (기본: ['hwpx'])
        session_id: 대화 세션 ID (없으면 DB 저장 건너뜀)
        user_id: 사용자 ID
        _auth: AuthContext 인스턴스

    Returns:
        template_id 없을 때 (양식 추천):
        {
            "status": "need_template_selection",
            "candidates": [...],
            "message": "어떤 양식으로 작성할까요?"
        }

        성공 시:
        {
            "status": "success",
            "doc_id": "doc_xxx",
            "files": {"hwpx": "/path/to.hwpx", "pptx": "/path/to.pptx"},
            "review": {"passed": true, "total_score": 0.95, ...},
            "sections": [...],
            "message": "문서 생성 완료 (95점)"
        }

        에러 시:
        {"status": "error", "message": "..."}
    """
    try:
        # ── 1. Plan 단계 ──
        plan_result = await plan_document(
            user_request=user_request,
            template_id=template_id,
            reference_content=reference_content,
            example_ids=example_ids,
            output_formats=output_formats,
            user_id=user_id,
        )

        # 양식 선택 필요 시 그대로 반환
        if plan_result["status"] == "need_template_selection":
            return plan_result

        # 에러 시 그대로 반환
        if plan_result["status"] != "success":
            return plan_result

        plan = DocumentPlan(**plan_result["plan"])

        # ── 2. DB 레코드 생성 (session_id 있을 때만) ──
        doc_id = None
        if session_id is not None:
            try:
                doc_id = await document_db.create_document(
                    session_id=session_id,
                    template_id=plan.template_id,
                    title=plan.title,
                    doc_type=plan.doc_type,
                    user_id=user_id or "",
                )
            except Exception as e:
                logger.warning("DB 문서 레코드 생성 실패 (계속 진행): %s", e)

        # doc_id가 없으면 임시 ID 생성 (반환값용)
        result_doc_id = doc_id or f"doc_{uuid.uuid4().hex[:12]}"

        # ── 3. Write 단계: 각 섹션 생성 ──
        sections = await _write_all_sections(plan, doc_id)
        if not sections:
            return {
                "status": "error",
                "message": "섹션 생성 실패: 모든 섹션 작성에 실패했습니다.",
            }

        # ── 4. Build 단계: DocumentOutput 조립 + Builder 호출 ──
        doc_output = DocumentOutput(
            title=plan.title,
            doc_type=plan.doc_type,
            sections=sections,
        )
        files = await _build_all_formats(doc_output, plan.output_formats)

        # 양식 구조 문자열 (리뷰에 전달)
        template_structure = _extract_template_structure(plan)

        # ── 5. Review + Reflexion 단계 ──
        review = None
        for attempt in range(MAX_REVIEW_RETRIES + 1):
            review = await review_document(
                document_json=doc_output.model_dump_json(),
                original_request=user_request,
                template_structure=template_structure,
            )

            if review.get("passed", False):
                break

            # 마지막 시도가 아니면 재작성
            if attempt < MAX_REVIEW_RETRIES:
                feedback_list = review.get("feedback", [])
                sections = await _rewrite_sections_with_feedback(
                    plan, feedback_list, doc_id,
                )
                # 재빌드
                doc_output = DocumentOutput(
                    title=plan.title,
                    doc_type=plan.doc_type,
                    sections=sections,
                )
                files = await _build_all_formats(doc_output, plan.output_formats)

        # ── 6. DB 상태 업데이트 ──
        if doc_id is not None:
            try:
                await document_db.update_document_status(doc_id, "completed")
            except Exception as e:
                logger.warning("DB 상태 업데이트 실패 (계속 진행): %s", e)

        # 점수 메시지
        total_score = review.get("total_score", 0.0) if review else 0.0
        score_pct = int(round(total_score * 100))

        return {
            "status": "success",
            "doc_id": result_doc_id,
            "files": files,
            "review": review,
            "sections": [s.model_dump() for s in sections],
            "message": f"문서 생성 완료 ({score_pct}점)",
        }

    except Exception as e:
        logger.error("문서 생성 파이프라인 실패: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}


# ─── 내부 헬퍼 ───


async def _write_all_sections(
    plan: DocumentPlan,
    doc_id: str = None,
) -> list[SectionOutput]:
    """계획의 모든 섹션을 순차적으로 작성한다."""
    sections = []
    for sp in plan.sections:
        result = await write_section(
            section_index=sp.section_index,
            section_title=sp.section_title,
            instruction=sp.instruction,
            template_content=sp.template_content,
            examples=sp.examples,
            reference_content=sp.reference_content,
            doc_id=doc_id,
        )
        if result["status"] == "success":
            sections.append(SectionOutput(**result["section"]))
        else:
            logger.warning(
                "섹션 '%s' 작성 실패: %s",
                sp.section_title,
                result.get("message", ""),
            )
    return sections


async def _rewrite_sections_with_feedback(
    plan: DocumentPlan,
    feedback_list: list[str],
    doc_id: str = None,
) -> list[SectionOutput]:
    """리뷰 피드백을 반영하여 모든 섹션을 재작성한다."""
    feedback_str = "\n".join(feedback_list)
    sections = []
    for sp in plan.sections:
        enhanced_instruction = (
            sp.instruction + f"\n\n[이전 피드백]\n{feedback_str}"
        )
        result = await write_section(
            section_index=sp.section_index,
            section_title=sp.section_title,
            instruction=enhanced_instruction,
            template_content=sp.template_content,
            examples=sp.examples,
            reference_content=sp.reference_content,
            doc_id=doc_id,
        )
        if result["status"] == "success":
            sections.append(SectionOutput(**result["section"]))
        else:
            logger.warning(
                "섹션 '%s' 재작성 실패: %s",
                sp.section_title,
                result.get("message", ""),
            )
    return sections


async def _build_all_formats(
    doc_output: DocumentOutput,
    output_formats: list[str],
) -> dict:
    """요청된 출력 형식별로 Builder를 호출하여 파일을 생성한다."""
    files = {}
    for fmt in output_formats:
        result = None
        if fmt == "hwpx":
            result = await build_hwpx(doc_output)
        elif fmt == "pptx":
            result = await build_pptx(doc_output)
        elif fmt == "xlsx":
            result = await build_xlsx(doc_output)
        else:
            logger.warning("지원하지 않는 출력 형식: %s", fmt)
            continue

        if result and result.get("status") == "success":
            files[fmt] = result["file_path"]
        else:
            logger.warning(
                "빌드 실패 (%s): %s",
                fmt,
                result.get("message", "") if result else "알 수 없는 오류",
            )
    return files


def _extract_template_structure(plan: DocumentPlan) -> str:
    """DocumentPlan에서 양식 구조 문자열을 추출한다 (리뷰용)."""
    parts = []
    for sp in plan.sections:
        parts.append(f"## {sp.section_title}\n{sp.template_content}")
    return "\n\n".join(parts)
