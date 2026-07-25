"""视频文案提取工具 — 提取标题、描述、字幕、语音转文字"""
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FFMPEG_PATH = PROJECT_ROOT / "ffmpeg" / "ffmpeg.exe"


def extract_audio_from_video(video_path: str, output_audio: str) -> bool:
    """使用 ffmpeg 从视频中提取音频"""
    if not os.path.exists(video_path):
        print(f"[text_extractor] 视频文件不存在: {video_path}")
        return False
    
    video_path = video_path.replace("\\", "/")
    output_audio = output_audio.replace("\\", "/")
    
    cmd = f'"{FFMPEG_PATH}" -i "{video_path}" -vn -acodec pcm_s16le -ar 16000 -ac 1 "{output_audio}" -y -loglevel error'
    print(f"[text_extractor] 执行命令: {cmd}")
    
    result = os.system(cmd)
    print(f"[text_extractor] 命令返回: {result}")
    
    if result != 0:
        print(f"[text_extractor] ffmpeg 执行失败，尝试其他方式")
        cmd2 = f'{FFMPEG_PATH} -i "{video_path}" -vn -acodec pcm_s16le -ar 16000 -ac 1 "{output_audio}" -y -loglevel error'
        result = os.system(cmd2)
        print(f"[text_extractor] 命令2返回: {result}")
    
    return result == 0


WHISPER_MODEL_PATH = str(PROJECT_ROOT / "checkpoints" / "whisper" / "ct2")
_WHISPER_MODEL = None


def get_whisper_model():
    """惰性加载并缓存 faster-whisper 模型（从本地 CTranslate2 格式目录加载）"""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        if not os.path.exists(WHISPER_MODEL_PATH):
            raise FileNotFoundError(
                f"Whisper 模型未找到: {WHISPER_MODEL_PATH}。"
                f"请下载 Systran/faster-whisper-tiny 到该目录。"
            )
        
        print(f"[text_extractor] 加载 faster-whisper 模型: {WHISPER_MODEL_PATH}")
        print(f"[text_extractor] 设备: cpu, 精度: int8")
        
        from faster_whisper import WhisperModel
        _WHISPER_MODEL = WhisperModel(
            WHISPER_MODEL_PATH,
            device="cpu",
            compute_type="int8",
        )
        print(f"[text_extractor] 模型加载完成")
    return _WHISPER_MODEL


def transcribe_with_faster_whisper(audio_path: str) -> Dict[str, Any]:
    """使用 faster-whisper 进行语音转文字"""
    try:
        model = get_whisper_model()
        print(f"[text_extractor] 开始转写: {audio_path}")
        segments_iter, info = model.transcribe(
            audio_path,
            language="zh",
            beam_size=5,
            vad_filter=True,
        )

        segments = []
        full_text = ""
        for seg in segments_iter:
            text = seg.text.strip()
            if text:
                segments.append({
                    "text": text,
                    "start": float(seg.start),
                    "end": float(seg.end),
                })
                full_text += text + " "
 
        return {
            "success": True,
            "text": full_text.strip(),
            "segments": segments,
            "language": getattr(info, "language", "zh"),
        }
    except Exception as e:
        print(f"[text_extractor] 转写异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def transcribe_with_whisper(input_path: str, model_path: str = None) -> Dict[str, Any]:
    """使用 Whisper 模型进行语音转文字（支持视频或音频文件）"""
    video_extensions = (".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm")

    try:
        audio_path = input_path
        is_video = input_path.lower().endswith(video_extensions)

        if is_video:
            with tempfile.TemporaryDirectory() as tmp_dir:
                audio_path = os.path.join(tmp_dir, "audio.wav")
                if not extract_audio_from_video(input_path, audio_path):
                    return {"success": False, "error": "提取音频失败"}
                result = transcribe_with_faster_whisper(audio_path)
        else:
            result = transcribe_with_faster_whisper(audio_path)

        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_video_text(video_path: str, use_whisper: bool = True) -> Dict[str, Any]:
    """提取视频中的所有文案信息"""
    result = {
        "title": "",
        "description": "",
        "asr_text": "",
        "asr_segments": [],
        "success": False,
    }
    
    if not os.path.exists(video_path):
        result["error"] = "视频文件不存在"
        return result
    
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    result["title"] = video_name
    
    if use_whisper:
        print(f"[text_extractor] 开始提取视频文案: {video_path}")
        asr_result = transcribe_with_whisper(video_path)
        if asr_result.get("success"):
            result["asr_text"] = asr_result["text"]
            result["asr_segments"] = asr_result.get("segments", [])
            result["success"] = True
        else:
            result["error"] = asr_result.get("error", "转写失败")
            result["success"] = False
    else:
        result["success"] = True
    
    return result


def clean_text(text: str) -> str:
    """清理文本中的多余空格和特殊字符"""
    if not text:
        return ""
    
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9，。！？、；：""''（）【】《》\s]", "", text)
    return text.strip()


def merge_texts(*texts: str) -> str:
    """合并多个文本，去重并保留顺序"""
    seen = set()
    result = []
    for text in texts:
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return "\n".join(result)