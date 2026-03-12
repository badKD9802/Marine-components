"""안전관련 법령/가이드 RAG 검색 도구.

ReAct agent의 도구로 동작하며, 안전관련 문서(법령, 행정규칙 등)를
대상으로 하이브리드 검색 + LLM 답변 생성을 수행한다.
"""

import json
import logging
from typing import List, Optional

from react_system.tools.safety_reg.answer_generator import generate_answer
from react_system.tools.safety_reg.prompts import (
    CROSS_REFERENCE_EXTRACTION_PROMPT,
    MULTI_QUERY_PROMPT,
)
from react_system.tools.safety_reg.search_client import (
    SafetyRegSearchClient,
    SearchResult,
)

logger = logging.getLogger(__name__)

# 싱글톤 검색 클라이언트
_search_client: Optional[SafetyRegSearchClient] = None


def _get_search_client() -> SafetyRegSearchClient:
    """검색 클라이언트 싱글톤."""
    global _search_client
    if _search_client is None:
        _search_client = SafetyRegSearchClient()
    return _search_client


def _get_llm_config():
    """환경변수에서 LLM 설정 로드."""
    import os
    return {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL"),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
        "embed_api_key": os.getenv("OPENAI_API_KEY", ""),
        "embed_base_url": os.getenv("OPENAI_BASE_URL"),
    }


def _get_embedding_fn(llm_cfg: dict):
    """임베딩 함수 — text-embedding-3-small (dim=1024)."""

    async def embed(texts):
        try:
            from openai import AsyncOpenAI

            api_key = llm_cfg.get("embed_api_key") or llm_cfg["api_key"]
            base_url = llm_cfg.get("embed_base_url") or llm_cfg.get("base_url")

            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            response = await client.embeddings.create(
                input=texts,
                model="text-embedding-3-small",
                dimensions=1024,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            return None

    return embed


_kiwi_instance = None


def _get_kiwi():
    """Kiwi 싱글톤 (모델 로딩 ~1-2초 → 최초 1회만)."""
    global _kiwi_instance
    if _kiwi_instance is None:
        try:
            from kiwipiepy import Kiwi

            _kiwi_instance = Kiwi()
            logger.info("Kiwi 형태소 분석기 초기화 완료")
        except ImportError:
            logger.warning("Kiwi 미설치 — 단순 공백 분리 사용")
    return _kiwi_instance


def _get_tokenize_fn():
    """BM25 토크나이즈 함수 — Kiwi 형태소 분석기 사용 (싱글톤)."""

    def tokenize(text):
        kiwi = _get_kiwi()
        if kiwi:
            tokens = kiwi.tokenize(text)
            sparse = {}
            for token in tokens:
                key = hash(token.form) % (2**31)
                sparse[key] = sparse.get(key, 0) + 1.0
            return sparse
        else:
            sparse = {}
            for word in text.split():
                key = hash(word) % (2**31)
                sparse[key] = sparse.get(key, 0) + 1.0
            return sparse

    return tokenize


def _get_llm_fn(llm_cfg: dict):
    """LLM 호출 함수 — stat에서 가져온 설정 사용."""

    async def llm_call(system_prompt: str, user_prompt: str) -> str:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=llm_cfg["api_key"], base_url=llm_cfg["base_url"])
            response = await client.chat.completions.create(
                model=llm_cfg["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM 호출 실패: {e}")
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"

    return llm_call


async def _split_query(query: str, llm_fn) -> List[str]:
    """복합 질문 분할. 단일 주제면 [query] 그대로 반환."""
    if not llm_fn:
        return [query]
    # 짧은 질문이거나 복합 패턴이 없으면 분할 불필요
    if len(query) < 20:
        return [query]
    has_compound = any(kw in query for kw in ["과 ", "와 ", ",", "그리고", "및 "])
    if not has_compound:
        return [query]
    try:
        result = await llm_fn(
            "질문을 분석하여 JSON으로 답변하세요.",
            MULTI_QUERY_PROMPT.format(query=query),
        )
        parsed = json.loads(result)
        queries = parsed.get("queries", [query])
        if queries and len(queries) > 1:
            logger.info(f"Multi-Query 분할: '{query}' → {queries}")
            return queries[:3]
        return [query]
    except Exception as e:
        logger.debug(f"Multi-Query 분할 실패 (원본 사용): {e}")
        return [query]


async def _extract_cross_references(parents, llm_fn) -> List[dict]:
    """LLM으로 Parent 조문에서 다른 법령 참조를 추출.

    Returns:
        [{"law_name": "산업재해보상보험법", "article": "제8조"}, ...]
    """
    if not llm_fn or not parents:
        return []

    # Parent 본문을 컨텍스트로 구성
    context_parts = []
    for p in parents[:5]:  # 최대 5개 Parent만
        context_parts.append(f"[{p.doc_name} {p.article_ref}]\n{p.orig_text[:500]}")
    context = "\n\n".join(context_parts)

    try:
        result = await llm_fn(
            "법령 문서에서 다른 법령 참조를 추출하세요. JSON으로만 답변하세요.",
            CROSS_REFERENCE_EXTRACTION_PROMPT.format(context=context),
        )
        parsed = json.loads(result)
        references = parsed.get("references", [])
        if references:
            logger.info(f"교차 참조 추출: {references}")
        return references[:5]
    except Exception as e:
        logger.debug(f"교차 참조 추출 실패: {e}")
        return []


async def search_safety_regulations(
    query: str,
    category: str = "전체",
    detail_level: str = "standard",
    _auth=None,
) -> dict:
    """안전관련 법령/가이드를 검색하고 답변을 생성합니다.

    Args:
        query: 검색할 질문 (예: "안전관리자 선임 기준", "산안법 제17조")
        category: 검색 범위 ("전체"|"법령"|"정부가이드"|"내부규정"|"매뉴얼"|"현장서식")
        detail_level: 답변 상세도 ("brief"|"standard"|"detailed")
        _auth: AuthContext — stat 참조로 LLM 설정 가져옴

    Returns:
        {
            "status": "success" | "no_results" | "error",
            "html_content": "구조화된 HTML 답변 + 출처",
            "text_summary": "LLM 후속 컨텍스트용 요약",
            "sources": [{"doc_name", "article_ref", "source_url", "excerpt"}, ...]
        }
    """
    try:
        llm_cfg = _get_llm_config()

        # 검색 클라이언트
        client = _get_search_client()

        # 함수 준비
        embedding_fn = _get_embedding_fn(llm_cfg)
        tokenize_fn = _get_tokenize_fn()
        llm_fn = _get_llm_fn(llm_cfg)

        # Multi-Query: 복합 질문 분할
        queries = await _split_query(query, llm_fn)
        if len(queries) > 1:
            search_result: SearchResult = await client.search_multi(
                queries=queries,
                category=category,
                embedding_fn=embedding_fn,
                tokenize_fn=tokenize_fn,
            )
        else:
            search_result: SearchResult = await client.search(
                query=query,
                category=category,
                embedding_fn=embedding_fn,
                tokenize_fn=tokenize_fn,
            )

        # 검색 결과 없음
        if not search_result.children and not search_result.parents:
            return {
                "status": "no_results",
                "html_content": _render_no_results(query),
                "text_summary": f"'{query}'에 대한 안전법령 검색 결과가 없습니다.",
                "sources": [],
            }

        # 교차 참조 확장: Parent 조문에서 다른 법령 참조 추출 → 추가 조회
        cross_refs = await _extract_cross_references(search_result.parents, llm_fn)
        if cross_refs:
            cross_ref_parents = await client.fetch_cross_references(cross_refs)
            if cross_ref_parents:
                # 기존 Parent에 없는 것만 추가
                existing_ids = {p.chunk_id for p in search_result.parents}
                for crp in cross_ref_parents:
                    if crp.chunk_id not in existing_ids:
                        search_result.parents.append(crp)
                        existing_ids.add(crp.chunk_id)
                        # 출처에도 추가
                        search_result.sources.append({
                            "doc_name": crp.doc_name,
                            "article_ref": crp.article_ref,
                            "source_url": crp.source_url,
                            "excerpt": crp.orig_text[:200] + "..." if len(crp.orig_text) > 200 else crp.orig_text,
                            "full_text": crp.orig_text,
                        })

        # LLM 답변 생성
        answer_result = await generate_answer(
            query=query,
            parents=search_result.parents,
            children=search_result.children,
            sources=search_result.sources,
            detail_level=detail_level,
            llm_fn=llm_fn,
        )

        return {
            "status": "success",
            "html_content": answer_result["html_content"],
            "text_summary": answer_result["text_summary"],
            "sources": answer_result["sources"],
        }

    except Exception as e:
        logger.error(f"안전법령 검색 오류: {e}", exc_info=True)
        return {
            "status": "error",
            "html_content": f"<p>안전법령 검색 중 오류가 발생했습니다: {str(e)}</p>",
            "text_summary": f"검색 오류: {str(e)}",
            "sources": [],
        }


def _render_no_results(query: str) -> str:
    """검색 결과 없음 HTML."""
    return f"""<div class="safety-reg-answer">
<p>'{query}'에 대한 안전관련 법령/가이드를 찾을 수 없습니다.</p>
<p style="color:#666;font-size:13px;">다음을 시도해보세요:</p>
<ul style="color:#666;font-size:13px;">
<li>검색어를 더 구체적으로 변경 (예: "안전관리자" → "안전관리자 선임 기준")</li>
<li>법령 약어 사용 (예: "산안법", "중처법")</li>
<li>조문 번호로 검색 (예: "산업안전보건법 제17조")</li>
</ul>
</div>"""
