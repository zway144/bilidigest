"""
LLM 结构化知识提取（Map-Reduce）
将转写文本提取为 arguments / timeline / concepts / conclusions 四类知识
"""
import json
import asyncio
from llm_client import llm_client

CHUNK_SIZE = 10000  # 每个 chunk 约字数（增大以减少 LLM 调用次数）

MAP_SYSTEM = """你是一个视频内容分析专家。请从以下视频转写片段中提取结构化信息，输出严格的 JSON。"""

MAP_PROMPT = """以下是视频转写片段（时间段 {time_range}），transcript_ids 为 {ids}：

{text}

请输出 JSON，格式如下：
{{
  "arguments": [
    {{"text": "论点描述", "time_ref": "MM:SS-MM:SS", "transcript_ids": [id列表], "confidence": "high/medium/low"}}
  ],
  "timeline": [
    {{"title": "章节标题", "start_time": 秒数, "end_time": 秒数, "summary": "简述", "transcript_ids": [id列表]}}
  ],
  "concepts": [
    {{"name": "概念名", "definition": "定义", "first_mention_time": 秒数, "transcript_ids": [id列表]}}
  ]
}}
只输出 JSON，不要其他文字。"""

REDUCE_SYSTEM = """你是一个知识整合专家。请将多个视频片段的分析结果合并去重，生成最终的结构化知识。"""

REDUCE_PROMPT = """以下是视频各片段的分析结果，请合并去重后输出最终 JSON：

{chunks_json}

输出格式：
{{
  "arguments": [...],
  "timeline": [...],
  "concepts": [...],
  "conclusions": {{
    "summary": "整体总结（1-3句）",
    "action_items": [
      {{"text": "可行动建议", "transcript_ids": [id列表]}}
    ]
  }}
}}
只输出 JSON，不要其他文字。"""


def _split_chunks(segments: list) -> list[list]:
    """将 transcript segments 按 CHUNK_SIZE 字数拆分为多个 chunk"""
    chunks, cur, cur_len = [], [], 0
    for seg in segments:
        cur.append(seg)
        cur_len += len(seg["text"])
        if cur_len >= CHUNK_SIZE:
            chunks.append(cur)
            cur, cur_len = [], 0
    if cur:
        chunks.append(cur)
    return chunks


def _fmt_time(sec: float) -> str:
    m, s = int(sec // 60), int(sec % 60)
    return f"{m:02d}:{s:02d}"


async def _map_chunk(chunk: list, chunk_idx: int) -> dict:
    """对单个 chunk 调用 LLM 提取知识"""
    ids = [seg["id"] for seg in chunk]
    text = "\n".join(f"[{seg['id']}]{_fmt_time(seg['start_time'])}: {seg['text']}" for seg in chunk)
    time_range = f"{_fmt_time(chunk[0]['start_time'])}-{_fmt_time(chunk[-1]['end_time'])}"
    prompt = MAP_PROMPT.format(time_range=time_range, ids=ids, text=text)
    try:
        result = await llm_client.chat_json(MAP_SYSTEM, prompt)
        return result
    except Exception as e:
        return {"arguments": [], "timeline": [], "concepts": [], "_error": str(e)}


async def extract_knowledge(segments: list) -> dict:
    """
    主入口：对 transcript segments 做 Map-Reduce 知识提取
    返回 {arguments, timeline, concepts, conclusions}
    """
    if not segments:
        return {"arguments": [], "timeline": [], "concepts": [], "conclusions": {"summary": "", "action_items": []}}

    total_text = "".join(s["text"] for s in segments)

    # 短文本直接一次性处理
    if len(total_text) < CHUNK_SIZE:
        chunks_result = [await _map_chunk(segments, 0)]
    else:
        chunks = _split_chunks(segments)
        # 并发 Map（限制并发数避免触发 API 速率限制）
        sem = asyncio.Semaphore(3)

        async def _limited_map(chunk, i):
            async with sem:
                return await _map_chunk(chunk, i)

        tasks = [_limited_map(chunk, i) for i, chunk in enumerate(chunks)]
        chunks_result = await asyncio.gather(*tasks)

    # Reduce：合并所有 chunk 结果
    chunks_json = json.dumps(list(chunks_result), ensure_ascii=False, indent=2)
    prompt = REDUCE_PROMPT.format(chunks_json=chunks_json)
    try:
        final = await llm_client.chat_json(REDUCE_SYSTEM, prompt)
    except Exception as e:
        # Reduce 失败时合并 Map 结果返回 partial
        final = _merge_chunks(chunks_result)
        final["_reduce_error"] = str(e)

    return final


def _merge_chunks(chunks: list) -> dict:
    """Reduce 失败时的简单合并"""
    merged = {"arguments": [], "timeline": [], "concepts": [],
               "conclusions": {"summary": "", "action_items": []}}
    for c in chunks:
        merged["arguments"].extend(c.get("arguments", []))
        merged["timeline"].extend(c.get("timeline", []))
        merged["concepts"].extend(c.get("concepts", []))
    return merged
