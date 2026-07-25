"""
数字人微服务 -- 独立 venv_latent 进程，端口 8102
调用时加载 LatentSync，不调用不占显存
"""
import sys, json, torch, gc, os, argparse
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 加入 ffmpeg 路径
os.environ["PATH"] = str(PROJECT_ROOT / "ffmpeg") + os.pathsep + os.environ.get("PATH", "")

sys.path.insert(0, str(PROJECT_ROOT / "models"))
sys.path.insert(0, str(PROJECT_ROOT / "models" / "latentsync"))

app = FastAPI(title="数字人服务")
_model = None

class GenerateRequest(BaseModel):
    audio_path: str
    video_path: str
    output_dir: str = ""
    guidance_scale: float = 2.0
    inference_steps: int = 15
    seed: int = 42

@app.post("/generate")
def generate(req: GenerateRequest):
    global _model
    try:
        if _model is None:
            from scripts.inference import main as latent_infer
            from omegaconf import OmegaConf
            _model = {"infer": latent_infer, "OmegaConf": OmegaConf}

        output_dir = Path(req.output_dir) if req.output_dir else (PROJECT_ROOT / "outputs" / "videos")
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_stem = Path(req.audio_path).stem
        output_path = (output_dir / f"dh_{audio_stem}.mp4").resolve()
        temp_dir = output_dir / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 切工作目录（scripts/inference.py 里有相对路径）
        cwd = os.getcwd()
        os.chdir(str(PROJECT_ROOT / "models" / "latentsync"))
        try:
            config = _model["OmegaConf"].load(str(PROJECT_ROOT / "models" / "latentsync" / "configs" / "unet" / "stage2.yaml"))
            config["run"].update({"guidance_scale": req.guidance_scale, "inference_steps": 20})

            parser = argparse.ArgumentParser()
            parser.add_argument("--inference_ckpt_path", type=str, required=True)
            parser.add_argument("--video_path", type=str, required=True)
            parser.add_argument("--audio_path", type=str, required=True)
            parser.add_argument("--video_out_path", type=str, required=True)
            parser.add_argument("--inference_steps", type=int, default=20)
            parser.add_argument("--guidance_scale", type=float, default=1.5)
            parser.add_argument("--temp_dir", type=str, default="temp")
            parser.add_argument("--seed", type=int, default=1247)
            parser.add_argument("--enable_deepcache", action="store_true")
            args = parser.parse_args([
                "--inference_ckpt_path", str(PROJECT_ROOT / "checkpoints" / "latentsync" / "latentsync_unet.pt"),
                "--video_path", req.video_path,
                "--audio_path", req.audio_path,
                "--video_out_path", str(output_path),
                "--inference_steps", str(req.inference_steps),
                "--guidance_scale", str(req.guidance_scale),
                "--seed", str(req.seed),
                "--temp_dir", str((output_dir / "temp").resolve()),
                "--enable_deepcache",
            ])

          
            _model["infer"](config=config, args=args)
        finally:
            os.chdir(cwd)

        video_rel = str(output_path.relative_to(PROJECT_ROOT).as_posix())
        return {"video_url": video_rel, "format": "mp4"}

    except Exception as e:
        import traceback
        print(f">> ERROR dh: {e}\n{traceback.format_exc()}", flush=True)
        return {"error": str(e)}

@app.get("/status")
def status():
    global _model
    vram = 0
    if torch.cuda.is_available():
        vram = torch.cuda.memory_allocated() / 1024**3
    return {"model_loaded": _model is not None, "vram_gb": round(vram, 2)}

@app.post("/unload")
def unload():
    global _model
    if _model is not None:
        # 1. 删除模型引用
        model = _model
        _model = None

        # 2. 递归清理模型内部所有子模块
        if isinstance(model, dict):
            for v in model.values():
                if hasattr(v, 'modules'):
                    for m in v.modules():
                        if hasattr(m, '_parameters'):
                            m._parameters.clear()
                        if hasattr(m, '_buffers'):
                            m._buffers.clear()
        if hasattr(model, 'modules'):
            for m in model.modules():
                if hasattr(m, '_parameters'):
                    m._parameters.clear()
                if hasattr(m, '_buffers'):
                    m._buffers.clear()

        del model

        # 3. 清理 sys.modules 中的模型模块
        import sys as _sys
        to_remove = [k for k in list(_sys.modules.keys()) if 'latentsync' in k.lower() or 'omegaconf' in k.lower()]
        for k in to_remove:
            _sys.modules.pop(k, None)

        # 4. GC + CUDA 全部清理
        gc.collect()
        torch.cuda.empty_cache()
        if hasattr(torch.cuda, 'ipc_collect'):
            torch.cuda.ipc_collect()

        # 5. 调用底层 malloc_trim / _heapmin 归还内存给操作系统
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
        try:
            import ctypes
            msvcrt = ctypes.CDLL("msvcrt")
            if hasattr(msvcrt, '_heapmin'):
                msvcrt._heapmin()
        except:
            pass

        # 6. 强制第二次 GC 清理（因为卸载模块后可能有新的循环引用）
        gc.collect()
        torch.cuda.empty_cache()

        print(">> LatentSync model unloaded (VRAM + RAM freed)", flush=True)
    return {"status": "unloaded"}

if __name__ == "__main__":
    print("Latent Service starting on :8102...")
    uvicorn.run(app, host="127.0.0.1", port=8102)
