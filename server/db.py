import os
import json
import asyncpg
from dotenv import load_dotenv

load_dotenv()

pool = None          # 일반 DB (products)
vector_pool = None   # pgvector DB (documents, chunks, embeddings)


async def init_db():
    """Initialize the database connection pool and create tables."""
    global pool
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("WARNING: DATABASE_URL not set, DB features disabled")
        return

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    await create_tables()
    print("DB connection pool initialized")


async def init_vector_db():
    """Initialize the pgvector database connection pool and create RAG tables."""
    global vector_pool
    vector_url = os.environ.get("PGVECTOR_DATABASE_URL")
    if not vector_url:
        print("WARNING: PGVECTOR_DATABASE_URL not set, RAG features disabled")
        return

    vector_pool = await asyncpg.create_pool(vector_url, min_size=1, max_size=5)
    await create_vector_tables()
    print("pgvector DB connection pool initialized")


async def close_db():
    """Close the database connection pool."""
    global pool
    if pool:
        await pool.close()
        pool = None
        print("DB connection pool closed")


async def close_vector_db():
    """Close the pgvector database connection pool."""
    global vector_pool
    if vector_pool:
        await vector_pool.close()
        vector_pool = None
        print("pgvector DB connection pool closed")


async def create_tables():
    """Create product tables in the main DB."""
    if not pool:
        return
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id            SERIAL PRIMARY KEY,
                image         TEXT NOT NULL,
                part_no       TEXT NOT NULL,
                price         TEXT NOT NULL,
                brand         TEXT NOT NULL DEFAULT '',
                category      TEXT NOT NULL DEFAULT '',
                name          JSONB NOT NULL,
                description   JSONB NOT NULL,
                category_name JSONB NOT NULL DEFAULT '{}',
                detail_info   JSONB NOT NULL DEFAULT '{}',
                specs         JSONB NOT NULL DEFAULT '{}',
                compatibility JSONB NOT NULL DEFAULT '{}',
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                updated_at    TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inquiries (
                id            SERIAL PRIMARY KEY,
                author_name   TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                title         TEXT NOT NULL,
                content       TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'waiting',
                created_at    TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inquiry_replies (
                id          SERIAL PRIMARY KEY,
                inquiry_id  INTEGER NOT NULL REFERENCES inquiries(id) ON DELETE CASCADE,
                content     TEXT NOT NULL,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)


async def create_vector_tables():
    """Create RAG tables in the pgvector DB."""
    if not vector_pool:
        return
    async with vector_pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id          SERIAL PRIMARY KEY,
                filename    TEXT NOT NULL,
                file_type   TEXT NOT NULL,
                raw_text    TEXT,
                status      TEXT DEFAULT 'pending',
                error_msg   TEXT,
                purpose     TEXT DEFAULT 'consultant',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 기존 테이블에 purpose 컬럼이 없으면 추가
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'documents' AND column_name = 'purpose'
                ) THEN
                    ALTER TABLE documents ADD COLUMN purpose TEXT DEFAULT 'consultant';
                END IF;
            END $$;
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id           SERIAL PRIMARY KEY,
                document_id  INTEGER REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index  INTEGER NOT NULL,
                chunk_text   TEXT NOT NULL,
                embedding    vector(1536),
                created_at   TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                ON document_chunks USING hnsw (embedding vector_cosine_ops);
        """)

        # RAG 대화 세션 테이블
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rag_conversations (
                id          SERIAL PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT '새 대화',
                saved       BOOLEAN NOT NULL DEFAULT FALSE,
                created_at  TIMESTAMPTZ DEFAULT NOW(),
                updated_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 기존 rag_conversations에 saved 컬럼이 없으면 추가
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'rag_conversations' AND column_name = 'saved'
                ) THEN
                    ALTER TABLE rag_conversations ADD COLUMN saved BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
            END $$;
        """)

        # RAG 대화 메시지 테이블
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rag_messages (
                id              SERIAL PRIMARY KEY,
                conversation_id INTEGER REFERENCES rag_conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                refs            JSONB DEFAULT '[]',
                created_at      TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 메일 작성 이력 테이블
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mail_compositions (
                id               SERIAL PRIMARY KEY,
                incoming_email   TEXT NOT NULL,
                detected_lang    TEXT DEFAULT 'en',
                tone             TEXT DEFAULT 'formal',
                korean_draft     TEXT,
                translated_draft TEXT,
                document_ids     JSONB DEFAULT '[]',
                refs             JSONB DEFAULT '[]',
                created_at       TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Gmail 설정 테이블 (단일 행)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS gmail_config (
                id                 SERIAL PRIMARY KEY,
                email              TEXT NOT NULL,
                app_password       TEXT NOT NULL,
                check_time         TEXT DEFAULT '09:00',
                auto_reply_enabled BOOLEAN DEFAULT FALSE,
                last_checked_at    TIMESTAMPTZ,
                created_at         TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # 수신 메일 테이블
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inbox_emails (
                id              SERIAL PRIMARY KEY,
                gmail_uid       TEXT,
                from_addr       TEXT NOT NULL,
                from_name       TEXT,
                subject         TEXT,
                body            TEXT,
                received_at     TIMESTAMPTZ,
                status          TEXT DEFAULT 'new',
                composition_id  INTEGER REFERENCES mail_compositions(id) ON DELETE SET NULL,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        print("pgvector + RAG 테이블 생성 완료")


async def get_all_products(category: str = None, search: str = None):
    """Get all products with optional category filter and search."""
    if not pool:
        return []
    async with pool.acquire() as conn:
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        idx = 1

        if category and category != "all":
            query += f" AND category = ${idx}"
            params.append(category)
            idx += 1

        if search:
            query += f" AND (part_no ILIKE ${idx} OR name::text ILIKE ${idx} OR description::text ILIKE ${idx})"
            params.append(f"%{search}%")
            idx += 1

        query += " ORDER BY id"
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_product_by_id(product_id: int):
    """Get a single product by ID."""
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
        return dict(row) if row else None


async def create_product(product: dict):
    """Insert a new product and return it."""
    if not pool:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO products (image, part_no, price, brand, category, name, description, category_name, detail_info, specs, compatibility)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
        """,
            product["image"],
            product["part_no"],
            product["price"],
            product.get("brand", ""),
            product.get("category", ""),
            json.dumps(product["name"], ensure_ascii=False),
            json.dumps(product["description"], ensure_ascii=False),
            json.dumps(product.get("category_name", {}), ensure_ascii=False),
            json.dumps(product.get("detail_info", {}), ensure_ascii=False),
            json.dumps(product.get("specs", {}), ensure_ascii=False),
            json.dumps(product.get("compatibility", {}), ensure_ascii=False),
        )
        return dict(row) if row else None


async def search_products(keyword: str):
    """Search products by keyword across name, description, part_no."""
    if not pool:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM products
            WHERE part_no ILIKE $1
               OR name::text ILIKE $1
               OR description::text ILIKE $1
               OR brand ILIKE $1
            ORDER BY id
        """, f"%{keyword}%")
        return [dict(row) for row in rows]


async def get_products_for_ai_prompt():
    """Get product info formatted for AI system prompt."""
    if not pool:
        return None
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT name, price, part_no, brand, description FROM products ORDER BY id")
        if not rows:
            return None

        lines = []
        for row in rows:
            name_data = row["name"] if isinstance(row["name"], dict) else json.loads(row["name"])
            desc_data = row["description"] if isinstance(row["description"], dict) else json.loads(row["description"])
            ko_name = name_data.get("ko", "")
            ko_desc = desc_data.get("ko", "")
            lines.append(f"- {ko_name} (Part No: {row['part_no']}, Brand: {row['brand']}): {row['price']}원 - {ko_desc}")

        return "\n".join(lines)
