"""路线规划智能体 — 服务入口"""
import os
import uvicorn
import argparse

import backend.api.routes  # noqa: F401
from backend.api.server import app
from fastapi.staticfiles import StaticFiles


# 生产环境：挂载前端静态文件
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
