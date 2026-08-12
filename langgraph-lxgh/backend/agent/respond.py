"""编排层 — 回复生成节点"""
import re
from collections import defaultdict
from langchain_core.messages import HumanMessage
from backend.model.factory import chat_model
from backend.utils.logger_handler import logger


def _emoji_for_file(source_file: str) -> str:
    if "限行" in source_file or "规则" in source_file: return "🚦"
    if "景区" in source_file or "游玩" in source_file: return "🏛️"
    if "出行方式" in source_file or "指南" in source_file: return "🚌"
    if "充电" in source_file or "电车" in source_file: return "⚡"
    if "省钱" in source_file or "费用" in source_file: return "💰"
    if "节假日" in source_file: return "📅"
    return "💡"

#把高德 API 返回的路线数据（米/秒）转换为人类可读格式（公里/小时分钟）。
def _format_route(route: dict, index: int, pref_modes: list) -> list[str]:
    dist_km = route.get("distance", 0) / 1000
    dur_min = route.get("duration", 0) / 60
    mode_label = route.get("mode_label", route.get("mode", "驾车"))
    hours, mins = int(dur_min // 60), int(dur_min % 60)
    dur_str = f"{hours}小时{mins}分钟" if hours >= 1 and mins > 5 else (f"{hours}小时" if hours >= 1 else f"{dur_min:.0f}分钟")

    lines = [f"### 方案 {index} · {mode_label}{' ⭐推荐' if index == 1 and pref_modes else ''}"]
    info = [f"🛣️ 距离 {dist_km:.0f} 公里", f"⏱️ 耗时 {dur_str}"]
    if route.get("tolls", 0) > 0:
        info.append(f"💰 过路费 {route['tolls']:.0f} 元")
    lines.append(" | ".join(info))
    if route.get("map_url"):
        lines.append(f"[📱 在高德地图中查看导航]({route['map_url']})")
    lines.append("")
    return lines


def _condense_knowledge(content: str) -> str:
    """提取知识文档中的可读内容"""
    lines, sentences = content.split("\n"), []
    header_names = {"项目", "场景", "方式", "信息", "推荐方案"}

    for line in lines:
        s = line.strip()
        if not s or re.match(r"^[\|\-\:\s\+]+$", s) or re.match(r"^[\s\-*•]+$", s):
            continue
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.split("|") if c.strip()]
            if len(cells) == 2 and cells[0] in header_names:
                continue
            row = f"{cells[0]}：{cells[1]}" if len(cells) == 2 else "，".join(cells)
            row = row.replace("**", "").replace("__", "")
            if row and not re.match(r"^[\s\-:\+]+$", row):
                sentences.append(row)
        else:
            clean = re.sub(r"^[#\s\-*•]+", "", s).strip().replace("**", "").replace("__", "")
            if clean:
                sentences.append(clean)
        if len("".join(sentences)) > 150:
            break

    return "；".join(sentences[:4])[:300] if sentences else ""


def _group_knowledge_items(items: list, min_dist_km: float = None) -> list[tuple]:
    """按来源文件分组"""
    if min_dist_km is not None and min_dist_km < 300:
        items = [it for it in items if "04_跨城交通方案" not in it.get("source", "")]
    grouped = defaultdict(list)
    for it in items:
        grouped[it["source_file"]].append(it)

    result = []
    seen = set()
    for src, group in grouped.items():
        name = src.replace(".md", "")
        merged = []
        for it in group:
            c = it["content"]
            k = c[:50]
            if k in seen:
                continue
            seen.add(k)
            lines = c.split("\n")
            while lines and lines[0].startswith("#"):
                lines = lines[1:]
            body = "\n".join(lines).strip()
            # 过滤推荐汇总表
            if body and not body.split("\n")[0].strip().startswith(("| 场景", "| 单人")):
                merged.append(body)
        if merged:
            result.append((name, "\n\n".join(merged)))
    return result


async def respond_node(state: dict) -> dict:
    """整合 specialist 输出为最终回复"""
    from langchain_core.messages import AIMessage
    outputs = state.get("specialist_outputs", {})
    query = state.get("user_query", "")
    profile = state.get("user_profile", {})
    pref_modes = profile.get("preferred_modes", [])

    # 闲聊直接返回
    if "chat" in outputs and outputs["chat"].get("success"):
        if not any(k in outputs for k in ["route", "poi", "train"]):
            msg = outputs["chat"]["message"]
            return {"final_response": msg, "messages": [AIMessage(content=msg)]}

    parts = []

    # ---- 路线方案 ----
    if "route" in outputs:
        r = outputs["route"]
        if r.get("success") and r.get("routes"):
            parts.append("## 🚗 路线方案" + ("  已按您的偏好排序" if pref_modes else ""))
            parts.append("")
            for i, route in enumerate(r["routes"][:3], 1):
                parts.extend(_format_route(route, i, pref_modes))

            # ---- 相关知识 ----
            items = r.get("knowledge_items", [])
            groups = _group_knowledge_items(items, r.get("min_distance_km"))
            if groups:
                parts.append("---")
                parts.append("## 📋 相关信息")
                parts.append("")
                for name, content in groups:
                    parts.append(f"**{name}**")
                    parts.append("")
                    parts.append(content)
                    parts.append("")
                    parts.append("---")
                    parts.append("")
        else:
            parts.append(f"⚠️ {r.get('message', '未找到可行路线')}")

    # ---- POI 推荐 ----
    if "poi" in outputs:
        p = outputs["poi"]
        if p.get("success") and p.get("pois"):
            parts.append("### 📍 附近推荐")
            for i, poi in enumerate(p["pois"][:5], 1):
                extras = [s for s in [poi.get("address", ""), f"{poi.get('distance', '')}米"] if s]
                parts.append(f"{i}. **{poi.get('name', '')}**" + (" — " + "，".join(extras) if extras else ""))
            parts.append("")
        else:
            parts.append(f"ℹ️ {p.get('message', '')}")

    # ---- 火车票 ----
    if "train" in outputs:
        t = outputs["train"]
        if t.get("success") and t.get("tickets"):
            parts.append("---")
            parts.append(t["tickets"])
            parts.append("")
        else:
            parts.append(f"ℹ️ {t.get('message', '')}")

    # ---- 兜底 ----
    if not parts:
        try:
            messages = state.get("messages", [])
            if messages:
                resp = await chat_model.ainvoke(messages[-5:] + [HumanMessage(content=query)])
            else:
                resp = await chat_model.ainvoke([HumanMessage(content=query)])
            parts.append(resp.content.strip())
        except Exception:
            parts.append("抱歉，我无法处理您的请求。")

    final = "\n".join(parts).strip()
    return {"final_response": final, "messages": [AIMessage(content=final)]}
