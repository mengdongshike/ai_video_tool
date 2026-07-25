"""项目数据操作"""
import uuid
from database.core import get_db, now

def list_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_project(id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_project(name: str):
    pid = uuid.uuid4().hex[:12]
    t = now()
    conn = get_db()
    conn.execute("INSERT INTO projects (id, name, created_at, updated_at) VALUES (?,?,?,?)", (pid, name, t, t))
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    return dict(row)

def update_project(id: str, data: dict):
    allowed = ["name","status","input_text","input_audio","input_video",
               "output_audio","output_video","compose_video","output_text","voice_id",
               "template_id","duration","file_size","error_message","srt_path",
               "cover_title","cover_subtitle","cover_path","topic"]
    sets = [f"{k}=?" for k in data if k in allowed]
    vals = [data[k] for k in data if k in allowed]
    if not sets: return get_project(id)
    sets.append("updated_at=?")
    vals.append(now())
    vals.append(id)
    conn = get_db()
    conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", vals)
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (id,)).fetchone()
    conn.close()
    return dict(row)

def delete_project(id: str):
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (id,))
    conn.commit()
    conn.close()
