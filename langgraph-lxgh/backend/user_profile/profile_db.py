"""
用户画像数据库 — SQLite 存储用户偏好、常用地点、出行历史。

Schema:
  user_id TEXT PRIMARY KEY
  preferred_modes TEXT   — JSON ["driving", "transit", "walking"]
  frequent_locations TEXT — JSON [{"name":"家","address":"...","location":"lng,lat"}]
  trip_preferences TEXT  — JSON {"prioritize_speed":true,"avoid_tolls":false,...}
  search_history TEXT    — JSON [{query, intent, timestamp}, ...]
  ev_car BOOLEAN         — 是否开电动车
  created_at / updated_at
"""

import json
import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "user_profiles.db")


def _get_conn():
    """获取数据库连接（线程安全：每次调用创建新连接）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row #让查询结果可以通过列名访问（ row["user_id"] ）
    conn.execute("PRAGMA journal_mode=WAL") # Write-Ahead Logging，提高并发性能
    _init_db(conn)
    return conn


def _init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            preferred_modes TEXT DEFAULT '[]',
            frequent_locations TEXT DEFAULT '[]',
            trip_preferences TEXT DEFAULT '{}',
            search_history TEXT DEFAULT '[]',
            ev_car INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


# ============================================================
# 公开 API
# ============================================================

def get_profile(user_id: str) -> dict:
    """获取用户画像，不存在则返回默认"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            return _default_profile(user_id)
        return {
            "user_id": row["user_id"],
            "preferred_modes": json.loads(row["preferred_modes"]),
            "frequent_locations": json.loads(row["frequent_locations"]),
            "trip_preferences": json.loads(row["trip_preferences"]),
            "search_history": json.loads(row["search_history"]),
            "ev_car": bool(row["ev_car"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


def update_profile(user_id: str, updates: dict) -> dict:
    """更新用户画像字段（部分更新）"""
    conn = _get_conn()
    try:
        # 确保用户存在
        existing = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id=?", (user_id,)
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,)
            )

        profile = get_profile(user_id)

        # 合并更新
        if "preferred_modes" in updates:
            profile["preferred_modes"] = updates["preferred_modes"]
        if "frequent_locations" in updates:
            profile["frequent_locations"] = updates["frequent_locations"]
        if "trip_preferences" in updates:
            profile["trip_preferences"].update(updates["trip_preferences"])
        if "ev_car" in updates:
            profile["ev_car"] = updates["ev_car"]

        conn.execute("""
            UPDATE user_profiles SET
                preferred_modes=?, frequent_locations=?,
                trip_preferences=?, ev_car=?,
                updated_at=datetime('now')
            WHERE user_id=?
        """, (
            json.dumps(profile["preferred_modes"], ensure_ascii=False),
            json.dumps(profile["frequent_locations"], ensure_ascii=False),
            json.dumps(profile["trip_preferences"], ensure_ascii=False),
            int(profile["ev_car"]),
            user_id,
        ))
        conn.commit()
        return profile
    finally:
        conn.close()


def add_search_history(user_id: str, query: str, intent: str = ""):
    """记录一条搜索历史（保留最近20条）"""
    conn = _get_conn()
    try:
        profile = get_profile(user_id)
        history = profile["search_history"]
        history.append({
            "query": query,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
        })
        history = history[-20:]  # 只保留最近20条
        conn.execute(
            "UPDATE user_profiles SET search_history=?, updated_at=datetime('now') WHERE user_id=?",
            (json.dumps(history, ensure_ascii=False), user_id),
        )
        conn.commit()
    finally:
        conn.close()


def extract_and_update_preferences(user_id: str, query: str):
    """从用户自然语言查询中提取偏好并更新画像"""
    profile = get_profile(user_id)
    prefs = profile["trip_preferences"]
    modes = profile["preferred_modes"]
    changed = False

    # 从查询中提取出行方式偏好
    mode_keywords = {
        "driving": ["开车", "驾车", "自驾", "我开车", "开车去"],
        "transit": ["坐地铁", "坐公交", "公共交通", "地铁", "公交"],
        "walking": ["走路", "步行"],
    }
    for mode, keywords in mode_keywords.items():
        if any(kw in query for kw in keywords):
            if mode not in modes:
                modes.insert(0, mode)
                changed = True
            break

    # 从查询中提取限行/收费偏好
    if any(kw in query for kw in ["避收费站", "不走高速", "省钱"]):
        prefs["avoid_tolls"] = True
        changed = True
    if any(kw in query for kw in ["最快", "赶时间", "最短时间"]):
        prefs["prioritize_speed"] = True
        changed = True
    if any(kw in query for kw in ["限行", "进京证", "外地牌"]):
        prefs["check_restrictions"] = True
        changed = True

    if changed:
        update_profile(user_id, {
            "preferred_modes": modes[:3],  # 最多保留3种偏好
            "trip_preferences": prefs,
        })


def personalize_routes(routes: list[dict], user_id: str) -> list[dict]:
    """根据用户画像对路线进行个性化排序和评分"""
    if not routes:
        return routes

    profile = get_profile(user_id)
    prefs = profile["trip_preferences"]
    modes = profile["preferred_modes"]

    scored = []
    for r in routes:
        score = 50  # 基础分

        # 偏好出行方式加分
        if modes and r.get("mode") in modes:
            score += 20

        # 速度偏好
        if prefs.get("prioritize_speed") and r.get("duration", 0) > 0:
            score += max(0, 30 - r["duration"] / 60)  # 耗时越短分越高

        # 费用偏好
        if prefs.get("avoid_tolls") and r.get("tolls", 0) == 0:
            score += 15
        elif prefs.get("avoid_tolls") and r.get("tolls", 0) > 0:
            score -= 15

        # 电动车偏好
        if profile.get("ev_car"):
            if r.get("mode") == "driving":
                score += 10  # 适合自驾查充电桩等信息

        scored.append((score, r))

    # 按分数降序排列
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]


def _default_profile(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "preferred_modes": [],
        "frequent_locations": [],
        "trip_preferences": {
            "prioritize_speed": False,
            "avoid_tolls": False,
            "check_restrictions": False,
        },
        "search_history": [],
        "ev_car": False,
        "created_at": None,
        "updated_at": None,
    }
