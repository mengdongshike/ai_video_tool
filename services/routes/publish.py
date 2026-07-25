"""发布相关路由 - 多平台队列发布 + 模拟人工操作"""
import sys
import subprocess
import threading
import json
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict

from utils.logger import get_logger
from database.publish import (
    list_accounts, get_account, add_account, update_account_status, delete_account,
    list_records, add_record, update_record,
)

logger = get_logger("publish")

router = APIRouter(prefix="/api/publish", tags=["publish"])

SAU_DIR = Path(__file__).parent.parent.parent / "models" / "social-auto-upload"
PYTHON_EXE = sys.executable

PLATFORM_MAP = {
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "kuaishou": "快手",
    "tencent": "视频号",
}

PLATFORM_COLORS = {
    "douyin": "#fe2c55",
    "xiaohongshu": "#ff2442",
    "kuaishou": "#ff4906",
    "tencent": "#07c160",
}

COOKIE_DIR = SAU_DIR / "cookies"
COOKIE_DIR.mkdir(exist_ok=True)

# ============================================================
# 发布队列状态管理
# ============================================================
_queue_lock = threading.Lock()
_queue_state: Dict[str, dict] = {}  # batch_id -> { items: [...], all_done: bool }
_queue_running = False


def _init_queue_state(batch_id: str, platforms: list):
    """初始化队列状态"""
    items = []
    for p in platforms:
        items.append({
            "platform": p,
            "platform_name": PLATFORM_MAP.get(p, p),
            "status": "pending",
            "step": "等待中",
            "record_id": 0,
            "error": None,
        })
    with _queue_lock:
        _queue_state[batch_id] = {
            "batch_id": batch_id,
            "items": items,
            "all_done": False,
        }


def _update_queue_item(batch_id: str, platform: str, **kwargs):
    """更新队列中某个平台的状态"""
    with _queue_lock:
        if batch_id not in _queue_state:
            return
        for item in _queue_state[batch_id]["items"]:
            if item["platform"] == platform:
                item.update(kwargs)
                break


def _set_queue_done(batch_id: str):
    """标记队列全部完成"""
    with _queue_lock:
        if batch_id in _queue_state:
            _queue_state[batch_id]["all_done"] = True


# ============================================================
# 工具函数
# ============================================================

def convert_electron_cookies_to_storage_state(electron_cookies: list) -> dict:
    """将 Electron cookies 转换为 playwright storage_state 格式"""
    cookies = []
    for c in electron_cookies:
        cookie = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
            "expires": c.get("expirationDate", -1),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": "Lax" if c.get("sameSite") == "no_restriction" else "Strict",
        }
        if cookie["expires"] and cookie["expires"] > 0:
            cookie["expires"] = float(cookie["expires"])
        else:
            cookie["expires"] = -1
        cookies.append(cookie)
    return {"cookies": cookies, "origins": []}


def save_storage_state(platform: str, account_name: str, storage_state: dict) -> Path:
    """保存 storage_state 到文件"""
    cookie_file = COOKIE_DIR / f"{platform}_{account_name}.json"
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, ensure_ascii=False, indent=2)
    return cookie_file


def run_sau_command(args: list, timeout: int = 600):
    """运行 sau 命令，返回 subprocess.CompletedProcess（不抛 HTTPException，适合后台调用）

    Playwright 会自动打开系统 Chrome 浏览器 GUI，不需要控制台窗口。
    通过管道捕获 stdout/stderr 用于判断发布是否成功。
    """
    import os
    import shlex
    import platform

    is_headed = "--headed" in args
    is_windows = platform.system() == "Windows"

    logger.info(f"执行 SAU 命令 (headed={is_headed}, platform={platform.system()}): {' '.join(shlex.quote(a) for a in args)}")

    code = f"""
import sys
sys.path.insert(0, {str(SAU_DIR)!r})
from sau_cli import main
sys.argv = ['sau_cli.py'] + {args!r}
sys.exit(main())
"""
    cmd = [PYTHON_EXE, "-c", code]
    env = os.environ.copy()
    # 确保子进程继承完整的桌面环境变量（Playwright 需要这些来启动系统 Chrome）
    for key in ["DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"]:
        if key in os.environ and key not in env:
            env[key] = os.environ[key]

    # Windows 下子进程统一使用 CREATE_NO_WINDOW，不弹控制台窗口
    popen_kwargs = {
        "cwd": str(SAU_DIR),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if is_windows:
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            logger.error(f"SAU 命令超时: {' '.join(args[:3])}")
            return subprocess.CompletedProcess(cmd, -1, stdout="", stderr="命令执行超时")

        # 判断发布是否成功：优先检查 stdout 中是否包含成功标记
        combined = (stdout or "") + (stderr or "")
        is_success = False
        success_markers = [
            "发布成功", "开心收工", "upload submitted",
            "video upload submitted", "note upload submitted",
        ]
        for marker in success_markers:
            if marker in combined:
                is_success = True
                break

        if is_success:
            # 实际发布成功，忽略 Playwright 清理阶段的异常退出码
            returncode = 0
            logger.info(f"SAU 命令成功（检测到成功标记）: {args[0] if args else ''} {args[1] if len(args) > 1 else ''}")
        elif returncode != 0:
            err_msg = f"exit={returncode}"
            err_msg += f"\nstdout: {(stdout or '')[-1000:]}\nstderr: {(stderr or '')[-1000:]}"
            logger.error(f"SAU 命令失败: {err_msg}")

        result = subprocess.CompletedProcess(cmd, returncode, stdout=stdout or "", stderr=stderr or "")
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"SAU 命令超时: {' '.join(args[:3])}")
        return subprocess.CompletedProcess(cmd, -1, stdout="", stderr="命令执行超时")
    except Exception as e:
        logger.error(f"SAU 命令异常: {e}")
        return subprocess.CompletedProcess(cmd, -1, stdout="", stderr=f"执行命令失败: {str(e)}")


# ============================================================
# 请求模型
# ============================================================

class AccountCreate(BaseModel):
    platform: str
    account_name: str = "default"


class PublishRequest(BaseModel):
    project_id: str
    platform: str
    account_name: str
    video_path: str
    title: str
    description: str = ""
    tags: List[str] = []
    cover_path: Optional[str] = None
    schedule_time: Optional[str] = None


class BatchPublishRequest(BaseModel):
    project_id: str
    platforms: List[str]
    video_path: str
    title: str
    description: str = ""
    tags: List[str] = []
    cover_path: Optional[str] = None
    schedule_time: Optional[str] = None


# ============================================================
# 账号管理接口（简化版：每平台一个账号）
# ============================================================

@router.get("/accounts")
def get_accounts(platform: Optional[str] = None):
    """获取发布账号列表"""
    accounts = list_accounts(platform)
    for acc in accounts:
        acc["platform_name"] = PLATFORM_MAP.get(acc["platform"], acc["platform"])
        acc["platform_color"] = PLATFORM_COLORS.get(acc["platform"], "#999")
    return accounts


@router.post("/accounts/login")
def login_account(data: AccountCreate):
    """触发 playwright 打开系统 Chrome 进行扫码登录（后台异步执行）"""
    if data.platform not in PLATFORM_MAP:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {data.platform}")

    account_name = data.account_name or "default"
    # 确保数据库有这条记录
    existing = list_accounts(data.platform)
    account_id = None
    for acc in existing:
        if acc["account_name"] == account_name:
            account_id = acc["id"]
            break
    if not account_id:
        account_id = add_account(data.platform, account_name, status="logging")
    else:
        update_account_status(account_id, "logging", None)

    # 后台线程执行 playwright 登录
    def _do_login():
        args = [data.platform, "login", "--account", account_name, "--headed"]
        result = run_sau_command(args, timeout=300)
        if result.returncode == 0:
            update_account_status(account_id, "active", None)
            logger.info(f"[登录] {data.platform} 账号 [{account_name}] 登录成功")
        else:
            err = (result.stderr or result.stdout or "登录失败")[:500]
            update_account_status(account_id, "error", err)
            logger.error(f"[登录] {data.platform} 账号 [{account_name}] 登录失败: {err}")

    threading.Thread(target=_do_login, daemon=True).start()
    return {
        "account_id": account_id,
        "status": "logging",
        "message": "正在打开系统 Chrome 浏览器进行扫码登录，请在新窗口中完成扫码"
    }


@router.post("/cookies/{platform}")
async def save_cookies_from_electron(platform: str, request: Request):
    """[已弃用] 接收 Electron 发来的 cookies（保留兼容旧版本）"""
    if platform not in PLATFORM_MAP:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")

    body = await request.json()
    cookies = body.get("cookies", [])
    account_name = body.get("account_name", "default")

    if not cookies:
        raise HTTPException(status_code=400, detail="cookies 不能为空")

    logger.info(f"收到 {platform} 账号 [{account_name}] 的 cookies: {len(cookies)} 条")

    storage_state = convert_electron_cookies_to_storage_state(cookies)
    save_storage_state(platform, account_name, storage_state)

    accounts = list_accounts(platform)
    for acc in accounts:
        if acc["account_name"] == account_name and acc["status"] == "logging":
            update_account_status(acc["id"], "active", None)
            logger.info(f"账号 {account_name} 状态更新为 active")

    return {"success": True, "count": len(cookies), "account_name": account_name}


@router.post("/accounts/{account_id}/check")
def check_account(account_id: int):
    """检查账号是否有效"""
    acc = get_account(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="账号不存在")

    args = [acc["platform"], "check", "--account", acc["account_name"]]
    result = run_sau_command(args)
    valid = result.returncode == 0

    if valid:
        update_account_status(account_id, "active", None)
    else:
        update_account_status(account_id, "expired", result.stderr[:500] if result.stderr else "Cookie 已过期")

    return {"valid": valid, "account_id": account_id}


@router.delete("/accounts/{account_id}")
def remove_account(account_id: int):
    """删除发布账号"""
    acc = get_account(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="账号不存在")

    cookie_file = SAU_DIR / "cookies" / f"{acc['platform']}_{acc['account_name']}.json"
    if cookie_file.exists():
        try:
            cookie_file.unlink()
        except:
            pass

    delete_account(account_id)
    return {"success": True}


# ============================================================
# 平台状态接口
# ============================================================

@router.get("/platform/status")
def get_platform_status():
    """获取各平台账号绑定状态（每个平台只有一个默认账号）"""
    result = []
    for platform_key, platform_name in PLATFORM_MAP.items():
        accounts = list_accounts(platform_key)
        active_account = None
        for acc in accounts:
            if acc["status"] == "active":
                active_account = acc
                break

        result.append({
            "platform": platform_key,
            "platform_name": platform_name,
            "platform_color": PLATFORM_COLORS.get(platform_key, "#999"),
            "logged_in": active_account is not None,
            "status": active_account["status"] if active_account else "not_logged_in",
            "account_name": active_account["account_name"] if active_account else "",
            "account_id": active_account["id"] if active_account else 0,
        })
    return result


# ============================================================
# 发布记录接口
# ============================================================

@router.get("/records")
def get_publish_records(project_id: Optional[str] = None):
    """获取发布记录"""
    records = list_records(project_id)
    for r in records:
        r["platform_name"] = PLATFORM_MAP.get(r["platform"], r["platform"])
        r["platform_color"] = PLATFORM_COLORS.get(r["platform"], "#999")
    return records


@router.get("/records/{record_id}")
def get_record(record_id: int):
    """获取发布记录状态"""
    records = list_records()
    for r in records:
        if r["id"] == record_id:
            r["platform_name"] = PLATFORM_MAP.get(r["platform"], r["platform"])
            return r
    raise HTTPException(status_code=404, detail="记录不存在")


# ============================================================
# 单平台发布（保留兼容）
# ============================================================

@router.post("/video")
def publish_video(data: PublishRequest):
    """发布视频到指定平台（单平台）"""
    if data.platform not in PLATFORM_MAP:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {data.platform}")

    video_path = Path(data.video_path)
    if not video_path.is_absolute():
        video_path = Path(__file__).parent.parent.parent / data.video_path
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="视频文件不存在")

    record_id = add_record({
        "project_id": data.project_id,
        "platform": data.platform,
        "account_name": data.account_name,
        "title": data.title,
        "description": data.description,
        "tags": ",".join(data.tags),
        "video_path": str(video_path),
        "cover_path": data.cover_path,
        "status": "publishing",
        "scheduled_at": data.schedule_time,
    })

    def _do_publish():
        _publish_single(record_id, data.platform, data.account_name, str(video_path),
                        data.title, data.description, data.tags, data.cover_path, data.schedule_time)

    t = threading.Thread(target=_do_publish, daemon=True)
    t.start()

    return {"record_id": record_id, "status": "publishing", "message": "发布任务已启动"}


# ============================================================
# 批量发布（核心新接口）
# ============================================================

@router.post("/batch")
def publish_batch(data: BatchPublishRequest):
    """多平台批量发布视频"""
    global _queue_running

    # 验证
    if not data.platforms:
        raise HTTPException(status_code=400, detail="请至少选择一个平台")
    for p in data.platforms:
        if p not in PLATFORM_MAP:
            raise HTTPException(status_code=400, detail=f"不支持的平台: {p}")

    video_path = Path(data.video_path)
    if not video_path.is_absolute():
        video_path = Path(__file__).parent.parent.parent / data.video_path
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="视频文件不存在")

    if _queue_running:
        raise HTTPException(status_code=409, detail="当前有发布任务正在进行中，请等待完成")

    # 为每个平台创建发布记录
    batch_id = str(uuid.uuid4())[:8]
    records = []
    for p in data.platforms:
        record_id = add_record({
            "project_id": data.project_id,
            "platform": p,
            "account_name": "default",
            "title": data.title,
            "description": data.description,
            "tags": ",".join(data.tags),
            "video_path": str(video_path),
            "cover_path": data.cover_path,
            "status": "pending",
            "scheduled_at": data.schedule_time,
        })
        records.append({"platform": p, "record_id": record_id})

    # 初始化队列状态
    _init_queue_state(batch_id, data.platforms)
    for item, rec in zip(_queue_state[batch_id]["items"], records):
        item["record_id"] = rec["record_id"]

    # 启动队列发布线程
    def _run_batch():
        global _queue_running
        _queue_running = True
        try:
            for p in data.platforms:
                # 找到对应 record
                rec = next((r for r in records if r["platform"] == p), None)
                if not rec:
                    continue

                record_id = rec["record_id"]

                # 更新数据库状态
                update_record(record_id, {"status": "publishing"})

                # 更新队列状态
                _update_queue_item(batch_id, p, status="publishing", step="正在打开浏览器...")

                # 执行发布
                try:
                    _publish_single_with_steps(batch_id, record_id, p, "default",
                                               str(video_path), data.title, data.description,
                                               data.tags, data.cover_path, data.schedule_time)
                    _update_queue_item(batch_id, p, status="success", step="发布完成")
                except Exception as e:
                    err_msg = str(e)[:500]
                    logger.error(f"[批量发布] {p} 发布失败: {err_msg}")
                    _update_queue_item(batch_id, p, status="failed", step="发布失败", error=err_msg)
                    update_record(record_id, {"status": "failed", "error_message": err_msg})

            _set_queue_done(batch_id)
        finally:
            _queue_running = False

    t = threading.Thread(target=_run_batch, daemon=True)
    t.start()

    return {
        "batch_id": batch_id,
        "records": records,
        "message": f"已加入发布队列，共 {len(data.platforms)} 个平台",
    }


@router.get("/queue/status")
def get_queue_status():
    """获取当前发布队列状态"""
    with _queue_lock:
        if not _queue_state:
            return {"batch_id": "", "items": [], "all_done": True, "running": False}

        # 返回最新的队列
        latest_batch_id = list(_queue_state.keys())[-1]
        state = _queue_state.get(latest_batch_id, {"batch_id": "", "items": [], "all_done": True})
        return {
            **state,
            "running": _queue_running,
        }


# ============================================================
# 内部发布执行函数
# ============================================================

def _publish_single(record_id: int, platform: str, account_name: str,
                    video_path: str, title: str, description: str,
                    tags: list, cover_path: str | None, schedule_time: str | None) -> dict:
    """执行单平台发布，返回 {"success": bool, "error": str}"""
    logger.info(f"[发布#{record_id}] 开始发布: platform={platform}, account={account_name}, title={title}")
    try:
        # ====== 发布前自动确保 cookie 有效 ======
        logger.info(f"[发布#{record_id}] 检查 {platform} 登录状态...")
        login_args = [platform, "login", "--account", account_name, "--headed"]
        login_result = run_sau_command(login_args, timeout=120)
        if login_result.returncode != 0:
            err = (login_result.stderr or login_result.stdout or "登录失败")[:500]
            raise RuntimeError(f"{platform} 登录失败: {err}")
        logger.info(f"[发布#{record_id}] {platform} 登录状态确认完成")

        # 检查视频文件是否存在
        vp = Path(video_path)
        if not vp.is_absolute():
            vp = Path(__file__).parent.parent.parent / video_path
        if not vp.exists():
            err_msg = f"视频文件不存在: {vp}"
            logger.error(f"[发布#{record_id}] {err_msg}")
            update_record(record_id, {"status": "failed", "error_message": err_msg})
            return {"success": False, "error": err_msg}

        args = [
            platform, "upload-video",
            "--account", account_name,
            "--file", str(vp),
            "--title", title,
            "--desc", description or title,
            "--headed",
        ]
        if tags:
            args.extend(["--tags", ",".join(tags)])
        if schedule_time:
            args.extend(["--schedule", schedule_time])
        if cover_path:
            cp = Path(cover_path)
            if not cp.is_absolute():
                cp = Path(__file__).parent.parent.parent / cover_path
            if cp.exists():
                logger.info(f"[发布#{record_id}] 使用封面: {cp}")
                args.extend(["--thumbnail", str(cp)])
            else:
                logger.warning(f"[发布#{record_id}] 封面文件不存在: {cp}")

        result = run_sau_command(args)
        if result.returncode == 0:
            logger.info(f"[发布#{record_id}] 发布成功")
            update_record(record_id, {"status": "success", "error_message": None})
            return {"success": True, "error": ""}
        else:
            err = (result.stderr or "") or (result.stdout or "") or f"发布失败 (exit={result.returncode})"
            if not err.strip():
                err = f"发布进程异常退出 (exit={result.returncode})，请检查浏览器是否能正常启动"
            logger.error(f"[发布#{record_id}] 发布失败: {err[:500]}")
            update_record(record_id, {"status": "failed", "error_message": err[:1000]})
            return {"success": False, "error": err[:200]}
    except Exception as e:
        logger.error(f"[发布#{record_id}] 发布异常: {e}", exc_info=True)
        update_record(record_id, {"status": "failed", "error_message": str(e)[:1000]})
        return {"success": False, "error": str(e)[:200]}


def _publish_single_with_steps(batch_id: str, record_id: int, platform: str, account_name: str,
                                video_path: str, title: str, description: str,
                                tags: list, cover_path: str | None, schedule_time: str | None):
    """执行单平台发布（带步骤更新，读取 stdout 获取真实进度）"""
    logger.info(f"[发布#{record_id}] 开始发布: platform={platform}, account={account_name}, title={title}")

    # 步骤关键词映射：匹配各平台 loguru 输出的实际内容
    # loguru 格式通常是: "时间 | LEVEL | module:function:line - message"
    # 或者更简单的 "LEVEL | message" 格式
    STEP_KEYWORDS = [
        ("搬运视频", "正在上传视频文件（含转码，请耐心等待）..."),
        ("上传视频", "正在上传视频文件（含转码，请耐心等待）..."),
        ("正在上传", "正在上传视频文件（含转码，请耐心等待）..."),
        ("上传前检查通过", "检查通过，正在进入发布页面..."),
        ("正在赶往", "正在进入发布页面..."),
        ("正在打开主页", "正在打开发布页面..."),
        ("进入.*发布页面", "已进入发布页面，正在填写内容..."),
        ("填标题", "正在填写标题和描述..."),
        ("填描述", "正在填写描述和标签..."),
        ("贴了.*话题", "标签设置完成"),
        ("设置封面", "正在设置封面..."),
        ("封面上传完成", "封面上传完成"),
        ("封面.*设置完成", "封面设置完成"),
        ("视频已经传完", "视频上传完成，正在等待发布..."),
        ("冲刺发布", "正在提交发布..."),
        ("发布成功", "发布完成！"),
        ("开心收工", "发布完成！"),
        ("cookie 更新", "清理中..."),
    ]

    try:
        # ====== 发布前自动确保 cookie 有效 ======
        _update_queue_item(batch_id, platform, status="publishing", step="检查登录状态...")
        logger.info(f"[发布#{record_id}] 检查 {platform} 登录状态...")
        login_args = [platform, "login", "--account", account_name, "--headed"]
        login_result = run_sau_command(login_args, timeout=120)
        if login_result.returncode != 0:
            err = (login_result.stderr or login_result.stdout or "登录失败")[:500]
            raise RuntimeError(f"{platform} 登录失败: {err}")
        logger.info(f"[发布#{record_id}] {platform} 登录状态确认完成")

        args = [
            platform, "upload-video",
            "--account", account_name,
            "--file", video_path,
            "--title", title,
            "--desc", description or title,
            "--headed",
        ]
        if tags:
            args.extend(["--tags", ",".join(tags)])
        if schedule_time:
            args.extend(["--schedule", schedule_time])
        if cover_path:
            cp = Path(cover_path)
            if not cp.is_absolute():
                cp = Path(__file__).parent.parent.parent / cover_path
            if cp.exists():
                args.extend(["--thumbnail", str(cp)])

        import os
        import platform
        env = os.environ.copy()

        code = f"""
import sys
sys.path.insert(0, {str(SAU_DIR)!r})
from sau_cli import main
sys.argv = ['sau_cli.py'] + {args!r}
sys.exit(main())
"""
        cmd = [PYTHON_EXE, "-c", code]

        popen_kwargs = {
            "cwd": str(SAU_DIR),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,  # 合并 stderr 到 stdout
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "env": env,
            "bufsize": 1,  # 行缓冲
        }
        if platform.system() == "Windows":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        proc = subprocess.Popen(cmd, **popen_kwargs)

        # 逐行读取 stdout，根据关键词更新步骤
        # Windows 不支持 select() 对管道操作，改用线程 + 阻塞 readline + poll
        import re
        import threading
        current_step = "正在打开浏览器..."
        _update_queue_item(batch_id, platform, status="publishing", step=current_step)

        all_output = []
        start_time = time.time()
        read_done = threading.Event()
        last_output_time = start_time

        def reader_thread():
            nonlocal last_output_time
            try:
                while not read_done.is_set():
                    line = proc.stdout.readline()
                    if not line:
                        break
                    all_output.append(line)
                    last_output_time = time.time()
                    line_stripped = line.strip()
                    logger.info(f"[发布#{record_id}] stdout: {line_stripped}")

                    # 根据关键词正则匹配步骤
                    for keyword, step_text in STEP_KEYWORDS:
                        if re.search(keyword, line_stripped):
                            if current_step != step_text:
                                _update_queue_item(batch_id, platform, step=step_text)
                            break
            except Exception:
                pass

        t = threading.Thread(target=reader_thread, daemon=True)
        t.start()

        try:
            # 最长等待 30 分钟（视频上传可能很久）
            max_wait = 1800
            while proc.poll() is None:
                time.sleep(1)

                elapsed = time.time() - start_time
                # 超时处理：检测到成功标记后如果进程仍不退出，主动 kill
                if elapsed > max_wait:
                    full_output = "".join(all_output)
                    is_success = False
                    for marker in ["发布成功", "开心收工", "upload submitted", "video upload submitted", "note upload submitted"]:
                        if marker in full_output:
                            is_success = True
                            break
                    if is_success:
                        logger.warning(f"[发布#{record_id}] 进程超时但已检测到成功标记，强制终止进程")
                        proc.kill()
                        read_done.set()
                        t.join(timeout=2)
                        update_record(record_id, {"status": "success", "error_message": None})
                        return
                    else:
                        logger.error(f"[发布#{record_id}] 进程超时且无成功标记，强制终止")
                        proc.kill()
                        read_done.set()
                        t.join(timeout=2)
                        update_record(record_id, {"status": "failed", "error_message": "发布超时（30分钟）"})
                        raise RuntimeError("发布超时（30分钟）")

                # 兜底：如果超过 5 分钟没有任何输出，显示等待中
                if elapsed > 300:
                    current_step_val = _queue_state.get(batch_id, {}).get("items", [])
                    current_step_val = next((i.get("step", "") for i in current_step_val if i["platform"] == platform), "")
                    if "上传视频" in current_step_val or "上传中" in current_step_val:
                        minutes = int(elapsed // 60)
                        seconds = int(elapsed % 60)
                        wait_step = f"视频上传中（已等待 {minutes} 分 {seconds} 秒，大文件转码中请耐心等待）..."
                        _update_queue_item(batch_id, platform, step=wait_step)
        finally:
            read_done.set()
            t.join(timeout=2)

        returncode = proc.returncode
        full_output = "".join(all_output)

        # 判断是否成功：优先检测输出中的成功标记，忽略 Playwright 清理阶段的异常退出码
        is_success = returncode == 0
        if not is_success:
            for marker in ["发布成功", "开心收工", "upload submitted", "video upload submitted", "note upload submitted"]:
                if marker in full_output:
                    is_success = True
                    logger.info(f"[发布#{record_id}] 检测到成功标记，忽略非零退出码 {returncode}")
                    break

        if is_success:
            logger.info(f"[发布#{record_id}] 发布成功")
            update_record(record_id, {"status": "success", "error_message": None})
        else:
            err = full_output.strip() or f"发布进程异常退出 (exit={returncode})"
            if not err.strip():
                err = f"发布进程异常退出 (exit={returncode})，请检查浏览器是否能正常启动"
            logger.error(f"[发布#{record_id}] 发布失败: {err[:500]}")
            update_record(record_id, {"status": "failed", "error_message": err[:1000]})
            raise RuntimeError(err[:500])

    except Exception as e:
        logger.error(f"[发布#{record_id}] 发布异常: {e}", exc_info=True)
        update_record(record_id, {"status": "failed", "error_message": str(e)[:1000]})
        raise
