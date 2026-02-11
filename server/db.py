import os
import json
import asyncpg
from dotenv import load_dotenv

load_dotenv()

pool = None


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


async def close_db():
    """Close the database connection pool."""
    global pool
    if pool:
        await pool.close()
        pool = None
        print("DB connection pool closed")


async def create_tables():
    """Create tables if they don't exist."""
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
