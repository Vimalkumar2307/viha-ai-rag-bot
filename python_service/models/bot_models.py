"""
V2 Models — Simplified state for conversational agent
"""

import operator
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from pydantic import BaseModel, Field


class BotState(TypedDict):
    """
    Simplified state — just messages and handoff flag
    No more rigid fields like requirements, validation, etc.
    LLM manages context naturally through conversation history
    """
    messages: Annotated[Sequence, operator.add]
    user_id: str
    needs_human_handoff: bool
    handoff_reason: str | None
    products_to_send: list | None
    requirements_summary: str | None
    customer_requirements: dict | None