"""Agent 图构建器 — Multi-Agent 图（SQLite 持久化）"""
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver 

from backend.agent.supervisor import supervisor_node, routing_decision
from backend.agent.specialists import (
    understand_image_node, rewrite_node,
    route_specialist_node, poi_specialist_node,
    train_specialist_node, chat_specialist_node,
)
from backend.agent.quality import quality_evaluator_node
from backend.agent.respond import respond_node
from backend.agent.state import MultiAgentState


async def _create_checkpointer(db_path: str = "data/multi_agent_checkpoints.db"):
    import aiosqlite
    conn = await aiosqlite.connect(db_path)
    return AsyncSqliteSaver(conn)


async def build_multi_agent_graph(db_path: str = "data/multi_agent_checkpoints.db"):
    """构建 Multi-Agent 图"""
    builder = StateGraph(MultiAgentState)

    builder.add_node("understand_image", understand_image_node)
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("route_specialist", route_specialist_node)
    builder.add_node("poi_specialist", poi_specialist_node)
    builder.add_node("train_specialist", train_specialist_node)
    builder.add_node("chat_specialist", chat_specialist_node)
    builder.add_node("quality_evaluator", quality_evaluator_node)
    builder.add_node("respond", respond_node)

    # 流程：图片 → 改写 → supervisor → [specialist] → supervisor
    #                                          ↓ (完成时)
    #                                    quality_evaluator → respond
    builder.add_edge(START, "understand_image")
    builder.add_edge("understand_image", "rewrite")
    builder.add_edge("rewrite", "supervisor")

    builder.add_conditional_edges(
        "supervisor", routing_decision,
        {
            "route_specialist": "route_specialist",
            "poi_specialist": "poi_specialist",
            "train_specialist": "train_specialist",
            "chat_specialist": "chat_specialist",
            "quality_evaluator": "quality_evaluator",
        }
    )

    builder.add_edge("route_specialist", "supervisor")
    builder.add_edge("poi_specialist", "supervisor")
    builder.add_edge("train_specialist", "supervisor")
    builder.add_edge("chat_specialist", "supervisor")
    builder.add_edge("quality_evaluator", "respond")
    builder.add_edge("respond", END)

    checkpointer = await _create_checkpointer(db_path)
    return builder.compile(checkpointer=checkpointer)


__all__ = ["build_multi_agent_graph"]
