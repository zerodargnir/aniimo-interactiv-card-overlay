from __future__ import annotations

from aniimo_overlay import config as cfg


def test_defaults_when_missing(tmp_path):
    c = cfg.load(tmp_path / "nope.toml")
    assert c.site.url == cfg.DEFAULT_URL
    assert c.hotkeys.toggle_visible == "<f8>"
    assert c.detection.auto is False


def test_roundtrip(tmp_path):
    path = tmp_path / "config.toml"
    c = cfg.Config()
    c.window.x = 42
    c.window.opacity = 0.5
    c.hotkeys.detect = "<ctrl>+d"
    c.capture.roi = [1, 2, 300, 400]
    c.detection.blue_hsv = [[90, 100, 100], [125, 255, 255]]
    cfg.save(c, path)
    loaded = cfg.load(path)
    assert loaded == c


def test_none_roi_not_written(tmp_path):
    path = tmp_path / "config.toml"
    cfg.save(cfg.Config(), path)
    assert "roi" not in path.read_text()
    assert cfg.load(path).capture.roi is None


def test_partial_file_keeps_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[window]\nx = 7\n\n[unknown]\nfoo = 1\n")
    c = cfg.load(path)
    assert c.window.x == 7
    assert c.window.y == 100
    assert c.hotkeys.zoom_in == "<ctrl>+<alt>+<right>"


def test_invalid_values_fall_back(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[window]\nx = "left"\nopacity = 5\nstart_visible = 1\n'
        "[detection]\norange_hsv = [[1, 2], [3, 4]]\ninterval_s = 3\n"
    )
    c = cfg.load(path)
    assert c.window.x == 100
    assert c.window.opacity == 1.0  # clamped
    assert c.window.start_visible is False
    assert c.detection.orange_hsv == cfg.DetectionConfig().orange_hsv
    assert c.detection.interval_s == 3.0
    assert isinstance(c.detection.interval_s, float)


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("this is [not toml")
    c = cfg.load(path)
    assert c == cfg.Config()
    assert not path.exists()
    assert (tmp_path / "config.toml.bak").read_text() == "this is [not toml"


def test_clamping(tmp_path):
    c = cfg.Config()
    c.window.zoom = 9
    c.window.opacity = 0.01
    c.detection.interval_s = 0.1
    c.clamp()
    assert c.window.zoom == cfg.ZOOM_MAX
    assert c.window.opacity == cfg.OPACITY_MIN
    assert c.detection.interval_s == cfg.INTERVAL_MIN
