"""Projets de montage décrits dans un fichier YAML."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import yaml

from .engine import Music, RenderOptions, Segment, render_segments
from .ffmpeg import parse_time


def _path(base: str, value: str) -> str:
    value = os.path.expanduser(str(value))
    return value if os.path.isabs(value) else os.path.join(base, value)


def load_project(path: str) -> Tuple[List[Segment], str, RenderOptions]:
    """Lit un projet YAML et retourne (segments, fichier de sortie, options).

    Les chemins relatifs sont résolus depuis le dossier du fichier projet.
    """
    with open(path, encoding="utf-8") as fh:
        data: Dict[str, Any] = yaml.safe_load(fh) or {}
    base = os.path.dirname(os.path.abspath(path))

    clips = data.get("clips")
    if not clips:
        raise ValueError("Le projet doit contenir une liste « clips ».")

    segments = []
    for n, clip in enumerate(clips, 1):
        if isinstance(clip, str):
            clip = {"source": clip}
        if "source" not in clip:
            raise ValueError(f"Clip n°{n} : champ « source » manquant.")
        segments.append(
            Segment(
                source=_path(base, clip["source"]),
                start=parse_time(clip.get("debut", clip.get("start", 0))),
                end=(
                    parse_time(clip["fin"]) if "fin" in clip
                    else parse_time(clip["end"]) if "end" in clip
                    else None
                ),
            )
        )

    music = None
    music_data = data.get("musique") or data.get("music")
    if music_data:
        if isinstance(music_data, str):
            music_data = {"source": music_data}
        music = Music(
            path=_path(base, music_data["source"]),
            volume=float(music_data.get("volume", 0.3)),
            fade_out=float(music_data.get("fondu_sortie", music_data.get("fade_out", 2.0))),
        )

    options = RenderOptions(
        preset=data.get("format", data.get("preset", "source")),
        fit=data.get("adaptation", data.get("fit", "pad")),
        fade_in=float(data.get("fondu_entree", data.get("fade_in", 0))),
        fade_out=float(data.get("fondu_sortie", data.get("fade_out", 0))),
        music=music,
    )
    output = _path(base, data.get("sortie", data.get("output", "montage.mp4")))
    return segments, output, options


def render_project(path: str, output: str = None) -> Tuple[str, float]:
    segments, default_output, options = load_project(path)
    output = output or default_output
    duration = render_segments(segments, output, options)
    return output, duration
