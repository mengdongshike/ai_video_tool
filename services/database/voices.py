"""音色数据操作"""
from pathlib import Path
from database.core import get_db, now

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # AI_video_tool/

def list_voices():
    conn = get_db()
    preset = conn.execute("SELECT * FROM voices WHERE is_default=1 ORDER BY id").fetchall()
    cloned = conn.execute("SELECT * FROM voices WHERE is_default=0 ORDER BY id").fetchall()
    conn.close()
    return {"preset": [dict(r) for r in preset], "cloned": [dict(r) for r in cloned]}

def get_voice(id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM voices WHERE id=?", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_voice(name: str, audio_path: str, profile_path: str = ""):
    t = now()
    conn = get_db()
    conn.execute("INSERT INTO voices (name, audio_path, profile_path, created_at) VALUES (?,?,?,?)", (name, audio_path, profile_path, t))
    conn.commit()
    vid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute("SELECT * FROM voices WHERE id=?", (vid,)).fetchone()
    conn.close()
    return dict(row)

def delete_voice(id: int):
    conn = get_db()
    row = conn.execute("SELECT audio_path FROM voices WHERE id=?", (id,)).fetchone()
    if row and row["audio_path"]:
        try:
            p = Path(row["audio_path"])
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            if p.is_file():
                p.unlink()
        except Exception as e:
            print(f">> Delete file failed: {e}", flush=True)
    conn.execute("DELETE FROM voices WHERE id=?", (id,))
    conn.commit()
    conn.close()

def rename_voice(id: int, new_name: str):
    conn = get_db()
    conn.execute("UPDATE voices SET name=? WHERE id=?", (new_name, id))
    conn.commit()
    conn.close()
    return get_voice(id)

def set_default_voice(id: int):
    conn = get_db()
    conn.execute("UPDATE voices SET is_default=0")
    conn.execute("UPDATE voices SET is_default=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()

def count_voices():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM voices").fetchone()[0]
    conn.close()
    return total
