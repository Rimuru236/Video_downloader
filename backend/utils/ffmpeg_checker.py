"""FFmpeg checker utility"""
import shutil
import subprocess
import logging

logger = logging.getLogger("streamvault.utils")

def check_ffmpeg() -> bool:
    path = shutil.which("ffmpeg")
    if path:
        try:
            # SEC-7: `-version` should return almost instantly — a short,
            # fixed timeout is enough here (unlike the actual transcode in
            # downloader_engine._HardsubPostProcessor, which needs a
            # configurable one). Without it, a hung/misbehaving ffmpeg binary
            # would block startup indefinitely.
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            ver = r.stdout.split("\n")[0]
            logger.info(f"FFmpeg found: {ver}")
            return True
        except subprocess.TimeoutExpired:
            logger.warning("FFmpeg found but `ffmpeg -version` did not respond within 5s")
        except Exception:
            pass
    logger.warning("FFmpeg not found in PATH")
    return False
