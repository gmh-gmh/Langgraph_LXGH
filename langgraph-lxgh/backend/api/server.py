"""FastAPI 服务配置和共享组件"""
import asyncio # 异步编程，用于启动智能体构建
import uuid  # 生成唯一 ID（会话管理用）
from typing import Optional, List  # 类型提示，用于请求和响应模型
from fastapi import FastAPI  # FastAPI 框架，用于构建 API 服务
from fastapi.middleware.cors import CORSMiddleware  # 跨域资源共享中间件，用于允许跨域请求
from pydantic import BaseModel # 数据模型，用于定义请求和响应的结构
from backend.agent.graph import build_multi_agent_graph  # 弄建多智能体图

app = FastAPI(title="路线规划智能体 API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])# 允许所有来源的请求

multi_agent = asyncio.run(build_multi_agent_graph()) #会阻塞执行，直到图构建完成
multi_sessions = {} # 会话管理字典，用于存储每个会话的状态


class ChatRequest(BaseModel):
    user_query: str                              # 用户的问题，如"从北京到上海怎么走"
    image_base64: Optional[str] = None           # 可选：图片的 Base64 编码（多模态）
    session_id: Optional[str] = None             # 可选：会话 ID（多轮对话用）
    user_id: Optional[str] = None                # 可选：用户 ID（个性化用）


class ProfileUpdateRequest(BaseModel):
    preferred_modes: Optional[List[str]] = None      # 偏好出行方式：["驾车","高铁"]
    frequent_locations: Optional[List[dict]] = None  # 常去地点
    trip_preferences: Optional[dict] = None          # 行程偏好
    ev_car: Optional[bool] = None                    # 是否开电动车


def build_multi_agent_input(user_query, user_id="default", image_base64=None):
    from backend.user_profile.profile_db import get_profile
    from langchain_core.messages import HumanMessage
    profile = get_profile(user_id)
    return {
        "messages": [HumanMessage(content=user_query)],  # LangGraph 消息列表
        "user_query": user_query,                        # 原始查询文本
        "user_id": user_id,                              # 用户 ID
        "user_profile": profile,                         # 从 SQLite 读取的用户画像
        "image_base64": image_base64,                    # 图片（多模态）
        "image_description": None,                       # 图片描述（待 AI 填充）
        "supervisor_decision": "",                       # Supervisor 的路由决策
        "specialist_outputs": {},                        # 各专家的输出结果
        "final_response": None,                          # 最终回复
        "current_step": 0,                               # 当前步数
        "max_steps": 5,                                  # 最大步数（防死循环）
    }
