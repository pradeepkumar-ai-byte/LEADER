"""
Leader – File Utilities Tests

Covers codebase gathering, snapshot/restore safety, and edge cases.
"""

import json

import pytest

from leader.file_utils import (
    create_snapshot,
    gather_codebase,
    latest_snapshot,
    restore_snapshot,
)

# ── gather_codebase ──────────────────────────────────────────────────────────


def test_gather_codebase_basic(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "ignore.bin").write_bytes(b"\x00\x01\x02")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("...", encoding="utf-8")

    res = gather_codebase(tmp_path)
    assert "main.py" in res
    assert "ignore.bin" not in res
    assert ".git" not in res
    assert "print('hello')" in res


def test_gather_codebase_respects_ignored_dirs(tmp_path):
    """node_modules, __pycache__, venv should all be ignored."""
    for ignored in ["node_modules", "__pycache__", "venv", ".venv"]:
        d = tmp_path / ignored
        d.mkdir()
        (d / "file.py").write_text("should be ignored", encoding="utf-8")

    (tmp_path / "real.py").write_text("real code", encoding="utf-8")
    res = gather_codebase(tmp_path)
    assert "should be ignored" not in res
    assert "real code" in res


def test_gather_codebase_respects_ignored_extensions(tmp_path):
    """Binary extensions (.pyc, .exe, .jpg, etc.) should be skipped."""
    (tmp_path / "module.pyc").write_bytes(b"\x00\x01")
    (tmp_path / "app.exe").write_bytes(b"\x00\x01")
    (tmp_path / "photo.jpg").write_bytes(b"\x00\x01")
    (tmp_path / "real.py").write_text("real code", encoding="utf-8")

    res = gather_codebase(tmp_path)
    assert "module.pyc" not in res
    assert "app.exe" not in res
    assert "photo.jpg" not in res
    assert "real.py" in res


def test_gather_codebase_max_files(tmp_path):
    """Should stop after max_files."""
    for i in range(10):
        (tmp_path / f"file_{i}.py").write_text(f"content {i}", encoding="utf-8")

    res = gather_codebase(tmp_path, max_files=3)
    # Should contain at most 3 file separators
    count = res.count("--- file_")
    assert count <= 3


def test_gather_codebase_max_bytes(tmp_path, capsys):
    (tmp_path / "large1.py").write_text("a" * 600, encoding="utf-8")
    (tmp_path / "large2.py").write_text("a" * 600, encoding="utf-8")

    res = gather_codebase(tmp_path, max_bytes=1000)
    assert "large1.py" in res or "large2.py" in res
    captured = capsys.readouterr()
    assert "Codebase truncated!" in captured.out


def test_gather_codebase_empty_dir(tmp_path):
    res = gather_codebase(tmp_path)
    assert res == ""


def test_gather_codebase_not_a_dir():
    with pytest.raises(ValueError, match="Not a directory"):
        gather_codebase("/nonexistent/path/that/does/not/exist")


# ── snapshot / restore ───────────────────────────────────────────────────────


def test_snapshot_creates_manifest(tmp_path):
    f = tmp_path / "main.py"
    f.write_text("original", encoding="utf-8")

    snap = create_snapshot(tmp_path, [f])
    manifest_path = snap / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "files" in manifest
    assert "main.py" in manifest["files"]
    assert str(tmp_path.resolve()) == manifest["root"]


def test_snapshot_restore_roundtrip(tmp_path):
    f = tmp_path / "main.py"
    f.write_text("original", encoding="utf-8")

    snap = create_snapshot(tmp_path, [f])
    assert snap.exists()
    assert latest_snapshot(tmp_path) == snap

    f.write_text("modified", encoding="utf-8")

    restored = restore_snapshot(snap, tmp_path)
    assert restored == 1
    assert f.read_text(encoding="utf-8") == "original"


def test_restore_does_not_write_outside_project_root(tmp_path):
    """Path traversal safety: restore should not write files outside the project root."""
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    f = project / "safe.py"
    f.write_text("safe", encoding="utf-8")

    snap = create_snapshot(project, [f])

    # Manually tamper with the manifest to include a path traversal
    manifest_path = snap / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].append("../outside/evil.py")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    # The restore should only restore safe.py, not the traversal path
    restored = restore_snapshot(snap, project)
    assert restored == 1  # Only safe.py
    assert not (outside / "evil.py").exists()


def test_latest_snapshot_returns_none_when_empty(tmp_path):
    result = latest_snapshot(tmp_path)
    assert result is None


def test_multiple_snapshots(tmp_path):
    """latest_snapshot should return the most recent one."""
    f = tmp_path / "main.py"
    f.write_text("v1", encoding="utf-8")
    create_snapshot(tmp_path, [f])

    f.write_text("v2", encoding="utf-8")
    snap2 = create_snapshot(tmp_path, [f])

    latest = latest_snapshot(tmp_path)
    assert latest == snap2
