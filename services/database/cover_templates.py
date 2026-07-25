"""封面模板数据操作"""
from database.core import get_db, now

def init_cover_templates_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cover_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            layout_type TEXT DEFAULT 'center',
            title_font_name TEXT NOT NULL,
            title_font_size INTEGER DEFAULT 72,
            title_color TEXT DEFAULT '#FFFFFF',
            title_border_color TEXT DEFAULT '#000000',
            title_border_width INTEGER DEFAULT 2,
            title_shadow_color TEXT DEFAULT '#000000',
            title_shadow_x INTEGER DEFAULT 3,
            title_shadow_y INTEGER DEFAULT 3,
            title_alignment TEXT DEFAULT 'center',
            title_position_x REAL DEFAULT 0.5,
            title_position_y REAL DEFAULT 0.4,
            subtitle_font_name TEXT DEFAULT 'SourceHanSansSC-Regular-2',
            subtitle_font_size INTEGER DEFAULT 36,
            subtitle_color TEXT DEFAULT '#CCCCCC',
            subtitle_border_color TEXT DEFAULT '#000000',
            subtitle_border_width INTEGER DEFAULT 1,
            subtitle_shadow_color TEXT DEFAULT '#000000',
            subtitle_shadow_x INTEGER DEFAULT 2,
            subtitle_shadow_y INTEGER DEFAULT 2,
            subtitle_alignment TEXT DEFAULT 'center',
            subtitle_position_x REAL DEFAULT 0.5,
            subtitle_position_y REAL DEFAULT 0.55,
            background_color TEXT DEFAULT '',
            overlay_color TEXT DEFAULT '',
            overlay_opacity REAL DEFAULT 0.5,
            icon_path TEXT DEFAULT '',
            icon_position TEXT DEFAULT 'top-left',
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    # 兼容旧数据库：添加 position_x 字段（如果不存在）
    try:
        conn.execute("ALTER TABLE cover_templates ADD COLUMN title_position_x REAL DEFAULT 0.5")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE cover_templates ADD COLUMN subtitle_position_x REAL DEFAULT 0.5")
    except Exception:
        pass
    conn.commit()
    conn.close()

def insert_default_templates():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM cover_templates").fetchone()[0]
    if count == 0 or (count > 0 and count < 10):
        conn.execute("DELETE FROM cover_templates")
        t = now()
        default_templates = [
            {
                "name": "居中白字",
                "layout_type": "center",
                "title_font_name": "SourceHanSansSC-Regular-2",
                "title_font_size": 72,
                "title_color": "#FFFFFF",
                "title_border_color": "#000000",
                "title_border_width": 2,
                "title_shadow_color": "#000000",
                "title_shadow_x": 3,
                "title_shadow_y": 3,
                "title_alignment": "center",
                "title_position_y": 0.4,
                "subtitle_font_name": "SourceHanSansSC-Regular-2",
                "subtitle_font_size": 36,
                "subtitle_color": "#CCCCCC",
                "subtitle_border_color": "#000000",
                "subtitle_border_width": 1,
                "subtitle_shadow_color": "#000000",
                "subtitle_shadow_x": 2,
                "subtitle_shadow_y": 2,
                "subtitle_alignment": "center",
                "subtitle_position_y": 0.55,
                "overlay_color": "#000000",
                "overlay_opacity": 0.4,
                "is_default": 1,
            },
            {
                "name": "竖排左列",
                "layout_type": "left-vertical",
                "title_font_name": "gkai00mp-2",
                "title_font_size": 56,
                "title_color": "#FFFFFF",
                "title_border_color": "#000000",
                "title_border_width": 3,
                "title_shadow_color": "#000000",
                "title_shadow_x": 2,
                "title_shadow_y": 2,
                "title_alignment": "left",
                "title_position_y": 0.5,
                "subtitle_font_name": "gkai00mp-2",
                "subtitle_font_size": 24,
                "subtitle_color": "#EEEEEE",
                "subtitle_border_color": "#000000",
                "subtitle_border_width": 1,
                "subtitle_shadow_color": "#000000",
                "subtitle_shadow_x": 1,
                "subtitle_shadow_y": 1,
                "subtitle_alignment": "left",
                "subtitle_position_y": 0.75,
                "overlay_color": "#1a1a2e",
                "overlay_opacity": 0.6,
                "is_default": 0,
            },
            {
                "name": "竖排右列",
                "layout_type": "right-vertical",
                "title_font_name": "LXGWHeartSerifCHS-2",
                "title_font_size": 52,
                "title_color": "#FFD700",
                "title_border_color": "#8B4513",
                "title_border_width": 2,
                "title_shadow_color": "#FF4500",
                "title_shadow_x": 3,
                "title_shadow_y": 3,
                "title_alignment": "right",
                "title_position_y": 0.5,
                "subtitle_font_name": "SourceHanSansSC-Regular-2",
                "subtitle_font_size": 28,
                "subtitle_color": "#FFA500",
                "subtitle_border_color": "#8B4513",
                "subtitle_border_width": 1,
                "subtitle_shadow_color": "#FF4500",
                "subtitle_shadow_x": 2,
                "subtitle_shadow_y": 2,
                "subtitle_alignment": "right",
                "subtitle_position_y": 0.75,
                "overlay_color": "#8B0000",
                "overlay_opacity": 0.5,
                "is_default": 0,
            },
            {
                "name": "底部横排",
                "layout_type": "bottom-horizontal",
                "title_font_name": "ZhanKuQingKeHuangYouTi-2",
                "title_font_size": 64,
                "title_color": "#FF69B4",
                "title_border_color": "#FFFFFF",
                "title_border_width": 3,
                "title_shadow_color": "#FF1493",
                "title_shadow_x": 4,
                "title_shadow_y": 4,
                "title_alignment": "center",
                "title_position_y": 0.7,
                "subtitle_font_name": "ZhanKuQingKeHuangYouTi-2",
                "subtitle_font_size": 32,
                "subtitle_color": "#FFB6C1",
                "subtitle_border_color": "#FFFFFF",
                "subtitle_border_width": 1,
                "subtitle_shadow_color": "#FF1493",
                "subtitle_shadow_x": 2,
                "subtitle_shadow_y": 2,
                "subtitle_alignment": "center",
                "subtitle_position_y": 0.85,
                "overlay_color": "#FFB6C1",
                "overlay_opacity": 0.3,
                "is_default": 0,
            },
            {
                "name": "顶部横排",
                "layout_type": "top-horizontal",
                "title_font_name": "Slidefu-Regular",
                "title_font_size": 58,
                "title_color": "#00D4FF",
                "title_border_color": "#0066CC",
                "title_border_width": 2,
                "title_shadow_color": "#0066CC",
                "title_shadow_x": 3,
                "title_shadow_y": 3,
                "title_alignment": "center",
                "title_position_y": 0.15,
                "subtitle_font_name": "SourceHanSansSC-Regular-2",
                "subtitle_font_size": 28,
                "subtitle_color": "#66B2FF",
                "subtitle_border_color": "#0066CC",
                "subtitle_border_width": 1,
                "subtitle_shadow_color": "#0066CC",
                "subtitle_shadow_x": 2,
                "subtitle_shadow_y": 2,
                "subtitle_alignment": "center",
                "subtitle_position_y": 0.28,
                "overlay_color": "#000033",
                "overlay_opacity": 0.5,
                "is_default": 0,
            },
            {
                "name": "左侧横排",
                "layout_type": "left-horizontal",
                "title_font_name": "ZhanKuXiaoLOGOTi-2",
                "title_font_size": 60,
                "title_color": "#FFFFFF",
                "title_border_color": "#000000",
                "title_border_width": 2,
                "title_shadow_color": "#000000",
                "title_shadow_x": 3,
                "title_shadow_y": 3,
                "title_alignment": "left",
                "title_position_y": 0.5,
                "subtitle_font_name": "SourceHanSansSC-Regular-2",
                "subtitle_font_size": 30,
                "subtitle_color": "#CCCCCC",
                "subtitle_border_color": "#000000",
                "subtitle_border_width": 1,
                "subtitle_shadow_color": "#000000",
                "subtitle_shadow_x": 2,
                "subtitle_shadow_y": 2,
                "subtitle_alignment": "left",
                "subtitle_position_y": 0.62,
                "overlay_color": "#222222",
                "overlay_opacity": 0.5,
                "is_default": 0,
            },
            {
                "name": "右侧横排",
                "layout_type": "right-horizontal",
                "title_font_name": "ZiTiQuanXinYiGuanHeiTi4.0-2",
                "title_font_size": 56,
                "title_color": "#FFFF00",
                "title_border_color": "#000000",
                "title_border_width": 3,
                "title_shadow_color": "#FF4500",
                "title_shadow_x": 4,
                "title_shadow_y": 4,
                "title_alignment": "right",
                "title_position_y": 0.5,
                "subtitle_font_name": "SourceHanSansSC-Regular-2",
                "subtitle_font_size": 28,
                "subtitle_color": "#FFA500",
                "subtitle_border_color": "#000000",
                "subtitle_border_width": 1,
                "subtitle_shadow_color": "#FF4500",
                "subtitle_shadow_x": 2,
                "subtitle_shadow_y": 2,
                "subtitle_alignment": "right",
                "subtitle_position_y": 0.62,
                "overlay_color": "#4a0e0e",
                "overlay_opacity": 0.6,
                "is_default": 0,
            },
            {
                "name": "艺术居中",
                "layout_type": "center-artistic",
                "title_font_name": "ZhanKuWenYiTi-2",
                "title_font_size": 88,
                "title_color": "#FF69B4",
                "title_border_color": "#FFFFFF",
                "title_border_width": 4,
                "title_shadow_color": "#FF1493",
                "title_shadow_x": 5,
                "title_shadow_y": 5,
                "title_alignment": "center",
                "title_position_y": 0.5,
                "subtitle_font_name": "ZhanKuQingKeHuangYouTi-2",
                "subtitle_font_size": 32,
                "subtitle_color": "#FFFFFF",
                "subtitle_border_color": "#FF69B4",
                "subtitle_border_width": 2,
                "subtitle_shadow_color": "#FF1493",
                "subtitle_shadow_x": 2,
                "subtitle_shadow_y": 2,
                "subtitle_alignment": "center",
                "subtitle_position_y": 0.68,
                "overlay_color": "#2d0a1a",
                "overlay_opacity": 0.7,
                "is_default": 0,
            },
            {
                "name": "渐变底部",
                "layout_type": "bottom-gradient",
                "title_font_name": "SourceHanSansSC-Regular-2",
                "title_font_size": 68,
                "title_color": "#FFFFFF",
                "title_border_color": "#000000",
                "title_border_width": 2,
                "title_shadow_color": "#000000",
                "title_shadow_x": 3,
                "title_shadow_y": 3,
                "title_alignment": "center",
                "title_position_y": 0.65,
                "subtitle_font_name": "SourceHanSansSC-Regular-2",
                "subtitle_font_size": 34,
                "subtitle_color": "#EEEEEE",
                "subtitle_border_color": "#000000",
                "subtitle_border_width": 1,
                "subtitle_shadow_color": "#000000",
                "subtitle_shadow_x": 2,
                "subtitle_shadow_y": 2,
                "subtitle_alignment": "center",
                "subtitle_position_y": 0.78,
                "overlay_color": "#000000",
                "overlay_opacity": 0.3,
                "is_default": 0,
            },
            {
                "name": "简约左上",
                "layout_type": "top-left",
                "title_font_name": "SourceHanSansSC-Regular-2",
                "title_font_size": 52,
                "title_color": "#FFFFFF",
                "title_border_color": "#000000",
                "title_border_width": 2,
                "title_shadow_color": "#000000",
                "title_shadow_x": 3,
                "title_shadow_y": 3,
                "title_alignment": "left",
                "title_position_y": 0.15,
                "subtitle_font_name": "SourceHanSansSC-Regular-2",
                "subtitle_font_size": 28,
                "subtitle_color": "#CCCCCC",
                "subtitle_border_color": "#000000",
                "subtitle_border_width": 1,
                "subtitle_shadow_color": "#000000",
                "subtitle_shadow_x": 2,
                "subtitle_shadow_y": 2,
                "subtitle_alignment": "left",
                "subtitle_position_y": 0.25,
                "overlay_color": "#000000",
                "overlay_opacity": 0.4,
                "is_default": 0,
            },
        ]
        for tmpl in default_templates:
            conn.execute("""
                INSERT INTO cover_templates 
                (name, layout_type, title_font_name, title_font_size, title_color, title_border_color, title_border_width,
                 title_shadow_color, title_shadow_x, title_shadow_y, title_alignment, title_position_y,
                 subtitle_font_name, subtitle_font_size, subtitle_color, subtitle_border_color, subtitle_border_width,
                 subtitle_shadow_color, subtitle_shadow_x, subtitle_shadow_y, subtitle_alignment, subtitle_position_y,
                 background_color, overlay_color, overlay_opacity, icon_path, icon_position, is_default,
                 created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                tmpl["name"], tmpl["layout_type"], tmpl["title_font_name"], tmpl["title_font_size"], tmpl["title_color"],
                tmpl["title_border_color"], tmpl["title_border_width"], tmpl["title_shadow_color"],
                tmpl["title_shadow_x"], tmpl["title_shadow_y"], tmpl["title_alignment"], tmpl["title_position_y"],
                tmpl["subtitle_font_name"], tmpl["subtitle_font_size"], tmpl["subtitle_color"],
                tmpl["subtitle_border_color"], tmpl["subtitle_border_width"], tmpl["subtitle_shadow_color"],
                tmpl["subtitle_shadow_x"], tmpl["subtitle_shadow_y"], tmpl["subtitle_alignment"], tmpl["subtitle_position_y"],
                tmpl.get("background_color", ""), tmpl["overlay_color"], tmpl["overlay_opacity"],
                tmpl.get("icon_path", ""), tmpl.get("icon_position", "top-left"), tmpl["is_default"], t, t
            ))
        conn.commit()
    conn.close()

init_cover_templates_table()

try:
    conn = get_db()
    conn.execute("ALTER TABLE cover_templates ADD COLUMN layout_type TEXT DEFAULT 'center'")
    conn.execute("ALTER TABLE cover_templates ADD COLUMN title_position_y REAL DEFAULT 0.4")
    conn.execute("ALTER TABLE cover_templates ADD COLUMN subtitle_position_y REAL DEFAULT 0.55")
    conn.commit()
    conn.close()
except:
    pass

insert_default_templates()

def list_cover_templates():
    conn = get_db()
    rows = conn.execute("SELECT * FROM cover_templates ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cover_template(id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM cover_templates WHERE id=?", (id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_cover_template(data: dict):
    t = now()
    conn = get_db()
    conn.execute("""
        INSERT INTO cover_templates 
        (name, layout_type, title_font_name, title_font_size, title_color, title_border_color, title_border_width,
         title_shadow_color, title_shadow_x, title_shadow_y, title_alignment, title_position_y,
         subtitle_font_name, subtitle_font_size, subtitle_color, subtitle_border_color, subtitle_border_width,
         subtitle_shadow_color, subtitle_shadow_x, subtitle_shadow_y, subtitle_alignment, subtitle_position_y,
         background_color, overlay_color, overlay_opacity, icon_path, icon_position, is_default,
         created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("name", ""),
        data.get("layout_type", "center"),
        data.get("title_font_name", "SourceHanSansSC-Regular-2"),
        data.get("title_font_size", 72),
        data.get("title_color", "#FFFFFF"),
        data.get("title_border_color", "#000000"),
        data.get("title_border_width", 2),
        data.get("title_shadow_color", "#000000"),
        data.get("title_shadow_x", 3),
        data.get("title_shadow_y", 3),
        data.get("title_alignment", "center"),
        data.get("title_position_y", 0.4),
        data.get("subtitle_font_name", "SourceHanSansSC-Regular-2"),
        data.get("subtitle_font_size", 36),
        data.get("subtitle_color", "#CCCCCC"),
        data.get("subtitle_border_color", "#000000"),
        data.get("subtitle_border_width", 1),
        data.get("subtitle_shadow_color", "#000000"),
        data.get("subtitle_shadow_x", 2),
        data.get("subtitle_shadow_y", 2),
        data.get("subtitle_alignment", "center"),
        data.get("subtitle_position_y", 0.55),
        data.get("background_color", ""),
        data.get("overlay_color", "#000000"),
        data.get("overlay_opacity", 0.5),
        data.get("icon_path", ""),
        data.get("icon_position", "top-left"),
        data.get("is_default", 0),
        t, t
    ))
    conn.commit()
    vid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute("SELECT * FROM cover_templates WHERE id=?", (vid,)).fetchone()
    conn.close()
    return dict(row)

def update_cover_template(id: int, data: dict):
    t = now()
    conn = get_db()
    conn.execute("""
        UPDATE cover_templates SET 
        name=?, layout_type=?, title_font_name=?, title_font_size=?, title_color=?, title_border_color=?, title_border_width=?,
        title_shadow_color=?, title_shadow_x=?, title_shadow_y=?, title_alignment=?, title_position_y=?,
        subtitle_font_name=?, subtitle_font_size=?, subtitle_color=?, subtitle_border_color=?, subtitle_border_width=?,
        subtitle_shadow_color=?, subtitle_shadow_x=?, subtitle_shadow_y=?, subtitle_alignment=?, subtitle_position_y=?,
        background_color=?, overlay_color=?, overlay_opacity=?, icon_path=?, icon_position=?, is_default=?, updated_at=?
        WHERE id=?
    """, (
        data.get("name", ""),
        data.get("layout_type", "center"),
        data.get("title_font_name", "SourceHanSansSC-Regular-2"),
        data.get("title_font_size", 72),
        data.get("title_color", "#FFFFFF"),
        data.get("title_border_color", "#000000"),
        data.get("title_border_width", 2),
        data.get("title_shadow_color", "#000000"),
        data.get("title_shadow_x", 3),
        data.get("title_shadow_y", 3),
        data.get("title_alignment", "center"),
        data.get("title_position_y", 0.4),
        data.get("subtitle_font_name", "SourceHanSansSC-Regular-2"),
        data.get("subtitle_font_size", 36),
        data.get("subtitle_color", "#CCCCCC"),
        data.get("subtitle_border_color", "#000000"),
        data.get("subtitle_border_width", 1),
        data.get("subtitle_shadow_color", "#000000"),
        data.get("subtitle_shadow_x", 2),
        data.get("subtitle_shadow_y", 2),
        data.get("subtitle_alignment", "center"),
        data.get("subtitle_position_y", 0.55),
        data.get("background_color", ""),
        data.get("overlay_color", "#000000"),
        data.get("overlay_opacity", 0.5),
        data.get("icon_path", ""),
        data.get("icon_position", "top-left"),
        data.get("is_default", 0),
        t, id
    ))
    conn.commit()
    conn.close()
    return get_cover_template(id)

def delete_cover_template(id: int):
    conn = get_db()
    conn.execute("DELETE FROM cover_templates WHERE id=?", (id,))
    conn.commit()
    conn.close()

def get_default_cover_template():
    conn = get_db()
    row = conn.execute("SELECT * FROM cover_templates WHERE is_default=1").fetchone()
    if row:
        conn.close()
        return dict(row)
    rows = conn.execute("SELECT * FROM cover_templates ORDER BY id LIMIT 1").fetchone()
    conn.close()
    return dict(rows) if rows else None