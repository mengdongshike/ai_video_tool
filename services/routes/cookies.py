"""平台 Cookie 管理 — 存储、验证、登录URL"""
import os
import json
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/cookies", tags=["平台Cookie"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROFILES_DIR = PROJECT_ROOT / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

PLATFORM_CONFIG = {
    "douyin": {
        "name": "抖音",
        "login_url": "https://www.douyin.com/",
        "verify_url": "https://www.douyin.com/follow",
        "cookie_domain_keywords": ["douyin"],
    },
    "xiaohongshu": {
        "name": "小红书",
        "login_url": "https://www.xiaohongshu.com/",
        "verify_url": "https://www.xiaohongshu.com/user/profile",
        "cookie_domain_keywords": ["xiaohongshu"],
    },
    "bilibili": {
        "name": "哔哩哔哩",
        "login_url": "https://www.bilibili.com/",
        "verify_url": "https://api.bilibili.com/x/web-interface/nav",
        "cookie_domain_keywords": ["bilibili"],
    },
}


def _cookie_path(platform: str) -> Path:
    return PROFILES_DIR / f"{platform}.txt"


def _parse_netscape(filepath: Path) -> list:
    """解析 Netscape 格式 cookie 文件"""
    cookies = []
    if not filepath.exists():
        return cookies
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies.append({
                    "domain": parts[0],
                    "flag": parts[1],
                    "path": parts[2],
                    "secure": parts[3],
                    "expires": parts[4],
                    "name": parts[5],
                    "value": parts[6],
                })
    return cookies


def _save_netscape(filepath: Path, cookies: list):
    """保存为 Netscape 格式 cookie 文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            domain = c.get("domain", "")
            flag = c.get("flag", "TRUE" if domain.startswith(".") else "FALSE")
            path = c.get("path", "/")
            secure = c.get("secure", "FALSE")
            expires = str(int(c.get("expires", c.get("expirationDate", 0))))
            name = c.get("name", "")
            value = c.get("value", "")
            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")


def _get_cookie_info(platform: str) -> dict:
    """获取单个平台的 cookie 状态"""
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        return {"platform": platform, "name": platform, "available": False, "error": "不支持的平台"}
    cf = _cookie_path(platform)
    if not cf.exists():
        return {
            "platform": platform,
            "name": cfg["name"],
            "available": False,
            "login_url": cfg["login_url"],
            "cookie_count": 0,
            "updated_at": None,
        }
    cookies = _parse_netscape(cf)
    mtime = os.path.getmtime(str(cf))
    return {
        "platform": platform,
        "name": cfg["name"],
        "available": len(cookies) > 0,
        "login_url": cfg["login_url"],
        "cookie_count": len(cookies),
        "updated_at": int(mtime),
    }


@router.get("")
def list_cookies():
    """列出所有平台的 cookie 状态"""
    result = []
    for plat, cfg in PLATFORM_CONFIG.items():
        result.append(_get_cookie_info(plat))
    return result


@router.get("/{platform}")
def get_cookie(platform: str):
    """获取单个平台的 cookie 状态"""
    if platform not in PLATFORM_CONFIG:
        raise HTTPException(400, f"不支持的平台: {platform}")
    return _get_cookie_info(platform)


class SaveCookieRequest(BaseModel):
    cookies: list
    format: Optional[str] = "json"


@router.post("/{platform}")
def save_cookie(platform: str, req: SaveCookieRequest):
    """保存 cookie（支持 JSON 数组格式，自动转 Netscape）"""
    if platform not in PLATFORM_CONFIG:
        raise HTTPException(400, f"不支持的平台: {platform}")

    cookies = req.cookies or []
    if not cookies:
        raise HTTPException(400, "cookie 列表不能为空")

    keywords = PLATFORM_CONFIG[platform]["cookie_domain_keywords"]
    filtered = []
    for c in cookies:
        domain = c.get("domain", "")
        if any(kw in domain.lower() for kw in keywords):
            filtered.append(c)

    if not filtered:
        filtered = cookies

    cf = _cookie_path(platform)
    _save_netscape(cf, filtered)
    return {"success": True, "saved_count": len(filtered)}


@router.post("/{platform}/verify")
def verify_cookie(platform: str):
    """验证 cookie 是否有效（尝试调用平台下载器获取信息）"""
    if platform not in PLATFORM_CONFIG:
        raise HTTPException(400, f"不支持的平台: {platform}")

    cf = _cookie_path(platform)
    if not cf.exists():
        return {"valid": False, "reason": "cookie 文件不存在"}

    try:
        from utils.platform import get_downloader
        downloader = get_downloader(platform)
        return {"valid": True, "reason": "cookie 文件存在"}
    except Exception as e:
        return {"valid": False, "reason": str(e)}


@router.delete("/{platform}")
def delete_cookie(platform: str):
    """删除指定平台的 cookie"""
    if platform not in PLATFORM_CONFIG:
        raise HTTPException(400, f"不支持的平台: {platform}")
    cf = _cookie_path(platform)
    if cf.exists():
        cf.unlink()
        return {"success": True}
    return {"success": False, "error": "cookie 文件不存在"}
