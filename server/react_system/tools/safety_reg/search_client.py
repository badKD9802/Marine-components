"""Milvus 검색 클라이언트 — 단일 하이브리드 컬렉션에서 hybrid_search.

pymilvus hybrid_search() + AnnSearchRequest + RRFRanker를 사용하여
Dense + Sparse 검색을 단일 호출로 수행.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import List
from react_system.tools.safety_reg.constants import (
    CATEGORY_TO_DOC_TYPES,
    COLLECTION_NAME,
    DEFAULT_CHILD_TOP_K,
    DEFAULT_MAX_PER_DOC,
    DEFAULT_RERANK_TOP_K,
    DEFAULT_RRF_K,
    LEGAL_ABBREVIATIONS,
)

logger = logging.getLogger(__name__)

# 조항 정규화 패턴
ARTICLE_OF_NORMALIZE = re.compile(r'(?<!\w)(\d+)\s*조의\s*(\d+)')
ARTICLE_NORMALIZE = re.compile(r'(?<!\w)(\d+)\s*조')
PARAGRAPH_NORMALIZE = re.compile(r'(?<!\w)(\d+)\s*항')
SUBITEM_NORMALIZE = re.compile(r'(?<!\w)(\d+)\s*호')
QUERY_CLEANUP = re.compile(r'(이\s*뭐야|알려\s*줘|뭔가요|인가요|인지|인지요|무엇인가요|어떻게\s*되나요|해줘)\s*[?？]*$')

# hybrid_search 결과에서 가져올 필드
OUTPUT_FIELDS = [
    "chunk_id", "chunk_type", "parent_chunk_id", "orig_text",
    "doc_name", "doc_type", "article_ref", "section_hierarchy",
    "source_url", "effective_date", "references_to", "referenced_by",
]


@dataclass
class SearchHit:
    """검색 결과 개별 항목."""

    chunk_id: str = ""
    chunk_type: str = ""
    parent_chunk_id: str = ""
    orig_text: str = ""
    doc_name: str = ""
    doc_type: str = ""
    article_ref: str = ""
    section_hierarchy: str = ""
    source_url: str = ""
    effective_date: str = ""
    references_to: str = "[]"
    referenced_by: str = "[]"
    score: float = 0.0


@dataclass
class SearchResult:
    """검색 결과."""

    query: str = ""
    children: List[SearchHit] = field(default_factory=list)
    parents: List[SearchHit] = field(default_factory=list)
    sources: List[dict] = field(default_factory=list)


class SafetyRegSearchClient:
    """안전법령 검색 클라이언트."""

    def __init__(self, milvus_host: str = None, milvus_port: str = "19530"):
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self._client = None

    async def search(
        self,
        query: str,
        category: str = "전체",
        top_k: int = DEFAULT_RERANK_TOP_K,
        embedding_fn=None,
        tokenize_fn=None,
        rerank_fn=None,
    ) -> SearchResult:
        """안전법령 하이브리드 검색.

        1. 쿼리 전처리 — 약어 확장, 조항 정규화
        2. pymilvus hybrid_search (Dense + Sparse → RRFRanker)
        3. 다양성 확보 + Reranking
        4. Parent 조회
        """
        processed_query = self._preprocess_query(query)
        logger.info(f"검색 쿼리: '{query}' → '{processed_query}'")

        result = SearchResult(query=processed_query)

        doc_type_filter = CATEGORY_TO_DOC_TYPES.get(category)

        # 하이브리드 검색
        merged = await self._hybrid_search(
            processed_query, embedding_fn, tokenize_fn,
            doc_type_filter, limit=DEFAULT_CHILD_TOP_K,
        )

        if not merged:
            logger.info("검색 결과 없음")
            return result

        # 다양성 확보
        merged = self._diversify(merged)

        # Reranking
        if rerank_fn and len(merged) > top_k:
            merged = await self._rerank(processed_query, merged, rerank_fn, top_k)
        else:
            merged = merged[:top_k]

        result.children = merged

        # Parent 조회
        parent_ids = list(set(h.parent_chunk_id for h in merged if h.parent_chunk_id))
        if parent_ids:
            parents = await self._get_parents(parent_ids)
            result.parents = parents

        result.sources = self._build_sources(result.parents or result.children)
        return result

    async def search_multi(
        self,
        queries: List[str],
        category: str = "전체",
        top_k: int = DEFAULT_RERANK_TOP_K,
        embedding_fn=None,
        tokenize_fn=None,
    ) -> SearchResult:
        """복수 쿼리 병렬 검색 → 결과 병합."""
        import asyncio

        tasks = [
            self.search(q, category, top_k, embedding_fn, tokenize_fn)
            for q in queries
        ]
        results = await asyncio.gather(*tasks)

        merged_children = {}
        all_parents = {}
        for sr in results:
            for child in sr.children:
                if child.chunk_id not in merged_children or child.score > merged_children[child.chunk_id].score:
                    merged_children[child.chunk_id] = child
            for parent in sr.parents:
                all_parents[parent.chunk_id] = parent

        sorted_children = sorted(merged_children.values(), key=lambda x: x.score, reverse=True)[:top_k]

        parent_ids = list(set(c.parent_chunk_id for c in sorted_children if c.parent_chunk_id))
        parents = [all_parents[pid] for pid in parent_ids if pid in all_parents]

        return SearchResult(
            query=" / ".join(queries),
            children=sorted_children,
            parents=parents,
            sources=self._build_sources(parents or sorted_children),
        )

    async def fetch_cross_references(
        self,
        references: List[dict],
    ) -> List[SearchHit]:
        """교차 참조 조문을 Milvus에서 직접 조회."""
        if not references:
            return []

        client = await self._get_client()
        found_parents = []

        for ref in references[:5]:
            law_name = ref.get("law_name", "")
            article = ref.get("article", "")
            if not law_name or not article:
                continue

            filter_expr = f'chunk_type == "parent" and doc_name like "%{law_name}%" and article_ref like "%{article}%"'

            try:
                results = client.query(
                    collection_name=COLLECTION_NAME,
                    filter=filter_expr,
                    output_fields=OUTPUT_FIELDS,
                    limit=1,
                )

                for entity in results:
                    hit = self._entity_to_hit(entity)
                    found_parents.append(hit)
                    logger.info(f"교차 참조 조회 성공: 「{law_name}」 {article}")

            except Exception as e:
                logger.warning(f"교차 참조 조회 실패: 「{law_name}」 {article} — {e}")

        return found_parents

    # ──────────────────────────────────────────────
    # 쿼리 전처리
    # ──────────────────────────────────────────────

    def _preprocess_query(self, query: str) -> str:
        """약어 확장 + 조항 정규화 + 종결어미 제거."""
        processed = query
        processed = QUERY_CLEANUP.sub('', processed).strip()

        for abbr, full in sorted(LEGAL_ABBREVIATIONS.items(), key=lambda x: -len(x[0])):
            if abbr in processed:
                processed = processed.replace(abbr, full)

        processed = ARTICLE_OF_NORMALIZE.sub(r'제\1조의\2', processed)
        processed = ARTICLE_NORMALIZE.sub(r'제\1조', processed)
        processed = PARAGRAPH_NORMALIZE.sub(r'제\1항', processed)
        processed = SUBITEM_NORMALIZE.sub(r'제\1호', processed)

        return processed

    # ──────────────────────────────────────────────
    # 하이브리드 검색 (pymilvus hybrid_search)
    # ──────────────────────────────────────────────

    async def _hybrid_search(
        self,
        query: str,
        embedding_fn,
        tokenize_fn,
        doc_type_filter: List[str] = None,
        limit: int = DEFAULT_CHILD_TOP_K,
    ) -> List[SearchHit]:
        """Dense + Sparse 하이브리드 검색 (RRFRanker)."""
        client = await self._get_client()

        from pymilvus import AnnSearchRequest, RRFRanker

        # 필터 구성
        filter_expr = 'chunk_type == "child"'
        if doc_type_filter:
            types_str = ", ".join(f'"{t}"' for t in doc_type_filter)
            filter_expr += f" and doc_type in [{types_str}]"

        reqs = []

        # Dense 검색 요청
        if embedding_fn:
            embeddings = await embedding_fn([query])
            if embeddings:
                dense_req = AnnSearchRequest(
                    data=[embeddings[0]],
                    anns_field="dense_vector",
                    param={"metric_type": "COSINE", "params": {"nprobe": 64}},
                    limit=limit,
                    expr=filter_expr,
                )
                reqs.append(dense_req)

        # Sparse 검색 요청
        if tokenize_fn:
            sparse_vec = tokenize_fn(query)
            sparse_req = AnnSearchRequest(
                data=[sparse_vec],
                anns_field="sparse_vector",
                param={"metric_type": "IP"},
                limit=limit,
                expr=filter_expr,
            )
            reqs.append(sparse_req)

        if not reqs:
            logger.error("검색 요청 없음 — embedding_fn과 tokenize_fn 모두 None")
            return []

        try:
            results = client.hybrid_search(
                collection_name=COLLECTION_NAME,
                reqs=reqs,
                ranker=RRFRanker(k=DEFAULT_RRF_K),
                limit=limit,
                output_fields=OUTPUT_FIELDS,
            )

            hits = []
            for res in results[0]:
                entity = res.get("entity", res)
                hit = self._entity_to_hit(entity)
                hit.score = res.get("distance", 0.0)
                hits.append(hit)
            return hits

        except Exception as e:
            logger.error(f"하이브리드 검색 실패: {e}")
            return []

    # ──────────────────────────────────────────────
    # 다양성 확보
    # ──────────────────────────────────────────────

    def _diversify(self, hits: List[SearchHit], max_per_doc: int = DEFAULT_MAX_PER_DOC) -> List[SearchHit]:
        """동일 법령에서 최대 max_per_doc건만 유지."""
        doc_counts = {}
        result = []
        deferred = []
        for hit in hits:
            count = doc_counts.get(hit.doc_name, 0)
            if count < max_per_doc:
                result.append(hit)
                doc_counts[hit.doc_name] = count + 1
            else:
                deferred.append(hit)
        return result + deferred

    # ──────────────────────────────────────────────
    # Reranking
    # ──────────────────────────────────────────────

    async def _rerank(
        self, query: str, hits: List[SearchHit], rerank_fn, top_k: int,
    ) -> List[SearchHit]:
        """Reranking으로 상위 top_k 선별."""
        docs = [h.orig_text for h in hits]
        try:
            indices = await rerank_fn(query, docs, top_k)
            return [hits[i] for i in indices if i < len(hits)]
        except Exception as e:
            logger.error(f"Reranking 실패, 기존 순서 사용: {e}")
            return hits[:top_k]

    # ──────────────────────────────────────────────
    # Parent 조회
    # ──────────────────────────────────────────────

    async def _get_parents(self, parent_ids: List[str]) -> List[SearchHit]:
        """parent_chunk_id로 Parent 청크 직접 조회."""
        client = await self._get_client()

        ids_str = ", ".join(f'"{pid}"' for pid in parent_ids)
        filter_expr = f'chunk_id in [{ids_str}]'

        try:
            results = client.query(
                collection_name=COLLECTION_NAME,
                filter=filter_expr,
                output_fields=OUTPUT_FIELDS,
            )

            return [self._entity_to_hit(entity) for entity in results]

        except Exception as e:
            logger.error(f"Parent 조회 실패: {e}")
            return []

    # ──────────────────────────────────────────────
    # 출처 목록 생성
    # ──────────────────────────────────────────────

    def _build_sources(self, hits: List[SearchHit]) -> List[dict]:
        """출처 목록 생성 (중복 제거)."""
        seen = set()
        sources = []
        for hit in hits:
            key = f"{hit.doc_name}_{hit.article_ref}"
            if key in seen:
                continue
            seen.add(key)
            sources.append({
                "doc_name": hit.doc_name,
                "article_ref": hit.article_ref,
                "source_url": hit.source_url,
                "excerpt": hit.orig_text[:200] + "..." if len(hit.orig_text) > 200 else hit.orig_text,
                "full_text": hit.orig_text,
            })
        return sources

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────

    @staticmethod
    def _entity_to_hit(entity: dict) -> SearchHit:
        """Milvus entity → SearchHit 변환."""
        return SearchHit(
            chunk_id=entity.get("chunk_id", ""),
            chunk_type=entity.get("chunk_type", ""),
            parent_chunk_id=entity.get("parent_chunk_id", ""),
            orig_text=entity.get("orig_text", ""),
            doc_name=entity.get("doc_name", ""),
            doc_type=entity.get("doc_type", ""),
            article_ref=entity.get("article_ref", ""),
            section_hierarchy=entity.get("section_hierarchy", ""),
            source_url=entity.get("source_url", ""),
            effective_date=entity.get("effective_date", ""),
            references_to=entity.get("references_to", "[]"),
            referenced_by=entity.get("referenced_by", "[]"),
        )

    # ──────────────────────────────────────────────
    # Milvus 클라이언트
    # ──────────────────────────────────────────────

    async def _get_client(self):
        """Milvus 클라이언트 lazy init."""
        if self._client is not None:
            return self._client

        host, port = self._resolve_connection()

        try:
            from pymilvus import MilvusClient

            uri = f"http://{host}:{port}"
            self._client = MilvusClient(uri=uri)
            return self._client
        except Exception as e:
            logger.error(f"Milvus 연결 실패: {e}")
            raise

    def _resolve_connection(self):
        """Milvus 연결 정보 해결."""
        if self.milvus_host:
            return self.milvus_host, self.milvus_port
        host = os.getenv("MILVUS_HOST", "localhost")
        port = os.getenv("MILVUS_PORT", "19530")
        return host, port
