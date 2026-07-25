"""
环境检测脚本 — 在启动服务前运行
检测：GPU / CUDA / Python / 依赖 / 模型文件
所有输出必须只在 stdout 末尾打印一次 JSON，其余信息全部 silenced
"""
import subprocess, sys, os, json, shutil, re, warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 屏蔽所有警告
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# 支持的最低 CUDA 版本
MIN_CUDA = 11.8

def get_torch_cmd(venv_name, cuda_version):
    """从 manifest.json 读取对应 CUDA 的 torch 安装命令"""
    VENV_MODEL_MAP = {"venv_tts": "indextts2", "venv_latent": "latentsync"}
    model_name = VENV_MODEL_MAP.get(venv_name)
    if not model_name:
        return None
    
    manifest_path = PROJECT_ROOT / "models" / model_name / "manifest.json"
    if not manifest_path.exists():
        return None
    
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        torch_map = manifest.get("torch", {})
        
        if not cuda_version:
            return None
        
        cuda_float = float(cuda_version)
        
        # 精确匹配
        if cuda_version in torch_map:
            return torch_map[cuda_version]
        
        # 找最近的兼容版本
        candidates = [float(k) for k in torch_map.keys() if float(k) <= cuda_float]
        if candidates:
            best = max(candidates)
            return torch_map[str(best)]
        
        return None
    except:
        return None

def check_gpu():
    """检测 NVIDIA GPU 信息"""
    result = {"has_gpu": False, "gpu_name": "", "vram_mb": 0, "cuda_version": ""}
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,compute_cap",
             "--format=csv,noheader,nounits"],
            timeout=10, text=True, encoding='utf-8', errors='replace'
        ).strip()
        if out:
            parts = out.split(",")
            result["has_gpu"] = True
            result["gpu_name"] = parts[0].strip()
            result["vram_mb"] = int(float(parts[1].strip()))
            
        # CUDA 版本
        try:
            nvout = subprocess.check_output(["nvidia-smi"], timeout=5, text=True, encoding='utf-8', errors='replace')
            m = re.search(r"CUDA Version:\s*(\d+\.\d+)", nvout)
            if m:
                result["cuda_version"] = m.group(1)
        except:
            pass
    except:
        pass
    return result

def check_python(venv_name):
    """检测 venv 里的 Python 及各依赖包是否齐全 — 用 pip list 快速查询"""
    venv_python = PROJECT_ROOT / venv_name / "Scripts" / "python.exe"
    result = {"exists": False, "version": "", "has_torch": False, "torch_version": "", "missing_pkgs": []}
    if not venv_python.exists():
        return result
    result["exists"] = True
    
    try:
        # 一次子进程查 Python 版本 + torch + 全部已装包
        script = (
            "import sys, json, importlib.metadata\n"
            "print(sys.version)\n"
            "try:\n"
            "    import torch\n"
            "    print(torch.__version__)\n"
            "    print(torch.cuda.is_available())\n"
            "except:\n"
            "    print('')\n"
            "    print('')\n"
            "    print('')\n"
            "pkgs = {d.metadata['Name'].lower(): d.version for d in importlib.metadata.distributions()}\n"
            "print(json.dumps(pkgs))\n"
        )
        out = subprocess.check_output(
            [str(venv_python), "-c", script],
            timeout=30, text=True, encoding='utf-8', errors='replace', stderr=subprocess.DEVNULL
        )
        lines = out.strip().split("\n")
        result["version"] = lines[0].strip() if len(lines) >= 1 else ""
        
        if len(lines) >= 2 and lines[1]:
            result["has_torch"] = True
            result["torch_version"] = lines[1].strip()
        if len(lines) >= 3 and lines[2] == "True":
            result["cuda_available"] = True
        
        # 解析已装包列表
        installed = {}
        if len(lines) >= 4:
            try:
                installed = json.loads(lines[3])
            except:
                pass
        
        # 从 manifest 读取需要哪些包
        VENV_MODEL_MAP = {"venv_tts": "indextts", "venv_latent": "latentsync"}
        model_name = VENV_MODEL_MAP.get(venv_name, venv_name.replace("venv_", ""))
        manifest_path = PROJECT_ROOT / "models" / model_name / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                for pkg_id, dep_info in manifest.get("deps", {}).items():
                    pip_name = dep_info["pip"] if isinstance(dep_info, dict) else pkg_id
                    ver = dep_info.get("ver", "") if isinstance(dep_info, dict) else dep_info
                    # 处理 pip extras 语法，如 imageio[ffmpeg] → imageio
                    has_extras = "[" in pip_name
                    base_name = pip_name.split("[")[0].lower()
                    # 用基础包名（小写）查找
                    installed_ver = installed.get(base_name, "")
                    if not installed_ver:
                        result.setdefault("missing_pkgs", []).append(pip_name)
                    elif ver and not has_extras:
                        # 宽松版本匹配：主版本号一致即可
                        installed_major = ".".join(installed_ver.split(".")[:2])
                        required_major = ".".join(ver.split(".")[:2])
                        if installed_major != required_major:
                            result.setdefault("version_mismatch", []).append(f"{pip_name}（需要 {ver}，实际 {installed_ver}）")
            except:
                pass
    except:
        pass
    
    return result

def check_checkpoints():
    """检测模型文件是否存在"""
    ckpt_tts = PROJECT_ROOT / "checkpoints" / "indextts2"
    ckpt_latent = PROJECT_ROOT / "checkpoints" / "latentsync"
    return {
        "tts_has_gpt": (ckpt_tts / "gpt.pth").exists(),
        "tts_has_s2mel": (ckpt_tts / "s2mel.pth").exists(),
        "latent_has_unet": (ckpt_latent / "latentsync_unet.pt").exists(),
    }

def check_disk_space():
    """检测磁盘空间"""
    try:
        usage = shutil.disk_usage(PROJECT_ROOT)
        free_gb = usage.free / (1024**3)
        return {"free_gb": round(free_gb, 1)}
    except:
        return {"free_gb": 0}

def main():
    report = {
        "gpu": check_gpu(),
        "venv_tts": check_python("venv_tts"),
        "venv_latent": check_python("venv_latent"),
        "checkpoints": check_checkpoints(),
        "disk": check_disk_space(),
        "python_host": sys.version,
    }
    
    # 综合判断
    issues = []
    warnings = []
    
    if not report["gpu"]["has_gpu"]:
        issues.append("❌ 未检测到 NVIDIA 显卡，本工具需要 NVIDIA GPU 才能运行")
    else:
        vram = report["gpu"]["vram_mb"]
        gpu = report["gpu"]["gpu_name"]
        cuda = report["gpu"]["cuda_version"]
        
        if vram < 4000:
            issues.append(f"❌ 显存仅 {vram}MB（{gpu}），需要至少 6GB")
        elif vram < 8000:
            warnings.append(f"⚠️ 显存 {vram}MB（{gpu}），建议 ≥ 8GB，部分模型可能受限")
        else:
            print(f"  GPU: {gpu} ({vram}MB) ✅", file=sys.stderr)
        
        # CUDA 版本校验 + 从 manifest 读取 torch 安装命令
        if cuda:
            print(f"  CUDA: {cuda} ✅", file=sys.stderr)
            cuda_float = float(cuda)
            if cuda_float < MIN_CUDA:
                issues.append(f"❌ CUDA {cuda} 版本过低，需要 ≥ {MIN_CUDA}，请更新 NVIDIA 驱动")
            else:
                # 分别读取 TTS 和 Latent 的 torch 命令
                for vname in ["venv_tts", "venv_latent"]:
                    cmd = get_torch_cmd(vname, cuda)
                    if cmd:
                        report.setdefault("torch_cmds", {})[vname] = cmd
        else:
            warnings.append("⚠️ 未检测到 CUDA 版本，将尝试 CPU 模式（不推荐）")
            report["torch_cmds"] = {
                "venv_tts": "pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu",
                "venv_latent": "pip install torch==2.5.1 torchaudio==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu",
            }
    
    if not report["venv_tts"]["exists"]:
        issues.append("❌ TTS 虚拟环境 (venv_tts) 未创建")
    elif not report["venv_tts"]["has_torch"]:
        issues.append("❌ TTS 环境缺少 torch")
    else:
        if report["venv_tts"].get("missing_pkgs"):
            issues.append(f"⚠️ TTS 环境缺少: {', '.join(report['venv_tts']['missing_pkgs'])}")
        if report["venv_tts"].get("version_mismatch"):
            issues.append(f"⚠️ TTS 版本不匹配: {', '.join(report['venv_tts']['version_mismatch'])}")
    
    if not report["venv_latent"]["exists"]:
        issues.append("❌ 数字人虚拟环境 (venv_latent) 未创建")
    elif not report["venv_latent"]["has_torch"]:
        issues.append("❌ 数字人环境缺少 torch")
    else:
        if report["venv_latent"].get("missing_pkgs"):
            issues.append(f"⚠️ 数字人环境缺少: {', '.join(report['venv_latent']['missing_pkgs'])}")
        if report["venv_latent"].get("version_mismatch"):
            issues.append(f"⚠️ 数字人版本不匹配: {', '.join(report['venv_latent']['version_mismatch'])}")
    
    if not report["checkpoints"]["tts_has_gpt"]:
        issues.append("❌ 模型文件缺失: checkpoints/indextts2/gpt.pth")
    if not report["checkpoints"]["tts_has_s2mel"]:
        issues.append("❌ 模型文件缺失: checkpoints/indextts2/s2mel.pth")
    if not report["checkpoints"]["latent_has_unet"]:
        issues.append("❌ 模型文件缺失: checkpoints/latentsync/latentsync_unet.pt")
    
    if report["disk"]["free_gb"] < 5:
        issues.append(f"❌ 磁盘空间不足: 仅剩 {report['disk']['free_gb']}GB")
    elif report["disk"]["free_gb"] < 20:
        warnings.append(f"⚠️ 磁盘空间: {report['disk']['free_gb']}GB，建议 ≥ 20GB")
    
    report["issues"] = issues
    report["warnings"] = warnings
    report["can_run"] = len(issues) == 0
    
    # 读取历史安装错误日志
    error_log = PROJECT_ROOT / "logs" / "install_errors.log"
    if error_log.exists():
        try:
            log_content = error_log.read_text(encoding="utf-8").strip()
            if log_content:
                report["install_errors"] = log_content.split("\n")[-10:]  # 最近 10 条
        except:
            pass
    
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)

if __name__ == "__main__":
    main()
