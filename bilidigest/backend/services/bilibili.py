import re
import json
import subprocess
import os
import shutil
import httpx
from typing import Optional


def _find_ffmpeg() -> str:
    """查找 ffmpeg 路径：优先系统 PATH，其次 imageio_ffmpeg 自带的"""
    path = shutil.which("ffmpeg")
    if path:
        return os.path.dirname(path)
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        return os.path.dirname(exe)
    except Exception:
        return ""


FFMPEG_DIR = _find_ffmpeg()


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com",
}


def extract_bv_id(url: str) -> Optional[str]:
    m = re.search(r"(BV[a-zA-Z0-9]{10})", url)
    return m.group(1) if m else None


async def get_metadata(bv_id: str) -> dict:
    """调用B站API获取视频元数据"""
    api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
    async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != 0:
        raise ValueError(f"B站API错误: {data.get('message', '未知错误')}")

    video = data["data"]

    return {
        "title": video.get("title", ""),
        "author": video.get("owner", {}).get("name", ""),
        "description": video.get("desc", ""),
        "tags": _parse_tags(video),
        "duration": video.get("duration", 0),
        "thumbnail_url": video.get("pic", ""),
        "cid": video.get("cid", 0),
    }


def _parse_tags(video: dict) -> list:
    """从视频数据中提取标签列表"""
    tags = []
    # tname 是分区名，pages 里第一个是主视频
    if video.get("tname"):
        tags.append(video["tname"])
    return tags


async def get_subtitle_url(bv_id: str, cid: int) -> Optional[str]:
    """获取字幕URL，无字幕返回None"""
    api_url = f"https://api.bilibili.com/x/player/v2?bvid={bv_id}&cid={cid}"
    async with httpx.AsyncClient(headers=HEADERS, timeout=15) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()
        data = resp.json()

    subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
    if not subtitles:
        return None

    # 优先中文字幕
    for sub in subtitles:
        if "zh" in sub.get("lan", "").lower():
            url = sub.get("subtitle_url", "")
            if url.startswith("//"):
                url = "https:" + url
            return url

    url = subtitles[0].get("subtitle_url", "")
    if url.startswith("//"):
        url = "https:" + url
    return url


def download_video(bv_id: str, url: str, output_dir: str) -> str:
    """用 yt-dlp 下载视频（720p），返回文件路径"""
    video_path = os.path.join(output_dir, "video.mp4")
    # 使用标准化 URL，避免用户分享链接中参数格式问题导致 404
    clean_url = f"https://www.bilibili.com/video/{bv_id}"
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "--merge-output-format", "mp4",
        "-o", video_path,
        "--no-playlist",
        "--retries", "3",
    ]
    if FFMPEG_DIR:
        cmd += ["--ffmpeg-location", FFMPEG_DIR]
    cmd.append(clean_url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp下载失败: {result.stderr[-500:]}")
    return video_path


def download_audio(bv_id: str, url: str, output_dir: str) -> str:
    """用 yt-dlp 只下载音频（mp3），用于 Whisper 转写"""
    audio_path = os.path.join(output_dir, "audio.mp3")
    clean_url = f"https://www.bilibili.com/video/{bv_id}"
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3",
        "-o", audio_path,
        "--no-playlist",
        "--retries", "3",
    ]
    if FFMPEG_DIR:
        cmd += ["--ffmpeg-location", FFMPEG_DIR]
    cmd.append(clean_url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp音频下载失败: {result.stderr[-500:]}")
    return audio_path


async def download_subtitle(subtitle_url: str) -> list:
    """下载字幕JSON，返回分段列表 [{start, end, text}]"""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(subtitle_url)
        resp.raise_for_status()
        data = resp.json()

    segments = []
    for item in data.get("body", []):
        segments.append({
            "start_time": item["from"],
            "end_time": item["to"],
            "text": item["content"],
        })
    return segments
