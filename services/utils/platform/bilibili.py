import yt_dlp
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from .base import BasePlatformDownloader, sanitize_filename


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "uploads" / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


class BilibiliDownloader(BasePlatformDownloader):
    """哔哩哔哩下载器"""
    
    PLATFORM_NAME = "哔哩哔哩"
    PLATFORM_KEY = "bilibili"
    NEEDS_COOKIE = False
    
    def resolve_url(self, url: str) -> str:
        url = url.strip()
        if url.startswith("http"):
            return url
        return url
    
    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        url = self.resolve_url(url)
        
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": False,
                "extract_flat": False,
                "skip_download": True,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            
            self.apply_cookie(ydl_opts)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                formats = []
                for fmt in info.get("formats", []):
                    if fmt.get("vcodec") != "none":
                        has_audio = fmt.get("acodec") != "none"
                        formats.append({
                            "format_id": fmt.get("format_id", ""),
                            "resolution": fmt.get("resolution", ""),
                            "height": fmt.get("height", 0),
                            "width": fmt.get("width", 0),
                            "fps": fmt.get("fps", 0),
                            "vcodec": fmt.get("vcodec", ""),
                            "acodec": fmt.get("acodec", ""),
                            "has_audio": has_audio,
                            "ext": fmt.get("ext", ""),
                            "size": fmt.get("filesize", 0),
                            "tbr": fmt.get("tbr", 0),
                        })
                
                formats.sort(key=lambda x: (x["height"] or 0, x["tbr"] or 0), reverse=True)
                
                return {
                    "title": info.get("title", ""),
                    "uploader": info.get("uploader", ""),
                    "upload_date": info.get("upload_date", ""),
                    "duration": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                    "like_count": info.get("like_count", 0),
                    "comment_count": info.get("comment_count", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "description": info.get("description", ""),
                    "platform": self.PLATFORM_KEY,
                    "platform_name": self.PLATFORM_NAME,
                    "formats": formats,
                }
        
        except Exception as e:
            print(f"[Bilibili] get_video_info error: {e}")
            return None
    
    def download_video(self, url: str, format_id: Optional[str] = None, 
                      output_filename: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        url = self.resolve_url(url)
        
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,
                "extract_flat": False,
                "merge_output_format": "mp4",
                "postprocessors": [],
                "retries": 3,
                "fragment_retries": 3,
                "skip_unavailable_fragments": True,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            
            self.apply_cookie(ydl_opts)
            temp_dir = tempfile.mkdtemp(dir=str(DOWNLOAD_DIR))
            safe_name = output_filename or "video"
            safe_name = sanitize_filename(safe_name)
            
            ydl_opts["outtmpl"] = os.path.join(temp_dir, f"{safe_name}.%(ext)s")
            
            if format_id:
                ydl_opts["format"] = format_id
            else:
                ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if not info:
                    return None, None
                
                video_path = None
                for fmt in info.get("formats", []):
                    if "filepath" in fmt:
                        video_path = fmt["filepath"]
                        break
                
                if not video_path:
                    possible_files = list(Path(temp_dir).glob(f"{safe_name}.*"))
                    if possible_files:
                        video_path = str(possible_files[0])
                
                if not video_path or not os.path.exists(video_path):
                    return None, None
                
                final_name = sanitize_filename(info.get("title", safe_name))
                final_ext = Path(video_path).suffix
                final_path = DOWNLOAD_DIR / f"{final_name}{final_ext}"
                
                if final_path.exists():
                    counter = 1
                    while final_path.exists():
                        final_path = DOWNLOAD_DIR / f"{final_name}_{counter}{final_ext}"
                        counter += 1
                
                shutil.move(video_path, str(final_path))
                
                for f in Path(temp_dir).glob("*"):
                    try:
                        f.unlink()
                    except:
                        pass
                try:
                    os.rmdir(temp_dir)
                except:
                    pass
                
                rel_path = f"uploads/downloads/{final_path.name}"
                return rel_path, final_path.name
        
        except Exception as e:
            return None, None
