from pydantic import BaseModel, field_validator
from typing import Optional, List
import re


# ── 请求体 ──────────────────────────────────────────────
class CreateAssetRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def must_contain_bv(cls, v: str) -> str:
        if not re.search(r"BV[a-zA-Z0-9]{10}", v):
            raise ValueError("无效的B站视频URL，请输入包含BV号的链接")
        # 用户可能粘贴了B站分享文本（标题+URL），提取出纯URL
        url_match = re.search(r"https?://\S+", v)
        if url_match:
            return url_match.group(0)
        return v


class GenerateRequest(BaseModel):
    asset_ids: List[str]
    mode: str  # summary | xiaohongshu | mindmap
    user_prompt: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, v: str) -> str:
        if v not in ("summary", "xiaohongshu", "mindmap"):
            raise ValueError("mode 必须是 summary、xiaohongshu 或 mindmap")
        return v


class QueryRequest(BaseModel):
    asset_ids: List[str]
    question: str


# ── 响应体 ──────────────────────────────────────────────
class AssetBrief(BaseModel):
    id: str
    title: str
    author: str
    duration: int
    thumbnail_url: str
    status: str
    created_at: str
    transcript_count: int = 0
    keyframe_count: int = 0
    knowledge_count: int = 0


class TranscriptSegment(BaseModel):
    id: int
    start_time: float
    end_time: float
    text: str
    source: str


class KeyframeItem(BaseModel):
    id: int
    timestamp: float
    file_path: str
    url: str
    ocr_text: Optional[str] = None
    description: Optional[str] = None


class AssetDetail(BaseModel):
    id: str
    url: str
    title: str
    author: str
    description: str
    tags: List[str]
    duration: int
    thumbnail_url: str
    status: str
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    transcripts: List[TranscriptSegment] = []
    keyframes: List[KeyframeItem] = []
    structured_knowledge: dict = {}


class CreateAssetResponse(BaseModel):
    id: str
    status: str
    message: str
    allow_reprocess: bool = False
