"""视频下载工具 — 使用 yt-dlp 支持多平台"""
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from .platform import PLATFORM_REGISTRY, get_downloader


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "uploads" / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_PLATFORMS = {
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "bilibili": "哔哩哔哩",
    "youtube": "YouTube",
    "weibo": "微博",
    "tiktok": "TikTok",
    "qq": "QQ视频",
    "iqiyi": "爱奇艺",
    "youku": "优酷",
}


def detect_platform(url: str) -> str:
    """根据URL检测平台"""
    url_lower = url.lower()
    if re.search(r"(douyin|v\.douyin|抖音)", url_lower):
        return "douyin"
    elif re.search(r"(xiaohongshu|xhs|小红书)", url_lower):
        return "xiaohongshu"
    elif re.search(r"(bilibili|bili|bilibili\.com|哔哩哔哩)", url_lower):
        return "bilibili"
    elif re.search(r"(youtube|youtu\.be)", url_lower):
        return "youtube"
    elif re.search(r"(weibo|微博)", url_lower):
        return "weibo"
    elif re.search(r"(tiktok|vt\.tiktok)", url_lower):
        return "tiktok"
    elif re.search(r"(qq\.com|qqlive)", url_lower):
        return "qq"
    elif re.search(r"(iqiyi|爱奇艺)", url_lower):
        return "iqiyi"
    elif re.search(r"(youku|优酷)", url_lower):
        return "youku"
    return "unknown"


def get_video_info(url: str) -> Optional[Dict[str, Any]]:
    """获取视频元信息（标题、封面、时长、分辨率等）"""
    platform = detect_platform(url)
    
    if platform not in PLATFORM_REGISTRY:
        return None
    
    try:
        downloader = get_downloader(platform)
        return downloader.get_video_info(url)
    except Exception as e:
        return None


def download_video(url: str, format_id: Optional[str] = None, output_filename: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """下载视频，返回保存路径和文件名"""
    platform = detect_platform(url)
    
    if platform not in PLATFORM_REGISTRY:
        return None, None
    
    try:
        downloader = get_downloader(platform)
        return downloader.download_video(url, format_id, output_filename)
    except Exception as e:
        return None, None


def format_duration(seconds: int) -> str:
    """格式化时长为 HH:MM:SS"""
    if seconds <= 0:
        return "00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_size(bytes_size: int) -> str:
    """格式化文件大小"""
    if bytes_size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    size = bytes_size
    unit_idx = 0
    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024
        unit_idx += 1
    return f"{size:.2f} {units[unit_idx]}"
