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
        """JSON解析容错：去除markdown代码块标记"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        return json.loads(text.strip())


llm_client = LLMClient()
