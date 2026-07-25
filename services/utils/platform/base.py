import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple, Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
COOKIE_DIR = PROJECT_ROOT / "profiles"


def sanitize_filename(filename: str) -> str:
    # 1. Windows 非法字符
    result = re.sub(r'[\\/:*?"<>|\r\n\t]', "", filename)
    # 2. emoji 和各种特殊符号（保留中文、字母、数字、常见标点）
    result = re.sub(
        r'[\U0001F000-\U0001FFFF\U00002600-\U000027BF\U0001F900-\U0001F9FF'
        r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U0000FE00-\U0000FE0F'
        r'\U00002B00-\U00002BFF\U0000200B-\U0000200F]',
        "", result)
    # 3. 话题标签 #、@ 提及
    result = re.sub(r'[@#]', "", result)
    # 4. 各种括号替换为空格（如【xxx】《xxx》）
    result = re.sub(r'[【】《》「」『』\[\]]', " ", result)
    # 5. 多余空白
    result = re.sub(r'\s+', " ", result).strip()
    # 6. Windows 保留名
    reserved_names = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                       "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
                       "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if result.upper() in reserved_names:
        result = f"{result}_"
    return result[:200] or "video"


class BasePlatformDownloader(ABC):
    """平台下载器抽象基类"""

    PLATFORM_NAME = ""
    PLATFORM_KEY = ""
    NEEDS_COOKIE = True

    def __init__(self):
        pass

    def get_cookie_file(self) -> Optional[str]:
        """返回当前平台的 Netscape cookie 文件路径（若存在）。
        路径固定为 ~/.hermes/cookies/{platform_key}.txt
        """
        if not self.PLATFORM_KEY:
            return None
        cf = COOKIE_DIR / f"{self.PLATFORM_KEY}.txt"
        if cf.exists():
            return str(cf)
        return None

    def apply_cookie(self, ydl_opts: dict) -> dict:
        """若 cookie 文件存在，注入到 yt-dlp 配置。返回原 ydl_opts。"""
        cf = self.get_cookie_file()
        if cf:
            ydl_opts["cookiefile"] = cf
        return ydl_opts

    @abstractmethod
    def resolve_url(self, url: str) -> str:
        """解析分享链接，返回真实视频页面URL"""
        pass

    @abstractmethod
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """获取视频元信息"""
        pass

    @abstractmethod
    def download_video(self, url: str, format_id: Optional[str] = None,
                      output_filename: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """下载视频，返回保存路径和文件名"""
        pass
