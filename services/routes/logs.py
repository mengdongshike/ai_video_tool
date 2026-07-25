"""日志查看路由"""
from fastapi import APIRouter, HTTPException
from pathlib import Path
from utils.logger import LOG_DIR

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def list_logs():
    """获取日志文件列表"""
    if not LOG_DIR.exists():
        return []
    files = []
    for f in sorted(LOG_DIR.glob("*.log"), reverse=True):
        files.append({
            "name": f.name,
            "size": f.stat().st_size,
            "mtime": f.stat().st_mtime,
        })
    return files


@router.get("/{filename}")
def get_log(filename: str, lines: int = 200, level: str = ""):
    """读取日志文件内容（最后 N 行）
    
    - lines: 返回最后多少行
    - level: 按级别过滤（空不过滤），如 ERROR/WARNING/INFO
    """
    log_file = LOG_DIR / filename
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {e}")

    # 取最后 N 行
    if lines > 0:
        all_lines = all_lines[-lines:]

    # 按级别过滤
    if level:
        level = level.upper()
        all_lines = [l for l in all_lines if f"[{level}]" in l]

    return {
        "filename": filename,
        "total_lines": len(all_lines),
        "content": "".join(all_lines),
    }
