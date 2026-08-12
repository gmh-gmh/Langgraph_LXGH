"""编排层 — 各 Specialist 节点"""
import re
import asyncio
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate

from backend.model.factory import chat_model
from backend.services.geocoding import geocode as geo, plan_route
from backend.rag.harness import get_harness
from backend.services.profile import (
    personalize_routes, extract_and_update_preferences, add_search_history, get_profile,
)
from backend.tools.train_tools import query_tickets
from backend.tools.tools import search_poi_around
from backend.utils.logger_handler import logger

# ============================================================
# Rewrite Specialist
# ============================================================

REWRITE_PROMPT = """你是一个智能出行助手的查询改写器。将用户问题改写得更清晰、更适合系统检索。

改写规则：
1. 补全地名上下文（如"天安门" → "北京天安门"）
2. 保持原意不变，不要添加新信息
3. 如果原问题已经很清晰，直接返回原问题
4. 移除语气词和冗余表达

用户原始问题：{query}
图片描述：{image_desc}

只输出改写后的文本，不要解释。"""


async def rewrite_node(state: dict) -> dict:
    query = state.get("user_query", "")
    if not query:
        return {"rewritten_query": ""}
    prompt = ChatPromptTemplate.from_messages([("system", REWRITE_PROMPT)])
    try:
        resp = await chat_model.ainvoke(prompt.format(query=query, image_desc=state.get("image_description", "") or "无"))
        rewritten = resp.content.strip()
        logger.info(f"[Rewrite] \"{query}\" → \"{rewritten}\"")
        return {"rewritten_query": rewritten}
    except Exception as e:
        logger.error(f"[Rewrite] 失败: {e}")
        return {"rewritten_query": query}


# ============================================================
# Route Specialist
# ============================================================

async def route_specialist_node(state: dict) -> dict:
    outputs = dict(state.get("specialist_outputs", {}))
    if "route" in outputs:
        return {"supervisor_decision": ""}

    query = state.get("user_query", "")
    messages = state.get("messages", [])
    user_id = state.get("user_id", "default")
    origin, destination, travel_mode = _extract_route_params(query, state.get("user_profile", {}), messages)

    if not origin or not destination:
        outputs["route"] = {"success": False, "message": "无法提取起点和终点", "routes": []}
        return {"specialist_outputs": outputs, "supervisor_decision": ""}

    try:
        origin_coord = await geo(origin)
        dest_coord = await geo(destination)
        logger.info(f"[Route] {origin} → {destination}")

        if travel_mode:
            modes = [travel_mode]
        else:
            profile = get_profile(user_id)
            modes = profile.get("preferred_modes", [])[:3] or ["car", "bus", "ride", "walk"]

        all_routes = []
        for mode in modes:
            result = await plan_route(origin_coord, dest_coord, mode, origin, destination)
            if result.get("status") == 1 and result.get("routes"):
                all_routes.extend(result["routes"])
                break

        min_dist_km = min(r.get("distance", 0) for r in all_routes) / 1000 if all_routes else None
        harness = get_harness()
        knowledge_items = harness.retrieve(query, distance_km=min_dist_km)

        if all_routes:
            all_routes = personalize_routes(all_routes, user_id)

        outputs["route"] = {
            "success": len(all_routes) > 0,
            "message": f"找到 {len(all_routes)} 条路线" + ("，并检索到相关知识" if knowledge_items else ""),
            "routes": all_routes,
            "knowledge_items": knowledge_items,
            "knowledge": harness.format_compact(knowledge_items),
            "min_distance_km": min_dist_km,
            "origin": origin, "destination": destination,
        }
        extract_and_update_preferences(user_id, query)
        add_search_history(user_id, query, "route_plan")
    except Exception as e:
        logger.error(f"[Route] 失败: {e}")
        outputs["route"] = {"success": False, "message": f"路线规划出错: {str(e)}", "routes": []}

    return {"specialist_outputs": outputs, "supervisor_decision": ""}


def _extract_route_params(query: str, profile: dict, messages: list = None) -> tuple:
    patterns = [
        r"从(.+?)到(.+?)(?:怎么走|路线|开车|打车|坐车|导航|怎么去|有几种方式|$)",
        r"从(.+?)到(.+?)[，,]\s*(开车|打车|坐车|坐地铁|坐公交|骑车|步行|自驾)?",
        r"从(.+?)到(.+?)$",
    ]
    mode_map = {"开车": "car", "自驾": "car", "打车": "car", "地铁": "bus", "公交": "bus",
                "骑车": "ride", "骑行": "ride", "步行": "walk", "走路": "walk"}
    for p in patterns:
        m = re.search(p, query)
        if m:
            origin, dest = m.group(1).strip(), m.group(2).strip()
            mode_str = m.group(3).strip() if len(m.groups()) >= 3 else ""
            mapped = mode_map.get(mode_str, "")
            if not mapped and profile.get("preferred_modes"):
                mapped = profile["preferred_modes"][0]
            return origin, dest, mapped
    # 当前查询没提取到，查对话历史（只看用户消息）
    if messages:
        for msg in reversed(messages):
            if getattr(msg, "type", "") != "human":
                continue
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            for p in patterns:
                m = re.search(p, content)
                if m:
                    origin, dest = m.group(1).strip(), m.group(2).strip()
                    mode_str = m.group(3).strip() if len(m.groups()) >= 3 else ""
                    mapped = mode_map.get(mode_str, "")
                    return origin, dest, mapped
    return "", "", ""


# ============================================================
# POI Specialist
# ============================================================

async def poi_specialist_node(state: dict) -> dict:
    outputs = dict(state.get("specialist_outputs", {}))
    if "poi" in outputs:
        return {"supervisor_decision": ""}

    query = state.get("user_query", "")
    user_id = state.get("user_id", "default")
    location, keywords = _extract_poi_params(query)

    if not keywords:
        outputs["poi"] = {"success": False, "message": "无法识别要搜索的地点类型", "pois": []}
        return {"specialist_outputs": outputs, "supervisor_decision": ""}

    try:
        coord = await geo(location) if location and location != "这里" else None
        pois = []
        if coord:
            raw = await search_poi_around.ainvoke({"location": coord, "keywords": keywords, "radius": 2000})
            pois = raw if isinstance(raw, list) else []

        outputs["poi"] = {
            "success": len(pois) > 0,
            "message": f"在 {location or '附近'} 找到 {len(pois)} 个 {keywords}" if pois else f"附近未找到 {keywords}",
            "pois": pois,
        }
        add_search_history(user_id, query, "poi_search")
    except Exception as e:
        logger.error(f"[POI] 失败: {e}")
        outputs["poi"] = {"success": False, "message": f"POI 搜索出错: {str(e)}", "pois": []}

    return {"specialist_outputs": outputs, "supervisor_decision": ""}


def _extract_poi_params(query: str) -> tuple:
    m = re.search(r"(.+?)附近有(什么|哪些|啥|哪些好)(.+?)(?:$|吗|的|？|\?)", query)
    if m: return m.group(1).strip(), m.group(3).strip()
    m = re.search(r"(.+?)附近(?:的|有)(.+?)(?:$|吗|的|？|\?)", query)
    if m: return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"推荐(.+?)(?:$|的|吗|？|\?)", query)
    if m: return "这里", m.group(1).strip()
    return "这里", query[:10]


# ============================================================
# Train Specialist
# ============================================================

async def train_specialist_node(state: dict) -> dict:
    outputs = dict(state.get("specialist_outputs", {}))
    if "train" in outputs:
        return {"supervisor_decision": ""}

    query = state.get("user_query", "")
    messages = state.get("messages", [])
    user_id = state.get("user_id", "default")
    origin, destination = _extract_train_params(query, messages)

    if not origin or not destination:
        outputs["train"] = {"success": False, "message": "无法提取出发站和到达站", "tickets": ""}
        return {"specialist_outputs": outputs, "supervisor_decision": ""}

    try:
        # 解析用户说的日期（明天/后天/默认今天）
        dates = _parse_train_dates(query, messages)
        all_tickets = []

        for date in dates:
            tickets_str = await query_tickets(origin, destination, date)
            if tickets_str:
                # query_tickets 已返回带 header 的完整文本
                all_tickets.append(tickets_str)
                break
            else:
                # 没查到，记录一下但继续试下一天
                logger.info(f"[Train] {origin}→{destination} {date} 无票，试下一天")

        if all_tickets:
            outputs["train"] = {
                "success": True,
                "message": f"查询到 {origin}→{destination} 的车次",
                "tickets": "\n\n".join(all_tickets),
                "origin": origin, "destination": destination, "date": dates[0],
            }
        else:
            date_str = "、".join(dates)
            outputs["train"] = {
                "success": False,
                "message": f"未查到 {origin}→{destination} ({date_str}) 的车次",
                "tickets": "",
                "origin": origin, "destination": destination, "date": dates[0],
            }
        add_search_history(user_id, query, "train_query")
    except Exception as e:
        logger.error(f"[Train] 失败: {e}")
        outputs["train"] = {"success": False, "message": f"查询出错: {str(e)}", "tickets": ""}

    return {"specialist_outputs": outputs, "supervisor_decision": ""}


def _parse_train_dates(query: str, messages: list = None) -> list[str]:
    """解析用户查询中的日期，返回要尝试的日期列表（优先到后）"""
    from datetime import datetime, timedelta
    now = datetime.now()

    def fmt(d):
        return d.strftime("%Y-%m-%d")

    # 判断当前查询是否提到日期
    current_has_date = any(kw in query for kw in ["明天", "明日", "后天", "今天", "昨日", "昨天"])

    if "后天" in query:
        base = now + timedelta(days=2)
        return [fmt(base), fmt(base + timedelta(days=1))]
    elif "明天" in query or "明日" in query:
        base = now + timedelta(days=1)
        return [fmt(base), fmt(base + timedelta(days=1))]
    elif "昨天" in query or "昨日" in query:
        base = now - timedelta(days=1)
        return [fmt(base)]

    # 当前 query 没有日期词 → 查历史中有没有
    if messages and not current_has_date:
        for msg in reversed(messages):
            if getattr(msg, "type", "") != "human":
                continue
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            if "后天" in content:
                base = now + timedelta(days=2)
                return [fmt(base), fmt(base + timedelta(days=1))]
            elif "明天" in content or "明日" in content:
                base = now + timedelta(days=1)
                return [fmt(base), fmt(base + timedelta(days=1))]

    # 默认今天，没票自动试明天
    return [fmt(now), fmt(now + timedelta(days=1))]


def _extract_train_params(query: str, messages: list = None) -> tuple:
    patterns = [
        r"从(.+?)到(.+?)(?:有哪些|有什么|的火车|的高铁|的车次|有火车|有高铁|火车票|高铁票)?",
        r"(.+?)到(.+?)(?:有哪些|有什么|的火车|的高铁|的车次|火车|高铁)",
    ]
    for p in patterns:
        m = re.search(p, query)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    # 当前查询没提取到，查对话历史（只看用户消息）
    if messages:
        for msg in reversed(messages):
            if getattr(msg, "type", "") != "human":
                continue
            content = getattr(msg, "content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            for p in patterns:
                m = re.search(p, content)
                if m:
                    return m.group(1).strip(), m.group(2).strip()
    return "", ""


# ============================================================
# Chat Specialist
# ============================================================

def _format_history(messages: list) -> str:
    """将消息列表格式化为对话历史文本"""
    lines = []
    for msg in messages[-6:]:  # 最近6轮
        role = "用户" if getattr(msg, "type", "") == "human" else "助手"
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        if content:
            lines.append(f"{role}: {content[:200]}")
    return "\n".join(lines)


async def chat_specialist_node(state: dict) -> dict:
    outputs = dict(state.get("specialist_outputs", {}))
    if "chat" in outputs:
        return {"supervisor_decision": ""}

    query = state.get("user_query", "")
    history = _format_history(state.get("messages", []))
    system_msg = "你是一个友好的出行规划助手。如果用户问路线相关问题，引导他们使用路线规划功能。"
    if history:
        system_msg += f"\n\n以下是对话历史：\n{history}"

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("human", query),
    ])
    try:
        resp = await chat_model.ainvoke(prompt.format())
        outputs["chat"] = {"success": True, "message": resp.content.strip()}
    except Exception as e:
        logger.error(f"[Chat] 失败: {e}")
        outputs["chat"] = {"success": False, "message": "抱歉，我暂时无法回复"}

    return {"specialist_outputs": outputs, "supervisor_decision": ""}


# ============================================================
# Image Understanding
# ============================================================

async def understand_image_node(state: dict) -> dict:
    if not state.get("image_base64"):
        return {"image_description": ""}
    try:
        from backend.model.factory import visual_model
        desc = await visual_model.acall(state["image_base64"])
        return {"image_description": desc or ""}
    except Exception as e:
        logger.error(f"[Image] 失败: {e}")
        return {"image_description": ""}
