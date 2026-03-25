"""
输出生成：图文总结 / 小红书图文 / 知识树
所有模式均返回结构化 JSON，由前端负责渲染
"""
import json
from llm_client import llm_client


def _fmt_time(sec: float) -> str:
    m, s = int(sec // 60), int(sec % 60)
    return f"{m:02d}:{s:02d}"


def _build_context(asset: dict) -> str:
    """构建发送给 LLM 的视频上下文"""
    parts = [f"视频标题：{asset['title']}", f"UP主：{asset['author']}"]
    if asset.get("description"):
        parts.append(f"简介：{asset['description'][:300]}")
    parts.append(f"时长：{_fmt_time(asset['duration'])}")

    # 结构化知识
    knowledge = asset.get("structured_knowledge", {})
    if knowledge.get("timeline"):
        parts.append("\n## 内容时间线")
        for item in knowledge["timeline"]:
            parts.append(f"- [{_fmt_time(item.get('start_time',0))}-{_fmt_time(item.get('end_time',0))}] {item.get('title','')}: {item.get('summary','')}")

    if knowledge.get("arguments"):
        parts.append("\n## 核心论点")
        for item in knowledge["arguments"]:
            parts.append(f"- [{item.get('time_ref','')}] {item.get('text','')} (置信度:{item.get('confidence','')})")

    if knowledge.get("concepts"):
        parts.append("\n## 关键概念")
        for item in knowledge["concepts"]:
            parts.append(f"- {item.get('name','')}: {item.get('definition','')}")

    if knowledge.get("conclusions"):
        conc = knowledge["conclusions"]
        if conc.get("summary"):
            parts.append(f"\n## 结论\n{conc['summary']}")

    # 转写文本（截断）
    transcripts = asset.get("transcripts", [])
    if transcripts:
        parts.append("\n## 转写文本（摘要）")
        text_so_far = 0
        for t in transcripts:
            line = f"[{_fmt_time(t['start_time'])}] {t['text']}"
            parts.append(line)
            text_so_far += len(t["text"])
            if text_so_far > 6000:
                parts.append("... (后续内容省略)")
                break

    return "\n".join(parts)


def _build_keyframe_list(asset: dict) -> list[dict]:
    """构建关键帧列表，带完整 URL 路径（兼容多视频融合）"""
    keyframes = sorted(asset.get("keyframes", []), key=lambda k: k.get("timestamp", 0))
    result = []
    for kf in keyframes:
        ts = _fmt_time(kf["timestamp"])
        # 直接用 file_path（格式 BVxxx/keyframes/frame_XXXX.jpg），兼容多视频融合
        url = f"/static/assets/{kf.get('file_path', '')}"
        result.append({"timestamp": kf["timestamp"], "time_str": ts, "url": url})
    return result


def _find_nearest_keyframe(keyframes: list[dict], target_sec: float) -> str:
    """找到离目标时间最近的关键帧 URL"""
    if not keyframes:
        return ""
    best = min(keyframes, key=lambda kf: abs(kf["timestamp"] - target_sec))
    return best["url"]


# ── 图文总结（结构化 JSON） ────────────────────────────

SUMMARY_SYSTEM = """你是一个专业的视频内容分析师。请根据视频信息生成一篇结构化总结笔记。

严格按以下 JSON 格式输出，不要输出任何其他内容：
{
  "abstract": "200-300字的全片摘要，概括视频核心内容和价值",
  "sections": [
    {
      "time": "00:47",
      "end_time": "01:30",
      "title": "🔥 章节标题（带emoji，简洁有力）",
      "content": "该章节的详细内容描述，2-5段文字，200-500字。要有深度，提炼核心观点。"
    }
  ]
}

要求：
1. abstract 必须200-300字，概括全片要点
2. sections 按视频时间线排列，5-10个章节
3. 每个 section 的 time 是起始时间（MM:SS格式），end_time 是结束时间
4. title 带合适的emoji，简洁有力，10-20字
5. content 要有深度，不要流水账，提炼观点和价值，每个章节200-500字
6. 只输出 JSON，不要包含 markdown 代码块标记"""

SUMMARY_PROMPT = """以下是视频的详细信息：

{context}

{user_prompt_section}

请生成结构化总结（纯JSON格式）："""


async def generate_summary(asset: dict, user_prompt: str | None = None) -> dict:
    """生成图文总结，返回结构化 dict"""
    context = _build_context(asset)
    keyframes = _build_keyframe_list(asset)

    user_section = ""
    if user_prompt:
        user_section = f"用户特别要求：{user_prompt}\n请在总结中侧重用户关注的方向。"

    prompt = SUMMARY_PROMPT.format(
        context=context,
        user_prompt_section=user_section,
    )

    result = await llm_client.chat_json(SUMMARY_SYSTEM, prompt)

    # 为每个 section 匹配最近的关键帧
    for section in result.get("sections", []):
        time_str = section.get("time", "00:00")
        parts = time_str.split(":")
        try:
            target_sec = int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            target_sec = 0
        section["keyframe_url"] = _find_nearest_keyframe(keyframes, target_sec)
        # 构建 time_refs
        end_time = section.pop("end_time", "")
        if end_time:
            section["time_refs"] = [f"{time_str}-{end_time}"]
        else:
            section["time_refs"] = [time_str]

    return {
        "title": f"{asset['title']} - 总结笔记",
        "abstract": result.get("abstract", ""),
        "sections": result.get("sections", []),
    }


# ── 小红书图文 ────────────────────────────────────────

XHS_SYSTEM = """你是一个小红书爆款内容创作者。请根据视频信息生成一篇小红书风格的图文笔记。

严格按以下 JSON 格式输出，不要输出任何其他内容：
{
  "title": "emoji标题，吸引人，20字以内",
  "sections": [
    {
      "subtitle": "emoji小标题",
      "content": "正文内容，100-200字，口语化、有趣、有料"
    }
  ],
  "tags": ["#tag1", "#tag2", "#tag3"]
}

要求：
1. 标题要吸引人，带emoji，20字以内
2. 正文分3-6个小段，每段有emoji小标题
3. 每段正文100-200字，口语化、有趣、有料
4. 结尾加上5-10个相关tag（#开头）
5. 只输出 JSON，不要包含 markdown 代码块标记"""

XHS_PROMPT = """以下是视频的详细信息：

{context}

{user_prompt_section}

请生成小红书图文（纯JSON格式）："""


async def generate_xiaohongshu(asset: dict, user_prompt: str | None = None) -> dict:
    """生成小红书图文，返回结构化 dict"""
    context = _build_context(asset)
    keyframes = _build_keyframe_list(asset)

    user_section = ""
    if user_prompt:
        user_section = f"用户特别要求：{user_prompt}"

    prompt = XHS_PROMPT.format(
        context=context,
        user_prompt_section=user_section,
    )

    result = await llm_client.chat_json(XHS_SYSTEM, prompt)

    # 为每个 section 均匀分配关键帧
    sections = result.get("sections", [])
    if keyframes and sections:
        step = max(1, len(keyframes) // len(sections))
        for i, section in enumerate(sections):
            kf_idx = min(i * step, len(keyframes) - 1)
            section["keyframe_url"] = keyframes[kf_idx]["url"]
    else:
        for section in sections:
            section["keyframe_url"] = ""

    return {
        "title": result.get("title", ""),
        "sections": sections,
        "tags": result.get("tags", []),
    }


# ── 知识树（Mindmap） ────────────────────────────────────

MINDMAP_SYSTEM = """你是一个知识结构化专家。请根据视频信息生成一个知识树结构。

严格按以下 JSON 格式输出，不要输出任何其他内容：
{
  "name": "视频主题（简短概括）",
  "children": [
    {
      "name": "章节/主题1",
      "children": [
        { "name": "具体论点或知识点1" },
        { "name": "具体论点或知识点2" }
      ]
    },
    {
      "name": "章节/主题2",
      "children": [
        { "name": "具体论点或知识点3" },
        {
          "name": "子主题",
          "children": [
            { "name": "更细的知识点" }
          ]
        }
      ]
    }
  ]
}

要求：
1. 根节点是视频的核心主题
2. 第一层子节点是视频的主要章节或核心主题（3-8个）
3. 第二层是每个章节下的具体论点、概念或知识点（每个章节2-5个）
4. 如有必要可以有第三层（更细分的知识点）
5. 每个节点的 name 简洁明确，10-30字
6. 只输出 JSON，不要包含 markdown 代码块标记"""

MINDMAP_PROMPT = """以下是视频的详细信息：

{context}

{user_prompt_section}

请生成知识树结构（纯JSON格式）："""


async def generate_mindmap(asset: dict, user_prompt: str | None = None) -> dict:
    """生成知识树，返回树状 dict"""
    context = _build_context(asset)

    user_section = ""
    if user_prompt:
        user_section = f"用户特别要求：{user_prompt}"

    prompt = MINDMAP_PROMPT.format(
        context=context,
        user_prompt_section=user_section,
    )

    try:
        tree = await llm_client.chat_json(MINDMAP_SYSTEM, prompt)
    except Exception:
        # JSON 完全损坏时返回基于 transcript 的简单章节树作为兜底
        transcripts = asset.get("transcripts", [])
        if transcripts:
            chunk_size = max(1, len(transcripts) // 5)
            children = []
            for i in range(0, min(len(transcripts), 25), chunk_size):
                chunk = transcripts[i:i+chunk_size]
                text = chunk[0].get("text", "")[:20] if chunk else ""
                children.append({"name": text, "children": []})
            tree = {"name": "内容概览", "children": children}
        else:
            tree = {"name": "暂无内容", "children": []}

    return {"tree": tree}
