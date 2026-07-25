"""发布账号与记录管理"""
from pathlib import Path
from .core import get_db, now


def list_accounts(platform: str | None = None):
    conn = get_db()
    try:
        if platform:
            rows = conn.execute(
                "SELECT * FROM publish_accounts WHERE platform = ? ORDER BY created_at DESC",
                (platform,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM publish_accounts ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_account(account_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM publish_accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_account(platform: str, account_name: str, status: str = "pending", error_message: str | None = None):
    conn = get_db()
    try:
        now_str = now()
        cur = conn.execute(
            "INSERT OR REPLACE INTO publish_accounts (platform, account_name, status, error_message, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (platform, account_name, status, error_message, now_str, now_str)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_account_status(account_id: int, status: str, error_message: str | None = None):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE publish_accounts SET status = ?, error_message = ?, updated_at = ? WHERE id = ?",
            (status, error_message, now(), account_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_account(account_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM publish_accounts WHERE id = ?", (account_id,))
        conn.commit()
    finally:
        conn.close()


def list_records(project_id: str | None = None):
    conn = get_db()
    try:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM publish_records WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM publish_records ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_record(data: dict):
    conn = get_db()
    try:
        now_str = now()
        cur = conn.execute(
            """INSERT INTO publish_records 
               (project_id, platform, account_name, title, description, tags, 
                video_path, cover_path, status, error_message, publish_url, scheduled_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("project_id"),
                data.get("platform"),
                data.get("account_name"),
                data.get("title"),
                data.get("description"),
                data.get("tags"),
                data.get("video_path"),
                data.get("cover_path"),
                data.get("status", "pending"),
                data.get("error_message"),
                data.get("publish_url"),
                data.get("scheduled_at"),
                now_str,
                now_str,
            )
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_record(record_id: int, data: dict):
    conn = get_db()
    try:
        sets = []
        vals = []
        for k, v in data.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        sets.append("updated_at = ?")
        vals.append(now())
        vals.append(record_id)
        conn.execute(
            f"UPDATE publish_records SET {', '.join(sets)} WHERE id = ?",
            vals
        )
        conn.commit()
    finally:
        conn.close()
