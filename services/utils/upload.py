"""
文件上传工具 — 只供后端内部调用
不注册为外部路由，直接 import 使用
"""
import uuid
import subprocess
import json
from pathlib import Path
from fastapi import UploadFile, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / "uploads"

ALLOWED_AUDIO = (".wav", ".mp3", ".m4a", ".flac", ".ogg")
ALLOWED_VIDEO = (".mp4", ".mov", ".avi", ".mkv", ".webm")

MAX_VOICE_DURATION = 15.0  # 参考音频最大时长（秒）


def _get_audio_duration(filepath: Path) -> float:
    """使用 ffprobe 获取音频时长（秒），失败返回 0"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(filepath)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info.get("format", {}).get("duration", 0))
    except Exception:
        pass
    return 0.0


def _trim_audio(input_path: Path, output_path: Path, max_duration: float = MAX_VOICE_DURATION):
    """用 ffmpeg 截取音频前 max_duration 秒，保留原格式"""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-t", str(max_duration),
         "-c", "copy", str(output_path)],
        capture_output=True, timeout=60,
    )


async def save_voice(file: UploadFile) -> str:
    """保存上传的音频文件，超过15秒自动截取前15秒，返回相对路径"""
    if not file.filename:
        raise HTTPException(400, "未选择文件")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_AUDIO:
        raise HTTPException(400, f"不支持的音频格式: {ext}")
    
    voices_dir = UPLOAD_DIR / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)

    # 先保存原始上传文件
    raw_name = f"{uuid.uuid4().hex[:8]}_raw_{file.filename}"
    raw_path = voices_dir / raw_name
    
    content = await file.read()
    raw_path.write_bytes(content)

    # 检测时长，超过15秒则截取
    duration = _get_audio_duration(raw_path)
    if duration > MAX_VOICE_DURATION:
        trim_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        trim_path = voices_dir / trim_name
        _trim_audio(raw_path, trim_path)
        # 删除原始长音频
        try:
            raw_path.unlink()
        except Exception:
            pass
        return f"uploads/voices/{trim_name}"
    else:
        # 不超过15秒，重命名为正式名称，删除 raw_ 前缀文件
        final_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        final_path = voices_dir / final_name
        raw_path.rename(final_path)
        return f"uploads/voices/{final_name}"

async def save_video(file: UploadFile) -> str:
    """保存上传的视频文件，返回相对路径"""
    if not file.filename:
        raise HTTPException(400, "未选择文件")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_VIDEO:
        raise HTTPException(400, f"不支持的视频格式: {ext}")

    videos_dir = UPLOAD_DIR / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    save_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    save_path = videos_dir / save_name

    content = await file.read()
    save_path.write_bytes(content)
    return f"uploads/videos/{save_name}"

async def save_bgm(file: UploadFile) -> str:
    """保存上传的 BGM 文件，返回相对路径"""
    if not file.filename:
        raise HTTPException(400, "未选择文件")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_AUDIO:
        raise HTTPException(400, f"不支持的音频格式: {ext}")

    bgm_dir = UPLOAD_DIR / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)
    save_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    save_path = bgm_dir / save_name

    content = await file.read()
    save_path.write_bytes(content)
    return f"uploads/bgm/{save_name}"
