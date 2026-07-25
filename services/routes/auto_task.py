"""自动流程 — 任务队列引擎 + API"""
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.projects import create_project, update_project
from database.voices import list_voices
from database.videos import list_videos as list_ref_videos
from utils.logger import setup_logger

router = APIRouter(prefix="/api/auto", tags=["自动流程"])
logger = setup_logger("auto_task")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ============================================================
# 任务队列
# ============================================================

_queue: list[dict] = []
_queue_lock = threading.Lock()
_running = False
_current_task: Optional[dict] = None

TTS_URL = "http://127.0.0.1:8101"
LATENT_URL = "http://127.0.0.1:8102"


class AutoTaskRequest(BaseModel):
    """自动任务请求"""
    # 文案（必须是已确定好的文案，自动化不做生成/改写/提取）
    copy_text: str = ""        # 已确定的文案内容
    topic: str = ""            # 仅用于项目命名

    # 音色
    voice_id: int = 0            # 音色ID

    # 参考视频
    ref_video_id: int = 0        # 参考视频ID

    # 字幕模板
    subtitle_template_id: Optional[int] = None

    # 封面模板
    cover_template_id: Optional[int] = None
    cover_title: str = ""
    cover_subtitle: str = ""

    # BGM
    bgm_path: str = ""
    bgm_volume: float = 0.3

    # 发布
    platforms: list[str] = []
    publish_title: str = ""
    publish_tags: list[str] = []
    publish_schedule: Optional[str] = None


def _task_status(task: dict) -> dict:
    """序列化任务状态"""
    return {
        "task_id": task["task_id"],
        "project_id": task["project_id"],
        "project_name": task.get("project_name", ""),
        "status": task["status"],
        "step": task.get("step", ""),
        "progress": task.get("progress", 0),
        "error": task.get("error", ""),
        "created_at": task.get("created_at", ""),
        "started_at": task.get("started_at", ""),
        "finished_at": task.get("finished_at", ""),
    }


def _update_task(task: dict, **kwargs):
    """更新任务状态"""
    task.update(kwargs)
    # 同步更新项目状态
    pid = task.get("project_id")
    if pid and "step" in kwargs:
        update_project(pid, {"status": "running"})


def _run_auto_pipeline(task: dict):
    """后台执行完整自动流水线"""
    global _running, _current_task
    pid = task["project_id"]
    params = task["params"]

    try:
        # ====== 步骤1: 文案校验 ======
        _update_task(task, step="copy", status="processing", progress=5)
        logger.info(f"[自动任务 {task['task_id']}] 步骤1: 文案校验")

        copy_content = params.copy_text.strip()
        if not copy_content:
            raise ValueError("文案不能为空，请先准备文案后再提交自动化任务")

        update_project(pid, {"input_text": copy_content})
        _update_task(task, progress=10)

        # ====== 步骤2: TTS 语音合成 ======
        _update_task(task, step="audio", progress=15)
        logger.info(f"[自动任务 {task['task_id']}] 步骤2: 语音合成")

        # 获取音色信息
        voices_data = list_voices()
        all_voices = voices_data.get("cloned", []) + voices_data.get("preset", [])
        selected_voice = next((v for v in all_voices if v.get("id") == params.voice_id), None)
        if not selected_voice and all_voices:
            selected_voice = all_voices[0]  # fallback 到第一个

        audio_path = selected_voice.get("audio_path", "") if selected_voice else ""

        timeout = httpx.Timeout(connect=10, read=1200, write=30, pool=30)
        with httpx.Client(timeout=timeout) as client:
            r = client.post(f"{TTS_URL}/synthesize", json={
                "text": copy_content,
                "audio_path": str(PROJECT_ROOT / audio_path) if audio_path else "",
                "output_dir": str(PROJECT_ROOT / "outputs" / "audio"),
                "interval_silence": 200,
                "max_text_tokens_per_segment": 120,
            })
        if r.status_code != 200:
            raise RuntimeError(f"TTS 服务错误: {r.text[:300]}")
        tts_result = r.json()

        audio_url = tts_result.get("audio_url", "")
        subtitle_url = tts_result.get("subtitle_url", "")
        if not audio_url:
            raise RuntimeError("TTS 合成失败，未返回音频")

        update_project(pid, {
            "output_audio": audio_url,
            "srt_path": subtitle_url,
            "voice_id": params.voice_id,
        })
        _update_task(task, progress=30)

        # TTS 完成后立即卸载 TTS 模型释放显存/内存（给数字人留空间）
        _unload_tts(task)

        # ====== 步骤3: 数字人生成 ======
        _update_task(task, step="video", progress=35)
        logger.info(f"[自动任务 {task['task_id']}] 步骤3: 数字人生成")

        # 获取参考视频
        ref_videos = list_ref_videos()
        selected_ref = next((v for v in ref_videos if v.get("id") == params.ref_video_id), None)
        if not selected_ref and ref_videos:
            selected_ref = ref_videos[0]

        if not selected_ref:
            raise ValueError("没有可用的参考视频，请先上传")

        avatar_path = selected_ref.get("video_path", "")
        if not avatar_path:
            raise ValueError("参考视频路径为空")

        # 数字人生成（带重试，处理 WinError 10054 连接断开）
        dh_payload = {
            "video_path": str(PROJECT_ROOT / avatar_path) if not Path(avatar_path).is_absolute() else avatar_path,
            "audio_path": str(PROJECT_ROOT / audio_url) if audio_url and not Path(audio_url).is_absolute() else audio_url,
            "output_dir": str(PROJECT_ROOT / "outputs" / "video"),
        }
        dh_result = None
        last_dh_error = ""
        for dh_attempt in range(3):
            try:
                with httpx.Client(timeout=httpx.Timeout(1800)) as client:
                    r = client.post(f"{LATENT_URL}/generate", json=dh_payload)
                if r.status_code != 200:
                    raise RuntimeError(f"数字人服务错误: {r.text[:300]}")
                dh_result = r.json()
                break
            except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_dh_error = str(e)[:200]
                logger.warning(f"[自动任务 {task['task_id']}] 数字人服务连接异常(第{dh_attempt+1}次): {last_dh_error}")
                if dh_attempt < 2:
                    time.sleep(5)
                    continue
                raise RuntimeError(f"数字人服务连接失败(重试3次): {last_dh_error}")

        if not dh_result:
            raise RuntimeError("数字人视频生成失败")

        video_url = dh_result.get("video_url", "")
        if not video_url:
            raise RuntimeError("数字人视频生成失败")

        update_project(pid, {"output_video": video_url})
        _update_task(task, progress=60)

        # 数字人生成完成后立即卸载模型释放显存（给合成步骤留内存）
        _unload_dh(task)

        # ====== 步骤4: 合成（字幕 + 封面 + BGM）=====
        _update_task(task, step="compose", progress=65)
        logger.info(f"[自动任务 {task['task_id']}] 步骤4: 视频合成")

        from routes.compose import compose_video as _compose_func
        compose_body = {
            "video_path": video_url,
            "srt_path": subtitle_url or "",
            "bgm_path": params.bgm_path,
            "bgm_volume": params.bgm_volume,
            "subtitle_template_id": str(params.subtitle_template_id) if params.subtitle_template_id else "",
            "cover_template_id": str(params.cover_template_id) if params.cover_template_id else "",
            "cover_title": params.cover_title,
            "cover_subtitle": params.cover_subtitle,
        }

        try:
            compose_result = _compose_func(compose_body)
        except HTTPException as e:
            raise RuntimeError(f"合成失败: {e.detail}")
        except Exception as e:
            raise RuntimeError(f"合成异常: {str(e)}")

        compose_video_path = compose_result.get("file_url", "")
        cover_url = compose_result.get("cover_url", "")

        update_project(pid, {
            "compose_video": compose_video_path,
            "cover_path": cover_url,
            "cover_title": params.cover_title,
            "cover_subtitle": params.cover_subtitle,
        })
        _update_task(task, progress=85)

        # ====== 步骤5: 发布 ======
        if params.platforms:
            _update_task(task, step="publish", progress=90)
            logger.info(f"[自动任务 {task['task_id']}] 步骤5: 多平台发布 -> {params.platforms}")

            publish_video_path = compose_video_path or video_url
            if not publish_video_path:
                raise RuntimeError("没有可发布的视频")

            from routes.publish import _publish_single, PLATFORM_MAP
            from database.publish import add_record, update_record

            publish_results = []
            for platform in params.platforms:
                if platform not in PLATFORM_MAP:
                    publish_results.append({"platform": platform, "status": "failed", "error": f"不支持的平台: {platform}"})
                    continue

                # 获取该平台已登录的账号
                from database.publish import list_accounts
                accounts = list_accounts(platform)
                active_account = next((a for a in accounts if a.get("status") == "active"), None)
                if not active_account and accounts:
                    active_account = accounts[0]  # fallback
                if not active_account:
                    publish_results.append({"platform": platform, "status": "failed", "error": "未绑定账号"})
                    continue

                account_name = active_account["account_name"]

                # 创建发布记录
                record_id = add_record({
                    "project_id": pid,
                    "platform": platform,
                    "account_name": account_name,
                    "title": params.publish_title or params.topic or "AI生成视频",
                    "description": params.copy_text[:500] if params.copy_text else copy_content[:500],
                    "tags": ",".join(params.publish_tags) if params.publish_tags else "",
                    "video_path": publish_video_path,
                    "cover_path": cover_url,
                })

                try:
                    result = _publish_single(
                        record_id, platform, account_name,
                        str(PROJECT_ROOT / publish_video_path) if not Path(publish_video_path).is_absolute() else publish_video_path,
                        params.publish_title or params.topic or "AI生成视频",
                        params.copy_text[:500] if params.copy_text else copy_content[:500],
                        params.publish_tags,
                        str(PROJECT_ROOT / cover_url) if cover_url and not Path(cover_url).is_absolute() else cover_url,
                        params.publish_schedule,
                    )
                    if result.get("success"):
                        publish_results.append({"platform": platform, "status": "success"})
                    else:
                        publish_results.append({"platform": platform, "status": "failed", "error": result.get("error", "未知错误")[:200]})
                except Exception as e:
                    update_record(record_id, {"status": "failed", "error_message": str(e)[:1000]})
                    publish_results.append({"platform": platform, "status": "failed", "error": str(e)[:200]})

            task["publish_results"] = publish_results
            _update_task(task, progress=98)

        # ====== 完成 ======
        _update_task(task, step="done", status="completed", progress=100, finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        update_project(pid, {"status": "done"})
        logger.info(f"[自动任务 {task['task_id']}] ✅ 全部完成")

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[自动任务 {task['task_id']}] ❌ 失败: {e}\n{tb}")
        _update_task(task, status="failed", error=str(e)[:500], finished_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            update_project(pid, {"status": "failed", "error_message": str(e)[:500]})
        except Exception:
            pass
    finally:
        # 清理 TTS 和数字人模型释放显存/内存
        _cleanup_models(task)

        with _queue_lock:
            global _running
            _running = False
            # _current_task 保留不设 None，让前端能轮询到 publish_results
            # 下一个任务启动时会自动覆盖


def _unload_tts(task: dict):
    """卸载 TTS 模型，释放显存/内存"""
    task_id = task.get("task_id", "unknown")
    try:
        with httpx.Client(timeout=httpx.Timeout(30)) as _c:
            r = _c.post(f"{TTS_URL}/unload", json={})
            logger.info(f"[自动任务 {task_id}] TTS 模型已卸载: {r.status_code}")
    except Exception as _e:
        logger.warning(f"[自动任务 {task_id}] TTS 卸载失败(可忽略): {_e}")


def _unload_dh(task: dict):
    """卸载数字人模型，释放显存/内存"""
    task_id = task.get("task_id", "unknown")
    try:
        with httpx.Client(timeout=httpx.Timeout(30)) as _c:
            r = _c.post(f"{LATENT_URL}/unload", json={})
            logger.info(f"[自动任务 {task_id}] 数字人模型已卸载: {r.status_code}")
    except Exception as _e:
        logger.warning(f"[自动任务 {task_id}] 数字人模型卸载失败(可忽略): {_e}")


def _cleanup_models(task: dict):
    """清理 TTS 和数字人模型，释放显存/内存"""
    task_id = task.get("task_id", "unknown")

    # 1. 卸载 TTS 模型（步骤2之后可能已经卸载了，这里做兜底）
    _unload_tts(task)

    # 2. 卸载数字人模型
    _unload_dh(task)

    # 3. 本地 Python 垃圾回收
    import gc
    gc.collect()
    logger.info(f"[自动任务 {task_id}] 本地 GC 完成")


def _process_queue():
    """队列消费线程 — 串行执行"""
    global _running, _current_task
    while True:
        with _queue_lock:
            if not _queue or _running:
                time.sleep(1)
                continue
            task = _queue.pop(0)
            _running = True
            _current_task = task  # 新任务覆盖旧任务

        task["status"] = "processing"
        task["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        update_project(task["project_id"], {"status": "running"})

        _run_auto_pipeline(task)

        # 任务完成后，保留 _current_task 30 秒供前端轮询 publish_results
        time.sleep(0.5)
        # 如果没有新任务排队，延迟清空 current 让前端有时间读取结果
        for _ in range(60):  # 最多等 30 秒
            with _queue_lock:
                if _queue:
                    break  # 有新任务排队了，直接开始下一个
            time.sleep(0.5)
        else:
            # 30 秒内没有新任务，清空 current
            with _queue_lock:
                if not _queue:
                    _current_task = None


# 启动队列消费线程
_queue_thread = threading.Thread(target=_process_queue, daemon=True)
_queue_thread.start()


# ============================================================
# API 接口
# ============================================================

def _task_fingerprint(params: AutoTaskRequest) -> str:
    """生成任务指纹，用于判断是否重复提交"""
    return f"{params.voice_id}|{params.ref_video_id}|{params.copy_text[:200]}|{params.topic[:100]}"


@router.post("/submit")
def submit_task(data: AutoTaskRequest):
    """提交自动任务到队列"""
    fingerprint = _task_fingerprint(data)

    # 检查是否已有相同任务在队列中或正在执行
    with _queue_lock:
        for t in _queue:
            if _task_fingerprint(t["params"]) == fingerprint:
                raise HTTPException(409, "该任务已在队列中，请勿重复添加")
        if _current_task and _task_fingerprint(_current_task["params"]) == fingerprint:
            raise HTTPException(409, "该任务正在执行中，请勿重复添加")

    # 创建项目
    project_name = data.topic or "自动任务"
    project = create_project(project_name)
    pid = project["id"]

    task = {
        "task_id": uuid.uuid4().hex[:8],
        "project_id": pid,
        "project_name": project_name,
        "status": "queued",
        "step": "",
        "progress": 0,
        "error": "",
        "params": data,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "started_at": "",
        "finished_at": "",
        "publish_results": [],
    }

    with _queue_lock:
        _queue.append(task)
        position = len(_queue)

    logger.info(f"[自动任务] 已入队: {task['task_id']} (项目: {pid}), 队列位置: {position}")

    return {
        "task_id": task["task_id"],
        "project_id": pid,
        "status": "queued",
        "queue_position": position,
        "message": "任务已添加到队列" + (f"，前面还有 {position - 1} 个任务" if position > 1 else ""),
    }


@router.get("/queue")
def get_queue():
    """获取队列状态"""
    with _queue_lock:
        items = [_task_status(t) for t in _queue]

    current = _task_status(_current_task) if _current_task else None
    # 补充 publish_results
    if current and _current_task and _current_task.get("publish_results"):
        current["publish_results"] = _current_task["publish_results"]

    return {
        "running": _running,
        "current": current,
        "queue": items,
        "queue_count": len(items),
    }


@router.get("/queue/{task_id}")
def get_task(task_id: str):
    """获取单个任务状态"""
    with _queue_lock:
        for t in _queue:
            if t["task_id"] == task_id:
                return _task_status(t)

    if _current_task and _current_task["task_id"] == task_id:
        result = _task_status(_current_task)
        if _current_task.get("publish_results"):
            result["publish_results"] = _current_task["publish_results"]
        return result

    raise HTTPException(404, "任务不存在")


@router.post("/queue/{task_id}/cancel")
def cancel_task(task_id: str):
    """取消队列中的任务（不能取消正在执行的任务）"""
    with _queue_lock:
        for i, t in enumerate(_queue):
            if t["task_id"] == task_id:
                removed = _queue.pop(i)
                update_project(removed["project_id"], {"status": "draft"})
                return {"success": True, "message": "任务已取消"}

    if _current_task and _current_task["task_id"] == task_id:
        raise HTTPException(400, "任务正在执行中，无法取消")

    raise HTTPException(404, "任务不存在")


@router.delete("/queue")
def clear_queue():
    """清空等待队列（不影响正在执行的任务）"""
    with _queue_lock:
        count = len(_queue)
        for t in _queue:
            update_project(t["project_id"], {"status": "draft"})
        _queue.clear()

    return {"success": True, "message": f"已清空 {count} 个等待任务"}
