"""
V2 ProductionVihaBot — Conversational sales assistant
Wraps LangGraph and returns structured response to api/chat.py
"""

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from bot.graph import build_production_graph
import json


class ProductionVihaBot:

    def __init__(self):
        self.graph = build_production_graph()
        print("✅ V2 ProductionVihaBot ready — Conversational Sales Agent")

    def chat(self, user_id: str, message: str) -> dict:
        config = {
            "configurable": {"thread_id": user_id},
            "metadata": {"customer_number": user_id},
            "tags": [f"customer:{user_id}"]
        }

        print(f"\n{'='*70}")
        print(f"💬 user={user_id}  msg={message[:80]}")
        print(f"{'='*70}")

        try:
            result = self.graph.invoke(
                {
                    "messages":              [HumanMessage(content=message)],
                    "user_id":               user_id,
                    "needs_human_handoff":   False,
                    "handoff_reason":        None,
                    "products_to_send":      None,
                    "requirements_summary":  None,
                    "customer_requirements": None
                },
                config
            )

            # Debug — print all messages
            all_messages = result.get("messages", [])
            print(f"  📥 Total messages in state: {len(all_messages)}")
            for m in all_messages:
                mtype = type(m).__name__
                content = str(getattr(m, 'content', ''))[:80]
                print(f"     [{mtype}] {content}")

            # Get latest AI message that has real text content
            latest_reply = None
            for m in reversed(all_messages):
                if isinstance(m, AIMessage) and m.content and str(m.content).strip():
                    # Skip if it only has tool_calls and empty content
                    if str(m.content).strip():
                        latest_reply = str(m.content).strip()
                        break

            print(f"  💬 Latest reply: {str(latest_reply)[:100] if latest_reply else 'NONE'}")

            needs_handoff  = result.get("needs_human_handoff", False)
            products       = result.get("products_to_send")
            handoff_reason = result.get("handoff_reason", "")

            # Clean reply
            if latest_reply:
                latest_reply = latest_reply.replace("[SEND_PRODUCT_IMAGES]", "").strip()

            # Products found — send images
            if products is not None and len(products) > 0:
                print(f"  📸 Sending {len(products)} product images")
                return {
                    "reply":                 "[SEND_PRODUCT_IMAGES_WITH_SUMMARY]",
                    "needs_handoff":         True,
                    "products":              products,
                    "requirements_summary":  latest_reply,
                    "customer_requirements": self._extract_requirements(result),
                    "handoff_reason":        "products_shown",
                    "locked":                False
                }

            # Handoff triggered
            if needs_handoff:
                print(f"  🚨 Handoff: {handoff_reason}")
                return {
                    "reply":                 latest_reply,
                    "needs_handoff":         True,
                    "products":              None,
                    "customer_requirements": self._extract_requirements(result),
                    "handoff_reason":        handoff_reason,
                    "locked":                False
                }

            # Normal reply
            return {
                "reply":         latest_reply,
                "needs_handoff": False,
                "products":      None,
                "locked":        False
            }

        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {
                "reply":         None,
                "needs_handoff": True,
                "products":      None,
                "locked":        False
            }

    def _extract_requirements(self, result: dict) -> dict | None:
        return result.get("customer_requirements")