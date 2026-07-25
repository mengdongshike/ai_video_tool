"""DB 连接与初始化"""
import sqlite3, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "app.db"

def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def now():
    return datetime.datetime.now().isoformat()

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '新项目',
            status TEXT NOT NULL DEFAULT 'draft',
            input_text TEXT, input_audio TEXT, input_video TEXT,
            output_audio TEXT, output_video TEXT, compose_video TEXT, output_text TEXT,
            voice_id INTEGER, template_id INTEGER,
            duration REAL, file_size INTEGER, error_message TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS voices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, audio_path TEXT,
            profile_path TEXT, is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS brand_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, type TEXT DEFAULT 'sub',
            file_path TEXT, preview_url TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, video_path TEXT,
            size_mb REAL, duration REAL, status TEXT DEFAULT 'ready',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS publish_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            account_name TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(platform, account_name)
        );
        CREATE TABLE IF NOT EXISTS publish_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            account_name TEXT NOT NULL,
            title TEXT,
            description TEXT,
            tags TEXT,
            video_path TEXT,
            cover_path TEXT,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            publish_url TEXT,
            scheduled_at TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

init_db()

# 兼容旧表：补充可能缺失的字段
for _col, _type in [
    ("srt_path", "TEXT"),
    ("cover_title", "TEXT"),
    ("cover_subtitle", "TEXT"),
    ("cover_path", "TEXT"),
    ("topic", "TEXT"),
    ("compose_video", "TEXT"),
]:
    try:
        conn = get_db()
        conn.execute(f"ALTER TABLE projects ADD COLUMN {_col} {_type}")
        conn.commit()
        conn.close()
    except:
        pass
