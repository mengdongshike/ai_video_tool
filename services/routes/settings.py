"""系统设置路由 — 文案模型选择 + API Key 配置"""
import json
from pathlib import Path
from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/settings", tags=["系统设置"])
SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "settings.json"

def _load():
    if not SETTINGS_FILE.exists():
        return {
            "text_model": "deepseek", 
            "api_key": "", 
            "api_keys": {},
        }
    data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    return data

@router.get("")
def get_settings():
    return _load()

@router.post("")
def save_settings(body: dict = Body(...)):
    data = _load()
    for k in ["text_model", "api_key", "api_keys"]:
        if k in body:
            data[k] = body[k]
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data