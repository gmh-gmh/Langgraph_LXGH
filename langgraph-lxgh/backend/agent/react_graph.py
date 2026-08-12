from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from backend.agent.react_nodes import understand_image, react_think, react_act, react_summarize, should_continue
from backend.agent.react_state import ReActState, get_initial_react_state
import sqlite3

def build_react_agent(checkpointer_type: str = "memory", db_path: str = "checkpoints.db"):
    """构建ReAct型Agent"""
    builder = StateGraph(ReActState)

    # 添加节点
    builder.add_node("understand_image", understand_image)
    builder.add_node("think", react_think)
    builder.add_node("act", react_act)
    builder.add_node("summarize", react_summarize)

    # 添加边
    builder.add_edge(START, "understand_image")
    builder.add_edge("understand_image", "think")
    builder.add_edge("act", "think")
    
    # 条件边：根据should_continue决定是继续思考还是总结
    builder.add_conditional_edges(
        "think",
        should_continue,
        {
            "think": "act",      # 继续思考 -> 执行行动
            "summarize": "summarize"  # 结束 -> 总结
        }
    )
    
    builder.add_edge("summarize", END)

    # 设置检查点
    if checkpointer_type == "sqlite":
        conn = sqlite3.connect(db_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    else:
        checkpointer = MemorySaver()

    agent = builder.compile(checkpointer=checkpointer)

    return agent

# 导出初始状态函数
__all__ = ["build_react_agent", "get_initial_react_state"]
