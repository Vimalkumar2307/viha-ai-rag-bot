"""
V2 Nodes — Single sales agent node
LLM with tools — decides everything
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from bot.tools import TOOLS, trigger_human_handoff
from bot.config import llm
import os
import json


# Bind tools to LLM
llm_with_tools = llm.bind_tools(TOOLS)

SYSTEM_PROMPT = """You are a friendly sales assistant for Viha Return Gifts, Chennai.

PERSONALITY:
- Warm, polite, very short replies
- Never pushy or forceful
- Like a helpful human sales person
- Use simple English

PRODUCTS WE SELL:
You have tools to check our exact product catalog, prices, and availability.
Always use tools to get accurate information — never guess prices.

BEHAVIOR RULES:

1. GREETING — First message:
   "Hello! Welcome to Viha Return Gifts 😊 How can I help you today?"

2. PRODUCT QUESTIONS — Use get_product_info tool:
   Customer asks price/size/details → fetch from DB → answer accurately

3. AVAILABILITY — Use get_all_products_summary tool:
   Customer asks if we sell something → check DB → answer honestly
   If we don't sell it: "We don't carry [X] currently. We have [suggest alternatives]"

4. MINIMUM ORDER — Use check_minimum_order tool:
   Customer gives quantity below minimum → "Our minimum order is X pieces. Would that work?"

5. GENERAL INQUIRY ("I want return gifts"):
   Ask these 4 questions naturally (not as a list):
   - Quantity needed
   - Budget per piece  
   - Delivery location
   - When needed
   Then use search_products_by_requirements tool

6. PRODUCT RECOMMENDATION:
   When recommending products → describe them briefly in text.
   Images are sent automatically — you don't need to add any marker.

7. HANDOFF — Use trigger_human_handoff tool when:
   - Customer sends image
   - Asks about delivery/shipping
   - Wants to place order
   - Asks for customization
   - Says yes/confirmed/let's proceed
   - Message contains [IMAGE_SENT]
   After tool call reply: "Let me connect you with our team 😊"

8. UNKNOWN QUERIES:
   Answer if you can. If not → use trigger_human_handoff

9. CAPTURE REQUIREMENTS — Use save_customer_requirements tool:
   Whenever customer mentions ANY of these — call this tool immediately:
   - Quantity ("100 pieces", "50 gifts")
   - Budget ("under 50 rupees", "Rs 100 each")
   - Location ("Chennai", "Bangalore")
   - Timeline ("next week", "March 15")
   - Occasion ("wedding", "birthday", "corporate")
   - Product interest ("eco friendly", "traditional")
   Don't wait for all fields. Save partial info too.

IMPORTANT:
- Keep replies SHORT — max 5-6 lines
- Never show prices without checking tools first
- Always be honest about what we have/don't have"""


def sales_agent_node(state: dict) -> dict:
    """
    Single agent node — handles entire conversation.
    LLM decides which tool to call based on message.
    """
    messages = state.get("messages", [])
    user_id  = state.get("user_id", "")

    print(f"  🤖 SALES AGENT NODE")

    # Build message list with system prompt
    full_messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    # Call LLM with tools
    response = llm_with_tools.invoke(full_messages)
    print(f"  📤 LLM response type: {type(response)}")

    new_state = {
        "messages":            [response],
        "needs_human_handoff": False,
        "handoff_reason":      None,
        "products_to_send":    None,
        "requirements_summary": None,
        "customer_requirements": None
    }

    # Check if LLM wants to call tools
    if response.tool_calls:
        tool_results = []

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            print(f"  🔧 Tool call: {tool_name}({tool_args})")

            # Execute tool
            result = _execute_tool(tool_name, tool_args)
            print(f"  ✅ Tool result: {str(result)[:100]}")

            tool_results.append(ToolMessage(
                content=json.dumps(result),
                tool_call_id=tool_call["id"]
            ))

            # Handle handoff tool
            if tool_name == "trigger_human_handoff":
                new_state["needs_human_handoff"] = True
                new_state["handoff_reason"]      = tool_args.get("reason", "")

            # Handle requirements capture tool
            if tool_name == "save_customer_requirements":
                new_state["customer_requirements"] = result.get("requirements", {})

        # Add tool results to messages
        new_state["messages"] = [response] + tool_results

        # Call LLM again with tool results to get final response
        final_messages = full_messages + [response] + tool_results
        final_response = llm_with_tools.invoke(final_messages)
        new_state["messages"] = [response] + tool_results + [final_response]

        # Auto detect products from tool results — don't rely on LLM marker
        for tr in tool_results:
            try:
                data = json.loads(tr.content)
                if isinstance(data, list) and len(data) > 0 and "image_url" in data[0]:
                    new_state["products_to_send"] = data
                    print(f"  📸 Auto detected {len(data)} products to send")
                    break
            except:
                pass

    else:
        # No tool calls — check for image marker in direct response
        if "[SEND_PRODUCT_IMAGES]" in (response.content or ""):
            new_state["products_to_send"] = []

    return new_state


def should_continue(state: dict) -> str:
    """
    After agent runs — always end.
    No looping needed for sales conversation.
    """
    return "end"


def _execute_tool(tool_name: str, tool_args: dict):
    """Execute tool by name and return result."""
    from bot.tools import (
        get_product_info,
        search_products_by_requirements,
        get_all_products_summary,
        check_minimum_order,
        trigger_human_handoff,
        save_customer_requirements
    )

    tool_map = {
        "get_product_info":                get_product_info,
        "search_products_by_requirements": search_products_by_requirements,
        "get_all_products_summary":        get_all_products_summary,
        "check_minimum_order":             check_minimum_order,
        "trigger_human_handoff":           trigger_human_handoff,
        "save_customer_requirements":      save_customer_requirements
    }

    tool_fn = tool_map.get(tool_name)
    if tool_fn:
        return tool_fn.invoke(tool_args)
    return {"error": f"Unknown tool: {tool_name}"}