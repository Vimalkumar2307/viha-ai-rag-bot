"""
V2 Tools — LLM calls these freely based on customer message
6 tools replacing 3 rigid V1 tools
"""

import os
import psycopg
from langchain.tools import tool
from services.rag_service import search_products_by_semantic


@tool
def get_product_info(product_name: str) -> dict:
    """
    Get full details of a specific product including all sizes and prices.
    Use when customer asks about a specific product by name.
    """
    conn = psycopg.connect(os.getenv("SUPABASE_DB_URL"))
    cursor = conn.cursor()

    try:
        # Search by name (fuzzy)
        cursor.execute("""
            SELECT id, name, category, description, 
                   min_order, has_variants, image_url
            FROM products
            WHERE LOWER(name) LIKE LOWER(%s)
            LIMIT 3
        """, (f"%{product_name}%",))
        products = cursor.fetchall()

        if not products:
            return {"found": False, "message": f"No product found matching '{product_name}'"}

        results = []
        for pid, name, category, desc, min_order, has_variants, img in products:
            product_info = {
                "name": name,
                "category": category,
                "description": desc,
                "min_order": min_order,
                "image_url": img,
                "pricing": []
            }

            if has_variants:
                cursor.execute("""
                    SELECT size, type, design_name,
                           quantity_range, price_per_piece, is_available
                    FROM product_variants
                    WHERE product_id = %s
                    ORDER BY price_per_piece
                """, (pid,))
                variants = cursor.fetchall()
                for size, vtype, design, qty_range, price, available in variants:
                    variant_label = name
                    if size:   variant_label += f" {size}"
                    if vtype:  variant_label += f" ({vtype})"
                    if design: variant_label += f" - {design}"
                    product_info["pricing"].append({
                        "variant":       variant_label,
                        "quantity_range": qty_range,
                        "price":         price,
                        "available":     available
                    })
            else:
                cursor.execute("""
                    SELECT quantity_range, price_per_piece
                    FROM pricing_tiers
                    WHERE product_id = %s
                    ORDER BY price_per_piece
                """, (pid,))
                tiers = cursor.fetchall()
                for qty_range, price in tiers:
                    product_info["pricing"].append({
                        "quantity_range": qty_range,
                        "price": price
                    })

            results.append(product_info)

        return {"found": True, "products": results}

    finally:
        cursor.close()
        conn.close()


@tool
def search_products_by_requirements(
    budget_max: int,
    quantity: int,
    query: str = ""
) -> list:
    """
    Find products matching budget and quantity.
    Uses RAG if query provided, falls back to SQL.
    Use when customer gives requirements.
    """
    from services.rag_service import search_products_by_semantic

    # Try RAG first if query given
    if query:
        results = search_products_by_semantic(
            query=query,
            budget_min=0,
            budget_max=budget_max,
            quantity=quantity
        )
        if results:
            return results

    # SQL fallback
    conn = psycopg.connect(os.getenv("SUPABASE_DB_URL"))
    cursor = conn.cursor()

    try:
        matching = []

        # Products without variants
        cursor.execute("""
            SELECT p.id, p.name, p.category, p.image_url, p.min_order,
                   pt.quantity_range, pt.price_per_piece
            FROM products p
            JOIN pricing_tiers pt ON p.id = pt.product_id
            WHERE p.min_order <= %s
              AND pt.price_per_piece <= %s
              AND (p.has_variants = FALSE OR p.has_variants IS NULL)
            ORDER BY pt.price_per_piece
        """, (quantity, budget_max))

        for pid, name, cat, img, min_ord, qty_range, price in cursor.fetchall():
            if _in_range(qty_range, quantity):
                matching.append({
                    "name": name, "price": price,
                    "category": cat, "image_url": img,
                    "min_order": min_ord,
                    "relevance_score": 80,
                    "search_type": "sql"
                })

        # Products with variants
        cursor.execute("""
            SELECT p.id, p.name, p.category, p.min_order,
                   pv.size, pv.type, pv.design_name,
                   pv.quantity_range, pv.price_per_piece, pv.image_url
            FROM products p
            JOIN product_variants pv ON p.id = pv.product_id
            WHERE p.min_order <= %s
              AND pv.price_per_piece <= %s
              AND pv.is_available = TRUE
              AND p.has_variants = TRUE
        """, (quantity, budget_max))

        for pid, name, cat, min_ord, size, vtype, design, qty_range, price, img in cursor.fetchall():
            if _in_range(qty_range, quantity):
                variant_name = name
                if size:   variant_name += f" - {size}"
                if vtype:  variant_name += f" ({vtype})"
                if design: variant_name += f" - {design}"
                matching.append({
                    "name": variant_name, "price": price,
                    "category": cat, "image_url": img,
                    "min_order": min_ord,
                    "relevance_score": 80,
                    "search_type": "sql"
                })

        results = sorted(matching, key=lambda x: x["price"])[:10]
        if not results:
            return [{"message": "No products found matching budget and quantity requirements"}]
        return results

    finally:
        cursor.close()
        conn.close()


@tool
def get_all_products_summary() -> list:
    """
    Get summary of all products we sell.
    Use when customer asks what products we have,
    or to check if we sell a specific type of product.
    """
    conn = psycopg.connect(os.getenv("SUPABASE_DB_URL"))
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT name, category, description, min_order
            FROM products
            ORDER BY category, name
        """)
        rows = cursor.fetchall()

        return [
            {
                "name":        name,
                "category":    category,
                "description": desc,
                "min_order":   min_order
            }
            for name, category, desc, min_order in rows
        ]
    finally:
        cursor.close()
        conn.close()


@tool
def check_minimum_order(product_name: str) -> dict:
    """
    Check minimum order quantity for a product.
    Use when customer mentions a specific quantity.
    """
    conn = psycopg.connect(os.getenv("SUPABASE_DB_URL"))
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT name, min_order
            FROM products
            WHERE LOWER(name) LIKE LOWER(%s)
            LIMIT 1
        """, (f"%{product_name}%",))
        row = cursor.fetchone()

        if row:
            return {"found": True, "product": row[0], "min_order": row[1]}
        return {"found": False, "message": "Product not found"}

    finally:
        cursor.close()
        conn.close()


@tool
def trigger_human_handoff(reason: str, customer_message: str = "") -> dict:
    """
    Trigger handoff to wife/human agent.
    Use when: customer sends image, asks about delivery,
    wants to place order, asks for customization,
    or confirms they want to buy.
    """
    # This just signals handoff — actual alert sent by viha_bot.py
    return {
        "handoff": True,
        "reason": reason,
        "message": "Connecting you with our team 😊"
    }


@tool
def save_customer_requirements(
    quantity: int = None,
    budget_max: int = None,
    budget_min: int = None,
    location: str = None,
    timeline: str = None,
    occasion: str = None,
    product_interest: str = None
) -> dict:
    """
    Save customer requirements when you have collected them.
    Call this whenever customer mentions quantity, budget, 
    location, timeline or occasion — even partially.
    Don't wait for all fields — save whatever you have.
    """
    requirements = {}
    if quantity:         requirements["quantity"]         = quantity
    if budget_max: 
        requirements["budget_max"]       = budget_max
        requirements["budget_per_piece"] = budget_max 
    if budget_min:       requirements["budget_min"]       = budget_min
    if location:         requirements["location"]         = location
    if timeline:         requirements["timeline"]         = timeline
    if occasion:         requirements["occasion"]         = occasion
    if product_interest: requirements["product_interest"] = product_interest

    print(f"  💾 Requirements captured: {requirements}")
    return {"saved": True, "requirements": requirements}

# ── Helper ────────────────────────────────────────────────
def _in_range(qty_range: str, quantity: int) -> bool:
    try:
        if '+' in qty_range:
            return quantity >= int(qty_range.split('+')[0].strip())
        elif '-' in qty_range:
            parts = qty_range.split('-')
            return int(parts[0].strip()) <= quantity <= int(parts[1].split()[0].strip())
    except:
        return False
    return False


TOOLS = [
    get_product_info,
    search_products_by_requirements,
    get_all_products_summary,
    check_minimum_order,
    trigger_human_handoff,
    save_customer_requirements
]