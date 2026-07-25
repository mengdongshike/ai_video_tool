"""项目管理 + 文案 + 品牌词"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from database import *

router = APIRouter(prefix="/api", tags=["项目"])

class ProjectCreate(BaseModel):
    name: str = "新项目"

@router.get("/projects")
def projects_list():
    return list_projects()

@router.get("/projects/stats")
def projects_stats():
    ps = list_projects()
    return {"total": len(ps), "draft": sum(1 for p in ps if p["status"]=="draft"), "done": sum(1 for p in ps if p["status"]=="done")}

@router.post("/projects")
def projects_create(data: ProjectCreate):
    return create_project(data.name)

@router.get("/projects/{id}")
def projects_get(id: str):
    p = get_project(id)
    if not p: raise HTTPException(404)
    return p

@router.put("/projects/{id}")
def projects_update(id: str, body: dict = Body(...)):
    p = update_project(id, body)
    if not p: raise HTTPException(404)
    return p

@router.delete("/projects/{id}")
def projects_delete(id: str):
    delete_project(id)
    return {"success": True}

@router.post("/projects/{id}/start")
def projects_start(id: str):
    update_project(id, {"status": "running"})
    return {"success": True}

@router.post("/projects/{id}/complete")
def projects_complete(id: str):
    update_project(id, {"status": "done"})
    return {"success": True}

@router.post("/projects/{id}/fail")
def projects_fail(id: str):
    update_project(id, {"status": "failed"})
    return {"success": True}

# ====== 文案 ======

@router.post("/copy/generate")
async def copy_generate(body: dict = Body(...)):
    topic = body.get("topic","") or body.get("prompt","")
    style = body.get("style","口语闲聊风")
    persona = body.get("persona", "知心姐姐")
    length = body.get("length", 200)
    brand_words = body.get("brand_words", "")
    language = body.get("language", "中文")
    try:
        from utils.llm_client import generate_copy
        content = await generate_copy(topic=topic, style=style, persona=persona,
                                      length=length, brand_words=brand_words,
                                      language=language)
    except Exception as e:
        return {"error": str(e)}
    pid = body.get("pid")
    if pid:
        update_project(pid, {"input_text": content})
    return {"content": content, "word_count": len(content)}

@router.post("/copy/optimize")
async def copy_optimize(body: dict = Body(...)):
    content = body.get("content","") or "优化文案"
    style = body.get("style","口语闲聊风")
    persona = body.get("persona", "知心姐姐")
    length = body.get("length", 200)
    brand_words = body.get("brand_words", "")
    language = body.get("language", "中文")
    try:
        from utils.llm_client import optimize_copy
        result = await optimize_copy(content=content, style=style, persona=persona,
                                      length=length, brand_words=brand_words,
                                      language=language)
    except Exception as e:
        return {"error": str(e)}
    pid = body.get("pid")
    if pid:
        update_project(pid, {"input_text": result})
    return {"content": result}

# ====== 品牌词 ======

@router.get("/copy/brand-words")
def brand_words_get():
    return get_brand_words()

@router.post("/copy/brand-words")
def brand_words_add(body: dict = Body(...)):
    return add_brand_word(body.get("word",""))

@router.delete("/copy/brand-words/{word}")
def brand_words_delete(word: str):
    from urllib.parse import unquote
    return delete_brand_word(unquote(word))

# ====== 音频 ======

@router.get("/audio/duration")
def audio_duration(body: dict = Body({})):
    return {"duration": 30}
