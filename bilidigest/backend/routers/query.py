"""
POST /api/query — 基于资产的AI对话查询
FTS5检索相关transcript + LLM生成回答
"""
import json
from fastapi import APIRouter, HTTPException

from models import QueryRequest
from database import get_db
from llm_client import llm_client

router = APIRouter(prefix="/api/query", tags=["query"])

QUERY_SYSTEM = """你是一个视频内容问答助手。根据提供的视频转写文本片段，回答用户的问题。

要求：
1. 只基于提供的内容回答，不要编造信息
2. 回答要具体，引用视频中的原文或时间点
3. 如果提供的内容不足以回答问题，诚实说明
4. 回答用中文，300字以内"""

QUERY_PROMPT = """视频信息：
标题：{title}
UP主：{author}

相关转写片段：
{segments}

用户问题：{question}

请回答："""


def _fmt_time(sec: float) -> str:
    m, s = int(sec // 60), int(sec % 60)
    return f"{m:02d}:{s:02d}"


@router.post("")
async def query(req: QueryRequest):
    if not req.asset_ids:
        raise HTTPException(400, "至少需要一个 asset_id")
    if not req.question.strip():
        raise HTTPException(400, "问题不能为空")

    db = get_db()
    try:
        # 验证资产存在
        asset = db.execute("SELECT id,title,author FROM assets WHERE id=?", (req.asset_ids[0],)).fetchone()
        if not asset:
            raise HTTPException(404, f"资产 {req.asset_ids[0]} 不存在")

        # 提取关键词（中文按单字/双字切片 + 空格分词）
        import re as _re
        question = req.question.strip()
        raw_words = _re.split(r'[\s，。？！、：；\u201c\u201d\u2018\u2019（）\?\!,\.]+', question)
        keywords = [w for w in raw_words if len(w) >= 2]
        # 对长词再按单字拆分（应对简繁体差异）
        extra_chars = set()
        for w in keywords:
            for ch in w:
                if '\u4e00' <= ch <= '\u9fff':
                    extra_chars.add(ch)
        # 用单字 LIKE 搜索（更宽泛，兼容繁简体共有汉字）
        search_terms = keywords + [ch for ch in list(extra_chars)[:8] if ch not in "的了是在有"]
        search_terms = search_terms[:10]

        # LIKE 搜索
        fts_results = []
        if search_terms:
            like_clause = " OR ".join(["t.text LIKE ?" for _ in search_terms])
            like_params = [f"%{kw}%" for kw in search_terms]
            placeholders = ",".join("?" * len(req.asset_ids))
            fts_results = db.execute(f"""
                SELECT t.id, t.asset_id, t.start_time, t.end_time, t.text
                FROM transcripts t
                WHERE t.asset_id IN ({placeholders})
                AND ({like_clause})
                ORDER BY t.start_time
                LIMIT 20
            """, req.asset_ids + like_params).fetchall()

        # 兜底：均匀采样转写文本，让 LLM 有足够上下文
        if len(fts_results) < 5:
            placeholders = ",".join("?" * len(req.asset_ids))
            all_rows = db.execute(f"""
                SELECT id, asset_id, start_time, end_time, text
                FROM transcripts
                WHERE asset_id IN ({placeholders})
                ORDER BY start_time
            """, req.asset_ids).fetchall()
            existing_ids = {r["id"] for r in fts_results}
            # 均匀采样
            step = max(1, len(all_rows) // 20)
            for i in range(0, len(all_rows), step):
                if all_rows[i]["id"] not in existing_ids:
                    fts_results.append(all_rows[i])
            fts_results = fts_results[:25]

        references = []
        segments_text = []
        for r in fts_results:
            ref = {
                "asset_id": r["asset_id"],
                "asset_title": asset["title"],
                "transcript_id": r["id"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "text": r["text"],
            }
            references.append(ref)
            segments_text.append(
                f"[{_fmt_time(r['start_time'])}-{_fmt_time(r['end_time'])}] {r['text']}"
            )

    finally:
        db.close()

    # LLM 生成回答
    prompt = QUERY_PROMPT.format(
        title=asset["title"],
        author=asset["author"],
        segments="\n".join(segments_text) if segments_text else "（未找到相关内容）",
        question=req.question,
    )

    try:
        answer = await llm_client.chat(QUERY_SYSTEM, prompt)
    except Exception as e:
        answer = f"AI 回答生成失败：{e}\n\n以下是检索到的相关片段，供参考。"

    return {
        "answer": answer,
        "references": references[:10],
    }
