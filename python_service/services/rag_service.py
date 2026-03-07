import os
import numpy as np
from sentence_transformers import SentenceTransformer
from db.connection import get_db_connection

# Lazy load — model loads on first use, not at startup
_model = None

def _get_model():
    global _model
    if _model is None:
        print("⏳ Loading sentence transformer model...")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Sentence transformer model loaded")
    return _model


def generate_embedding(text: str) -> list[float]:
    model = _get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def build_product_text(product: dict) -> str:
    parts = []
    if product.get("name"):
        parts.append(product["name"])
    if product.get("category"):
        parts.append(product["category"])
    if product.get("description"):
        parts.append(product["description"])

    category = (product.get("category") or "").lower()
    if "eco" in category:
        parts.append("eco friendly green sustainable environment plantable")
    if "traditional" in category:
        parts.append("traditional ethnic indian cultural festive")
    if "religious" in category:
        parts.append("religious god temple pooja spiritual")
    if "kids" in category:
        parts.append("kids children birthday school fun colorful")
    if "premium" in category:
        parts.append("premium luxury high quality elegant")
    if "practical" in category:
        parts.append("practical useful everyday functional")

    return " ".join(parts)


def search_products_by_semantic(
    query: str,
    budget_min: int = 0,
    budget_max: int = 10000,
    quantity: int = 1,
    limit: int = 10
) -> list[dict]:
    print(f"    🔍 RAG Search: '{query}' budget={budget_min}-{budget_max} qty={quantity}")

    query_embedding = generate_embedding(query)
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        p.id, p.name, p.category, p.description,
                        p.image_url, p.min_order, p.has_variants,
                        pe.embedding <=> %s::vector AS distance
                    FROM product_embeddings pe
                    JOIN products p ON pe.product_id = p.id
                    WHERE p.min_order <= %s
                    ORDER BY distance ASC
                    LIMIT 20
                """, (embedding_str, quantity))

                semantic_results = cursor.fetchall()
                print(f"    📊 Semantic matches: {len(semantic_results)}")

                if not semantic_results:
                    return []

                matching_products = []

                for row in semantic_results:
                    pid, name, category, description, image_url, min_order, has_variants, distance = row

                    if has_variants:
                        cursor.execute("""
                            SELECT size, type, design_name, quantity_range,
                                   price_per_piece, image_url
                            FROM product_variants
                            WHERE product_id = %s AND is_available = TRUE
                            ORDER BY price_per_piece
                        """, (pid,))
                        for size, vtype, design, qty_range, price, vimg in cursor.fetchall():
                            if not _in_quantity_range(qty_range, quantity):
                                continue
                            if not (budget_min <= price <= budget_max):
                                continue
                            variant_name = name
                            if size:   variant_name += f" - {size}"
                            if vtype:  variant_name += f" ({vtype})"
                            if design: variant_name += f" - {design}"
                            matching_products.append({
                                "name":            variant_name,
                                "price":           price,
                                "category":        category,
                                "min_order":       min_order,
                                "image_url":       vimg or image_url,
                                "relevance_score": round((1 - distance) * 100, 2),
                                "search_type":     "semantic"
                            })
                    else:
                        cursor.execute("""
                            SELECT quantity_range, price_per_piece
                            FROM pricing_tiers
                            WHERE product_id = %s
                            ORDER BY price_per_piece
                        """, (pid,))
                        for qty_range, price in cursor.fetchall():
                            if not _in_quantity_range(qty_range, quantity):
                                continue
                            if not (budget_min <= price <= budget_max):
                                continue
                            matching_products.append({
                                "name":            name,
                                "price":           price,
                                "category":        category,
                                "min_order":       min_order,
                                "image_url":       image_url,
                                "relevance_score": round((1 - distance) * 100, 2),
                                "search_type":     "semantic"
                            })
                            break

                matching_products.sort(key=lambda x: x["relevance_score"], reverse=True)
                final = matching_products[:limit]
                print(f"    ✅ RAG returned {len(final)} products")
                return final

    except Exception as e:
        print(f"    ❌ RAG search failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def _in_quantity_range(qty_range: str, quantity: int) -> bool:
    try:
        if '+' in qty_range:
            return quantity >= int(qty_range.split('+')[0].strip())
        elif '-' in qty_range:
            parts = qty_range.split('-')
            return int(parts[0].strip()) <= quantity <= int(parts[1].split()[0].strip())
    except:
        return False
    return False