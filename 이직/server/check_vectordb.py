"""pgvector DB 조회 스크립트 — 문서, 청크, 임베딩 상태 확인"""

import sys
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ.get("PGVECTOR_DATABASE_URL", "postgresql://postgres:nb60xg31qnu4rm04v4zvv24htz5580o6@nozomi.proxy.rlwy.net:51615/railway")


def connect():
    return psycopg2.connect(DB_URL)


def show_documents(cur):
    print("=" * 60)
    print("  documents 테이블")
    print("=" * 60)
    cur.execute("SELECT id, filename, file_type, status, error_msg, created_at FROM documents ORDER BY id")
    rows = cur.fetchall()
    if not rows:
        print("  (비어 있음)")
        return
    for r in rows:
        status = r[3]
        err = f" | error: {r[4]}" if r[4] else ""
        print(f"  id={r[0]} | {r[1]} | {r[2]} | {status}{err} | {r[5]}")
    print(f"  -> 총 {len(rows)}개 문서")


def show_chunks(cur):
    print()
    print("=" * 60)
    print("  document_chunks 요약")
    print("=" * 60)
    cur.execute("SELECT d.id, d.filename, COUNT(dc.id) FROM documents d LEFT JOIN document_chunks dc ON d.id = dc.document_id GROUP BY d.id, d.filename ORDER BY d.id")
    for r in cur.fetchall():
        print(f"  doc_id={r[0]} ({r[1]}) -> {r[2]}개 청크")
    cur.execute("SELECT COUNT(*), COUNT(embedding) FROM document_chunks")
    r = cur.fetchone()
    print(f"  -> 전체: {r[0]}개 청크 | 임베딩: {r[1]}개")


def show_chunk_preview(cur, limit=5):
    print()
    print("=" * 60)
    print(f"  청크 미리보기 (처음 {limit}개)")
    print("=" * 60)
    cur.execute("SELECT dc.document_id, dc.chunk_index, LEFT(dc.chunk_text, 100) FROM document_chunks dc ORDER BY dc.document_id, dc.chunk_index LIMIT %s", (limit,))
    rows = cur.fetchall()
    if not rows:
        print("  (비어 있음)")
        return
    for r in rows:
        print(f"  [{r[0]}-{r[1]}] {r[2]}...")


def show_embedding_sample(cur):
    print()
    print("=" * 60)
    print("  임베딩 벡터 샘플")
    print("=" * 60)
    cur.execute("SELECT chunk_index, LEFT(embedding::text, 70) FROM document_chunks ORDER BY document_id, chunk_index LIMIT 3")
    rows = cur.fetchall()
    if not rows:
        print("  (비어 있음)")
        return
    for r in rows:
        print(f"  chunk[{r[0]}] {r[1]}...")


def search_chunks(cur, query_text):
    """특정 문서 ID의 청크 전체 보기"""
    print()
    print("=" * 60)
    print(f"  document_id={query_text} 의 청크 전체")
    print("=" * 60)
    cur.execute("SELECT chunk_index, chunk_text FROM document_chunks WHERE document_id = %s ORDER BY chunk_index", (int(query_text),))
    rows = cur.fetchall()
    if not rows:
        print("  (해당 문서의 청크 없음)")
        return
    for r in rows:
        print(f"\n  --- chunk[{r[0]}] ---")
        print(f"  {r[1]}")


def main():
    args = sys.argv[1:]
    conn = connect()
    cur = conn.cursor()

    if not args or args[0] == "all":
        show_documents(cur)
        show_chunks(cur)
        show_chunk_preview(cur)
        show_embedding_sample(cur)
    elif args[0] == "docs":
        show_documents(cur)
    elif args[0] == "chunks":
        limit = int(args[1]) if len(args) > 1 else 5
        show_chunks(cur)
        show_chunk_preview(cur, limit)
    elif args[0] == "doc" and len(args) > 1:
        search_chunks(cur, args[1])
    elif args[0] == "sql" and len(args) > 1:
        query = " ".join(args[1:])
        print(f"  SQL: {query}")
        print("=" * 60)
        cur.execute(query)
        for r in cur.fetchall():
            print(f"  {r}")
    else:
        print("사용법:")
        print("  python check_vectordb.py           # 전체 요약")
        print("  python check_vectordb.py docs       # 문서 목록만")
        print("  python check_vectordb.py chunks 10  # 청크 미리보기 (10개)")
        print("  python check_vectordb.py doc 3      # 특정 문서의 청크 전체")
        print('  python check_vectordb.py sql "SELECT ..."  # 직접 SQL 실행')

    conn.close()


if __name__ == "__main__":
    main()
