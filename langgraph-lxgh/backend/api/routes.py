"""API 路由"""
import json
import uuid
import asyncio
from typing import Optional
from fastapi.responses import StreamingResponse

from backend.api.server import (
    app, multi_agent, multi_sessions,
    ChatRequest, ProfileUpdateRequest,
    build_multi_agent_input,
)
from backend.user_profile.profile_db import get_profile, update_profile, add_search_history


async def generate_chunks(text: str, chunk_size: int = 10):
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]
        await asyncio.sleep(0.05)

#前端启动时会调用这个接口，检查后端是否在线。
@app.get("/api/status")
async def read_root():
    return {"message": "路线规划智能体 API 服务"}


# ============================================================
# 用户画像 API 读取用户偏好（出行方式、常去地点等）。前端页面加载时调用（日志中的 GET /api/profile/user_ms0b6x9e 就是这个）
# ============================================================
@app.get("/api/profile/{user_id}")
async def api_get_profile(user_id: str):
    profile = get_profile(user_id)
    return {"status": "success", "profile": profile}


# ============================================================
# 用户画像 API 更新用户偏好（出行方式、常去地点等）。前端页面提交表单时调用（日志中的 PUT /api/profile/user_ms0b6x9e 就是这个）
# ============================================================
@app.put("/api/profile/{user_id}")
async def api_update_profile(user_id: str, request: ProfileUpdateRequest):
    updates = {}
    if request.preferred_modes is not None:
        updates["preferred_modes"] = request.preferred_modes
    if request.frequent_locations is not None:
        updates["frequent_locations"] = request.frequent_locations
    if request.trip_preferences is not None:
        updates["trip_preferences"] = request.trip_preferences
    if request.ev_car is not None:
        updates["ev_car"] = request.ev_car
    profile = update_profile(user_id, updates)
    return {"status": "success", "profile": profile}

#统计用户历史查询的意图分布，用于前端展示用户画像仪表盘。
@app.get("/api/profile/{user_id}/stats")
async def api_profile_stats(user_id: str):
    profile = get_profile(user_id)
    history = profile.get("search_history", [])
    intents = {}
    for h in history:
        intent = h.get("intent", "unknown")
        intents[intent] = intents.get(intent, 0) + 1
    return {
        "status": "success",
        "stats": {
            "total_queries": len(history),
            "intent_breakdown": intents,
            "preferred_modes": profile.get("preferred_modes", []),
            "ev_car": profile.get("ev_car", False),
        }
    }


# ============================================================
# Multi-Agent 流式聊天
# ============================================================
async def multi_stream_response(
    session_id: str,            # 会话 ID（多轮对话标识）
    user_query: str,            # 用户问题
    user_id: str = "default",   # 用户 ID
    image_base64: Optional[str] = None,  # 可选图片
):
    if session_id not in multi_sessions:
        multi_sessions[session_id] = {"config": {"configurable": {"thread_id": session_id}}}
    session = multi_sessions[session_id]

    try:
        add_search_history(user_id, user_query, "multi_agent")
        result = await multi_agent.ainvoke(
            build_multi_agent_input(user_query, user_id, image_base64),
            session["config"],
        )

        final = result.get("final_response") if isinstance(result, dict) else "处理完成"
        outputs = result.get("specialist_outputs", {}) if isinstance(result, dict) else {}

        if "route" in outputs:
            r_route = outputs["route"]
            if r_route.get("success") and r_route.get("routes"):
                info1 = {"type": "info", "content": "🔍 已调用路线规划专家"}
                yield f"data: {json.dumps(info1, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
                start = r_route.get("origin", "")
                end = r_route.get("destination", "")
                info2 = {"type": "info", "content": f"📍 起点: {start} → 终点: {end}"}
                yield f"data: {json.dumps(info2, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
                routes_count = len(r_route["routes"])
                info3 = {"type": "info", "content": f"🚗 找到 {routes_count} 条路线方案"}
                yield f"data: {json.dumps(info3, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)

        async for chunk in generate_chunks(str(final)):
            yield f"data: {json.dumps({'type': 'stream', 'content': chunk}, ensure_ascii=False)}\n\n"
        yield f'data: {json.dumps({"type": "end", "content": "", "session_id": session_id}, ensure_ascii=False)}\n\n'

    except Exception as e:
        print(f"[ERROR] multi_stream: {e}")
        import traceback; traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'content': f'处理请求时出错: {str(e)}'}, ensure_ascii=False)}\n\n"


@app.post("/api/multi/chat/stream")
async def multi_chat_stream(request: ChatRequest):
    if not request.session_id:
        request.session_id = str(uuid.uuid4())
    if not request.user_id:
        request.user_id = "default"
    return StreamingResponse(
        multi_stream_response(request.session_id, request.user_query, request.user_id, request.image_base64),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no", "X-Session-Id": request.session_id}
    )


@app.post("/api/multi/chat")
async def multi_chat(request: ChatRequest):
    if not request.session_id:
        request.session_id = str(uuid.uuid4())
    if not request.user_id:
        request.user_id = "default"
    if request.session_id not in multi_sessions:
        multi_sessions[request.session_id] = {"config": {"configurable": {"thread_id": request.session_id}}}
    session = multi_sessions[request.session_id]
    try:
        add_search_history(request.user_id, request.user_query, "multi_agent")
        result = await multi_agent.ainvoke(
            build_multi_agent_input(request.user_query, request.user_id, request.image_base64),
            session["config"],
        )
        final = result.get("final_response") if isinstance(result, dict) else "处理完成"
        return {
            "session_id": request.session_id,
            "status": "success",
            "response": str(final),
        }
    except Exception as e:
        print(f"[ERROR] multi_chat: {e}")
        import traceback; traceback.print_exc()
        return {"session_id": request.session_id, "status": "error", "response": f"处理出错: {str(e)}"}
