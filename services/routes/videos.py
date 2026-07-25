"""视频路由 — 管理 + 数字人生成 + 视频下载"""
import httpx
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel
from utils.upload import save_video
from database import *

router = APIRouter(prefix="/api", tags=["视频"])
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LATENT_URL = "http://127.0.0.1:8102"

class GenerateRequest(BaseModel):
    avatar_video: str
    audio_path: str

# ------ 视频 CRUD ------

@router.get("/videos")
def list_all():
    # 进入视频页面，卸载 TTS 模型释放显存（后台线程执行，不阻塞）
    import threading
    def _unload_tts():
        import httpx
        try:
            httpx.post("http://127.0.0.1:8101/unload", timeout=3)
        except:
            pass
    threading.Thread(target=_unload_tts, daemon=True).start()
    return list_videos()

@router.get("/videos/stats")
def stats():
    return {"total": count_videos()}

@router.get("/videos/{id}")
def get_one(id: int):
    v = get_video(id)
    if not v: raise HTTPException(404)
    return v

@router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...), name: str = Form("")):
    video_path = await save_video(file)
    return create_video(name or Path(file.filename).stem, video_path)

@router.delete("/videos/{id}")
def delete_one(id: int):
    delete_video(id)
    return {"success": True}

@router.put("/videos/{id}")
def rename_one(id: int, body: dict = Body(...)):
    v = rename_video(id, body.get("name", ""))
    if not v: raise HTTPException(404)
    return v

@router.post("/videos/{id}/thumbnail")
def thumbnail(id: int):
    return {"success": True}

# ------ 数字人 ------

@router.post("/dh/generate")
async def generate(avatar_url: str = Form(...), pid: str = Form("")):
    """数字人生成"""
    # 从项目取合成音频路径
    audio_path = ""
    if pid:
        p = get_project(str(pid))
        if p: audio_path = p.get("output_audio", "")
    # 转绝对路径
    abs_video = str(PROJECT_ROOT / avatar_url) if not Path(avatar_url).is_absolute() else avatar_url
    abs_audio = str(PROJECT_ROOT / audio_path) if audio_path and not Path(audio_path).is_absolute() else audio_path

    payload = {
        "video_path": abs_video,
        "audio_path": abs_audio,
        "output_dir": str(PROJECT_ROOT / "outputs" / "video")
    }

    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(f"{LATENT_URL}/generate", json=payload, timeout=1800)
                if r.status_code != 200:
                    raise HTTPException(502, f"数字人服务错误: {r.text[:200]}")
                result = r.json()
                break
        except httpx.ReadError:
            last_error = "数字人服务连接断开(可能显存不足导致崩溃)，正在重试..."
            if attempt < 2:
                import asyncio
                await asyncio.sleep(3)  # 等待服务重启
                continue
            raise HTTPException(502, f"数字人服务连接失败(重试3次): {last_error}")
        except httpx.ConnectError:
            last_error = "数字人服务未响应，正在等待恢复..."
            if attempt < 2:
                import asyncio
                await asyncio.sleep(5)
                continue
            raise HTTPException(502, f"数字人服务连接失败(重试3次): {last_error}")
    else:
        raise HTTPException(502, f"数字人服务异常: {last_error}")

    # 存库
    if pid and result.get("video_url"):
        update_project(str(pid), {"output_video": result["video_url"]})

    return result

@router.get("/dh/models")
async def list_models():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{LATENT_URL}/models", timeout=5)
        return r.json()


