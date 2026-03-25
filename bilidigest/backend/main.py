import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response
from pathlib import Path

from config import settings
from database import init_db
from routers import assets, generate, query

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="BiliDigest API", version="0.1.0")


@app.middleware("http")
async def catch_client_disconnect(request: Request, call_next):
    """客户端提前断开连接（如页面跳转）时，静默处理而非抛异常"""
    try:
        return await call_next(request)
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        logger.debug("客户端断开连接: %s %s", request.method, request.url.path)
        return Response(
            status_code=499,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )


# CORS：开发环境全部放行
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件（关键帧图片）
static_dir = settings.assets_path
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/assets", StaticFiles(directory=str(static_dir)), name="static")

# 路由注册
app.include_router(assets.router)
app.include_router(generate.router)
app.include_router(query.router)


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
