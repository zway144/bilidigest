from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import settings
from database import init_db
from routers import assets, generate, query

app = FastAPI(title="BiliDigest API", version="0.1.0")

# CORS：允许前端 localhost:3000 访问
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
