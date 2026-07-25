"""模板数据操作"""
from database.core import get_db, now

def list_templates(type_filter=None):
    conn = get_db()
    if type_filter:
        rows = conn.execute("SELECT * FROM templates WHERE type=? ORDER BY id", (type_filter,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM templates ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_template(id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM templates WHERE id=?", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_template(name: str, type: str = "sub", file_path: str = ""):
    t = now()
    conn = get_db()
    conn.execute("INSERT INTO templates (name, type, file_path, created_at) VALUES (?,?,?,?)",
                 (name, type, file_path, t))
    conn.commit()
    vid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute("SELECT * FROM templates WHERE id=?", (vid,)).fetchone()
    conn.close()
    return dict(row)

def update_template(id: int, name: str):
    conn = get_db()
    conn.execute("UPDATE templates SET name=? WHERE id=?", (name, id))
    conn.commit()
    conn.close()
    return get_template(id)

def delete_template(id: int):
    conn = get_db()
    conn.execute("DELETE FROM templates WHERE id=?", (id,))
    conn.commit()
    conn.close()

def count_templates():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
    conn.close()
    return total
