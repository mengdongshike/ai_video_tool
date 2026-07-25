"""
TTS 微服务 — 独立 venv_tts 进程，端口 8101
调用时加载 IndexTTS2，不调用不占显存
合成直接用参考音频，无需 profile 文件
"""
import sys, json, torch
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PROJECT_ROOT / "models"))

# Windows 控制台编码修复
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = FastAPI(title="TTS 服务")
_tts = None

class SynthesizeRequest(BaseModel):
    text: str
    audio_path: str = ""
    output_dir: str = ""
    # 情感控制
    emo_vector: list | None = None   # 8 维情感向量
    emo_audio_path: str = ""       # 情感参考音频
    emo_alpha: float = 1.0         # 情感强度
    emo_text: str = ""             # 情感文字描述
    interval_silence: int = 200    # 句间停顿(ms)
    max_text_tokens_per_segment: int = 120

@app.post("/synthesize")
def synthesize(req: SynthesizeRequest):
    global _tts
    try:
        if _tts is None:
            from indextts.infer_v2 import IndexTTS2
            model_dir = str(PROJECT_ROOT / "checkpoints" / "indextts2")
            cfg_path = str(Path(model_dir) / "config.yaml")
            print(">> Loading IndexTTS2...")
            _tts = IndexTTS2(cfg_path=cfg_path, model_dir=model_dir, use_fp16=True)

        ref_audio = req.audio_path
        if not ref_audio or not Path(ref_audio).is_file():
            return {"error": f"参考音频不存在: {ref_audio}"}

        output_dir = Path(req.output_dir) if req.output_dir else (PROJECT_ROOT / "outputs" / "audio")
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = req.emo_text or (str(req.emo_vector) if req.emo_vector else "")
        output_path = output_dir / f"synth_{abs(hash(req.text + suffix))}.wav"
        print(f">> Synthesizing: {req.text}")

        _tts.infer(
            spk_audio_prompt=ref_audio,
            text=req.text,
            output_path=str(output_path),
            emo_vector=req.emo_vector,
            emo_audio_prompt=req.emo_audio_path or None,
            emo_alpha=req.emo_alpha,
            emo_text=req.emo_text or None,
            use_emo_text=bool(req.emo_text),
            interval_silence=req.interval_silence,
            max_text_tokens_per_segment=req.max_text_tokens_per_segment,
            verbose=False,
            do_sample=False,
        )

        # 生成字幕 SRT（按实际音频时长分配时间）
        import re, subprocess as sp
        # 获取音频时长
        dur_out = sp.run([
            str(PROJECT_ROOT / "ffmpeg" / "ffprobe.exe") if (PROJECT_ROOT / "ffmpeg" / "ffprobe.exe").exists() else "ffprobe",
            "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(output_path)
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        duration = float(dur_out.stdout.strip() or 1)

        sentences = [s.strip() for s in re.split(r'(?<=[。！？，.!?,])', req.text) if s.strip()]
        if not sentences:
            sentences = [req.text]
        total_chars = sum(len(s) for s in sentences)
        srt_path = output_dir / f"synth_{abs(hash(req.text + suffix))}.srt"

        lines = []
        t = 0.0
        for i, sent in enumerate(sentences):
            ratio = len(sent) / max(total_chars, 1)
            seg_dur = duration * ratio
            def fmt(sec):
                h = int(sec // 3600); m = int((sec % 3600) // 60)
                s = int(sec % 60); ms = int((sec - int(sec)) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            lines.append(str(i+1))
            lines.append(f"{fmt(t)} --> {fmt(t + seg_dur)}")
            lines.append(sent)
            lines.append("")
            t += seg_dur

        with open(str(srt_path), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return {
            "audio_url": str(output_path.relative_to(PROJECT_ROOT).as_posix()),
            "subtitle_url": str(srt_path.relative_to(PROJECT_ROOT).as_posix()),
            "format": "wav"
        }

    except Exception as e:
        import traceback
        print(f">> ERROR: {e}\n{traceback.format_exc()}")
        return {"error": str(e)}

@app.post("/unload")
def unload():
    """卸载模型释放显存 + 内存"""
    global _tts
    if _tts is not None:
        # 0. 先清理 IndexTTS2 内部的缓存 tensor
        cache_attrs = [
            'cache_spk_cond', 'cache_s2mel_style', 'cache_s2mel_prompt',
            'cache_emo_cond', 'cache_mel',
        ]
        for attr in cache_attrs:
            if hasattr(_tts, attr):
                val = getattr(_tts, attr)
                if val is not None:
                    if hasattr(val, 'cpu'):
                        val = val.cpu()
                    del val
                setattr(_tts, attr, None)

        # 1. 删除模型引用
        model = _tts
        _tts = None

        # 2. 递归清理模型内部所有子模块，释放 GPU/CPU tensor
        if hasattr(model, 'modules'):
            for m in model.modules():
                if hasattr(m, '_parameters'):
                    m._parameters.clear()
                if hasattr(m, '_buffers'):
                    m._buffers.clear()
        if hasattr(model, 'model') and hasattr(model.model, 'cpu'):
            try:
                model.model.cpu()
            except:
                pass
        if hasattr(model, 'to'):
            try:
                model.to('cpu')
            except:
                pass

        del model

        # 3. 清理 sys.modules 中的模型模块（释放 import 占用的内存）
        import sys as _sys
        import gc
        to_remove = [k for k in list(_sys.modules.keys()) if 'indextts' in k.lower()]
        for k in to_remove:
            _sys.modules.pop(k, None)

        # 4. GC + CUDA + CPU 缓存全部清理
        gc.collect()
        torch.cuda.empty_cache()
        if hasattr(torch.cuda, 'ipc_collect'):
            torch.cuda.ipc_collect()

        # 5. 强制释放 PyTorch CPU 内存分配器缓存
        try:
            torch.cuda.empty_cache()
            # PyTorch 1.x/2.x: 释放 CPU allocator 缓存
            if hasattr(torch, 'cuda') and hasattr(torch.cuda, 'memory'):
                pass  # memory_stats/reset 不释放 CPU，用 malloc_trim 代替
        except:
            pass

        # 6. 调用底层 malloc_trim 归还内存给操作系统
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            libc.malloc_trim(0)
        except:
            pass
        try:
            import ctypes.util
            libc_path = ctypes.util.find_library("c")
            if libc_path:
                libc = ctypes.CDLL(libc_path)
                if hasattr(libc, 'malloc_trim'):
                    libc.malloc_trim(0)
        except:
            pass

        # Windows: 使用 ctypes 调用 CRT 的 _heapmin
        try:
            import ctypes
            msvcrt = ctypes.CDLL("msvcrt")
            if hasattr(msvcrt, '_heapmin'):
                msvcrt._heapmin()
        except:
            pass

        print(">> TTS model unloaded (VRAM + RAM freed)")
    return {"status": "unloaded"}

if __name__ == "__main__":
    print("TTS Service starting on :8101...")
    uvicorn.run("tts_service:app", host="127.0.0.1", port=8101, reload=False)
