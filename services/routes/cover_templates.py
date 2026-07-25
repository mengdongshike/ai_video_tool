"""封面模板路由"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Body
import subprocess, os
from database.cover_templates import *

router = APIRouter(prefix="/api", tags=["封面模板"])

BASE = Path(__file__).resolve().parent.parent.parent
FF = str(BASE / "ffmpeg" / "ffmpeg.exe") if (BASE / "ffmpeg" / "ffmpeg.exe").exists() else "ffmpeg"
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

def find_font(font_name: str) -> str:
    name = font_name
    if not font_name.endswith(('.ttf', '.ttc', '.otf')):
        name = font_name + '.otf'
    for f in FONT_DIR.iterdir():
        if f.suffix.lower() in ('.ttf', '.ttc', '.otf'):
            if f.stem == font_name or f.name == name or f.stem.replace('-2', '') == font_name.replace('-2', ''):
                return str(f.relative_to(BASE))
    return font_name

def hex_to_rgb(hex_color: str) -> str:
    """统一返回 0xRRGGBB 格式（drawtext 和 color 滤镜都用这个，冒号是参数分隔符不能用 RR:GG:BB）"""
    h = hex_color.strip().lstrip('#')
    if len(h) == 6:
        return f"0x{h.upper()}"
    return "0xFFFFFF"

def build_drawtext_for_cover(fontfile: str, text: str, fontsize: int, fontcolor: str,
                             bordercolor: str, borderw: int, shadowcolor: str,
                             shadowx: int, shadowy: int, alignment: str, y_pos: str,
                             layout_type: str = 'center', x_pos: float = 0.5) -> str:
    fontfile = Path(fontfile).as_posix()
    fontcolor = hex_to_rgb(fontcolor)
    bordercolor = hex_to_rgb(bordercolor)
    shadowcolor = hex_to_rgb(shadowcolor)

    def _one_drawtext(ch: str, x_expr: str, y_expr: str) -> str:
        ch_escaped = ch.replace("'", "\\'").replace(':', '\\:').replace(',', '\\,')
        ft = f"drawtext=fontfile='{fontfile}':text='{ch_escaped}':"
        ft += f"fontsize={fontsize}:"
        ft += f"fontcolor={fontcolor}:"
        ft += f"bordercolor={bordercolor}:"
        ft += f"borderw={borderw}:"
        ft += f"shadowcolor={shadowcolor}:"
        ft += f"shadowx={shadowx}:"
        ft += f"shadowy={shadowy}:"
        ft += f"x={x_expr}:"
        ft += f"y={y_expr}"
        return ft

    if layout_type in ('left-vertical', 'right-vertical'):
        if layout_type == 'left-vertical':
            x_expr = "(w*0.04)"
        else:
            x_expr = "(w-w*0.04-text_w)"
        chars = list(text)
        if len(chars) == 1:
            return _one_drawtext(chars[0], x_expr, y_pos)
        parts = []
        for i, ch in enumerate(chars):
            y_offset = i * fontsize * 1.1
            y_expr = f"{y_pos}+{y_offset}"
            in_label = "" if i == 0 else f"[t{i-1}]"
            out_label = f"[t{i}]" if i < len(chars) - 1 else ""
            parts.append(f"{in_label}{_one_drawtext(ch, x_expr, y_expr)}{out_label}")
        return ";".join(parts)

    # 自由布局：使用 position_x 百分比计算 X 坐标
    if x_pos != 0.5:
        x_expr = f"(w*{x_pos}-text_w/2)"
    else:
        x_map = {
            'left': '0',
            'center': '(w-text_w)/2',
            'right': 'w-text_w'
        }
        x_expr = x_map.get(alignment, '(w-text_w)/2')
    return _one_drawtext(text, x_expr, y_pos)

@router.get("/cover/templates")
def api_cover_templates_list():
    return list_cover_templates()

@router.get("/cover/templates/{id}")
def api_cover_templates_get(id: int):
    t = get_cover_template(id)
    if not t:
        raise HTTPException(404, "模板不存在")
    return t

@router.post("/cover/templates")
def api_cover_templates_create(body: dict = Body(...)):
    if not body.get("name"):
        raise HTTPException(400, "模板名称不能为空")
    if not body.get("title_font_name"):
        raise HTTPException(400, "标题字体不能为空")
    return create_cover_template(body)

@router.put("/cover/templates/{id}")
def api_cover_templates_update(id: int, body: dict = Body(...)):
    t = get_cover_template(id)
    if not t:
        raise HTTPException(404, "模板不存在")
    return update_cover_template(id, body)

@router.delete("/cover/templates/{id}")
def api_cover_templates_delete(id: int):
    t = get_cover_template(id)
    if not t:
        raise HTTPException(404, "模板不存在")
    delete_cover_template(id)
    return {"success": True}

@router.get("/cover/templates/default")
def api_cover_templates_default():
    t = get_default_cover_template()
    if not t:
        raise HTTPException(404, "没有可用的封面模板")
    return t

@router.post("/cover/templates/{id}/default")
def api_cover_templates_set_default(id: int):
    t = get_cover_template(id)
    if not t:
        raise HTTPException(404, "模板不存在")
    conn = get_db()
    conn.execute("UPDATE cover_templates SET is_default=0")
    conn.execute("UPDATE cover_templates SET is_default=1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return {"success": True}

@router.get("/cover/fonts")
def api_cover_fonts():
    fonts = []
    if FONT_DIR.exists():
        for f in FONT_DIR.iterdir():
            if f.suffix.lower() in (".ttf", ".ttc", ".otf"):
                name = f.stem.replace("-2", "")
                fonts.append({
                    "name": name,
                    "file": f.name,
                    "path": str(f),
                    "cn_name": FONT_CN_MAP.get(name, name)
                })
    return fonts

@router.post("/cover/generate")
def api_cover_generate(body: dict = Body(...)):
    title = body.get("title", "")
    subtitle = body.get("subtitle", "")
    template_id = body.get("template_id", "")
    background_image = body.get("background_image", "")
    width = body.get("width", 1080)
    height = body.get("height", 1920)

    if not title:
        raise HTTPException(400, "标题不能为空")

    try:
        out, _ = generate_cover_image(title, subtitle, template_id, background_image, width, height)
        size = round(Path(out).stat().st_size / (1024*1024), 2)
        return {"file_url": Path(out).relative_to(BASE).as_posix(), "size_mb": size}
    except HTTPException:
        raise
    except subprocess.CalledProcessError as e:
        msg = e.stderr[-800:] if e.stderr else e.stdout[-800:] if e.stdout else ""
        raise HTTPException(500, "封面生成失败: " + msg)
    except Exception as e:
        raise HTTPException(500, f"封面生成异常: {e}")


def generate_cover_image(title: str, subtitle: str = "", template_id="", background_image="", width=1080, height=1920):
    """生成封面图，返回 (绝对路径, 模板dict)。供 compose 等模块复用。"""
    template = None
    if template_id:
        try:
            template = get_cover_template(int(template_id))
        except Exception:
            template = None
    if not template:
        template = get_default_cover_template()
    if not template:
        raise HTTPException(400, "没有可用的封面模板")

    out_dir = BASE / "outputs" / "covers"
    out_dir.mkdir(parents=True, exist_ok=True)

    import hashlib
    hash_str = f"{title}{subtitle}{template_id}{width}{height}"
    hash_name = hashlib.md5(hash_str.encode()).hexdigest()[:16]
    out = str(out_dir / f"cover_{hash_name}.png")

    title_fontfile = find_font(template["title_font_name"])
    subtitle_fontfile = find_font(template["subtitle_font_name"])

    overlay_color = hex_to_rgb(template["overlay_color"])
    overlay_opacity = template["overlay_opacity"]

    filters = []
    bg_path = None
    if background_image:
        bg_path = background_image
        if bg_path.startswith("http://") or bg_path.startswith("https://"):
            bg_path = bg_path.replace("http://localhost:8000/", "").replace("https://localhost:8000/", "")
            bg_path = bg_path.lstrip("/")
        if not os.path.isabs(bg_path):
            bg_path = str(BASE / bg_path)
        if not Path(bg_path).exists():
            raise HTTPException(400, f"背景图片不存在: {bg_path}")

        filters.append(f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[bg]")

        if template["overlay_color"] and template["overlay_color"] != "":
            filters.append(f"[bg]drawbox=x=0:y=0:w=iw:h=ih:color={overlay_color}@{overlay_opacity}:t=fill[bg_overlay]")
            input_label = "[bg_overlay]"
        else:
            input_label = "[bg]"
    else:
        filters.append(f"color=c={overlay_color}:s={width}x{height}[bg]")
        input_label = "[bg]"

    title_y = f"(h*{template.get('title_position_y', 0.4)})"
    subtitle_y = f"(h*{template.get('subtitle_position_y', 0.55)})"
    title_x = float(template.get('title_position_x', 0.5))
    subtitle_x = float(template.get('subtitle_position_x', 0.5))

    title_ft = build_drawtext_for_cover(
        title_fontfile, title,
        template["title_font_size"], template["title_color"],
        template["title_border_color"], template["title_border_width"],
        template["title_shadow_color"], template["title_shadow_x"], template["title_shadow_y"],
        template["title_alignment"], title_y,
        template.get("layout_type", "center"), title_x
    )
    filters.append(f"{input_label}{title_ft}[v1]")

    if subtitle:
        subtitle_ft = build_drawtext_for_cover(
            subtitle_fontfile, subtitle,
            template["subtitle_font_size"], template["subtitle_color"],
            template["subtitle_border_color"], template["subtitle_border_width"],
            template["subtitle_shadow_color"], template["subtitle_shadow_x"], template["subtitle_shadow_y"],
            template["subtitle_alignment"], subtitle_y,
            template.get("layout_type", "center"), subtitle_x
        )
        filters.append(f"[v1]{subtitle_ft}[vout]")
    else:
        filters.append(f"[v1]copy[vout]")

    filter_complex = ";".join(filters)

    inputs = []
    if bg_path:
        inputs.extend(["-i", str(bg_path)])

    cmd = [FF, "-y"]
    cmd.extend(inputs)
    cmd.extend(["-filter_complex", filter_complex, "-map", "[vout]", "-frames:v", "1", "-q:v", "2", out])

    try:
        subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=120, check=True, cwd=str(BASE))
    except subprocess.CalledProcessError as e:
        print(f"[cover] filter_complex 长度: {len(filter_complex)}")
        print(f"[cover] stderr 完整输出:")
        print(e.stderr or "(空)")
        raise

    return out, template