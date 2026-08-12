"""意图分类器 — GLiClass 零样本分类 + 关键字规则兜底"""
import os
import re

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

_CLASSIFIER = None


def _get_classifier():
    global _CLASSIFIER
    if _CLASSIFIER is not None:
        return _CLASSIFIER

    import warnings
    warnings.filterwarnings("ignore", message=".*symlinks.*")
    warnings.filterwarnings("ignore", message=".*You are using a model of type.*")

    from gliclass import GLiClassModel, ZeroShotClassificationPipeline
    from transformers import AutoTokenizer

    model_id = "knowledgator/gliclass-small-v1.0"
    from huggingface_hub import try_to_load_from_cache
    if try_to_load_from_cache(model_id, "config.json") is not None:
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    try:
        model = GLiClassModel.from_pretrained(model_id)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
    finally:
        os.environ.pop("TRANSFORMERS_OFFLINE", None)

    _CLASSIFIER = ZeroShotClassificationPipeline(
        model, tokenizer, classification_type="single-label", device="cpu",
    )
    return _CLASSIFIER


# ============================================================
# 关键字规则（优先级高于 GLiClass）
# ============================================================

_ROUTE_KW = ["怎么走", "怎么去", "路线", "驾车", "自驾", "开车",
             "坐车", "公交", "地铁", "打车", "不驾车", "不开车",
             "最快", "最近", "推荐.*路线", "导航"]

_POI_KW = ["附近", "周边", "有什么", "推荐.*(?:餐厅|酒店|景点|停车场|充电桩|加油站)",
           "哪里有好", "哪里有", "搜索", "找.*(?:餐厅|酒店|景点|停车|充电|加油)"]

_GENERAL_KW = ["你好", "您好", "hi", "hello", "谢谢", "再见", "天气",
               "时间", "日期", "你是谁", "你能做什么"]


def _keyword_classify(text: str) -> str | None:
    """关键字规则分类，命中则直接返回"""
    t = text.strip()

    # 极短文本 → general_chat
    if len(t) <= 4:
        return "general_chat"

    # 带 "到" 且含城市名 → route_plan（但排除纯闲聊）
    has_dao = "到" in t or "去" in t
    if has_dao and ("票" in t or "火车" in t or "高铁" in t):
        return "route_plan"

    for kw in _GENERAL_KW:
        if re.search(kw, t):
            return "general_chat"

    for kw in _ROUTE_KW:
        if re.search(kw, t):
            return "route_plan"

    # POI 关键字
    for kw in _POI_KW:
        if re.search(kw, t):
            return "poi_search"

    # "X到Y" 模式 → route_plan
    if re.search(r'[^的]到[^底]', t) and len(t) > 6:
        return "route_plan"

    return None  # 交给 GLiClass


# ============================================================
# GLiClass 零样本分类
# ============================================================

GLI_LABELS = ["路线规划", "周边搜索", "闲聊"]
LABEL_MAP = {"路线规划": "route_plan", "周边搜索": "poi_search", "闲聊": "general_chat"}


def classify_intent(text: str) -> dict:
    """意图分类（关键字规则 → GLiClass 兜底）"""
    # 1. 关键字规则
    rule_result = _keyword_classify(text)
    if rule_result:
        print(f"[INTENT] 关键字→ {rule_result}: {text[:30]}...")
        return {"intent": rule_result, "score": 1.0, "source": "rule"}

    # 2. GLiClass 兜底
    pipeline = _get_classifier()
    try:
        results = pipeline(text, GLI_LABELS, threshold=0.0)[0]
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        top_cn = sorted_results[0]["label"] if sorted_results else "闲聊"
        top_score = sorted_results[0]["score"] if sorted_results else 0.0
        if top_score < 0.3:
            top_cn = "闲聊"
        intent = LABEL_MAP.get(top_cn, "general_chat")
        print(f"[INTENT] GLiClass→ {top_cn}→{intent} ({top_score:.3f}): {text[:30]}...")
        return {"intent": intent, "score": round(top_score, 3), "source": "gliclass"}
    except Exception as e:
        print(f"[INTENT] GLiClass 失败，降级到 general_chat: {e}")
        return {"intent": "general_chat", "score": 0.0, "source": "fallback"}
