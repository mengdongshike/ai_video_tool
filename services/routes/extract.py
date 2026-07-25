"""视频文案提取路由 — 解析链接、下载视频、提取文案"""
import re
import sys
from pathlib import Path
from database import update_project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.video_downloader import get_video_info, download_video, detect_platform, SUPPORTED_PLATFORMS
from utils.platform import get_downloader
from utils.text_extractor import extract_video_text, clean_text

router = APIRouter(prefix="/api", tags=["文案提取"])
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _needs_cookie(platform: str) -> bool:
    """检查指定平台是否需要 cookie"""
    try:
        d = get_downloader(platform)
        return getattr(d, "NEEDS_COOKIE", True)
    except Exception:
        return False


def _has_cookie(platform: str) -> bool:
    """检查指定平台是否有 cookie"""
    try:
        d = get_downloader(platform)
        return d.get_cookie_file() is not None
    except Exception:
        return False


def parse_video_url(raw_url: str) -> str:
    """解析视频链接，提取真实页面地址"""
    if not raw_url:
        return ""
    
    url = raw_url.strip()
    
    url_pattern = re.compile(
        r'https?://[^\s\'\"<>]+',
        re.IGNORECASE
    )
    
    match = url_pattern.search(url)
    if match:
        url = match.group(0)
    
    url = re.sub(r'[^\x00-\x7F]', '', url)
    url = url.rstrip('，。！？、；：""''（）【】《》,.;:!?()[]<>')
    
    return url


class ExtractRequest(BaseModel):
    url: str = None
    pid: str = None


@router.post("/extract/text")
def extract_text(request: ExtractRequest):
    """从视频链接提取文案"""
    raw_url = request.url or ""
    parsed_url = parse_video_url(raw_url)
    
    if not parsed_url:
        raise HTTPException(400, "无法解析视频链接")
    
    platform = detect_platform(parsed_url)
    print(platform)
    
    info = get_video_info(parsed_url)
    if not info:
        platform_name = SUPPORTED_PLATFORMS.get(platform, '未知')
        if _needs_cookie(platform) and not _has_cookie(platform):
            raise HTTPException(status_code=401, detail={
                "code": "COOKIE_REQUIRED",
                "platform": platform,
                "platform_name": platform_name,
                "message": f"{platform_name}需要登录才能采集，请先登录",
            })
        raise HTTPException(400, f"无法获取视频信息，平台: {platform_name}")

    rel_path, filename = download_video(parsed_url)
    print(rel_path, filename)
    if not rel_path:
        platform_name = SUPPORTED_PLATFORMS.get(platform, '未知')
        if _needs_cookie(platform) and not _has_cookie(platform):
            raise HTTPException(status_code=401, detail={
                "code": "COOKIE_REQUIRED",
                "platform": platform,
                "platform_name": platform_name,
                "message": f"{platform_name}需要登录才能下载，请先登录",
            })
        raise HTTPException(500, "下载视频失败")
    
    video_full_path = str(PROJECT_ROOT / rel_path)
    
    text_result = extract_video_text(video_full_path, use_whisper=True)
    
    if not text_result.get("success"):
        raise HTTPException(500, text_result.get("error", "提取文案失败"))
    
    content = clean_text(text_result.get("asr_text", ""))

    #这里要存库 项目id
    pid = request.pid or ""
    if pid:
        update_project(pid, {"input_text": content})
    
    return {"content": content, "word_count": len(content), "video_path": rel_path}


@router.post("/extract/info")
def extract_info(request: ExtractRequest):
    """获取视频信息（不下载）"""
    parsed_url = parse_video_url(request.url)
    
    if not parsed_url:
        raise HTTPException(400, "无法解析视频链接")
    
    platform = detect_platform(parsed_url)
    
    info = get_video_info(parsed_url)
    if not info:
        platform_name = SUPPORTED_PLATFORMS.get(platform, '未知')
        if _needs_cookie(platform) and not _has_cookie(platform):
            raise HTTPException(status_code=401, detail={
                "code": "COOKIE_REQUIRED",
                "platform": platform,
                "platform_name": platform_name,
                "message": f"{platform_name}需要登录才能获取信息，请先登录",
            })
        raise HTTPException(400, f"无法获取视频信息，平台: {platform_name}")
    
    return {
        "title": info.get("title", ""),
        "description": info.get("description", ""),
        "platform": platform,
        "platform_name": SUPPORTED_PLATFORMS.get(platform, "未知"),
        "thumbnail": info.get("thumbnail", ""),
        "duration": info.get("duration", 0),
        "view_count": info.get("view_count", 0),
        "like_count": info.get("like_count", 0),
        "uploader": info.get("uploader", ""),
    }


@router.post("/extract/text/clean")
def clean_text_api(request: dict):
    """清理文本（去除多余空格和特殊字符）"""
    text = request.get("text", "")
    return {"cleaned_text": clean_text(text)}


@router.get("/extract/platforms")
def list_platforms():
    """获取支持的平台列表"""
    return SUPPORTED_PLATFORMS