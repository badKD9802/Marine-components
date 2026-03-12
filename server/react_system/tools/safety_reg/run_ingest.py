"""안전법령 데이터 Milvus 인덱싱 스크립트.

Usage:
  cd server
  python3 -m react_system.tools.safety_reg.run_ingest

환경변수:
  OPENAI_API_KEY   — 임베딩 API 키 (필수)
  MILVUS_HOST      — Milvus 호스트 (기본: localhost)
  MILVUS_PORT      — Milvus 포트 (기본: 19530)
"""

import asyncio
import os
import sys
import time

# server/ 디렉토리를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from react_system.tools.safety_reg.law_api_client import LawApiClient
from react_system.tools.safety_reg.chunker import SafetyChunker
from react_system.tools.safety_reg.indexer import SafetyRegIndexer


def _get_embedding_fn():
    """임베딩 함수 — text-embedding-3-small (dim=1024)."""

    async def embed(texts):
        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL")

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.embeddings.create(
            input=texts,
            model="text-embedding-3-small",
            dimensions=1024,
        )
        return [item.embedding for item in response.data]

    return embed


def _get_tokenize_fn():
    """BM25 토크나이즈 함수 — Kiwi 형태소 분석기."""
    from kiwipiepy import Kiwi

    kiwi = Kiwi()

    def tokenize(text):
        tokens = kiwi.tokenize(text)
        sparse = {}
        for token in tokens:
            key = hash(token.form) % (2**31)
            sparse[key] = sparse.get(key, 0) + 1.0
        return sparse

    return tokenize


async def main():
    data_dir = os.path.join(os.path.dirname(__file__), "data", "laws")

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    host = os.getenv("MILVUS_HOST", "localhost")
    port = os.getenv("MILVUS_PORT", "19530")
    print(f"📌 Milvus: {host}:{port}")
    print(f"📌 데이터: {data_dir}")
    print()

    # 1. JSON 로드
    t0 = time.time()
    client = LawApiClient()
    docs = client.load_from_json(data_dir)
    print(f"[1/3] 문서 로드 완료: {len(docs)}개 ({time.time()-t0:.1f}초)")

    # 2. 청킹
    t1 = time.time()
    chunker = SafetyChunker()
    chunks = chunker.chunk_all(docs)
    parents = [c for c in chunks if c.chunk_type == "parent"]
    children = [c for c in chunks if c.chunk_type == "child"]
    print(f"[2/3] 청킹 완료: {len(chunks)}개 (Parent {len(parents)}, Child {len(children)}) ({time.time()-t1:.1f}초)")

    # 3. 임베딩 + Milvus 인덱싱
    t2 = time.time()
    indexer = SafetyRegIndexer(milvus_host=host, milvus_port=int(port))
    embedding_fn = _get_embedding_fn()
    tokenize_fn = _get_tokenize_fn()
    await indexer.ingest(chunks, embedding_fn=embedding_fn, tokenize_fn=tokenize_fn)
    print(f"[3/3] 인덱싱 완료! ({time.time()-t2:.1f}초)")

    print()
    print(f"✅ 전체 완료 — 총 {time.time()-t0:.1f}초")


if __name__ == "__main__":
    asyncio.run(main())
