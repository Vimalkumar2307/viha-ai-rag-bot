import os
import sys

# Load .env FIRST before any other imports
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path)

db_url = os.getenv("SUPABASE_DB_URL")
print(f"DB URL loaded: {'✅' if db_url else '❌ NOT FOUND'}")
print(f"DB URL: {db_url[:50] if db_url else 'None'}")

# NOW import everything else
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_db_connection
from services.rag_service import generate_embedding, build_product_text


def embed_all_products():
    print("🚀 Starting product embedding generation...")

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, category, description
                FROM products ORDER BY id
            """)
            products = cursor.fetchall()
            print(f"📦 Found {len(products)} products to embed")

            success = 0
            failed = 0

            for pid, name, category, description in products:
                try:
                    product_dict = {
                        "name": name,
                        "category": category,
                        "description": description
                    }
                    text = build_product_text(product_dict)
                    print(f"\n   Product: {name}")
                    print(f"   Text:    {text}")

                    embedding = generate_embedding(text)
                    embedding_str = "[" + ",".join(map(str, embedding)) + "]"

                    cursor.execute("""
                        INSERT INTO product_embeddings
                            (product_id, embedding, content, product_name, category)
                        VALUES (%s, %s::vector, %s, %s, %s)
                        ON CONFLICT (product_id)
                        DO UPDATE SET
                            embedding    = EXCLUDED.embedding,
                            content      = EXCLUDED.content,
                            product_name = EXCLUDED.product_name,
                            category     = EXCLUDED.category
                    """, (pid, embedding_str, text, name, category))

                    conn.commit()
                    print(f"   ✅ Embedded successfully")
                    success += 1

                except Exception as e:
                    print(f"   ❌ Failed: {name} — {e}")
                    failed += 1

    print(f"\n{'='*50}")
    print(f"✅ Done! Success: {success} | Failed: {failed}")
    print(f"{'='*50}")


if __name__ == "__main__":
    embed_all_products()