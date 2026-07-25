"""统一 API 入口 — 注册各路由模块"""
import sys, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

from utils.logger import setup_logger

logger = setup_logger("api")

app = FastAPI(title="AI 口播工坊", version="1.0.0")

# 允许跨域，便于前端通过 FontFace 加载字体文件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件 — 挂载上传、输出、音色特征、字体目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
for name in ["uploads", "outputs", "profiles", "fonts"]:
    d = PROJECT_ROOT / name
    if d.exists():
        app.mount(f"/{name}", StaticFiles(directory=str(d)), name=name)

# 捕获验证错误，避免二进制序列化崩溃
@app.exception_handler(Exception)
async def global_exception(request: Request, exc: Exception):
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(f"[{request.method}] {request.url.path} - {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "SERVER_ERROR", "message": str(exc)[:200], "detail": tb[-500:]}}
    )


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start = time.time()
    response = await call_next(request)
    cost = round((time.time() - start) * 1000, 1)
    if response.status_code >= 400:
        logger.warning(f"[{request.method}] {request.url.path} -> {response.status_code} ({cost}ms)")
    else:
        logger.info(f"[{request.method}] {request.url.path} -> {response.status_code} ({cost}ms)")
    return response

# 注册路由
from routes.general import router as general_router
from routes.voices import router as voices_router
from routes.videos import router as videos_router
from routes.templates import router as templates_router
from routes.compose import router as compose_router
from routes.settings import router as settings_router
from routes.subtitle_templates import router as subtitle_templates_router
from routes.cover_templates import router as cover_templates_router
from routes.extract import router as extract_router
from routes.cookies import router as cookies_router
from routes.publish import router as publish_router
from routes.logs import router as logs_router
from routes.auto_task import router as auto_task_router

app.include_router(general_router)
app.include_router(voices_router)
app.include_router(videos_router)
app.include_router(templates_router)
app.include_router(compose_router)
app.include_router(settings_router)
app.include_router(subtitle_templates_router)
app.include_router(cover_templates_router)
app.include_router(extract_router)
app.include_router(cookies_router)
app.include_router(publish_router)
app.include_router(logs_router)
app.include_router(auto_task_router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-video-tool"}

if __name__ == "__main__":
    print("API Service starting on :8000...")
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)
