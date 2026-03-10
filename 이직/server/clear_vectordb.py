"""pgvector DB 데이터 삭제 스크립트 — 문서/청크 정리용"""

import sys
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ.get("PGVECTOR_DATABASE_URL", "postgresql://postgres:nb60xg31qnu4rm04v4zvv24htz5580o6@nozomi.proxy.rlwy.net:51615/railway")


def connect():
    return psycopg2.connect(DB_URL)


def show_status(cur):
    cur.execute("SELECT COUNT(*) FROM documents")
    doc_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM document_chunks")
    chunk_count = cur.fetchone()[0]
    print(f"  현재 상태: 문서 {doc_count}개 | 청크 {chunk_count}개")
    return doc_count, chunk_count


def delete_document(cur, doc_id):
    """특정 문서 삭제 (CASCADE로 청크도 함께 삭제)"""
    cur.execute("SELECT filename FROM documents WHERE id = %s", (doc_id,))
    row = cur.fetchone()
    if not row:
        print(f"  document_id={doc_id} 없음")
        return
    print(f"  삭제: id={doc_id} ({row[0]})")
    cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    print(f"  완료 (청크도 CASCADE 삭제됨)")


def delete_error_docs(cur):
    """status='error'인 문서 전체 삭제"""
    cur.execute("SELECT id, filename FROM documents WHERE status = 'error'")
    rows = cur.fetchall()
    if not rows:
        print("  에러 문서 없음")
        return
    for r in rows:
        print(f"  삭제: id={r[0]} ({r[1]})")
    cur.execute("DELETE FROM documents WHERE status = 'error'")
    print(f"  -> {len(rows)}개 에러 문서 삭제 완료")


def delete_all(cur):
    """모든 데이터 삭제"""
    cur.execute("DELETE FROM document_chunks")
    chunk_del = cur.rowcount
    cur.execute("DELETE FROM documents")
    doc_del = cur.rowcount
    print(f"  삭제 완료: 문서 {doc_del}개, 청크 {chunk_del}개")


def confirm(message):
    answer = input(f"  {message} (y/N): ").strip().lower()
    return answer == "y"


def main():
    args = sys.argv[1:]
    conn = connect()
    cur = conn.cursor()

    print()
    show_status(cur)
    print()

    if not args:
        print("사용법:")
        print("  python clear_vectordb.py doc 2       # 특정 문서 삭제 (id=2)")
        print("  python clear_vectordb.py errors      # 에러 문서 전체 삭제")
        print("  python clear_vectordb.py all          # 모든 데이터 삭제")
        conn.close()
        return

    if args[0] == "doc" and len(args) > 1:
        doc_id = int(args[1])
        if confirm(f"document_id={doc_id} 를 삭제하시겠습니까?"):
            delete_document(cur, doc_id)
            conn.commit()
        else:
            print("  취소됨")

    elif args[0] == "errors":
        if confirm("에러 상태 문서를 모두 삭제하시겠습니까?"):
            delete_error_docs(cur)
            conn.commit()
        else:
            print("  취소됨")

    elif args[0] == "all":
        if confirm("정말 모든 데이터를 삭제하시겠습니까?"):
            delete_all(cur)
            conn.commit()
        else:
            print("  취소됨")

    else:
        print(f"  알 수 없는 명령: {args[0]}")

    print()
    show_status(cur)
    conn.close()


if __name__ == "__main__":
    main()
