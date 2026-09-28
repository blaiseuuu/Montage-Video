"""Accès à FFmpeg : localisation du binaire, exécution et analyse des médias."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional


class FFmpegError(RuntimeError):
    """Erreur levée quand FFmpeg est introuvable ou échoue."""


def find_ffmpeg() -> str:
    """Retourne le chemin de FFmpeg.

    Ordre de recherche : variable ``MONTAGE_FFMPEG``, ``ffmpeg`` dans le PATH,
    puis le binaire fourni par le paquet ``imageio-ffmpeg`` s'il est installé.
    """
    env = os.environ.get("MONTAGE_FFMPEG")
    if env:
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    raise FFmpegError(
        "FFmpeg est introuvable. Installez-le (https://ffmpeg.org) ou lancez "
        "`pip install imageio-ffmpeg`, ou définissez MONTAGE_FFMPEG."
    )


def run(args: List[str], quiet: bool = True) -> subprocess.CompletedProcess:
    """Exécute FFmpeg avec ``args`` et lève FFmpegError en cas d'échec."""
    cmd = [find_ffmpeg(), "-hide_banner", "-nostdin", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise FFmpegError(f"FFmpeg a échoué (code {proc.returncode}) :\n{tail}")
    if not quiet and proc.stderr:
        print(proc.stderr)
    return proc


@dataclass
class MediaInfo:
    path: str
    duration: float
    width: Optional[int]
    height: Optional[int]
    fps: Optional[float]
    has_video: bool
    has_audio: bool


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Stream #.*?Video:.*?(\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")


def probe(path: str) -> MediaInfo:
    """Lit la durée, la résolution et les flux d'un fichier sans ffprobe."""
    if not os.path.exists(path):
        raise FFmpegError(f"Fichier introuvable : {path}")
    cmd = [find_ffmpeg(), "-hide_banner", "-nostdin", "-i", path]
    # Sans fichier de sortie, FFmpeg termine en erreur mais affiche les infos.
    stderr = subprocess.run(cmd, capture_output=True, text=True, errors="replace").stderr

    m = _DURATION_RE.search(stderr)
    if not m:
        raise FFmpegError(f"Impossible de lire le média : {path}")
    h, mnt, s = m.groups()
    duration = int(h) * 3600 + int(mnt) * 60 + float(s)

    width = height = None
    fps = None
    video_lines = [l for l in stderr.splitlines() if "Video:" in l and "Stream #" in l]
    if video_lines:
        vm = _VIDEO_RE.search(video_lines[0])
        if vm:
            width, height = int(vm.group(1)), int(vm.group(2))
        fm = _FPS_RE.search(video_lines[0])
        if fm:
            fps = float(fm.group(1))

    return MediaInfo(
        path=path,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        has_video=bool(video_lines),
        has_audio=any("Audio:" in l and "Stream #" in l for l in stderr.splitlines()),
    )


def format_time(seconds: float) -> str:
    """Formate des secondes en ``HH:MM:SS.mmm``."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def parse_time(value) -> float:
    """Convertit ``90``, ``"1:30"``, ``"00:01:30.5"`` ou ``"90s"`` en secondes."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower().rstrip("s")
    parts = text.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"Temps invalide : {value!r}") from None
    if len(nums) > 3:
        raise ValueError(f"Temps invalide : {value!r}")
    total = 0.0
    for n in nums:
        total = total * 60 + n
    return total
