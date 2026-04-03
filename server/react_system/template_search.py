"""
양식 검색 API — Milvus document_templates 컬렉션 고수준 검색

3가지 검색 모드를 지원:
  1. RAG 추천 — Dense + Sparse 하이브리드 검색
  2. 키워드 재검색 — 카테고리 브라우징
  3. 양식 상세 / 예시 조회

TemplateStore를 의존성으로 받아 Milvus 컬렉션에 접근한다.
"""

import logging

from react_system.template_store import (
    TemplateStore,
    get_embedding_fn,
    get_tokenize_fn,
)

logger = logging.getLogger(__name__)


# ─── 헬퍼 ───


def _build_visibility_filter(user_id: str = None) -> str:
    """visibility 필터 생성. public + 해당 사용자의 비공개 데이터."""
    if user_id:
        return f'visibility in ["public", "user:{user_id}"]'
    return 'visibility == "public"'


def _build_filter_expr(
    chunk_type: str,
    user_id: str = None,
    category: str = None,
    template_id: str = None,
) -> str:
    """복합 필터 표현식 빌더. 여러 조건을 AND로 결합한다."""
    parts = [f'chunk_type == "{chunk_type}"']
    parts.append(_build_visibility_filter(user_id))
    if category:
        parts.append(f'category == "{category}"')
    if template_id:
        parts.append(f'template_id == "{template_id}"')
    return " and ".join(parts)


def _get_default_store() -> TemplateStore:
    """기본 TemplateStore 인스턴스 생성."""
    return TemplateStore()


# ─── 1. RAG 양식 추천 (하이브리드 검색) ───


async def search_templates(
    query: str,
    user_id: str = None,
    category: str = None,
    limit: int = 10,
    offset: int = 0,
    store: TemplateStore = None,
) -> dict:
    """
    사용자 쿼리로 양식 검색 (Dense + Sparse 하이브리드).

    - chunk_type="template"만 검색
    - visibility in ["public", "user:{user_id}"] 필터
    - category 필터 (선택)

    Returns: {
        "status": "success",
        "templates": [{"id", "title", "category", "subcategory", "score", ...}],
        "total": int
    }
    """
    try:
        if store is None:
            store = _get_default_store()

        filter_expr = _build_filter_expr(
            chunk_type="template",
            user_id=user_id,
            category=category,
        )

        embedding_fn = get_embedding_fn()
        tokenize_fn = get_tokenize_fn()

        hits = await store.hybrid_search(
            query_text=query,
            embedding_fn=embedding_fn,
            tokenize_fn=tokenize_fn,
            filter_expr=filter_expr,
            limit=limit,
        )

        return {
            "status": "success",
            "templates": hits,
            "total": len(hits),
        }
    except Exception as e:
        logger.error(f"양식 검색 실패: {e}")
        return {"status": "error", "message": str(e)}


# ─── 2. 카테고리 브라우징 ───


async def browse_by_category(
    category: str = None,
    user_id: str = None,
    limit: int = 20,
    offset: int = 0,
    store: TemplateStore = None,
) -> dict:
    """
    카테고리별 양식 목록 (벡터 검색 없음, 스칼라 필터만).

    - category=None이면 전체 카테고리 목록 반환
    - category 지정 시 해당 카테고리의 양식 목록
    - chunk_type="template"만

    Returns: {
        "status": "success",
        "templates": [...],   # category 지정 시
        "categories": [...],  # category=None 시
        "total": int,
        "has_more": bool
    }
    """
    try:
        if store is None:
            store = _get_default_store()

        if category is None:
            # 전체 카테고리 목록: 모든 template을 조회하고 category 그룹핑
            filter_expr = _build_filter_expr(
                chunk_type="template",
                user_id=user_id,
            )
            records = await store.query(
                filter_expr=filter_expr,
                limit=10000,  # 카테고리 집계를 위해 충분히 큰 수
                offset=0,
                output_fields=["category"],
            )
            categories = sorted(set(
                r["category"] for r in records if r.get("category")
            ))
            return {
                "status": "success",
                "categories": categories,
                "total": len(categories),
                "has_more": False,
            }

        # 특정 카테고리의 양식 목록
        filter_expr = _build_filter_expr(
            chunk_type="template",
            user_id=user_id,
            category=category,
        )
        # has_more 판별을 위해 limit+1개 조회
        records = await store.query(
            filter_expr=filter_expr,
            limit=limit + 1,
            offset=offset,
        )

        has_more = len(records) > limit
        templates = records[:limit]

        return {
            "status": "success",
            "templates": templates,
            "total": len(templates),
            "has_more": has_more,
        }
    except Exception as e:
        logger.error(f"카테고리 브라우징 실패: {e}")
        return {"status": "error", "message": str(e)}


# ─── 3. 특정 양식의 예시 조회 ───


async def get_examples_for_template(
    template_id: str,
    user_id: str = None,
    limit: int = 20,
    offset: int = 0,
    store: TemplateStore = None,
) -> dict:
    """
    특정 양식에 연결된 예시 목록.

    - chunk_type="example" AND template_id={template_id}
    - visibility in ["public", "user:{user_id}"]
    - 내 예시(user_id 매칭)를 먼저, 그 다음 public 예시

    Returns: {
        "status": "success",
        "examples": [{"id", "title", "content", "user_id", "is_mine", ...}],
        "total": int
    }
    """
    try:
        if store is None:
            store = _get_default_store()

        filter_expr = _build_filter_expr(
            chunk_type="example",
            user_id=user_id,
            template_id=template_id,
        )

        records = await store.query(
            filter_expr=filter_expr,
            limit=limit,
            offset=offset,
        )

        # is_mine 플래그 추가 + 내 예시를 먼저 정렬
        examples = []
        for rec in records:
            rec["is_mine"] = bool(user_id and rec.get("user_id") == user_id)
            examples.append(rec)

        # 내 예시 먼저, 그 다음 public 예시
        examples.sort(key=lambda x: (not x["is_mine"],))

        return {
            "status": "success",
            "examples": examples,
            "total": len(examples),
        }
    except Exception as e:
        logger.error(f"예시 조회 실패: {e}")
        return {"status": "error", "message": str(e)}


# ─── 4. 양식 상세 조회 (섹션 포함) ───


async def get_template_detail(
    template_id: str,
    store: TemplateStore = None,
) -> dict:
    """
    양식 상세 정보 + 섹션 목록.

    - template 레코드 + 연결된 section 레코드들

    Returns: {
        "status": "success",
        "template": {...},
        "sections": [{"section_id", "title", "content", ...}]
    }
    """
    try:
        if store is None:
            store = _get_default_store()

        # 양식 레코드 조회
        template = await store.get_by_id(template_id)
        if template is None:
            return {
                "status": "error",
                "message": f"양식을 찾을 수 없습니다: {template_id}",
            }

        # 연결된 섹션 조회
        filter_expr = _build_filter_expr(
            chunk_type="section",
            template_id=template_id,
        )
        sections = await store.query(
            filter_expr=filter_expr,
            limit=100,  # 섹션은 양식당 많지 않으므로 충분한 수
        )

        return {
            "status": "success",
            "template": template,
            "sections": sections,
        }
    except Exception as e:
        logger.error(f"양식 상세 조회 실패: {e}")
        return {"status": "error", "message": str(e)}
