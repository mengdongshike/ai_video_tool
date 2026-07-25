"""视频数据操作"""
from database.core import get_db, now

def list_videos():
    conn = get_db()
    rows = conn.execute("SELECT * FROM videos ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_video(id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM videos WHERE id=?", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_video(name: str, video_path: str):
    t = now()
    conn = get_db()
    conn.execute("INSERT INTO videos (name, video_path, created_at) VALUES (?,?,?)", (name, video_path, t))
    conn.commit()
    vid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
    conn.close()
    return dict(row)

def delete_video(id: int):
    conn = get_db()
    conn.execute("DELETE FROM videos WHERE id=?", (id,))
    conn.commit()
    conn.close()

def rename_video(id: int, name: str):
    conn = get_db()
    conn.execute("UPDATE videos SET name=? WHERE id=?", (name, id))
    conn.commit()
    conn.close()
    return get_video(id)

def count_videos():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    conn.close()
    return total
