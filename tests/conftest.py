import pytest

from montage import ffmpeg


def make_video(path, duration=2.0, size="320x240", audio="sine", color="blue"):
    """Génère une vidéo de test. ``audio`` : "sine", "none" ou une expression aevalsrc."""
    args = ["-y", "-f", "lavfi", "-i", f"color=c={color}:s={size}:r=25:d={duration}"]
    if audio == "sine":
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    elif audio != "none":
        args += ["-f", "lavfi", "-i", f"aevalsrc={audio}:s=48000:d={duration}"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if audio != "none":
        args += ["-c:a", "aac", "-shortest"]
    args.append(str(path))
    ffmpeg.run(args)
    return str(path)


@pytest.fixture
def video(tmp_path):
    return lambda name="clip.mp4", **kw: make_video(tmp_path / name, **kw)
