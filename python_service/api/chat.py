"""
Chat endpoint
POST /chat — main bot interaction endpoint
"""

from fastapi import APIRouter
from models.schemas import ChatRequest
from services.lock_service import (
    locked_conversations_cache,
    is_conversation_locked
)
from services.lead_service import save_or_update_lead

router = APIRouter()

_bot = None


def set_bot(bot_instance):
    global _bot
    _bot = bot_instance


@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        # ── Check if locked ──────────────────────────────────────────
        lock_info = locked_conversations_cache.get(request.user_id)
        if not lock_info:
            lock_info = is_conversation_locked(request.user_id)
            if lock_info:
                locked_conversations_cache[request.user_id] = lock_info

        if lock_info:
            print(f"\n{'='*70}")
            print(f"🔒 LOCKED - BOT SILENT for {request.user_id}")
            print(f"{'='*70}\n")
            return {
                "status":        "locked",
                "reply":         None,
                "needs_handoff": False,
                "products":      None,
                "locked":        True,
                "locked_at":     lock_info["locked_at"],
                "locked_by":     lock_info["locked_by"]
            }

        # ── Normal chat flow ─────────────────────────────────────────
        print(f"\n{'='*70}")
        print(f"💬 API Request from: {request.user_id}")
        print(f"📩 Message: {request.message}")
        print(f"{'='*70}")

        response = _bot.chat(request.user_id, request.message)

       # ── Save lead on handoff, products shown, or requirements captured ──
        is_products_shown     = response.get("reply") == "[SEND_PRODUCT_IMAGES_WITH_SUMMARY]"
        is_handoff            = response.get("needs_handoff", False)
        captured_requirements = response.get("customer_requirements")

        if is_products_shown or is_handoff or captured_requirements:
            lead_status = "products_shown" if is_products_shown else \
                          "follow_up"       if is_handoff        else \
                          "requirements_collecting"

            # Use captured structured requirements if available
            # Otherwise save minimal info
            requirements_to_save = captured_requirements or {
                "last_message":         request.message,
                "handoff_reason":       response.get("handoff_reason", ""),
                "requirements_summary": response.get("requirements_summary", "")
            }

            response["customer_requirements"] = requirements_to_save
            response["last_message"]          = request.message

            try:
                save_or_update_lead(
                    request.user_id,
                    response,
                    lead_status,
                    request.push_name
                )
                print(f"✅ Lead saved — status: {lead_status} | requirements: {requirements_to_save}")
            except Exception as lead_error:
                print(f"⚠️ Lead save failed (non-critical): {lead_error}")

        return {
            "status":                "success",
            "reply":                 response["reply"],
            "needs_handoff":         response["needs_handoff"],
            "products":              response.get("products"),
            "requirements_summary":  response.get("requirements_summary"),
            "customer_requirements": response.get("customer_requirements"),
            "handoff_reason":        response.get("handoff_reason"),
            "locked":                False,
            "customer_number":       request.user_id,
            "last_message":          request.message
        }

    except Exception as e:
        print(f"❌ ERROR in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status":          "error",
            "reply":           None,
            "needs_handoff":   True,
            "products":        None,
            "locked":          False,
            "customer_number": request.user_id,
            "last_message":    request.message
        }