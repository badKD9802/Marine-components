"""
Document Writer 도구

개별 섹션을 LLM으로 생성하는 Writer 도구.
Orchestrator가 섹션별로 호출하며, 결과를 DB에 저장한다.
"""

import json
import logging
import os

from openai import AsyncOpenAI

from react_system import document_db
from react_system.document_schema import SectionOutput

logger = logging.getLogger(__name__)


def _build_writer_prompt(
    section_title: str,
    instruction: str,
    template_content: str,
    examples: list[str],
    reference_content: str,
) -> list[dict]:
    """Writer LLM 프롬프트 구성."""

    system_prompt = """당신은 공공기관 문서 작성 전문가입니다.
주어진 양식 구조를 정확히 따르고, 잘 쓴 예시의 문체와 수준을 참고하여 섹션을 작성합니다.
결과는 반드시 JSON 형식으로 출력하세요.

JSON 스키마:
{
    "section_id": "sec_XX",
    "section_title": "섹션 제목",
    "elements": [
        {"type": "heading", "content": {"text": "...", "bold": true}},
        {"type": "paragraph", "content": {"text": "..."}},
        {"type": "table", "content": {"columns": [...], "rows": [...]}},
        {"type": "list", "content": {"items": [...], "list_type": "bullet"}}
    ]
}"""

    # 예시 텍스트 구성
    examples_text = "\n".join(
        f"### 예시 {i + 1}\n{ex}" for i, ex in enumerate(examples)
    )

    user_content = f"""## 작성할 섹션: {section_title}

## 지시사항
{instruction}

## 양식 구조 (이 구조를 따라 작성)
{template_content}

## 잘 쓴 예시 (이 수준으로 작성)
{examples_text}

## 참고문서 (이 내용을 기반으로 작성)
{reference_content}

위 양식 구조를 정확히 따르고, 예시의 문체를 참고하여 JSON으로 결과를 출력하세요."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


async def write_section(
    section_index: int,
    section_title: str,
    instruction: str,
    template_content: str,
    examples: list[str],
    reference_content: str,
    doc_id: str = None,
    _auth=None,
    **kwargs,
) -> dict:
    """
    단일 섹션 생성.

    1. 프롬프트 구성: 시스템 프롬프트 + 양식 구조 + 예시 + 참고문서 + 지시사항
    2. LLM 호출 → JSON 응답 파싱 (SectionOutput)
    3. doc_id가 있으면 DB에 저장 (document_db.save_section)

    Returns:
        {
            "status": "success",
            "section": SectionOutput.model_dump(),
            "message": "섹션 '{section_title}' 생성 완료"
        }
    """
    # 1. 프롬프트 구성
    messages = _build_writer_prompt(
        section_title=section_title,
        instruction=instruction,
        template_content=template_content,
        examples=examples,
        reference_content=reference_content,
    )

    # 2. LLM 호출
    try:
        client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        model = os.getenv("WRITER_LLM_MODEL", "gpt-4o-mini")

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.error("LLM 호출 실패: %s", e)
        return {
            "status": "error",
            "message": f"LLM 호출 실패: {e}",
        }

    # 3. JSON 파싱 → SectionOutput
    raw_content = response.choices[0].message.content
    try:
        parsed = json.loads(raw_content)
        section_output = SectionOutput(**parsed)
    except (json.JSONDecodeError, Exception) as e:
        logger.error("JSON 파싱 실패: %s / 원본: %s", e, raw_content[:200])
        return {
            "status": "error",
            "message": f"JSON 파싱 실패: {e}",
        }

    section_dict = section_output.model_dump()

    # 4. DB 저장 (doc_id가 있을 때만)
    if doc_id is not None:
        try:
            await document_db.save_section(
                doc_id=doc_id,
                section_index=section_index,
                section_title=section_title,
                content=section_dict,
            )
        except Exception as e:
            logger.warning("DB 저장 실패 (계속 진행): %s", e)

    return {
        "status": "success",
        "section": section_dict,
        "message": f"섹션 '{section_title}' 생성 완료",
    }
