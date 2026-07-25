"""视频合成 — YYKA 两步法"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Body
import subprocess, os, shutil
from utils.subtitle import find_font, parse_srt, build_drawtext_filter_file, build_drawtext_filter
from database.subtitle_templates import get_subtitle_template, get_default_template
from routes.cover_templates import generate_cover_image
from utils.logger import get_logger

logger = get_logger("compose")

router = APIRouter(prefix="/api", tags=["合成"])
BASE = Path(__file__).resolve().parent.parent.parent
FF = str(BASE / "ffmpeg" / "ffmpeg.exe") if (BASE / "ffmpeg" / "ffmpeg.exe").exists() else "ffmpeg"
FP = str(BASE / "ffmpeg" / "ffprobe.exe") if (BASE / "ffmpeg" / "ffprobe.exe").exists() else "ffprobe"

def ap(p: str) -> str:
    if not p: return p
    p = p.lstrip("/")
    if p.startswith("http://") or p.startswith("https://"):
        p = p.replace("http://localhost:8000/", "").replace("https://localhost:8000/", "")
        p = p.lstrip("/")
    return p if os.path.isabs(p) else str(BASE / p)

def fx(p: str) -> str:
    return Path(p).as_posix()

DEFAULT_STYLE = {
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
}

@router.post("/compose/video")
def compose_video(body: dict = Body(...)):
    try:
        video = ap(body.get("video_path", ""))
        srt = ap(body.get("srt_path", ""))
        bgm = ap(body.get("bgm_path", "")) if body.get("bgm_path") else ""
        vol = float(body.get("bgm_volume", 0.3))
        template_id = body.get("subtitle_template_id", "")
        cover_template_id = body.get("cover_template_id", "")
        cover_title = body.get("cover_title", "")
        cover_subtitle = body.get("cover_subtitle", "")
    except Exception as e:
        import traceback
        logger.error(f"compose 参数解析失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(400, f"参数错误: {e}")

    if not video or not Path(video).is_file():
        raise HTTPException(400, f"视频不存在: {video}")

    out_dir = BASE / "outputs" / "compose"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(video).stem
    out = str(out_dir / f"final_{stem}.mp4")

    v, b = fx(video), fx(bgm) if bgm else ""
    has_srt = srt and Path(srt).is_file()
    has_bgm = bgm and Path(bgm).is_file()

    # 生成封面图（从视频抽帧作为背景 + 叠加文字）
    cover_url = ""
    if cover_template_id and cover_title:
        try:
            # 获取视频尺寸
            r = subprocess.run([FP, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0", v],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            dims = r.stdout.strip().split('x') if r.stdout.strip() else []
            vw, vh = (int(dims[0]), int(dims[1])) if len(dims) == 2 else (1080, 1920)

            # 从视频抽首帧作为封面背景
            frame_path = str(out_dir / f"cover_bg_{stem}.png")
            subprocess.run([FF, "-y", "-i", v, "-ss", "0", "-frames:v", "1", "-q:v", "2", frame_path],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30, check=True, cwd=str(BASE))

            cover_img, _ = generate_cover_image(
                cover_title, cover_subtitle, cover_template_id,
                background_image=frame_path, width=vw, height=vh
            )
            cover_url = Path(cover_img).relative_to(BASE).as_posix()
            try: os.remove(frame_path)
            except: pass
        except subprocess.CalledProcessError as e:
            logger.error(f"封面生成失败，stderr: {(e.stderr or e.stdout or '(空)')[-500:]}")
        except Exception as e:
            logger.error(f"封面生成失败: {e}")

    subtitle_style = DEFAULT_STYLE.copy()

    if template_id:
        template = get_subtitle_template(int(template_id))
        if template:
            subtitle_style.update({
                "font_name": template["font_name"],
                "font_size": template["font_size"],
                "font_color": template["font_color"],
                "border_color": template["border_color"],
                "border_width": template["border_width"],
                "shadow_color": template["shadow_color"],
                "shadow_x": template["shadow_x"],
                "shadow_y": template["shadow_y"],
                "margin_bottom": template["margin_bottom"],
                "alignment": template["alignment"],
                "background_color": template["background_color"],
                "background_padding": template["background_padding"],
            })

    fontfile = find_font(subtitle_style["font_name"])

    try:
        # 合成：BGM + 字幕
        if has_bgm:
            r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", v],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            vdur = float(r.stdout.strip() or 1)
            bgm_filter = (
                f"[0:a]acompressor=threshold=-20dB:ratio=3:attack=5:release=50,"
                f"equalizer=f=100:t=q:w=1:g=3,"
                f"equalizer=f=3000:t=q:w=1:g=2,"
                f"aecho=0.8:0.9:50:0.2[vocal];"
                f"[1:a]volume={vol}[bgm];"
                f"[bgm]aloop=loop=-1,atrim=duration={vdur}[bgm_loop];"
                f"[vocal][bgm_loop]amix=inputs=2:duration=first[aout]"
            )
            temp = str(out_dir / f"{stem}_temp.mp4")
            subprocess.run([FF, "-y", "-i", v, "-i", b,
                "-filter_complex", bgm_filter,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", temp],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, check=True, cwd=str(BASE))

            if has_srt:
                subtitles = parse_srt(srt)
                vf = build_drawtext_filter(subtitles, fontfile, subtitle_style)
                subprocess.run([FF, "-y", "-i", temp,
                    "-filter_complex", vf,
                    "-map", "[vout]", "-map", "0:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "copy", out],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, check=True, cwd=str(BASE))
                try: os.remove(temp)
                except: pass
            else:
                shutil.move(temp, out)
        else:
            if has_srt:
                subtitles = parse_srt(srt)
                vf = build_drawtext_filter(subtitles, fontfile, subtitle_style)
                subprocess.run([FF, "-y", "-i", v,
                    "-filter_complex", vf,
                    "-map", "[vout]", "-map", "0:a",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "copy", out],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, check=True, cwd=str(BASE))
            else:
                shutil.copy2(video, out)
    except subprocess.TimeoutExpired as e:
        logger.error(f"视频合成超时 ({e.timeout}s)")
        logger.error(f"输入视频: {video}")
        logger.error(f"输入字幕: {srt}")
        logger.error(f"输入BGM: {bgm}")
        raise HTTPException(500, f"合成超时 ({e.timeout}秒)")
    except subprocess.CalledProcessError as e:
        raw = (e.stderr or e.stdout or "")

        # 提取真正的错误行，过滤 libx264 编码统计日志
        error_lines = []
        libx264_lines = []
        for line in raw.split("\n"):
            line_s = line.strip()
            if not line_s:
                continue
            # 跳过 libx264 编码统计
            if any(kw in line_s for kw in ("mb ", "skip:", "i16 v,h,dc,p:", "8x8 transform", "coded y,uvDC", "L0:", "y,uv,intra:", "y,uv,inter:", "kb/s:")):
                libx264_lines.append(line_s)
                continue
            error_lines.append(line_s)

        logger.error(f"视频合成失败 (exit={e.returncode})")
        logger.error(f"输入视频: {video}")
        logger.error(f"输入字幕: {srt}")
        logger.error(f"输入BGM: {bgm}")
        logger.error(f"字体: {fontfile}")
        if error_lines:
            for l in error_lines:
                logger.error(f"ERR: {l}")
        if libx264_lines:
            logger.error(f"libx264 编码统计: {libx264_lines[-3:]} ...共 {len(libx264_lines)} 行")

        msg = "\n".join(error_lines[-10:]) if error_lines else f"ffmpeg 退出码={e.returncode}"
        raise HTTPException(500, "合成失败: " + msg)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"视频合成异常: {e}")
        logger.error(f"输入视频: {video}")
        logger.error(f"输入字幕: {srt}")
        logger.error(f"输入BGM: {bgm}")
        logger.error(f"Traceback:\n{tb}")
        raise HTTPException(500, f"合成异常: {e}")

    size = round(Path(out).stat().st_size / (1024*1024), 1)
    return {
        "file_url": Path(out).relative_to(BASE).as_posix(),
        "size_mb": size,
        "cover_url": cover_url,
    }

@router.post("/compose/watermark")
def compose_watermark(body: dict = Body(...)):
    video = ap(body.get("video_path", ""))
    watermark = ap(body.get("watermark_path", ""))
    if not video or not Path(video).is_file():
        raise HTTPException(400, f"视频不存在: {video}")
    if not watermark or not Path(watermark).is_file():
        raise HTTPException(400, f"水印不存在: {watermark}")
    
    out_dir = BASE / "outputs" / "compose"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(video).stem
    out = str(out_dir / f"wm_{stem}.mp4")
    
    v, w = fx(video), fx(watermark)
    vf = f"overlay=W-w-20:H-h-20"
    
    subprocess.run([FF, "-y", "-i", v, "-i", w,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy", out],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, check=True)
    
    size = round(Path(out).stat().st_size / (1024*1024), 1)
    return {"file_url": Path(out).relative_to(BASE).as_posix(), "size_mb": size}

@router.post("/compose/resize")
def compose_resize(body: dict = Body(...)):
    video = ap(body.get("video_path", ""))
    width = body.get("width", 1080)
    height = body.get("height", 1920)
    if not video or not Path(video).is_file():
        raise HTTPException(400, f"视频不存在: {video}")
    
    out_dir = BASE / "outputs" / "compose"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(video).stem
    out = str(out_dir / f"rs_{stem}.mp4")
    
    v = fx(video)
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    
    subprocess.run([FF, "-y", "-i", v,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy", out],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, check=True)
    
    size = round(Path(out).stat().st_size / (1024*1024), 1)
    return {"file_url": Path(out).relative_to(BASE).as_posix(), "size_mb": size}

@router.post("/compose/extract-audio")
def compose_extract_audio(body: dict = Body(...)):
    video = ap(body.get("video_path", ""))
    if not video or not Path(video).is_file():
        raise HTTPException(400, f"视频不存在: {video}")
    
    out_dir = BASE / "outputs" / "compose"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(video).stem
    out = str(out_dir / f"audio_{stem}.mp3")
    
    v = fx(video)
    subprocess.run([FF, "-y", "-i", v, "-q:a", "0", "-map", "a", out],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, check=True)
    
    size = round(Path(out).stat().st_size / (1024*1024), 1)
    return {"file_url": Path(out).relative_to(BASE).as_posix(), "size_mb": size}

@router.get("/compose/duration")
def compose_duration(video_path: str):
    video = ap(video_path)
    if not video or not Path(video).is_file():
        raise HTTPException(400, f"视频不存在: {video}")
    
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", fx(video)],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
    duration = float(r.stdout.strip() or 0)
    return {"duration": duration}
