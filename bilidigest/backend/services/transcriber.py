"""
字幕获取 + Whisper 转写降级
优先使用 B 站字幕，无字幕时用 faster-whisper 转写
"""
import asyncio
import os
from typing import Optional
from services.bilibili import get_subtitle_url, download_subtitle

WHISPER_TIMEOUT = 1800  # 30 分钟


async def get_transcripts(bv_id: str, cid: int, audio_path: str) -> tuple[list, str]:
    """
    返回 (segments, source)
    segments: [{start_time, end_time, text}]
    source: 'subtitle' | 'whisper'
    """
    # 优先尝试获取 B 站字幕
    try:
        subtitle_url = await get_subtitle_url(bv_id, cid)
        if subtitle_url:
            segments = await download_subtitle(subtitle_url)
            if segments:
                return segments, "subtitle"
    except Exception:
        pass  # 字幕获取失败，降级到 Whisper

    # 降级：faster-whisper 转写（带超时保护）
    segments = await _whisper_transcribe(audio_path)
    return segments, "whisper"


def _whisper_sync(audio_path: str) -> list:
    """同步执行 faster-whisper 转写（在线程池中运行）"""
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segs, _info = model.transcribe(audio_path, language="zh", beam_size=1, vad_filter=True)

    segments = []
    for seg in segs:
        text = seg.text.strip()
        if text:
            segments.append({
                "start_time": seg.start,
                "end_time": seg.end,
                "text": text,
            })
    return segments


async def _whisper_transcribe(audio_path: str) -> list:
    """调用 faster-whisper base 模型转写音频，带超时保护"""
    loop = asyncio.get_event_loop()
    try:
        segments = await asyncio.wait_for(
            loop.run_in_executor(None, _whisper_sync, audio_path),
            timeout=WHISPER_TIMEOUT,
        )
        return segments
    except asyncio.TimeoutError:
        raise RuntimeError(f"Whisper 转写超时（超过 {WHISPER_TIMEOUT // 60} 分钟）")
