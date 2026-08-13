"""JCodex desktop UI - skill management RPC."""

import base64
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

import eel

from agent.ui.desktop import constants, helpers, runtime


@eel.expose
def list_skills():
    """List installed skills using the explicit built-in allowlist."""
    try:
        skills: dict[str, dict] = {}
        for location, skills_path in _installed_skill_roots():
            if not skills_path.exists():
                continue
            for skill_dir in skills_path.iterdir():
                if not _is_skill_directory(skill_dir):
                    continue
                metadata = _skill_directory_metadata(skill_dir)
                skills[skill_dir.name] = {
                    **metadata,
                    "builtin": skill_dir.name in constants.BUILTIN_SKILL_NAMES,
                    "location": location,
                }

        return sorted(
            skills.values(),
            key=lambda skill: (
                not bool(skill["builtin"]),
                str(skill["name"]).casefold(),
            ),
        )
    except Exception as e:
        print(f"Error listing skills: {e}")
        return []


def _installed_skill_roots() -> tuple[tuple[str, Path], ...]:
    """Return installed roots in override order (workspace wins)."""
    return (
        ("agent", constants.PROJECT_ROOT / "agent" / "skills"),
        ("workspace", constants.DATA_ROOT / "workspace" / "skills"),
    )


def _valid_skill_name(skill_name: object) -> bool:
    name = str(skill_name or "")
    return bool(name) and Path(name).name == name and name not in {".", ".."}


def _is_skill_directory(skill_dir: Path) -> bool:
    return (
        skill_dir.is_dir()
        and not skill_dir.is_symlink()
        and _valid_skill_name(skill_dir.name)
        and (skill_dir / "SKILL.md").is_file()
    )


def _skill_directory_metadata(skill_dir: Path) -> dict[str, str]:
    """Read the small display metadata needed by the desktop UI."""
    metadata = {"name": skill_dir.name, "description": ""}
    try:
        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return metadata
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.strip() == "description":
                metadata["description"] = value.strip().strip("\"'")
                break
    except (OSError, UnicodeError):
        pass
    return metadata


def _find_installed_skill_dir(skill_name: str) -> Path | None:
    """Find the active installed copy, preferring workspace skills."""
    for _, root in reversed(_installed_skill_roots()):
        skill_dir = root / skill_name
        if _is_skill_directory(skill_dir):
            return skill_dir
    return None


def _skill_store_root() -> Path:
    """Resolve the local catalog folder, optionally overridden by the environment."""
    configured = os.getenv("SKILL_STORE_PATH", "").strip()
    if configured:
        configured_path = Path(configured).expanduser()
        return (
            configured_path
            if configured_path.is_absolute()
            else constants.PROJECT_ROOT / configured_path
        )
    return constants.DATA_ROOT / "workspace" / "skill-store"


def _validate_store_skill_tree(source: Path) -> None:
    """Reject links and unexpectedly large catalog entries before copying."""
    file_count = 0
    total_bytes = 0
    for item in source.rglob("*"):
        if item.is_symlink():
            raise ValueError("Skill store entries cannot contain symbolic links")
        if not item.is_file():
            continue
        file_count += 1
        if file_count > constants.MAX_SKILL_IMPORT_FILES:
            raise ValueError("Skill folder has too many files")
        file_size = item.stat().st_size
        if file_size > constants.MAX_SKILL_IMPORT_FILE_BYTES:
            raise ValueError("A skill file exceeds the 12 MB limit")
        total_bytes += file_size
        if total_bytes > constants.MAX_SKILL_IMPORT_BYTES:
            raise ValueError("Skill folder exceeds the 30 MB limit")


def _sync_nonbuiltin_skills_to_store(store_root: Path) -> None:
    """Seed missing catalog entries from installed non-built-in skills."""
    installed: dict[str, Path] = {}
    for _, skills_root in _installed_skill_roots():
        if not skills_root.exists():
            continue
        for skill_dir in skills_root.iterdir():
            if _is_skill_directory(skill_dir):
                installed[skill_dir.name] = skill_dir

    with runtime._skill_import_lock:
        for name, source in installed.items():
            if name in constants.BUILTIN_SKILL_NAMES:
                continue
            destination = helpers._resolve_within(store_root, name)
            if destination.exists():
                continue
            _validate_store_skill_tree(source)
            staging_dir = Path(tempfile.mkdtemp(prefix=".skill-store-seed-", dir=store_root))
            try:
                shutil.copytree(source, staging_dir, dirs_exist_ok=True)
                staging_dir.replace(destination)
            except Exception:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise


@eel.expose
def list_skill_store():
    """List catalog entries without modifying the installed skills directory."""
    try:
        store_root = _skill_store_root()
        store_root.mkdir(parents=True, exist_ok=True)
        _sync_nonbuiltin_skills_to_store(store_root)
        entries = []
        for skill_dir in store_root.iterdir():
            if not _is_skill_directory(skill_dir):
                continue
            name = skill_dir.name
            entries.append(
                {
                    **_skill_directory_metadata(skill_dir),
                    "installed": _find_installed_skill_dir(name) is not None,
                    "builtin": name in constants.BUILTIN_SKILL_NAMES,
                }
            )
        return sorted(entries, key=lambda entry: str(entry["name"]).casefold())
    except (OSError, ValueError) as exc:
        return {"error": str(exc), "skills": []}


@eel.expose
def install_store_skill(skill_name: str):
    """Copy one catalog skill into workspace/skills, keeping the catalog intact."""
    if not _valid_skill_name(skill_name):
        return {"success": False, "error": "Invalid skill name"}

    try:
        store_root = _skill_store_root()
        source = helpers._resolve_within(store_root, skill_name)
        if not _is_skill_directory(source):
            return {"success": False, "error": "Skill not found in store"}
        _validate_store_skill_tree(source)

        skills_dir = helpers._resolve_within(constants.DATA_ROOT / "workspace", "skills")
        skills_dir.mkdir(parents=True, exist_ok=True)
        destination = helpers._resolve_within(skills_dir, skill_name)
        with runtime._skill_import_lock:
            if _find_installed_skill_dir(skill_name) is not None:
                return {
                    "success": False,
                    "error": f"Skill '{skill_name}' is already installed",
                }
            staging_dir = Path(tempfile.mkdtemp(prefix=".skill-store-install-", dir=skills_dir))
            try:
                shutil.copytree(source, staging_dir, dirs_exist_ok=True)
                staging_dir.replace(destination)
            except Exception:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise
        return {"success": True, "name": skill_name}
    except (OSError, ValueError) as exc:
        return {"success": False, "error": str(exc)}


@eel.expose
def open_skill_store_folder():
    """Open the backing catalog folder in the platform file manager."""
    try:
        store_root = _skill_store_root()
        store_root.mkdir(parents=True, exist_ok=True)
        abs_path = str(store_root.resolve())
        if platform.system() == "Darwin":
            subprocess.run(["open", abs_path], check=False)
        elif platform.system() == "Windows":
            os.startfile(abs_path)
        else:
            subprocess.run(["xdg-open", abs_path], check=False)
        return {"success": True, "path": abs_path}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@eel.expose
def open_skill_folder(skill_name: str):
    """打开skill文件夹"""
    try:
        import platform
        import subprocess

        if not _valid_skill_name(skill_name):
            return {"success": False, "error": "Invalid skill name"}
        skill_path = _find_installed_skill_dir(skill_name)
        if skill_path is None:
            return {"success": False, "error": "Skill not found"}

        abs_path = str(skill_path.resolve())

        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", abs_path])
        elif platform.system() == "Windows":
            os.startfile(abs_path)
        else:  # Linux
            subprocess.run(["xdg-open", abs_path])

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _decode_skill_import_file(data_url: object) -> bytes:
    """Decode one browser-selected skill file without accepting arbitrary URLs."""
    if not isinstance(data_url, str) or "," not in data_url:
        raise ValueError("Invalid skill file data")
    header, encoded = data_url.split(",", 1)
    if not header.lower().endswith(";base64"):
        raise ValueError("Skill files must use base64 encoding")
    try:
        return base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("Skill file data is invalid") from exc


def _skill_import_path(value: object) -> tuple[str, PurePosixPath]:
    """Validate a relative browser folder path and return its skill name."""
    provided_path = str(value or "")
    if "\\" in provided_path:
        raise ValueError("Invalid skill folder path")
    raw_path = provided_path.strip("/")
    path = PurePosixPath(raw_path)
    if (
        not raw_path
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or len(path.parts) < 2
    ):
        raise ValueError("Invalid skill folder path")
    skill_name = path.parts[0]
    if Path(skill_name).name != skill_name:
        raise ValueError("Invalid skill folder name")
    if any(
        part.startswith(".") or part in constants._SKILL_IMPORT_IGNORED_PARTS
        for part in path.parts[1:]
    ):
        raise ValueError("Skill folder contains unsupported hidden or dependency files")
    return skill_name, path


@eel.expose
def import_skill_folder(files: object):
    """Import one browser-selected skill folder into ``workspace/skills``."""
    if not isinstance(files, list) or not files:
        return {"success": False, "error": "Please select a skill folder"}
    if len(files) > constants.MAX_SKILL_IMPORT_FILES:
        return {"success": False, "error": "Skill folder has too many files"}

    try:
        imported_files: list[tuple[PurePosixPath, bytes]] = []
        imported_paths: set[PurePosixPath] = set()
        skill_name = ""
        total_bytes = 0
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("Invalid skill file")
            item_skill_name, relative_path = _skill_import_path(item.get("path"))
            if skill_name and item_skill_name != skill_name:
                raise ValueError("Select exactly one skill folder")
            skill_name = item_skill_name
            content = _decode_skill_import_file(item.get("data"))
            if len(content) > constants.MAX_SKILL_IMPORT_FILE_BYTES:
                raise ValueError("A skill file exceeds the 12 MB limit")
            total_bytes += len(content)
            if total_bytes > constants.MAX_SKILL_IMPORT_BYTES:
                raise ValueError("Skill folder exceeds the 30 MB limit")
            if relative_path in imported_paths:
                raise ValueError("Skill folder contains duplicate files")
            imported_paths.add(relative_path)
            imported_files.append((relative_path, content))

        if not any(path.parts[1:] == ("SKILL.md",) for path, _ in imported_files):
            raise ValueError("SKILL.md not found in selected folder")

        skills_dir = helpers._resolve_within(constants.DATA_ROOT / "workspace", "skills")
        skills_dir.mkdir(parents=True, exist_ok=True)
        destination = helpers._resolve_within(skills_dir, skill_name)
        with runtime._skill_import_lock:
            if _find_installed_skill_dir(skill_name) is not None:
                return {
                    "success": False,
                    "error": f"Skill '{skill_name}' already exists",
                }
            staging_dir = Path(tempfile.mkdtemp(prefix=".skill-import-", dir=skills_dir))
            try:
                for relative_path, content in imported_files:
                    target = helpers._resolve_within(staging_dir, *relative_path.parts[1:])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                staging_dir.replace(destination)
            except Exception:
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise
        return {"success": True, "name": skill_name}
    except (OSError, ValueError) as exc:
        return {"success": False, "error": str(exc)}


@eel.expose
def delete_skill(skill_name: str):
    """Delete installed non-built-in copies without touching the store."""
    try:
        if not _valid_skill_name(skill_name):
            return {"success": False, "error": "Invalid skill name"}
        if skill_name in constants.BUILTIN_SKILL_NAMES:
            return {"success": False, "error": "Cannot delete built-in skill"}

        targets = [
            root / skill_name
            for _, root in _installed_skill_roots()
            if _is_skill_directory(root / skill_name)
        ]
        if not targets:
            return {"success": False, "error": "Skill not found"}
        with runtime._skill_import_lock:
            for skill_path in targets:
                shutil.rmtree(skill_path)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


__all__ = [
    "_decode_skill_import_file",
    "_find_installed_skill_dir",
    "_installed_skill_roots",
    "_is_skill_directory",
    "_skill_directory_metadata",
    "_skill_import_path",
    "_skill_store_root",
    "_sync_nonbuiltin_skills_to_store",
    "_valid_skill_name",
    "_validate_store_skill_tree",
    "delete_skill",
    "import_skill_folder",
    "install_store_skill",
    "list_skill_store",
    "list_skills",
    "open_skill_folder",
    "open_skill_store_folder",
]
