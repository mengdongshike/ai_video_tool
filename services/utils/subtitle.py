"""字幕处理工具"""
from pathlib import Path
import re, tempfile, os

BASE = Path(__file__).resolve().parent.parent.parent
FONT_DIR = BASE / "fonts"

FONT_MAP = {
    "SourceHanSansSC-Regular": "SourceHanSansSC-Regular-2.otf",
    "ZhanKuQingKeHuangYouTi": "ZhanKuQingKeHuangYouTi-2.ttf",
    "gkai00mp": "gkai00mp-2.ttf",
    "LXGWHeartSerifCHS": "LXGWHeartSerifCHS-2.ttf",
    "Slidefu-Regular": "Slidefu-Regular-2.ttf",
    "ZhanKuWenYiTi": "ZhanKuWenYiTi-2.ttf",
    "ZhanKuXiaoLOGOTi": "ZhanKuXiaoLOGOTi-2.otf",
    "ZiTiQuanXinYiGuanHeiTi4.0": "ZiTiQuanXinYiGuanHeiTi4.0-2.ttf",
}

def find_font(font_name):
    if font_name in FONT_MAP:
        font_file = FONT_DIR / FONT_MAP[font_name]
        if font_file.exists():
            return str(font_file.relative_to(BASE))
    
    font_file = FONT_DIR / f"{font_name}.ttf"
    if font_file.exists():
        return str(font_file.relative_to(BASE))
    
    font_file = FONT_DIR / f"{font_name}.otf"
    if font_file.exists():
        return str(font_file.relative_to(BASE))
    
    font_file = FONT_DIR / f"{font_name}.ttc"
    if font_file.exists():
        return str(font_file.relative_to(BASE))
    
    for f in FONT_DIR.iterdir():
        if f.stem.replace("-2", "") == font_name or f.stem == font_name:
            return str(f.relative_to(BASE))
    
    default_font = FONT_DIR / "SourceHanSansSC-Regular-2.otf"
    return str(default_font.relative_to(BASE)) if default_font.exists() else "fonts/SourceHanSansSC-Regular-2.otf"

def parse_time(time_str):
    hh, mm, ss_ms = time_str.split(':')
    if ',' in ss_ms:
        ss, ms = ss_ms.split(',')
    elif '.' in ss_ms:
        ss, ms = ss_ms.split('.')
    else:
        ss, ms = ss_ms, '0'
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000

def parse_srt(srt_path):
    subtitles = []
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(srt_path, 'r', encoding='gbk') as f:
            content = f.read()
    
    blocks = content.strip().split('\n\n')
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            idx = lines[0]
            if not idx.isdigit():
                continue
            time_range = lines[1]
            text = '\n'.join(lines[2:])
            if '-->' in time_range:
                start_str, end_str = time_range.split(' --> ')
                subtitles.append({
                    'index': int(idx),
                    'start': parse_time(start_str),
                    'end': parse_time(end_str),
                    'text': text.strip()
                })
    return subtitles

def escape_text(text):
    text = text.replace('\\', '\\\\')
    text = text.replace("'", "\\'")
    text = text.replace('"', '\\"')
    text = text.replace('\n', '\\\\N')
    # ffmpeg drawtext has a bug with % in multi-byte UTF-8 strings,
    # so replace half-width % with full-width ％ (U+FF05)
    text = text.replace('%', '\uff05')
    return text

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return f"0x{hex_color}"

def build_drawtext_filter(subtitles, fontfile, style):
    filters = []
    
    fontsize = style.get("font_size", 40)
    fontcolor = hex_to_rgb(style.get("font_color", "#FFFFFF"))
    bordercolor = hex_to_rgb(style.get("border_color", "#000000"))
    borderw = style.get("border_width", 2)
    shadowcolor = hex_to_rgb(style.get("shadow_color", "#000000"))
    shadowx = style.get("shadow_x", 2)
    shadowy = style.get("shadow_y", 2)
    margin_bottom = style.get("margin_bottom", 50)
    alignment = style.get("alignment", "center")
    bg_color = style.get("background_color", "")
    bg_padding = style.get("background_padding", 0)
    
    fontfile_path = Path(fontfile).as_posix()
    
    if alignment == "left":
        x_expr = f"{margin_bottom}"
    elif alignment == "right":
        x_expr = f"w-text_w-{margin_bottom}"
    else:
        x_expr = "(w-text_w)/2"
    
    base_y = f"h-{margin_bottom}-text_h"
    
    for sub in subtitles:
        text = escape_text(sub['text'])
        
        ft = f"drawtext=fontfile='{fontfile_path}':text='{text}':"
        ft += f"fontsize={fontsize}:"
        ft += f"fontcolor={fontcolor}:"
        ft += f"bordercolor={bordercolor}:"
        ft += f"borderw={borderw}:"
        
        if shadowx > 0 or shadowy > 0:
            ft += f"shadowcolor={shadowcolor}:"
            ft += f"shadowx={shadowx}:"
            ft += f"shadowy={shadowy}:"
        
        if bg_color and bg_color != "":
            ft += f"box=1:boxcolor={hex_to_rgb(bg_color)}:boxborderw={bg_padding}:"
        
        ft += f"x={x_expr}:"
        ft += f"y={base_y}:"
        ft += f"enable='between(t,{sub['start']:.3f},{sub['end']:.3f})'"
        
        filters.append(ft)
    
    return "[0:v]%s[vout]" % ','.join(filters)

def build_drawtext_filter_file(subtitles, fontfile, style, output_dir):
    filter_str = build_drawtext_filter(subtitles, fontfile, style)
    
    fd, path = tempfile.mkstemp(suffix='.ff', dir=str(output_dir))
    try:
        os.write(fd, filter_str.encode('utf-8'))
        os.close(fd)
        content = Path(path).read_bytes()
        if content[:3] == b'\xef\xbb\xbf':
            Path(path).write_bytes(content[3:])
        return path
    except:
        os.close(fd)
        os.unlink(path)
        raise
