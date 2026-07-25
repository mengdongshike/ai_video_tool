from .base import BasePlatformDownloader
from .bilibili import BilibiliDownloader
from .douyin import DouyinDownloader
from .xiaohongshu import XiaohongshuDownloader


PLATFORM_REGISTRY = {
    "bilibili": BilibiliDownloader,
    "douyin": DouyinDownloader,
    "xiaohongshu": XiaohongshuDownloader,
}


def get_downloader(platform_key: str) -> BasePlatformDownloader:
    """根据平台key获取对应的下载器实例"""
    downloader_class = PLATFORM_REGISTRY.get(platform_key)
    if downloader_class:
        return downloader_class()
    raise ValueError(f"不支持的平台: {platform_key}")
