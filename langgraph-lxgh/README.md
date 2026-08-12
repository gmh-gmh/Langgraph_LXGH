# 智能路线规划助手 🗺️

基于 **LangGraph Supervisor+Specialists 架构** 的多智能体路线规划 Agent，支持自然语言交互、多模态图片理解与 SSE 实时流式对话。后端自主决策调用高德地图 API / 12306 MCP 完成路线规划与 POI 搜索，集成通义千问四模型全家桶构建全链路 RAG + 验证护栏。

## 架构亮点

```
                    ┌─────────────────────────────────┐
                    │        用户输入 (文本/图片)        │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │       understand_image           │
                    │    (qwen3-omni-flash 多模态分析)   │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │           rewrite                │
                    │      (查询改写与上下文补全)         │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │        Supervisor (qwen-max)      │
                    │        LLM 路由决策 + 关键词兜底    │
                    └──┬─────────┬─────────┬────────┬──┘
                       │         │         │        │
          ┌────────────▼──┐ ┌───▼────┐ ┌──▼───┐ ┌─▼──────┐
          │route_special.│ │poi_spec│ │train │ │chat    │
          │高德路线规划   │ │POI搜索 │ │12306 │ │闲聊    │
          └───────────────┘ └────────┘ └──────┘ └────────┘
                       │         │         │        │
                       └─────────┴─────────┴────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │      quality_evaluator           │
                    │      (RAG 知识过滤与质检)          │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │           respond                │
                    │    (结构化 Markdown 回复生成)      │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   SSE 流式推送 (info/stream/end)  │
                    └─────────────────────────────────┘
```

## 功能特性

- 🧭 **智能路线规划** — 自然语言描述出行需求，自动调用高德 API 生成多方案比选（驾车/公交/骑行/步行）
- 🏙️ **POI 周边搜索** — "天安门附近的美食"→ 自动识别位置与关键词，返回结构化结果
- 🚄 **火车票查询** — 集成 12306 MCP（JSON-RPC 子进程直连），支持日期上下文继承
- 📷 **多模态理解** — 上传地图截图/路况图，qwen3-omni-flash 自动提取关键信息辅助规划
- 💬 **SSE 实时流式对话** — 多类型事件推送（进度提示 + 文本流 + 结束信号），模拟打字效果
- 📚 **RAG 知识库** — 15 份城市出行文档（限行/景区/跨城交通），通义全链路检索 + 重排 + 验证护栏
- 👤 **用户画像个性化** — SQLite 持久化偏好，自动从对话中提取出行习惯，路线个性化排序
- 🔄 **多会话记忆** — LangGraph AsyncSqliteSaver 持久化检查点，跨会话上下文恢复

## 技术栈

| 层级 | 技术 |
|------|------|
| **AI 编排** | LangGraph (StateGraph, Supervisor+Specialists, AsyncSqliteSaver) |
| **大模型** | 通义千问 qwen-max / qwen3-omni-flash / text-embedding-v3 / qwen3-rerank |
| **后端** | Python 3.13 + FastAPI + Uvicorn + SSE 流式 |
| **向量数据库** | ChromaDB + DashScope Embeddings |
| **地图服务** | 高德地图 API（地理编码 / 路线规划 / POI搜索 / 静态地图） |
| **火车票** | 12306 MCP（JSON-RPC 子进程直连） |
| **前端** | Vue 3 (Composition API) + Vite + Naive UI + marked |
| **数据库** | SQLite（用户画像 + LangGraph 检查点） |
| **容器化** | Docker 多阶段构建 + docker-compose |
| **包管理** | uv (Python) / npm (前端) |

## 快速开始

### 1. 环境变量

复制 `.env.example` 为 `.env` 并填入密钥：

```env
AMAP_KEY=你的高德地图API Key
AMAP_DRIVING_API_URL=https://restapi.amap.com/v3/direction/driving
AMAP_BASE_URL=https://restapi.amap.com/v3

DASHSCOPE_API_KEY=你的阿里云DashScope API Key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 2. 安装依赖

```bash
# 后端（推荐使用 uv）
pip install uv
uv sync

# 前端
cd frontend && npm install && cd ..
```

### 3. 运行

```bash
# 启动后端服务
python main.py --port 8001

# 新终端：启动前端开发服务器
cd frontend && npm run dev
```

- 后端 API: http://localhost:8001
- 前端页面: http://localhost:5173

## Docker 部署

```bash
docker compose up -d --build
```

服务将在 `http://localhost:8001` 启动（前后端合一）。

## API 接口

### POST `/api/multi/chat/stream` — 流式对话（SSE）

```json
{
  "user_query": "从北京到上海怎么走",
  "session_id": null,
  "user_id": "default",
  "image_base64": null
}
```

响应为 `text/event-stream`，包含三种事件类型：
- `info` — 进度提示（如"已调用路线规划专家"）
- `stream` — Markdown 文本流（每 10 字符一片，间隔 50ms）
- `end` — 结束信号，携带 session_id

### POST `/api/multi/chat` — 非流式对话

### GET/PUT `/api/profile/{user_id}` — 用户画像管理

### GET `/api/profile/{user_id}/stats` — 查询统计

## 项目结构

```
route_planning_agent/
├── backend/
│   ├── agent/               # LangGraph 多智能体
│   │   ├── graph.py         # StateGraph 定义（8 节点有向图）
│   │   ├── supervisor.py    # LLM 路由决策节点
│   │   ├── specialists.py   # 4 个 Specialist 执行节点
│   │   ├── respond.py       # 回复生成节点
│   │   ├── quality.py       # RAG 质量评价节点
│   │   └── state.py         # 多智能体状态定义
│   ├── api/
│   │   ├── server.py        # FastAPI 应用 + CORS
│   │   └── routes.py        # API 路由（聊天/画像/统计）
│   ├── services/
│   │   └── geocoding.py     # 高德地图 API 封装
│   ├── tools/
│   │   ├── tools.py         # LangChain 工具函数
│   │   └── train_tools.py   # 12306 MCP 工具（JSON-RPC）
│   ├── rag/
│   │   ├── harness.py       # RAGHarness 验证护栏
│   │   ├── retriever.py     # 检索器（初检 + 重排）
│   │   ├── vectorstore.py   # ChromaDB 向量存储
│   │   ├── loader.py        # 文档加载
│   │   ├── splitter.py      # 文本分块
│   │   ├── ingest.py        # 知识库导入
│   │   └── data/            # 15 份城市出行文档
│   ├── model/
│   │   └── factory.py       # 模型工厂（4 种通义模型）
│   ├── nlu/
│   │   └── intent_classifier.py  # GLiClass 两阶段意图分类
│   ├── user_profile/
│   │   └── profile_db.py    # SQLite 用户画像
│   ├── config/
│   │   ├── chroma.yml       # ChromaDB 配置
│   │   └── prompts.yml      # 提示词路径配置
│   └── utils/
│       ├── config_handler.py
│       ├── prompt_load.py
│       ├── path_tool.py
│       └── logger_handler.py
├── frontend/
│   ├── src/
│   │   ├── components/      # ChatSidebar / ChatHeader / MessagesArea / ChatInput
│   │   ├── composables/     # useChat.js（SSE 流式 + 状态管理）
│   │   └── style.css        # Naive UI 暗黑主题
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── main.py                  # 服务入口（--port 8001）
├── Dockerfile               # 多阶段构建
├── docker-compose.yml       # 国内镜像源优化
├── pyproject.toml           # Python 依赖
└── .env.example             # 环境变量模板
```

## 开源

GitHub: [https://github.com/YIGUAREN/-agent](https://github.com/YIGUAREN/-agent)
