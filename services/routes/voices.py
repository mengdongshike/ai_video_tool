"""音色路由 — 上传管理 + 合成（通过 HTTP 调用 TTS 微服务）"""
import httpx
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel
from utils.upload import save_voice
from database import list_voices, get_voice, create_voice, delete_voice, rename_voice, set_default_voice, count_voices, update_project

router = APIRouter(prefix="/api")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # routes/ → services/ → AI_video_tool/
TTS_URL = "http://127.0.0.1:8101"

def _fmt(v):
    return {"id": v["id"], "title": v["name"],
            "voice_url": v.get("audio_path",""), "audio_path": v.get("audio_path",""),
            "is_default": bool(v.get("is_default",0))}

class SynthesizeRequest(BaseModel):
    text: str
    profile: str = ""
    pid: str = ""
    use_emo_text: bool = False
    emo_text: str = ""
    emo_vector: list | None = None
    emo_alpha: float = 1.0
    emo_audio_path: str = ""
    interval_silence: int = 200
    max_text_tokens_per_segment: int = 120
    extra: str = "allow"   # 允许额外字段

@router.post("/voices")
async def create(file: UploadFile = File(...), name: str = Form("")):
    audio_path = await save_voice(file)
    final_name = name or Path(file.filename).stem
    voice = create_voice(final_name, audio_path, audio_path)
    return _fmt(voice)

@router.delete("/voices/{id}")
def delete_one(id: int):
    delete_voice(id)
    return {"success": True}

@router.put("/voices/{id}")
def rename_one(id: int, body: dict = Body(...)):
    v = rename_voice(id, body.get("new_name",""))
    if not v: raise HTTPException(404)
    return _fmt(v)

@router.post("/voices/{id}/default")
def set_default(id: int):
    set_default_voice(id)
    return {"success": True}

@router.get("/voices")
def list_all():
    # 进入音频页面，卸载数字人模型释放显存（后台线程执行，不阻塞）
    import threading
    def _unload_latent():
        import httpx
        try:
            httpx.post("http://127.0.0.1:8102/unload", timeout=3)
        except:
            pass
    threading.Thread(target=_unload_latent, daemon=True).start()
    data = list_voices()
    return {
        "preset": [_fmt(v) for v in data.get("preset", [])],
        "cloned": [_fmt(v) for v in data.get("cloned", [])]
    }

@router.get("/voices/stats")
def stats():
    return {"total": count_voices()}

@router.post("/tts/synthesize")
async def synthesize(req: SynthesizeRequest):
    """合成语音 — 直接用音频路径，无需 profile 文件"""
    timeout = httpx.Timeout(connect=10, read=1200, write=30, pool=30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{TTS_URL}/synthesize", json={
            "text": req.text,
            "audio_path": str(PROJECT_ROOT / req.profile) if req.profile else "",
            "output_dir": str(PROJECT_ROOT / "outputs" / "audio"),
            "emo_vector": req.emo_vector,
            "emo_audio_path": req.emo_audio_path,
            "emo_alpha": req.emo_alpha,
            "emo_text": req.emo_text,
            "interval_silence": req.interval_silence,
            "max_text_tokens_per_segment": req.max_text_tokens_per_segment,
        })
        if r.status_code != 200:
            raise HTTPException(502, f"TTS 服务错误: {r.text[:200]}")
        result = r.json()

    if req.pid and result.get("audio_url"):
        update_project(str(req.pid), {"output_audio": result["audio_url"], "srt_path": result.get("subtitle_url","")})

    return result
