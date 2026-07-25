"""数据层 — 统一导出"""
from database.core import get_db, now, init_db
from database.projects import list_projects, get_project, create_project, update_project, delete_project
from database.voices import list_voices, get_voice, create_voice, delete_voice, rename_voice, set_default_voice, count_voices
from database.videos import list_videos, get_video, create_video, delete_video, rename_video, count_videos
from database.templates import list_templates, get_template, create_template, update_template, delete_template, count_templates
from database.brand_words import get_brand_words, add_brand_word, delete_brand_word

__all__ = [
    "get_db", "now", "init_db",
    "list_projects", "get_project", "create_project", "update_project", "delete_project",
    "list_voices", "get_voice", "create_voice", "delete_voice", "rename_voice", "set_default_voice", "count_voices",
    "list_videos", "get_video", "create_video", "delete_video", "rename_video", "count_videos",
    "list_templates", "get_template", "create_template", "update_template", "delete_template", "count_templates",
    "get_brand_words", "add_brand_word", "delete_brand_word",
]
