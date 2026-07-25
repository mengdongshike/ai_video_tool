"""字幕模板路由"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Body
from database.subtitle_templates import *

router = APIRouter(prefix="/api", tags=["字幕模板"])

BASE = Path(__file__).resolve().parent.parent.parent
FONT_DIR = BASE / "fonts"

FONT_CN_MAP = {
    "SourceHanSansSC-Regular": "思源黑体",
    "ZhanKuQingKeHuangYouTi": "站酷黄油体",
    "gkai00mp": "楷体",
    "LXGWHeartSerifCHS": "霞鹜文楷",
    "Slidefu-Regular": "Slidefu",
    "ZhanKuWenYiTi": "站酷文艺体",
    "ZhanKuXiaoLOGOTi": "站酷小LOGO体",
    "ZiTiQuanXinYiGuanHeiTi4.0": "全新一关黑体",
}

def get_available_fonts():
    fonts = []
    if FONT_DIR.exists():
        for f in FONT_DIR.iterdir():
            if f.suffix.lower() in (".ttf", ".ttc", ".otf"):
                name = f.stem.replace("-2", "")
                fonts.append({
                    "name": name,
                    "file": f.name,
                    "url": f"/fonts/{f.name}",
                    "cn_name": FONT_CN_MAP.get(name, name)
                })
    return fonts

@router.get("/subtitle/templates")
def api_subtitle_templates_list():
    return list_subtitle_templates()

@router.get("/subtitle/templates/{id}")
def api_subtitle_templates_get(id: int):
    t = get_subtitle_template(id)
    if not t:
        raise HTTPException(404, "模板不存在")
    return t

@router.post("/subtitle/templates")
def api_subtitle_templates_create(body: dict = Body(...)):
    if not body.get("name"):
        raise HTTPException(400, "模板名称不能为空")
    if not body.get("font_name"):
        raise HTTPException(400, "字体名称不能为空")
    return create_subtitle_template(body)

@router.put("/subtitle/templates/{id}")
def api_subtitle_templates_update(id: int, body: dict = Body(...)):
    t = get_subtitle_template(id)
    if not t:
        raise HTTPException(404, "模板不存在")
    return update_subtitle_template(id, body)

@router.delete("/subtitle/templates/{id}")
def api_subtitle_templates_delete(id: int):
    t = get_subtitle_template(id)
    if not t:
        raise HTTPException(404, "模板不存在")
    delete_subtitle_template(id)
    return {"success": True}

@router.get("/subtitle/fonts")
def api_subtitle_fonts():
    return get_available_fonts()

@router.get("/subtitle/templates/default")
def api_subtitle_templates_default():
    t = get_default_template()
    if not t:
        raise HTTPException(404, "没有可用的字幕模板")
    return t

@router.post("/subtitle/templates/{id}/default")
def api_subtitle_templates_set_default(id: int):
    t = get_subtitle_template(id)
    if not t:
        raise HTTPException(404, "模板不存在")
    conn = get_db()
    conn.execute("UPDATE subtitle_templates SET is_default=0")
    conn.execute("UPDATE subtitle_templates SET is_default=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return {"success": True}
