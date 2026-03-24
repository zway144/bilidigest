"""
ffmpeg 关键帧截取：每 60 秒取 1 帧，写入 keyframes 表
"""
import os
import subprocess
from typing import Optional


def _get_ffmpeg_exe() -> str:
    """获取 ffmpeg 可执行路径：系统PATH → WinGet安装路径 → imageio-ffmpeg内置"""
    import shutil, glob
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    # WinGet 安装路径（Windows）
    winget_pattern = os.path.expanduser(
        r"~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\ffmpeg.exe"
    )
    matches = glob.glob(winget_pattern, recursive=True)
    if matches:
        return matches[0]
    # imageio-ffmpeg 内置二进制
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError("未找到 ffmpeg，请安装 ffmpeg 或 pip install imageio-ffmpeg")


def extract_keyframes(video_path: str, output_dir: str, interval: int = 60) -> list[dict]:
    """
    每 interval 秒截一帧，返回 [{timestamp, file_path}]
    file_path 是相对于 data/assets/ 的路径，例如 BVxxx/keyframes/frame_0060.jpg
    """
    keyframes_dir = os.path.join(output_dir, "keyframes")
    os.makedirs(keyframes_dir, exist_ok=True)

    ffmpeg = _get_ffmpeg_exe()
    output_pattern = os.path.join(keyframes_dir, "frame_%04d.jpg")

    cmd = [
        ffmpeg,
        "-i", video_path,
        "-vf", f"fps=1/{interval},scale=1280:-1",
        "-q:v", "3",
        "-y",
        output_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg截帧失败: {result.stderr[-300:]}")

    # 收集截帧结果，计算时间戳
    frames = sorted(f for f in os.listdir(keyframes_dir) if f.endswith(".jpg"))
    results = []
    for fname in frames:
        # frame_0001.jpg → index=1 → timestamp=60s
        idx = int(fname.replace("frame_", "").replace(".jpg", ""))
        timestamp = idx * interval

        # file_path 存储相对于 assets/ 目录的路径
        bv_id = os.path.basename(output_dir)
        rel_path = f"{bv_id}/keyframes/{fname}"
        results.append({"timestamp": float(timestamp), "file_path": rel_path})

    return results
