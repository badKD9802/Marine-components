"""
문서 품질 평가 도구 (Document Reviewer)

생성된 문서의 품질을 체크리스트 기반으로 평가한다.
5대 기준으로 개별 LLM 호출 → 가중 합산 → 통과/재작성 판정.
"""

import json
import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


# ─── 5대 평가 기준 (가중치 합 = 1.0) ───

REVIEW_CRITERIA = {
    "completeness": {
        "weight": 0.25,
        "name": "완성도",
        "prompt": "문서가 요청된 모든 항목을 포함하고 있습니까?",
        "definition": "모든 필수 섹션이 존재하고 각 섹션에 실질적 내용이 포함됨",
    },
    "accuracy": {
        "weight": 0.25,
        "name": "정확성",
        "prompt": "문서의 내용이 참고문서와 일치하고 사실적으로 정확합니까?",
        "definition": "수치, 날짜, 명칭 등이 정확하고 참고문서 내용과 일치함",
    },
    "format_compliance": {
        "weight": 0.20,
        "name": "형식 준수",
        "prompt": "문서 형식이 양식 구조를 정확히 따르고 있습니까?",
        "definition": "양식의 섹션 구조, 항목 순서, 표 형식 등이 정확히 준수됨",
    },
    "clarity": {
        "weight": 0.15,
        "name": "명확성",
        "prompt": "문서가 명확하고 이해하기 쉽습니까?",
        "definition": "모호한 표현 없이 핵심이 명확하게 전달되고 문장이 간결함",
    },
    "coherence": {
        "weight": 0.15,
        "name": "일관성",
        "prompt": "섹션 간 논리적 흐름이 자연스럽고 문체가 일관됩니까?",
        "definition": "섹션 간 연결이 자연스럽고 용어/문체가 통일됨",
    },
}

PASS_THRESHOLD = 0.80  # 80점 이상 통과


# ─── 개별 기준 평가 ───


async def _evaluate_criterion(
    criterion_key: str,
    criterion_config: dict,
    document_json: str,
    original_request: str,
    template_structure: str,
) -> dict:
    """
    단일 기준 평가. LLM에게 Chain-of-Thought 추론 후 Yes/No 판정 요청.

    Args:
        criterion_key: 기준 키 (예: "completeness")
        criterion_config: 기준 설정 dict (weight, name, prompt, definition)
        document_json: 평가 대상 문서 JSON 문자열
        original_request: 원본 작성 요청
        template_structure: 양식 구조 (선택)

    Returns:
        {"criterion": key, "score": 1.0 또는 0.0, "feedback": "피드백"}
    """
    try:
        client = AsyncOpenAI()
        model = os.getenv("REVIEWER_LLM_MODEL", "gpt-4o-mini")

        criterion_name = criterion_config["name"]
        definition = criterion_config["definition"]

        # 프롬프트 구성
        user_prompt = (
            f"다음 문서를 '{criterion_name}' 기준으로 평가하세요.\n\n"
            f"[평가 기준] {definition}\n"
            f"[원본 요청] {original_request}\n"
            f"[양식 구조] {template_structure}\n"
            f"[문서] {document_json}\n\n"
            f'단계별로 생각한 후 JSON으로 출력:\n'
            f'{{"reasoning": "평가 근거", "verdict": "Yes" or "No", "feedback": "개선 제안"}}'
        )

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 문서 품질 평가 전문가입니다. "
                        "주어진 기준에 따라 문서를 엄격하게 평가하고 "
                        "반드시 JSON 형식으로 응답하세요."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        # LLM 응답 파싱
        content = response.choices[0].message.content
        parsed = json.loads(content)

        verdict = parsed.get("verdict", "No").strip()
        feedback = parsed.get("feedback", "")
        score = 1.0 if verdict == "Yes" else 0.0

        return {"criterion": criterion_key, "score": score, "feedback": feedback}

    except Exception as e:
        logger.warning("기준 '%s' 평가 실패: %s", criterion_key, e)
        return {
            "criterion": criterion_key,
            "score": 0.0,
            "feedback": f"평가 실패: {str(e)}",
        }


# ─── 문서 평가 통합 ───


async def review_document(
    document_json: str,
    original_request: str,
    template_structure: str = "",
    _auth=None,
    **kwargs,
) -> dict:
    """
    문서 품질 평가.

    1. 각 기준별로 개별 LLM 호출 (Chain-of-Thought)
    2. Yes/No 판정 → 1.0/0.0 점수
    3. 가중 합산 → 총점
    4. PASS_THRESHOLD 이상이면 통과

    Args:
        document_json: 평가 대상 문서 JSON 문자열
        original_request: 원본 작성 요청
        template_structure: 양식 구조 (선택)
        _auth: 인증 정보 (미사용)

    Returns:
        {
            "status": "success",
            "passed": bool,
            "total_score": float,  # 0.0 ~ 1.0
            "scores": [{"criterion": "...", "score": 1.0, "feedback": "..."}],
            "feedback": ["미달 항목의 구체적 피드백"],
            "message": "통과" or "재작성 필요 (75점, 기준 미달: 정확성, 형식 준수)"
        }
    """
    scores = []

    # 각 기준별 개별 평가
    for key, config in REVIEW_CRITERIA.items():
        result = await _evaluate_criterion(
            criterion_key=key,
            criterion_config=config,
            document_json=document_json,
            original_request=original_request,
            template_structure=template_structure,
        )
        scores.append(result)

    # 가중 합산
    total_score = 0.0
    for score_item in scores:
        criterion_key = score_item["criterion"]
        weight = REVIEW_CRITERIA[criterion_key]["weight"]
        total_score += score_item["score"] * weight

    # 통과 여부 판정
    passed = total_score >= PASS_THRESHOLD

    # 미달 기준의 피드백 수집
    feedback_list = []
    failed_names = []
    for score_item in scores:
        if score_item["score"] == 0.0:
            criterion_key = score_item["criterion"]
            criterion_name = REVIEW_CRITERIA[criterion_key]["name"]
            failed_names.append(criterion_name)
            if score_item["feedback"]:
                feedback_list.append(score_item["feedback"])

    # 메시지 구성
    score_pct = int(round(total_score * 100))
    if passed:
        message = f"통과 ({score_pct}점)"
    else:
        failed_str = ", ".join(failed_names)
        message = f"재작성 필요 ({score_pct}점, 기준 미달: {failed_str})"

    return {
        "status": "success",
        "passed": passed,
        "total_score": total_score,
        "scores": scores,
        "feedback": feedback_list,
        "message": message,
    }
