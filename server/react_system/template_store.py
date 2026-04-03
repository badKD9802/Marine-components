"""
Milvus 양식/예시문 저장소 — 컬렉션 관리 + CRUD

document_templates 컬렉션:
- 양식 전체(template), 양식 섹션(section), 잘 쓴 예시(example)를 단일 컬렉션에 저장
- Partition Key(visibility)로 멀티테넌시 (public / user:{id})
- Dense + Sparse 하이브리드 벡터 검색
"""

import logging
import os
import time
from typing import Optional

from pymilvus import (
    AnnSearchRequest,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    RRFRanker,
)

logger = logging.getLogger(__name__)

# ─── 상수 ───

COLLECTION_NAME = "document_templates"
DENSE_DIM = 1024  # text-embedding-3-small (dimensions=1024)

# 기본 검색 파라미터
DEFAULT_TOP_K = 20
DEFAULT_RRF_K = 40

# 반환 필드
OUTPUT_FIELDS = [
    "id", "template_id", "chunk_type", "parent_id",
    "title", "content", "category", "subcategory",
    "visibility", "user_id", "metadata",
    "created_at", "updated_at",
]


# ─── 스키마 정의 ───

FIELDS = [
    {"name": "id", "dtype": DataType.VARCHAR, "max_length": 256, "is_primary": True},
    {"name": "dense_vector", "dtype": DataType.FLOAT_VECTOR, "dim": DENSE_DIM},
    {"name": "sparse_vector", "dtype": DataType.SPARSE_FLOAT_VECTOR},
    {"name": "template_id", "dtype": DataType.VARCHAR, "max_length": 256},
    {"name": "chunk_type", "dtype": DataType.VARCHAR, "max_length": 16},
    {"name": "parent_id", "dtype": DataType.VARCHAR, "max_length": 256},
    {"name": "title", "dtype": DataType.VARCHAR, "max_length": 512},
    {"name": "content", "dtype": DataType.VARCHAR, "max_length": 65535},
    {"name": "category", "dtype": DataType.VARCHAR, "max_length": 64},
    {"name": "subcategory", "dtype": DataType.VARCHAR, "max_length": 64},
    {"name": "visibility", "dtype": DataType.VARCHAR, "max_length": 64, "is_partition_key": True},
    {"name": "user_id", "dtype": DataType.VARCHAR, "max_length": 64},
    {"name": "metadata", "dtype": DataType.JSON},
    {"name": "created_at", "dtype": DataType.INT64},
    {"name": "updated_at", "dtype": DataType.INT64},
]

INDEXES = [
    {
        "field_name": "dense_vector",
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 256},
    },
    {
        "field_name": "sparse_vector",
        "index_type": "SPARSE_INVERTED_INDEX",
        "metric_type": "IP",
    },
]

# 스칼라 인덱스 (필터링 성능 향상)
SCALAR_INDEXES = [
    {"field_name": "category", "index_type": "INVERTED"},
    {"field_name": "chunk_type", "index_type": "INVERTED"},
    {"field_name": "template_id", "index_type": "INVERTED"},
    {"field_name": "user_id", "index_type": "INVERTED"},
]


# ─── 임베딩 함수 ───

def get_embedding_fn():
    """OpenAI text-embedding-3-small (dim=1024) 임베딩 함수."""

    async def embed(texts: list[str]) -> list[list[float]]:
        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL")
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        response = await client.embeddings.create(
            input=texts,
            model="text-embedding-3-small",
            dimensions=DENSE_DIM,
        )
        return [item.embedding for item in response.data]

    return embed


def get_tokenize_fn():
    """BM25 토크나이즈 함수 — Kiwi 형태소 분석기 (폴백: 공백 분리)."""
    _kiwi = None

    def tokenize(text: str) -> dict:
        nonlocal _kiwi
        if _kiwi is None:
            try:
                from kiwipiepy import Kiwi
                _kiwi = Kiwi()
            except ImportError:
                _kiwi = False

        sparse = {}
        if _kiwi:
            tokens = _kiwi.tokenize(text)
            for token in tokens:
                key = hash(token.form) % (2**31)
                sparse[key] = sparse.get(key, 0) + 1.0
        else:
            for word in text.split():
                key = hash(word) % (2**31)
                sparse[key] = sparse.get(key, 0) + 1.0
        return sparse

    return tokenize


# ─── 메인 클래스 ───

class TemplateStore:
    """Milvus document_templates 컬렉션 관리."""

    def __init__(self, milvus_host: str = None, milvus_port: str = "19530"):
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self._client: Optional[MilvusClient] = None

    async def _get_client(self) -> MilvusClient:
        """Milvus 클라이언트 lazy init."""
        if self._client is not None:
            return self._client

        host = self.milvus_host or os.getenv("MILVUS_HOST", "localhost")
        port = self.milvus_port or os.getenv("MILVUS_PORT", "19530")

        uri = f"http://{host}:{port}"
        self._client = MilvusClient(uri=uri)
        logger.info(f"Milvus 연결: {uri}")
        return self._client

    # ─── 컬렉션 관리 ───

    async def create_collection(self, drop_existing: bool = False):
        """document_templates 컬렉션 생성."""
        client = await self._get_client()

        if client.has_collection(COLLECTION_NAME):
            if drop_existing:
                client.drop_collection(COLLECTION_NAME)
                logger.info(f"컬렉션 삭제: {COLLECTION_NAME}")
            else:
                logger.info(f"컬렉션 이미 존재: {COLLECTION_NAME}")
                return

        # 스키마 생성
        fields = []
        for f in FIELDS:
            kwargs = {"name": f["name"], "dtype": f["dtype"]}
            if "max_length" in f:
                kwargs["max_length"] = f["max_length"]
            if "dim" in f:
                kwargs["dim"] = f["dim"]
            if f.get("is_primary"):
                kwargs["is_primary"] = True
            if f.get("is_partition_key"):
                kwargs["is_partition_key"] = True
            fields.append(FieldSchema(**kwargs))

        schema = CollectionSchema(
            fields=fields,
            description="양식/예시문 저장소 (Partition Key 멀티테넌시)",
        )
        client.create_collection(
            collection_name=COLLECTION_NAME,
            schema=schema,
            num_partitions=64,
        )

        # 벡터 인덱스
        index_params = MilvusClient.prepare_index_params()
        for idx in INDEXES:
            index_params.add_index(
                field_name=idx["field_name"],
                index_type=idx["index_type"],
                metric_type=idx["metric_type"],
                params=idx.get("params", {}),
            )
        client.create_index(
            collection_name=COLLECTION_NAME,
            index_params=index_params,
        )

        logger.info(f"컬렉션 생성 완료: {COLLECTION_NAME}")

    # ─── 삽입 ───

    async def insert(
        self,
        records: list[dict],
        embedding_fn=None,
        tokenize_fn=None,
        batch_size: int = 50,
    ):
        """레코드 리스트를 컬렉션에 삽입."""
        if not records:
            return

        await self.create_collection(drop_existing=False)
        client = await self._get_client()

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]

            # Dense 임베딩 생성
            if embedding_fn:
                texts = [r.get("content", r.get("title", "")) for r in batch]
                embeddings = await embedding_fn(texts)
            else:
                embeddings = None

            # 레코드에 벡터 추가
            data = []
            for j, rec in enumerate(batch):
                now = int(time.time())
                record = {
                    "id": rec["id"],
                    "template_id": rec.get("template_id", ""),
                    "chunk_type": rec.get("chunk_type", "template"),
                    "parent_id": rec.get("parent_id", ""),
                    "title": rec.get("title", "")[:512],
                    "content": rec.get("content", "")[:65000],
                    "category": rec.get("category", "")[:64],
                    "subcategory": rec.get("subcategory", "")[:64],
                    "visibility": rec.get("visibility", "public"),
                    "user_id": rec.get("user_id", ""),
                    "metadata": rec.get("metadata", {}),
                    "created_at": rec.get("created_at", now),
                    "updated_at": rec.get("updated_at", now),
                }

                # Dense vector
                if embeddings:
                    record["dense_vector"] = embeddings[j]
                else:
                    record["dense_vector"] = [0.0] * DENSE_DIM

                # Sparse vector
                if tokenize_fn:
                    record["sparse_vector"] = tokenize_fn(
                        rec.get("content", rec.get("title", ""))
                    )
                else:
                    record["sparse_vector"] = {0: 1.0}

                data.append(record)

            client.insert(collection_name=COLLECTION_NAME, data=data)
            logger.info(f"삽입 배치 {i // batch_size + 1}: {len(batch)}건")

        logger.info(f"삽입 완료: {len(records)}건")

    # ─── 삭제 ───

    async def delete(self, ids: list[str]):
        """ID 리스트로 레코드 삭제."""
        if not ids:
            return
        client = await self._get_client()
        ids_str = ", ".join(f'"{id_}"' for id_ in ids)
        client.delete(
            collection_name=COLLECTION_NAME,
            filter=f'id in [{ids_str}]',
        )
        logger.info(f"삭제 완료: {len(ids)}건")

    # ─── 조회 ───

    async def get_by_id(self, id_: str) -> Optional[dict]:
        """ID로 단일 레코드 조회."""
        client = await self._get_client()
        results = client.query(
            collection_name=COLLECTION_NAME,
            filter=f'id == "{id_}"',
            output_fields=OUTPUT_FIELDS,
            limit=1,
        )
        return results[0] if results else None

    async def query(
        self,
        filter_expr: str,
        limit: int = 20,
        offset: int = 0,
        output_fields: list[str] = None,
    ) -> list[dict]:
        """필터 기반 조회 (벡터 검색 없음)."""
        client = await self._get_client()
        return client.query(
            collection_name=COLLECTION_NAME,
            filter=filter_expr,
            output_fields=output_fields or OUTPUT_FIELDS,
            limit=limit,
            offset=offset,
        )

    # ─── 하이브리드 검색 ───

    async def hybrid_search(
        self,
        query_text: str,
        embedding_fn,
        tokenize_fn,
        filter_expr: str = None,
        limit: int = DEFAULT_TOP_K,
    ) -> list[dict]:
        """Dense + Sparse 하이브리드 검색 (RRFRanker)."""
        client = await self._get_client()

        reqs = []

        # Dense 검색
        if embedding_fn:
            embeddings = await embedding_fn([query_text])
            if embeddings:
                dense_req = AnnSearchRequest(
                    data=[embeddings[0]],
                    anns_field="dense_vector",
                    param={"metric_type": "COSINE", "params": {"nprobe": 64}},
                    limit=limit,
                    expr=filter_expr or "",
                )
                reqs.append(dense_req)

        # Sparse 검색
        if tokenize_fn:
            sparse_vec = tokenize_fn(query_text)
            sparse_req = AnnSearchRequest(
                data=[sparse_vec],
                anns_field="sparse_vector",
                param={"metric_type": "IP"},
                limit=limit,
                expr=filter_expr or "",
            )
            reqs.append(sparse_req)

        if not reqs:
            logger.error("검색 요청 없음")
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
                entity["score"] = res.get("distance", 0.0)
                hits.append(entity)
            return hits

        except Exception as e:
            logger.error(f"하이브리드 검색 실패: {e}")
            return []
