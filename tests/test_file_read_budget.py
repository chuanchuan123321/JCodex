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
    # The window was cut by the line cap, so the footer teaches the next offset.
    assert "Use offset=1001 to continue." in content


def test_read_file_truncates_an_oversized_single_line(tmp_path) -> None:
    path = tmp_path / "minified.json"
    source = "x" * 100_004
    path.write_text(source, encoding="utf-8")

    success, content = FileTool.read_file(str(path))

    assert success is True
    assert "(line truncated to 2000 chars)" in content
    assert source not in content
    assert "(End of file - total 1 lines)" in content


def test_read_file_partial_window_when_token_budget_exceeded(tmp_path) -> None:
    # A window whose full content would exceed the token budget now returns the
    # partial window that fits, plus a continuation footer, instead of refusing.
    path = tmp_path / "budget.txt"
    path.write_text(
        "".join(f"{'y' * 800} {index}\n" for index in range(1, 300)),
        encoding="utf-8",
    )

    success, content = FileTool.read_file(str(path))

    assert success is True
    assert "exceeds maximum allowed tokens" not in content
    assert "Use offset=" in content
    assert "to continue." in content


def test_read_file_end_of_file_footer(tmp_path) -> None:
    path = tmp_path / "small.txt"
    path.write_text(
        "".join(f"line {index}\n" for index in range(1, 21)), encoding="utf-8"
    )

    success, content = FileTool.read_file(str(path))

    assert success is True
    assert content.endswith("(End of file - total 20 lines)")


def test_read_file_empty_file_is_a_valid_read(tmp_path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")

    success, content = FileTool.read_file(str(path))

    assert success is True
    assert content == "(End of file - total 0 lines)"


def test_read_file_offset_beyond_empty_file_still_errors(tmp_path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")

    success, content = FileTool.read_file(str(path), offset=5)

    assert success is False
    assert "out of range" in content


def test_read_file_continue_footer_for_focused_range(tmp_path) -> None:
    path = tmp_path / "numbered.txt"
    path.write_text(
        "".join(f"line {index}\n" for index in range(1, 51)), encoding="utf-8"
    )

    success, content = FileTool.read_file(str(path), offset=10, limit=5)

    assert success is True
    assert "10\u2192line 10" in content
    assert content.endswith("(Showing lines 10-14. Use offset=15 to continue.)")


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


# ── Read/write version staleness ───────────────────────────────────────────


def test_edit_rejected_when_file_changed_since_read(tmp_path) -> None:
    path = tmp_path / "target.txt"
    path.write_text("old content\n", encoding="utf-8")
    executor = ExtendedToolExecutor(project_root=tmp_path, preview_manager=object())

    read_result = executor.execute_file_read({"filePath": str(path)})
    assert not read_result.startswith("Error:")

    # The file changes on disk without another read (e.g. an external process).
    path.write_text("brand new content\n", encoding="utf-8")

    result = executor.execute(
        {
            "tool": "edit",
            "params": {
                "filePath": str(path),
                "oldString": "brand new content",
                "newString": "changed",
            },
        }
    )

    assert result.startswith("Error:")
    assert "changed since it was read" in result
    assert "Re-read the file" in result
    # The stale edit must not have mutated the file.
    assert path.read_text(encoding="utf-8") == "brand new content\n"


def test_edit_allowed_when_file_unchanged_since_read(tmp_path) -> None:
    path = tmp_path / "target.txt"
    path.write_text("old content\n", encoding="utf-8")
    executor = ExtendedToolExecutor(project_root=tmp_path, preview_manager=object())

    executor.execute_file_read({"filePath": str(path)})

    result = executor.execute(
        {
            "tool": "edit",
            "params": {
                "filePath": str(path),
                "oldString": "old content",
                "newString": "new content",
            },
        }
    )

    assert not result.startswith("Error: changed since it was read")
    assert path.read_text(encoding="utf-8") == "new content\n"


def test_write_to_unread_new_file_is_allowed(tmp_path) -> None:
    executor = ExtendedToolExecutor(project_root=tmp_path, preview_manager=object())
    target = tmp_path / "fresh.txt"

    result = executor.execute(
        {"tool": "write", "params": {"path": str(target), "content": "hello"}}
    )

    assert not result.startswith("Error: changed since it was read")
    assert target.read_text(encoding="utf-8") == "hello"


def test_edit_after_successful_write_is_not_stale(tmp_path) -> None:
    # A successful mutation refreshes the recorded version, so the read->write
    # ->edit sequence must not be rejected as stale.
    executor = ExtendedToolExecutor(project_root=tmp_path, preview_manager=object())
    target = tmp_path / "fresh.txt"

    executor.execute_file_read({"filePath": str(target)})
    executor.execute(
        {"tool": "write", "params": {"path": str(target), "content": "hello\n"}}
    )

    result = executor.execute(
        {
            "tool": "edit",
            "params": {
                "filePath": str(target),
                "oldString": "hello",
                "newString": "hello world",
            },
        }
    )

    assert not result.startswith("Error: changed since it was read")
    assert target.read_text(encoding="utf-8") == "hello world\n"


def test_multiple_edits_after_single_read_are_not_stale(tmp_path) -> None:
    # One read unlocks an arbitrary sequence of edits on the same file: every
    # successful edit refreshes the recorded version, so later edits are not
    # mistaken for stale targets.
    path = tmp_path / "target.txt"
    path.write_text("line1\nline2\nline3\n", encoding="utf-8")
    executor = ExtendedToolExecutor(project_root=tmp_path, preview_manager=object())

    executor.execute_file_read({"filePath": str(path)})

    for old, new in (("line1", "A"), ("line2", "B"), ("line3", "C")):
        result = executor.execute(
            {
                "tool": "edit",
                "params": {
                    "filePath": str(path),
                    "oldString": old,
                    "newString": new,
                },
            }
        )
        assert not result.startswith("Error: changed since it was read"), result

    assert path.read_text(encoding="utf-8") == "A\nB\nC\n"


def test_write_overwrites_file_changed_since_read(tmp_path) -> None:
    # A whole-file write replaces everything, so it is not treated as stale
    # even when the target changed on disk after the last read.
    path = tmp_path / "target.txt"
    path.write_text("old content\n", encoding="utf-8")
    executor = ExtendedToolExecutor(project_root=tmp_path, preview_manager=object())

    executor.execute_file_read({"filePath": str(path)})

    # The file changes on disk without another read (e.g. the user edited it).
    path.write_text("user edited\n", encoding="utf-8")

    result = executor.execute(
        {
            "tool": "write",
            "params": {"path": str(path), "content": "agent output\n"},
        }
    )

    assert not result.startswith("Error: changed since it was read")
    assert path.read_text(encoding="utf-8") == "agent output\n"

