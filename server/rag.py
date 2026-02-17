"""RAG 모듈 — 텍스트 청킹 + OpenAI 임베딩 + pgvector 유사도 검색"""

import os
from openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

import db

# OpenAI 클라이언트 (lazy init)
_client = None

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def _get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def chunk_text(text: str) -> list[str]:
    """텍스트를 청크로 분할한다."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """OpenAI API로 텍스트 리스트의 임베딩을 생성한다."""
    client = _get_openai_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


async def store_chunks(document_id: int, chunks: list[str]):
    """청크를 임베딩과 함께 pgvector DB에 저장한다."""
    if not db.vector_pool or not chunks:
        return

    embeddings = get_embeddings(chunks)

    async with db.vector_pool.acquire() as conn:
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
            await conn.execute(
                """
                INSERT INTO document_chunks (document_id, chunk_index, chunk_text, embedding)
                VALUES ($1, $2, $3, $4::vector)
                """,
                document_id,
                i,
                chunk,
                embedding_str,
            )


async def search_similar_chunks(
    query: str,
    top_k: int = 5,
    purpose: str | None = None,
    document_ids: list[int] | None = None,
) -> list[dict]:
    """쿼리와 유사한 청크를 pgvector DB에서 검색한다.

    Args:
        purpose: 'consultant' 또는 'rag_session'으로 필터링
        document_ids: 특정 문서 ID 목록으로 필터링
    """
    if not db.vector_pool:
        return []

    query_embedding = get_embeddings([query])[0]
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    where_clauses = ["d.status = 'done'"]
    params: list = [embedding_str]
    idx = 2

    if purpose:
        where_clauses.append(f"d.purpose = ${idx}")
        params.append(purpose)
        idx += 1

    if document_ids:
        where_clauses.append(f"d.id = ANY(${idx}::int[])")
        params.append(document_ids)
        idx += 1

    where_sql = " AND ".join(where_clauses)
    params.append(top_k)

    async with db.vector_pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                dc.chunk_text,
                dc.document_id,
                d.filename,
                1 - (dc.embedding <=> $1::vector) AS similarity
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE {where_sql}
            ORDER BY dc.embedding <=> $1::vector
            LIMIT ${idx}
            """,
            *params,
        )

    return [
        {
            "chunk_text": row["chunk_text"],
            "document_id": row["document_id"],
            "filename": row["filename"],
            "similarity": float(row["similarity"]),
        }
        for row in rows
    ]
