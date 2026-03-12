"""Milvus 검색 클라이언트 — Child 하이브리드 검색 → Parent 조회.

stat 의존성 없이 Milvus에 접속하여 안전법령 검색을 수행한다.
Dense + Sparse 하이브리드 검색 → RRF 결합 → Reranking → Parent 가져오기.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import List
from react_system.tools.safety_reg.constants import (
    CATEGORY_TO_DOC_TYPES,
    COLLECTION_DENSE,
    COLLECTION_SPARSE,
    DEFAULT_CHILD_TOP_K,
    DEFAULT_MAX_PER_DOC,
    DEFAULT_RERANK_TOP_K,
    DEFAULT_RRF_DENSE_WEIGHT,
    DEFAULT_RRF_K,
    DEFAULT_RRF_SPARSE_WEIGHT,
    LEGAL_ABBREVIATIONS,
)

logger = logging.getLogger(__name__)

# 조항 정규화 패턴: "13조" → "제13조", "2항" → "제2항", "3호" → "제3호", "13조의2" → "제13조의2"
ARTICLE_OF_NORMALIZE = re.compile(r'(?<!\w)(\d+)\s*조의\s*(\d+)')
ARTICLE_NORMALIZE = re.compile(r'(?<!\w)(\d+)\s*조')
PARAGRAPH_NORMALIZE = re.compile(r'(?<!\w)(\d+)\s*항')
SUBITEM_NORMALIZE = re.compile(r'(?<!\w)(\d+)\s*호')
# 불필요한 종결어미 제거
QUERY_CLEANUP = re.compile(r'(이\s*뭐야|알려\s*줘|뭔가요|인가요|인지|인지요|무엇인가요|어떻게\s*되나요|해줘)\s*[?？]*$')


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
    children: List[SearchHit] = field(default_factory=list)  # 매칭된 Child 청크
    parents: List[SearchHit] = field(default_factory=list)  # Child에서 가져온 Parent 청크
    sources: List[dict] = field(default_factory=list)  # 출처 목록


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
        2. 임베딩 생성 + 토크나이즈
        3. Child 대상 하이브리드 검색 (dense + sparse, top 15)
        4. RRF 스코어 결합
        5. Reranking → top 5
        6. Parent 조회 — 매칭된 Child의 parent_chunk_id로 Parent 가져옴
        7. 반환: children + parents + sources

        Args:
            query: 사용자 질문
            category: "전체"|"법령"|"정부가이드"|"내부규정"|"매뉴얼"|"현장서식"
            top_k: 최종 반환 건수
            embedding_fn: async (texts: List[str]) -> List[List[float]]
            tokenize_fn: (text: str) -> dict (sparse vector)
            rerank_fn: async (query, docs, top_k) -> List[int] (indices)

        Returns:
            SearchResult
        """
        # 1. 쿼리 전처리
        processed_query = self._preprocess_query(query)
        logger.info(f"검색 쿼리: '{query}' → '{processed_query}'")

        result = SearchResult(query=processed_query)

        # 카테고리 → doc_type 필터
        doc_type_filter = CATEGORY_TO_DOC_TYPES.get(category)

        # 2~3. 하이브리드 검색
        dense_hits = []
        sparse_hits = []

        if embedding_fn:
            dense_hits = await self._search_dense(
                processed_query, embedding_fn, doc_type_filter, limit=DEFAULT_CHILD_TOP_K
            )

        if tokenize_fn:
            sparse_hits = await self._search_sparse(
                processed_query, tokenize_fn, doc_type_filter, limit=DEFAULT_CHILD_TOP_K
            )

        # 4. RRF 스코어 결합
        merged = self._rrf_merge(dense_hits, sparse_hits)

        if not merged:
            logger.info("검색 결과 없음")
            return result

        # 4.5. 다양성 확보 (동일 법령 편중 방지)
        merged = self._diversify(merged)

        # 5. Reranking
        if rerank_fn and len(merged) > top_k:
            merged = await self._rerank(processed_query, merged, rerank_fn, top_k)
        else:
            merged = merged[:top_k]

        result.children = merged

        # 6. Parent 조회
        parent_ids = list(set(h.parent_chunk_id for h in merged if h.parent_chunk_id))
        if parent_ids:
            parents = await self._get_parents(parent_ids)
            result.parents = parents

        # 7. 출처 목록
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

        # 결과 병합: chunk_id 기준 중복 제거, 최고 스코어 유지
        merged_children = {}
        all_parents = {}
        for sr in results:
            for child in sr.children:
                if child.chunk_id not in merged_children or child.score > merged_children[child.chunk_id].score:
                    merged_children[child.chunk_id] = child
            for parent in sr.parents:
                all_parents[parent.chunk_id] = parent

        # 스코어 정렬 → top_k
        sorted_children = sorted(merged_children.values(), key=lambda x: x.score, reverse=True)[:top_k]

        # 병합된 Parent
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
        """교차 참조 조문을 Milvus에서 직접 조회.

        Args:
            references: [{"law_name": "산업재해보상보험법", "article": "제8조"}, ...]

        Returns:
            매칭된 Parent 청크 리스트
        """
        if not references:
            return []

        client = await self._get_client()
        found_parents = []

        for ref in references[:5]:  # 최대 5건
            law_name = ref.get("law_name", "")
            article = ref.get("article", "")
            if not law_name or not article:
                continue

            # doc_name LIKE + article_ref LIKE 필터
            filter_expr = f'chunk_type == "parent" and doc_name like "%{law_name}%" and article_ref like "%{article}%"'

            try:
                results = client.query(
                    collection_name=COLLECTION_DENSE,
                    filter=filter_expr,
                    output_fields=[
                        "chunk_id", "chunk_type", "parent_chunk_id", "orig_text",
                        "doc_name", "doc_type", "article_ref", "section_hierarchy",
                        "source_url", "effective_date", "references_to", "referenced_by",
                    ],
                    limit=1,
                )

                for entity in results:
                    hit = SearchHit(
                        chunk_id=entity.get("chunk_id", ""),
                        chunk_type="parent",
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

        # 종결어미 제거
        processed = QUERY_CLEANUP.sub('', processed).strip()

        # 약어 확장 (긴 것부터 매칭)
        for abbr, full in sorted(LEGAL_ABBREVIATIONS.items(), key=lambda x: -len(x[0])):
            if abbr in processed:
                processed = processed.replace(abbr, full)

        # 조항 정규화: "13조의2" → "제13조의2" (조의N을 먼저 처리)
        processed = ARTICLE_OF_NORMALIZE.sub(r'제\1조의\2', processed)
        processed = ARTICLE_NORMALIZE.sub(r'제\1조', processed)
        processed = PARAGRAPH_NORMALIZE.sub(r'제\1항', processed)
        processed = SUBITEM_NORMALIZE.sub(r'제\1호', processed)

        return processed

    # ──────────────────────────────────────────────
    # Dense 검색
    # ──────────────────────────────────────────────

    async def _search_dense(
        self, query: str, embedding_fn, doc_type_filter: List[str] = None, limit: int = 15,
    ) -> List[SearchHit]:
        """Dense 벡터 검색 (COSINE)."""
        client = await self._get_client()

        embeddings = await embedding_fn([query])
        if not embeddings:
            logger.error("임베딩 생성 실패 — embedding_fn이 None 반환")
            return []
        query_vector = embeddings[0]

        # 필터: chunk_type == "child" + doc_type
        filter_expr = 'chunk_type == "child"'
        if doc_type_filter:
            types_str = ", ".join(f'"{t}"' for t in doc_type_filter)
            filter_expr += f" and doc_type in [{types_str}]"

        try:
            results = client.search(
                collection_name=COLLECTION_DENSE,
                data=[query_vector],
                anns_field="dense_vector",
                limit=limit,
                filter=filter_expr,
                output_fields=[
                    "chunk_id", "chunk_type", "parent_chunk_id", "orig_text",
                    "doc_name", "doc_type", "article_ref", "section_hierarchy",
                    "source_url", "effective_date", "references_to", "referenced_by",
                ],
                search_params={"metric_type": "COSINE", "params": {"nprobe": 64}},
            )

            hits = []
            for res in results[0]:
                entity = res.get("entity", res)
                hit = SearchHit(
                    chunk_id=entity.get("chunk_id", ""),
                    chunk_type=entity.get("chunk_type", "child"),
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
                    score=res.get("distance", 0.0),
                )
                hits.append(hit)
            return hits

        except Exception as e:
            logger.error(f"Dense 검색 실패: {e}")
            return []

    # ──────────────────────────────────────────────
    # Sparse 검색
    # ──────────────────────────────────────────────

    async def _search_sparse(
        self, query: str, tokenize_fn, doc_type_filter: List[str] = None, limit: int = 15,
    ) -> List[SearchHit]:
        """Sparse(BM25) 검색."""
        client = await self._get_client()

        sparse_vector = tokenize_fn(query)

        filter_expr = 'chunk_type == "child"'
        if doc_type_filter:
            types_str = ", ".join(f'"{t}"' for t in doc_type_filter)
            filter_expr += f" and doc_type in [{types_str}]"

        try:
            results = client.search(
                collection_name=COLLECTION_SPARSE,
                data=[sparse_vector],
                anns_field="sparse_vector",
                limit=limit,
                filter=filter_expr,
                output_fields=[
                    "chunk_id", "chunk_type", "parent_chunk_id", "orig_text",
                    "doc_name", "doc_type", "article_ref", "section_hierarchy",
                ],
                search_params={"metric_type": "IP"},
            )

            hits = []
            for res in results[0]:
                entity = res.get("entity", res)
                hit = SearchHit(
                    chunk_id=entity.get("chunk_id", ""),
                    chunk_type=entity.get("chunk_type", "child"),
                    parent_chunk_id=entity.get("parent_chunk_id", ""),
                    orig_text=entity.get("orig_text", ""),
                    doc_name=entity.get("doc_name", ""),
                    doc_type=entity.get("doc_type", ""),
                    article_ref=entity.get("article_ref", ""),
                    section_hierarchy=entity.get("section_hierarchy", ""),
                    score=res.get("distance", 0.0),
                )
                hits.append(hit)
            return hits

        except Exception as e:
            logger.error(f"Sparse 검색 실패: {e}")
            return []

    # ──────────────────────────────────────────────
    # RRF 결합
    # ──────────────────────────────────────────────

    def _rrf_merge(
        self,
        dense_hits: List[SearchHit],
        sparse_hits: List[SearchHit],
    ) -> List[SearchHit]:
        """Reciprocal Rank Fusion으로 Dense + Sparse 결과 결합.

        RRF 스코어 = w_dense * 1/(k+rank_dense) + w_sparse * 1/(k+rank_sparse)
        """
        k = DEFAULT_RRF_K
        # chunk_id → SearchHit 매핑 (sparse에서 온 것 우선, dense 보완)
        hit_map = {}
        rrf_scores = {}

        # Dense 순위
        for rank, hit in enumerate(dense_hits):
            hit_map[hit.chunk_id] = hit
            rrf_scores[hit.chunk_id] = DEFAULT_RRF_DENSE_WEIGHT * (1.0 / (k + rank + 1))

        # Sparse 순위
        for rank, hit in enumerate(sparse_hits):
            if hit.chunk_id not in hit_map:
                hit_map[hit.chunk_id] = hit
            rrf_scores[hit.chunk_id] = rrf_scores.get(hit.chunk_id, 0) + DEFAULT_RRF_SPARSE_WEIGHT * (1.0 / (k + rank + 1))

        # RRF 스코어로 정렬
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        result = []
        for cid in sorted_ids:
            hit = hit_map[cid]
            hit.score = rrf_scores[cid]
            result.append(hit)

        return result

    # ──────────────────────────────────────────────
    # 다양성 확보
    # ──────────────────────────────────────────────

    def _diversify(self, hits: List[SearchHit], max_per_doc: int = DEFAULT_MAX_PER_DOC) -> List[SearchHit]:
        """동일 법령에서 최대 max_per_doc건만 유지 (다양성 확보)."""
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
            logger.error(f"Reranking 실패, RRF 결과 사용: {e}")
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
                collection_name=COLLECTION_DENSE,
                filter=filter_expr,
                output_fields=[
                    "chunk_id", "chunk_type", "parent_chunk_id", "orig_text",
                    "doc_name", "doc_type", "article_ref", "section_hierarchy",
                    "source_url", "effective_date", "references_to", "referenced_by",
                ],
            )

            parents = []
            for entity in results:
                hit = SearchHit(
                    chunk_id=entity.get("chunk_id", ""),
                    chunk_type="parent",
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
                parents.append(hit)

            return parents

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
