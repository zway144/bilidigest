import json
import os
from fastapi import APIRouter, BackgroundTasks, HTTPException
from database import get_db
from config import settings
from models import CreateAssetRequest, CreateAssetResponse, AssetBrief, AssetDetail, TranscriptSegment, KeyframeItem
from services.bilibili import extract_bv_id, get_metadata, download_video, download_audio
from services.transcriber import get_transcripts
from services.keyframe import extract_keyframes
from services.knowledge import extract_knowledge

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("", response_model=CreateAssetResponse, status_code=202)
async def create_asset(req: CreateAssetRequest, bg: BackgroundTasks):
    bv_id = extract_bv_id(req.url)
    if not bv_id:
        raise HTTPException(status_code=422, detail="无效的B站视频URL，请输入包含BV号的链接")

    db = get_db()
    try:
        row = db.execute("SELECT id, status FROM assets WHERE id=?", (bv_id,)).fetchone()
        if row and row["status"] == "ready":
            return CreateAssetResponse(
                id=bv_id, status="ready",
                message="该视频已处理完成", allow_reprocess=True
            )

        # 获取 metadata
        try:
            meta = await get_metadata(bv_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"获取视频信息失败: {e}")

        tags_json = json.dumps(meta.get("tags", []), ensure_ascii=False)

        if row:
            db.execute(
                "UPDATE assets SET url=?,title=?,author=?,description=?,tags=?,duration=?,thumbnail_url=?,status='pending',error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (req.url, meta["title"], meta["author"], meta["description"], tags_json, meta["duration"], meta["thumbnail_url"], bv_id)
            )
        else:
            db.execute(
                "INSERT INTO assets(id,url,title,author,description,tags,duration,thumbnail_url,status) VALUES(?,?,?,?,?,?,?,?,'pending')",
                (bv_id, req.url, meta["title"], meta["author"], meta["description"], tags_json, meta["duration"], meta["thumbnail_url"])
            )
        db.commit()
    finally:
        db.close()

    bg.add_task(process_asset, bv_id, req.url, meta.get("cid", 0))
    return CreateAssetResponse(id=bv_id, status="pending", message="资产创建成功，正在后台处理")


@router.get("", response_model=dict)
async def list_assets():
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM assets ORDER BY created_at DESC").fetchall()
        assets = []
        for row in rows:
            t_count = db.execute("SELECT COUNT(*) FROM transcripts WHERE asset_id=?", (row["id"],)).fetchone()[0]
            k_count = db.execute("SELECT COUNT(*) FROM keyframes WHERE asset_id=?", (row["id"],)).fetchone()[0]
            kn_count = db.execute("SELECT COUNT(DISTINCT knowledge_type) FROM structured_knowledge WHERE asset_id=?", (row["id"],)).fetchone()[0]
            # 摘要预览：从 generation_history 取最新一条 mode=summary 的 abstract
            summary_preview = ""
            gen_row = db.execute(
                "SELECT output_content FROM generation_history WHERE asset_ids LIKE ? AND mode='summary' ORDER BY created_at DESC LIMIT 1",
                (f'%"{row["id"]}"%',)
            ).fetchone()
            if gen_row:
                try:
                    import json as _json
                    gen_content = _json.loads(gen_row["output_content"])
                    summary_preview = (gen_content.get("abstract") or "")[:300]
                except Exception:
                    pass

            brief = AssetBrief(
                id=row["id"], title=row["title"], author=row["author"],
                duration=row["duration"], thumbnail_url=row["thumbnail_url"],
                status=row["status"], created_at=row["created_at"],
                transcript_count=t_count, keyframe_count=k_count, knowledge_count=kn_count
            )
            d = brief.model_dump()
            d["summary_preview"] = summary_preview
            assets.append(d)
        return {"assets": assets}
    finally:
        db.close()


@router.get("/{bv_id}", response_model=dict)
async def get_asset(bv_id: str):
    db = get_db()
    try:
        row = db.execute("SELECT * FROM assets WHERE id=?", (bv_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="资产不存在")

        transcripts = [
            TranscriptSegment(id=r["id"], start_time=r["start_time"], end_time=r["end_time"], text=r["text"], source=r["source"])
            for r in db.execute("SELECT * FROM transcripts WHERE asset_id=? ORDER BY start_time", (bv_id,)).fetchall()
        ]

        keyframes = [
            KeyframeItem(id=r["id"], timestamp=r["timestamp"], file_path=r["file_path"],
                         url=f"/static/assets/{r['file_path']}", ocr_text=r["ocr_text"], description=r["description"])
            for r in db.execute("SELECT * FROM keyframes WHERE asset_id=? ORDER BY timestamp", (bv_id,)).fetchall()
        ]

        knowledge: dict = {}
        for r in db.execute("SELECT knowledge_type, content FROM structured_knowledge WHERE asset_id=?", (bv_id,)).fetchall():
            knowledge[r["knowledge_type"]] = json.loads(r["content"])

        detail = AssetDetail(
            id=row["id"], url=row["url"], title=row["title"], author=row["author"],
            description=row["description"], tags=json.loads(row["tags"] or "[]"),
            duration=row["duration"], thumbnail_url=row["thumbnail_url"],
            status=row["status"], error_message=row["error_message"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            transcripts=transcripts, keyframes=keyframes, structured_knowledge=knowledge
        )
        return detail.model_dump()
    finally:
        db.close()


@router.delete("/{bv_id}")
async def delete_asset(bv_id: str):
    db = get_db()
    try:
        row = db.execute("SELECT id FROM assets WHERE id=?", (bv_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="资产不存在")
        db.execute("DELETE FROM assets WHERE id=?", (bv_id,))
        db.commit()
        return {"message": "资产已删除", "id": bv_id}
    finally:
        db.close()


def _set_status(bv_id: str, status: str, error: str = None):
    db = get_db()
    try:
        db.execute(
            "UPDATE assets SET status=?, error_message=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, error, bv_id)
        )
        db.commit()
    finally:
        db.close()


async def process_asset(bv_id: str, url: str, cid: int):
    """后台全流程：下载 → 转写 → 截帧 → LLM知识提取"""
    import time as _time
    import logging
    logger = logging.getLogger("bilidigest.pipeline")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    asset_dir = str(settings.assets_path / bv_id)
    os.makedirs(asset_dir, exist_ok=True)
    pipeline_start = _time.time()

    # ── 1. 下载 ─────────────────────────────────────────
    _set_status(bv_id, "downloading")
    t0 = _time.time()
    try:
        video_path = download_video(bv_id, url, asset_dir)
        audio_path = download_audio(bv_id, url, asset_dir)
    except Exception as e:
        _set_status(bv_id, "failed", f"下载失败: {e}")
        return
    t_download = _time.time() - t0
    logger.info(f"[{bv_id}] ⬇️  下载完成: {t_download:.1f}s")

    # ── 2. 转写 ─────────────────────────────────────────
    _set_status(bv_id, "transcribing")
    t0 = _time.time()
    try:
        segments, source = await get_transcripts(bv_id, cid, audio_path)
        db = get_db()
        try:
            db.execute("DELETE FROM transcripts WHERE asset_id=?", (bv_id,))
            for seg in segments:
                db.execute(
                    "INSERT INTO transcripts(asset_id,start_time,end_time,text,source) VALUES(?,?,?,?,?)",
                    (bv_id, seg["start_time"], seg["end_time"], seg["text"], source)
                )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        _set_status(bv_id, "failed", f"转写失败: {e}")
        return
    t_transcribe = _time.time() - t0
    logger.info(f"[{bv_id}] 🎙️  转写完成: {t_transcribe:.1f}s (source={source}, segments={len(segments)})")

    # ── 3. 截帧 ─────────────────────────────────────────
    _set_status(bv_id, "extracting_frames")
    t0 = _time.time()
    try:
        frames = extract_keyframes(video_path, asset_dir)
        db = get_db()
        try:
            db.execute("DELETE FROM keyframes WHERE asset_id=?", (bv_id,))
            for f in frames:
                db.execute(
                    "INSERT INTO keyframes(asset_id,timestamp,file_path) VALUES(?,?,?)",
                    (bv_id, f["timestamp"], f["file_path"])
                )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        # 截帧失败不中断，记录但继续
        _set_status(bv_id, "analyzing", f"截帧部分失败: {e}")
        frames = []
    t_keyframes = _time.time() - t0
    logger.info(f"[{bv_id}] 📸 截帧完成: {t_keyframes:.1f}s (frames={len(frames)})")

    # ── 4. LLM 知识提取 ──────────────────────────────────
    _set_status(bv_id, "analyzing")
    t0 = _time.time()
    try:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT id,start_time,end_time,text FROM transcripts WHERE asset_id=? ORDER BY start_time",
                (bv_id,)
            ).fetchall()
            seg_list = [dict(r) for r in rows]
        finally:
            db.close()

        knowledge = await extract_knowledge(seg_list)

        db = get_db()
        try:
            db.execute("DELETE FROM structured_knowledge WHERE asset_id=?", (bv_id,))
            type_map = {
                "arguments": knowledge.get("arguments"),
                "timeline": knowledge.get("timeline"),
                "concepts": knowledge.get("concepts"),
                "conclusions": knowledge.get("conclusions"),
            }
            for ktype, content in type_map.items():
                if content:
                    db.execute(
                        "INSERT INTO structured_knowledge(asset_id,knowledge_type,content) VALUES(?,?,?)",
                        (bv_id, ktype, json.dumps(content, ensure_ascii=False))
                    )
            db.commit()
        finally:
            db.close()

        _set_status(bv_id, "ready")

    except Exception as e:
        # LLM 失败 → partial（转写和截帧已保存）
        _set_status(bv_id, "partial", f"知识提取失败，可重试: {e}")
    t_knowledge = _time.time() - t0
    t_total = _time.time() - pipeline_start
    logger.info(f"[{bv_id}] 🧠 知识提取完成: {t_knowledge:.1f}s")
    logger.info(f"[{bv_id}] ✅ 全流程完成: 总计 {t_total:.1f}s | 下载={t_download:.1f}s 转写={t_transcribe:.1f}s 截帧={t_keyframes:.1f}s 知识={t_knowledge:.1f}s")


async def _reprocess_with_meta(bv_id: str, url: str):
    try:
        meta = await get_metadata(bv_id)
        await process_asset(bv_id, url, meta.get("cid", 0))
    except Exception as e:
        _set_status(bv_id, "failed", str(e))


@router.post("/{bv_id}/reprocess", status_code=202)
async def reprocess_asset(bv_id: str, bg: BackgroundTasks):
    db = get_db()
    try:
        row = db.execute("SELECT id FROM assets WHERE id=?", (bv_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="资产不存在")
        db.execute("UPDATE assets SET status='pending',error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?", (bv_id,))
        db.commit()
    finally:
        db.close()
    # 需要 cid，从 DB 拿 url 重新获取
    url_row = None
    db2 = get_db()
    try:
        url_row = db2.execute("SELECT url FROM assets WHERE id=?", (bv_id,)).fetchone()
    finally:
        db2.close()
    if url_row:
        bg.add_task(_reprocess_with_meta, bv_id, url_row["url"])
    return {"id": bv_id, "status": "pending", "message": "已触发重新处理"}
