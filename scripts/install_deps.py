"""
自动安装缺失依赖
被 Electron 调用，输出 JSON 进度到 stdout
"""
import subprocess, sys, os, json, re, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ["PYTHONIOENCODING"] = "utf-8"

LOG_FILE = PROJECT_ROOT / "logs" / "install_errors.log"

def log_error(msg, detail=""):
    """持久化记录安装错误，包含详细信息"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 60
    entry = f"\n{separator}\n[{timestamp}] {msg}\n"
    if detail:
        entry += f"{detail}\n"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    log_size = LOG_FILE.stat().st_size
    if log_size > 1024 * 1024:  # 超过 1MB 截断
        lines = LOG_FILE.read_text(encoding="utf-8").split("\n")
        LOG_FILE.write_text("\n".join(lines[-500:]), encoding="utf-8")

def report(percent, message, detail="", error=False):
    data = {"percent": percent, "message": message, "detail": detail}
    if error:
        data["error"] = True
    print(json.dumps(data), flush=True)

def run(cmd, timeout=300):
    """运行命令，返回 (exit_code, full_output)"""
    output_lines = []
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace')
    for line in proc.stdout:
        line_s = line.strip()
        if line_s:
            output_lines.append(line_s)
            print(f"  {line_s}", file=sys.stderr)
    ret = proc.wait()
    return ret, "\n".join(output_lines[-50:])  # 只保留最后 50 行

def install_venv(venv_name, torch_pkg, index_url, skip_torch=False):
    venv_python = PROJECT_ROOT / venv_name / "Scripts" / "python.exe"
    if not venv_python.exists():
        report(0, f"❌ {venv_name} 未创建", "")
        return False
    
    pip = PROJECT_ROOT / venv_name / "Scripts" / "pip.exe"
    # venv 名 → 模型目录映射
    VENV_MODEL_MAP = {"venv_tts": "indextts", "venv_latent": "latentsync"}
    model_name = VENV_MODEL_MAP.get(venv_name, venv_name.replace("venv_", ""))
    manifest_path = PROJECT_ROOT / "models" / model_name / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except:
            pass
    
    # 1. 装 torch（除非 skip）
    if not skip_torch and torch_pkg:
        report(10, f"正在安装 {venv_name} 的 torch...", torch_pkg)
        cmd = [str(pip), "install"] + torch_pkg.split() + ["--index-url", index_url]
        ret, out = run(cmd, timeout=600)
        if ret != 0:
            log_error(f"{venv_name} torch 安装失败", out)
            report(0, "❌ 环境安装失败", "请联系运营人员，错误已记录到 logs/install_errors.log", error=True)
            return False
        report(40, f"torch 安装完成 ✅", "")
    
    # 2. 读 manifest.json 的 deps，逐包检查版本并安装
    deps = manifest.get("deps", {})
    failed = []
    if deps:
        total = len(deps)
        for i, (pkg_id, dep_info) in enumerate(deps.items()):
            pip_name = dep_info["pip"] if isinstance(dep_info, dict) else pkg_id
            ver = dep_info.get("ver", "") if isinstance(dep_info, dict) else dep_info
            install_spec = f"{pip_name}=={ver}" if ver else pip_name
            pct = 40 + int((i / total) * 50) if not skip_torch else int((i / total) * 90)
            
            # 检查是否已装且版本正确
            need_install = False
            try:
                out = subprocess.check_output(
                    [str(venv_python), "-c",
                     f"import {pkg_id}; "
                     f"print(getattr({pkg_id}, '__version__', '') or 'ok')"],
                    timeout=10, text=True, stderr=subprocess.DEVNULL)
                actual = out.strip()
                if ver and actual != ver and actual != 'ok':
                    report(pct, f"版本不匹配: {pip_name}（需要 {ver}，实际 {actual}），重新安装...", "")
                    need_install = True
                else:
                    continue  # 已装
            except:
                need_install = True
            
            if need_install:
                report(pct, f"安装 {install_spec}...", "")
                cmd = [str(pip), "install", install_spec]
                ret, out = run(cmd, timeout=120)
                if ret != 0:
                    log_error(f"{pip_name} 安装失败 (cmd: {install_spec})", out)
                    failed.append(pip_name)
    
    if failed:
        report(0, f"❌ 依赖安装失败: {', '.join(failed)}", "请联系运营人员，错误已记录到 logs/install_errors.log", error=True)
        return False
    
    report(90, f"依赖安装完成 ✅", "")
    return True

if __name__ == "__main__":
    args = json.loads(sys.argv[1])
    venv = args["venv"]
    torch_pkg = args["torch_pkg"]
    index_url = args["index_url"]
    
    report(5, f"开始安装 {venv} 依赖...", "")
    ok = install_venv(venv, torch_pkg, index_url, args.get("skip_torch", False))
    
    if ok:
        report(100, f"{venv} 就绪 ✅", "")
    else:
        report(0, f"{venv} 安装失败 ❌", "")
