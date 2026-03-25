"""
统一LLM调用封装（OpenAI兼容接口）
阶段二实现：用于知识提取（Map-Reduce）和输出生成
"""
import json
import httpx
from config import settings


class LLMClient:
    def __init__(self):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model
        self.timeout = 120
        self.max_retries = 5

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        """发送聊天请求，返回文本响应（含重试+指数退避）"""
        import asyncio
        last_err = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                last_err = e
                if e.response.status_code == 429:
                    await asyncio.sleep(2 ** attempt * 2)
                    continue
                raise
            except Exception as e:
                last_err = e
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"LLM调用失败（重试{self.max_retries}次）: {last_err}")

    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        """发送请求并解析JSON响应，含容错处理"""
        text = await self.chat(system_prompt, user_prompt)
        return self._parse_json(text)

    def _parse_json(self, text: str) -> dict:
        """JSON解析容错：去除markdown代码块 + 修复LLM常见格式错误"""
        text = text.strip()

        # 去除 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]

        # 第一次尝试直接解析
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # ── 修复策略 ──
        original = text

        # 1. 去除尾部多余逗号（"...,}"/"...],}" → "...}")
        text = _remove_trailing_commas(text)

        # 2. 尝试提取 JSON 对象（找最外层 {...}）
        text = _extract_json_object(text)

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 3. 去除 LLM 常在逗号/冒号后插入的非法换行
        # 例如 {"a": 1, \n "b": 2} → {"a": 1, "b": 2}
        lines = text.split("\n")
        fixed_lines = []
        for line in lines:
            stripped = line.rstrip()
            # 如果行以逗号结尾且下一行不是缩进行，恢复逗号到行尾
            fixed_lines.append(stripped)
        text = "\n".join(fixed_lines)
        # 去除连续空白
        import re
        text = re.sub(r'\s+', ' ', text)

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 4. 最后尝试：逐行解析并重建
        try:
            return _reconstruct_json(original)
        except Exception:
            raise json.JSONDecodeError(
                f"无法解析 LLM 返回的 JSON（已尝试自动修复）\n原始文本：{original[:200]}",
                original, 0
            )


def _remove_trailing_commas(text: str) -> str:
    """去除每个对象/数组末尾的多余逗号"""
    import re
    # 匹配 },] 前面任意空白 + 逗号
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def _extract_json_object(text: str) -> str:
    """提取最外层 JSON 对象（处理 LLM 在 JSON 前后插入的非 JSON 文本）"""
    # 找第一个 { 和最后一个 }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    # 找第一个 [ 和最后一个 ]
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text


def _reconstruct_json(text: str) -> dict:
    """暴力重建：去除所有非 JSON 字符，只保留键值对结构"""
    import re
    # 去除 markdown 残留
    text = re.sub(r'```[^`]*```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    # 去除注释行
    lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('#'):
            continue
        lines.append(line)
    text = '\n'.join(lines)
    # 去除尾部逗号
    text = _remove_trailing_commas(text)
    # 去除 object/array 之间的换行干扰（宽松匹配）
    # {"a": 1\n, "b": 2} → {"a": 1, "b": 2}
    text = re.sub(r'(\n\s*)+\s*,', ',', text)
    text = re.sub(r',\s*\n\s*\)', ')', text)
    return json.loads(text.strip())


llm_client = LLMClient()
