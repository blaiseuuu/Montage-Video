import pytest

from montage import ffmpeg
from montage.cli import main
from montage.engine import RenderOptions, Segment, render_segments, speech_segments
from montage.project import load_project, render_project


@pytest.mark.parametrize(
    "value,expected",
    [(90, 90.0), ("90", 90.0), ("90s", 90.0), ("1:30", 90.0), ("00:01:30.5", 90.5)],
)
def test_parse_time(value, expected):
    assert ffmpeg.parse_time(value) == expected


def test_parse_time_invalide():
    with pytest.raises(ValueError):
        ffmpeg.parse_time("abc")


def test_probe(video):
    info = ffmpeg.probe(video(duration=2))
    assert info.width == 320 and info.height == 240
    assert info.has_audio and info.has_video
    assert info.duration == pytest.approx(2.0, abs=0.1)


def test_couper(video, tmp_path):
    out = tmp_path / "extrait.mp4"
    main(["couper", video(duration=3), "-d", "0.5", "-t", "2", "-o", str(out), "--rapide"])
    assert ffmpeg.probe(str(out)).duration == pytest.approx(1.5, abs=0.1)


def test_assembler_resolutions_et_audio_differents(video, tmp_path):
    a = video("a.mp4", duration=1, size="320x240")
    b = video("b.mp4", duration=1.5, size="240x320", audio="none", color="red")
    out = tmp_path / "assemble.mp4"
    main(["assembler", a, b, "-o", str(out), "--rapide", "--fondu", "0.3"])
    info = ffmpeg.probe(str(out))
    assert (info.width, info.height) == (320, 240)
    assert info.has_audio
    assert info.duration == pytest.approx(2.5, abs=0.15)


def test_exporter_shorts_crop(video, tmp_path):
    out = tmp_path / "short.mp4"
    main(["exporter", video(duration=1), "-f", "shorts", "--adaptation", "crop",
          "-o", str(out), "--rapide"])
    info = ffmpeg.probe(str(out))
    assert (info.width, info.height) == (1080, 1920)


def test_silences(video, tmp_path):
    # 1 s de son, 2 s de silence, 1 s de son.
    expr = "'if(lt(t,1)+gt(t,3),0.5*sin(2*PI*440*t),0)'"
    src = video("parole.mp4", duration=4, audio=expr)
    segments = speech_segments(src, padding=0.1)
    assert len(segments) == 2
    out = tmp_path / "sans_silences.mp4"
    duration = render_segments(segments, str(out), RenderOptions(x264_preset="ultrafast"))
    assert duration == pytest.approx(2.2, abs=0.2)
    assert ffmpeg.probe(str(out)).duration == pytest.approx(duration, abs=0.15)


def test_projet_yaml(video, tmp_path):
    video("intro.mp4", duration=2)
    video("musique.mp4", duration=1)
    projet = tmp_path / "projet.yaml"
    projet.write_text(
        "format: brouillon\n"
        "sortie: rendu/final.mp4\n"
        "fondu_entree: 0.2\n"
        "clips:\n"
        "  - source: intro.mp4\n"
        "    debut: 0.5\n"
        "    fin: 1.5\n"
        "  - intro.mp4\n"
        "musique:\n"
        "  source: musique.mp4\n"
        "  volume: 0.2\n",
        encoding="utf-8",
    )
    segments, output, options = load_project(str(projet))
    assert output == str(tmp_path / "rendu" / "final.mp4")
    assert segments[0] == Segment(str(tmp_path / "intro.mp4"), 0.5, 1.5)
    assert options.music.volume == 0.2

    output, duration = render_project(str(projet))
    info = ffmpeg.probe(output)
    assert (info.width, info.height) == (1280, 720)
    assert info.duration == pytest.approx(3.0, abs=0.15)


def test_segment_vide(video, tmp_path):
    with pytest.raises(ValueError):
        render_segments([Segment(video(duration=1), 5, 6)], str(tmp_path / "x.mp4"))
