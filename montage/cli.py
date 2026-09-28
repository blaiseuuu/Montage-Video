"""Interface en ligne de commande : ``montage <commande> ...``."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__, ffmpeg
from .engine import (
    RenderOptions,
    Segment,
    detect_silences,
    render_segments,
    speech_segments,
)
from .presets import FIT_MODES, PRESETS
from .project import render_project


def _default_output(path: str, suffix: str) -> str:
    root, _ = os.path.splitext(path)
    return f"{root}_{suffix}.mp4"


def _add_render_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-f", "--format", default="source", choices=list(PRESETS),
                   help="format d'export (défaut : source)")
    p.add_argument("--adaptation", default="pad", choices=list(FIT_MODES),
                   help="pad = bandes noires, crop = recadrage (défaut : pad)")
    p.add_argument("--rapide", action="store_true",
                   help="encodage plus rapide, fichier un peu plus lourd")


def _options(args) -> RenderOptions:
    return RenderOptions(
        preset=args.format,
        fit=args.adaptation,
        x264_preset="veryfast" if args.rapide else "medium",
    )


def _done(output: str, duration: float) -> None:
    print(f"✔ {output} ({ffmpeg.format_time(duration)})")


def cmd_info(args) -> None:
    for path in args.fichiers:
        info = ffmpeg.probe(path)
        res = f"{info.width}x{info.height}" if info.width else "—"
        fps = f"{info.fps:g} i/s" if info.fps else "—"
        audio = "oui" if info.has_audio else "non"
        print(f"{path}\n  durée : {ffmpeg.format_time(info.duration)}  "
              f"résolution : {res}  cadence : {fps}  audio : {audio}")


def cmd_couper(args) -> None:
    start = ffmpeg.parse_time(args.debut)
    end = ffmpeg.parse_time(args.fin) if args.fin else None
    output = args.sortie or _default_output(args.fichier, "extrait")
    _done(output, render_segments([Segment(args.fichier, start, end)], output, _options(args)))


def cmd_assembler(args) -> None:
    segments = [Segment(path) for path in args.fichiers]
    options = _options(args)
    options.fade_in = options.fade_out = args.fondu
    _done(args.sortie, render_segments(segments, args.sortie, options))


def cmd_silences(args) -> None:
    if args.analyser:
        silences = detect_silences(args.fichier, args.seuil, args.duree_min)
        total = sum(e - s for s, e in silences)
        for s, e in silences:
            print(f"  {ffmpeg.format_time(s)} → {ffmpeg.format_time(e)}  ({e - s:.2f} s)")
        print(f"{len(silences)} silence(s), {total:.1f} s au total.")
        return
    segments = speech_segments(args.fichier, args.seuil, args.duree_min, args.marge)
    if not segments:
        sys.exit("Aucun passage parlé détecté : essayez un seuil plus bas (ex. -45).")
    before = ffmpeg.probe(args.fichier).duration
    output = args.sortie or _default_output(args.fichier, "sans_silences")
    after = render_segments(segments, output, _options(args))
    _done(output, after)
    print(f"  {len(segments)} passage(s) gardé(s), {before - after:.1f} s supprimée(s).")


def cmd_exporter(args) -> None:
    output = args.sortie or _default_output(args.fichier, args.format)
    _done(output, render_segments([Segment(args.fichier)], output, _options(args)))


def cmd_projet(args) -> None:
    output, duration = render_project(args.projet, args.sortie)
    _done(output, duration)


def cmd_formats(args) -> None:
    for name, preset in PRESETS.items():
        print(f"  {name:<20} {preset.description}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="montage",
        description="Outils pour accélérer le montage vidéo (basés sur FFmpeg).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="commande", required=True)

    p = sub.add_parser("info", help="afficher durée, résolution, cadence")
    p.add_argument("fichiers", nargs="+")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("couper", help="extraire un passage d'une vidéo")
    p.add_argument("fichier")
    p.add_argument("-d", "--debut", default="0", help="ex. 1:05 ou 65")
    p.add_argument("-t", "--fin", help="ex. 2:30 (défaut : fin du fichier)")
    p.add_argument("-o", "--sortie")
    _add_render_options(p)
    p.set_defaults(func=cmd_couper)

    p = sub.add_parser("assembler", help="mettre plusieurs vidéos bout à bout")
    p.add_argument("fichiers", nargs="+")
    p.add_argument("-o", "--sortie", required=True)
    p.add_argument("--fondu", type=float, default=0.0,
                   help="fondu d'entrée et de sortie en secondes")
    _add_render_options(p)
    p.set_defaults(func=cmd_assembler)

    p = sub.add_parser("silences", help="couper automatiquement les silences (jump cuts)")
    p.add_argument("fichier")
    p.add_argument("-o", "--sortie")
    p.add_argument("--seuil", type=float, default=-35.0,
                   help="niveau (dB) sous lequel c'est un silence (défaut : -35)")
    p.add_argument("--duree-min", type=float, default=0.6,
                   help="durée minimale d'un silence à couper, en s (défaut : 0.6)")
    p.add_argument("--marge", type=float, default=0.15,
                   help="marge gardée autour de la parole, en s (défaut : 0.15)")
    p.add_argument("--analyser", action="store_true",
                   help="lister les silences sans générer de vidéo")
    _add_render_options(p)
    p.set_defaults(func=cmd_silences)

    p = sub.add_parser("exporter", help="convertir vers un format (YouTube, Shorts…)")
    p.add_argument("fichier")
    p.add_argument("-o", "--sortie")
    _add_render_options(p)
    p.set_defaults(func=cmd_exporter)

    p = sub.add_parser("projet", help="rendre un montage décrit dans un fichier YAML")
    p.add_argument("projet")
    p.add_argument("-o", "--sortie", help="remplace la sortie définie dans le projet")
    p.set_defaults(func=cmd_projet)

    p = sub.add_parser("formats", help="lister les formats d'export")
    p.set_defaults(func=cmd_formats)
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (ffmpeg.FFmpegError, ValueError, OSError) as exc:
        sys.exit(f"Erreur : {exc}")


if __name__ == "__main__":
    main()
