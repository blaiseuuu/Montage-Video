"""Formats d'export prêts à l'emploi."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Preset:
    name: str
    width: Optional[int]
    height: Optional[int]
    fps: Optional[int]
    crf: int = 20
    description: str = ""


PRESETS = {
    "source": Preset("source", None, None, None, description="Résolution du premier clip"),
    "youtube": Preset("youtube", 1920, 1080, 30, description="16:9 Full HD, 30 i/s"),
    "youtube-4k": Preset("youtube-4k", 3840, 2160, 30, crf=18, description="16:9 4K, 30 i/s"),
    "shorts": Preset("shorts", 1080, 1920, 30, description="9:16 YouTube Shorts / TikTok / Reels"),
    "instagram": Preset("instagram", 1080, 1080, 30, description="1:1 carré Instagram"),
    "instagram-portrait": Preset("instagram-portrait", 1080, 1350, 30, description="4:5 Instagram"),
    "brouillon": Preset("brouillon", 1280, 720, 30, crf=28, description="720p rapide pour relecture"),
}

# Manière d'adapter une image à un format différent.
FIT_MODES = {
    "pad": "bandes noires, toute l'image reste visible",
    "crop": "recadrage centré pour remplir le cadre",
}


def get_preset(name: str) -> Preset:
    try:
        return PRESETS[name]
    except KeyError:
        choices = ", ".join(PRESETS)
        raise ValueError(f"Format inconnu « {name} ». Choix possibles : {choices}") from None
