"""编排层 — 质量评价节点（过滤不相关知识）"""
from backend.rag.harness import get_harness
from backend.utils.logger_handler import logger

CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "重庆",
    "武汉", "南京", "西安", "长沙", "郑州", "天津", "苏州",
    "合肥", "蚌埠", "厦门", "青岛", "大连", "昆明", "贵阳",
    "福州", "南昌", "哈尔滨", "长春", "沈阳", "济南", "太原",
]

#遍历城市列表，返回文本中出现的所有城市名。
def _extract_locations(text: str) -> list[str]:
    return [c for c in CITIES if c in text]


async def quality_evaluator_node(state: dict) -> dict:
    """过滤不相关的知识条目"""
    outputs = dict(state.get("specialist_outputs", {}))
    query = state.get("user_query", "")
    locations = _extract_locations(query)

    if len(locations) < 2:
        return {"supervisor_decision": ""}

    for key in ["route", "poi", "train"]:
        if key in outputs and outputs[key].get("knowledge_items"):
            items = outputs[key]["knowledge_items"]
            filtered = [it for it in items if sum(1 for loc in locations if loc in (it["content"] + " " + it.get("source", ""))) >= 2]

            if filtered:
                outputs[key]["knowledge_items"] = filtered
                outputs[key]["knowledge"] = get_harness().format_compact(filtered)
            else:
                outputs[key]["knowledge_items"] = []
                outputs[key]["knowledge"] = ""
                outputs[key]["knowledge_cited"] = ""

    return {"specialist_outputs": outputs, "supervisor_decision": ""}
