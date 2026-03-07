"""
V2 Graph — Single conversational agent
"""

import os
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from models.bot_models import BotState
from bot.nodes import sales_agent_node, should_continue


def build_production_graph():
    workflow = StateGraph(BotState)

    workflow.add_node("sales_agent", sales_agent_node)
    workflow.set_entry_point("sales_agent")
    workflow.add_conditional_edges(
        "sales_agent",
        should_continue,
        {"continue": "sales_agent", "end": END}
    )

    db_url = os.getenv("SUPABASE_DB_URL")
    if "sslmode" not in db_url:
        db_url += "?sslmode=require"

    pool = ConnectionPool(
        conninfo=db_url,
        min_size=1,
        max_size=3,
        timeout=30,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None  # ← disables prepared statements, fixes the error
        }
    )

    with pool.connection() as conn:
        PostgresSaver(conn).setup()

    checkpointer = PostgresSaver(pool)
    return workflow.compile(checkpointer=checkpointer)