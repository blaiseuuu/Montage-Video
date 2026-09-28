"""Moteur de rendu : transforme une liste de segments en une vidéo finale.

Toutes les opérations (découpe, assemblage, suppression des silences, projet
YAML) se ramènent à une liste de :class:`Segment` rendue par
:func:`render_segments` en un seul passage FFmpeg.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import ffmpeg
from .presets import FIT_MODES, Preset, get_preset

AUDIO_RATE = 48000


@dataclass
class Segment:
    source: str
    start: float = 0.0
    end: Optional[float] = None  # None = jusqu'à la fin du fichier


@dataclass
class Music:
    path: str
    volume: float = 0.3
    fade_out: float = 2.0


@dataclass
class RenderOptions:
    preset: str = "source"
    fit: str = "pad"
    fade_in: float = 0.0
    fade_out: float = 0.0
    music: Optional[Music] = None
    x264_preset: str = "medium"
    extra: Dict[str, str] = field(default_factory=dict)


def _resolve_segments(segments: List[Segment]) -> Tuple[List[Segment], Dict[str, ffmpeg.MediaInfo]]:
    """Vérifie les segments et remplace les fins implicites par la durée réelle."""
    infos: Dict[str, ffmpeg.MediaInfo] = {}
    resolved = []
    for seg in segments:
        if seg.source not in infos:
            infos[seg.source] = ffmpeg.probe(seg.source)
        info = infos[seg.source]
        if not info.has_video:
            raise ffmpeg.FFmpegError(f"Pas de piste vidéo dans {seg.source}")
        end = info.duration if seg.end is None else min(seg.end, info.duration)
        start = max(0.0, seg.start)
        if end - start <= 0.01:
            raise ValueError(
                f"Segment vide pour {seg.source} ({ffmpeg.format_time(start)} → "
                f"{ffmpeg.format_time(end)})"
            )
        resolved.append(Segment(seg.source, start, end))
    return resolved, infos


def _target_format(preset: Preset, first: ffmpeg.MediaInfo) -> Tuple[int, int, float]:
    width = preset.width or first.width or 1920
    height = preset.height or first.height or 1080
    fps = preset.fps or first.fps or 30
    # libx264 exige des dimensions paires.
    return width - width % 2, height - height % 2, fps


def _scale_filter(width: int, height: int, fit: str) -> str:
    if fit == "crop":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )


def build_command(
    segments: List[Segment], output: str, options: RenderOptions
) -> Tuple[List[str], float]:
    """Construit les arguments FFmpeg. Retourne (arguments, durée finale)."""
    if not segments:
        raise ValueError("Aucun segment à rendre.")
    if options.fit not in FIT_MODES:
        raise ValueError(f"Mode d'adaptation inconnu « {options.fit} » (pad ou crop).")
    preset = get_preset(options.preset)
    segments, infos = _resolve_segments(segments)
    width, height, fps = _target_format(preset, infos[segments[0].source])

    inputs: List[str] = []
    input_index: Dict[str, int] = {}
    for seg in segments:
        if seg.source not in input_index:
            input_index[seg.source] = len(input_index)
            inputs += ["-i", seg.source]

    filters: List[str] = []
    concat_inputs = ""
    scale = _scale_filter(width, height, options.fit)
    for n, seg in enumerate(segments):
        i = input_index[seg.source]
        length = seg.end - seg.start
        filters.append(
            f"[{i}:v]trim=start={seg.start:.3f}:end={seg.end:.3f},setpts=PTS-STARTPTS,"
            f"{scale},setsar=1,fps={fps},format=yuv420p[v{n}]"
        )
        if infos[seg.source].has_audio:
            filters.append(
                f"[{i}:a]atrim=start={seg.start:.3f}:end={seg.end:.3f},asetpts=PTS-STARTPTS,"
                f"aresample={AUDIO_RATE},aformat=channel_layouts=stereo[a{n}]"
            )
        else:
            # Silence de la bonne durée pour garder l'audio synchronisé.
            filters.append(
                f"anullsrc=r={AUDIO_RATE}:cl=stereo,atrim=duration={length:.3f}[a{n}]"
            )
        concat_inputs += f"[v{n}][a{n}]"

    total = sum(seg.end - seg.start for seg in segments)
    filters.append(f"{concat_inputs}concat=n={len(segments)}:v=1:a=1[vcat][acat]")

    vlabel, alabel = "vcat", "acat"
    if options.fade_in > 0 or options.fade_out > 0:
        vf, af = [], []
        if options.fade_in > 0:
            vf.append(f"fade=t=in:st=0:d={options.fade_in:.3f}")
            af.append(f"afade=t=in:st=0:d={options.fade_in:.3f}")
        if options.fade_out > 0:
            st = max(0.0, total - options.fade_out)
            vf.append(f"fade=t=out:st={st:.3f}:d={options.fade_out:.3f}")
            af.append(f"afade=t=out:st={st:.3f}:d={options.fade_out:.3f}")
        filters.append(f"[vcat]{','.join(vf)}[vfade]")
        filters.append(f"[acat]{','.join(af)}[afade]")
        vlabel, alabel = "vfade", "afade"

    if options.music:
        music = options.music
        m = len(input_index)
        inputs += ["-stream_loop", "-1", "-i", music.path]
        music_chain = f"[{m}:a]atrim=duration={total:.3f},volume={music.volume}"
        if music.fade_out > 0:
            st = max(0.0, total - music.fade_out)
            music_chain += f",afade=t=out:st={st:.3f}:d={music.fade_out:.3f}"
        filters.append(
            f"{music_chain},aresample={AUDIO_RATE},aformat=channel_layouts=stereo[music]"
        )
        filters.append(
            f"[{alabel}][music]amix=inputs=2:duration=first:normalize=0[amix]"
        )
        alabel = "amix"

    args = [
        "-y",
        *inputs,
        "-filter_complex", ";".join(filters),
        "-map", f"[{vlabel}]",
        "-map", f"[{alabel}]",
        "-c:v", "libx264",
        "-preset", options.x264_preset,
        "-crf", str(preset.crf),
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
    ]
    for key, value in options.extra.items():
        args += [key, value]
    args.append(output)
    return args, total


def render_segments(
    segments: List[Segment], output: str, options: Optional[RenderOptions] = None
) -> float:
    """Rend les segments dans ``output`` et retourne la durée obtenue."""
    options = options or RenderOptions()
    out_dir = os.path.dirname(os.path.abspath(output))
    os.makedirs(out_dir, exist_ok=True)
    args, total = build_command(segments, output, options)
    ffmpeg.run(args)
    return total


# --- Détection des silences -------------------------------------------------

_SILENCE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


def detect_silences(
    path: str, threshold_db: float = -35.0, min_duration: float = 0.6
) -> List[Tuple[float, float]]:
    """Retourne les intervalles (début, fin) où le son est sous le seuil."""
    info = ffmpeg.probe(path)
    if not info.has_audio:
        raise ffmpeg.FFmpegError(f"Pas de piste audio dans {path}")
    proc = ffmpeg.run(
        [
            "-i", path,
            "-vn",
            "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
            "-f", "null", "-",
        ]
    )
    silences = []
    start = None
    for line in proc.stderr.splitlines():
        ms = _SILENCE_START.search(line)
        if ms:
            start = max(0.0, float(ms.group(1)))
            continue
        me = _SILENCE_END.search(line)
        if me and start is not None:
            silences.append((start, float(me.group(1))))
            start = None
    if start is not None:  # silence jusqu'à la fin du fichier
        silences.append((start, info.duration))
    return silences


def speech_segments(
    path: str,
    threshold_db: float = -35.0,
    min_silence: float = 0.6,
    padding: float = 0.15,
    min_segment: float = 0.2,
) -> List[Segment]:
    """Calcule les passages à garder (hors silences) avec une marge ``padding``."""
    duration = ffmpeg.probe(path).duration
    keep: List[Segment] = []
    cursor = 0.0
    for s_start, s_end in detect_silences(path, threshold_db, min_silence):
        seg_end = min(duration, s_start + padding)
        if seg_end - cursor >= min_segment:
            keep.append(Segment(path, cursor, seg_end))
        cursor = max(cursor, s_end - padding)
    if duration - cursor >= min_segment:
        keep.append(Segment(path, cursor, duration))
    return keep
