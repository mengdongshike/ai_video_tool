"""模板路由"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from database import *
from utils.upload import save_bgm

router = APIRouter(prefix="/api", tags=["模板"])

@router.get("/templates")
def api_templates_list(type: str = ""):
    return list_templates(type or None)

@router.get("/templates/type/{type}")
def api_templates_by_type(type: str):
    return list_templates(type)

@router.get("/templates/{id}")
def api_templates_get(id: int):
    t = get_template(id)
    if not t: raise HTTPException(404)
    return t

@router.post("/templates")
async def api_templates_create(file: UploadFile = File(...), name: str = Form(""), type: str = Form("sub")):
    file_path = ""
    if type == "bgm":
        file_path = await save_bgm(file)
    return create_template(name or Path(file.filename).stem, type, file_path)

@router.put("/templates/{id}")
def api_templates_update(id: int, body: dict = Body(...)):
    t = update_template(id, body.get("name", ""))
    if not t: raise HTTPException(404)
    return t

@router.delete("/templates/{id}")
def api_templates_delete(id: int):
    delete_template(id)
    return {"success": True}

@router.get("/templates/stats")
def api_templates_stats():
    return {"total": count_templates()}
