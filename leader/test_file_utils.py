from leader.file_utils import create_snapshot, gather_codebase, latest_snapshot, restore_snapshot


def test_gather_codebase(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "ignore.bin").write_bytes(b"\x00\x01\x02")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("...", encoding="utf-8")

    res = gather_codebase(tmp_path)
    assert "main.py" in res
    assert "ignore.bin" not in res
    assert ".git" not in res
    assert "print('hello')" in res


def test_gather_codebase_max_bytes(tmp_path, capsys):
    (tmp_path / "large1.py").write_text("a" * 600, encoding="utf-8")
    (tmp_path / "large2.py").write_text("a" * 600, encoding="utf-8")

    # If max bytes is 1000, it will append the file that crosses the threshold, print warning, and return
    res = gather_codebase(tmp_path, max_bytes=1000)
    assert "large1.py" in res or "large2.py" in res
    captured = capsys.readouterr()
    assert "Codebase truncated!" in captured.out


def test_snapshot_restore(tmp_path):
    f = tmp_path / "main.py"
    f.write_text("original", encoding="utf-8")

    snap = create_snapshot(tmp_path, [f])
    assert snap.exists()
    assert latest_snapshot(tmp_path) == snap

    f.write_text("modified", encoding="utf-8")

    restored = restore_snapshot(snap, tmp_path)
    assert restored == 1
    assert f.read_text(encoding="utf-8") == "original"
