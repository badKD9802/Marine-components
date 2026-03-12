"""Milvus 인제스트 — Parent + Child 청크를 Dense/Sparse 컬렉션에 적재.

컬렉션 구조:
- safety_reg_dense: FLOAT_VECTOR (dim=1024) + 메타데이터
- safety_reg_sparse: SPARSE_FLOAT_VECTOR + 메타데이터

Child는 검색 대상, Parent는 chunk_type 필터로 검색에서 제외하되
chunk_id로 직접 조회 가능.
"""

import logging
from typing import List

from react_system.tools.safety_reg.chunker import SafetyChunk
from react_system.tools.safety_reg.constants import (
    COLLECTION_DENSE,
    COLLECTION_SPARSE,
)

logger = logging.getLogger(__name__)

# Dense 컬렉션 스키마 정의
DENSE_SCHEMA = {
    "collection_name": COLLECTION_DENSE,
    "fields": [
        {"name": "chunk_id", "dtype": "VARCHAR", "max_length": 512, "is_primary": True},
        {"name": "dense_vector", "dtype": "FLOAT_VECTOR", "dim": 1024},
        {"name": "chunk_type", "dtype": "VARCHAR", "max_length": 16},
        {"name": "parent_chunk_id", "dtype": "VARCHAR", "max_length": 512},
        {"name": "orig_text", "dtype": "VARCHAR", "max_length": 65535},
        {"name": "embed_text", "dtype": "VARCHAR", "max_length": 65535},
        {"name": "doc_name", "dtype": "VARCHAR", "max_length": 256},
        {"name": "doc_type", "dtype": "VARCHAR", "max_length": 64},
        {"name": "article_ref", "dtype": "VARCHAR", "max_length": 256},
        {"name": "section_hierarchy", "dtype": "VARCHAR", "max_length": 1024},
        {"name": "source_url", "dtype": "VARCHAR", "max_length": 1024},
        {"name": "effective_date", "dtype": "VARCHAR", "max_length": 32},
        {"name": "references_to", "dtype": "VARCHAR", "max_length": 4096},
        {"name": "referenced_by", "dtype": "VARCHAR", "max_length": 4096},
    ],
    "index": {
        "field_name": "dense_vector",
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 256},
    },
}

# Sparse 컬렉션 스키마 정의
SPARSE_SCHEMA = {
    "collection_name": COLLECTION_SPARSE,
    "fields": [
        {"name": "chunk_id", "dtype": "VARCHAR", "max_length": 512, "is_primary": True},
        {"name": "sparse_vector", "dtype": "SPARSE_FLOAT_VECTOR"},
        {"name": "chunk_type", "dtype": "VARCHAR", "max_length": 16},
        {"name": "parent_chunk_id", "dtype": "VARCHAR", "max_length": 512},
        {"name": "orig_text", "dtype": "VARCHAR", "max_length": 65535},
        {"name": "doc_name", "dtype": "VARCHAR", "max_length": 256},
        {"name": "doc_type", "dtype": "VARCHAR", "max_length": 64},
        {"name": "article_ref", "dtype": "VARCHAR", "max_length": 256},
        {"name": "section_hierarchy", "dtype": "VARCHAR", "max_length": 1024},
    ],
    "index": {
        "field_name": "sparse_vector",
        "index_type": "SPARSE_INVERTED_INDEX",
        "metric_type": "BM25",
    },
}


class SafetyRegIndexer:
    """Milvus에 안전법령 청크를 인덱싱."""

    def __init__(self, milvus_host: str = None, milvus_port: str = "19530"):
        """
        Args:
            milvus_host: Milvus 호스트. None이면 resolve_milvus_connection() 사용.
            milvus_port: Milvus 포트.
        """
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self._client = None

    async def _get_client(self):
        """Milvus 클라이언트 가져오기 (lazy init)."""
        if self._client is not None:
            return self._client

        host, port = self._resolve_connection()

        try:
            from pymilvus import MilvusClient

            uri = f"http://{host}:{port}"
            self._client = MilvusClient(uri=uri)
            logger.info(f"Milvus 연결 성공: {uri}")
            return self._client
        except Exception as e:
            logger.error(f"Milvus 연결 실패: {e}")
            raise

    def _resolve_connection(self):
        """Milvus 연결 정보 해결."""
        if self.milvus_host:
            return self.milvus_host, self.milvus_port
        import os
        host = os.getenv("MILVUS_HOST", "localhost")
        port = os.getenv("MILVUS_PORT", "19530")
        return host, port

    async def create_collections(self, drop_existing: bool = False):
        """Dense/Sparse 컬렉션 생성.

        Args:
            drop_existing: True면 기존 컬렉션 삭제 후 재생성.
        """
        client = await self._get_client()

        for schema_def in [DENSE_SCHEMA, SPARSE_SCHEMA]:
            coll_name = schema_def["collection_name"]

            if client.has_collection(coll_name):
                if drop_existing:
                    client.drop_collection(coll_name)
                    logger.info(f"컬렉션 삭제: {coll_name}")
                else:
                    logger.info(f"컬렉션 이미 존재: {coll_name}")
                    continue

            from pymilvus import CollectionSchema, DataType, FieldSchema

            fields = []
            for f in schema_def["fields"]:
                kwargs = {"name": f["name"]}

                dtype_str = f["dtype"]
                if dtype_str == "VARCHAR":
                    kwargs["dtype"] = DataType.VARCHAR
                    kwargs["max_length"] = f.get("max_length", 256)
                elif dtype_str == "FLOAT_VECTOR":
                    kwargs["dtype"] = DataType.FLOAT_VECTOR
                    kwargs["dim"] = f.get("dim", 1024)
                elif dtype_str == "SPARSE_FLOAT_VECTOR":
                    kwargs["dtype"] = DataType.SPARSE_FLOAT_VECTOR

                kwargs["is_primary"] = f.get("is_primary", False)
                fields.append(FieldSchema(**kwargs))

            schema = CollectionSchema(fields=fields, description=f"Safety Regulation {coll_name}")
            client.create_collection(collection_name=coll_name, schema=schema)

            # 인덱스 생성
            idx = schema_def["index"]
            index_params = {
                "index_type": idx["index_type"],
                "metric_type": idx["metric_type"],
            }
            if "params" in idx:
                index_params["params"] = idx["params"]

            client.create_index(
                collection_name=coll_name,
                field_name=idx["field_name"],
                index_params=index_params,
            )

            logger.info(f"컬렉션 생성 완료: {coll_name}")

    async def ingest(
        self,
        chunks: List[SafetyChunk],
        embedding_fn=None,
        tokenize_fn=None,
        batch_size: int = 50,
    ):
        """청크 리스트를 Dense + Sparse 컬렉션에 적재.

        Args:
            chunks: SafetyChunk 리스트
            embedding_fn: async (texts: List[str]) -> List[List[float]] 임베딩 함수
            tokenize_fn: (text: str) -> dict sparse 벡터 변환 함수
            batch_size: 배치 크기
        """
        if not chunks:
            logger.warning("인제스트할 청크가 없습니다.")
            return

        client = await self._get_client()

        # 컬렉션이 없으면 자동 생성
        await self.create_collections(drop_existing=False)

        # 배치 처리
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            logger.info(f"인제스트 배치 {i // batch_size + 1}: {len(batch)}건")

            # Dense 인제스트
            if embedding_fn:
                texts = [c.embed_text for c in batch]
                embeddings = await embedding_fn(texts)

                dense_data = []
                for chunk, emb in zip(batch, embeddings):
                    dense_data.append({
                        "chunk_id": chunk.chunk_id,
                        "dense_vector": emb,
                        "chunk_type": chunk.chunk_type,
                        "parent_chunk_id": chunk.parent_chunk_id,
                        "orig_text": chunk.orig_text[:65000],
                        "embed_text": chunk.embed_text[:65000],
                        "doc_name": chunk.doc_name,
                        "doc_type": chunk.doc_type,
                        "article_ref": chunk.article_ref,
                        "section_hierarchy": chunk.section_hierarchy,
                        "source_url": chunk.source_url,
                        "effective_date": chunk.effective_date,
                        "references_to": chunk.references_to,
                        "referenced_by": chunk.referenced_by,
                    })

                client.insert(collection_name=COLLECTION_DENSE, data=dense_data)

            # Sparse 인제스트
            if tokenize_fn:
                sparse_data = []
                for chunk in batch:
                    sparse_vec = tokenize_fn(chunk.embed_text)
                    sparse_data.append({
                        "chunk_id": chunk.chunk_id,
                        "sparse_vector": sparse_vec,
                        "chunk_type": chunk.chunk_type,
                        "parent_chunk_id": chunk.parent_chunk_id,
                        "orig_text": chunk.orig_text[:65000],
                        "doc_name": chunk.doc_name,
                        "doc_type": chunk.doc_type,
                        "article_ref": chunk.article_ref,
                        "section_hierarchy": chunk.section_hierarchy,
                    })

                client.insert(collection_name=COLLECTION_SPARSE, data=sparse_data)

        logger.info(f"인제스트 완료: {len(chunks)}건")

    async def reindex_laws(self, updates: List[dict], api_client, chunker, embedding_fn=None, tokenize_fn=None):
        """변경된 법령만 재수집 → 재청킹 → 기존 청크 삭제 → 재인덱싱.

        Args:
            updates: check_updates() 반환 리스트
            api_client: LawApiClient 인스턴스
            chunker: SafetyRegChunker 인스턴스
            embedding_fn: 임베딩 함수
            tokenize_fn: 토크나이즈 함수
        """
        for update in updates:
            name = update["name"]
            logger.info(f"법령 재인덱싱 시작: {name}")

            # 1. API에서 최신 본문 수집
            doc = await api_client.get_law_full(update["mst"], name, update["doc_type"])
            if not doc:
                logger.error(f"법령 재수집 실패: {name}")
                continue

            # JSON 저장
            api_client._save_to_json(doc)

            # 2. 청킹
            chunks = chunker.chunk_document(doc)

            # 3. 기존 청크 삭제
            await self._delete_by_doc_name(name)

            # 4. 재인덱싱
            await self.ingest(chunks, embedding_fn=embedding_fn, tokenize_fn=tokenize_fn)
            logger.info(f"법령 재인덱싱 완료: {name} ({len(chunks)} 청크)")

    async def _delete_by_doc_name(self, doc_name: str):
        """특정 법령의 모든 청크 삭제."""
        client = await self._get_client()
        filter_expr = f'doc_name == "{doc_name}"'

        try:
            client.delete(collection_name=COLLECTION_DENSE, filter=filter_expr)
            client.delete(collection_name=COLLECTION_SPARSE, filter=filter_expr)
            logger.info(f"기존 청크 삭제 완료: {doc_name}")
        except Exception as e:
            logger.error(f"청크 삭제 실패 [{doc_name}]: {e}")

    async def get_collection_stats(self) -> dict:
        """컬렉션 통계 조회."""
        client = await self._get_client()
        stats = {}
        for coll_name in [COLLECTION_DENSE, COLLECTION_SPARSE]:
            if client.has_collection(coll_name):
                info = client.get_collection_stats(coll_name)
                stats[coll_name] = info
            else:
                stats[coll_name] = {"exists": False}
        return stats
