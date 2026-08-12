"""编排层 — Supervisor 调度节点"""
import json
from typing import Literal
from langchain_core.prompts import ChatPromptTemplate
from backend.model.factory import chat_model
from backend.utils.logger_handler import logger

SUPERVISOR_PROMPT = """你是一个智能出行规划系统的调度主管（Supervisor）。

你的职责是分析用户的问题和当前对话状态，决定下一步调用哪个专家。

可选专家（每次只能选一个）：
1. route_specialist：路线规划（从A到B的导航、路线查询、出行方式选择）
2. poi_specialist：地点搜索（附近有什么、推荐餐厅/景点/加油站等）
3. train_specialist：火车票查询（查车次、票价、中转方案）
4. chat_specialist：闲聊对话（问候、感谢、不需要查任何API的简单问题）
5. respond：信息已收集完毕，生成最终回答回复用户

当前已完成的专家输出（为空表示还没开始）：
{outputs}

用户画像偏好：
{profile}

重要规则：
- 如果某个专家已经在"已完成的专家输出"中出现过了，就不要再调用它
- 如果所有必要的专家都已经调用过，或者当前信息足够回答用户，就调 respond

请只输出以下 JSON 格式（不要其他任何内容）：
{{"next": "专家名"}}"""


def _format_history(messages: list) -> str:
    """将消息列表格式化为对话历史文本"""
    lines = []
    for msg in messages[-6:]:
        role = "用户" if getattr(msg, "type", "") == "human" else "助手"
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        if content:
            lines.append(f"{role}: {content[:200]}")
    return "\n".join(lines)


async def supervisor_node(state: dict) -> dict:
    """用 LLM 决策下一步调用哪个专家"""
    if state.get("current_step", 0) >= state.get("max_steps", 5):
        logger.info("[Supervisor] 达到最大步数限制，强制结束")
        return {"supervisor_decision": "respond", "current_step": state["current_step"] + 1}

    outputs = state.get("specialist_outputs", {})
    if outputs:
        logger.info(f"[Supervisor] 已有专家输出: {list(outputs.keys())}, 进入 respond")
        return {"supervisor_decision": "respond", "current_step": state["current_step"] + 1}

    summary = _summarize_outputs(outputs)
    profile = _summarize_profile(state.get("user_profile", {}))
    history = _format_history(state.get("messages", []))

    prompt = ChatPromptTemplate.from_messages([
        ("system", SUPERVISOR_PROMPT),
        ("human", "用户问题：{query}\n\n对话历史：{history}\n\n已完成的专家输出：{outputs}\n\n用户画像：{profile}"),
    ])
    try:
        resp = await chat_model.ainvoke(prompt.format(
            query=state.get("user_query", ""),
            history=history or "（无历史记录）",
            outputs=summary, profile=profile,
        ))
        decision = _parse_decision(resp.content.strip())
        logger.info(f"[Supervisor] 决策: {decision}")
    except Exception as e:
        logger.error(f"[Supervisor] LLM 决策失败: {e}")
        decision = "respond"

    return {"supervisor_decision": decision, "current_step": state.get("current_step", 0) + 1}


def routing_decision(state: dict) -> Literal[
    "route_specialist", "poi_specialist", "train_specialist",
    "chat_specialist", "quality_evaluator"
]:
    decision = state.get("supervisor_decision", "respond")
    if decision == "respond":
        return "quality_evaluator"
    return decision


def _summarize_outputs(outputs: dict) -> str:
    if not outputs:
        return "（暂无，尚未调用任何专家）"
    return "\n".join(f"- {k}: {v.get('message', '已执行')[:100]}" for k, v in outputs.items() if isinstance(v, dict))


def _summarize_profile(profile: dict) -> str:
    if not profile or not profile.get("preferred_modes"):
        return "（无偏好设置）"
    return f"偏好出行方式：{', '.join(profile.get('preferred_modes', []))} | 电动车：{'是' if profile.get('ev_car') else '否'}"


def _parse_decision(text: str) -> str:
    try:
        start, end = text.index("{"), text.rindex("}")
        return json.loads(text[start:end + 1]).get("next", "respond")
    except (ValueError, json.JSONDecodeError):
        pass
    for kw in ["route_specialist", "poi_specialist", "train_specialist", "chat_specialist", "respond"]:
        if kw in text.lower():
            return kw
    return "respond"
