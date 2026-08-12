from typing import Optional, List, Any, Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class MultiAgentState(TypedDict):
    """Multi-Agent 系统状态"""
    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    user_id: str
    user_profile: dict
    image_base64: Optional[str]
    image_description: Optional[str]
    supervisor_decision: str
    specialist_outputs: dict[str, Any]
    final_response: Optional[str]
    current_step: int
    max_steps: int


def get_initial_multi_agent_state(user_id: str = "default") -> dict:
    """获取Multi-Agent的初始状态"""
    return {
        "messages": [],
        "user_query": "",
        "user_id": user_id,
        "user_profile": {},
        "image_base64": None,
        "image_description": None,
        "supervisor_decision": "",
        "specialist_outputs": {},
        "final_response": None,
        "current_step": 0,
        "max_steps": 5,
    }

