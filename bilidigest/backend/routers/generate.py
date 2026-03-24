"""
POST /api/generate — 图文总结 / 小红书图文 / 知识树
GET  /api/history  — 历史生成记录
"""
import json
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from models import GenerateRequest
from database import get_db
from services.generator import generate_summary, generate_xiaohongshu, generate_mindmap

router = APIRouter(prefix="/api", tags=["generate"])


def _load_asset(bv_id: str) -> dict:
    """从数据库加载完整资产数据（含 transcripts/keyframes/knowledge）"""
    db = get_db()
    try:
        row = db.execute("SELECT * FROM assets WHERE id=?", (bv_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"资产 {bv_id} 不存在")
        if row["status"] not in ("ready", "partial"):
            raise HTTPException(400, f"资产 {bv_id} 尚未处理完成（status={row['status']}）")

        asset = dict(row)
        asset["tags"] = json.loads(asset.get("tags", "[]"))

        asset["transcripts"] = [
            dict(r) for r in db.execute(
                "SELECT id,start_time,end_time,text,source FROM transcripts WHERE asset_id=? ORDER BY start_time",
                (bv_id,)
            ).fetchall()
        ]

        asset["keyframes"] = [
            dict(r) for r in db.execute(
                "SELECT id,timestamp,file_path FROM keyframes WHERE asset_id=? ORDER BY timestamp",
                (bv_id,)
            ).fetchall()
        ]

        knowledge = {}
        for r in db.execute(
            "SELECT knowledge_type,content FROM structured_knowledge WHERE asset_id=?",
            (bv_id,)
        ).fetchall():
            knowledge[r["knowledge_type"]] = json.loads(r["content"])
        asset["structured_knowledge"] = knowledge

        return asset
    finally:
        db.close()


def _save_history(asset_ids: list, mode: str, user_prompt: str | None, content: str) -> int:
    asset_ids_json = json.dumps(asset_ids)
    db = get_db()
    try:
        # 同视频同模式只保留最新一条：先删旧的
        db.execute(
            "DELETE FROM generation_history WHERE asset_ids=? AND mode=?",
            (asset_ids_json, mode)
        )
        cur = db.execute(
            "INSERT INTO generation_history(asset_ids,mode,user_prompt,output_content) VALUES(?,?,?,?)",
            (asset_ids_json, mode, user_prompt, content)
        )
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


def _extract_preview(content: dict, mode: str) -> str:
    """从生成内容中提取前100字预览"""
    if mode == "summary":
        return (content.get("abstract") or "")[:100]
    elif mode == "xiaohongshu":
        sections = content.get("sections", [])
        if sections:
            return (sections[0].get("content") or "")[:100]
    elif mode == "mindmap":
        tree = content.get("tree", {})
        children = tree.get("children", [])
        names = [c.get("name", "") for c in children[:5]]
        return " / ".join(names)[:100]
    text = content.get("text", "")
    return text[:100] if text else ""


def _merge_assets(assets: list[dict]) -> dict:
    """合并多个资产数据为一个，供 LLM 使用"""
    if len(assets) == 1:
        return assets[0]
    merged = {
        "id": "+".join(a["id"] for a in assets),
        "title": " + ".join(a["title"] for a in assets),
        "author": ", ".join(dict.fromkeys(a["author"] for a in assets)),
        "description": "\n".join(f"[{a['title']}] {a.get('description','')[:150]}" for a in assets),
        "duration": sum(a.get("duration", 0) for a in assets),
        "tags": [],
        "transcripts": [],
        "keyframes": [],
        "structured_knowledge": {},
    }
    for a in assets:
        # 转写文本加视频来源标记
        for t in a.get("transcripts", []):
            t["text"] = f"[{a['title'][:15]}] {t['text']}"
            merged["transcripts"].append(t)
        merged["keyframes"].extend(a.get("keyframes", []))
        for ktype, content in a.get("structured_knowledge", {}).items():
            if ktype not in merged["structured_knowledge"]:
                merged["structured_knowledge"][ktype] = []
            if isinstance(content, list):
                merged["structured_knowledge"][ktype].extend(content)
            elif isinstance(content, dict):
                merged["structured_knowledge"][ktype] = content
    return merged


@router.post("/generate")
async def generate(req: GenerateRequest):
    if not req.asset_ids:
        raise HTTPException(400, "至少需要一个 asset_id")

    assets = [_load_asset(aid) for aid in req.asset_ids]
    asset = _merge_assets(assets)

    if req.mode == "summary":
        result = await generate_summary(asset, req.user_prompt)
        gen_id = _save_history(
            req.asset_ids, "summary", req.user_prompt,
            json.dumps(result, ensure_ascii=False)
        )
        return {
            "mode": "summary",
            "title": result["title"],
            "abstract": result["abstract"],
            "sections": result["sections"],
            "generation_id": gen_id,
        }

    elif req.mode == "xiaohongshu":
        result = await generate_xiaohongshu(asset, req.user_prompt)
        gen_id = _save_history(
            req.asset_ids, "xiaohongshu", req.user_prompt,
            json.dumps(result, ensure_ascii=False)
        )
        return {
            "mode": "xiaohongshu",
            "title": result["title"],
            "sections": result["sections"],
            "tags": result["tags"],
            "generation_id": gen_id,
        }

    elif req.mode == "mindmap":
        result = await generate_mindmap(asset, req.user_prompt)
        gen_id = _save_history(
            req.asset_ids, "mindmap", req.user_prompt,
            json.dumps(result, ensure_ascii=False)
        )
        return {
            "mode": "mindmap",
            "tree": result["tree"],
            "generation_id": gen_id,
        }

    raise HTTPException(400, f"不支持的 mode: {req.mode}")


@router.get("/generate/cache")
async def get_cached_generation(
    asset_id: str = Query(..., description="视频BV号"),
    mode: str = Query(..., description="生成模式: summary/xiaohongshu/mindmap"),
):
    """查询已有的缓存生成结果，无需重新调 LLM"""
    db = get_db()
    try:
        asset_ids_json = json.dumps([asset_id])
        row = db.execute(
            "SELECT id, output_content, created_at FROM generation_history "
            "WHERE asset_ids=? AND mode=? ORDER BY id DESC LIMIT 1",
            (asset_ids_json, mode)
        ).fetchone()
        if not row:
            return {"cached": False}

        raw = row["output_content"]
        try:
            content = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"cached": False}

        # 按模式构造与 generate 一致的响应格式
        result: dict = {"cached": True, "mode": mode, "generation_id": row["id"]}
        if mode == "summary":
            result["title"] = content.get("title", "")
            result["abstract"] = content.get("abstract", "")
            result["sections"] = content.get("sections", [])
        elif mode == "xiaohongshu":
            result["title"] = content.get("title", "")
            result["sections"] = content.get("sections", [])
            result["tags"] = content.get("tags", [])
        elif mode == "mindmap":
            result["tree"] = content.get("tree", {})
        return result
    finally:
        db.close()


@router.get("/history")
async def list_history(mode: Optional[str] = Query(None, description="按模式筛选: summary/xiaohongshu/mindmap")):
    """返回所有生成历史记录，支持按 mode 筛选"""
    db = get_db()
    try:
        if mode:
            rows = db.execute(
                "SELECT h.*, GROUP_CONCAT(a.title, ', ') as asset_titles "
                "FROM generation_history h "
                "LEFT JOIN json_each(h.asset_ids) je ON 1=1 "
                "LEFT JOIN assets a ON a.id = je.value "
                "WHERE h.mode = ? "
                "GROUP BY h.id "
                "ORDER BY h.created_at DESC",
                (mode,)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT h.*, GROUP_CONCAT(a.title, ', ') as asset_titles "
                "FROM generation_history h "
                "LEFT JOIN json_each(h.asset_ids) je ON 1=1 "
                "LEFT JOIN assets a ON a.id = je.value "
                "GROUP BY h.id "
                "ORDER BY h.created_at DESC"
            ).fetchall()

        items = []
        for row in rows:
            raw = row["output_content"]
            try:
                content = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                content = {"text": raw}
            title = ""
            if isinstance(content, dict):
                title = content.get("title", "")
            preview = _extract_preview(content, row["mode"]) if isinstance(content, dict) else raw[:100]
            items.append({
                "id": row["id"],
                "asset_ids": json.loads(row["asset_ids"]),
                "asset_titles": row["asset_titles"] or "",
                "mode": row["mode"],
                "title": title,
                "preview": preview,
                "user_prompt": row["user_prompt"],
                "content": content,
                "created_at": row["created_at"],
            })
        return {"items": items}
    finally:
        db.close()


@router.get("/history/{history_id}")
async def get_history(history_id: int):
    """获取单条历史记录详情"""
    db = get_db()
    try:
        row = db.execute(
            "SELECT h.*, GROUP_CONCAT(a.title, ', ') as asset_titles "
            "FROM generation_history h "
            "LEFT JOIN json_each(h.asset_ids) je ON 1=1 "
            "LEFT JOIN assets a ON a.id = je.value "
            "WHERE h.id = ? "
            "GROUP BY h.id",
            (history_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")
        raw = row["output_content"]
        try:
            content = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            content = {"text": raw}
        title = content.get("title", "") if isinstance(content, dict) else ""
        return {
            "id": row["id"],
            "asset_ids": json.loads(row["asset_ids"]),
            "asset_titles": row["asset_titles"] or "",
            "mode": row["mode"],
            "title": title,
            "user_prompt": row["user_prompt"],
            "content": content,
            "created_at": row["created_at"],
        }
    finally:
        db.close()
