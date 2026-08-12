# ============================================================
# Stage 1: Build Frontend
# ============================================================
FROM docker.m.daocloud.io/library/node:20-alpine AS frontend-builder

WORKDIR /build
COPY frontend/ ./
RUN npm config set registry https://registry.npmmirror.com \
    && npm install \
    && npm run build

# ============================================================
# Stage 2: Python Backend
# ============================================================
FROM docker.m.daocloud.io/library/python:3.13-slim

WORKDIR /app

# 安装系统依赖（torch + sentence-transformers + Node.js 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm config set registry https://registry.npmmirror.com

# 安装 uv（使用清华 PyPI 镜像）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple "uv>=0.4.0"

# 复制依赖文件并安装（利用 Docker 层缓存 + 清华镜像）
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端源码
COPY backend/ ./backend/
COPY main.py ./

# 复制前端构建产物
COPY --from=frontend-builder /build/dist/ ./frontend/dist/

# 创建运行时数据目录
RUN mkdir -p /app/data

EXPOSE 8001

# 默认使用 uvicorn 直接启动（更稳定）
CMD ["uv", "run", "python", "main.py", "--port", "8001", "--host", "0.0.0.0"]
