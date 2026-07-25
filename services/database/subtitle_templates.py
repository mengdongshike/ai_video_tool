"""字幕模板数据操作"""
from database.core import get_db, now

def init_subtitle_templates_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subtitle_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            font_name TEXT NOT NULL,
            font_size INTEGER DEFAULT 40,
            font_color TEXT DEFAULT '#FFFFFF',
            border_color TEXT DEFAULT '#000000',
            border_width INTEGER DEFAULT 2,
            shadow_color TEXT DEFAULT '#000000',
            shadow_x INTEGER DEFAULT 2,
            shadow_y INTEGER DEFAULT 2,
            margin_bottom INTEGER DEFAULT 50,
            alignment TEXT DEFAULT 'center',
            background_color TEXT DEFAULT '',
            background_padding INTEGER DEFAULT 0,
            effect_type TEXT DEFAULT 'none',
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    try:
        conn.execute("ALTER TABLE subtitle_templates ADD COLUMN effect_type TEXT DEFAULT 'none'")
    except:
        pass
    conn.commit()
    conn.close()

def insert_default_templates():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM subtitle_templates").fetchone()[0]
    if count == 0:
        t = now()
        default_templates = [
            {
                "name": "标准白底黑边",
                "font_name": "SourceHanSansSC-Regular-2",
                "font_size": 40,
                "font_color": "#FFFFFF",
                "border_color": "#000000",
                "border_width": 2,
                "shadow_color": "#000000",
                "shadow_x": 2,
                "shadow_y": 2,
                "margin_bottom": 50,
                "alignment": "center",
                "background_color": "",
                "background_padding": 0,
                "is_default": 1,
            },
            {
                "name": "高亮黄底",
                "font_name": "SourceHanSansSC-Regular-2",
                "font_size": 44,
                "font_color": "#FFFF00",
                "border_color": "#000000",
                "border_width": 3,
                "shadow_color": "#000000",
                "shadow_x": 3,
                "shadow_y": 3,
                "margin_bottom": 80,
                "alignment": "center",
                "background_color": "",
                "background_padding": 0,
                "is_default": 0,
            },
            {
                "name": "粉色温馨",
                "font_name": "ZhanKuQingKeHuangYouTi-2",
                "font_size": 36,
                "font_color": "#FF69B4",
                "border_color": "#FFFFFF",
                "border_width": 2,
                "shadow_color": "#FF1493",
                "shadow_x": 2,
                "shadow_y": 2,
                "margin_bottom": 60,
                "alignment": "center",
                "background_color": "",
                "background_padding": 0,
                "is_default": 0,
            },
            {
                "name": "书法艺术",
                "font_name": "gkai00mp-2",
                "font_size": 48,
                "font_color": "#333333",
                "border_color": "#FFFFFF",
                "border_width": 2,
                "shadow_color": "#CCCCCC",
                "shadow_x": 1,
                "shadow_y": 1,
                "margin_bottom": 50,
                "alignment": "center",
                "background_color": "",
                "background_padding": 0,
                "is_default": 0,
            },
            {
                "name": "带背景框",
                "font_name": "SourceHanSansSC-Regular-2",
                "font_size": 38,
                "font_color": "#FFFFFF",
                "border_color": "#000000",
                "border_width": 1,
                "shadow_color": "#000000",
                "shadow_x": 0,
                "shadow_y": 0,
                "margin_bottom": 50,
                "alignment": "center",
                "background_color": "#00000080",
                "background_padding": 8,
                "is_default": 0,
            },
            {
                "name": "左侧对齐",
                "font_name": "SourceHanSansSC-Regular-2",
                "font_size": 36,
                "font_color": "#FFFFFF",
                "border_color": "#000000",
                "border_width": 2,
                "shadow_color": "#000000",
                "shadow_x": 2,
                "shadow_y": 2,
                "margin_bottom": 50,
                "alignment": "left",
                "background_color": "",
                "background_padding": 0,
                "is_default": 0,
            },
        ]
        for tmpl in default_templates:
            conn.execute("""
                INSERT INTO subtitle_templates 
                (name, font_name, font_size, font_color, border_color, border_width,
                 shadow_color, shadow_x, shadow_y, margin_bottom, alignment,
                 background_color, background_padding, is_default, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                tmpl["name"], tmpl["font_name"], tmpl["font_size"], tmpl["font_color"],
                tmpl["border_color"], tmpl["border_width"], tmpl["shadow_color"],
                tmpl["shadow_x"], tmpl["shadow_y"], tmpl["margin_bottom"], tmpl["alignment"],
                tmpl["background_color"], tmpl["background_padding"], tmpl["is_default"], t, t
            ))
        conn.commit()
    conn.close()

init_subtitle_templates_table()
insert_default_templates()

def list_subtitle_templates():
    conn = get_db()
    rows = conn.execute("SELECT * FROM subtitle_templates ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_subtitle_template(id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM subtitle_templates WHERE id=?", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_subtitle_template(data: dict):
    t = now()
    conn = get_db()
    conn.execute("""
        INSERT INTO subtitle_templates 
        (name, font_name, font_size, font_color, border_color, border_width,
         shadow_color, shadow_x, shadow_y, margin_bottom, alignment,
         background_color, background_padding, effect_type, is_default, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("name", ""),
        data.get("font_name", "SourceHanSansSC-Regular-2"),
        data.get("font_size", 40),
        data.get("font_color", "#FFFFFF"),
        data.get("border_color", "#000000"),
        data.get("border_width", 2),
        data.get("shadow_color", "#000000"),
        data.get("shadow_x", 2),
        data.get("shadow_y", 2),
        data.get("margin_bottom", 50),
        data.get("alignment", "center"),
        data.get("background_color", ""),
        data.get("background_padding", 0),
        data.get("effect_type", "none"),
        data.get("is_default", 0),
        t, t
    ))
    conn.commit()
    vid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute("SELECT * FROM subtitle_templates WHERE id=?", (vid,)).fetchone()
    conn.close()
    return dict(row)

def update_subtitle_template(id: int, data: dict):
    t = now()
    conn = get_db()
    conn.execute("""
        UPDATE subtitle_templates SET 
        name=?, font_name=?, font_size=?, font_color=?, border_color=?, border_width=?,
        shadow_color=?, shadow_x=?, shadow_y=?, margin_bottom=?, alignment=?,
        background_color=?, background_padding=?, effect_type=?, is_default=?, updated_at=?
        WHERE id=?
    """, (
        data.get("name", ""),
        data.get("font_name", "SourceHanSansSC-Regular-2"),
        data.get("font_size", 40),
        data.get("font_color", "#FFFFFF"),
        data.get("border_color", "#000000"),
        data.get("border_width", 2),
        data.get("shadow_color", "#000000"),
        data.get("shadow_x", 2),
        data.get("shadow_y", 2),
        data.get("margin_bottom", 50),
        data.get("alignment", "center"),
        data.get("background_color", ""),
        data.get("background_padding", 0),
        data.get("effect_type", "none"),
        data.get("is_default", 0),
        t, id
    ))
    conn.commit()
    conn.close()
    return get_subtitle_template(id)

def delete_subtitle_template(id: int):
    conn = get_db()
    conn.execute("DELETE FROM subtitle_templates WHERE id=?", (id,))
    conn.commit()
    conn.close()

def get_default_template():
    conn = get_db()
    row = conn.execute("SELECT * FROM subtitle_templates WHERE is_default=1").fetchone()
    if row:
        conn.close()
        return dict(row)
    rows = conn.execute("SELECT * FROM subtitle_templates ORDER BY id LIMIT 1").fetchone()
    conn.close()
    return dict(rows) if rows else None

def count_subtitle_templates():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM subtitle_templates").fetchone()[0]
    conn.close()
    return total
