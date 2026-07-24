"""Grok Build-compatible limits for model-facing file reads."""

from agent.tools.file import FileTool


def test_read_file_caps_each_window_at_one_thousand_lines(tmp_path) -> None:
    path = tmp_path / "large.txt"
    path.write_text(
        "".join(f"line {index}\n" for index in range(1, 1201)), encoding="utf-8"
    )

    success, content = FileTool.read_file(str(path), limit=5000)

    assert success is True
    assert "1\u2192line 1" in content
    assert "10\u2192line 10" in content
    assert "line 11" in content
    assert "1000\u2192line 1000" in content
    assert "line 1001" not in content


def test_read_file_rejects_an_oversized_single_line_without_corruption(tmp_path) -> None:
    path = tmp_path / "minified.json"
    source = "x" * 100_004
    path.write_text(source, encoding="utf-8")

    success, content = FileTool.read_file(str(path))

    assert success is False
    assert "exceeds maximum allowed tokens (25000 tokens)" in content
    assert "offset and limit" in content
    assert source not in content
