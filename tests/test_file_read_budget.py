"""Grok Build-compatible limits for model-facing file reads."""

from agent.tools.file import FileTool
from agent.core.extended_tool_executor import ExtendedToolExecutor


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


def test_read_file_coerces_string_or_float_offset_to_int(tmp_path) -> None:
    path = tmp_path / "numbered.txt"
    path.write_text(
        "".join(f"line {index}\n" for index in range(1, 21)), encoding="utf-8"
    )

    success, content = FileTool.read_file(str(path), offset="10", limit=5)
    assert success is True
    assert "10\u2192line 10" in content
    assert "line 14" in content
    assert "line 15" not in content

    success, content = FileTool.read_file(str(path), offset=10.0, limit=5)
    assert success is True
    assert "10\u2192line 10" in content


def test_read_file_rejects_non_numeric_offset_and_limit(tmp_path) -> None:
    path = tmp_path / "numbered.txt"
    path.write_text("line\n", encoding="utf-8")

    success, content = FileTool.read_file(str(path), offset="abc")
    assert success is False
    assert "positive integers" in content

    success, content = FileTool.read_file(str(path), limit="abc")
    assert success is False
    assert "positive integers" in content


def test_read_file_rejects_image_files(tmp_path) -> None:
    for name in ("photo.png", "photo.JPG", "anim.gif", "pic.webp", "img.bmp", "scan.tiff"):
        path = tmp_path / name
        path.write_bytes(b"\x89PNG\r\n\x1a\nnot a real image")

        success, content = FileTool.read_file(str(path))

        assert success is False
        assert "Cannot read image file" in content
        assert "can only read document files" in content


def test_read_file_still_reads_text_based_svg(tmp_path) -> None:
    path = tmp_path / "logo.svg"
    path.write_text("<svg><rect /></svg>", encoding="utf-8")

    success, content = FileTool.read_file(str(path))

    assert success is True
    assert "<svg><rect /></svg>" in content


def test_execute_file_read_rejects_image_files(tmp_path) -> None:
    image = tmp_path / "photo.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nnot a real image")
    executor = ExtendedToolExecutor(project_root=tmp_path, preview_manager=object())

    result = executor.execute_file_read({"filePath": str(image)})

    assert result.startswith("Error: Cannot read image file")
    assert "can only read document files" in result
