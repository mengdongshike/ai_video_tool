import os
import re
import json
import shutil
import requests
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from .base import BasePlatformDownloader, sanitize_filename


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "uploads" / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

MOBILE_UA = "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _extract_video_id(url: str) -> Optional[str]:
    """从各种抖音 URL 格式中提取视频 ID"""
    patterns = [
        r"/share/video/(\d+)",
        r"/video/(\d+)",
        r"[?&]modal_id=(\d+)",
        r"[?&]aweme_id=(\d+)",
        r"/(\d{15,})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def _find_aweme_detail(obj: Any, depth: int = 0) -> Optional[dict]:
    """递归搜索 _ROUTER_DATA 里的 aweme_detail"""
    if depth > 15:
        return None
    if isinstance(obj, dict):
        if "aweme_detail" in obj:
            return obj["aweme_detail"]
        if "video" in obj and "desc" in obj and "aweme_id" in obj:
            return obj
        for v in obj.values():
            result = _find_aweme_detail(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_aweme_detail(item, depth + 1)
            if result:
                return result
    return None


class DouyinDownloader(BasePlatformDownloader):
    """抖音下载器 — 直接解析 iesdouyin 分享页，不需要 cookie"""

    PLATFORM_NAME = "抖音"
    PLATFORM_KEY = "douyin"
    NEEDS_COOKIE = False

    def resolve_url(self, url: str) -> str:
        url = url.strip()

        if not url.startswith("http"):
            match = re.search(r"(https?://[^\s]+)", url)
            if match:
                url = match.group(1)
            else:
                return url

        video_id = _extract_video_id(url)
        if video_id:
            return f"https://www.iesdouyin.com/share/video/{video_id}/"

        if "v.douyin.com" in url:
            try:
                response = requests.get(
                    url,
                    headers={"User-Agent": DESKTOP_UA},
                    allow_redirects=True,
                    timeout=30,
                )
                vid = _extract_video_id(response.url)
                if vid:
                    return f"https://www.iesdouyin.com/share/video/{vid}/"
                return response.url
            except:
                return url

        return url

    def _fetch_detail(self, url: str) -> Optional[dict]:
        """从 iesdouyin 分享页获取视频详情"""
        share_url = self.resolve_url(url)
        try:
            r = requests.get(
                share_url,
                headers={
                    "User-Agent": MOBILE_UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
                timeout=15,
            )
            r.raise_for_status()
            html = r.text

            m = re.search(r"window\._ROUTER_DATA\s*=\s*(\{.+?\})\s*</script>", html, re.DOTALL)
            if not m:
                print("[Douyin] 未找到 _ROUTER_DATA")
                return None

            data = json.loads(m.group(1))
            detail = _find_aweme_detail(data)
            if not detail:
                print("[Douyin] _ROUTER_DATA 中未找到视频详情")
                return None

            return detail
        except Exception as e:
            print(f"[Douyin] 获取视频详情失败: {e}")
            return None

    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        detail = self._fetch_detail(url)
        if not detail:
            return None

        author = detail.get("author", {})
        stats = detail.get("statistics", {})
        video = detail.get("video", {})
        play_addr = video.get("play_addr", {})
        urls = play_addr.get("url_list", [])

        return {
            "title": detail.get("desc", ""),
            "uploader": author.get("nickname", ""),
            "duration": video.get("duration", 0),
            "view_count": stats.get("play_count", 0),
            "like_count": stats.get("digg_count", 0),
            "comment_count": stats.get("comment_count", 0),
            "thumbnail": "",
            "description": detail.get("desc", ""),
            "platform": self.PLATFORM_KEY,
            "platform_name": self.PLATFORM_NAME,
            "formats": [],
        }

    def download_video(self, url: str, format_id: Optional[str] = None,
                       output_filename: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        detail = self._fetch_detail(url)
        if not detail:
            return None, None

        video = detail.get("video", {})
        play_addr = video.get("play_addr", {})
        urls = play_addr.get("url_list", [])
        if not urls:
            print("[Douyin] 未找到视频下载地址")
            return None, None

        download_url = urls[0].replace("playwm", "play")

        title = detail.get("desc", "") or output_filename or "video"
        safe_name = sanitize_filename(title)
        final_path = DOWNLOAD_DIR / f"{safe_name}.mp4"

        if final_path.exists():
            counter = 1
            while final_path.exists():
                final_path = DOWNLOAD_DIR / f"{safe_name}_{counter}.mp4"
                counter += 1

        try:
            print(f"[Douyin] 开始下载: {download_url[:100]}")
            r = requests.get(
                download_url,
                headers={
                    "User-Agent": MOBILE_UA,
                    "Referer": "https://www.iesdouyin.com/",
                },
                stream=True,
                timeout=60,
            )
            r.raise_for_status()

            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(final_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

            print(f"[Douyin] 下载完成: {final_path.name} ({downloaded // 1024}KB)")

            rel_path = f"uploads/downloads/{final_path.name}"
            return rel_path, final_path.name

        except Exception as e:
            print(f"[Douyin] 下载失败: {e}")
            if final_path.exists():
                try:
                    final_path.unlink()
                except:
                    pass
            return None, None
