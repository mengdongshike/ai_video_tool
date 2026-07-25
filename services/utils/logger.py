"""统一日志配置 — 同时输出到控制台和文件"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

_HANDLERS_INITED = False
_ch: logging.Handler = None
_fh: logging.Handler = None


def _init_handlers(level: int):
    global _HANDLERS_INITED, _ch, _fh
    if _HANDLERS_INITED:
        return

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _ch = logging.StreamHandler(stream=sys.stdout)
    _ch.setLevel(level)
    _ch.setFormatter(fmt)

    log_file = LOG_DIR / f"api_{datetime.now().strftime('%Y%m%d')}.log"
    _fh = RotatingFileHandler(str(log_file), maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
    _fh.setLevel(level)
    _fh.setFormatter(fmt)

    _HANDLERS_INITED = True


def setup_logger(name: str = "app", level: int = logging.INFO) -> logging.Logger:
    _init_handlers(level)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False          # 不依赖 root，防止被 uvicorn 覆盖
    logger.handlers.clear()           # 防止重复添加
    logger.addHandler(_ch)
    logger.addHandler(_fh)
    return logger


def get_logger(name: str = "app") -> logging.Logger:
    return setup_logger(name)
